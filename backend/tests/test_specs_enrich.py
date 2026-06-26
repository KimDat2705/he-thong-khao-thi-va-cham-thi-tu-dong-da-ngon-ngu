from sqlalchemy.orm import Session
from app.models.question import Question
from app.models.question_group import QuestionGroup
from app.services.b1_question_gen import B1QuestionGenerator, B1_TOPICS
from app.core.config import settings

def test_SPEC_ENRICH_001_ai_question_generation_and_validation(db_session: Session, monkeypatch):
    """
    SPEC-ENRICH-001: AI-based VSTEP B1 Reading Question Ingestion and Validation.
    Asserts structure, validation, draft status, and idempotency in Mock mode.
    """
    # Force mock mode by setting GEMINI_API_KEY to None
    monkeypatch.setattr(settings, "GEMINI_API_KEY", None)

    generator = B1QuestionGenerator()

    # --- Part 1: Standalone Choice (R1) Verification ---
    r1_count_first = generator.generate_r1_questions(db=db_session, count=3, seed=42)
    assert r1_count_first == 3, "Generator should succeed in saving 3 R1 questions"

    # Query R1 questions in bank
    r1_questions = db_session.query(Question).filter(
        Question.exam_id.is_(None),
        Question.part == 1,
        Question.exam_type == "VSTEP_B1",
        Question.status == "draft"
    ).all()
    assert len(r1_questions) == 3

    for q in r1_questions:
        assert q.type == "choice"
        assert q.exam_type == "VSTEP_B1"
        assert q.language == "EN"
        assert q.status == "draft"
        assert q.group_id is None
        assert q.difficulty in ["easy", "medium", "hard"]
        assert q.clo in ["Nhận diện", "Thông hiểu"]
        assert q.topic in B1_TOPICS
        assert set(q.options.keys()) == {"A", "B", "C", "D"}
        assert q.reference_answer in {"A", "B", "C", "D"}
        assert q.content_hash is not None

    # --- Part 3: Passage-based Choice (R3) Verification ---
    r3_count_first = generator.generate_r3_groups(db=db_session, count=1, seed=42)
    assert r3_count_first == 1, "Generator should succeed in saving 1 R3 group"

    # Query R3 groups
    r3_groups = db_session.query(QuestionGroup).filter(
        QuestionGroup.exam_id.is_(None),
        QuestionGroup.part == 3,
        QuestionGroup.status == "draft"
    ).all()
    assert len(r3_groups) == 1
    g3 = r3_groups[0]
    assert len(g3.passage_text) > 100
    assert g3.topic in B1_TOPICS
    assert g3.difficulty in ["easy", "medium", "hard"]
    assert g3.status == "draft"
    assert g3.content_hash is not None

    # Child questions of R3 group
    g3_questions = db_session.query(Question).filter(
        Question.group_id == g3.id
    ).all()
    assert len(g3_questions) == 5, "R3 group must have exactly 5 child questions"
    for q in g3_questions:
        assert q.part == 3
        assert q.type == "choice"
        assert q.exam_type == "VSTEP_B1"
        assert q.language == "EN"
        assert q.status == "draft"
        assert q.clo == "Thông hiểu"
        assert set(q.options.keys()) == {"A", "B", "C", "D"}
        assert q.reference_answer in {"A", "B", "C", "D"}
        assert q.content_hash is not None

    # --- Part 4: Cloze Fill (R4) Verification ---
    r4_count_first = generator.generate_r4_groups(db=db_session, count=1, seed=42)
    assert r4_count_first == 1, "Generator should succeed in saving 1 R4 group"

    # Query R4 groups
    r4_groups = db_session.query(QuestionGroup).filter(
        QuestionGroup.exam_id.is_(None),
        QuestionGroup.part == 4,
        QuestionGroup.status == "draft"
    ).all()
    assert len(r4_groups) == 1
    g4 = r4_groups[0]
    assert "Choose the correct word from the box below" in g4.passage_text
    assert "Passage:" in g4.passage_text
    assert g4.topic in B1_TOPICS
    assert g4.difficulty in ["easy", "medium", "hard"]
    assert g4.status == "draft"
    assert g4.content_hash is not None

    # Child questions of R4 group
    g4_questions = db_session.query(Question).filter(
        Question.group_id == g4.id
    ).all()
    assert len(g4_questions) == 10, "R4 group must have exactly 10 child questions"
    
    # Extract word box values from formatted passage
    import re
    word_box_matches = re.findall(r'\[(.*?)\]', g4.passage_text)
    assert len(word_box_matches) == 15, "Formatted passage text must display 15 words in brackets"

    for q in g4_questions:
        assert q.part == 4
        assert q.type == "fill"
        assert q.exam_type == "VSTEP_B1"
        assert q.language == "EN"
        assert q.status == "draft"
        assert q.clo == "Vận dụng có kiểm soát"
        assert q.options == {} or q.options is None
        assert q.reference_answer in word_box_matches, f"Answer '{q.reference_answer}' must exist in word box {word_box_matches}"
        assert q.content_hash is not None

    # --- Idempotency (Chạy lại KHÔNG trùng) Verification ---
    # Running again with the exact same seed:
    # 1) R1
    r1_count_second = generator.generate_r1_questions(db=db_session, count=3, seed=42)
    assert r1_count_second == 0, "Second call with same seed must insert 0 questions (skipped duplicates)"
    r1_questions_after = db_session.query(Question).filter(
        Question.exam_id.is_(None),
        Question.part == 1,
        Question.exam_type == "VSTEP_B1",
        Question.status == "draft"
    ).all()
    assert len(r1_questions_after) == 3, "R1 question count should not increase"

    # 2) R3
    r3_count_second = generator.generate_r3_groups(db=db_session, count=1, seed=42)
    assert r3_count_second == 0, "Second call with same seed must insert 0 R3 groups"
    r3_groups_after = db_session.query(QuestionGroup).filter(
        QuestionGroup.exam_id.is_(None),
        QuestionGroup.part == 3,
        QuestionGroup.status == "draft"
    ).all()
    assert len(r3_groups_after) == 1, "R3 group count should not increase"

    # 3) R4
    r4_count_second = generator.generate_r4_groups(db=db_session, count=1, seed=42)
    assert r4_count_second == 0, "Second call with same seed must insert 0 R4 groups"
    r4_groups_after = db_session.query(QuestionGroup).filter(
        QuestionGroup.exam_id.is_(None),
        QuestionGroup.part == 4,
        QuestionGroup.status == "draft"
    ).all()
    assert len(r4_groups_after) == 1, "R4 group count should not increase"


def test_SPEC_ENRICH_001_validation_gate_rejects_invalid(db_session: Session, monkeypatch):
    """
    SPEC-ENRICH-001 (negative / non-tautological): the validation gate must REJECT
    malformed generated items (bad CLO, wrong option count, invalid reference) and
    only persist the valid ones — proving the gate works, not just that the mock is
    well-formed. Feeds a crafted batch (1 valid + 3 invalid) into the R1 path.
    """
    monkeypatch.setattr(settings, "GEMINI_API_KEY", None)
    gen = B1QuestionGenerator()

    crafted = {"questions": [
        {  # VALID
            "content": "She ______ to school every morning.",
            "options": {"A": "go", "B": "goes", "C": "going", "D": "gone"},
            "reference_answer": "B", "difficulty": "easy",
            "clo": "Nhận diện", "topic": B1_TOPICS[0], "explanation": "x",
        },
        {  # INVALID: CLO not allowed for R1
            "content": "They ______ dinner now.",
            "options": {"A": "have", "B": "has", "C": "having", "D": "had"},
            "reference_answer": "A", "difficulty": "easy",
            "clo": "Vận dụng tổng hợp", "topic": B1_TOPICS[0], "explanation": "x",
        },
        {  # INVALID: only 3 options (must be A-D)
            "content": "He ______ a car.",
            "options": {"A": "drive", "B": "drives", "C": "driving"},
            "reference_answer": "B", "difficulty": "easy",
            "clo": "Nhận diện", "topic": B1_TOPICS[0], "explanation": "x",
        },
        {  # INVALID: reference_answer outside A-D
            "content": "We ______ football.",
            "options": {"A": "play", "B": "plays", "C": "playing", "D": "played"},
            "reference_answer": "Z", "difficulty": "easy",
            "clo": "Nhận diện", "topic": B1_TOPICS[0], "explanation": "x",
        },
    ]}
    # Force the generator to ingest the crafted (mixed) batch instead of clean mock data.
    monkeypatch.setattr(gen, "_mock_r1_data", lambda rnd, count, topic=None: crafted)

    saved = gen.generate_r1_questions(db=db_session, count=4, seed=1)
    # Definitive proof the validation gate works: of 4 fed, only the 1 valid persists.
    assert saved == 1, "Only the 1 valid item must be saved; the 3 malformed items must be skipped"

    # State-independent checks (db_session may hold rows from other tests): assert by
    # the crafted batch's unique signatures rather than total bank counts.
    valid = db_session.query(Question).filter(
        Question.content == "She ______ to school every morning."
    ).all()
    assert len(valid) == 1 and valid[0].reference_answer == "B", "the valid item must be ingested"
    assert set(valid[0].options.keys()) == {"A", "B", "C", "D"}

    # The 3 malformed items must NOT exist in the bank (gate rejected them).
    assert db_session.query(Question).filter(Question.reference_answer == "Z").count() == 0, "bad-reference item must be rejected"
    assert db_session.query(Question).filter(Question.content == "He ______ a car.").count() == 0, "3-option item must be rejected"
    assert db_session.query(Question).filter(Question.clo == "Vận dụng tổng hợp", Question.part == 1).count() == 0, "bad-CLO item must be rejected"
