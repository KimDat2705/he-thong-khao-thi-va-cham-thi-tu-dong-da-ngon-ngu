"""Dịch vụ nhà máy sinh câu cho web.

Luồng 1 lượt: nạp seed (đề mẫu tổng hợp) → sinh biến thể (boss_factory, bám seed thật) →
cổng kiểm đáp án AI (R1–R4) → chuyển sang hàng ngân hàng → lưu vào DB dưới dạng nháp (draft)
cho giáo viên soát/duyệt tại /admin/bank.

Seed dùng bộ MẪU TỔNG HỢP trong repo (backend/tests/fixtures/factory_sample/bank_raw.json) — an toàn
công khai, KHÔNG chứa dữ liệu bản quyền của đối tác. Đổi sang đề thật của đối tác = thay file này.

Phạm vi hiện tại: ĐỌC R1–R4. Viết/Nói/Nghe = slice sau.
"""
import json
import os
import uuid

from sqlalchemy.orm import Session

from app.models.import_batch import ImportBatch
from app.services import boss_factory, parser
from app.services.factory_to_bank import bundle_items_to_rows

# backend/app/services/factory_service.py → backend/tests/fixtures/factory_sample/
_SEED_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "tests", "fixtures", "factory_sample",
)

# skill (tên bundle boss_factory) → (nạp seed, sinh biến thể). Chỉ ĐỌC R1–R4 lúc này.
FACTORY_SKILLS = {
    "reading_s1": (boss_factory.load_r1_seeds, boss_factory.build_r1_variants),
    "reading_s2_notice": (boss_factory.load_r2_seeds, boss_factory.build_r2_variants),
    "reading_s3_comprehension": (boss_factory.load_r3_seeds, boss_factory.build_r3_variants),
    "reading_s4_cloze": (boss_factory.load_r4_seeds, boss_factory.build_r4_variants),
}

# Nhãn hiển thị cho giao diện (khớp cách gọi ở /admin/bank).
SKILL_LABELS = {
    "reading_s1": "R1 · Đọc phần 1 (trắc nghiệm 4 phương án)",
    "reading_s2_notice": "R2 · Đọc phần 2 (thông báo, 3 phương án)",
    "reading_s3_comprehension": "R3 · Đọc phần 3 (đoạn văn + câu hỏi)",
    "reading_s4_cloze": "R4 · Đọc phần 4 (điền từ vào chỗ trống)",
}


def supported_skills() -> list:
    """Danh sách skill hỗ trợ (cho endpoint /factory/skills)."""
    return [{"skill": s, "label": SKILL_LABELS.get(s, s)} for s in FACTORY_SKILLS]


def _load_seed_bank() -> list:
    """Đọc đề mẫu tổng hợp làm seed cho nhà máy."""
    with open(os.path.join(_SEED_DIR, "bank_raw.json"), encoding="utf-8") as f:
        return json.load(f)


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

    seeds = load_seeds(_load_seed_bank())
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
    }
