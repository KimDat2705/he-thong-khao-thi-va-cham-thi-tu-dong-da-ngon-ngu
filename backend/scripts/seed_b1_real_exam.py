"""
Seed the real VSTEP B1 exam (Đề 2601) with all four skills into the database.
Attached directly to the exam (exam_id set) rather than to the shared question bank (exam_id IS NULL).
Idempotent: safe update/skip if there are submissions referencing this exam.

Run (from backend/):
    DATABASE_URL="sqlite:///./demo_toeic.db" python scripts/seed_b1_real_exam.py
"""
import os
import sys
import shutil
import re

os.environ.setdefault("DATABASE_URL", "sqlite:///./demo_toeic.db")

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.core.database import Base, engine, SessionLocal
from app.models.exam import Exam
from app.models.question import Question
from app.models.question_group import QuestionGroup
from app.services.parser import (
    convert_doc_to_docx,
    parse_b1_reading_docx,
    parse_b1_answer_key,
    parse_b1_listening_docx,
    parse_b1_listening_key,
    parse_b1_speaking_card,
)

EXAM_TITLE = "VSTEP B1 — Đề 2601 (đề thật)"
STATIC_IMG_DIR = os.path.join(BACKEND_DIR, "static", "img")


def extract_and_save_b1_images(doc, img_indices, out_dir, set_id, q_num):
    """
    Extracts inline shapes at indices specified in img_indices and saves them.
    Returns a comma-separated list of relative URLs.
    """
    import os
    os.makedirs(os.path.join(out_dir, set_id), exist_ok=True)
    
    option_letters = ["A", "B", "C"]
    urls = []
    
    for i, idx in enumerate(img_indices):
        if i >= len(option_letters):
            break
        letter = option_letters[i]
        try:
            if idx >= len(doc.inline_shapes):
                print(f"[REPORT] Image index {idx} out of range for Q{q_num} (total shapes: {len(doc.inline_shapes)})")
                continue
            inline_shape = doc.inline_shapes[idx]
            rId = inline_shape._inline.xpath('.//a:blip/@r:embed') or inline_shape._inline.xpath('.//a:blip/@r:link')
            if rId:
                image_part = doc.part.related_parts[rId[0]]
                image_bytes = image_part.blob
                
                from app.services.docx_images import _ext_for
                try:
                    ext = _ext_for(image_part)
                except Exception:
                    ext = ".png"
                
                filename = f"q{q_num}_{letter}{ext}"
                rel_path = os.path.join(set_id, filename)
                full_path = os.path.join(out_dir, rel_path)
                
                with open(full_path, "wb") as f:
                    f.write(image_bytes)
                
                urls.append(f"/static/img/{set_id}/{filename}".replace("\\", "/"))
        except Exception as e:
            print(f"[REPORT] Error extracting image index {idx} for Q{q_num}: {e}")
            
    return ",".join(urls) if urls else None


def seed_b1_exam(db) -> Exam:
    # 1. Idempotency Check
    existing = db.query(Exam).filter(Exam.title == EXAM_TITLE).first()
    if existing:
        from app.models.submission import Submission
        has_sub = db.query(Submission).filter(Submission.exam_id == existing.id).first() is not None
        if has_sub:
            print(f"Exam '{EXAM_TITLE}' already exists and has submissions (id={existing.id}). Skipping recreation to preserve data.")
            return existing
        else:
            print(f"Deleting existing exam '{EXAM_TITLE}' without submissions...")
            db.delete(existing)
            db.commit()

    # 2. File Paths
    b1_dir = os.environ.get("B1_INPUT_DIR", r"D:\Dat-Antigravity\drive_input\B1_2601")
    audio_dir = os.environ.get("AUDIO_DIR", r"D:\Dat-Antigravity\drive_input\audio")
    
    reading_docx = os.path.join(b1_dir, "1. ĐỌC + VIẾT (đề) — EB1-2601.docx")
    reading_key_docx = os.path.join(b1_dir, "5. ĐÁP ÁN Đọc-Viết (phiếu chấm) — B1 2601.docx")
    listening_docx = os.path.join(b1_dir, "2. NGHE (đề) — LB1-2601.docx")
    listening_key_doc = os.path.join(b1_dir, "6. ĐÁP ÁN Nghe — B1 2601.doc")
    speaking_doc = os.path.join(b1_dir, "4. NÓI (Speaking card, gồm đề 2601-2610).doc")

    # 3. Conversions
    print("Converting legacy .doc files to .docx...")
    listening_key_docx = convert_doc_to_docx(listening_key_doc)
    speaking_docx = convert_doc_to_docx(speaking_doc)

    # 4. Parsing
    print("Parsing exam files...")
    reading_data = parse_b1_reading_docx(reading_docx)
    reading_key = parse_b1_answer_key(reading_key_docx)
    
    listening_data = parse_b1_listening_docx(listening_docx)
    listening_key = parse_b1_listening_key(listening_key_docx)
    
    speaking_items = parse_b1_speaking_card(speaking_docx, "LB12601")

    # 5. Create Exam
    exam = Exam(
        title=EXAM_TITLE,
        language="EN",
        exam_type="VSTEP_B1",
        duration_minutes=135,
        is_active=True,
    )
    db.add(exam)
    db.commit()
    db.refresh(exam)
    print(f"Created Exam id={exam.id}")

    # 6. Copy Audio
    src_audio = os.path.join(b1_dir, "3. NGHE (audio) — LB1-2601.mp3")
    audio_filename = "3. NGHE (audio) — LB1-2601.mp3"
    if os.path.exists(src_audio) and os.path.exists(audio_dir):
        dest_audio = os.path.join(audio_dir, audio_filename)
        try:
            shutil.copy2(src_audio, dest_audio)
            print(f"Copied audio file to {dest_audio}")
        except Exception as e:
            print(f"Warning: Could not copy audio: {e}")

    # 7. Seed Reading & Writing Questions
    print("Seeding Reading & Writing questions...")
    for item in reading_data["items"]:
        q_num = item["number"]
        ref_ans = reading_key.get(q_num)
        
        q = Question(
            exam_id=exam.id,
            part=item["part"],  # parts 1-4 for Reading, 5-6 for Writing
            type=item["type"],  # choice, fill, writing
            content=item["content"],
            options=item["options"],
            reference_answer=ref_ans,
            difficulty="medium",
            status="approved",
            exam_type="VSTEP_B1",
            language="EN"
        )
        db.add(q)

    # 8. Seed Listening Questions
    print("Seeding Listening questions...")
    import docx
    list_doc = docx.Document(listening_docx)
    
    for item in listening_data["items"]:
        q_num = item["number"]
        ref_ans = listening_key.get(q_num)
        
        # Map parts: MCQ -> 7, Fill -> 8
        part = 7 if item["part"] == 1 else 8
        
        # Extract images best-effort
        img_url = None
        img_indices_str = item.get("image_url")
        if img_indices_str:
            try:
                img_indices = [int(x) for x in img_indices_str.split(",") if x.strip()]
                img_url = extract_and_save_b1_images(list_doc, img_indices, STATIC_IMG_DIR, "LB12601", q_num)
            except Exception as e:
                print(f"[REPORT] Failed to extract images for Q{q_num}: {e}")
        
        q = Question(
            exam_id=exam.id,
            part=part,
            type=item["type"],
            content=item["content"],
            options=item["options"],
            reference_answer=ref_ans,
            audio_url=f"/audio/{audio_filename}",
            image_url=img_url,
            difficulty="medium",
            status="approved",
            exam_type="VSTEP_B1",
            language="EN"
        )
        db.add(q)

    # 9. Seed Speaking Questions
    print("Seeding Speaking questions...")
    for idx, item in enumerate(speaking_items):
        part = idx + 9  # parts 9, 10, 11
        q = Question(
            exam_id=exam.id,
            part=part,
            type="speaking",
            content=item["content"],
            options={},
            reference_answer=None,
            difficulty="medium",
            status="approved",
            exam_type="VSTEP_B1",
            language="EN"
        )
        db.add(q)

    db.commit()
    print(f"Successfully seeded exam '{EXAM_TITLE}' (id={exam.id}) with Reading/Writing/Listening/Speaking.")
    return exam


def main() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_b1_exam(db)
    finally:
        db.close()


if __name__ == "__main__":
    main()
