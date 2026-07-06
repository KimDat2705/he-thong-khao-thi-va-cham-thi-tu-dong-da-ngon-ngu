"""Chuyển kết quả nhà máy sinh câu (boss_factory) → hàng ngân hàng.

Đầu ra khớp shape mà ``parser.save_parsed_items`` mong đợi (câu đơn lẻ + nhóm passage),
để tái dùng nguyên cơ chế lưu-nháp + chống-trùng (content_hash) + tạo QuestionGroup có sẵn.

Phạm vi hiện tại: ĐỌC R1–R4 (map sạch vào Question/QuestionGroup + có cổng kiểm đáp án AI).
Viết/Nói/Nghe = slice sau (Đạt duyệt riêng vì Nghe kéo theo audio nặng).

Cờ cổng kiểm đáp án (⚠ NGHI / ✅ PASS) được nhét vào ``explanation`` để giáo viên thấy NGAY trong
ngân hàng — KHÔNG thêm cột DB mới (không cần migration).
"""
import hashlib
import re
from typing import Optional

from app.services import boss_factory

_DIFF_EN_OK = {"easy", "medium", "hard"}


def _diff(item: dict) -> str:
    """Độ khó tiếng Anh chuẩn hoá cho cột difficulty (easy|medium|hard)."""
    d = str(item.get("difficulty_en") or "medium").lower()
    return d if d in _DIFF_EN_OK else "medium"


def _verify_prefix(item: dict) -> str:
    """Dòng ghi chú cổng kiểm đáp án AI để chèn đầu ``explanation`` (GV thấy trong ngân hàng)."""
    cell = boss_factory.verify_cell(item)      # "" | PASS | ⚠ NGHI | CHƯA KIỂM
    if not cell:
        return ""
    note = str((item.get("answer_verify") or {}).get("note") or "").strip()
    if cell == "PASS":
        tag = "✅ Cổng kiểm đáp án AI: PASS (AI giải độc lập KHỚP đáp án)"
    elif cell.startswith("⚠"):
        tag = "⚠ CỔNG KIỂM ĐÁP ÁN AI: NGHI — giáo viên soát kỹ đáp án"
    else:
        tag = f"Cổng kiểm đáp án AI: {cell}"
    return f"[{tag}]" + (f" {note}" if note else "")


def _explanation(item: dict) -> Optional[str]:
    """Gộp ghi chú cổng kiểm + giải thích gốc của nhà máy thành explanation cho câu."""
    prefix = _verify_prefix(item)
    base = str(item.get("explanation") or "").strip()
    if prefix and base:
        return f"{prefix}\n{base}"
    return prefix or base or None


def _r1_rows(items: list) -> list:
    """R1 (Đọc phần 1, 4 phương án) → câu đơn lẻ part 1, type choice."""
    rows = []
    for it in items:
        s = it.get("s1_item") or {}
        content = str(s.get("stem") or "").strip()
        if not content:
            continue
        opts = s.get("options")
        rows.append({
            "part": 1, "type": "choice", "content": content,
            "audio_url": None, "image_url": None,
            # Ép str giá trị phương án (Gemini đôi khi trả list/số) — nhất quán R2/R3/R4, tránh lưu méo.
            "options": {k: str(v) for k, v in opts.items()} if isinstance(opts, dict) else {},
            "reference_answer": s.get("answer"),
            "difficulty": _diff(it), "clo": None, "topic": None,
            "explanation": _explanation(it),
        })
    return rows


def _r2_rows(items: list) -> list:
    """R2 (Đọc phần 2, thông báo 3 phương án) → câu đơn lẻ part 2, type choice."""
    rows = []
    for it in items:
        s = it.get("s2_item") or {}
        content = str(s.get("stem") or "").strip()
        if not content:
            continue
        rows.append({
            "part": 2, "type": "choice", "content": content,
            "audio_url": None, "image_url": None,
            "options": s.get("options") or {},
            "reference_answer": s.get("answer"),
            "difficulty": _diff(it), "clo": None, "topic": None,
            "explanation": _explanation(it),
        })
    return rows


def _r3_rows(items: list) -> list:
    """R3 (Đọc phần 3, đoạn văn + câu hỏi) → NHÓM part 3 (passage) + câu con type choice."""
    rows = []
    for it in items:
        s3 = it.get("s3_item") or {}
        passage = str(s3.get("passage") or "").strip()
        exp = _explanation(it)   # ghi chú cấp-nhóm (gắn lên mỗi câu con để GV luôn thấy)
        children = []
        for q in (s3.get("questions") or []):
            content = str(q.get("stem") or "").strip()
            if not content:
                continue
            children.append({
                "part": 3, "type": "choice", "content": content,
                "audio_url": None, "image_url": None,
                "options": q.get("options") or {},
                "reference_answer": q.get("answer"),
                "difficulty": _diff(it), "clo": None, "topic": None,
                "explanation": exp,
            })
        if not passage or not children:
            continue
        rows.append({
            "part": 3, "topic": None, "passage_text": passage,
            "audio_url": None, "image_url": None, "difficulty": _diff(it),
            "questions": children,
        })
    return rows


def _r4_blank_content(passage: str, k: str, ptag: str) -> str:
    """Nội dung câu điền R4: ngữ cảnh quanh chỗ trống + mã đoạn.

    QUAN TRỌNG: nếu để chung 'Chỗ trống (21)' cho mọi đoạn, hai câu con cùng số + cùng đáp án ở HAI ĐOẠN
    khác nhau sẽ trùng content_hash → save_parsed_items (dedup toàn cục) nuốt câu con thứ hai → nhóm rỗng.
    Mã đoạn (hash passage) đảm bảo content KHÁC nhau giữa các đoạn → không bị nuốt.
    """
    m = re.search(r"\(\s*" + re.escape(str(k)) + r"\s*\)", passage)
    if m:
        start = max(0, m.start() - 32)
        end = min(len(passage), m.end() + 32)
        ctx = " ".join(passage[start:end].split())
        return f"…{ctx}… · đoạn {ptag}"
    return f"Chỗ trống ({k}) · đoạn {ptag}"


def _r4_rows(items: list) -> list:
    """R4 (Đọc phần 4, cloze hộp-từ) → NHÓM part 4 (passage + hộp từ) + 10 câu con type fill."""
    rows = []
    for it in items:
        s4item = it.get("s4_item") or {}
        s4_raw = s4item.get("s4_raw") or []
        answers = {str(k): str(v) for k, v in (it.get("answers") or s4item.get("s4_answers") or {}).items()}
        box = [str(w) for w in (it.get("word_box") or [])]
        passage = boss_factory._r4_passage_from_raw(s4_raw) if s4_raw else ""
        if not passage.strip() or not answers:
            continue
        box_line = ("Hộp từ (chọn từ để điền): " + " · ".join(box)) if box else ""
        passage_text = (box_line + "\n\n" + passage).strip() if box_line else passage.strip()
        exp = _explanation(it)
        ptag = hashlib.sha1(passage.encode("utf-8")).hexdigest()[:6]  # phân biệt câu con giữa các đoạn
        children = []
        for k in sorted(answers, key=lambda x: int(x) if str(x).isdigit() else 0):
            children.append({
                "part": 4, "type": "fill", "content": _r4_blank_content(passage, k, ptag),
                "audio_url": None, "image_url": None, "options": {},
                "reference_answer": answers[k],
                "difficulty": _diff(it), "clo": None, "topic": None,
                "explanation": exp,
            })
        if not children:
            continue
        rows.append({
            "part": 4, "topic": None, "passage_text": passage_text,
            "audio_url": None, "image_url": None, "difficulty": _diff(it),
            "questions": children,
        })
    return rows


_DISPATCH = {
    "reading_s1": _r1_rows,
    "reading_s2_notice": _r2_rows,
    "reading_s3_comprehension": _r3_rows,
    "reading_s4_cloze": _r4_rows,
}


def bundle_items_to_rows(skill: str, items: list) -> list:
    """Chuyển danh sách item của nhà máy (1 skill) → rows cho save_parsed_items.

    CHỈ nhận item qua QC cấu trúc (qc_ok) để không đẩy câu hỏng vào ngân hàng. Item bị cổng kiểm
    đáp án gắn cờ NGHI vẫn VÀO ngân hàng (kèm ghi chú) — GV là cổng cuối, không tự xoá.
    """
    fn = _DISPATCH.get(skill)
    if fn is None:
        raise ValueError(f"skill chưa hỗ trợ chuyển vào ngân hàng: {skill!r}")
    ok_items = [it for it in items if it.get("qc_ok", True)]
    return fn(ok_items)
