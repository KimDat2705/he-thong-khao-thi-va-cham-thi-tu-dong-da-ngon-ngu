import json
import logging
import random
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

    def _call_gemini(self, system_instruction: str, user_prompt: str) -> str:
        """Call Gemini using the google-genai Client and return the raw text response."""
        if not self.client:
            raise RuntimeError("Gemini client is not initialized.")

        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=[system_instruction, user_prompt],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json"
                )
            )
            return response.text
        except Exception as e:
            logger.error(f"Gemini API call failed: {e}")
            raise e

    def generate_r1_questions(self, db: Session, count: int, topic: Optional[str] = None, seed: Optional[int] = None) -> int:
        """Generate R1 (Part 1 Standalone Choice) questions and save to the bank."""
        if topic and topic not in B1_TOPICS:
            raise ValueError(f"Invalid topic '{topic}'. Must be one of {B1_TOPICS}")

        if not self.client:
            # Mock mode
            rnd = random.Random(seed)
            data = self._mock_r1_data(rnd, count, topic)
        else:
            system_instruction = (
                "You are an expert English language examiner. Generate a batch of VSTEP B1 Reading Part 1 standalone multiple-choice questions.\n"
                "Each question must test English grammar, vocabulary, or semantics suitable for CEFR B1 level.\n"
                "Provide a gap placeholder '______' in the question content.\n"
                "Options must contain exactly 4 options (A, B, C, D) and reference_answer must be A, B, C, or D.\n"
                "The CLO must be 'Nhận diện' or 'Thông hiểu'.\n"
                "The difficulty must be exactly one of: easy, medium, hard.\n"
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
                difficulty = diff_val if diff_val in ["easy", "medium", "hard"] else "medium"

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

    def generate_r3_groups(self, db: Session, count: int, topic: Optional[str] = None, seed: Optional[int] = None) -> int:
        """Generate R3 (Part 3 Passage + 5 Choice Questions) groups and save to the bank."""
        if topic and topic not in B1_TOPICS:
            raise ValueError(f"Invalid topic '{topic}'. Must be one of {B1_TOPICS}")

        if not self.client:
            # Mock mode
            rnd = random.Random(seed)
            data = self._mock_r3_data(rnd, count, topic)
        else:
            system_instruction = (
                "You are an expert English language examiner. Generate a batch of VSTEP B1 Reading Part 3 question groups.\n"
                "Each group must contain:\n"
                "1. A passage_text of 200-300 words.\n"
                "2. A topic from the 14 valid B1 topics.\n"
                "3. Exactly 5 child questions of 'choice' type based on the passage.\n"
                "Each child question must have options (A, B, C, D), reference_answer (A, B, C, or D), CLO='Thông hiểu'.\n"
                "The difficulty must be exactly one of: easy, medium, hard.\n"
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
                g_difficulty = diff_val if diff_val in ["easy", "medium", "hard"] else "medium"

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
                    q_difficulty = q_diff_val if q_diff_val in ["easy", "medium", "hard"] else "medium"

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

    def generate_r4_groups(self, db: Session, count: int, topic: Optional[str] = None, seed: Optional[int] = None) -> int:
        """Generate R4 (Part 4 Cloze Passage with blanks 21-30 + word box of 15 words) groups and save to the bank."""
        if topic and topic not in B1_TOPICS:
            raise ValueError(f"Invalid topic '{topic}'. Must be one of {B1_TOPICS}")

        if not self.client:
            # Mock mode
            rnd = random.Random(seed)
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
                "The difficulty must be exactly one of: easy, medium, hard.\n"
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
                g_difficulty = diff_val if diff_val in ["easy", "medium", "hard"] else "medium"

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
                    q_difficulty = q_diff_val if q_diff_val in ["easy", "medium", "hard"] else "medium"

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

    # --- Deterministic Mock Data Generators ---

    def generate_writing_questions(self, db: Session, count: int, part: int, topic: Optional[str] = None, seed: Optional[int] = None) -> int:
        """Generate Writing questions (Part 5 (W1) or Part 6 (W2)) and save to the bank."""
        if part not in (5, 6):
            raise ValueError(f"Invalid Writing part '{part}'. Must be 5 or 6.")
        if topic and topic not in B1_TOPICS:
            raise ValueError(f"Invalid topic '{topic}'. Must be one of {B1_TOPICS}")

        expected_clo = "Vận dụng có kiểm soát" if part == 5 else "Vận dụng tổng hợp"

        if not self.client:
            # Mock mode
            rnd = random.Random(seed)
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
                "The difficulty must be exactly one of: easy, medium, hard.\n"
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
                difficulty = diff_val if diff_val in ["easy", "medium", "hard"] else "medium"

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

    def generate_speaking_questions(self, db: Session, count: int, part: int, topic: Optional[str] = None, seed: Optional[int] = None) -> int:
        """Generate Speaking questions (Part 9 (S1), Part 10 (S2), Part 11 (S3)) and save to the bank."""
        if part not in (9, 10, 11):
            raise ValueError(f"Invalid Speaking part '{part}'. Must be 9, 10, or 11.")
        if topic and topic not in B1_TOPICS:
            raise ValueError(f"Invalid topic '{topic}'. Must be one of {B1_TOPICS}")

        expected_clo = "Vận dụng tổng hợp" if part == 11 else "Vận dụng có kiểm soát"

        if not self.client:
            # Mock mode
            rnd = random.Random(seed)
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
                "The difficulty must be exactly one of: easy, medium, hard.\n"
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
                difficulty = diff_val if diff_val in ["easy", "medium", "hard"] else "medium"

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

    def _mock_r1_data(self, rnd: random.Random, count: int, topic: Optional[str] = None) -> dict:
        questions = []
        for _ in range(count):
            t = topic or rnd.choice(B1_TOPICS)
            diff = rnd.choice(["easy", "medium", "hard"])
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

    def _mock_r3_data(self, rnd: random.Random, count: int, topic: Optional[str] = None) -> dict:
        groups = []
        for _ in range(count):
            t = topic or rnd.choice(B1_TOPICS)
            diff = rnd.choice(["easy", "medium", "hard"])
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

    def _mock_r4_data(self, rnd: random.Random, count: int, topic: Optional[str] = None) -> dict:
        groups = []
        for _ in range(count):
            t = topic or rnd.choice(B1_TOPICS)
            diff = rnd.choice(["easy", "medium", "hard"])
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

    def _mock_writing_data(self, rnd: random.Random, count: int, part: int, topic: Optional[str] = None) -> dict:
        questions = []
        for _ in range(count):
            t = topic or rnd.choice(B1_TOPICS)
            diff = rnd.choice(["easy", "medium", "hard"])
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

    def _mock_speaking_data(self, rnd: random.Random, count: int, part: int, topic: Optional[str] = None) -> dict:
        questions = []
        for _ in range(count):
            t = topic or rnd.choice(B1_TOPICS)
            diff = rnd.choice(["easy", "medium", "hard"])
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
