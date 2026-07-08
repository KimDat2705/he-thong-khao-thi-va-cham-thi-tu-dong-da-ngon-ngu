import base64
import json
import inspect
import logging
import os
import random
import time
import wave
from typing import Optional, List, Dict
from sqlalchemy.orm import Session
from pydantic import BaseModel

from google import genai
from google.genai import types
from app.core.config import settings
from app.models.question import Question
from app.models.question_group import QuestionGroup
from app.services.parser import calculate_question_hash, calculate_group_hash

logger = logging.getLogger(__name__)

# Retry/backoff cho lỗi Gemini TẠM THỜI (500/503 INTERNAL/UNAVAILABLE, 429 quá hạn) khi sinh TEXT —
# nhánh render TTS đã có _tts_with_retry riêng; nhánh text-gen trước đây 1 cú 500 là rớt cả lô
# (đúng gốc sự cố A3 khi Gemini chập chờn). Chỉ thử lại lỗi tạm; lỗi khác (safety, bad-request) raise ngay.
# _call_gemini DÙNG CHUNG với Bản 1 (kể cả endpoint ĐỒNG BỘ /enrich, /paraphrase) → giữ 2 lần thử
# (backoff 1s,2s → tối đa ~3s/_once) để không chặn worker HTTP quá lâu (review S57i).
_GEMINI_TRANSIENT_RETRIES = 2
# Marker CHỮ (KHÔNG dùng '500'/'429' trần — dễ khớp nhầm số trong thông điệp lỗi khác, vd 'token 1500';
# ưu tiên mã lỗi có cấu trúc e.code khi có). review S57i.
_GEMINI_TRANSIENT_MARKERS = ("INTERNAL", "UNAVAILABLE", "RESOURCE_EXHAUSTED", "overloaded", "deadline")

B1_TOPICS = [
    "Bản thân",
    "Nhà cửa-gia đình-môi trường",
    "Cuộc sống hằng ngày",
    "Vui chơi-giải trí",
    "Đi lại-du lịch",
    "Mối quan hệ",
    "Sức khỏe",
    "Giáo dục",
    "Mua bán",
    "Thực phẩm-đồ uống",
    "Các dịch vụ",
    "Địa điểm-địa danh",
    "Ngôn ngữ",
    "Thời tiết"
]

# --- Pydantic Schemas for validation ---

class R1QuestionAI(BaseModel):
    content: str
    options: Dict[str, str]
    reference_answer: str
    difficulty: str
    clo: str
    topic: str
    explanation: Optional[str] = None

class R1BatchAI(BaseModel):
    questions: List[R1QuestionAI]

class R3QuestionAI(BaseModel):
    content: str
    options: Dict[str, str]
    reference_answer: str
    difficulty: str
    clo: str
    explanation: Optional[str] = None

class R3GroupAI(BaseModel):
    passage_text: str
    topic: str
    difficulty: str
    questions: List[R3QuestionAI]

class R3BatchAI(BaseModel):
    groups: List[R3GroupAI]

class R4QuestionAI(BaseModel):
    blank_number: int
    content: str
    reference_answer: str
    difficulty: str
    clo: str
    explanation: Optional[str] = None

class R4GroupAI(BaseModel):
    passage_text: str
    word_box: List[str]
    topic: str
    difficulty: str
    questions: List[R4QuestionAI]

class R4BatchAI(BaseModel):
    groups: List[R4GroupAI]


class R2QuestionAI(BaseModel):
    content: str
    options: Dict[str, str]
    reference_answer: str
    difficulty: str
    clo: str
    topic: str
    explanation: Optional[str] = None


class R2BatchAI(BaseModel):
    questions: List[R2QuestionAI]


class L2QuestionAI(BaseModel):
    blank_number: int
    content: str
    reference_answer: str
    difficulty: str
    clo: str
    explanation: Optional[str] = None


class L2GroupAI(BaseModel):
    script_text: str
    note_template: str
    topic: str
    difficulty: str
    questions: List[L2QuestionAI]


class L2BatchAI(BaseModel):
    groups: List[L2GroupAI]


class WritingSpeakingQuestionAI(BaseModel):
    part: int
    type: str
    content: str
    difficulty: str
    clo: str
    topic: str
    explanation: Optional[str] = None


class WritingSpeakingBatchAI(BaseModel):
    questions: List[WritingSpeakingQuestionAI]


class L1QuestionAI(BaseModel):
    script_text: str
    question_text: str
    description_a: str
    description_b: str
    description_c: str
    reference_answer: str
    difficulty: str
    clo: str
    topic: str
    explanation: Optional[str] = None


class L1BatchAI(BaseModel):
    questions: List[L1QuestionAI]


def _extract_gemini_text(resp) -> tuple:
    """Trích text ĐẦU RA (bỏ phần 'thought') + cờ truncated (finish_reason=MAX_TOKENS) + usage.

    Đọc parts TRỰC TIẾP thay vì tin `resp.text`: khi model chỉ kịp 'thinking' rồi hết budget,
    `resp.text` trả None ÂM THẦM → json.loads vỡ mà không rõ nguyên nhân. Ở đây ta PHÁT HIỆN cắt
    để retry/raise có chủ đích (SPEC-FACTORY-013)."""
    cand = (getattr(resp, "candidates", None) or [None])[0]
    fr = getattr(cand, "finish_reason", None)
    truncated = fr is not None and "MAX_TOKENS" in str(fr)
    content = getattr(cand, "content", None) if cand is not None else None
    parts = (getattr(content, "parts", None) if content is not None else None) or []
    chunks = [p.text for p in parts
              if isinstance(getattr(p, "text", None), str) and not getattr(p, "thought", False)]
    text = "".join(chunks)
    if not text:                       # fallback: resp.text (SDK cũng bỏ thought) — guard None
        try:
            text = resp.text or ""
        except Exception:
            text = ""
    um = getattr(resp, "usage_metadata", None)
    usage = None
    if um is not None:
        usage = {"thoughts": getattr(um, "thoughts_token_count", None),
                 "candidates": getattr(um, "candidates_token_count", None),
                 "total": getattr(um, "total_token_count", None)}
    return text, truncated, usage


class B1QuestionGenerator:
    def __init__(self):
        # Initialize Google GenAI client if API key is present
        if getattr(settings, "GEMINI_API_KEY", None):
            self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
            self.model_name = getattr(settings, "GEMINI_MODEL", "gemini-1.5-flash")
        else:
            self.client = None
            self.model_name = None
            logger.warning("GEMINI_API_KEY is not set. B1 Question Generator will run in mock mode.")

    def _call_gemini(self, system_instruction: str, user_prompt: str,
                     max_output_tokens: Optional[int] = None,
                     thinking_budget: Optional[int] = None) -> str:
        """Gọi Gemini (google-genai Client) → text JSON thô.

        max_output_tokens: trần token đầu ra. Ở Gemini 2.5/3.x token "thinking" + JSON DÙNG CHUNG
        budget này (thinking đo THẬT tới ~9500 token) → trần quá thấp làm JSON bị cắt/méo
        (finish_reason=MAX_TOKENS). None → settings.GEMINI_MAX_OUTPUT_TOKENS; kẹp <=65536 (trần model).
        thinking_budget: giới hạn token suy nghĩ (0=tắt) để nhường chỗ cho JSON — honored trên cả
        2.5 lẫn 3.5-flash (đo THẬT). None → KHÔNG đụng thinking (giữ hành vi mặc định cho các dạng
        ngắn đang chạy tốt). Nếu phát hiện cắt (MAX_TOKENS/text rỗng) → RETRY 1 lần (trần cao hơn +
        thinking=0); vẫn cắt → raise RuntimeError (không drop âm thầm). SPEC-FACTORY-013."""
        if not self.client:
            raise RuntimeError("Gemini client is not initialized.")

        eff_max = int(max_output_tokens if max_output_tokens is not None else settings.GEMINI_MAX_OUTPUT_TOKENS)
        eff_max = max(256, min(eff_max, 65536))     # env override không vượt trần model

        def _once(cap: int, think: Optional[int]) -> tuple:
            cfg_kw = {"response_mime_type": "application/json", "max_output_tokens": cap}
            if think is not None:
                cfg_kw["thinking_config"] = types.ThinkingConfig(thinking_budget=think)
            for attempt in range(_GEMINI_TRANSIENT_RETRIES + 1):
                try:
                    response = self.client.models.generate_content(
                        model=self.model_name,
                        contents=[system_instruction, user_prompt],
                        config=types.GenerateContentConfig(**cfg_kw),
                    )
                    return _extract_gemini_text(response)
                except Exception as e:
                    # Chỉ thử lại lỗi TẠM THỜI (500/503/429). Ưu tiên mã lỗi có cấu trúc (e.code) rồi mới
                    # tới marker chữ; lỗi khác (safety/bad-request) raise ngay.
                    code = getattr(e, "code", None) or getattr(e, "status_code", None)
                    transient = code in (429, 500, 503) or any(t in str(e) for t in _GEMINI_TRANSIENT_MARKERS)
                    if transient and attempt < _GEMINI_TRANSIENT_RETRIES:
                        wait = 2 ** attempt      # 1s, 2s, 4s
                        logger.warning("Gemini lỗi tạm thời (lần %d/%d): %s — thử lại sau %ds",
                                       attempt + 1, _GEMINI_TRANSIENT_RETRIES, str(e)[:120], wait)
                        time.sleep(wait)
                        continue
                    logger.error(f"Gemini API call failed: {e}")
                    raise

        text, truncated, usage = _once(eff_max, thinking_budget)
        if truncated or not text:
            retry_cap = min(65536, max(eff_max * 2, 32768))
            logger.warning("Gemini output bị cắt/rỗng (cap=%s, thinking=%s, usage=%s) — retry cap=%s + thinking=0",
                           eff_max, thinking_budget, usage, retry_cap)
            text, truncated, usage = _once(retry_cap, 0)
            if truncated or not text:
                raise RuntimeError(
                    f"Gemini response truncated (MAX_TOKENS) — JSON không đầy đủ sau retry (usage={usage}).")
        return text

    def generate_r1_questions(self, db: Session, count: int, topic: Optional[str] = None, req_difficulty: Optional[str] = None, seed: Optional[int] = None) -> int:
        """Generate R1 (Part 1 Standalone Choice) questions and save to the bank."""
        if topic and topic not in B1_TOPICS:
            raise ValueError(f"Invalid topic '{topic}'. Must be one of {B1_TOPICS}")

        if not self.client:
            # Mock mode
            rnd = random.Random(seed)
            sig = inspect.signature(self._mock_r1_data)
            if "difficulty" in sig.parameters:
                data = self._mock_r1_data(rnd, count, topic, req_difficulty)
            else:
                data = self._mock_r1_data(rnd, count, topic)
        else:
            system_instruction = (
                "You are an expert English language examiner. Generate a batch of VSTEP B1 Reading Part 1 standalone multiple-choice questions.\n"
                "Each question must test English grammar, vocabulary, or semantics suitable for CEFR B1 level.\n"
                "Provide a gap placeholder '______' in the question content.\n"
                "Options must contain exactly 4 options (A, B, C, D) and reference_answer must be A, B, C, or D.\n"
                "The CLO must be 'Nhận diện' or 'Thông hiểu'.\n"
                + (f"The difficulty must be exactly: {req_difficulty}.\n" if req_difficulty else "The difficulty must be exactly one of: easy, medium, hard.\n") +
                "The topic must be chosen from the 14 valid B1 topics.\n"
                "Return JSON matching the schema:\n"
                "{\n"
                "  \"questions\": [\n"
                "    {\n"
                "      \"content\": \"string\",\n"
                "      \"options\": {\"A\": \"string\", \"B\": \"string\", \"C\": \"string\", \"D\": \"string\"},\n"
                "      \"reference_answer\": \"string\",\n"
                "      \"difficulty\": \"string\",\n"
                "      \"clo\": \"string\",\n"
                "      \"topic\": \"string\",\n"
                "      \"explanation\": \"string\"\n"
                "    }\n"
                "  ]\n"
                "}"
            )
            topic_hint = f"Topic to focus: {topic}" if topic else f"Select randomly from valid B1 topics: {', '.join(B1_TOPICS)}"
            user_prompt = f"Generate {count} questions. {topic_hint}"
            
            try:
                raw_json = self._call_gemini(system_instruction, user_prompt)
                data = json.loads(raw_json)
            except Exception as e:
                logger.error(f"Failed to generate R1 questions via Gemini: {e}. Falling back to Mock.")
                rnd = random.Random(seed)
                sig = inspect.signature(self._mock_r1_data)
                if "difficulty" in sig.parameters:
                    data = self._mock_r1_data(rnd, count, topic, req_difficulty)
                else:
                    data = self._mock_r1_data(rnd, count, topic)

        # Validate and Ingest
        saved_count = 0
        questions_list = data.get("questions", [])
        for q_raw in questions_list:
            try:
                # Schema Validation
                q_validated = R1QuestionAI(**q_raw)
                
                # Semantic / Business Rule Validations
                if q_validated.topic not in B1_TOPICS:
                    logger.warning(f"Invalid topic in generated question: {q_validated.topic}. Skipping.")
                    continue
                if q_validated.clo not in ["Nhận diện", "Thông hiểu"]:
                    logger.warning(f"Invalid CLO for R1: {q_validated.clo}. Skipping.")
                    continue
                if set(q_validated.options.keys()) != {"A", "B", "C", "D"}:
                    logger.warning("R1 question must have exactly A-D options. Skipping.")
                    continue
                if q_validated.reference_answer not in {"A", "B", "C", "D"}:
                    logger.warning(f"Invalid reference_answer: {q_validated.reference_answer}. Skipping.")
                    continue

                # Clean/Map difficulty
                diff_val = q_validated.difficulty.lower()
                difficulty = req_difficulty if req_difficulty in ["easy", "medium", "hard"] else (diff_val if diff_val in ["easy", "medium", "hard"] else "medium")

                # Idempotency checks
                q_data_dict = {
                    "set_id": "",
                    "number": "",
                    "part": 1,
                    "type": "choice",
                    "content": q_validated.content,
                    "options": q_validated.options,
                    "reference_answer": q_validated.reference_answer
                }
                q_hash = calculate_question_hash(q_data_dict)

                existing = db.query(Question).filter(
                    Question.exam_id.is_(None),
                    Question.content_hash == q_hash
                ).first()

                if existing:
                    logger.info("Question already exists in bank (duplicate content_hash). Skipping.")
                    continue

                new_q = Question(
                    exam_id=None,
                    group_id=None,
                    part=1,
                    type="choice",
                    content=q_validated.content,
                    options=q_validated.options,
                    reference_answer=q_validated.reference_answer,
                    difficulty=difficulty,
                    clo=q_validated.clo,
                    topic=q_validated.topic,
                    explanation=q_validated.explanation,
                    status="draft",
                    content_hash=q_hash,
                    exam_type="VSTEP_B1",
                    language="EN"
                )
                db.add(new_q)
                db.commit()
                saved_count += 1
            except Exception as val_err:
                logger.warning(f"Item failed validation: {val_err}. Skipping.")
                db.rollback()

        return saved_count

    def generate_r2_questions(self, db: Session, count: int, topic: Optional[str] = None, req_difficulty: Optional[str] = None, seed: Optional[int] = None) -> int:
        """Generate R2 (Part 2 Standalone Choice - 3 options) questions and save to the bank."""
        if topic and topic not in B1_TOPICS:
            raise ValueError(f"Invalid topic '{topic}'. Must be one of {B1_TOPICS}")

        if not self.client:
            # Mock mode
            rnd = random.Random(seed)
            sig = inspect.signature(self._mock_r2_data)
            if "difficulty" in sig.parameters:
                data = self._mock_r2_data(rnd, count, topic, req_difficulty)
            else:
                data = self._mock_r2_data(rnd, count, topic)
        else:
            system_instruction = (
                "You are an expert English language examiner. Generate a batch of VSTEP B1 Reading Part 2 standalone multiple-choice questions based on short notices, signs, or labels.\n"
                "Each question must contain a short text (notice, message, label) and a question asking for its meaning.\n"
                "Options must contain exactly 3 options (A, B, C) and reference_answer must be A, B, or C.\n"
                "The CLO must be 'Thông hiểu'.\n"
                + (f"The difficulty must be exactly: {req_difficulty}.\n" if req_difficulty else "The difficulty must be exactly one of: easy, medium, hard.\n") +
                "The topic must be chosen from the 14 valid B1 topics.\n"
                "Return JSON matching the schema:\n"
                "{\n"
                "  \"questions\": [\n"
                "    {\n"
                "      \"content\": \"string\",\n"
                "      \"options\": {\"A\": \"string\", \"B\": \"string\", \"C\": \"string\"},\n"
                "      \"reference_answer\": \"string\",\n"
                "      \"difficulty\": \"string\",\n"
                "      \"clo\": \"string\",\n"
                "      \"topic\": \"string\",\n"
                "      \"explanation\": \"string\"\n"
                "    }\n"
                "  ]\n"
                "}"
            )
            topic_hint = f"Topic to focus: {topic}" if topic else f"Select randomly from valid B1 topics: {', '.join(B1_TOPICS)}"
            user_prompt = f"Generate {count} questions. {topic_hint}"
            
            try:
                raw_json = self._call_gemini(system_instruction, user_prompt)
                data = json.loads(raw_json)
            except Exception as e:
                logger.error(f"Failed to generate R2 questions via Gemini: {e}. Falling back to Mock.")
                rnd = random.Random(seed)
                sig = inspect.signature(self._mock_r2_data)
                if "difficulty" in sig.parameters:
                    data = self._mock_r2_data(rnd, count, topic, req_difficulty)
                else:
                    data = self._mock_r2_data(rnd, count, topic)

        # Validate and Ingest
        saved_count = 0
        questions_list = data.get("questions", [])
        for q_raw in questions_list:
            try:
                # Schema Validation
                q_validated = R2QuestionAI(**q_raw)
                
                # Semantic / Business Rule Validations
                if q_validated.topic not in B1_TOPICS:
                    logger.warning(f"Invalid topic in generated question: {q_validated.topic}. Skipping.")
                    continue
                if q_validated.clo != "Thông hiểu":
                    logger.warning(f"Invalid CLO for R2: {q_validated.clo}. Skipping.")
                    continue
                if set(q_validated.options.keys()) != {"A", "B", "C"}:
                    logger.warning("R2 question must have exactly A-C options. Skipping.")
                    continue
                if q_validated.reference_answer not in {"A", "B", "C"}:
                    logger.warning(f"Invalid reference_answer: {q_validated.reference_answer}. Skipping.")
                    continue
                if not q_validated.content or len(q_validated.content.strip()) < 20:
                    logger.warning("Content too short or empty. Skipping.")
                    continue

                # Clean/Map difficulty
                diff_val = q_validated.difficulty.lower()
                difficulty = req_difficulty if req_difficulty in ["easy", "medium", "hard"] else (diff_val if diff_val in ["easy", "medium", "hard"] else "medium")

                # Idempotency checks
                q_data_dict = {
                    "set_id": "",
                    "number": "",
                    "part": 2,
                    "type": "choice",
                    "content": q_validated.content,
                    "options": q_validated.options,
                    "reference_answer": q_validated.reference_answer
                }
                q_hash = calculate_question_hash(q_data_dict)

                existing = db.query(Question).filter(
                    Question.exam_id.is_(None),
                    Question.content_hash == q_hash
                ).first()

                if existing:
                    logger.info("Question already exists in bank (duplicate content_hash). Skipping.")
                    continue

                new_q = Question(
                    exam_id=None,
                    group_id=None,
                    part=2,
                    type="choice",
                    content=q_validated.content,
                    options=q_validated.options,
                    reference_answer=q_validated.reference_answer,
                    difficulty=difficulty,
                    clo=q_validated.clo,
                    topic=q_validated.topic,
                    explanation=q_validated.explanation,
                    status="draft",
                    content_hash=q_hash,
                    exam_type="VSTEP_B1",
                    language="EN"
                )
                db.add(new_q)
                db.commit()
                saved_count += 1
            except Exception as val_err:
                logger.warning(f"Item failed validation: {val_err}. Skipping.")
                db.rollback()

        return saved_count

    def generate_r3_groups(self, db: Session, count: int, topic: Optional[str] = None, req_difficulty: Optional[str] = None, seed: Optional[int] = None) -> int:
        """Generate R3 (Part 3 Passage + 5 Choice Questions) groups and save to the bank."""
        if topic and topic not in B1_TOPICS:
            raise ValueError(f"Invalid topic '{topic}'. Must be one of {B1_TOPICS}")

        if not self.client:
            # Mock mode
            rnd = random.Random(seed)
            sig = inspect.signature(self._mock_r3_data)
            if "difficulty" in sig.parameters:
                data = self._mock_r3_data(rnd, count, topic, req_difficulty)
            else:
                data = self._mock_r3_data(rnd, count, topic)
        else:
            system_instruction = (
                "You are an expert English language examiner. Generate a batch of VSTEP B1 Reading Part 3 question groups.\n"
                "Each group must contain:\n"
                "1. A passage_text of 200-300 words.\n"
                "2. A topic from the 14 valid B1 topics.\n"
                "3. Exactly 5 child questions of 'choice' type based on the passage.\n"
                "Each child question must have options (A, B, C, D), reference_answer (A, B, C, or D), CLO='Thông hiểu'.\n"
                + (f"The difficulty must be exactly: {req_difficulty}.\n" if req_difficulty else "The difficulty must be exactly one of: easy, medium, hard.\n") +
                "Return JSON matching the schema:\n"
                "{\n"
                "  \"groups\": [\n"
                "    {\n"
                "      \"passage_text\": \"string\",\n"
                "      \"topic\": \"string\",\n"
                "      \"difficulty\": \"string\",\n"
                "      \"questions\": [\n"
                "        {\n"
                "          \"content\": \"string\",\n"
                "          \"options\": {\"A\": \"string\", \"B\": \"string\", \"C\": \"string\", \"D\": \"string\"},\n"
                "          \"reference_answer\": \"string\",\n"
                "          \"difficulty\": \"string\",\n"
                "          \"clo\": \"string\",\n"
                "          \"explanation\": \"string\"\n"
                "        }\n"
                "      ]\n"
                "    }\n"
                "  ]\n"
                "}"
            )
            topic_hint = f"Topic to focus: {topic}" if topic else f"Select randomly from valid B1 topics: {', '.join(B1_TOPICS)}"
            user_prompt = f"Generate {count} question groups. {topic_hint}"

            try:
                raw_json = self._call_gemini(system_instruction, user_prompt)
                data = json.loads(raw_json)
            except Exception as e:
                logger.error(f"Failed to generate R3 groups via Gemini: {e}. Falling back to Mock.")
                rnd = random.Random(seed)
                sig = inspect.signature(self._mock_r3_data)
                if "difficulty" in sig.parameters:
                    data = self._mock_r3_data(rnd, count, topic, req_difficulty)
                else:
                    data = self._mock_r3_data(rnd, count, topic)

        # Validate and Ingest
        saved_count = 0
        groups_list = data.get("groups", [])
        for g_raw in groups_list:
            try:
                # Schema Validation
                g_validated = R3GroupAI(**g_raw)

                # Semantic / Business Rule Validations
                if g_validated.topic not in B1_TOPICS:
                    logger.warning(f"Invalid topic in group: {g_validated.topic}. Skipping.")
                    continue
                if len(g_validated.questions) != 5:
                    logger.warning(f"R3 group must contain exactly 5 questions (got {len(g_validated.questions)}). Skipping.")
                    continue

                valid_questions = True
                for q in g_validated.questions:
                    if set(q.options.keys()) != {"A", "B", "C", "D"}:
                        valid_questions = False
                        break
                    if q.reference_answer not in {"A", "B", "C", "D"}:
                        valid_questions = False
                        break
                    if q.clo != "Thông hiểu":
                        valid_questions = False
                        break

                if not valid_questions:
                    logger.warning("One or more child questions failed validation. Skipping entire group.")
                    continue

                # Idempotency check for the group
                g_data_dict = {
                    "set_id": "",
                    "part": 3,
                    "passage_text": g_validated.passage_text,
                    "audio_url": "",
                    "questions": [{"content": q.content} for q in g_validated.questions]
                }
                g_hash = calculate_group_hash(g_data_dict)

                existing_g = db.query(QuestionGroup).filter(
                    QuestionGroup.exam_id.is_(None),
                    QuestionGroup.content_hash == g_hash
                ).first()

                if existing_g:
                    logger.info("QuestionGroup already exists (duplicate content_hash). Skipping.")
                    continue

                # Clean/Map difficulty
                diff_val = g_validated.difficulty.lower()
                g_difficulty = req_difficulty if req_difficulty in ["easy", "medium", "hard"] else (diff_val if diff_val in ["easy", "medium", "hard"] else "medium")

                new_g = QuestionGroup(
                    exam_id=None,
                    part=3,
                    topic=g_validated.topic,
                    passage_text=g_validated.passage_text,
                    audio_url=None,
                    image_url=None,
                    difficulty=g_difficulty,
                    status="draft",
                    content_hash=g_hash
                )
                db.add(new_g)
                db.commit()
                db.refresh(new_g)

                for q_validated in g_validated.questions:
                    q_data_dict = {
                        "set_id": "",
                        "number": "",
                        "part": 3,
                        "type": "choice",
                        "content": q_validated.content,
                        "options": q_validated.options,
                        "reference_answer": q_validated.reference_answer
                    }
                    q_hash = calculate_question_hash(q_data_dict)

                    q_diff_val = q_validated.difficulty.lower()
                    q_difficulty = req_difficulty if req_difficulty in ["easy", "medium", "hard"] else (q_diff_val if q_diff_val in ["easy", "medium", "hard"] else "medium")

                    new_q = Question(
                        exam_id=None,
                        group_id=new_g.id,
                        part=3,
                        type="choice",
                        content=q_validated.content,
                        options=q_validated.options,
                        reference_answer=q_validated.reference_answer,
                        difficulty=q_difficulty,
                        clo=q_validated.clo,
                        topic=g_validated.topic,
                        explanation=q_validated.explanation,
                        status="draft",
                        content_hash=q_hash,
                        exam_type="VSTEP_B1",
                        language="EN"
                    )
                    db.add(new_q)

                db.commit()
                saved_count += 1
            except Exception as val_err:
                logger.warning(f"R3 Group failed validation: {val_err}. Skipping.")
                db.rollback()

        return saved_count

    def generate_r4_groups(self, db: Session, count: int, topic: Optional[str] = None, req_difficulty: Optional[str] = None, seed: Optional[int] = None) -> int:
        """Generate R4 (Part 4 Cloze Passage with blanks 21-30 + word box of 15 words) groups and save to the bank."""
        if topic and topic not in B1_TOPICS:
            raise ValueError(f"Invalid topic '{topic}'. Must be one of {B1_TOPICS}")

        if not self.client:
            # Mock mode
            rnd = random.Random(seed)
            sig = inspect.signature(self._mock_r4_data)
            if "difficulty" in sig.parameters:
                data = self._mock_r4_data(rnd, count, topic, req_difficulty)
            else:
                data = self._mock_r4_data(rnd, count, topic)
        else:
            system_instruction = (
                "You are an expert English language examiner. Generate a batch of VSTEP B1 Reading Part 4 gap-fill cloze question groups.\n"
                "Each group must contain:\n"
                "1. A passage_text of 150-250 words containing exactly 10 blank labels: (21), (22), ..., (30) in order.\n"
                "2. A word_box of exactly 15 words (the 10 correct words to fill the blanks, plus 5 distractor words).\n"
                "3. A topic from the 14 valid B1 topics.\n"
                "4. Exactly 10 child questions, one for each blank number 21-30.\n"
                "Each child question must specify: blank_number, content (the sentence containing the blank), "
                "reference_answer (the exact correct word from word_box), CLO='Vận dụng có kiểm soát'.\n"
                + (f"The difficulty must be exactly: {req_difficulty}.\n" if req_difficulty else "The difficulty must be exactly one of: easy, medium, hard.\n") +
                "Return JSON matching the schema:\n"
                "{\n"
                "  \"groups\": [\n"
                "    {\n"
                "      \"passage_text\": \"string\",\n"
                "      \"word_box\": [\"string\"],\n"
                "      \"topic\": \"string\",\n"
                "      \"difficulty\": \"string\",\n"
                "      \"questions\": [\n"
                "        {\n"
                "          \"blank_number\": 21,\n"
                "          \"content\": \"string\",\n"
                "          \"reference_answer\": \"string\",\n"
                "          \"difficulty\": \"string\",\n"
                "          \"clo\": \"string\",\n"
                "          \"explanation\": \"string\"\n"
                "        }\n"
                "      ]\n"
                "    }\n"
                "  ]\n"
                "}"
            )
            topic_hint = f"Topic to focus: {topic}" if topic else f"Select randomly from valid B1 topics: {', '.join(B1_TOPICS)}"
            user_prompt = f"Generate {count} cloze groups. {topic_hint}"

            try:
                raw_json = self._call_gemini(system_instruction, user_prompt)
                data = json.loads(raw_json)
            except Exception as e:
                logger.error(f"Failed to generate R4 groups via Gemini: {e}. Falling back to Mock.")
                rnd = random.Random(seed)
                sig = inspect.signature(self._mock_r4_data)
                if "difficulty" in sig.parameters:
                    data = self._mock_r4_data(rnd, count, topic, req_difficulty)
                else:
                    data = self._mock_r4_data(rnd, count, topic)

        # Validate and Ingest
        saved_count = 0
        groups_list = data.get("groups", [])
        for g_raw in groups_list:
            try:
                # Schema Validation
                g_validated = R4GroupAI(**g_raw)

                # Semantic / Business Rule Validations
                if g_validated.topic not in B1_TOPICS:
                    logger.warning(f"Invalid topic in group: {g_validated.topic}. Skipping.")
                    continue
                if len(g_validated.word_box) != 15:
                    logger.warning(f"Word box must contain exactly 15 words (got {len(g_validated.word_box)}). Skipping.")
                    continue
                if len(g_validated.questions) != 10:
                    logger.warning(f"R4 group must contain exactly 10 questions (got {len(g_validated.questions)}). Skipping.")
                    continue

                valid_questions = True
                blank_numbers = [q.blank_number for q in g_validated.questions]
                if sorted(blank_numbers) != list(range(21, 31)):
                    logger.warning("R4 blank numbers must be exactly 21 to 30 in some order. Skipping.")
                    continue

                # Format the word box as a display grid at the top of the passage
                rows = []
                for idx in range(0, 15, 5):
                    row_words = g_validated.word_box[idx:idx+5]
                    rows.append("  ".join(f"[{w}]" for w in row_words))
                word_box_grid = "\n".join(rows)

                formatted_passage_text = (
                    "Choose the correct word from the box below to fill in each blank (21-30):\n"
                    f"{word_box_grid}\n\n"
                    "Passage:\n"
                    f"{g_validated.passage_text}"
                )

                for q in g_validated.questions:
                    # check if reference answer is in the word box
                    if q.reference_answer not in g_validated.word_box:
                        valid_questions = False
                        logger.warning(f"Reference answer '{q.reference_answer}' not found in word box. Skipping.")
                        break
                    # blank label format check
                    blank_placeholder = f"({q.blank_number})"
                    if blank_placeholder not in g_validated.passage_text:
                        valid_questions = False
                        logger.warning(f"Blank placeholder '{blank_placeholder}' not found in passage text. Skipping.")
                        break
                    if q.clo != "Vận dụng có kiểm soát":
                        valid_questions = False
                        logger.warning(f"Invalid CLO for R4: {q.clo}. Skipping.")
                        break

                if not valid_questions:
                    continue

                # Idempotency check for the group
                g_data_dict = {
                    "set_id": "",
                    "part": 4,
                    "passage_text": formatted_passage_text,
                    "audio_url": "",
                    "questions": [{"content": q.content} for q in g_validated.questions]
                }
                g_hash = calculate_group_hash(g_data_dict)

                existing_g = db.query(QuestionGroup).filter(
                    QuestionGroup.exam_id.is_(None),
                    QuestionGroup.content_hash == g_hash
                ).first()

                if existing_g:
                    logger.info("QuestionGroup already exists (duplicate content_hash). Skipping.")
                    continue

                # Clean/Map difficulty
                diff_val = g_validated.difficulty.lower()
                g_difficulty = req_difficulty if req_difficulty in ["easy", "medium", "hard"] else (diff_val if diff_val in ["easy", "medium", "hard"] else "medium")

                new_g = QuestionGroup(
                    exam_id=None,
                    part=4,
                    topic=g_validated.topic,
                    passage_text=formatted_passage_text,
                    audio_url=None,
                    image_url=None,
                    difficulty=g_difficulty,
                    status="draft",
                    content_hash=g_hash
                )
                db.add(new_g)
                db.commit()
                db.refresh(new_g)

                for q_validated in g_validated.questions:
                    q_data_dict = {
                        "set_id": "",
                        "number": str(q_validated.blank_number),
                        "part": 4,
                        "type": "fill",
                        "content": q_validated.content,
                        "options": {},
                        "reference_answer": q_validated.reference_answer
                    }
                    q_hash = calculate_question_hash(q_data_dict)

                    q_diff_val = q_validated.difficulty.lower()
                    q_difficulty = req_difficulty if req_difficulty in ["easy", "medium", "hard"] else (q_diff_val if q_diff_val in ["easy", "medium", "hard"] else "medium")

                    new_q = Question(
                        exam_id=None,
                        group_id=new_g.id,
                        part=4,
                        type="fill",
                        content=q_validated.content,
                        options={},
                        reference_answer=q_validated.reference_answer,
                        difficulty=q_difficulty,
                        clo=q_validated.clo,
                        topic=g_validated.topic,
                        explanation=q_validated.explanation,
                        status="draft",
                        content_hash=q_hash,
                        exam_type="VSTEP_B1",
                        language="EN"
                    )
                    db.add(new_q)

                db.commit()
                saved_count += 1
            except Exception as val_err:
                logger.warning(f"R4 Group failed validation: {val_err}. Skipping.")
                db.rollback()

        return saved_count

    def _generate_tts_wav(self, text: str, output_path: str):
        """Call Gemini TTS API to generate linear 16-bit PCM and save as a WAV file."""
        if not self.client:
            raise RuntimeError("Gemini client is not initialized.")
        try:
            response = self.client.models.generate_content(
                model="gemini-2.5-flash-preview-tts",
                contents=text,
                config=types.GenerateContentConfig(
                    response_modalities=["AUDIO"],
                    speech_config=types.SpeechConfig(
                        voice_config=types.VoiceConfig(
                            prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                voice_name="Puck"
                            )
                        )
                    )
                )
            )
            audio_data = None
            for candidate in response.candidates:
                if not candidate.content or not candidate.content.parts:
                    continue
                for part in candidate.content.parts:
                    if part.inline_data and part.inline_data.mime_type.startswith("audio/"):
                        audio_data = part.inline_data.data
                        break
            if audio_data is None:
                raise ValueError("No audio part found in Gemini TTS response.")

            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            with wave.open(output_path, "wb") as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(24000)
                wav_file.writeframes(audio_data)

        except Exception as e:
            logger.error(f"Gemini TTS generation failed: {e}")
            raise e

    def _generate_image(self, prompt: str, output_path: str):
        """Call Gemini Image API to generate PNG image and save to output_path."""
        if not self.client:
            raise RuntimeError("Gemini client is not initialized.")
        try:
            response = self.client.models.generate_content(
                model="gemini-2.5-flash-image",
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_modalities=["IMAGE"]
                )
            )
            image_data = None
            for candidate in response.candidates:
                if not candidate.content or not candidate.content.parts:
                    continue
                for part in candidate.content.parts:
                    if part.inline_data and part.inline_data.mime_type.startswith("image/"):
                        image_data = part.inline_data.data
                        break
            if image_data is None:
                raise ValueError("No image part found in Gemini Image response.")

            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, "wb") as f:
                f.write(image_data)

        except Exception as e:
            logger.error(f"Gemini Image generation failed: {e}")
            raise e

    # --- SPEC-BANK-007: Hybrid Seed & Paraphrase ---

    # 1x1 transparent PNG used as a placeholder when regenerating images in mock mode.
    _PLACEHOLDER_PNG = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAC0lEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    )

    def paraphrase_from_seed(self, db: Session, seed: Question, count: int) -> int:
        """SPEC-BANK-007: paraphrase a choice-type SEED question into `count` fresh draft
        variants. Rewrites the stem, rewords every distractor (keeping the correct answer's
        meaning), AI-labels difficulty against CEFR B1, and — for picture questions —
        regenerates a NEW illustration so the original wording/image copyright is not
        reproduced. Each variant links back to the seed via source_question_id."""
        if seed.type != "choice" or not isinstance(seed.options, dict) or len(seed.options) < 2:
            raise ValueError("Chỉ paraphrase được câu trắc nghiệm (choice) có sẵn phương án.")

        option_keys = sorted(seed.options.keys())
        is_picture = bool(seed.image_url)

        if not self.client:
            data = self._mock_paraphrase_data(seed, count, option_keys)
        else:
            system_instruction = (
                "You are an expert VSTEP B1 (CEFR B1) English item writer. You are given a SEED "
                "multiple-choice question. Produce fresh PARAPHRASED variants that test the SAME "
                "language point at the SAME level but are NOT verbatim copies:\n"
                "- Rewrite the question stem using different wording.\n"
                f"- Reword EVERY option; keep exactly the same option keys ({', '.join(option_keys)}) "
                "and keep the correct answer's MEANING.\n"
                "- reference_answer must be one of the option keys, pointing to the option whose meaning "
                "matches the seed's correct answer.\n"
                "- Assess difficulty by comparing the vocabulary to the CEFR B1 wordlist: 'easy' if all "
                "words are core A2-B1, 'medium' if it uses upper-B1 vocabulary, 'hard' if it contains "
                "B2+ or low-frequency words. difficulty must be exactly one of: easy, medium, hard.\n"
                + ("- Also return image_description: a NEW English scene description illustrating the "
                   "correct answer so a fresh, copyright-free picture can be drawn (do NOT describe the "
                   "original image).\n" if is_picture else "")
                + "Return JSON: {\"variants\": [{\"content\": str, \"options\": object, "
                "\"reference_answer\": str, \"difficulty\": str, \"explanation\": str"
                + (", \"image_description\": str" if is_picture else "") + "}]}"
            )
            user_prompt = (
                f"SEED question (topic: {seed.topic or 'general'}):\n"
                f"Stem: {seed.content}\n"
                f"Options: {json.dumps(seed.options, ensure_ascii=False)}\n"
                f"Correct answer key: {seed.reference_answer}\n"
                f"Generate {count} distinct paraphrased variants."
            )
            try:
                data = json.loads(self._call_gemini(system_instruction, user_prompt))
            except Exception as e:
                logger.error(f"Paraphrase via Gemini failed: {e}. Falling back to mock.")
                data = self._mock_paraphrase_data(seed, count, option_keys)

        saved = 0
        for var in data.get("variants", []):
            try:
                content = (var.get("content") or "").strip()
                options = var.get("options") or {}
                ref = var.get("reference_answer")
                difficulty = (var.get("difficulty") or "medium").lower()
                if difficulty not in ("easy", "medium", "hard"):
                    difficulty = "medium"

                # Validation gate
                if not content or content == (seed.content or "").strip():
                    logger.warning("Paraphrase rỗng hoặc trùng nguyên văn seed. Bỏ qua.")
                    continue
                if sorted(options.keys()) != option_keys:
                    logger.warning("Paraphrase lệch bộ khóa phương án so với seed. Bỏ qua.")
                    continue
                if ref not in options:
                    logger.warning("Paraphrase reference_answer không thuộc options. Bỏ qua.")
                    continue

                q_hash = calculate_question_hash({
                    "set_id": "", "number": "", "part": seed.part, "type": "choice",
                    "content": content, "options": options, "reference_answer": ref,
                })
                existing = db.query(Question).filter(
                    Question.exam_id.is_(None), Question.content_hash == q_hash
                ).first()
                if existing:
                    logger.info("Câu paraphrase đã tồn tại trong ngân hàng. Bỏ qua.")
                    continue

                # AC3: regenerate a fresh illustration for picture questions (copyright-safe).
                # If regeneration fails, SKIP the variant rather than save a picture
                # question with no image of its own.
                new_image_url = None
                if is_picture:
                    new_image_url = self._render_paraphrase_image(
                        var.get("image_description") or content, q_hash
                    )
                    if new_image_url is None:
                        logger.warning("Sinh ảnh paraphrase thất bại cho câu tranh. Bỏ qua biến thể.")
                        continue

                new_q = Question(
                    exam_id=None, group_id=None, part=seed.part, type="choice",
                    content=content, options=options, reference_answer=ref,
                    difficulty=difficulty, clo=seed.clo, topic=seed.topic,
                    explanation=var.get("explanation"), status="draft",
                    content_hash=q_hash, exam_type="VSTEP_B1", language="EN",
                    source_question_id=seed.id, image_url=new_image_url,
                )
                db.add(new_q)
                db.commit()
                saved += 1
            except Exception as val_err:
                logger.warning(f"Biến thể paraphrase lỗi: {val_err}. Bỏ qua.")
                db.rollback()

        return saved

    def _render_paraphrase_image(self, description: str, q_hash: str) -> Optional[str]:
        """Generate (real) or write a placeholder (mock) illustration for a paraphrased
        picture question. Returns the /static URL, or None on failure."""
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        fname = f"paraphrase_{q_hash[:16]}.png"
        out_path = os.path.join(base_dir, "static", "img", fname)
        try:
            os.makedirs(os.path.dirname(out_path), exist_ok=True)
            if self.client:
                self._generate_image(
                    "A simple, clear, copyright-free illustration for a B1 English picture "
                    f"question: {description}",
                    out_path,
                )
            else:
                with open(out_path, "wb") as f:
                    f.write(self._PLACEHOLDER_PNG)
        except Exception as e:
            logger.error(f"Paraphrase image generation failed: {e}")
            return None
        return f"/static/img/{fname}"

    def _mock_paraphrase_data(self, seed: Question, count: int, option_keys: List[str]) -> dict:
        """Deterministic mock paraphrase (no network): reword stem+options so content
        differs from the seed (copyright-safe) and stays distinct per variant."""
        diffs = ["easy", "medium", "hard"]
        variants = []
        for i in range(count):
            # Deterministic stand-in reword: reorder the stem words so the output does
            # NOT contain the seed verbatim (a real paraphrase rewrites; the mock only
            # needs to prove the plumbing produces a genuinely different, seed-free stem).
            reworded = " ".join(reversed((seed.content or "").split()))
            var = {
                "content": f"(Paraphrase {i + 1}) {reworded}",
                "options": {k: f"{seed.options[k]} (variant {i + 1})" for k in option_keys},
                "reference_answer": seed.reference_answer,
                "difficulty": diffs[i % 3],
                "explanation": f"Paraphrase từ seed #{seed.id}; đáp án đúng giữ nguyên nghĩa.",
            }
            if seed.image_url:
                var["image_description"] = (
                    f"New illustration for: {seed.options.get(seed.reference_answer, '')}"
                )
            variants.append(var)
        return {"variants": variants}

    def generate_l1_questions(self, db: Session, count: int, topic: Optional[str] = None, req_difficulty: Optional[str] = None, seed: Optional[int] = None) -> int:
        """Generate L1 (Part 7 Listening Picture Matching - 3 choices) questions and save to the bank."""
        if topic and topic not in B1_TOPICS:
            raise ValueError(f"Invalid topic '{topic}'. Must be one of {B1_TOPICS}")

        import wave
        import os

        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        static_dir_audio = os.path.join(base_dir, "static", "audio_gen")
        static_dir_img = os.path.join(base_dir, "static", "img")

        if not self.client:
            rnd = random.Random(seed)
            sig = inspect.signature(self._mock_l1_data)
            if "difficulty" in sig.parameters:
                data = self._mock_l1_data(rnd, count, topic, req_difficulty)
            else:
                data = self._mock_l1_data(rnd, count, topic)
        else:
            system_instruction = (
                "You are an expert English language examiner. Generate a batch of VSTEP B1 Listening Part 1 standalone multiple-choice questions with 3 picture choices.\n"
                "Each question must contain:\n"
                "1. A script_text (the actual dialogue/monologue script to be read aloud, 50-100 words).\n"
                "2. A question_text (the short query about the dialogue, e.g., 'What will the weather be like tomorrow?').\n"
                "3. Three image descriptions: description_a, description_b, description_c. Each description should describe a simple, clear visual scene corresponding to options A, B, and C.\n"
                "   Write these prompts formatted for a line drawing generator. E.g., 'A simple black and white line drawing of a book on a table, white background, sketch style'.\n"
                "4. A reference_answer (must be exactly 'A', 'B', or 'C').\n"
                "5. The CLO must be 'Thông hiểu' or 'Nhận diện'.\n"
                "6. The difficulty must be exactly one of: easy, medium, hard.\n"
                "7. The topic must be chosen from the 14 valid B1 topics.\n"
                "Return JSON matching the schema:\n"
                "{\n"
                "  \"questions\": [\n"
                "    {\n"
                "      \"script_text\": \"string\",\n"
                "      \"question_text\": \"string\",\n"
                "      \"description_a\": \"string\",\n"
                "      \"description_b\": \"string\",\n"
                "      \"description_c\": \"string\",\n"
                "      \"reference_answer\": \"string\",\n"
                "      \"difficulty\": \"string\",\n"
                "      \"clo\": \"string\",\n"
                "      \"topic\": \"string\",\n"
                "      \"explanation\": \"string\"\n"
                "    }\n"
                "  ]\n"
                "}"
            )
            topic_hint = f"Topic to focus: {topic}" if topic else f"Select randomly from valid B1 topics: {', '.join(B1_TOPICS)}"
            user_prompt = f"Generate {count} questions. {topic_hint}"

            try:
                raw_json = self._call_gemini(system_instruction, user_prompt)
                data = json.loads(raw_json)
            except Exception as e:
                logger.error(f"Failed to generate L1 questions via Gemini: {e}. Falling back to Mock.")
                rnd = random.Random(seed)
                sig = inspect.signature(self._mock_l1_data)
                if "difficulty" in sig.parameters:
                    data = self._mock_l1_data(rnd, count, topic, req_difficulty)
                else:
                    data = self._mock_l1_data(rnd, count, topic)

        saved_count = 0
        questions_list = data.get("questions", [])
        for q_raw in questions_list:
            # Deterministic paths upfront for cleanup
            audio_path = None
            img_path_a = None
            img_path_b = None
            img_path_c = None
            try:
                q_validated = L1QuestionAI(**q_raw)

                # Validation checks
                if q_validated.topic not in B1_TOPICS:
                    logger.warning(f"Invalid topic in generated question: {q_validated.topic}. Skipping.")
                    continue
                if q_validated.clo not in ["Nhận diện", "Thông hiểu"]:
                    logger.warning(f"Invalid CLO for L1: {q_validated.clo}. Skipping.")
                    continue
                if q_validated.reference_answer not in {"A", "B", "C"}:
                    logger.warning(f"Invalid reference_answer: {q_validated.reference_answer}. Skipping.")
                    continue

                # Idempotency checks
                q_data_dict = {
                    "set_id": "",
                    "number": "",
                    "part": 7,
                    "type": "choice",
                    "content": q_validated.question_text,
                    "options": {},
                    "reference_answer": q_validated.reference_answer
                }
                q_hash = calculate_question_hash(q_data_dict)

                existing = db.query(Question).filter(
                    Question.exam_id.is_(None),
                    Question.content_hash == q_hash
                ).first()

                if existing:
                    logger.info("Question already exists in bank (duplicate content_hash). Skipping.")
                    continue

                # Prepare asset paths
                audio_filename = f"l1_{q_hash}.wav"
                audio_path = os.path.join(static_dir_audio, audio_filename)
                audio_url = f"/static/audio_gen/{audio_filename}"

                img_a_filename = f"l1_{q_hash}_A.png"
                img_b_filename = f"l1_{q_hash}_B.png"
                img_c_filename = f"l1_{q_hash}_C.png"

                img_path_a = os.path.join(static_dir_img, img_a_filename)
                img_path_b = os.path.join(static_dir_img, img_b_filename)
                img_path_c = os.path.join(static_dir_img, img_c_filename)

                img_url_a = f"/static/img/{img_a_filename}"
                img_url_b = f"/static/img/{img_b_filename}"
                img_url_c = f"/static/img/{img_c_filename}"
                image_url = f"{img_url_a},{img_url_b},{img_url_c}"

                # Generate Audio (TTS)
                if not self.client:
                    os.makedirs(os.path.dirname(audio_path), exist_ok=True)
                    with wave.open(audio_path, "wb") as wav_file:
                        wav_file.setnchannels(1)
                        wav_file.setsampwidth(2)
                        wav_file.setframerate(24000)
                        wav_file.writeframes(b"\x00" * 48000)
                else:
                    self._generate_tts_wav(q_validated.script_text, audio_path)

                if not os.path.exists(audio_path):
                    raise FileNotFoundError(f"Audio file failed to generate at {audio_path}")

                # Generate Images
                if not self.client:
                    os.makedirs(os.path.dirname(img_path_a), exist_ok=True)
                    MINIMAL_PNG_BYTES = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\rIDATx\x9cc`\x00\x00\x00\x02\x00\x01H\xaf\xa4q\x00\x00\x00\x00IEND\xaeB`\x82'
                    for img_p in [img_path_a, img_path_b, img_path_c]:
                        with open(img_p, "wb") as img_file:
                            img_file.write(MINIMAL_PNG_BYTES)
                else:
                    self._generate_image(q_validated.description_a, img_path_a)
                    self._generate_image(q_validated.description_b, img_path_b)
                    self._generate_image(q_validated.description_c, img_path_c)

                # Check all files exist
                for fp in [audio_path, img_path_a, img_path_b, img_path_c]:
                    if not os.path.exists(fp):
                        raise FileNotFoundError(f"Asset file not found at {fp}")

                # Clean/Map difficulty
                diff_val = q_validated.difficulty.lower()
                difficulty = req_difficulty if req_difficulty in ["easy", "medium", "hard"] else (diff_val if diff_val in ["easy", "medium", "hard"] else "medium")

                new_q = Question(
                    exam_id=None,
                    group_id=None,
                    part=7,
                    type="choice",
                    content=q_validated.question_text,
                    options={},
                    reference_answer=q_validated.reference_answer,
                    difficulty=difficulty,
                    clo=q_validated.clo,
                    topic=q_validated.topic,
                    explanation=q_validated.explanation,
                    status="draft",
                    content_hash=q_hash,
                    exam_type="VSTEP_B1",
                    language="EN",
                    image_url=image_url,
                    audio_url=audio_url
                )
                db.add(new_q)
                db.commit()
                saved_count += 1
            except Exception as val_err:
                logger.warning(f"L1 question failed validation or generation: {val_err}. Skipping.")
                db.rollback()
                for fp in [audio_path, img_path_a, img_path_b, img_path_c]:
                    if fp and os.path.exists(fp):
                        try:
                            os.remove(fp)
                        except Exception as rm_err:
                            logger.error(f"Failed to remove file {fp}: {rm_err}")

        return saved_count

    def generate_l2_groups(self, db: Session, count: int, topic: Optional[str] = None, req_difficulty: Optional[str] = None, seed: Optional[int] = None) -> int:
        """Generate L2 (Part 8 Note Completion - 10 blanks) groups and save to the bank."""
        if topic and topic not in B1_TOPICS:
            raise ValueError(f"Invalid topic '{topic}'. Must be one of {B1_TOPICS}")

        import hashlib
        import wave
        import os

        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        static_dir = os.path.join(base_dir, "static", "audio_gen")

        if not self.client:
            rnd = random.Random(seed)
            sig = inspect.signature(self._mock_l2_data)
            if "difficulty" in sig.parameters:
                data = self._mock_l2_data(rnd, count, topic, req_difficulty)
            else:
                data = self._mock_l2_data(rnd, count, topic)
        else:
            system_instruction = (
                "You are an expert English language examiner. Generate a batch of VSTEP B1 Listening Part 2 gap-fill note completion question groups.\n"
                "Each group must contain:\n"
                "1. A script_text (the actual dialogue/monologue script to be read aloud, 200-300 words).\n"
                "2. A note_template (the summary notes containing exactly 10 blank labels: (1), (2), ..., (10) in order).\n"
                "3. A topic from the 14 valid B1 topics.\n"
                "4. Exactly 10 child questions, one for each blank number 1-10.\n"
                "Each child question must specify: blank_number, content (the short context sentence containing the blank), "
                "reference_answer (the correct word or short phrase from the script), CLO='Thông hiểu'.\n"
                + (f"The difficulty must be exactly: {req_difficulty}.\n" if req_difficulty else "The difficulty must be exactly one of: easy, medium, hard.\n") +
                "Return JSON matching the schema:\n"
                "{\n"
                "  \"groups\": [\n"
                "    {\n"
                "      \"script_text\": \"string\",\n"
                "      \"note_template\": \"string\",\n"
                "      \"topic\": \"string\",\n"
                "      \"difficulty\": \"string\",\n"
                "      \"questions\": [\n"
                "        {\n"
                "          \"blank_number\": 1,\n"
                "          \"content\": \"string\",\n"
                "          \"reference_answer\": \"string\",\n"
                "          \"difficulty\": \"string\",\n"
                "          \"clo\": \"string\",\n"
                "          \"explanation\": \"string\"\n"
                "        }\n"
                "      ]\n"
                "    }\n"
                "  ]\n"
                "}"
            )
            topic_hint = f"Topic to focus: {topic}" if topic else f"Select randomly from valid B1 topics: {', '.join(B1_TOPICS)}"
            user_prompt = f"Generate {count} listening note-completion groups. {topic_hint}"

            try:
                raw_json = self._call_gemini(system_instruction, user_prompt)
                data = json.loads(raw_json)
            except Exception as e:
                logger.error(f"Failed to generate L2 groups via Gemini: {e}. Falling back to Mock.")
                rnd = random.Random(seed)
                sig = inspect.signature(self._mock_l2_data)
                if "difficulty" in sig.parameters:
                    data = self._mock_l2_data(rnd, count, topic, req_difficulty)
                else:
                    data = self._mock_l2_data(rnd, count, topic)

        saved_count = 0
        groups_list = data.get("groups", [])
        for g_raw in groups_list:
            audio_path = None
            try:
                g_validated = L2GroupAI(**g_raw)

                if g_validated.topic not in B1_TOPICS:
                    logger.warning(f"Invalid topic in group: {g_validated.topic}. Skipping.")
                    continue
                if len(g_validated.questions) != 10:
                    logger.warning(f"L2 group must contain exactly 10 questions (got {len(g_validated.questions)}). Skipping.")
                    continue

                valid_questions = True
                blank_numbers = [q.blank_number for q in g_validated.questions]
                if sorted(blank_numbers) != list(range(1, 11)):
                    logger.warning("L2 blank numbers must be exactly 1 to 10. Skipping.")
                    continue

                for q in g_validated.questions:
                    if not q.reference_answer or not q.reference_answer.strip():
                        valid_questions = False
                        logger.warning("L2 child question reference answer cannot be empty. Skipping.")
                        break
                    blank_placeholder = f"({q.blank_number})"
                    if blank_placeholder not in g_validated.note_template:
                        valid_questions = False
                        logger.warning(f"Blank placeholder '{blank_placeholder}' not found in note template. Skipping.")
                        break
                    if q.clo != "Thông hiểu":
                        valid_questions = False
                        logger.warning(f"Invalid CLO for L2: {q.clo}. Skipping.")
                        break

                if not valid_questions:
                    continue

                g_data_dict = {
                    "set_id": "",
                    "part": 8,
                    "passage_text": g_validated.note_template,
                    "audio_url": f"/static/audio_gen/l2_{hashlib.sha256(g_validated.script_text.encode('utf-8')).hexdigest()[:16]}.wav",
                    "questions": [{"content": q.content} for q in g_validated.questions]
                }
                g_hash = calculate_group_hash(g_data_dict)

                existing_g = db.query(QuestionGroup).filter(
                    QuestionGroup.exam_id.is_(None),
                    QuestionGroup.content_hash == g_hash
                ).first()

                if existing_g:
                    logger.info("QuestionGroup already exists (duplicate content_hash). Skipping.")
                    continue

                audio_filename = f"l2_{g_hash}.wav"
                audio_path = os.path.join(static_dir, audio_filename)
                audio_url = f"/static/audio_gen/{audio_filename}"

                if not self.client:
                    os.makedirs(os.path.dirname(audio_path), exist_ok=True)
                    with wave.open(audio_path, "wb") as wav_file:
                        wav_file.setnchannels(1)
                        wav_file.setsampwidth(2)
                        wav_file.setframerate(24000)
                        wav_file.writeframes(b"\x00" * 48000)
                else:
                    self._generate_tts_wav(g_validated.script_text, audio_path)

                if not os.path.exists(audio_path):
                    raise FileNotFoundError(f"Audio file failed to generate at {audio_path}")

                diff_val = g_validated.difficulty.lower()
                g_difficulty = req_difficulty if req_difficulty in ["easy", "medium", "hard"] else (diff_val if diff_val in ["easy", "medium", "hard"] else "medium")

                new_g = QuestionGroup(
                    exam_id=None,
                    part=8,
                    topic=g_validated.topic,
                    passage_text=g_validated.note_template,
                    audio_url=audio_url,
                    image_url=None,
                    difficulty=g_difficulty,
                    status="draft",
                    content_hash=g_hash
                )
                db.add(new_g)
                db.commit()
                db.refresh(new_g)

                for q_validated in g_validated.questions:
                    q_data_dict = {
                        "set_id": "",
                        "number": str(q_validated.blank_number),
                        "part": 8,
                        "type": "fill",
                        "content": q_validated.content,
                        "options": {},
                        "reference_answer": q_validated.reference_answer
                    }
                    q_hash = calculate_question_hash(q_data_dict)

                    q_diff_val = q_validated.difficulty.lower()
                    q_difficulty = req_difficulty if req_difficulty in ["easy", "medium", "hard"] else (q_diff_val if q_diff_val in ["easy", "medium", "hard"] else "medium")

                    new_q = Question(
                        exam_id=None,
                        group_id=new_g.id,
                        part=8,
                        type="fill",
                        content=q_validated.content,
                        options={},
                        reference_answer=q_validated.reference_answer,
                        difficulty=q_difficulty,
                        clo=q_validated.clo,
                        topic=g_validated.topic,
                        explanation=q_validated.explanation,
                        status="draft",
                        content_hash=q_hash,
                        exam_type="VSTEP_B1",
                        language="EN"
                    )
                    db.add(new_q)

                db.commit()
                saved_count += 1
            except Exception as val_err:
                logger.warning(f"L2 Group failed validation or generation: {val_err}. Skipping.")
                db.rollback()
                if audio_path and os.path.exists(audio_path):
                    try:
                        os.remove(audio_path)
                    except Exception as e:
                        logger.error(f"Failed to remove audio file {audio_path}: {e}")

        return saved_count

    # --- Deterministic Mock Data Generators ---

    def generate_writing_questions(self, db: Session, count: int, part: int, topic: Optional[str] = None, req_difficulty: Optional[str] = None, seed: Optional[int] = None) -> int:
        """Generate Writing questions (Part 5 (W1) or Part 6 (W2)) and save to the bank."""
        if part not in (5, 6):
            raise ValueError(f"Invalid Writing part '{part}'. Must be 5 or 6.")
        if topic and topic not in B1_TOPICS:
            raise ValueError(f"Invalid topic '{topic}'. Must be one of {B1_TOPICS}")

        expected_clo = "Vận dụng có kiểm soát" if part == 5 else "Vận dụng tổng hợp"

        if not self.client:
            # Mock mode
            rnd = random.Random(seed)
            sig = inspect.signature(self._mock_writing_data)
            if "difficulty" in sig.parameters:
                data = self._mock_writing_data(rnd, count, part, topic, req_difficulty)
            else:
                data = self._mock_writing_data(rnd, count, part, topic)
        else:
            system_instruction = (
                "You are an expert English language examiner. Generate a batch of VSTEP B1 Writing questions.\n"
                f"For part {part}:\n"
                + (
                    "Part 5 (Writing Task 1): 'Rewrite the sentence' prompts. The CLO must be 'Vận dụng có kiểm soát'.\n"
                    if part == 5 else
                    "Part 6 (Writing Task 2): 'Write an email/letter (~100-120 words)' prompts. The CLO must be 'Vận dụng tổng hợp'.\n"
                ) +
                "The type must be 'writing'.\n"
                + (f"The difficulty must be exactly: {req_difficulty}.\n" if req_difficulty else "The difficulty must be exactly one of: easy, medium, hard.\n") +
                "The topic must be chosen from the 14 valid B1 topics.\n"
                "Return JSON matching the schema:\n"
                "{\n"
                "  \"questions\": [\n"
                "    {\n"
                "      \"part\": int,\n"
                "      \"type\": \"string\",\n"
                "      \"content\": \"string\",\n"
                "      \"difficulty\": \"string\",\n"
                "      \"clo\": \"string\",\n"
                "      \"topic\": \"string\",\n"
                "      \"explanation\": \"string\"\n"
                "    }\n"
                "  ]\n"
                "}"
            )
            topic_hint = f"Topic to focus: {topic}" if topic else f"Select randomly from valid B1 topics: {', '.join(B1_TOPICS)}"
            user_prompt = f"Generate {count} questions for part {part}. {topic_hint}"

            try:
                raw_json = self._call_gemini(system_instruction, user_prompt)
                data = json.loads(raw_json)
            except Exception as e:
                logger.error(f"Failed to generate Writing questions via Gemini: {e}. Falling back to Mock.")
                rnd = random.Random(seed)
                sig = inspect.signature(self._mock_writing_data)
                if "difficulty" in sig.parameters:
                    data = self._mock_writing_data(rnd, count, part, topic, req_difficulty)
                else:
                    data = self._mock_writing_data(rnd, count, part, topic)

        # Validate and Ingest
        saved_count = 0
        questions_list = data.get("questions", [])
        for q_raw in questions_list:
            try:
                # Schema Validation
                q_validated = WritingSpeakingQuestionAI(**q_raw)

                # Semantic / Business Rule Validations
                if q_validated.part != part:
                    logger.warning(f"Generated part {q_validated.part} does not match requested part {part}. Skipping.")
                    continue
                if q_validated.type != "writing":
                    logger.warning(f"Invalid type in generated question: {q_validated.type}. Skipping.")
                    continue
                if q_validated.topic not in B1_TOPICS:
                    logger.warning(f"Invalid topic in generated question: {q_validated.topic}. Skipping.")
                    continue
                if q_validated.clo != expected_clo:
                    logger.warning(f"Invalid CLO for part {part}: {q_validated.clo}. Skipping.")
                    continue
                if not q_validated.content or len(q_validated.content.strip()) < 20:
                    logger.warning("Content too short or empty. Skipping.")
                    continue

                # Clean/Map difficulty
                diff_val = q_validated.difficulty.lower()
                difficulty = req_difficulty if req_difficulty in ["easy", "medium", "hard"] else (diff_val if diff_val in ["easy", "medium", "hard"] else "medium")

                # Idempotency checks
                q_data_dict = {
                    "set_id": "",
                    "number": "",
                    "part": part,
                    "type": "writing",
                    "content": q_validated.content,
                    "options": {},
                    "reference_answer": ""
                }
                q_hash = calculate_question_hash(q_data_dict)

                existing = db.query(Question).filter(
                    Question.exam_id.is_(None),
                    Question.content_hash == q_hash
                ).first()

                if existing:
                    logger.info("Question already exists in bank (duplicate content_hash). Skipping.")
                    continue

                new_q = Question(
                    exam_id=None,
                    group_id=None,
                    part=part,
                    type="writing",
                    content=q_validated.content,
                    options={},
                    reference_answer=None,
                    difficulty=difficulty,
                    clo=q_validated.clo,
                    topic=q_validated.topic,
                    explanation=q_validated.explanation,
                    status="draft",
                    content_hash=q_hash,
                    exam_type="VSTEP_B1",
                    language="EN"
                )
                db.add(new_q)
                db.commit()
                saved_count += 1
            except Exception as val_err:
                logger.warning(f"Item failed validation: {val_err}. Skipping.")
                db.rollback()

        return saved_count

    def generate_speaking_questions(self, db: Session, count: int, part: int, topic: Optional[str] = None, req_difficulty: Optional[str] = None, seed: Optional[int] = None) -> int:
        """Generate Speaking questions (Part 9 (S1), Part 10 (S2), Part 11 (S3)) and save to the bank."""
        if part not in (9, 10, 11):
            raise ValueError(f"Invalid Speaking part '{part}'. Must be 9, 10, or 11.")
        if topic and topic not in B1_TOPICS:
            raise ValueError(f"Invalid topic '{topic}'. Must be one of {B1_TOPICS}")

        expected_clo = "Vận dụng tổng hợp" if part == 11 else "Vận dụng có kiểm soát"

        if not self.client:
            # Mock mode
            rnd = random.Random(seed)
            sig = inspect.signature(self._mock_speaking_data)
            if "difficulty" in sig.parameters:
                data = self._mock_speaking_data(rnd, count, part, topic, req_difficulty)
            else:
                data = self._mock_speaking_data(rnd, count, part, topic)
        else:
            system_instruction = (
                "You are an expert English language examiner. Generate a batch of VSTEP B1 Speaking questions.\n"
                f"For part {part}:\n"
                + (
                    "Part 9 (Speaking Part 1 - Social Interaction): Answer three independent questions about a topic. The CLO must be 'Vận dụng có kiểm soát'.\n"
                    if part == 9 else
                    "Part 10 (Speaking Part 2 - Solution Discussion): Situation discussion (given a situation with 3 options, discuss and justify choice). The CLO must be 'Vận dụng có kiểm soát'.\n"
                    if part == 10 else
                    "Part 11 (Speaking Part 3 - Topic Development): Topic development based on a mind map/points and follow-up questions. The CLO must be 'Vận dụng tổng hợp'.\n"
                ) +
                "The type must be 'speaking'.\n"
                + (f"The difficulty must be exactly: {req_difficulty}.\n" if req_difficulty else "The difficulty must be exactly one of: easy, medium, hard.\n") +
                "The topic must be chosen from the 14 valid B1 topics.\n"
                "Return JSON matching the schema:\n"
                "{\n"
                "  \"questions\": [\n"
                "    {\n"
                "      \"part\": int,\n"
                "      \"type\": \"string\",\n"
                "      \"content\": \"string\",\n"
                "      \"difficulty\": \"string\",\n"
                "      \"clo\": \"string\",\n"
                "      \"topic\": \"string\",\n"
                "      \"explanation\": \"string\"\n"
                "    }\n"
                "  ]\n"
                "}"
            )
            topic_hint = f"Topic to focus: {topic}" if topic else f"Select randomly from valid B1 topics: {', '.join(B1_TOPICS)}"
            user_prompt = f"Generate {count} questions for part {part}. {topic_hint}"

            try:
                raw_json = self._call_gemini(system_instruction, user_prompt)
                data = json.loads(raw_json)
            except Exception as e:
                logger.error(f"Failed to generate Speaking questions via Gemini: {e}. Falling back to Mock.")
                rnd = random.Random(seed)
                sig = inspect.signature(self._mock_speaking_data)
                if "difficulty" in sig.parameters:
                    data = self._mock_speaking_data(rnd, count, part, topic, req_difficulty)
                else:
                    data = self._mock_speaking_data(rnd, count, part, topic)

        # Validate and Ingest
        saved_count = 0
        questions_list = data.get("questions", [])
        for q_raw in questions_list:
            try:
                # Schema Validation
                q_validated = WritingSpeakingQuestionAI(**q_raw)

                # Semantic / Business Rule Validations
                if q_validated.part != part:
                    logger.warning(f"Generated part {q_validated.part} does not match requested part {part}. Skipping.")
                    continue
                if q_validated.type != "speaking":
                    logger.warning(f"Invalid type in generated question: {q_validated.type}. Skipping.")
                    continue
                if q_validated.topic not in B1_TOPICS:
                    logger.warning(f"Invalid topic in generated question: {q_validated.topic}. Skipping.")
                    continue
                if q_validated.clo != expected_clo:
                    logger.warning(f"Invalid CLO for part {part}: {q_validated.clo}. Skipping.")
                    continue
                if not q_validated.content or len(q_validated.content.strip()) < 20:
                    logger.warning("Content too short or empty. Skipping.")
                    continue

                # Clean/Map difficulty
                diff_val = q_validated.difficulty.lower()
                difficulty = req_difficulty if req_difficulty in ["easy", "medium", "hard"] else (diff_val if diff_val in ["easy", "medium", "hard"] else "medium")

                # Idempotency checks
                q_data_dict = {
                    "set_id": "",
                    "number": "",
                    "part": part,
                    "type": "speaking",
                    "content": q_validated.content,
                    "options": {},
                    "reference_answer": ""
                }
                q_hash = calculate_question_hash(q_data_dict)

                existing = db.query(Question).filter(
                    Question.exam_id.is_(None),
                    Question.content_hash == q_hash
                ).first()

                if existing:
                    logger.info("Question already exists in bank (duplicate content_hash). Skipping.")
                    continue

                new_q = Question(
                    exam_id=None,
                    group_id=None,
                    part=part,
                    type="speaking",
                    content=q_validated.content,
                    options={},
                    reference_answer=None,
                    difficulty=difficulty,
                    clo=q_validated.clo,
                    topic=q_validated.topic,
                    explanation=q_validated.explanation,
                    status="draft",
                    content_hash=q_hash,
                    exam_type="VSTEP_B1",
                    language="EN"
                )
                db.add(new_q)
                db.commit()
                saved_count += 1
            except Exception as val_err:
                logger.warning(f"Item failed validation: {val_err}. Skipping.")
                db.rollback()

        return saved_count

    def _mock_r1_data(self, rnd: random.Random, count: int, topic: Optional[str] = None, difficulty: Optional[str] = None) -> dict:
        questions = []
        for _ in range(count):
            t = topic or rnd.choice(B1_TOPICS)
            diff = difficulty if difficulty in ["easy", "medium", "hard"] else rnd.choice(["easy", "medium", "hard"])
            clo = rnd.choice(["Nhận diện", "Thông hiểu"])
            ref = rnd.choice(["A", "B", "C", "D"])
            questions.append({
                "content": "Although they encountered obstacles on the road, they managed to arrive ______ the destination.",
                "options": {
                    "A": "at",
                    "B": "in",
                    "C": "on",
                    "D": "to"
                },
                "reference_answer": ref,
                "difficulty": diff,
                "clo": clo,
                "topic": t,
                "explanation": f"The correct preposition with destination here is 'at' or 'to', select mock answer {ref}."
            })
        return {"questions": questions}

    def _mock_r2_data(self, rnd: random.Random, count: int, topic: Optional[str] = None, difficulty: Optional[str] = None) -> dict:
        questions = []
        for _ in range(count):
            t = topic or rnd.choice(B1_TOPICS)
            diff = difficulty if difficulty in ["easy", "medium", "hard"] else rnd.choice(["easy", "medium", "hard"])
            ref = rnd.choice(["A", "B", "C"])
            questions.append({
                "content": f"NOTICE: The presentation on {t} has been moved from Room 102 to Room 204. It will start at 10 AM instead of 9:30 AM.\nWhat change has been made?",
                "options": {
                    "A": "The location of the presentation.",
                    "B": "The speaker of the presentation.",
                    "C": "The price of the presentation."
                },
                "reference_answer": ref,
                "difficulty": diff,
                "clo": "Thông hiểu",
                "topic": t,
                "explanation": f"The notice specifies that the room changed from Room 102 to Room 204. Mock answer is {ref}."
            })
        return {"questions": questions}

    def _mock_r3_data(self, rnd: random.Random, count: int, topic: Optional[str] = None, difficulty: Optional[str] = None) -> dict:
        groups = []
        for _ in range(count):
            t = topic or rnd.choice(B1_TOPICS)
            diff = difficulty if difficulty in ["easy", "medium", "hard"] else rnd.choice(["easy", "medium", "hard"])
            questions = []
            for q_num in range(1, 6):
                ref = rnd.choice(["A", "B", "C", "D"])
                questions.append({
                    "content": f"According to paragraph {q_num}, which statement is true about {t}?",
                    "options": {
                        "A": f"Statement A for question {q_num}",
                        "B": f"Statement B for question {q_num}",
                        "C": f"Statement C for question {q_num}",
                        "D": f"Statement D for question {q_num}"
                    },
                    "reference_answer": ref,
                    "difficulty": diff,
                    "clo": "Thông hiểu",
                    "explanation": f"The passage states that option {ref} is correct."
                })
            groups.append({
                "passage_text": f"This passage discuss about the details of {t}. General paragraph describing various aspects. " * 15,
                "topic": t,
                "difficulty": diff,
                "questions": questions
            })
        return {"groups": groups}

    def _mock_r4_data(self, rnd: random.Random, count: int, topic: Optional[str] = None, difficulty: Optional[str] = None) -> dict:
        groups = []
        for _ in range(count):
            t = topic or rnd.choice(B1_TOPICS)
            diff = difficulty if difficulty in ["easy", "medium", "hard"] else rnd.choice(["easy", "medium", "hard"])
            g_idx = rnd.randint(100, 999)

            words = [f"word{i}_{g_idx}" for i in range(1, 16)]
            word_box = list(words)
            rnd.shuffle(word_box)

            passage_parts = []
            questions = []
            for q_num in range(21, 31):
                correct_word = words[q_num - 21]
                passage_parts.append(f"The group decided to ({q_num}) the options.")
                questions.append({
                    "blank_number": q_num,
                    "content": f"The group decided to ({q_num}) the options.",
                    "reference_answer": correct_word,
                    "difficulty": diff,
                    "clo": "Vận dụng có kiểm soát",
                    "explanation": f"The context requires the infinitive verb '{correct_word}'."
                })

            passage_text = " ".join(passage_parts)

            groups.append({
                "passage_text": passage_text,
                "word_box": word_box,
                "topic": t,
                "difficulty": diff,
                "questions": questions
            })
        return {"groups": groups}

    def _mock_writing_data(self, rnd: random.Random, count: int, part: int, topic: Optional[str] = None, difficulty: Optional[str] = None) -> dict:
        questions = []
        for _ in range(count):
            t = topic or rnd.choice(B1_TOPICS)
            diff = difficulty if difficulty in ["easy", "medium", "hard"] else rnd.choice(["easy", "medium", "hard"])
            if part == 5:
                content = f"Rewrite the following sentence about {t} using the given word:\n'It is important to study {t} every day.'\n-> You must..."
                clo = "Vận dụng có kiểm soát"
            else:
                content = f"Write an email (~100-120 words) to your friend talking about your experience with {t}.\nYou should mention:\n- What you did\n- Why you liked it\n- Your future plans about {t}."
                clo = "Vận dụng tổng hợp"

            questions.append({
                "part": part,
                "type": "writing",
                "content": content,
                "difficulty": diff,
                "clo": clo,
                "topic": t,
                "explanation": f"Mock explanation for Writing Part {part} topic {t}."
            })
        return {"questions": questions}

    def _mock_speaking_data(self, rnd: random.Random, count: int, part: int, topic: Optional[str] = None, difficulty: Optional[str] = None) -> dict:
        questions = []
        for _ in range(count):
            t = topic or rnd.choice(B1_TOPICS)
            diff = difficulty if difficulty in ["easy", "medium", "hard"] else rnd.choice(["easy", "medium", "hard"])
            if part == 9:
                content = f"Answer three questions about {t}:\n1. Do you like {t}?\n2. How often do you learn about {t}?\n3. Who do you share {t} with?"
                clo = "Vận dụng có kiểm soát"
            elif part == 10:
                content = f"Situation: You want to choose a topic related to {t} for a presentation. Three options: Option A, Option B, Option C. Discuss which option is the best."
                clo = "Vận dụng có kiểm soát"
            else:
                content = f"Topic Development: 'Discuss the role of {t} in modern society.'\nPoints:\n- Job opportunities\n- Personal development\n- Global communication\nFollow-up question: What are the main challenges related to {t}?"
                clo = "Vận dụng tổng hợp"

            questions.append({
                "part": part,
                "type": "speaking",
                "content": content,
                "difficulty": diff,
                "clo": clo,
                "topic": t,
                "explanation": f"Mock explanation for Speaking Part {part} topic {t}."
            })
        return {"questions": questions}

    def _mock_l2_data(self, rnd: random.Random, count: int, topic: Optional[str] = None, difficulty: Optional[str] = None) -> dict:
        groups = []
        for _ in range(count):
            t = topic or rnd.choice(B1_TOPICS)
            diff = difficulty if difficulty in ["easy", "medium", "hard"] else rnd.choice(["easy", "medium", "hard"])
            
            script_parts = []
            note_parts = [f"Notes on {t}:"]
            questions = []
            
            for idx in range(1, 11):
                correct_answer = f"val{idx}_{rnd.randint(100, 999)}"
                script_parts.append(f"For item {idx}, the correct information is {correct_answer}.")
                note_parts.append(f"- Point {idx}: ({idx})")
                questions.append({
                    "blank_number": idx,
                    "content": f"The lecture notes mention that point {idx} is ({idx}).",
                    "reference_answer": correct_answer,
                    "difficulty": diff,
                    "clo": "Thông hiểu",
                    "explanation": f"The script explicitly says: '{correct_answer}'."
                })
            
            script_text = " ".join(script_parts)
            note_template = "\n".join(note_parts)
            
            groups.append({
                "script_text": script_text,
                "note_template": note_template,
                "topic": t,
                "difficulty": diff,
                "questions": questions
            })
        return {"groups": groups}

    def _mock_l1_data(self, rnd: random.Random, count: int, topic: Optional[str] = None, difficulty: Optional[str] = None) -> dict:
        questions = []
        for _ in range(count):
            t = topic or rnd.choice(B1_TOPICS)
            diff = difficulty if difficulty in ["easy", "medium", "hard"] else rnd.choice(["easy", "medium", "hard"])
            clo = rnd.choice(["Nhận diện", "Thông hiểu"])
            ref = rnd.choice(["A", "B", "C"])
            questions.append({
                "script_text": f"This is a mock listening script about {t}. The correct answer is option {ref}.",
                "question_text": f"Which picture shows the correct item related to {t}?",
                "description_a": f"A simple black and white line drawing representing option A for {t}.",
                "description_b": f"A simple black and white line drawing representing option B for {t}.",
                "description_c": f"A simple black and white line drawing representing option C for {t}.",
                "reference_answer": ref,
                "difficulty": diff,
                "clo": clo,
                "topic": t,
                "explanation": f"The script mentions that option {ref} is correct."
            })
        return {"questions": questions}
