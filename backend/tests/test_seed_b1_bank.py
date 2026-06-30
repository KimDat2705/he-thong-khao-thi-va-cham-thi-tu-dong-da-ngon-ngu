import os
import json
from sqlalchemy.orm import Session

from app.models.question import Question
from app.models.question_group import QuestionGroup
from scripts.seed_b1_bank import seed_from_json


def test_seed_b1_bank_idempotency_and_update(db_session: Session, tmp_path):
    # 1. Create a TOEIC question to verify it is untouched
    toeic_q = Question(
        exam_id=None,
        group_id=None,
        part=1,
        type="choice",
        content="TOEIC Question Content",
        options={"A": "opt1", "B": "opt2"},
        reference_answer="A",
        difficulty="easy",
        status="draft",
        exam_type="TOEFL",
        language="EN",
        content_hash="toeic_hash_123"
    )
    db_session.add(toeic_q)

    # 2. Create a pre-existing B1 question in "draft" status to verify it gets updated to "approved"
    pre_existing_q = Question(
        exam_id=None,
        group_id=None,
        part=5,
        type="writing",
        content="Pre-existing Writing prompt",
        options={},
        reference_answer="",
        difficulty="medium",
        status="draft",
        exam_type="VSTEP_B1",
        language="EN",
        content_hash="b1_draft_hash_123"
    )
    db_session.add(pre_existing_q)
    db_session.commit()

    initial_count = db_session.query(Question).filter(
        Question.exam_id.is_(None),
        Question.exam_type == "VSTEP_B1"
    ).count()

    # 3. Create mock JSON payload with B1 questions/groups
    mock_data = {
        "groups": [
            {
                "part": 3,
                "topic": "Family",
                "passage_text": "Passage text about family.",
                "audio_url": None,
                "image_url": None,
                "passage_type": "notice",
                "speaker_count": 2,
                "speech_rate": "normal",
                "accent": "American",
                "difficulty": "medium",
                "status": "draft",
                "content_hash": "mock_group_hash_456",
                "questions": [
                    {
                        "part": 3,
                        "type": "choice",
                        "content": "Group Question 1",
                        "audio_url": None,
                        "image_url": None,
                        "options": {"A": "Yes", "B": "No"},
                        "reference_answer": "A",
                        "difficulty": "medium",
                        "clo": "Understanding",
                        "topic": "Family",
                        "status": "draft",
                        "explanation": None,
                        "exam_type": "VSTEP_B1",
                        "language": "EN",
                        "content_hash": "child_q_hash_1"
                    },
                    {
                        "part": 3,
                        "type": "choice",
                        "content": "Group Question 2",
                        "audio_url": None,
                        "image_url": None,
                        "options": {"A": "Maybe", "B": "Never"},
                        "reference_answer": "B",
                        "difficulty": "medium",
                        "clo": "Understanding",
                        "topic": "Family",
                        "status": "draft",
                        "explanation": None,
                        "exam_type": "VSTEP_B1",
                        "language": "EN",
                        "content_hash": "child_q_hash_2"
                    }
                ]
            }
        ],
        "standalone_questions": [
            {
                "part": 5,
                "type": "writing",
                "content": "Pre-existing Writing prompt", # Match pre_existing_q content_hash
                "audio_url": None,
                "image_url": None,
                "options": {},
                "reference_answer": "",
                "difficulty": "medium",
                "clo": "Writing Skill",
                "topic": "Work",
                "status": "draft",
                "explanation": None,
                "exam_type": "VSTEP_B1",
                "language": "EN",
                "content_hash": "b1_draft_hash_123"
            },
            {
                "part": 1,
                "type": "choice",
                "content": "New Standalone Choice",
                "audio_url": "/static/audio_gen/new.wav",
                "image_url": "/static/img/new.png",
                "options": {"A": "One", "B": "Two", "C": "Three", "D": "Four"},
                "reference_answer": "C",
                "difficulty": "easy",
                "clo": "Recognition",
                "topic": "General",
                "status": "draft",
                "explanation": "Simple choice",
                "exam_type": "VSTEP_B1",
                "language": "EN",
                "content_hash": "standalone_new_hash_789"
            }
        ]
    }

    # Write to a temporary file
    temp_json = tmp_path / "mock_b1_bank.json"
    with open(temp_json, "w", encoding="utf-8") as f:
        json.dump(mock_data, f)

    # 4. Run seeder for the FIRST time
    success = seed_from_json(db_session, str(temp_json))
    assert success is True

    # 5. Assert database records after first seed
    # Verify group was created with status approved
    seeded_g = db_session.query(QuestionGroup).filter(QuestionGroup.content_hash == "mock_group_hash_456").first()
    assert seeded_g is not None
    assert seeded_g.status == "approved"
    assert seeded_g.part == 3
    assert seeded_g.topic == "Family"

    # Verify child questions are created under the group and updated to approved
    child_qs = db_session.query(Question).filter(Question.group_id == seeded_g.id).all()
    assert len(child_qs) == 2
    for cq in child_qs:
        assert cq.status == "approved"
        assert cq.exam_type == "VSTEP_B1"

    # Verify the pre-existing draft B1 question flipped status from draft -> approved
    updated_q = db_session.query(Question).filter(Question.content_hash == "b1_draft_hash_123").first()
    assert updated_q is not None
    assert updated_q.status == "approved"

    # Verify the new standalone question was created with status approved
    new_standalone = db_session.query(Question).filter(Question.content_hash == "standalone_new_hash_789").first()
    assert new_standalone is not None
    assert new_standalone.status == "approved"
    assert new_standalone.audio_url == "/static/audio_gen/new.wav"
    assert new_standalone.image_url == "/static/img/new.png"

    # Verify TOEIC question remains draft and untouched
    unchanged_toeic = db_session.query(Question).filter(Question.content_hash == "toeic_hash_123").first()
    assert unchanged_toeic is not None
    assert unchanged_toeic.status == "draft"

    # Count total VSTEP B1 questions
    b1_q_count_before = db_session.query(Question).filter(
        Question.exam_id.is_(None),
        Question.exam_type == "VSTEP_B1"
    ).count()
    assert b1_q_count_before == initial_count + 3 # pre-existing (1) + child_qs (2) + new_standalone (1)

    # 6. Run seeder for the SECOND time (Idempotency check)
    success_2 = seed_from_json(db_session, str(temp_json))
    assert success_2 is True

    # Count total VSTEP B1 questions again
    b1_q_count_after = db_session.query(Question).filter(
        Question.exam_id.is_(None),
        Question.exam_type == "VSTEP_B1"
    ).count()
    # Should not increase
    assert b1_q_count_after == b1_q_count_before

    # Verify status is still approved and groups still map correctly
    child_qs_2 = db_session.query(Question).filter(Question.group_id == seeded_g.id).all()
    assert len(child_qs_2) == 2
    for cq in child_qs_2:
        assert cq.status == "approved"

    # TOEIC question remains draft
    unchanged_toeic_2 = db_session.query(Question).filter(Question.content_hash == "toeic_hash_123").first()
    assert unchanged_toeic_2.status == "draft"
