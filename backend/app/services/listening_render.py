"""Render AUDIO (+ảnh chọn-tranh) cho một bộ Nghe đã có trong ngân hàng — SPEC-FACTORY-024.

Slice 3 (text-only) đưa KỊCH BẢN Nghe vào ngân hàng nhưng audio_url=None → cổng approve chặn duyệt.
Slice này render audio thật cho bộ đã soát: đọc lại BUNDLE THÔ (transcripts gốc) từ sidecar Storage
(SPEC-FACTORY-023 cất lúc sinh) → build_listening_audio (giọng C, đọc-2-lần, pause Cambridge) → 1 file
MP3 trọn bài → upload Storage → gắn audio_url lên CẢ BỘ 15 câu (nhóm part 8 + 5 câu part 7). Sau đó GV
duyệt được (cổng audio thỏa). Ảnh chọn-tranh part 7 = OPT-IN (build_listening_images, billing).

ĐỊNH DANH BÀI = token 'code·ltag' (KHÔNG chỉ code): code (LB1.90-<seed>-<idx>) TẤT ĐỊNH nên TRÙNG giữa
2 lượt sinh cùng seed; ltag (phái sinh nội dung) phân biệt. Token nhúng CẢ content câu con part 8 lẫn
trace explanation part 7 → render gom ĐÚNG 15 câu của bài này + tải ĐÚNG sidecar (review S57h: nếu chỉ
theo code → vớ nhầm câu part 7 bài khác + đè sidecar). Storage dùng slug 'code.ltag' (path-safe).

KHÔNG đổi schema: bộ Nghe nhận diện qua NHÓM part 8 (anchor GV chọn) + token trong content/explanation.
Audio là 1 FILE trọn bài gắn cấp-file cho mọi câu (khớp quyết định 'audio cả file không cắt').

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
from app.services.factory_to_bank import lis_storage_slug

logger = logging.getLogger(__name__)

# Token bài nằm trong content câu con part 8: "(Bài LB1.90-2601-1·a3f9c2) Nghe ...". Bắt CẢ code·ltag.
_BUNDLE_IN_CONTENT = re.compile(r"\(Bài\s+([^\s·)]+·[^\s·)]+)\)")


def _bundle_token_from_group(db: Session, group: QuestionGroup) -> str:
    """Đọc token 'code·ltag' từ content câu con part 8 (converter nhúng '(Bài {code}·{ltag})')."""
    child = (db.query(Question)
             .filter(Question.group_id == group.id)
             .order_by(Question.id).first())
    if not child:
        return ""
    m = _BUNDLE_IN_CONTENT.search(child.content or "")
    return m.group(1).strip() if m else ""


def _part7_of_bundle(db: Session, token: str) -> list:
    """5 câu part 7 standalone CỦA ĐÚNG bài — gom qua token 'Mã sinh: {code·ltag} ·' trong explanation
    (converter ghi 'Mã sinh: {token} · Nguồn seed'). Token gồm ltag → KHÔNG vớ nhầm bài khác cùng code."""
    return (db.query(Question)
            .filter(Question.exam_id.is_(None), Question.part == 7,
                    Question.explanation.like(f"%Mã sinh: {token} ·%"))
            .order_by(Question.id).all())


def render_listening_media(db: Session, group_id: int, generator, with_images: bool = False) -> dict:
    """Render audio (+ảnh opt-in) cho bộ Nghe của NHÓM part 8 `group_id` → gắn URL lên cả bộ, trả tổng kết.

    Raise ValueError (→ HTTP 400 ở endpoint / status error ở job) khi: nhóm không phải bộ Nghe part 8
    trong ngân hàng / không đọc được token bài / thiếu sidecar (chưa sinh sau khi có Storage) / Storage lỗi.
    """
    group = (db.query(QuestionGroup)
             .filter(QuestionGroup.id == group_id, QuestionGroup.exam_id.is_(None),
                     QuestionGroup.part == 8).first())
    if group is None:
        raise ValueError(f"Không tìm thấy nhóm Nghe (part 8) id={group_id} trong ngân hàng.")
    token = _bundle_token_from_group(db, group)
    if not token:
        raise ValueError(f"Nhóm {group_id} không đọc được mã bài Nghe (không phải bộ nhà máy sinh?).")
    code, _, ltag = token.partition("·")
    slug = lis_storage_slug(code, ltag)     # path-safe cho Storage (khớp key sidecar lúc sinh)

    # Tải bundle thô (transcripts gốc) từ sidecar Storage — build_listening_audio cần đúng shape này.
    try:
        raw = media_store.download_bytes(f"listening/{slug}.bundle.json")
    except media_store.MediaStoreError as exc:
        raise ValueError(
            f"Không tải được bundle Nghe {slug} từ Storage ({exc}). Bộ sinh TRƯỚC khi có Storage sẽ "
            "thiếu sidecar — sinh lại bộ Nghe (sidecar cất lúc sinh) rồi render."
        )
    try:
        item = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise ValueError(f"Sidecar bundle Nghe {slug} hỏng/không phải JSON: {exc}")

    out_dir = tempfile.mkdtemp(prefix=f"lis_render_{slug}_")
    try:
        info = boss_factory.build_listening_audio(generator, item, out_dir, to_mp3=True)
        audio_url = media_store.upload_file(info["audio_path"], f"listening/{slug}.{info['format']}")

        # Audio 1 FILE trọn bài → gắn cấp-file cho nhóm part 8 + mọi câu part 7 (khớp 'cả file không cắt').
        group.audio_url = audio_url
        part7 = _part7_of_bundle(db, token)
        for q in part7:
            q.audio_url = audio_url
        db.commit()     # COMMIT audio TRƯỚC ảnh — ảnh opt-in lỗi KHÔNG được làm mất công render audio đắt.

        result = {
            "code": code, "group_id": group_id, "audio_url": audio_url,
            "duration_s": info["duration_s"], "duration_min": round(info["duration_s"] / 60.0, 1),
            "format": info["format"], "n_part7": len(part7), "n_segments": info["n_segments"],
            "images": None,
        }

        # Ảnh chọn-tranh part 7 (OPT-IN — billing). 3 ảnh A/B/C/câu → upload → image_url = 3 URL nối phẩy
        # (FE hiển thị 3 tranh = follow-up 6b). BEST-EFFORT: upload lỗi 1 câu → log, bỏ qua (audio đã cất).
        if with_images:
            img = boss_factory.build_listening_images(generator, item, out_dir)
            l1 = (item.get("transcripts") or {}).get("l1") or []
            n_set = 0
            for idx, q in enumerate(part7):
                if idx >= len(l1):
                    break
                fns = [fn.strip() for fn in str(l1[idx].get("image_urls") or "").split(",") if fn.strip()]
                try:
                    urls = [media_store.upload_file(os.path.join(out_dir, fn), f"listening/{slug}/{fn}")
                            for fn in fns]
                except media_store.MediaStoreError as exc:
                    logger.warning("Render Nghe %s: upload ảnh câu %d lỗi, bỏ qua: %s", slug, idx + 1, exc)
                    continue
                if len(urls) == len(boss_factory.L1_OPTION_KEYS):     # chỉ gắn khi đủ 3 tranh A/B/C
                    q.image_url = ",".join(urls)
                    n_set += 1
            db.commit()
            result["images"] = {"n_images": img["n_images"], "n_failed": img["n_failed"],
                                "needs_billing": img["needs_billing"], "questions_with_images": n_set}

        logger.info("Render Nghe %s: audio %.1f' (%s), %d câu part 7, ảnh=%s",
                    slug, result["duration_min"], info["format"], len(part7), bool(with_images))
        return result
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)
