"""Chuyển kết quả nhà máy sinh câu (boss_factory) → hàng ngân hàng.

Đầu ra khớp shape mà ``parser.save_parsed_items`` mong đợi (câu đơn lẻ + nhóm passage),
để tái dùng nguyên cơ chế lưu-nháp + chống-trùng (content_hash) + tạo QuestionGroup có sẵn.

Phạm vi: ĐỌC R1–R4 (SPEC-FACTORY-016) + VIẾT W1/W2 (SPEC-FACTORY-017) + NÓI (SPEC-FACTORY-018).
Nghe = slice sau (Đạt duyệt riêng vì Nghe kéo theo audio nặng).

Cờ cổng kiểm đáp án (⚠ NGHI / ✅ PASS) được nhét vào ``explanation`` để giáo viên thấy NGAY trong
ngân hàng — KHÔNG thêm cột DB mới (không cần migration). Dạng KHÔNG có cổng kiểm (W2 tự luận) →
converter TỰ chèn note "GV soát tay" (deterministic — không phụ thuộc cờ verify/nhánh nào khác).
"""
import hashlib
import re
from collections import Counter
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


# Khối W1 chuẩn = 5 câu viết-lại / 1 mục đề (đúng format đề 2601 thật: parser gộp cả Section 1
# thành MỘT Question part 5; blueprint part 5 count=1 → đề generate lấy nguyên khối).
W1_BLOCK_SIZE = 5
W1_BLOCK_INSTRUCTION = (
    "Finish each of the following sentences in such a way that it means the same as the "
    "sentence printed before it."
)
# Note GV cho dạng KHÔNG có cổng kiểm đáp án AI (W2 tự luận) — converter chèn thẳng, deterministic.
MANUAL_REVIEW_NOTE = (
    "[✍ CHƯA QUA CỔNG KIỂM ĐÁP ÁN AI — dạng tự luận không có đáp án đóng; "
    "GIÁO VIÊN SOÁT TAY nội dung trước khi duyệt]"
)


def _block_diff(chunk: list) -> str:
    """Độ khó đại diện cho 1 khối nhiều câu: lấy mức xuất hiện nhiều nhất trong khối."""
    return Counter(_diff(it) for it in chunk).most_common(1)[0][0]


def _w1_rows(items: list) -> list:
    """W1 (Viết phần 1, viết lại câu) → khối 5 câu / 1 Question part 5, type writing (format đề 2601).

    content = hướng dẫn + '<i>. <câu gốc>' + dòng phần-đầu-cho-sẵn; reference_answer = câu mẫu đánh số
    (grade_writing nhận qua prompt_requirements + reference_answer). Khối cuối thiếu câu (<5) vẫn vào
    ngân hàng kèm CẢNH BÁO rõ trong explanation — GV quyết (sinh lô nhỏ mà bỏ hết = nhà máy 'câm').
    Cổng kiểm W1 chạy TỪNG câu trước khi gộp → explanation liệt kê kết quả kiểm theo câu.
    """
    rows = []
    ok_items = [it for it in items if str(((it.get("w1_item") or {}).get("answer")) or "").strip()
                and str(((it.get("w1_item") or {}).get("original")) or "").strip()
                and str(((it.get("w1_item") or {}).get("prompt")) or "").strip()]
    # Xếp XEN KẼ theo nguon_seed (round-robin) trước khi cắt khối: build_w1_variants trả biến thể
    # CÙNG seed nằm liền kề (cùng điểm ngữ pháp) — cắt tuần tự sẽ dồn 2-3 câu cùng dạng vào 1 khối,
    # lệch chuẩn đề W1 thật (5 câu = 5 phép biến đổi khác nhau). Review đối kháng S57.
    buckets: dict = {}
    for it in ok_items:
        buckets.setdefault(str(it.get("nguon_seed") or "?"), []).append(it)
    interleaved = []
    while any(buckets.values()):
        for k in list(buckets):
            if buckets[k]:
                interleaved.append(buckets[k].pop(0))
    for start in range(0, len(interleaved), W1_BLOCK_SIZE):
        chunk = interleaved[start:start + W1_BLOCK_SIZE]
        content_lines, answer_lines, verify_lines = [W1_BLOCK_INSTRUCTION, ""], [], []
        for i, it in enumerate(chunk, 1):
            w = it["w1_item"]
            content_lines.append(f"{i}. {str(w['original']).strip()}")
            content_lines.append(str(w["prompt"]).strip())
            answer_lines.append(f"{i}. {str(w['answer']).strip()}")
            cell = boss_factory.verify_cell(it)  # "" | PASS | ⚠ NGHI | CHƯA KIỂM
            note = str((it.get("answer_verify") or {}).get("note") or "").strip()
            # Note hiển thị CẢ khi PASS (như _verify_prefix R1-R4) — đặc biệt giữ chỉ dấu
            # 'mock (offline)' để khối mock KHÔNG hiển thị như đã-qua-kiểm-AI-thật.
            verify_lines.append(f"{i}) {cell or 'chưa bật kiểm'}" + (f" — {note[:160]}" if note else ""))
        n_suspect = sum(1 for it in chunk if it.get("answer_verify_flag") == "SUSPECT")
        exp_parts = []
        if n_suspect:
            exp_parts.append(f"[⚠ CỔNG KIỂM ĐÁP ÁN AI: {n_suspect}/{len(chunk)} câu NGHI — giáo viên soát kỹ câu mẫu]")
        else:
            exp_parts.append("[Cổng kiểm đáp án AI theo câu — GV vẫn duyệt câu mẫu trước khi dùng]")
        exp_parts.append("Kiểm theo câu: " + " · ".join(verify_lines))
        if len(chunk) < W1_BLOCK_SIZE:
            exp_parts.append(f"⚠ Khối chỉ có {len(chunk)}/{W1_BLOCK_SIZE} câu (lô sinh lẻ) — "
                             "đề chuẩn cần đủ 5 câu; GV cân nhắc trước khi duyệt.")
        srcs = [str(it.get("nguon_seed") or "?") for it in chunk]
        n_dup_seed = len(srcs) - len(set(srcs))
        if n_dup_seed:
            exp_parts.append(f"⚠ Khối có {n_dup_seed} câu TRÙNG nguồn seed (biến thể cùng điểm ngữ pháp) — "
                             "GV soát độ đa dạng dạng biến đổi trong khối.")
        exp_parts.append("Nguồn seed: " + ", ".join(srcs))
        rows.append({
            "part": 5, "type": "writing", "content": "\n".join(content_lines),
            "audio_url": None, "image_url": None, "options": {},
            "reference_answer": "\n".join(answer_lines),
            "difficulty": _block_diff(chunk), "clo": None, "topic": None,
            "explanation": "\n".join(exp_parts),
        })
    return rows


def _w2_rows(items: list) -> list:
    """W2 (Viết phần 2, thư ~100 từ, KHÔNG đáp án) → 1 Question part 6 / đề, type writing.

    content = vai + bối cảnh + các ý phải trả lời + hướng dẫn (đủ cho grade_writing chấm theo
    prompt_requirements); reference_answer=None (tự luận). Converter chèn note GV-soát-tay.
    """
    rows = []
    for it in items:
        w = it.get("w2_item") or {}
        role = str(w.get("role") or "").strip()
        situation = str(w.get("situation") or "").strip()
        if not role or not situation:
            continue
        points = [str(p).strip() for p in (w.get("points") or []) if str(p).strip()]
        instruction = str(w.get("instruction") or "").strip()
        content_parts = [role, "", situation]
        if points:
            content_parts += [""] + [f"- {p}" for p in points]
        if instruction:
            content_parts += ["", instruction]
        base = str(it.get("explanation") or "").strip()
        exp = MANUAL_REVIEW_NOTE + (f"\n{base}" if base else "") + \
            f"\nNguồn seed: {it.get('nguon_seed') or '?'}"
        rows.append({
            "part": 6, "type": "writing", "content": "\n".join(content_parts),
            "audio_url": None, "image_url": None, "options": {},
            "reference_answer": None,
            "difficulty": _diff(it), "clo": None, "topic": w.get("domain_guess"),
            "explanation": exp,
        })
    return rows


# Hướng dẫn thí sinh cho câu Nói phần phát triển chủ đề (part 11). Đề (part2_topic) sinh bằng tiếng
# Anh; dòng hướng dẫn tiếng Việt khớp giao diện app cho thí sinh — hệ chấm AI đọc cả nội dung.
SPEAK_INSTRUCTION = "Trình bày về chủ đề trên trong khoảng 2 phút (VSTEP B1 – Nói: phát triển chủ đề)."


def _speak_rows(items: list) -> list:
    """Nói → 1 Question part 11 (phát triển chủ đề)/thẻ, type speaking, KHÔNG có đáp án.

    D4 (Đạt duyệt): CHỈ import part2_topic (nội dung MỚI duy nhất) → 1 câu Nói part 11; part1/part3
    là seed lặp nguyên xi → KHÔNG import (tránh câu trùng vô nghĩa giữa mọi thẻ). content = đề nói
    (grade_speaking chấm theo prompt_requirements=content + audio thí sinh, reference_answer=None).
    Không có cổng kiểm đáp án đóng → converter chèn note GV soát tay (như W2).
    """
    rows = []
    for it in items:
        card = it.get("speak_card") or {}
        topic = str(card.get("part2_topic") or "").strip()
        if not topic:
            continue
        content = f"{topic}\n\n({SPEAK_INSTRUCTION})"
        base = str(it.get("explanation") or "").strip()
        src = card.get("src_code") or it.get("nguon_seed") or "?"
        exp = MANUAL_REVIEW_NOTE + (f"\n{base}" if base else "") + \
            f"\nMã sinh: {card.get('code') or '?'} · Nguồn seed: {src}"
        rows.append({
            "part": 11, "type": "speaking", "content": content,
            "audio_url": None, "image_url": None, "options": {},
            "reference_answer": None,
            "difficulty": _diff(it), "clo": None, "topic": card.get("domain_guess"),
            "explanation": exp,
        })
    return rows


_DISPATCH = {
    "reading_s1": _r1_rows,
    "reading_s2_notice": _r2_rows,
    "reading_s3_comprehension": _r3_rows,
    "reading_s4_cloze": _r4_rows,
    "writing_w1_rewrite": _w1_rows,
    "writing_w2_letter": _w2_rows,
    "speaking": _speak_rows,
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
