"""
Validate the VSTEP B1 question bank for quality issues BEFORE approval / export / deploy.

Bắt đúng lớp lỗi đã từng phải sửa tay (S45): audio TTS hỏng (file 19 byte / 1 giây),
asset thiếu, và câu trùng nội dung nhưng đáp án MÂU THUẪN (vd R1 "arrive ___ the
destination" có bản KEY=C sai lẫn bản KEY=A đúng).

Kiểm:
  1. audio_url trỏ /static → file tồn tại, mở được (WAV hợp lệ), đủ dài.
  2. image_url trỏ /static (kể cả multi-image phẩy) → mọi file tồn tại, không quá nhỏ.
  3. Câu cùng nội dung nhưng khác reference_answer → đáp án mâu thuẫn.
  4. (CẢNH BÁO) số câu/nhóm mỗi part so với VSTEP_B1_BLUEPRINT tối thiểu.

Critical issue (1/2/3) → exit 1. Shortfall (4) chỉ cảnh báo, exit 0.

    DATABASE_URL=sqlite:///./grading_db.db python scripts/validate_b1_bank.py
"""
import os
import sys
import wave
from collections import defaultdict

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.core.database import SessionLocal  # noqa: E402
from app.models.question import Question  # noqa: E402
from app.models.question_group import QuestionGroup  # noqa: E402
from app.services.exam_generator import VSTEP_B1_BLUEPRINT  # noqa: E402

MIN_WAV_BYTES = 100 * 1024     # file TTS thật ~MB; <100KB là nghi/hỏng
MIN_WAV_SECONDS = 3.0          # item nghe ngắn nhất vẫn > vài giây
MIN_IMG_BYTES = 10 * 1024      # ảnh AI ~hàng trăm KB; <10KB là nghi


def _static_paths(url):
    """Tách các đường dẫn /static/... (hỗ trợ multi-image phẩy) → đường tương đối từ BACKEND_DIR."""
    if not url:
        return []
    return [p.strip().lstrip("/") for p in url.split(",") if p.strip().startswith("/static/")]


def _check_audio(path):
    if not os.path.isfile(path):
        return "missing"
    if os.path.getsize(path) < MIN_WAV_BYTES:
        return f"too_small({os.path.getsize(path)}B)"
    try:
        with wave.open(path) as w:
            dur = w.getnframes() / float(w.getframerate())
            if dur < MIN_WAV_SECONDS:
                return f"too_short({dur:.1f}s)"
    except Exception as e:
        return f"invalid_wav({type(e).__name__})"
    return None


def find_b1_bank_issues(db, static_root=BACKEND_DIR):
    """Trả về list issue. static_root = thư mục chứa thư mục `static/` (mặc định BACKEND_DIR)."""
    issues = []
    questions = db.query(Question).filter(
        Question.exam_id.is_(None), Question.exam_type == "VSTEP_B1"
    ).all()
    groups = db.query(QuestionGroup).filter(QuestionGroup.exam_id.is_(None)).all()

    owners = [("question", q) for q in questions] + [("group", g) for g in groups]
    for kind, owner in owners:
        for rel in _static_paths(getattr(owner, "audio_url", None)):
            why = _check_audio(os.path.join(static_root, rel))
            if why:
                issues.append({"severity": "critical", "type": "audio",
                               "kind": kind, "id": owner.id, "path": rel, "why": why})
        for rel in _static_paths(getattr(owner, "image_url", None)):
            p = os.path.join(static_root, rel)
            if not os.path.isfile(p):
                issues.append({"severity": "critical", "type": "image",
                               "kind": kind, "id": owner.id, "path": rel, "why": "missing"})
            elif os.path.getsize(p) < MIN_IMG_BYTES:
                issues.append({"severity": "critical", "type": "image",
                               "kind": kind, "id": owner.id, "path": rel,
                               "why": f"too_small({os.path.getsize(p)}B)"})

    # Đáp án mâu thuẫn: cùng nội dung, khác reference_answer.
    # CHỈ xét câu STANDALONE (group_id IS NULL) — câu fill trong nhóm chia sẻ chung passage
    # làm `content` nhưng mỗi blank có đáp án khác nhau (hợp lệ, không phải mâu thuẫn).
    answers_by_content = defaultdict(set)
    ids_by_content = defaultdict(list)
    for q in questions:
        if q.reference_answer and q.group_id is None:
            answers_by_content[q.content].add(q.reference_answer)
            ids_by_content[q.content].append(q.id)
    for content, answers in answers_by_content.items():
        if len(answers) > 1:
            issues.append({"severity": "critical", "type": "conflicting_answer",
                           "ids": ids_by_content[content], "answers": sorted(answers),
                           "content": (content or "")[:70]})

    # Cảnh báo: thiếu so với blueprint tối thiểu
    for part_str, spec in VSTEP_B1_BLUEPRINT["parts"].items():
        part = int(part_str)
        if spec["type"] == "standalone":
            have = sum(1 for q in questions if q.part == part and q.group_id is None and q.status == "approved")
            need = spec.get("count", 0)
        else:
            have = sum(1 for g in groups if g.part == part and g.status == "approved")
            need = spec.get("groups", 0)
        if have < need:
            issues.append({"severity": "warning", "type": "part_shortfall",
                           "part": part, "have": have, "need": need})
    return issues


def main():
    db = SessionLocal()
    try:
        issues = find_b1_bank_issues(db)
    finally:
        db.close()

    critical = [i for i in issues if i["severity"] == "critical"]
    warnings = [i for i in issues if i["severity"] == "warning"]

    if not issues:
        print("✓ Bank B1 SẠCH — không có vấn đề chất lượng.")
        return

    if critical:
        print(f"✗ {len(critical)} CRITICAL issue:")
        for i in critical:
            if i["type"] == "conflicting_answer":
                print(f"  - [đáp án mâu thuẫn] ids={i['ids']} answers={i['answers']} | {i['content']}")
            else:
                print(f"  - [{i['type']}] {i['kind']} #{i['id']} {i['path']} → {i['why']}")
    if warnings:
        print(f"⚠ {len(warnings)} cảnh báo:")
        for i in warnings:
            print(f"  - [thiếu blueprint] part {i['part']}: có {i['have']} / cần {i['need']}")

    sys.exit(1 if critical else 0)


if __name__ == "__main__":
    main()
