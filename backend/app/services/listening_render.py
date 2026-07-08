"""Render AUDIO (+ảnh chọn-tranh) cho một bộ Nghe đã có trong ngân hàng — SPEC-FACTORY-024.

Slice 3 (text-only) đưa KỊCH BẢN Nghe vào ngân hàng nhưng audio_url=None → cổng approve chặn duyệt.
Slice này render audio thật cho bộ đã soát: đọc lại BUNDLE THÔ (transcripts gốc) từ sidecar Storage
(SPEC-FACTORY-023 cất lúc sinh) → build_listening_audio (giọng C, đọc-2-lần, pause Cambridge) → 1 file
MP3 trọn bài → upload Storage → gắn audio_url lên CẢ BỘ 15 câu (nhóm part 8 + 5 câu part 7). Sau đó GV
duyệt được (cổng audio thỏa). Ảnh chọn-tranh part 7 = OPT-IN (build_listening_images, billing).

KHÔNG đổi schema: bộ Nghe được nhận diện qua NHÓM part 8 (anchor GV chọn) + token 'Mã sinh: {code}'
trong explanation để gom 5 câu part 7 standalone. Audio là 1 FILE trọn bài gắn cấp-file cho mọi câu
(khớp quyết định 'audio cả file không cắt').

build_listening_audio là op DÀI (nhiều call TTS + retry) → CHỈ chạy trong job nền (enrich_jobs), KHÔNG
inline request.
"""
import json
import logging
import os
import re
import shutil
import tempfile

from sqlalchemy.orm import Session

from app.models.question import Question
from app.models.question_group import QuestionGroup
from app.services import boss_factory, media_store

logger = logging.getLogger(__name__)

# Mã bài nằm trong content câu con part 8: "(Bài LB1.90-2601-1·a3f9c2) Nghe ...". Lấy phần trước '·'.
_CODE_IN_CONTENT = re.compile(r"\(Bài\s+([^·)]+)·")


def _bundle_code_from_group(db: Session, group: QuestionGroup) -> str:
    """Đọc mã bài (LB1.90-*) từ content câu con part 8 (converter nhúng '(Bài {code}·{ltag})')."""
    child = (db.query(Question)
             .filter(Question.group_id == group.id)
             .order_by(Question.id).first())
    if not child:
        return ""
    m = _CODE_IN_CONTENT.search(child.content or "")
    return m.group(1).strip() if m else ""


def _part7_of_bundle(db: Session, code: str) -> list:
    """5 câu part 7 standalone của bộ Nghe — gom qua token 'Mã sinh: {code} ·' trong explanation
    (converter ghi 'Mã sinh: {code} · Nguồn seed'). Token có dấu cách + '·' → không nuốt mã dài hơn."""
    return (db.query(Question)
            .filter(Question.exam_id.is_(None), Question.part == 7,
                    Question.explanation.like(f"%Mã sinh: {code} ·%"))
            .order_by(Question.id).all())


def render_listening_media(db: Session, group_id: int, generator, with_images: bool = False) -> dict:
    """Render audio (+ảnh opt-in) cho bộ Nghe của NHÓM part 8 `group_id` → gắn URL lên cả bộ, trả tổng kết.

    Raise ValueError (→ HTTP 400 ở endpoint / status error ở job) khi: nhóm không phải bộ Nghe part 8
    trong ngân hàng / không đọc được mã bài / thiếu sidecar (chưa sinh sau khi có Storage) / Storage lỗi.
    """
    group = (db.query(QuestionGroup)
             .filter(QuestionGroup.id == group_id, QuestionGroup.exam_id.is_(None),
                     QuestionGroup.part == 8).first())
    if group is None:
        raise ValueError(f"Không tìm thấy nhóm Nghe (part 8) id={group_id} trong ngân hàng.")
    code = _bundle_code_from_group(db, group)
    if not code:
        raise ValueError(f"Nhóm {group_id} không đọc được mã bài Nghe (không phải bộ nhà máy sinh?).")

    # Tải bundle thô (transcripts gốc) từ sidecar Storage — build_listening_audio cần đúng shape này.
    try:
        raw = media_store.download_bytes(f"listening/{code}.bundle.json")
    except media_store.MediaStoreError as exc:
        raise ValueError(
            f"Không tải được bundle Nghe {code} từ Storage ({exc}). Bộ sinh TRƯỚC khi có Storage sẽ "
            "thiếu sidecar — sinh lại bộ Nghe (sidecar cất lúc sinh) rồi render."
        )
    try:
        item = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise ValueError(f"Sidecar bundle Nghe {code} hỏng/không phải JSON: {exc}")

    out_dir = tempfile.mkdtemp(prefix=f"lis_render_{code}_")
    try:
        info = boss_factory.build_listening_audio(generator, item, out_dir, to_mp3=True)
        audio_url = media_store.upload_file(info["audio_path"], f"listening/{code}.{info['format']}")

        # Audio 1 FILE trọn bài → gắn cấp-file cho nhóm part 8 + mọi câu part 7 (khớp 'cả file không cắt').
        group.audio_url = audio_url
        part7 = _part7_of_bundle(db, code)
        for q in part7:
            q.audio_url = audio_url

        result = {
            "code": code, "group_id": group_id, "audio_url": audio_url,
            "duration_s": info["duration_s"], "duration_min": round(info["duration_s"] / 60.0, 1),
            "format": info["format"], "n_part7": len(part7), "n_segments": info["n_segments"],
            "images": None,
        }

        # Ảnh chọn-tranh part 7 (OPT-IN — billing). 3 ảnh A/B/C/câu → upload → image_url = 3 URL nối phẩy
        # (FE hiển thị 3 tranh = follow-up 6b). GRACEFUL: build_listening_images tự skip ảnh lỗi.
        if with_images:
            img = boss_factory.build_listening_images(generator, item, out_dir)
            l1 = (item.get("transcripts") or {}).get("l1") or []
            n_set = 0
            for idx, q in enumerate(part7):
                if idx >= len(l1):
                    break
                fns = [fn.strip() for fn in str(l1[idx].get("image_urls") or "").split(",") if fn.strip()]
                urls = [media_store.upload_file(os.path.join(out_dir, fn), f"listening/{fn}") for fn in fns]
                if len(urls) == len(boss_factory.L1_OPTION_KEYS):     # chỉ gắn khi đủ 3 tranh A/B/C
                    q.image_url = ",".join(urls)
                    n_set += 1
            result["images"] = {"n_images": img["n_images"], "n_failed": img["n_failed"],
                                "needs_billing": img["needs_billing"], "questions_with_images": n_set}

        db.commit()
        logger.info("Render Nghe %s: audio %.1f' (%s), %d câu part 7, ảnh=%s",
                    code, result["duration_min"], info["format"], len(part7), bool(with_images))
        return result
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)
