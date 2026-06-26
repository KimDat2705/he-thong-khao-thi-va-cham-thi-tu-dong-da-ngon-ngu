"""
Seed B1 Bank: Read portable JSON dump and import/upsert VSTEP B1 questions
and question groups into the bank idempotently.
"""
import os
import sys
import json
from sqlalchemy.orm import Session

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.core.database import SessionLocal  # noqa: E402
from app.models.question import Question  # noqa: E402
from app.models.question_group import QuestionGroup  # noqa: E402


def seed_from_json(db: Session, json_path: str):
    """Seed questions and groups from a JSON file into the database bank."""
    if not os.path.exists(json_path):
        print(f"Error: JSON file not found at {json_path}")
        return False

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    groups = data.get("groups", [])
    standalone_questions = data.get("standalone_questions", [])

    print(f"Seeding {len(groups)} groups and {len(standalone_questions)} standalone questions...")

    # 1. Seed Groups
    for g_data in groups:
        g_hash = g_data.get("content_hash")
        if not g_hash:
            print("Warning: Group missing content_hash. Skipping group.")
            continue

        # Idempotency check: find group with same content_hash inside bank (exam_id is NULL)
        existing_g = db.query(QuestionGroup).filter(
            QuestionGroup.exam_id.is_(None),
            QuestionGroup.content_hash == g_hash
        ).first()

        if existing_g:
            print(f"Group with hash {g_hash[:8]}... already exists. Ensuring status='approved'.")
            existing_g.status = "approved"
            db.commit()
            db.refresh(existing_g)
            group_id = existing_g.id
        else:
            # Create new QuestionGroup, ensure status is "approved"
            new_g = QuestionGroup(
                exam_id=None,
                part=g_data["part"],
                topic=g_data.get("topic"),
                passage_text=g_data.get("passage_text"),
                audio_url=g_data.get("audio_url"),
                image_url=g_data.get("image_url"),
                passage_type=g_data.get("passage_type"),
                speaker_count=g_data.get("speaker_count"),
                speech_rate=g_data.get("speech_rate"),
                accent=g_data.get("accent"),
                difficulty=g_data.get("difficulty"),
                status="approved",
                content_hash=g_hash
            )
            db.add(new_g)
            db.commit()
            db.refresh(new_g)
            group_id = new_g.id
            print(f"Created new Group (ID={group_id}, hash={g_hash[:8]}...).")

        # Seed child questions for this group
        for q_data in g_data.get("questions", []):
            q_hash = q_data.get("content_hash")
            if not q_hash:
                print("Warning: Question missing content_hash. Skipping.")
                continue

            existing_q = db.query(Question).filter(
                Question.exam_id.is_(None),
                Question.content_hash == q_hash
            ).first()

            if existing_q:
                print(f"  Child Question {q_hash[:8]}... already exists. Ensuring status='approved' and remapping group.")
                existing_q.status = "approved"
                existing_q.group_id = group_id
            else:
                new_q = Question(
                    exam_id=None,
                    group_id=group_id,
                    part=q_data["part"],
                    type=q_data["type"],
                    content=q_data["content"],
                    audio_url=q_data.get("audio_url"),
                    image_url=q_data.get("image_url"),
                    options=q_data.get("options"),
                    reference_answer=q_data.get("reference_answer"),
                    difficulty=q_data.get("difficulty"),
                    clo=q_data.get("clo"),
                    topic=q_data.get("topic"),
                    status="approved",
                    explanation=q_data.get("explanation"),
                    exam_type=q_data.get("exam_type", "VSTEP_B1"),
                    language=q_data.get("language", "EN"),
                    content_hash=q_hash
                )
                db.add(new_q)
                print(f"  Created new child Question (hash={q_hash[:8]}...).")
        db.commit()

    # 2. Seed Standalone Questions
    for q_data in standalone_questions:
        q_hash = q_data.get("content_hash")
        if not q_hash:
            print("Warning: Standalone question missing content_hash. Skipping.")
            continue

        existing_q = db.query(Question).filter(
            Question.exam_id.is_(None),
            Question.content_hash == q_hash
        ).first()

        if existing_q:
            print(f"Standalone Question {q_hash[:8]}... already exists. Ensuring status='approved'.")
            existing_q.status = "approved"
        else:
            new_q = Question(
                exam_id=None,
                group_id=None,
                part=q_data["part"],
                type=q_data["type"],
                content=q_data["content"],
                audio_url=q_data.get("audio_url"),
                image_url=q_data.get("image_url"),
                options=q_data.get("options"),
                reference_answer=q_data.get("reference_answer"),
                difficulty=q_data.get("difficulty"),
                clo=q_data.get("clo"),
                topic=q_data.get("topic"),
                status="approved",
                explanation=q_data.get("explanation"),
                exam_type=q_data.get("exam_type", "VSTEP_B1"),
                language=q_data.get("language", "EN"),
                content_hash=q_hash
            )
            db.add(new_q)
            print(f"Created new standalone Question (hash={q_hash[:8]}...).")
        db.commit()

    print("Seeding B1 bank completed successfully.")
    return True


def main():
    # If a custom JSON path is provided in arguments, use it; otherwise fallback to default
    if len(sys.argv) > 1:
        json_path = sys.argv[1]
    else:
        json_path = os.path.join(BACKEND_DIR, "scripts", "b1_bank_export.json")

    print(f"Running seeder with file: {json_path}")
    db = SessionLocal()
    try:
        success = seed_from_json(db, json_path)
        if not success:
            sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
