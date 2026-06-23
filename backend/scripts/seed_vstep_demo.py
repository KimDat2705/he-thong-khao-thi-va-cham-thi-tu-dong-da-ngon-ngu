"""
Seed a small VSTEP (English B1) demo exam — a SECOND exam type alongside TOEIC —
to demonstrate the system handling a different exam format end-to-end, with MIXED
grading: a Reading section (multiple-choice, auto-graded) plus a Writing task
(free-text, AI-graded via the GRADE-003 Celery/Gemini path).

The questions are attached directly to the exam (exam_id set) rather than to the
shared question bank (exam_id IS NULL), so they do NOT collide with the TOEIC bank
(the bank has no language/exam_type discriminator — see notes in claude-progress).

Submitting this exam routes through the asynchronous AI grading path because it
contains a writing question; the worker grades the multiple-choice answers
(score_multiple_choice) and the essay (score_writing) together.

Idempotent: re-running does not duplicate the exam (matched by title).

Run (from backend/):
    DATABASE_URL="sqlite:///./demo_toeic.db" CELERY_TASK_ALWAYS_EAGER=true \
        python scripts/seed_vstep_demo.py
"""
import os
import sys

os.environ.setdefault("DATABASE_URL", "sqlite:///./demo_toeic.db")

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.core.database import Base, engine, SessionLocal  # noqa: E402
from app.models.exam import Exam  # noqa: E402
from app.models.question import Question  # noqa: E402

EXAM_TITLE = "VSTEP B1 Demo (Reading + Writing, AI-graded)"

# Reading section (Part 1): short B1-level multiple-choice items.
READING_QUESTIONS = [
    {
        "content": "Choose the correct option:\n\"If it ____ tomorrow, we will cancel the picnic.\"",
        "options": {"A": "rains", "B": "rained", "C": "will rain", "D": "is raining"},
        "answer": "A",
    },
    {
        "content": "Read: \"The library closes at 8 p.m. on weekdays and 5 p.m. on weekends.\"\nWhen does the library close on Saturday?",
        "options": {"A": "8 p.m.", "B": "5 p.m.", "C": "It does not close", "D": "6 p.m."},
        "answer": "B",
    },
    {
        "content": "Choose the word closest in meaning to \"purchase\".",
        "options": {"A": "sell", "B": "return", "C": "buy", "D": "borrow"},
        "answer": "C",
    },
    {
        "content": "Choose the correct option:\n\"She has worked here ____ 2019.\"",
        "options": {"A": "since", "B": "for", "C": "during", "D": "from"},
        "answer": "A",
    },
]

# Writing section (Part 2): a free-text task graded by AI.
WRITING_PROMPT = (
    "Task — Write a paragraph of about 150 words about the advantages and "
    "disadvantages of working from home. Give at least two reasons and an example."
)

# Speaking section (Part 3): a spoken task graded by AI (audio upload/recording).
SPEAKING_PROMPT = (
    "Speaking — Talk for about 1 minute about a place you would like to visit. "
    "Say where it is, why you want to go there, and what you would do."
)


def seed_vstep_exam(db) -> Exam:
    existing = db.query(Exam).filter(Exam.title == EXAM_TITLE).first()
    if existing:
        print(f"VSTEP demo exam already exists (id={existing.id}).")
        return existing

    exam = Exam(
        title=EXAM_TITLE,
        language="EN",
        exam_type="VSTEP",
        duration_minutes=90,
        is_active=True,
    )
    db.add(exam)
    db.commit()
    db.refresh(exam)

    # Part 1 — Reading (multiple choice, auto-graded)
    for item in READING_QUESTIONS:
        db.add(Question(
            exam_id=exam.id,
            part=1,
            type="choice",
            content=item["content"],
            options=item["options"],
            reference_answer=item["answer"],
            status="approved",
            difficulty="medium",
            topic="Reading",
        ))

    # Part 2 — Writing (free-text, AI-graded)
    db.add(Question(
        exam_id=exam.id,
        part=2,
        type="writing",
        content=WRITING_PROMPT,
        reference_answer=None,
        status="approved",
        difficulty="medium",
        topic="Writing",
    ))

    # Part 3 — Speaking (audio, AI-graded)
    db.add(Question(
        exam_id=exam.id,
        part=3,
        type="speaking",
        content=SPEAKING_PROMPT,
        reference_answer=None,
        status="approved",
        difficulty="medium",
        topic="Speaking",
    ))
    db.commit()
    print(f"Seeded VSTEP demo exam id={exam.id}: "
          f"{len(READING_QUESTIONS)} reading MCQ + 1 writing + 1 speaking task.")
    return exam


def main() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_vstep_exam(db)
    finally:
        db.close()


if __name__ == "__main__":
    main()
