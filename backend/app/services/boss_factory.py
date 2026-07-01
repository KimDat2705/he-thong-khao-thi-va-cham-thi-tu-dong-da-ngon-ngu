"""Question Factory — sinh biến thể câu hỏi B1 xuất ĐÚNG định dạng ngân hàng của đối tác
(pipeline "ghép đề từ ngân hàng" của sếp). SPEC-FACTORY-001 — slice P1-R1 (Đọc phần 1).

Định hướng (S52): sếp sở hữu pipeline ghép đề; việc mình = MỞ RỘNG NGÂN HÀNG. Module này là
"nhà máy sinh câu": lấy câu R1 THẬT trong bank_raw.json của đối tác làm SEED (grounded → hạn
chế tối đa ảo giác), rồi sinh biến thể MỚI cùng điểm ngữ pháp, xuất ĐÚNG shape s1 của đối tác
`{stem, options{A,B,C,D}, answer}` + nhãn độ khó (Dễ/TB/Khó cho quota 3/5/2 của sếp) +
explanation + truy vết seed + trạng thái QC + bản GV soát/ký.

KHÔNG đụng DB/web của hệ mình. Tái dùng engine Gemini qua B1QuestionGenerator (được truyền vào):
dùng `generator._call_gemini` khi có key; mock TẤT ĐỊNH khi không → test không gọi mạng.
"""
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Nhãn độ khó của đối tác (phan_loai_do_kho.py, quota 3 Dễ / 5 TB / 2 Khó).
DIFF_MAP = {"easy": "Dễ", "medium": "TB", "hard": "Khó"}
OPTION_KEYS = ["A", "B", "C", "D"]


def load_r1_seeds(bank: list) -> list:
    """Trích câu R1 (khóa `s1`) từ bank_raw.json của đối tác thành danh sách seed sạch."""
    seeds = []
    for rec in bank:
        ma_de = rec.get("ma_de") or rec.get("file") or "?"
        s1 = rec.get("s1") or {}
        for qnum, q in s1.items():
            stem = (q.get("stem") or "").strip()
            options = q.get("options") or {}
            answer = q.get("answer")
            if stem and isinstance(options, dict) and answer in options:
                seeds.append({
                    "ma_de": ma_de, "q": str(qnum), "stem": stem,
                    "options": options, "answer": answer,
                })
    return seeds


def _mock_variant(seed: dict, idx: int) -> dict:
    """Biến thể MOCK tất định (không gọi mạng): đổi câu để khác nguyên văn seed.

    Chỉ là stand-in cho test — chất lượng thật do Gemini real-mode + GV duyệt lo."""
    diff = ["easy", "medium", "hard"][idx % 3]
    reworded = " ".join(reversed((seed["stem"] or "").split()))
    options = {k: seed["options"][k] for k in OPTION_KEYS if k in seed["options"]}
    return {
        "stem": f"(Biến thể {idx + 1}) {reworded}",
        "options": options,
        "answer": seed["answer"],
        "difficulty": diff,
        "explanation": f"Biến thể từ {seed['ma_de']}#Q{seed['q']} (cùng điểm ngữ pháp).",
    }


def _real_variant(generator, seed: dict, idx: int) -> Optional[dict]:
    """Sinh biến thể THẬT qua Gemini: câu MỚI cùng điểm ngữ pháp, không sao chép."""
    system = (
        "You are a VSTEP B1 (CEFR B1) English item writer. Given a B1 multiple-choice "
        "grammar/vocabulary gap-fill question, write ONE NEW, parallel question that tests "
        "the SAME language point at the SAME B1 level — a FRESH sentence (NOT a copy or a "
        "trivial reword), with exactly 4 options A, B, C, D and exactly one correct answer. "
        "Distractors must be plausible. Assess difficulty by comparing the vocabulary to the "
        "CEFR B1 wordlist (easy = core A2-B1, medium = upper-B1, hard = B2+/low-frequency). "
        "Return ONLY JSON: {\"stem\": \"<sentence with a ...... blank>\", "
        "\"options\": {\"A\": str, \"B\": str, \"C\": str, \"D\": str}, "
        "\"answer\": \"A|B|C|D\", \"difficulty\": \"easy|medium|hard\", \"explanation\": str}."
    )
    user = (
        f"SEED question (test the SAME point, do NOT copy it):\n"
        f"Stem: {seed['stem']}\n"
        f"Options: {json.dumps(seed['options'], ensure_ascii=False)}\n"
        f"Correct answer key: {seed['answer']}\n"
        f"Generate parallel variant #{idx + 1}."
    )
    raw = generator._call_gemini(system, user)
    data = _loads_lenient(raw)
    return data if isinstance(data, dict) else None


def _loads_lenient(raw: str) -> dict:
    """Parse JSON khoan dung: gỡ rào ```code``` / text thừa quanh object {...} nếu có."""
    raw = (raw or "").strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start, end = raw.find("{"), raw.rfind("}")
        if start != -1 and end > start:
            return json.loads(raw[start:end + 1])
        raise


def qc_r1(variant: dict, seed: dict) -> list:
    """Cổng QC cho item R1 (bám cổng của đối tác). Trả danh sách lỗi (rỗng = đạt)."""
    issues = []
    stem = (variant.get("stem") or "").strip()
    options = variant.get("options") or {}
    answer = variant.get("answer")
    if not stem:
        issues.append("stem rỗng")
    if sorted(options.keys()) != OPTION_KEYS:
        issues.append(f"options phải đủ A,B,C,D (đang có {sorted(options.keys())})")
    else:
        vals = [str(v).strip().lower() for v in options.values()]
        if len(set(vals)) < len(vals):
            issues.append("có phương án trùng nội dung")
        if any(not str(v).strip() for v in options.values()):
            issues.append("có phương án rỗng")
    if answer not in options:
        issues.append("answer không thuộc options")
    if stem and stem == (seed.get("stem") or "").strip():
        issues.append("trùng nguyên văn seed (bản quyền)")
    return issues


def build_r1_variants(seeds: list, per_seed: int = 1, generator=None) -> list:
    """Sinh biến thể R1 cho danh sách seed. Mỗi item ra: shape s1 của đối tác + metadata."""
    use_mock = generator is None or getattr(generator, "client", None) is None
    out = []
    for seed in seeds:
        for i in range(per_seed):
            try:
                v = _mock_variant(seed, i) if use_mock else _real_variant(generator, seed, i)
            except Exception as e:  # sinh lỗi 1 biến thể không làm hỏng cả lô
                logger.warning(f"Sinh biến thể lỗi seed {seed['ma_de']}#Q{seed['q']}: {e}")
                continue
            if not v:
                continue
            diff_en = (v.get("difficulty") or "medium").lower()
            if diff_en not in DIFF_MAP:
                diff_en = "medium"
            issues = qc_r1(v, seed)
            out.append({
                # Item ĐÚNG shape s1 của đối tác (chỉ 3 field) — merge được thẳng.
                "s1_item": {
                    "stem": v.get("stem"),
                    "options": v.get("options"),
                    "answer": v.get("answer"),
                },
                "do_kho": DIFF_MAP[diff_en],        # nhãn cho quota 3/5/2 của đối tác
                "difficulty_en": diff_en,
                "explanation": v.get("explanation"),
                "nguon_seed": f"{seed['ma_de']}#Q{seed['q']}",
                "seed_stem": seed["stem"],
                "qc_issues": issues,
                "qc_ok": len(issues) == 0,
            })
    return out


def export_bundle(items: list) -> dict:
    """Gói bàn giao (JSON) cho sếp: item shape s1 + metadata truy vết + độ khó."""
    return {
        "skill": "reading_s1",
        "spec": "SPEC-FACTORY-001",
        "note": "Biến thể R1 paraphrase từ bank_raw.json của đối tác; CẦN GV tiếng Anh duyệt+ký trước khi dùng.",
        "count": len(items),
        "count_qc_ok": sum(1 for it in items if it["qc_ok"]),
        "items": items,
    }


def review_sheet(items: list) -> str:
    """Bảng GV soát/ký (Markdown): câu gốc | biến thể | đáp án | độ khó | QC | ô ký."""
    header = (
        "| # | Nguồn seed | Câu gốc (seed) | Biến thể (stem) | Đáp án | Độ khó | QC | GV duyệt (Đạt/Không + chữ ký) |\n"
        "|---|---|---|---|---|---|---|---|"
    )
    rows = [header]
    for i, it in enumerate(items, 1):
        s = it["s1_item"]
        qc = "OK" if it["qc_ok"] else "⚠ " + "; ".join(it["qc_issues"])
        seed_stem = (it["seed_stem"] or "").replace("|", "/")[:55]
        var_stem = (s.get("stem") or "").replace("|", "/")[:70]
        rows.append(
            f"| {i} | {it['nguon_seed']} | {seed_stem} | {var_stem} | {s.get('answer')} | {it['do_kho']} | {qc} |  |"
        )
    return "\n".join(rows)
