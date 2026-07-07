"""Dịch vụ nhà máy sinh câu cho web.

Luồng 1 lượt: nạp seed (đề mẫu tổng hợp) → sinh biến thể (boss_factory, bám seed thật) →
cổng kiểm đáp án AI (R1–R4 + W1; W2 tự luận không có → converter chèn note GV soát tay) →
chuyển sang hàng ngân hàng → lưu vào DB dưới dạng nháp (draft) cho giáo viên soát/duyệt
tại /admin/bank.

Seed dùng bộ MẪU TỔNG HỢP trong repo (backend/tests/fixtures/factory_sample/) — an toàn công khai,
KHÔNG chứa dữ liệu bản quyền của đối tác. Đọc/Viết dùng bank_raw.json, Nói dùng pool_speak.json,
Nghe dùng pool_lis.json. Đổi sang đề thật của đối tác = thay các file này.

Phạm vi: ĐỌC R1–R4 (SPEC-FACTORY-016) + VIẾT W1/W2 (SPEC-FACTORY-017) + NÓI (SPEC-FACTORY-018) +
NGHE text-only (SPEC-FACTORY-019: kịch bản vào ngân hàng, audio render ở slice sau).
"""
import json
import logging
import os
import uuid

from sqlalchemy.orm import Session

from app.models.import_batch import ImportBatch
from app.services import boss_factory, media_store, parser
from app.services.factory_to_bank import bundle_items_to_rows

logger = logging.getLogger(__name__)

# backend/app/services/factory_service.py → backend/tests/fixtures/factory_sample/
_SEED_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "tests", "fixtures", "factory_sample",
)

# skill (tên bundle boss_factory) → (nạp seed, sinh biến thể). ĐỌC R1–R4 + VIẾT W1/W2 + NÓI + NGHE.
FACTORY_SKILLS = {
    "reading_s1": (boss_factory.load_r1_seeds, boss_factory.build_r1_variants),
    "reading_s2_notice": (boss_factory.load_r2_seeds, boss_factory.build_r2_variants),
    "reading_s3_comprehension": (boss_factory.load_r3_seeds, boss_factory.build_r3_variants),
    "reading_s4_cloze": (boss_factory.load_r4_seeds, boss_factory.build_r4_variants),
    "writing_w1_rewrite": (boss_factory.load_w1_seeds, boss_factory.build_w1_variants),
    "writing_w2_letter": (boss_factory.load_w2_seeds, boss_factory.build_w2_variants),
    "speaking": (boss_factory.load_speak_seeds, boss_factory.build_speak_variants),
    # Nghe: build_lis_variants sinh KỊCH BẢN + đáp án (CHƯA render audio — audio là slice sau).
    "listening": (boss_factory.load_lis_seeds, boss_factory.build_lis_variants),
}

# Seed file theo skill (mặc định bank_raw.json cho Đọc/Viết). Nói dùng pool_speak.json (DICT thẻ),
# Nghe dùng pool_lis.json — mỗi nguồn có schema riêng nên tách file.
_SKILL_SEED_FILE = {
    "speaking": "pool_speak.json",
    "listening": "pool_lis.json",
}

# Nhãn hiển thị cho giao diện (khớp cách gọi ở /admin/bank).
SKILL_LABELS = {
    "reading_s1": "R1 · Đọc phần 1 (trắc nghiệm 4 phương án)",
    "reading_s2_notice": "R2 · Đọc phần 2 (thông báo, 3 phương án)",
    "reading_s3_comprehension": "R3 · Đọc phần 3 (đoạn văn + câu hỏi)",
    "reading_s4_cloze": "R4 · Đọc phần 4 (điền từ vào chỗ trống)",
    "writing_w1_rewrite": "W1 · Viết phần 1 (viết lại câu — khối 5 câu/đề)",
    "writing_w2_letter": "W2 · Viết phần 2 (viết thư ~100 từ, tự luận)",
    "speaking": "S · Nói (phát triển chủ đề — chấm AI, GV soát)",
    "listening": "L · Nghe (5 chọn-tranh part 7 + 10 điền-từ part 8 — kịch bản text, audio slice sau)",
}

# Part VSTEP_B1 mà câu của skill đổ vào (FE auto-chuyển bộ lọc sau khi sinh; Nghe span 2 part
# 7 (chọn-tranh L1) + 8 (điền-từ L2) nên là LIST).
SKILL_PARTS = {
    "reading_s1": [1],
    "reading_s2_notice": [2],
    "reading_s3_comprehension": [3],
    "reading_s4_cloze": [4],
    "writing_w1_rewrite": [5],
    "writing_w2_letter": [6],
    "speaking": [11],           # D4: part2_topic → part 11 (phát triển chủ đề)
    "listening": [7, 8],        # L1 chọn-tranh → part 7 (đơn); L2 điền-từ → part 8 (nhóm 10 con)
}


def supported_skills() -> list:
    """Danh sách skill hỗ trợ (cho endpoint /factory/skills).

    gate: 'ai' = có cổng kiểm đáp án AI (R1-R4 MCQ/cloze, W1 viết-lại-độc-lập) ·
    'manual' = không có cổng kiểm đáp án đóng tự động, GV soát tay (W2, Nói, Nghe).
    """
    return [{
        "skill": s,
        "label": SKILL_LABELS.get(s, s),
        "parts": SKILL_PARTS.get(s, []),
        "gate": "ai" if s in boss_factory.VERIFY_SUPPORTED_SKILLS else "manual",
    } for s in FACTORY_SKILLS]


def _load_seed_bank(skill: str):
    """Đọc file seed mẫu ĐÚNG theo skill (bank_raw.json / pool_speak.json). Trả nội dung JSON thô
    (list cho Đọc/Viết, dict thẻ cho Nói) — loader của skill tự chuẩn hoá."""
    fname = _SKILL_SEED_FILE.get(skill, "bank_raw.json")
    with open(os.path.join(_SEED_DIR, fname), encoding="utf-8") as f:
        return json.load(f)


def _persist_listening_sidecars(items: list) -> int:
    """Cất bundle Nghe THÔ (transcripts L1/L2 + lis_item) lên Supabase Storage keyed theo mã bài —
    để slice RENDER audio đọc lại: build_listening_audio cần transcripts GỐC mà ngân hàng KHÔNG lưu
    dạng cấu trúc (chỉ nhét chuỗi vào explanation, parse ngược mong manh). File: listening/{code}.bundle.json.

    Chỉ chạy khi Storage đã cấu hình (LIVE Supabase); local/test thiếu cấu hình → bỏ qua (render là
    tính năng LIVE). Lỗi upload 1 bài KHÔNG làm hỏng cả lượt sinh (log + bỏ qua — bài đó chưa render được
    tới khi cất lại). Trả số sidecar đã cất.
    """
    if not media_store.is_configured():
        return 0
    n = 0
    for it in items:
        if not it.get("qc_ok", True):
            continue
        lis = it.get("lis_item") or {}
        code = str(lis.get("code") or "").strip()
        tr = it.get("transcripts") or {}
        if not code or not tr.get("l1") or not tr.get("l2"):
            continue
        payload = json.dumps({"transcripts": tr, "lis_item": lis}, ensure_ascii=False).encode("utf-8")
        try:
            media_store.upload_bytes(f"listening/{code}.bundle.json", payload, "application/json")
            n += 1
        except media_store.MediaStoreError as exc:
            logger.warning("Nghe: không cất được sidecar bundle %s: %s", code, exc)
    return n


def run_factory_to_bank(
    db: Session,
    skill: str,
    limit: int = 3,
    per_seed: int = 1,
    verify: bool = True,
    generator=None,
) -> dict:
    """Chạy nhà máy cho 1 skill và lưu câu sinh vào ngân hàng (draft). Trả về bảng tổng kết.

    generator=None → chế độ MOCK (không gọi Gemini, để test luồng); ngược lại dùng B1QuestionGenerator.
    """
    if skill not in FACTORY_SKILLS:
        raise ValueError(f"skill không hỗ trợ: {skill!r}")
    load_seeds, build_variants = FACTORY_SKILLS[skill]

    seeds = load_seeds(_load_seed_bank(skill))
    if limit:
        seeds = seeds[: int(limit)]
    items = build_variants(seeds, per_seed=int(per_seed), generator=generator)

    if verify and skill in boss_factory.VERIFY_SUPPORTED_SKILLS:
        boss_factory.verify_bundle_answers(items, skill, generator)

    rows = bundle_items_to_rows(skill, items)

    # Mỗi lần chạy = một lô nhập mới (truy vết). Tạo 'pending' TRƯỚC, chỉ đánh 'imported' khi lưu XONG;
    # lỗi giữa chừng → đánh 'failed' + error_report (không để lô mồ côi mang nhãn 'imported').
    batch = ImportBatch(source_file=f"factory:{skill}", content_hash=uuid.uuid4().hex, status="pending")
    db.add(batch)
    db.commit()
    db.refresh(batch)

    try:
        saved = parser.save_parsed_items(db, rows, batch.id)
    except Exception as exc:
        db.rollback()
        db.query(ImportBatch).filter(ImportBatch.id == batch.id).update(
            {"status": "failed", "error_report": {"error": str(exc)}}
        )
        db.commit()
        raise
    db.query(ImportBatch).filter(ImportBatch.id == batch.id).update({"status": "imported"})
    db.commit()

    # Nghe: cất bundle thô lên Storage để render audio đọc lại transcript gốc (slice render).
    sidecars = _persist_listening_sidecars(items) if skill == "listening" else 0

    suspect = sum(
        1 for it in items
        if it.get("qc_ok", True) and it.get("answer_verify_flag") == "SUSPECT"
    )
    return {
        "skill": skill,
        "generated": len(items),
        "qc_ok": sum(1 for it in items if it.get("qc_ok")),
        "saved_questions": saved["imported_questions"],
        "saved_groups": saved["imported_groups"],
        "skipped_questions": saved["skipped_questions"],
        "answer_suspect": suspect,
        "sidecars_stored": sidecars,
    }
