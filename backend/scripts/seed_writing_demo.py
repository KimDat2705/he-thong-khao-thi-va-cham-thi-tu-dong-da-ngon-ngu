"""
Seed a small Writing exam so the AI essay-grading path (SPEC-GRADE-003) is
demoable end-to-end in the browser: a candidate opens the exam, types an essay,
submits, and sees the AI score + feedback once grading completes.

This is a free-text (Writing) exam — NOT generated from the TOEIC bank. We insert
the Exam + a couple of writing Questions directly. Submitting it routes through the
asynchronous Celery/Gemini grading path (works without Redis when
CELERY_TASK_ALWAYS_EAGER=true; see app/core/celery.py).

Idempotent: re-running does not create a duplicate exam (matched by title).

Run (from backend/):
    DATABASE_URL="sqlite:///./demo_toeic.db" CELERY_TASK_ALWAYS_EAGER=true \
        python scripts/seed_writing_demo.py
"""
import os
import sys

# Default the demo DB to the same local SQLite file as the TOEIC demo seed
# BEFORE importing app modules (env var wins over backend/.env).
os.environ.setdefault("DATABASE_URL", "sqlite:///./demo_toeic.db")

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.core.database import Base, engine, SessionLocal  # noqa: E402
from app.models.exam import Exam  # noqa: E402
from app.models.question import Question  # noqa: E402

EXAM_TITLE = "VSTEP Writing Demo (AI-graded)"

# Two short writing prompts (VSTEP B1-style). reference_answer is left None — the
# AI grades against the prompt requirements, not an exact key.
WRITING_PROMPTS = [
    "Task 1 — Write an email of about 120 words to a friend describing a recent "
    "trip you took. Mention where you went, what you did, and how you felt.",
    "Task 2 — Some people think students should learn online; others prefer "
    "traditional classrooms. Write about 250 words giving your opinion with reasons "
    "and examples.",
]


def seed_writing_exam(db) -> Exam:
    existing = db.query(Exam).filter(Exam.title == EXAM_TITLE).first()
    if existing:
        print(f"Writing demo exam already exists (id={existing.id}).")
        return existing

    exam = Exam(
        title=EXAM_TITLE,
        language="EN",
        exam_type="VSTEP",
        duration_minutes=60,
        is_active=True,
    )
    db.add(exam)
    db.commit()
    db.refresh(exam)

    for idx, prompt in enumerate(WRITING_PROMPTS, start=1):
        db.add(Question(
            exam_id=exam.id,
            part=idx,
            type="writing",
            content=prompt,
            reference_answer=None,
            status="approved",
            difficulty="medium",
            topic="Writing",
        ))
    db.commit()
    print(f"Seeded Writing demo exam id={exam.id} with {len(WRITING_PROMPTS)} prompts.")
    return exam


def main() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_writing_exam(db)
    finally:
        db.close()


if __name__ == "__main__":
    main()
