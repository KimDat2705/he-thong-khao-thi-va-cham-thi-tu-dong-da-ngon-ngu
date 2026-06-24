"""
Seed a FULL VSTEP B1 (English) demo exam — a second exam type alongside TOEIC —
covering all four skills end-to-end: LISTENING + READING (multiple-choice,
auto-graded) plus WRITING (2 tasks) and SPEAKING (3 parts) which are AI-graded via
the GRADE-003 Celery/Gemini path.

The questions/groups are attached directly to the exam (exam_id set) rather than to
the shared question bank (exam_id IS NULL), so they do NOT collide with the TOEIC
bank (the bank has no language/exam_type discriminator — see notes in
claude-progress / memory bank-thieu-cot-exam-type).

Listening note: this demo has no audio file, so the Listening section shows the
audio *script* as the group passage (clearly labelled). When a real recording is
available it attaches at the group's audio_url via the parser pipeline (TOEIC-style)
and the script can be hidden — no structural change needed.

Submitting this exam routes through the asynchronous AI grading path (it contains
writing/speaking questions); the worker grades the multiple-choice answers
(score_multiple_choice) and the essays/speech (score_writing/score_speaking).

Idempotent: re-running does not duplicate the exam (matched by title). The older
thin "VSTEP B1 Demo (Reading + Writing...)" exam, if present, is left untouched —
retire it from the admin UI if you no longer want it.

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
from app.models.question_group import QuestionGroup  # noqa: E402

EXAM_TITLE = "VSTEP B1 — Đề mẫu đầy đủ (Nghe · Đọc · Viết · Nói)"

# ── Part 1 — LISTENING (transcript-based for the demo; real audio attaches later) ──
LISTENING_TRANSCRIPT = (
    "🎧 Phần NGHE — bản ghi nội dung (bản demo chưa gắn file audio; khi có file, "
    "đoạn này sẽ được thay bằng trình phát audio).\n\n"
    "Woman: Excuse me, does this bus go to the city centre?\n"
    "Man: Yes, but you need bus number 12, not number 21. Number 12 stops right in "
    "front of the museum.\n"
    "Woman: Great. How often does it come?\n"
    "Man: Every fifteen minutes on weekdays, but only every half an hour at the weekend.\n"
    "Woman: And how much is the ticket?\n"
    "Man: It's two dollars if you pay the driver, but only one fifty if you buy a "
    "card from that machine over there."
)
LISTENING_QUESTIONS = [
    {
        "content": "Which bus should the woman take?",
        "options": {"A": "Number 12", "B": "Number 21", "C": "Number 15", "D": "Number 30"},
        "answer": "A",
    },
    {
        "content": "How often does the bus come at the weekend?",
        "options": {"A": "Every 15 minutes", "B": "Every 30 minutes", "C": "Every hour", "D": "Twice a day"},
        "answer": "B",
    },
    {
        "content": "How much is the ticket if she buys a card from the machine?",
        "options": {"A": "$2.00", "B": "$1.50", "C": "$1.20", "D": "It is free"},
        "answer": "B",
    },
]

# ── Part 2 — READING: a short passage + comprehension, plus language-use items ──
READING_PASSAGE = (
    "Greenfield Community Garden — Notice\n\n"
    "The Greenfield Community Garden is open to all residents from 7 a.m. to 7 p.m. "
    "every day. Members pay a small yearly fee of $20, which covers water and basic "
    "tools. New members must attend a short training session before they start. "
    "Children under 12 are welcome but must be with an adult at all times. The garden "
    "also holds a free market every Sunday morning, where members can sell the "
    "vegetables they grow."
)
READING_PASSAGE_QUESTIONS = [
    {
        "content": "What time does the garden close?",
        "options": {"A": "7 a.m.", "B": "12 p.m.", "C": "7 p.m.", "D": "It never closes"},
        "answer": "C",
    },
    {
        "content": "What does the yearly fee cover?",
        "options": {"A": "Water and basic tools", "B": "Seeds and plants", "C": "Training only", "D": "Nothing"},
        "answer": "A",
    },
    {
        "content": "What must new members do before they start?",
        "options": {"A": "Pay an extra $50", "B": "Attend a training session", "C": "Bring their own water", "D": "Sell vegetables first"},
        "answer": "B",
    },
    {
        "content": "When is the free market held?",
        "options": {"A": "Every day", "B": "Saturday evening", "C": "Sunday morning", "D": "Once a year"},
        "answer": "C",
    },
]
READING_LANGUAGE_QUESTIONS = [
    {
        "content": "Choose the correct option:\n\"I'm really interested ____ learning Japanese.\"",
        "options": {"A": "in", "B": "on", "C": "at", "D": "for"},
        "answer": "A",
    },
    {
        "content": "Choose the word closest in meaning to \"enormous\".",
        "options": {"A": "tiny", "B": "huge", "C": "empty", "D": "quiet"},
        "answer": "B",
    },
]

# ── Part 3 — WRITING (2 tasks, AI-graded) ──
WRITING_TASK_1 = (
    "Writing — Task 1 (viết khoảng 120 từ). You recently bought a product online "
    "but it arrived damaged. Write an email to the shop. In your email:\n"
    "• describe the problem;\n"
    "• say when and how you bought it;\n"
    "• ask what the shop will do to solve it."
)
WRITING_TASK_2 = (
    "Writing — Task 2 (viết khoảng 250 từ). Some people think students should study "
    "online, while others prefer traditional classrooms. Discuss both views and give "
    "your own opinion. Give reasons and relevant examples to support your answer."
)

# ── Part 4 — SPEAKING (3 parts, AI-graded via audio upload/recording) ──
SPEAKING_PART_1 = (
    "Speaking — Part 1 (Social interaction). Answer these questions: Where do you "
    "live, and what do you like about it? What do you usually do in your free time?"
)
SPEAKING_PART_2 = (
    "Speaking — Part 2 (Solution discussion). Your friend wants to improve their "
    "English. Suggest some solutions (for example: watching films, joining a club, "
    "using apps) and recommend the best one, giving reasons."
)
SPEAKING_PART_3 = (
    "Speaking — Part 3 (Topic development). Talk for about two minutes about the "
    "benefits of learning a foreign language. Develop ideas such as travel, work "
    "opportunities, and understanding other cultures."
)


def _add_choice(db, exam_id, part, item, topic, group_id=None):
    db.add(Question(
        exam_id=exam_id,
        group_id=group_id,
        part=part,
        type="choice",
        content=item["content"],
        options=item["options"],
        reference_answer=item["answer"],
        status="approved",
        difficulty="medium",
        topic=topic,
    ))


def seed_vstep_exam(db) -> Exam:
    existing = db.query(Exam).filter(Exam.title == EXAM_TITLE).first()
    if existing:
        print(f"VSTEP B1 full demo exam already exists (id={existing.id}).")
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

    # Part 1 — Listening (one passage group: shared transcript + comprehension MCQ)
    listen_group = QuestionGroup(
        exam_id=exam.id, part=1, topic="Listening",
        passage_text=LISTENING_TRANSCRIPT, passage_type="conversation",
        speaker_count=2, status="approved", difficulty="medium",
    )
    db.add(listen_group)
    db.commit()
    db.refresh(listen_group)
    for item in LISTENING_QUESTIONS:
        _add_choice(db, exam.id, 1, item, "Listening", group_id=listen_group.id)

    # Part 2 — Reading (one passage group + standalone language-use items)
    read_group = QuestionGroup(
        exam_id=exam.id, part=2, topic="Reading",
        passage_text=READING_PASSAGE, passage_type="notice",
        status="approved", difficulty="medium",
    )
    db.add(read_group)
    db.commit()
    db.refresh(read_group)
    for item in READING_PASSAGE_QUESTIONS:
        _add_choice(db, exam.id, 2, item, "Reading", group_id=read_group.id)
    for item in READING_LANGUAGE_QUESTIONS:
        _add_choice(db, exam.id, 2, item, "Reading")

    # Part 3 — Writing (2 free-text tasks, AI-graded)
    for prompt in (WRITING_TASK_1, WRITING_TASK_2):
        db.add(Question(
            exam_id=exam.id, part=3, type="writing", content=prompt,
            reference_answer=None, status="approved", difficulty="medium", topic="Writing",
        ))

    # Part 4 — Speaking (3 spoken tasks, AI-graded)
    for prompt in (SPEAKING_PART_1, SPEAKING_PART_2, SPEAKING_PART_3):
        db.add(Question(
            exam_id=exam.id, part=4, type="speaking", content=prompt,
            reference_answer=None, status="approved", difficulty="medium", topic="Speaking",
        ))

    db.commit()
    n_reading = len(READING_PASSAGE_QUESTIONS) + len(READING_LANGUAGE_QUESTIONS)
    n_choice = len(LISTENING_QUESTIONS) + n_reading
    print(
        f"Seeded FULL VSTEP B1 exam id={exam.id}: "
        f"Listening {len(LISTENING_QUESTIONS)} + Reading {n_reading} "
        f"(= {n_choice} MCQ) + Writing 2 + Speaking 3."
    )
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
