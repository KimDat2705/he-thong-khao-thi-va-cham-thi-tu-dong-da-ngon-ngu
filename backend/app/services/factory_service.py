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
from typing import Optional

from sqlalchemy.orm import Session

from app.models.import_batch import ImportBatch
from app.services import boss_factory, media_store, parser
from app.services.factory_to_bank import bundle_items_to_rows, lis_bundle_identity, lis_storage_slug

logger = logging.getLogger(__name__)

# backend/app/services/factory_service.py → backend/tests/fixtures/factory_sample/
_SEED_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "tests", "fixtures", "factory_sample",
)

# --- Chủ đề / Độ khó (Cách A — gợi ý mềm cho AI) -----------------------------------------------
# Nhà máy (Bản 2) sinh biến thể BÁM SEED thật → chủ đề/độ khó KHÔNG tự do như Bản 1 (bịa từ đầu).
# Cách A: GIỮ NGUYÊN format đề mẫu, nhét "yêu cầu thêm" (chủ đề/độ khó người dùng chọn) vào cuối
# prompt sinh biến thể — đúng cơ chế Bản 1 đang dùng. Bọc generator ở MỘT chỗ để KHÔNG phải sửa 8
# hàm build_*_variants. CHỈ áp cho bước SINH, KHÔNG áp cho cổng kiểm đáp án (gate giải độc lập).
_DIFF_VI = {"easy": "Dễ", "medium": "Trung bình", "hard": "Khó"}


def _build_steer(topic: Optional[str], difficulty: Optional[str]) -> str:
    """Câu 'yêu cầu thêm' nhét vào cuối user_prompt khi sinh biến thể (rỗng nếu không chọn gì)."""
    lines = []
    if topic:
        lines.append(f'- Chủ đề nội dung: "{topic}". Viết câu/ngữ liệu XOAY QUANH chủ đề này.')
    if difficulty:
        dv = _DIFF_VI.get(difficulty, difficulty)
        lines.append(f"- Mức độ khó: {dv} ({difficulty}). Điều chỉnh từ vựng/ngữ pháp cho đúng mức này.")
    if not lines:
        return ""
    return ("\n\n--- YÊU CẦU THÊM (điều chỉnh theo người dùng — GIỮ NGUYÊN cấu trúc/format như đề mẫu):\n"
            + "\n".join(lines))


class _SteeredGenerator:
    """Bọc generator: nhét 'yêu cầu thêm' (chủ đề/độ khó) vào cuối user_prompt của MỌI lần _call_gemini,
    KHÔNG phải sửa từng hàm build_*_variants. Uỷ quyền mọi thuộc tính khác (client, model_name...) về gốc."""

    def __init__(self, base, steer: str):
        self._base = base
        self._steer = steer

    def _call_gemini(self, system_instruction, user_prompt, *args, **kwargs):
        if self._steer:
            user_prompt = f"{user_prompt}{self._steer}"
        return self._base._call_gemini(system_instruction, user_prompt, *args, **kwargs)

    def __getattr__(self, name):
        # Chỉ gọi khi thuộc tính KHÔNG có trên wrapper (_base/_steer/_call_gemini đã có) → uỷ quyền về gốc.
        return getattr(self._base, name)

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
    "reading_s1": "Part 1 · R1 Đọc — trắc nghiệm (câu đơn)",
    "reading_s2_notice": "Part 2 · R2 Đọc — thông báo (câu đơn)",
    "reading_s3_comprehension": "Part 3 · R3 Đọc — đoạn văn (nhóm: 1 đoạn + 5 câu)",
    "reading_s4_cloze": "Part 4 · R4 Đọc — điền từ (nhóm: 1 đoạn + 10 chỗ)",
    "writing_w1_rewrite": "Part 5 · W1 Viết — viết lại câu (khối 5 câu)",
    "writing_w2_letter": "Part 6 · W2 Viết — viết thư (tự luận)",
    "speaking": "Part 11 · Nói — phát triển chủ đề (GV soát tay)",
    "listening": "Part 7+8 · Nghe cả bài (nhóm part 8, chung 1 audio)",
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
        tr = it.get("transcripts") or {}
        if not lis.get("code") or not tr.get("l1") or not tr.get("l2"):
            continue
        # Key theo slug code.ltag (KHÔNG chỉ code): code trùng giữa 2 lượt sinh cùng seed → nếu key chỉ
        # theo code + upsert, lượt 2 ĐÈ sidecar lượt 1 → render tải nhầm transcript (review S57h HIGH).
        code, ltag = lis_bundle_identity(it)
        slug = lis_storage_slug(code, ltag)
        payload = json.dumps({"transcripts": tr, "lis_item": lis}, ensure_ascii=False).encode("utf-8")
        try:
            media_store.upload_bytes(f"listening/{slug}.bundle.json", payload, "application/json")
            n += 1
        except media_store.MediaStoreError as exc:
            logger.warning("Nghe: không cất được sidecar bundle %s: %s", slug, exc)
    return n


def run_factory_to_bank(
    db: Session,
    skill: str,
    limit: int = 3,
    per_seed: int = 1,
    verify: bool = True,
    generator=None,
    topic: Optional[str] = None,
    difficulty: Optional[str] = None,
    count: Optional[int] = None,
) -> dict:
    """Chạy nhà máy cho 1 skill và lưu câu sinh vào ngân hàng (draft). Trả về bảng tổng kết.

    generator=None → chế độ MOCK (không gọi Gemini, để test luồng); ngược lại dùng B1QuestionGenerator.
    topic/difficulty (Cách A): gợi ý mềm cho AI khi SINH (không đụng cổng kiểm). count (Số lượng cần
    sinh — giao diện Bản 2 như Bản 1): quy đổi sang seed×biến-thể theo số seed THẬT có; None → dùng
    limit/per_seed trực tiếp (giữ tương thích test/gọi cũ).
    """
    if skill not in FACTORY_SKILLS:
        raise ValueError(f"skill không hỗ trợ: {skill!r}")
    load_seeds, build_variants = FACTORY_SKILLS[skill]

    seeds = load_seeds(_load_seed_bank(skill))
    n_seeds = len(seeds)

    # 'count' = Số lượng cần sinh → quy đổi (limit, per_seed) sao cho TỔNG limit×per_seed BÁM SÁT count
    # (không vượt xa), trần cứng = n_seeds×3. per_seed nhỏ nhất trước (trải đều nhiều seed) rồi limit vừa
    # đủ → tránh over-generate (review S57i: ceil(count/limit) làm dư, vd count=6/n_seeds=5 → 10). Che
    # cơ chế seed khỏi giao diện (Đạt: giống Bản 1, 1 ô số lượng).
    if count is not None and n_seeds:
        want = max(1, int(count))
        per_seed = max(1, min(3, -(-want // n_seeds)))       # ceil(want/n_seeds), kẹp trần 3
        limit = max(1, min(n_seeds, -(-want // per_seed)))   # ceil(want/per_seed), kẹp n_seeds

    if limit:
        seeds = seeds[: int(limit)]

    # Steer chủ đề/độ khó (Cách A) CHỈ cho bước SINH; cổng kiểm dùng generator GỐC (giải độc lập,
    # không được lái theo chủ đề/độ khó).
    build_gen = generator
    if generator is not None:
        steer = _build_steer(topic, difficulty)
        if steer:
            build_gen = _SteeredGenerator(generator, steer)

    items = build_variants(seeds, per_seed=int(per_seed), generator=build_gen)
    if count is not None:
        # Cắt về ĐÚNG số lượng yêu cầu (derivation có thể dư ≤ per_seed-1; giữ đơn vị của skill: câu /
        # nhóm / bài — items là 1 đơn vị mỗi phần tử). Không vượt count → không lách trần MAX_ASYNC_COUNT.
        items = items[: int(count)]

    if verify and skill in boss_factory.VERIFY_SUPPORTED_SKILLS:
        boss_factory.verify_bundle_answers(items, skill, generator)

    rows = bundle_items_to_rows(skill, items, topic=topic, difficulty=difficulty)

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
        "n_seeds": n_seeds,
        "generated": len(items),
        "qc_ok": sum(1 for it in items if it.get("qc_ok")),
        "saved_questions": saved["imported_questions"],
        "saved_groups": saved["imported_groups"],
        "skipped_questions": saved["skipped_questions"],
        "answer_suspect": suspect,
        "sidecars_stored": sidecars,
    }
