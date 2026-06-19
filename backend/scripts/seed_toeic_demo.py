"""
Seed an approved TOEIC question bank from REAL partner data for the demo.

Pipeline:
  1. Import a real Listening set (LT2601) + Reading set (RT2605) via import_exam_set
     (parses .docx, merges .xlsx answer keys, links audio if present) -> bank as 'draft'.
  2. Backfill per-part difficulty + topic so the generator's blueprint constraints are
     satisfiable. The real parser stamps every item difficulty='medium', topic=None;
     the generator REQUIRES topic diversity (all-None -> one topic = 100% -> fails), and
     benefits from a proper difficulty matrix. We assign distinct topics per group and
     a difficulty distribution matching TOEIC_BLUEPRINT per part.
  3. Approve everything (draft -> approved) so generate_toeic_exam can use it.
  4. (optional) Generate one demo exam to verify end-to-end.

Idempotent: import dedups via content_hash; backfill/approve re-apply safely.

Run (from backend/):
    DATABASE_URL="sqlite:///./demo_toeic.db" python scripts/seed_toeic_demo.py
Environment overrides:
    DRIVE_INPUT   base folder of partner data (default D:\\Dat-Antigravity\\drive_input)
    AUDIO_DIR     folder with consolidated .mp3 files (optional)
"""
import os
import re
import sys

# Default the demo DB to a local SQLite file BEFORE importing app modules
# (env var takes priority over backend/.env, keeping the demo self-contained).
os.environ.setdefault("DATABASE_URL", "sqlite:///./demo_toeic.db")

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.core.database import Base, engine, SessionLocal  # noqa: E402
from app.models.question import Question  # noqa: E402
from app.models.question_group import QuestionGroup  # noqa: E402
from app.services.parser import import_exam_set  # noqa: E402
from app.services.toeic_generator import TOEIC_BLUEPRINT, generate_toeic_exam  # noqa: E402
from app.services.docx_images import extract_question_images  # noqa: E402

STATIC_IMG_DIR = os.path.join(BACKEND_DIR, "static", "img")

DRIVE_INPUT = os.environ.get("DRIVE_INPUT", r"D:\Dat-Antigravity\drive_input")
AUDIO_DIR = os.environ.get("AUDIO_DIR")  # optional

# File paths default to the local Drive layout but can be overridden via env
# (used by scripts/cloud_bootstrap.py which downloads files to flat paths).
SETS = [
    {
        "exam_type": "listening",
        "docx": os.environ.get("LT_DOCX", os.path.join(DRIVE_INPUT, "LT", "LT2601.docx")),
        "key": os.environ.get("LT_KEY", os.path.join(DRIVE_INPUT, "KEY_LT", "Key LT2601.xlsx")),
    },
    {
        "exam_type": "reading",
        "docx": os.environ.get("RT_DOCX", os.path.join(DRIVE_INPUT, "RT", "ĐỀ ĐỌC", "CDR TOEIC - RT2605.docx")),
        "key": os.environ.get("RT_KEY", os.path.join(DRIVE_INPUT, "RT", "KEY", "KEY RT.2605.xlsx")),
    },
]

# Realistic TOEIC-ish topics; assigned distinct-per-group within each part so the
# topic-diversity cap is comfortably satisfied.
TOPIC_POOL = [
    "Business", "Travel", "Dining", "Office", "Finance", "Health", "Technology",
    "Marketing", "Human Resources", "Education", "Shopping", "Transport",
    "Entertainment", "Environment", "Real Estate", "Manufacturing",
    "Customer Service", "Legal", "Media", "Logistics",
]


def _difficulty_sequence(diff_spec: dict, total: int) -> list:
    """Build a list of length `total` of difficulty labels matching the blueprint matrix."""
    seq = []
    for label in ("easy", "medium", "hard"):
        seq.extend([label] * diff_spec.get(label, 0))
    # Pad/trim to total (real counts match blueprint, but be defensive).
    if len(seq) < total:
        seq.extend(["medium"] * (total - len(seq)))
    return seq[:total]


def backfill_metadata(db) -> None:
    """Assign per-part difficulty + distinct topics to bank items so generation works."""
    parts_cfg = TOEIC_BLUEPRINT.get("parts", {})
    for part_str, spec in parts_cfg.items():
        part = int(part_str)
        diff_spec = spec.get("difficulty", {})
        ptype = spec.get("type")

        if ptype == "standalone":
            qs = (
                db.query(Question)
                .filter(Question.exam_id.is_(None), Question.group_id.is_(None), Question.part == part)
                .order_by(Question.id)
                .all()
            )
            seq = _difficulty_sequence(diff_spec, len(qs))
            for q, diff in zip(qs, seq):
                q.difficulty = diff
                q.topic = q.topic or "General"
        else:  # grouped / subset_sum
            groups = (
                db.query(QuestionGroup)
                .filter(QuestionGroup.exam_id.is_(None), QuestionGroup.part == part)
                .order_by(QuestionGroup.id)
                .all()
            )
            # subset_sum (P7) ignores difficulty; grouped uses the group difficulty matrix.
            gdiff = _difficulty_sequence(diff_spec, len(groups)) if ptype == "grouped" else ["medium"] * len(groups)
            for idx, g in enumerate(groups):
                g.topic = TOPIC_POOL[idx % len(TOPIC_POOL)]
                if idx < len(gdiff):
                    g.difficulty = gdiff[idx]
                for q in g.questions:
                    q.topic = g.topic
                    q.difficulty = g.difficulty
    db.commit()


def link_part1_images(db, docx_path: str, set_id: str) -> int:
    """
    Extract Part 1 photos from the Listening .docx and link them to the bank's
    Part 1 questions (in order). Returns count linked.
    NOTE: assumes a single Listening set in the bank (demo). Question has no set_id
    column, so Part 1 questions are matched by part + id order.
    """
    img_map = extract_question_images(docx_path, STATIC_IMG_DIR, set_id)
    p1 = (
        db.query(Question)
        .filter(Question.exam_id.is_(None), Question.part == 1)
        .order_by(Question.id)
        .all()
    )
    linked = 0
    for idx, q in enumerate(p1):
        qnum = idx + 1  # Part 1 questions are Q1..Q6 in document order
        rel = img_map.get(qnum)
        if rel:
            q.image_url = f"/static/img/{rel}"
            linked += 1
    db.commit()
    return linked


def approve_all(db) -> int:
    """Approve every bank question and group (draft -> approved)."""
    nq = (
        db.query(Question)
        .filter(Question.exam_id.is_(None), Question.status != "approved")
        .update({"status": "approved"}, synchronize_session=False)
    )
    db.query(QuestionGroup).filter(
        QuestionGroup.exam_id.is_(None), QuestionGroup.status != "approved"
    ).update({"status": "approved"}, synchronize_session=False)
    db.commit()
    return nq


def seed_admin_user(db) -> None:
    """Seed the admin user for testing and local management.
    WARNING: For local development only. When merging to production/main (Gate-2),
    make sure to set a strong ADMIN_PASSWORD in environment variables (e.g. Render settings)
    and NEVER commit real secrets to .env or the codebase.
    """
    from app.models.user import User
    from app.core.security import hash_password
    import os

    admin_username = os.environ.get("ADMIN_USERNAME", "admin")
    admin_password = os.environ.get("ADMIN_PASSWORD", "adminpassword")

    existing = db.query(User).filter(User.username == admin_username).first()
    if not existing:
        admin_user = User(
            username=admin_username,
            hashed_password=hash_password(admin_password),
            full_name="Admin Demo",
            role="admin",
            is_active=True
        )
        db.add(admin_user)
        db.commit()
        print(f"Seeded admin user '{admin_username}' successfully.")
    else:
        print(f"Admin user '{admin_username}' already exists in database.")


def main() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        for s in SETS:
            if not os.path.isfile(s["docx"]) or not os.path.isfile(s["key"]):
                print(f"!! SKIP {s['exam_type']}: missing file\n   docx={s['docx']}\n   key={s['key']}")
                continue
            audio_dir = AUDIO_DIR if (s["exam_type"] == "listening" and AUDIO_DIR) else None
            res = import_exam_set(db, s["docx"], s["key"], s["exam_type"], audio_dir=audio_dir)
            print(f"OK import {s['exam_type']}: imported_q={res.get('imported_questions')} "
                  f"imported_g={res.get('imported_groups')} skipped_q={res.get('skipped_questions')} "
                  f"audio={res.get('audio_linked')}")

        # Link Part 1 photos (extracted from the Listening .docx) to bank questions.
        for s in SETS:
            if s["exam_type"] == "listening" and os.path.isfile(s["docx"]):
                m = re.search(r"(?i)(LT|RT)\.?\s*(\d+)", os.path.basename(s["docx"]))
                set_id = f"{m.group(1).upper()}{m.group(2)}" if m else "LT"
                n_img = link_part1_images(db, s["docx"], set_id)
                print(f"Linked {n_img} Part 1 images for {set_id}.")

        print("Backfilling difficulty/topic ...")
        backfill_metadata(db)
        n = approve_all(db)
        print(f"Approved {n} questions (and their groups).")
        seed_admin_user(db)

        # Bank summary
        for part in range(1, 8):
            qc = db.query(Question).filter(
                Question.exam_id.is_(None), Question.part == part, Question.status == "approved"
            ).count()
            gc = db.query(QuestionGroup).filter(
                QuestionGroup.exam_id.is_(None), QuestionGroup.part == part, QuestionGroup.status == "approved"
            ).count()
            print(f"  Part {part}: {qc} questions, {gc} groups (approved)")

        # End-to-end check: generate one demo exam.
        try:
            exam = generate_toeic_exam(db, title="TOEIC Demo Exam (seed)", seed=42)
            total = db.query(Question).filter(Question.exam_id == exam.id).count()
            print(f"Generated demo exam id={exam.id} with {total} questions.")
        except Exception as e:
            print(f"!! Generation check failed: {type(e).__name__}: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
