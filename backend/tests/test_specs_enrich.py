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


def test_SPEC_ENRICH_002_ai_writing_speaking_generation_and_validation(db_session: Session, monkeypatch):
    """
    SPEC-ENRICH-002: AI-based VSTEP B1 Writing and Speaking Prompt Ingestion and Validation.
    Asserts structure, validation, draft status, negative validation, and idempotency in Mock mode.
    """
    monkeypatch.setattr(settings, "GEMINI_API_KEY", None)

    generator = B1QuestionGenerator()

    # 1. Verify W1 (Part 5) and W2 (Part 6) Structure
    w1_saved = generator.generate_writing_questions(db=db_session, count=2, part=5, seed=123)
    w2_saved = generator.generate_writing_questions(db=db_session, count=2, part=6, seed=123)
    assert w1_saved == 2
    assert w2_saved == 2

    # Query and assert on W1
    w1_qs = db_session.query(Question).filter(
        Question.exam_id.is_(None),
        Question.part == 5,
        Question.type == "writing",
        Question.status == "draft"
    ).all()
    assert len(w1_qs) == 2
    for q in w1_qs:
        assert q.clo == "Vận dụng có kiểm soát"
        assert q.options == {} or q.options is None
        assert q.reference_answer is None
        assert q.status == "draft"
        assert q.difficulty in ["easy", "medium", "hard"]
        assert q.topic in B1_TOPICS
        assert len(q.content.strip()) >= 20

    # Query and assert on W2
    w2_qs = db_session.query(Question).filter(
        Question.exam_id.is_(None),
        Question.part == 6,
        Question.type == "writing",
        Question.status == "draft"
    ).all()
    assert len(w2_qs) == 2
    for q in w2_qs:
        assert q.clo == "Vận dụng tổng hợp"
        assert q.options == {} or q.options is None
        assert q.reference_answer is None
        assert q.status == "draft"
        assert len(q.content.strip()) >= 20

    # 2. Verify S1 (Part 9), S2 (Part 10), S3 (Part 11) Structure
    s1_saved = generator.generate_speaking_questions(db=db_session, count=1, part=9, seed=123)
    s2_saved = generator.generate_speaking_questions(db=db_session, count=1, part=10, seed=123)
    s3_saved = generator.generate_speaking_questions(db=db_session, count=1, part=11, seed=123)
    assert s1_saved == 1
    assert s2_saved == 1
    assert s3_saved == 1

    # Query and assert Speaking
    speaking_qs = db_session.query(Question).filter(
        Question.exam_id.is_(None),
        Question.part.in_([9, 10, 11]),
        Question.type == "speaking",
        Question.status == "draft"
    ).all()
    assert len(speaking_qs) == 3
    for q in speaking_qs:
        assert q.status == "draft"
        assert q.options == {} or q.options is None
        assert q.reference_answer is None
        if q.part in [9, 10]:
            assert q.clo == "Vận dụng có kiểm soát"
        elif q.part == 11:
            assert q.clo == "Vận dụng tổng hợp"

    # 3. Idempotency (same seed does not insert duplicates)
    w1_dup_saved = generator.generate_writing_questions(db=db_session, count=2, part=5, seed=123)
    assert w1_dup_saved == 0, "Idempotency check should skip duplicate content hashes for writing"
    
    s1_dup_saved = generator.generate_speaking_questions(db=db_session, count=1, part=9, seed=123)
    assert s1_dup_saved == 0, "Idempotency check should skip duplicate content hashes for speaking"

    # 4. Negative Validation Cases: Rejects items with bad type, clo, topic or too short content
    crafted_writing = {"questions": [
        { # VALID
            "part": 5, "type": "writing", "content": "This is a valid sentence rewriting prompt that is long enough.",
            "difficulty": "easy", "clo": "Vận dụng có kiểm soát", "topic": B1_TOPICS[0]
        },
        { # INVALID: content too short
            "part": 5, "type": "writing", "content": "Too short.",
            "difficulty": "easy", "clo": "Vận dụng có kiểm soát", "topic": B1_TOPICS[0]
        },
        { # INVALID: wrong type
            "part": 5, "type": "choice", "content": "This has a choice type instead of writing type which is wrong.",
            "difficulty": "easy", "clo": "Vận dụng có kiểm soát", "topic": B1_TOPICS[0]
        },
        { # INVALID: wrong clo
            "part": 5, "type": "writing", "content": "This is a prompt with a wrong clo for part 5.",
            "difficulty": "easy", "clo": "Vận dụng tổng hợp", "topic": B1_TOPICS[0]
        },
        { # INVALID: wrong part
            "part": 6, "type": "writing", "content": "This is a prompt with a wrong part for part 5 call.",
            "difficulty": "easy", "clo": "Vận dụng có kiểm soát", "topic": B1_TOPICS[0]
        }
    ]}
    monkeypatch.setattr(generator, "_mock_writing_data", lambda rnd, count, part, topic=None: crafted_writing)
    # Using a new seed to make sure we don't hit idempotency check from step 1
    w1_neg_saved = generator.generate_writing_questions(db=db_session, count=5, part=5, seed=999)
    assert w1_neg_saved == 1, "Only 1 valid question should be saved, 4 malformed skipped"

    # Verify the one valid writing question is in the db and the invalid ones are not
    valid_neg_q = db_session.query(Question).filter(
        Question.content == "This is a valid sentence rewriting prompt that is long enough."
    ).first()
    assert valid_neg_q is not None
    assert valid_neg_q.part == 5

    assert db_session.query(Question).filter(Question.content == "Too short.").count() == 0
    assert db_session.query(Question).filter(Question.content == "This has a choice type instead of writing type which is wrong.").count() == 0
    assert db_session.query(Question).filter(Question.content == "This is a prompt with a wrong clo for part 5.").count() == 0
    assert db_session.query(Question).filter(Question.content == "This is a prompt with a wrong part for part 5 call.").count() == 0


def test_SPEC_ENRICH_003_ai_r2_generation_and_validation(db_session: Session, monkeypatch):
    """
    SPEC-ENRICH-003: AI-based VSTEP B1 Reading Part 2 Ingestion and Validation.
    Asserts structure, validation, draft status, negative validation, and idempotency in Mock mode.
    """
    monkeypatch.setattr(settings, "GEMINI_API_KEY", None)

    generator = B1QuestionGenerator()

    # 1. Happy path: generate 3 questions
    r2_saved = generator.generate_r2_questions(db=db_session, count=3, seed=123)
    assert r2_saved == 3

    # Query and assert
    r2_qs = db_session.query(Question).filter(
        Question.exam_id.is_(None),
        Question.part == 2,
        Question.type == "choice",
        Question.content.like("NOTICE: The presentation on%")
    ).all()
    assert len(r2_qs) == 3
    for q in r2_qs:
        assert q.clo == "Thông hiểu"
        assert set(q.options.keys()) == {"A", "B", "C"}
        assert q.reference_answer in {"A", "B", "C"}
        assert q.status == "draft"
        assert q.difficulty in ["easy", "medium", "hard"]
        assert q.topic in B1_TOPICS
        assert len(q.content.strip()) >= 20

    # 2. Idempotency: same seed does not insert duplicates
    r2_dup_saved = generator.generate_r2_questions(db=db_session, count=3, seed=123)
    assert r2_dup_saved == 0, "Idempotency check should skip duplicate content hashes"

    # 3. Negative validation cases: rejects bad type, clo, ref, options count, or too short content
    crafted_r2 = {"questions": [
        { # VALID
            "content": "NOTICE: This is a valid notice content for testing that is long enough.",
            "options": {"A": "Correct", "B": "Wrong 1", "C": "Wrong 2"},
            "reference_answer": "A", "difficulty": "easy", "clo": "Thông hiểu", "topic": B1_TOPICS[0]
        },
        { # INVALID: content too short
            "content": "Too short.",
            "options": {"A": "Correct", "B": "Wrong 1", "C": "Wrong 2"},
            "reference_answer": "A", "difficulty": "easy", "clo": "Thông hiểu", "topic": B1_TOPICS[0]
        },
        { # INVALID: 4 options instead of 3
            "content": "NOTICE: This notice has four options instead of three options.",
            "options": {"A": "Correct", "B": "Wrong 1", "C": "Wrong 2", "D": "Wrong 3"},
            "reference_answer": "A", "difficulty": "easy", "clo": "Thông hiểu", "topic": B1_TOPICS[0]
        },
        { # INVALID: wrong CLO
            "content": "NOTICE: This notice has an invalid CLO for Part 2.",
            "options": {"A": "Correct", "B": "Wrong 1", "C": "Wrong 2"},
            "reference_answer": "A", "difficulty": "easy", "clo": "Vận dụng tổng hợp", "topic": B1_TOPICS[0]
        },
        { # INVALID: reference answer outside A-C
            "content": "NOTICE: This notice has a reference answer that is D instead of A-C.",
            "options": {"A": "Correct", "B": "Wrong 1", "C": "Wrong 2"},
            "reference_answer": "D", "difficulty": "easy", "clo": "Thông hiểu", "topic": B1_TOPICS[0]
        }
    ]}
    monkeypatch.setattr(generator, "_mock_r2_data", lambda rnd, count, topic=None: crafted_r2)
    # Using a new seed to make sure we don't hit idempotency check from step 1
    r2_neg_saved = generator.generate_r2_questions(db=db_session, count=5, seed=999)
    assert r2_neg_saved == 1, "Only 1 valid question should be saved, 4 malformed skipped"

    # Verify the one valid question is in the db and the invalid ones are not
    valid_neg_q = db_session.query(Question).filter(
        Question.content == "NOTICE: This is a valid notice content for testing that is long enough."
    ).first()
    assert valid_neg_q is not None
    assert valid_neg_q.part == 2

    assert db_session.query(Question).filter(Question.content == "Too short.").count() == 0
    assert db_session.query(Question).filter(Question.content == "NOTICE: This notice has four options instead of three options.").count() == 0
    assert db_session.query(Question).filter(Question.content == "NOTICE: This notice has an invalid CLO for Part 2.").count() == 0
    assert db_session.query(Question).filter(Question.content == "NOTICE: This notice has a reference answer that is D instead of A-C.").count() == 0


def test_SPEC_ENRICH_004_ai_l2_generation_and_validation(db_session: Session, monkeypatch):
    """
    SPEC-ENRICH-004: AI-based VSTEP B1 Listening Part 2 Ingestion and Validation.
    Asserts structure, validation, draft status, negative validation, and idempotency in Mock mode.
    """
    monkeypatch.setattr(settings, "GEMINI_API_KEY", None)

    generator = B1QuestionGenerator()

    # 1. Happy path: generate 1 group
    l2_saved = generator.generate_l2_groups(db=db_session, count=1, seed=123)
    assert l2_saved == 1

    # Query and assert
    l2_groups = db_session.query(QuestionGroup).filter(
        QuestionGroup.exam_id.is_(None),
        QuestionGroup.part == 8,
        QuestionGroup.passage_text.like("Notes on%")
    ).all()
    assert len(l2_groups) == 1
    g = l2_groups[0]
    assert g.status == "draft"
    assert g.topic in B1_TOPICS
    assert g.difficulty in ["easy", "medium", "hard"]
    assert g.audio_url.startswith("/static/audio_gen/")
    assert g.audio_url.endswith(".wav")

    # Verify audio file exists on disk
    import os
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    audio_path = os.path.join(backend_dir, g.audio_url.lstrip("/"))
    assert os.path.exists(audio_path), f"Audio file should exist at {audio_path}"

    # Verify child questions
    child_qs = db_session.query(Question).filter(
        Question.group_id == g.id
    ).all()
    assert len(child_qs) == 10
    for q in child_qs:
        assert q.part == 8
        assert q.type == "fill"
        assert q.clo == "Thông hiểu"
        assert q.options == {} or q.options is None
        assert q.status == "draft"
        assert q.reference_answer is not None
        assert len(q.content.strip()) >= 20

    # 2. Idempotency: same seed does not insert duplicates
    l2_dup_saved = generator.generate_l2_groups(db=db_session, count=1, seed=123)
    assert l2_dup_saved == 0, "Idempotency check should skip duplicate content hashes"

    # 3. Negative validation cases: rejects group with incorrect questions count, empty answers, or wrong CLO
    crafted_l2 = {"groups": [
        { # VALID
            "script_text": "This is a valid listening lecture script for testing that contains enough words.",
            "note_template": "Notes on topic:\n" + "\n".join(f"- Point {i}: ({i})" for i in range(1, 11)),
            "topic": B1_TOPICS[0], "difficulty": "easy",
            "questions": [
                {
                    "blank_number": i, "content": f"Context description for blank number ({i}) which is long enough.",
                    "reference_answer": f"val{i}", "difficulty": "easy", "clo": "Thông hiểu"
                } for i in range(1, 11)
            ]
        },
        { # INVALID: only 9 questions instead of 10
            "script_text": "This script has only nine child questions which is malformed.",
            "note_template": "Notes on topic:\n" + "\n".join(f"- Point {i}: ({i})" for i in range(1, 11)),
            "topic": B1_TOPICS[0], "difficulty": "easy",
            "questions": [
                {
                    "blank_number": i, "content": f"Context description for blank number ({i}) which is long enough.",
                    "reference_answer": f"val{i}", "difficulty": "easy", "clo": "Thông hiểu"
                } for i in range(1, 10)
            ]
        },
        { # INVALID: one child question has empty reference answer
            "script_text": "This script has one child question with an empty answer.",
            "note_template": "Notes on topic:\n" + "\n".join(f"- Point {i}: ({i})" for i in range(1, 11)),
            "topic": B1_TOPICS[0], "difficulty": "easy",
            "questions": [
                {
                    "blank_number": i, "content": f"Context description for blank number ({i}) which is long enough.",
                    "reference_answer": "" if i == 5 else f"val{i}", "difficulty": "easy", "clo": "Thông hiểu"
                } for i in range(1, 11)
            ]
        },
        { # INVALID: wrong CLO for child questions
            "script_text": "This script has wrong CLO.",
            "note_template": "Notes on topic:\n" + "\n".join(f"- Point {i}: ({i})" for i in range(1, 11)),
            "topic": B1_TOPICS[0], "difficulty": "easy",
            "questions": [
                {
                    "blank_number": i, "content": f"Context description for blank number ({i}) which is long enough.",
                    "reference_answer": f"val{i}", "difficulty": "easy", "clo": "Vận dụng tổng hợp"
                } for i in range(1, 11)
            ]
        }
    ]}
    monkeypatch.setattr(generator, "_mock_l2_data", lambda rnd, count, topic=None: crafted_l2)
    # Using a new seed to make sure we don't hit idempotency check from step 1
    l2_neg_saved = generator.generate_l2_groups(db=db_session, count=4, seed=999)
    assert l2_neg_saved == 1, "Only 1 valid group should be saved, 3 malformed skipped"

    # Verify the one valid group exists
    valid_neg_group = db_session.query(QuestionGroup).filter(
        QuestionGroup.passage_text.like("Notes on topic%"),
        QuestionGroup.exam_id.is_(None)
    ).first()
    assert valid_neg_group is not None

    # The invalid groups must not exist in the bank
    assert db_session.query(QuestionGroup).filter(
        QuestionGroup.passage_text == "Notes on topic:\n" + "\n".join(f"- Point {i}: ({i})" for i in range(1, 11)),
        QuestionGroup.exam_id.is_(None)
    ).count() == 1


def test_SPEC_ENRICH_005_ai_l1_generation_and_validation(db_session: Session, monkeypatch):
    """
    SPEC-ENRICH-005: AI-based VSTEP B1 Listening Part 1 Ingestion and Validation.
    Asserts structure, validation, draft status, assets existence, negative validation, and idempotency in Mock mode.
    """
    monkeypatch.setattr(settings, "GEMINI_API_KEY", None)

    generator = B1QuestionGenerator()

    # 1. Happy path: generate 2 questions
    l1_saved = generator.generate_l1_questions(db=db_session, count=2, seed=123)
    assert l1_saved == 2

    # Query and assert
    l1_qs = db_session.query(Question).filter(
        Question.exam_id.is_(None),
        Question.part == 7,
        Question.type == "choice",
        Question.content.like("Which picture shows the correct item related to%")
    ).all()
    assert len(l1_qs) == 2

    import os
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    for q in l1_qs:
        assert q.status == "draft"
        assert q.difficulty in ["easy", "medium", "hard"]
        assert q.clo in ["Thông hiểu", "Nhận diện"]
        assert q.topic in B1_TOPICS
        assert q.options == {} or q.options is None
        assert q.reference_answer in {"A", "B", "C"}
        assert len(q.content.strip()) >= 20

        # Check audio file
        assert q.audio_url.startswith("/static/audio_gen/")
        assert q.audio_url.endswith(".wav")
        audio_path = os.path.join(backend_dir, q.audio_url.lstrip("/"))
        assert os.path.exists(audio_path), f"Audio file should exist at {audio_path}"

        # Check 3 image files
        img_urls = q.image_url.split(",")
        assert len(img_urls) == 3, f"image_url must contain exactly 3 URLs, got: {img_urls}"
        for url in img_urls:
            assert url.startswith("/static/img/")
            assert url.endswith(".png")
            img_path = os.path.join(backend_dir, url.lstrip("/"))
            assert os.path.exists(img_path), f"Image file should exist at {img_path}"

    # 2. Idempotency: same seed does not insert duplicates
    l1_dup_saved = generator.generate_l1_questions(db=db_session, count=2, seed=123)
    assert l1_dup_saved == 0, "Idempotency check should skip duplicate content hashes"

    # 3. Negative validation cases: rejects bad type, clo, ref, missing assets, or too short content
    crafted_l1 = {"questions": [
        { # VALID
            "script_text": "This is a valid script that is long enough to read.",
            "question_text": "Which is the valid question text?",
            "description_a": "Drawing of a cat.",
            "description_b": "Drawing of a dog.",
            "description_c": "Drawing of a bird.",
            "reference_answer": "A", "difficulty": "easy", "clo": "Thông hiểu", "topic": B1_TOPICS[0]
        },
        { # INVALID: reference answer outside A-C
            "script_text": "Script with wrong reference.",
            "question_text": "Question with wrong reference?",
            "description_a": "Cat", "description_b": "Dog", "description_c": "Bird",
            "reference_answer": "D", "difficulty": "easy", "clo": "Thông hiểu", "topic": B1_TOPICS[0]
        },
        { # INVALID: wrong CLO for Listening Part 1
            "script_text": "Script with wrong CLO.",
            "question_text": "Question with wrong CLO?",
            "description_a": "Cat", "description_b": "Dog", "description_c": "Bird",
            "reference_answer": "A", "difficulty": "easy", "clo": "Vận dụng tổng hợp", "topic": B1_TOPICS[0]
        },
        { # INVALID: topic not in B1 topics
            "script_text": "Script with wrong topic.",
            "question_text": "Question with wrong topic?",
            "description_a": "Cat", "description_b": "Dog", "description_c": "Bird",
            "reference_answer": "A", "difficulty": "easy", "clo": "Thông hiểu", "topic": "Invalid Topic"
        }
    ]}
    
    monkeypatch.setattr(generator, "_mock_l1_data", lambda rnd, count, topic=None: crafted_l1)
    # Using a new seed to make sure we don't hit idempotency check from step 1
    l1_neg_saved = generator.generate_l1_questions(db=db_session, count=4, seed=999)
    assert l1_neg_saved == 1, "Only 1 valid question should be saved, 3 malformed skipped"

    # Verify the one valid question is in the db and the invalid ones are not
    valid_neg_q = db_session.query(Question).filter(
        Question.content == "Which is the valid question text?",
        Question.exam_id.is_(None)
    ).first()
    assert valid_neg_q is not None
    assert valid_neg_q.part == 7

    assert db_session.query(Question).filter(Question.content == "Question with wrong reference?").count() == 0
    assert db_session.query(Question).filter(Question.content == "Question with wrong CLO?").count() == 0
    assert db_session.query(Question).filter(Question.content == "Question with wrong topic?").count() == 0




