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
import hashlib
import json
import logging
import os
import random
import re
import time
import unicodedata
import wave
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


def build_r1_variants(seeds: list, per_seed: int = 1, generator=None, dup_threshold: float = 0.85) -> list:
    """Sinh biến thể R1 cho danh sách seed. Mỗi item ra: shape s1 của đối tác + metadata.
    Khử near-dup stem toàn-lô bằng jaccard (nhất quán các build_*_variants khác — gắn nhãn, không xoá)."""
    use_mock = generator is None or getattr(generator, "client", None) is None
    accepted_stems = []
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
            stem = str(v.get("stem") or "")
            for prev in accepted_stems:
                if _jaccard(stem, prev) >= dup_threshold:
                    issues.append("near-duplicate stem (trùng lặp gần với câu khác trong lô)")
                    break
            accepted_stems.append(stem)
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


# ======================================================================
# SLICE P3-NÓI (Speaking) — SPEC-FACTORY-002
# ----------------------------------------------------------------------
# Mở rộng ngân hàng Nói của đối tác (pool_speak.json). Đơn vị = THẺ NÓI: đề B1 chỉ đổi
# `part2_topic` (part1/part3 chuẩn hoá, cố định) → biến thể = part2_topic MỚI CÙNG domain
# grounded từ thẻ thật (không bịa chủ đề). Song song pattern R1 ở trên. Xuất ĐÚNG shape
# pool_speak (7 field) + metadata sibling (độ khó/nguồn/QC) — KHÔNG nhét độ khó vào card
# vì schema pool_speak không có field độ khó (giữ round-trip qua build_db của đối tác).

# 14 chủ đề B1 (sở hữu cục bộ ở module này để KHÔNG phụ thuộc b1_question_gen/DB).
DOMAINS_14 = [
    "Bản thân",
    "Nhà cửa-gia đình-môi trường",
    "Cuộc sống hằng ngày",
    "Vui chơi-giải trí",
    "Đi lại-du lịch",
    "Mối quan hệ",
    "Sức khỏe",
    "Giáo dục",
    "Mua bán",
    "Thực phẩm-đồ uống",
    "Các dịch vụ",
    "Địa điểm-địa danh",
    "Ngôn ngữ",
    "Thời tiết",
]

# 7 field của một thẻ pool_speak (bảo toàn round-trip khi merge vào ngân hàng đối tác).
SPEAK_CARD_FIELDS = ["code", "src_code", "set_file", "part2_topic", "domain_guess", "part1", "part3"]


def _norm_topic(text) -> str:
    """Chuẩn hoá chuỗi topic để so trùng/near-dup: strip, lower, gộp khoảng trắng."""
    return " ".join(str(text or "").strip().lower().split())


def _jaccard(a: str, b: str) -> float:
    """Jaccard token-set giữa 2 topic (đã chuẩn hoá), 0..1. Rỗng bất kỳ vế → 0.0."""
    ta, tb = set(_norm_topic(a).split()), set(_norm_topic(b).split())
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def _norm_domain(text) -> str:
    """Chuẩn hoá domain để khớp 14 chủ đề bất kể lệch dấu (NFC), hoa/thường, hyphen↔space, khoảng trắng.

    domain_guess trong pool_speak thật của đối tác có thể lệch định dạng ('Vui chơi - giải trí',
    dạng NFD từ .docx) — không được báo QC oan cho thẻ grounded."""
    t = unicodedata.normalize("NFC", str(text or "")).replace("-", " ")
    return " ".join(t.strip().lower().split())


# Tập 14 chủ đề đã chuẩn hoá — dùng cho qc_speak (khoan dung định dạng, vẫn bắt domain bịa).
_DOMAINS_14_NORM = {_norm_domain(d) for d in DOMAINS_14}


def load_speak_seeds(pool) -> list:
    """Trích thẻ Nói THẬT từ pool_speak.json của đối tác thành danh sách seed sạch.

    pool_speak là DICT 30 thẻ (keyed by code 'SB1.26xx') — KHÁC bank_raw của R1 là LIST →
    duyệt .values() (chấp nhận cả list để phòng thủ)."""
    records = pool.values() if isinstance(pool, dict) else pool
    seeds = []
    for rec in records:
        if not isinstance(rec, dict):
            continue
        code = rec.get("code") or "?"
        part2_topic = (rec.get("part2_topic") or "").strip()
        part1 = rec.get("part1")
        part3 = rec.get("part3")
        if part2_topic and part1 and part3:
            seeds.append({
                "code": code,
                "src_code": rec.get("src_code") or code,
                "set_file": rec.get("set_file"),
                "part2_topic": part2_topic,
                "domain_guess": rec.get("domain_guess"),
                "part1": part1,
                "part3": part3,
            })
    return seeds


def _mock_speak_variant(seed: dict, idx: int) -> dict:
    """Biến thể MOCK tất định (không gọi mạng) — stand-in cho test (song song _mock_variant R1).

    Sinh part2_topic MỚI: khác nguyên văn seed + KHÁC NHAU theo idx VÀ theo seed (nhúng chính
    part2_topic của seed) → hai seed CÙNG domain vẫn cho topic khác nhau, cổng khử near-dup không
    loại nhầm. GIỮ domain của seed (grounded). Chất lượng thật do Gemini lo."""
    diff = ["easy", "medium", "hard"][idx % 3]
    domain = seed.get("domain_guess") or "chủ đề B1"
    code = seed.get("code") or "?"
    base = (seed.get("part2_topic") or "").strip()
    templates = [
        f"{base} — kể một trải nghiệm cá nhân",
        f"{base} — mô tả một tình huống khác",
        f"{base} — trình bày quan điểm của bạn",
    ]
    return {
        "part2_topic": f"{templates[idx % len(templates)]} (mẫu {code}/{idx + 1}).",
        "difficulty": diff,
        "explanation": f"Biến thể part2_topic mock từ {code} (giữ domain {domain}).",
    }


def _real_speak_variant(generator, seed: dict, idx: int) -> Optional[dict]:
    """Sinh biến thể THẬT qua Gemini: part2_topic MỚI cùng domain, không sao chép seed.

    KHÔNG hỏi Gemini về domain — domain giữ nguyên của seed (chống 'bịa chủ đề')."""
    domain = seed.get("domain_guess")
    system = (
        "You are a VSTEP B1 (CEFR B1) speaking-test item writer. Given a Part 2 cue-card "
        "topic, write ONE NEW, parallel Part 2 topic on the SAME domain and SAME B1 difficulty "
        "— a FRESH cue (NOT a copy or trivial reword). It must be a single Part 2 speaking topic "
        "the candidate talks about for ~2 minutes. Assess difficulty vs the CEFR B1 wordlist "
        "(easy = core A2-B1, medium = upper-B1, hard = B2+/abstract). Return ONLY JSON: "
        "{\"part2_topic\": str, \"difficulty\": \"easy|medium|hard\", \"explanation\": str}."
    )
    user = (
        f"SEED Part 2 topic (write a NEW one on the SAME domain, do NOT copy it):\n"
        f"Domain: {domain}\n"
        f"Seed part2_topic: {seed['part2_topic']}\n"
        f"Generate parallel variant #{idx + 1}."
    )
    raw = generator._call_gemini(system, user)
    data = _loads_lenient(raw)
    return data if isinstance(data, dict) else None


def qc_speak(card: dict, seed: dict) -> list:
    """Cổng QC cho thẻ Nói (bám cổng của đối tác). Trả danh sách lỗi (rỗng = đạt)."""
    issues = []
    part2_topic = (card.get("part2_topic") or "").strip()
    if not part2_topic:
        issues.append("part2_topic rỗng")
    elif _norm_topic(part2_topic) == _norm_topic(seed.get("part2_topic")):
        issues.append("trùng nguyên văn seed (bản quyền)")
    if _norm_domain(card.get("domain_guess")) not in _DOMAINS_14_NORM:
        issues.append(f"domain_guess ngoài 14 chủ đề B1 ({card.get('domain_guess')!r})")
    if not (card.get("part1") and str(card.get("part1")).strip()):
        issues.append("thiếu part1")
    if not (card.get("part3") and str(card.get("part3")).strip()):
        issues.append("thiếu part3")
    missing = [k for k in SPEAK_CARD_FIELDS if k not in card]
    if missing:
        issues.append(f"thiếu field schema pool_speak: {missing}")
    return issues


def _next_speak_code(seed: dict, idx: int, used: set) -> str:
    """Cấp code MỚI cho thẻ sinh: dải SB1.90-* (tách khỏi SB1.26xx thật của đối tác).

    NHÚNG code seed + idx → code ỔN ĐỊNH & DUY NHẤT qua nhiều lô (chạy lại cùng pool ra cùng code,
    tránh va chạm khi merge nhiều lô vào pool_speak dạng dict); đồng thời truy vết thẳng về seed.
    Prefix '90-' báo hiệu 'câu MỞ RỘNG chờ GV ký' — đối tác dễ lọc/renumber khi merge."""
    src_num = str(seed.get("code") or "seed").split(".")[-1]
    base = f"SB1.90-{src_num}-{idx + 1}"
    code, n = base, 1
    while code in used:   # phòng thủ va chạm (rất hiếm) — thêm hậu tố
        n += 1
        code = f"{base}.{n}"
    used.add(code)
    return code


def build_speak_variants(seeds: list, per_seed: int = 1, generator=None, dup_threshold: float = 0.85) -> list:
    """Sinh biến thể thẻ Nói cho danh sách seed (song song build_r1_variants).

    Mỗi item ra: card shape pool_speak THUẦN (7 field) + metadata sibling (độ khó/nguồn/QC).
    Khử near-dup part2_topic toàn-lô bằng jaccard (KHÔNG im lặng xoá — gắn issue cho GV thấy)."""
    use_mock = generator is None or getattr(generator, "client", None) is None
    used_codes = {s["code"] for s in seeds}   # không đụng code seed thật của đối tác
    accepted_topics = []                       # part2_topic đã nhận (khử near-dup toàn-lô)
    out = []
    for seed in seeds:
        for i in range(per_seed):
            try:
                v = _mock_speak_variant(seed, i) if use_mock else _real_speak_variant(generator, seed, i)
            except Exception as e:  # sinh lỗi 1 thẻ không làm hỏng cả lô
                logger.warning(f"Sinh thẻ Nói lỗi seed {seed['code']}#{i}: {e}")
                continue
            if not v:
                continue
            diff_en = (v.get("difficulty") or "medium").lower()
            if diff_en not in DIFF_MAP:
                diff_en = "medium"
            part2_topic = (v.get("part2_topic") or "").strip()
            card = {
                # Thẻ ĐÚNG shape pool_speak của đối tác (7 field) — merge được thẳng.
                "code": _next_speak_code(seed, i, used_codes),   # code MỚI dải SB1.90-* (ổn định, truy vết)
                "src_code": seed["code"],                  # truy vết grounded về seed thật
                "set_file": seed.get("set_file"),
                "part2_topic": part2_topic,
                "domain_guess": seed.get("domain_guess"),  # GIỮ domain seed (không bịa chủ đề)
                "part1": seed["part1"],                    # cố định (chuẩn hoá từ seed)
                "part3": seed["part3"],                    # cố định (chuẩn hoá từ seed)
            }
            issues = qc_speak(card, seed)
            for prev in accepted_topics:
                if _jaccard(part2_topic, prev) >= dup_threshold:
                    issues.append("near-duplicate part2_topic (trùng lặp gần với thẻ khác trong lô)")
                    break
            accepted_topics.append(part2_topic)
            out.append({
                "speak_card": card,
                "do_kho": DIFF_MAP[diff_en],       # nhãn cho quota 3/5/2 (tham chiếu — mỗi đề 1 phần Nói)
                "difficulty_en": diff_en,
                "explanation": v.get("explanation"),
                "nguon_seed": seed["code"],
                "seed_part2_topic": seed["part2_topic"],
                "domain": card["domain_guess"],
                "qc_issues": issues,
                "qc_ok": len(issues) == 0,
            })
    return out


def export_speak_bundle(items: list) -> dict:
    """Gói bàn giao (JSON) cho đối tác: thẻ shape pool_speak + metadata truy vết + độ khó."""
    return {
        "skill": "speaking",
        "spec": "SPEC-FACTORY-002",
        "note": (
            "Thẻ part2_topic Nói paraphrase từ pool_speak.json của đối tác (GIỮ part1/part3 chuẩn, "
            "chỉ đổi part2_topic CÙNG domain); code SB1.90-<seed>-<n> là TẠM (đối tác renumber khi "
            "merge). CẦN GV tiếng Anh duyệt+ký trước khi dùng."
        ),
        "count": len(items),
        "count_qc_ok": sum(1 for it in items if it["qc_ok"]),
        "items": items,
    }


def speak_review_sheet(items: list) -> str:
    """Bảng GV soát/ký (Markdown) cho Nói: seed | domain | part2_topic gốc | mới | độ khó | QC | ô ký."""
    header = (
        "| # | Nguồn seed | Domain | part2_topic gốc (seed) | part2_topic MỚI | Độ khó | QC | GV duyệt (Đạt/Không + chữ ký) |\n"
        "|---|---|---|---|---|---|---|---|"
    )
    rows = [header]
    for i, it in enumerate(items, 1):
        c = it["speak_card"]
        qc = "OK" if it["qc_ok"] else "⚠ " + "; ".join(it["qc_issues"])
        seed_topic = (it["seed_part2_topic"] or "").replace("|", "/")[:45]
        new_topic = (c.get("part2_topic") or "").replace("|", "/")[:60]
        rows.append(
            f"| {i} | {it['nguon_seed']} | {it['domain']} | {seed_topic} | {new_topic} | {it['do_kho']} | {qc} |  |"
        )
    return "\n".join(rows)


# ======================================================================
# SLICE R4 (Cloze điền-từ-hộp-từ, Đọc phần 4) — SPEC-FACTORY-003
# ----------------------------------------------------------------------
# Mở rộng ngân hàng cloze R4 của đối tác (khóa `s4` trong bank_raw.json). Cấu trúc THẬT:
#   s4_raw = list block {kind:"p"|"tbl", text}: 2 block "p" (tiêu đề + hướng dẫn) → 1 block
#   "tbl" = HỘP TỪ (các từ cách nhau space) → các block "p" = passage với chỗ trống "(21)…".
#   s4_answers == key_cloze = dict {"21":"fact", ..., "30":"must"} (10 chỗ, khóa 21-30).
# Đáp án đối tác có thể VIẾT HOA (vd "Both") trong khi hộp từ viết thường ("both") → cổng
# kiểm-hộp-từ (kiem_hop_tu) so KHÔNG phân biệt hoa/thường. Song song pattern R1/Nói ở trên.

R4_HEADER = "Section 4 Questions 21-30 (10 points)"
R4_INSTRUCTION = "Read the text below and fill each of the blanks with ONE suitable word from the box."
R4_BLANK_KEYS = [str(n) for n in range(21, 31)]   # 10 chỗ trống, đánh số 21..30
# "(21)" THEO SAU bởi ô trống (___ / … / ...) → chỉ tính chỗ trống thật, bỏ qua số trong ngoặc
# như năm "(1980)" (tránh báo thừa-blank oan).
_BLANK_RE = re.compile(r"\(\s*(\d+)\s*\)\s*(?:_{2,}|…+|\.{3,})")


def _norm_word(w) -> str:
    """Chuẩn hoá 1 từ để so khớp hộp từ (không phân biệt hoa/thường + gọn khoảng trắng)."""
    return " ".join(str(w or "").strip().lower().split())


def load_r4_seeds(bank: list) -> list:
    """Trích cloze R4 (khóa `s4`) từ bank_raw.json của đối tác: hộp từ + passage + đáp án."""
    seeds = []
    for rec in bank:
        ma_de = rec.get("ma_de") or rec.get("file") or "?"
        s4_raw = rec.get("s4_raw")
        answers = rec.get("s4_answers") or rec.get("key_cloze") or {}
        if not isinstance(s4_raw, list) or not answers:
            continue
        tbl_idx = next((i for i, b in enumerate(s4_raw)
                        if isinstance(b, dict) and b.get("kind") == "tbl"), None)
        if tbl_idx is None:
            continue
        box = str(s4_raw[tbl_idx].get("text") or "").split()   # hộp từ = block tbl
        passage_blocks = [str(b.get("text")).strip() for b in s4_raw[tbl_idx + 1:]
                          if isinstance(b, dict) and b.get("kind") == "p"
                          and str(b.get("text") or "").strip()]
        passage = "\n".join(passage_blocks)                    # tiêu đề + passage
        if box and passage and answers:
            seeds.append({
                "ma_de": ma_de, "box": box, "passage": passage,
                "answers": {str(k): v for k, v in answers.items()},
            })
    return seeds


def _mock_r4_variant(seed: dict, idx: int) -> dict:
    """Biến thể MOCK tất định (không gọi mạng) — stand-in cho test (song song _mock_variant R1).

    Dùng lại hộp từ + đáp án của seed (đảm bảo đáp án ∈ hộp từ), sinh passage MỚI có đủ 10 chỗ
    trống (21)..(30), khác nguyên văn seed. Chất lượng thật do Gemini lo."""
    diff = ["easy", "medium", "hard"][idx % 3]
    box = list(seed.get("box") or [])
    seed_ans = {str(k): v for k, v in (seed.get("answers") or {}).items()}
    answers = {n: seed_ans[n] for n in R4_BLANK_KEYS if n in seed_ans}
    # bù đủ 10 chỗ bằng từ trong hộp (hiếm khi seed thiếu) — giữ đáp án ∈ hộp
    used = {_norm_word(v) for v in answers.values()}
    spare = [w for w in box if _norm_word(w) not in used]
    for n in R4_BLANK_KEYS:
        if n not in answers and spare:
            answers[n] = spare.pop(0)
    for v in answers.values():   # đảm bảo hộp chứa mọi đáp án
        if _norm_word(v) not in {_norm_word(w) for w in box}:
            box.append(v)
    tag = seed.get("ma_de") or "seed"
    # token DUY NHẤT theo (seed, idx, chỗ) trong MỖI câu → 2 seed / 2 idx (kể cả cùng hộp từ) đều
    # khác set tokens → cổng khử near-dup KHÔNG loại nhầm biến thể mock hợp lệ (bài học slice Nói).
    sents = [f"Câu {tag}-{idx + 1}-{n} ({n}) ______." for n in R4_BLANK_KEYS]
    passage = f"Cloze mẫu {tag} phiên {idx + 1}\n" + " ".join(sents)
    return {"title": f"Cloze mock {tag}/{idx + 1}", "passage": passage, "word_box": box,
            "answers": answers, "difficulty": diff, "explanation": f"Cloze mock từ {tag}."}


def _real_r4_variant(generator, seed: dict, idx: int) -> Optional[dict]:
    """Sinh cloze R4 THẬT qua Gemini: passage MỚI + hộp từ, đáp án ∈ hộp, không sao chép seed."""
    system = (
        "You are a VSTEP B1 (CEFR B1) English item writer. Create ONE NEW gap-fill cloze task "
        "(Reading Part 4 style): a SHORT original passage (~120-160 words) on a fresh everyday "
        "topic with EXACTLY 10 numbered blanks written as '(21) ______' through '(30) ______'. "
        "Provide a WORD BOX of 15 single lowercase words: the 10 correct answers PLUS 5 plausible "
        "distractors; each answer fills exactly one blank and EVERY answer MUST appear in the box. "
        "Do NOT copy the seed passage. Return ONLY JSON: {\"title\": str, \"passage\": "
        "\"...text with (21)..(30) blanks...\", \"word_box\": [15 words], "
        "\"answers\": {\"21\": word, ..., \"30\": word}, \"difficulty\": \"easy|medium|hard\", "
        "\"explanation\": str}."
    )
    user = (
        f"SEED cloze (write a NEW one at the SAME B1 level, do NOT copy it):\n"
        f"Word box: {' '.join(seed['box'])}\n"
        f"Passage: {seed['passage'][:900]}\n"
        f"Answers: {json.dumps(seed['answers'], ensure_ascii=False)}\n"
        f"Generate parallel variant #{idx + 1}."
    )
    raw = generator._call_gemini(system, user)
    data = _loads_lenient(raw)
    return data if isinstance(data, dict) else None


def qc_r4(variant: dict, seed: dict) -> list:
    """Cổng QC cho cloze R4 (bám cổng kiem_hop_tu của đối tác). Trả danh sách lỗi (rỗng = đạt)."""
    issues = []
    passage = str(variant.get("passage") or "").strip()
    box = variant.get("word_box") or []
    answers = {str(k): v for k, v in (variant.get("answers") or {}).items()}
    if not passage:
        issues.append("passage rỗng")
    if not isinstance(box, list) or len(box) < 10:
        issues.append(f"hộp từ phải ≥10 từ (đang {len(box) if isinstance(box, list) else 'N/A'})")
    if set(answers.keys()) != set(R4_BLANK_KEYS):
        issues.append(f"đáp án phải đủ 10 chỗ 21-30 (đang {sorted(answers.keys())})")
    found = _BLANK_RE.findall(passage)   # dùng list (KHÔNG set) để bắt cả lặp/thừa chỗ trống
    if sorted(found, key=lambda s: int(s)) != R4_BLANK_KEYS:
        issues.append(f"passage phải đúng 10 chỗ trống 21-30, không thiếu/lặp/thừa (đang {sorted(found, key=lambda s: int(s))})")
    box_norm = {_norm_word(w) for w in box} if isinstance(box, list) else set()
    for k, v in answers.items():   # CỔNG kiem_hop_tu: đáp án ∈ hộp từ (không phân biệt hoa/thường)
        if _norm_word(v) not in box_norm:
            issues.append(f"đáp án ({k})={v!r} KHÔNG có trong hộp từ")
    vals = [_norm_word(v) for v in answers.values()]
    if len(set(vals)) < len(vals):
        issues.append("có đáp án lặp lại (mỗi từ trong hộp chỉ dùng 1 lần)")
    if passage and passage == str(seed.get("passage") or "").strip():
        issues.append("trùng nguyên văn passage seed (bản quyền)")
    return issues


def _assemble_s4_raw(title, passage, word_box: list) -> list:
    """Dựng lại block list s4_raw đúng cấu trúc đối tác (tiêu đề · hướng dẫn · hộp từ · passage)."""
    blocks = [
        {"kind": "p", "text": R4_HEADER},
        {"kind": "p", "text": R4_INSTRUCTION},
        {"kind": "tbl", "text": " ".join(str(w) for w in word_box)},
    ]
    if title:
        blocks.append({"kind": "p", "text": str(title)})
    for para in str(passage).split("\n"):
        if para.strip():
            blocks.append({"kind": "p", "text": para.strip()})
    return blocks


def build_r4_variants(seeds: list, per_seed: int = 1, generator=None, dup_threshold: float = 0.85) -> list:
    """Sinh biến thể cloze R4 cho danh sách seed (song song build_r1_variants).

    Mỗi item ra: `s4_item` = {s4_raw(block list) + s4_answers + key_cloze} đúng shape đối tác +
    metadata sibling (độ khó/nguồn/QC). Phát hiện+gắn nhãn near-dup passage (KHÔNG im lặng xoá)."""
    use_mock = generator is None or getattr(generator, "client", None) is None
    accepted_passages = []
    out = []
    for seed in seeds:
        for i in range(per_seed):
            try:
                v = _mock_r4_variant(seed, i) if use_mock else _real_r4_variant(generator, seed, i)
            except Exception as e:   # sinh lỗi 1 cloze không làm hỏng cả lô
                logger.warning(f"Sinh cloze R4 lỗi seed {seed['ma_de']}#{i}: {e}")
                continue
            if not v:
                continue
            diff_en = (v.get("difficulty") or "medium").lower()
            if diff_en not in DIFF_MAP:
                diff_en = "medium"
            passage = str(v.get("passage") or "").strip()
            box = [str(w) for w in (v.get("word_box") or [])]        # ép str: Gemini có thể trả số → tránh crash join cả lô
            answers = {str(k): str(val) for k, val in (v.get("answers") or {}).items()}
            issues = qc_r4({"passage": passage, "word_box": box, "answers": answers}, seed)
            for prev in accepted_passages:
                if _jaccard(passage, prev) >= dup_threshold:
                    issues.append("near-duplicate passage (trùng lặp gần với cloze khác trong lô)")
                    break
            accepted_passages.append(passage)
            out.append({
                # s4 ĐÚNG shape đối tác — merge được vào bank_raw (s4_raw + s4_answers + key_cloze).
                "s4_item": {
                    "s4_raw": _assemble_s4_raw(v.get("title"), passage, box),
                    "s4_answers": answers,
                    "key_cloze": answers,
                },
                "do_kho": DIFF_MAP[diff_en],
                "difficulty_en": diff_en,
                "explanation": v.get("explanation"),
                "nguon_seed": seed["ma_de"],
                "seed_passage": seed["passage"],
                "word_box": box,
                "answers": answers,
                "qc_issues": issues,
                "qc_ok": len(issues) == 0,
            })
    return out


def export_r4_bundle(items: list) -> dict:
    """Gói bàn giao (JSON) cho đối tác: cloze shape s4 + metadata truy vết + độ khó."""
    return {
        "skill": "reading_s4_cloze",
        "spec": "SPEC-FACTORY-003",
        "note": (
            "Cloze hộp-từ R4 sinh từ bank_raw.json của đối tác (passage MỚI + hộp từ, đáp án ∈ hộp, "
            "không phân biệt hoa/thường); s4_item = s4_raw(blocks)+s4_answers+key_cloze để merge. "
            "CẦN GV tiếng Anh duyệt+ký trước khi dùng."
        ),
        "count": len(items),
        "count_qc_ok": sum(1 for it in items if it["qc_ok"]),
        "items": items,
    }


def r4_review_sheet(items: list) -> str:
    """Bảng GV soát/ký (Markdown) cho R4: seed | passage mới | hộp từ | đáp án | độ khó | QC | ô ký."""
    header = (
        "| # | Nguồn seed | Passage MỚI (rút gọn) | Hộp từ | Đáp án 21-30 | Độ khó | QC | GV duyệt (Đạt/Không + chữ ký) |\n"
        "|---|---|---|---|---|---|---|---|"
    )
    rows = [header]
    for i, it in enumerate(items, 1):
        qc = "OK" if it["qc_ok"] else "⚠ " + "; ".join(it["qc_issues"])
        ptext = " ".join(b["text"] for b in it["s4_item"]["s4_raw"]
                         if b["kind"] == "p").replace("|", "/")[:70]
        box = " ".join(str(w) for w in it["word_box"]).replace("|", "/")[:40]
        ans = "; ".join(f"{k}:{it['answers'][k]}" for k in sorted(it["answers"], key=int)).replace("|", "/")[:60]
        rows.append(
            f"| {i} | {it['nguon_seed']} | {ptext} | {box} | {ans} | {it['do_kho']} | {qc} |  |"
        )
    return "\n".join(rows)


# ======================================================================
# SLICE R2 (Đọc thông báo/biển báo — Đọc phần 2) — SPEC-FACTORY-004
# ----------------------------------------------------------------------
# Mở rộng ngân hàng R2 của đối tác (khóa `s2` trong bank_raw.json). Cấu trúc THẬT:
#   s2_raw = list block: 2 block "p" (tiêu đề + hướng dẫn) → 1 block "tbl" gộp CẢ 5 thông báo
#   (câu 11-15) + phương án dạng chuỗi: "11. <thông báo> A. <a> B. <b> C. <c> 12. <...> ...".
#   s2_answers = {"11":"A", ..., "15":"C"} (5 câu, ĐÁP ÁN 3 lựa chọn A/B/C). key_reading là key
#   GỘP cả Đọc 1-20 → lấy subset 11-15 nếu thiếu s2_answers.
# Đơn vị = MỘT thông báo (notice/sign/label/note/ad) + 3 phương án A/B/C. Song song pattern R1
# (khác: 3 phương án A/B/C, stem = thông báo). Parser ROBUST cho dữ liệu THẬT (best-effort):
#   - Tìm mốc câu 11-15 theo THỨ TỰ TĂNG, trái→phải → số 11-15 nằm TRONG thân thông báo ở câu SAU
#     không bị nhầm thành mốc (bắt được lỗi thật EB1.2605: "...at 12. C. Jane..." trong câu 15).
#   - Tách 3 phương án bằng cụm ' A. ' HỢP LỆ CUỐI (có ' B. '+' C. ' sau) → chịu ' A. ' trong thân
#     thông báo (vd 'grade A.', 'Dear A. Smith').
#   - Notice dạng ẢNH (text rỗng, s2_has_image ~18/30) TỰ bị loại vì không tách đủ 3 phương án.

R2_OPTION_KEYS = ["A", "B", "C"]
_R2_EXPECTED_NUMS = ["11", "12", "13", "14", "15"]


def _r2_split_options(body: str):
    """Tách 'body' = '<thông báo> A. <a> B. <b> C. <c>' → (notice, {A,B,C}) hoặc None.

    Dùng cụm ' A. ' hợp lệ CUỐI CÙNG (có ' B. ' và ' C. ' theo sau) làm mốc phương án A."""
    best = None
    for am in re.finditer(r"(?:(?<=\s)|^)A\.\s", body):
        tail = body[am.end():]
        om = re.match(r"(.*?)(?:(?<=\s)|^)B\.\s(.*?)(?:(?<=\s)|^)C\.\s(.+)$", tail, re.DOTALL)
        if om:
            best = (
                body[:am.start()].strip(),
                {"A": om.group(1).strip(), "B": om.group(2).strip(), "C": om.group(3).strip()},
            )
    return best


def load_r2_seeds(bank: list) -> list:
    """Trích thông báo R2 (khóa `s2`) từ bank_raw.json của đối tác: từng notice + 3 phương án + đáp án."""
    seeds = []
    for rec in bank:
        ma_de = rec.get("ma_de") or rec.get("file") or "?"
        s2_raw = rec.get("s2_raw")
        answers = rec.get("s2_answers") or {}
        if not answers:   # fallback: subset 11-15 của key_reading gộp
            kr = rec.get("key_reading") or {}
            answers = {k: kr[k] for k in _R2_EXPECTED_NUMS if k in kr}
        if not isinstance(s2_raw, list) or not answers:
            continue
        tbl_text = " ".join(str(b.get("text") or "") for b in s2_raw
                            if isinstance(b, dict) and b.get("kind") == "tbl").strip()
        if not tbl_text:
            continue
        nums = [n for n in _R2_EXPECTED_NUMS if answers.get(n) in R2_OPTION_KEYS]
        # định vị mốc từng câu theo thứ tự TĂNG, tìm trái→phải (bỏ qua số embedded ở câu sau)
        marks = []
        frm = 0
        for num in nums:
            mm = re.search(r"(?:(?<=\s)|^)" + num + r"\.\s", tbl_text[frm:])
            if not mm:
                continue
            start = frm + mm.start()
            marks.append((num, start))
            frm = frm + mm.end()
        parsed = 0
        for i, (num, start) in enumerate(marks):
            end = marks[i + 1][1] if i + 1 < len(marks) else len(tbl_text)
            block = tbl_text[start:end].strip()
            body = re.sub(r"^" + num + r"\.\s*", "", block).strip()
            split = _r2_split_options(body)
            if not split:
                continue
            notice, options = split
            if notice and answers.get(num) in R2_OPTION_KEYS:
                seeds.append({
                    "ma_de": ma_de, "num": num, "notice": notice,
                    "notice_raw": block, "options": options, "answer": answers[num],
                })
                parsed += 1
        if parsed != len(nums):
            logger.warning(f"R2 {ma_de}: tách được {parsed}/{len(nums)} thông báo (tbl s2 không chuẩn?).")
    return seeds


def _mock_r2_variant(seed: dict, idx: int) -> dict:
    """Biến thể MOCK tất định (không gọi mạng) — stand-in cho test (song song _mock_variant R1).

    Notice + 3 phương án MỚI, khác nguyên văn seed, token duy nhất theo (seed, idx) → không near-dup."""
    diff = ["easy", "medium", "hard"][idx % 3]
    ans = seed.get("answer") if seed.get("answer") in R2_OPTION_KEYS else "A"
    tag = f"{seed.get('ma_de')}#{seed.get('num')}"
    stem = f"THÔNG BÁO {tag} phiên {idx + 1}: Please follow notice {tag} rule {idx + 1}."
    options = {k: f"Diễn giải {k} của {tag}/{idx + 1}" for k in R2_OPTION_KEYS}
    return {"stem": stem, "options": options, "answer": ans, "difficulty": diff,
            "explanation": f"Biến thể thông báo từ {tag} (cùng dạng đọc-hiểu)."}


def _real_r2_variant(generator, seed: dict, idx: int) -> Optional[dict]:
    """Sinh thông báo R2 THẬT qua Gemini: notice MỚI cùng dạng + 3 phương án A/B/C, không copy seed."""
    system = (
        "You are a VSTEP B1 (CEFR B1) English item writer for Reading Part 2 (short public texts: "
        "signs, labels, notices, notes, adverts). Given a seed notice with three interpretation "
        "options, write ONE NEW, parallel item of the SAME text-type and SAME B1 level: a FRESH "
        "short realistic notice (NOT a copy) plus exactly 3 options A, B, C where exactly ONE is "
        "the correct interpretation and the other two are plausible misreadings. Return ONLY JSON: "
        "{\"stem\": \"<the notice text>\", \"options\": {\"A\": str, \"B\": str, \"C\": str}, "
        "\"answer\": \"A|B|C\", \"difficulty\": \"easy|medium|hard\", \"explanation\": str}."
    )
    seed_opts = seed.get("options") or {}
    user = (
        f"SEED notice (write a NEW one of the same text-type, do NOT copy it):\n"
        f"Notice: {seed.get('notice')}\n"
        f"A. {seed_opts.get('A', '')}\nB. {seed_opts.get('B', '')}\nC. {seed_opts.get('C', '')}\n"
        f"Correct answer key: {seed['answer']}\n"
        f"Generate parallel variant #{idx + 1}."
    )
    raw = generator._call_gemini(system, user)
    data = _loads_lenient(raw)
    return data if isinstance(data, dict) else None


def qc_r2(variant: dict, seed: dict) -> list:
    """Cổng QC cho thông báo R2 (bám cổng của đối tác, 3 phương án). Trả danh sách lỗi (rỗng = đạt)."""
    issues = []
    stem = (variant.get("stem") or "").strip()
    options = variant.get("options") or {}
    answer = variant.get("answer")
    if not stem:
        issues.append("stem (thông báo) rỗng")
    if sorted(options.keys()) != R2_OPTION_KEYS:
        issues.append(f"options phải đủ A,B,C (đang {sorted(options.keys())})")
    else:
        vals = [str(v).strip().lower() for v in options.values()]
        if len(set(vals)) < len(vals):
            issues.append("có phương án trùng nội dung")
        if any(not str(v).strip() for v in options.values()):
            issues.append("có phương án rỗng")
    if answer not in options:
        issues.append("answer không thuộc options")
    if stem and _norm_topic(stem) == _norm_topic(seed.get("notice")):
        issues.append("trùng nguyên văn seed (bản quyền)")
    return issues


def build_r2_variants(seeds: list, per_seed: int = 1, generator=None, dup_threshold: float = 0.85) -> list:
    """Sinh biến thể thông báo R2 cho danh sách seed (song song build_r1_variants, 3 phương án).

    Mỗi item ra: `s2_item` {stem, options{A,B,C}, answer} (clean, D2 Option (a) — đối tác render từ
    JSON) + `s2_raw_fragment` (chuỗi "NN. stem A. .. B. .. C. ..") tiện merge vào tbl s2 + metadata.
    Phát hiện + gắn nhãn near-dup stem toàn-lô (KHÔNG im lặng xoá)."""
    use_mock = generator is None or getattr(generator, "client", None) is None
    accepted_stems = []
    out = []
    for seed in seeds:
        for i in range(per_seed):
            try:
                v = _mock_r2_variant(seed, i) if use_mock else _real_r2_variant(generator, seed, i)
            except Exception as e:   # sinh lỗi 1 thông báo không làm hỏng cả lô
                logger.warning(f"Sinh thông báo R2 lỗi seed {seed['ma_de']}#{seed.get('num')}#{i}: {e}")
                continue
            if not v:
                continue
            diff_en = (v.get("difficulty") or "medium").lower()
            if diff_en not in DIFF_MAP:
                diff_en = "medium"
            stem = str(v.get("stem") or "").strip()
            options = {k: str(val) for k, val in (v.get("options") or {}).items()}
            answer = v.get("answer")
            issues = qc_r2({"stem": stem, "options": options, "answer": answer}, seed)
            for prev in accepted_stems:
                if _jaccard(stem, prev) >= dup_threshold:
                    issues.append("near-duplicate stem (trùng lặp gần với thông báo khác trong lô)")
                    break
            accepted_stems.append(stem)
            frag_opts = " ".join(f"{k}. {options.get(k, '')}" for k in R2_OPTION_KEYS)
            out.append({
                # Clean per-notice (D2 Option a — đối tác render từ JSON); s1-style nhưng 3 phương án.
                "s2_item": {"stem": stem, "options": options, "answer": answer},
                "s2_raw_fragment": f"{seed.get('num', '11')}. {stem} {frag_opts}".strip(),
                "do_kho": DIFF_MAP[diff_en],
                "difficulty_en": diff_en,
                "explanation": v.get("explanation"),
                "nguon_seed": f"{seed['ma_de']}#{seed.get('num')}",
                "seed_notice": seed.get("notice"),
                "qc_issues": issues,
                "qc_ok": len(issues) == 0,
            })
    return out


def export_r2_bundle(items: list) -> dict:
    """Gói bàn giao (JSON) cho đối tác: thông báo R2 (3 phương án) + metadata truy vết + độ khó."""
    return {
        "skill": "reading_s2_notice",
        "spec": "SPEC-FACTORY-004",
        "note": (
            "Thông báo/biển báo R2 (3 phương án A/B/C) paraphrase từ bank_raw.json của đối tác; "
            "s2_item {stem, options{A-C}, answer} clean + s2_raw_fragment tiện merge vào tbl s2. "
            "Chỉ phần TEXT (thông báo dạng ảnh s2_has_image ngoài phạm vi). CẦN GV tiếng Anh duyệt+ký."
        ),
        "count": len(items),
        "count_qc_ok": sum(1 for it in items if it["qc_ok"]),
        "items": items,
    }


def r2_review_sheet(items: list) -> str:
    """Bảng GV soát/ký (Markdown) cho R2: seed | thông báo gốc | thông báo mới | đáp án | độ khó | QC | ô ký."""
    header = (
        "| # | Nguồn seed | Thông báo gốc (seed) | Thông báo MỚI (stem) | Đáp án | Độ khó | QC | GV duyệt (Đạt/Không + chữ ký) |\n"
        "|---|---|---|---|---|---|---|---|"
    )
    rows = [header]
    for i, it in enumerate(items, 1):
        s = it["s2_item"]
        qc = "OK" if it["qc_ok"] else "⚠ " + "; ".join(it["qc_issues"])
        seed_notice = (it["seed_notice"] or "").replace("|", "/")[:50]
        new_stem = (s.get("stem") or "").replace("|", "/")[:60]
        rows.append(
            f"| {i} | {it['nguon_seed']} | {seed_notice} | {new_stem} | {s.get('answer')} | {it['do_kho']} | {qc} |  |"
        )
    return "\n".join(rows)


# ======================================================================
# SLICE R3 (Đọc-hiểu đoạn văn — Đọc phần 3) — SPEC-FACTORY-005
# ----------------------------------------------------------------------
# Mở rộng ngân hàng R3 của đối tác (khóa `s3` trong bank_raw.json). Cấu trúc THẬT:
#   s3_raw = list block "p": 2 block tiêu đề/hướng dẫn → các block PASSAGE (đoạn văn, nhiều p) →
#   rồi từng CÂU HỎI: 1 block "16. <stem>" + 4 block option "A. .." "B. .." "C. .." "D. ..",
#   lặp cho câu 16-20. s3_answers = {"16":"D", ..., "20":"C"} (5 câu, 4 lựa chọn A-D).
# Đơn vị = CẢ NHÓM (1 đoạn văn + 5 câu hỏi hiểu). Biến thể = đoạn văn MỚI cùng chủ đề/độ khó +
# 5 câu hỏi hiểu MỚI (4 lựa chọn). ĐÂY LÀ SLICE NGỮ-NGHĨA-NẶNG → GV BẮT BUỘC soát kỹ đáp án.

R3_Q_NUMS = ["16", "17", "18", "19", "20"]
R3_OPTION_KEYS = ["A", "B", "C", "D"]
# (?!\d) sau dấu chấm → KHÔNG nhầm số thập phân trong passage ("16.2 million tonnes") thành câu hỏi.
_R3_QSTEM_RE = re.compile(r"^(1[6-9]|20)\.(?!\d)\s*(.*)$", re.DOTALL)
_R3_OPT_RE = re.compile(r"^([A-D])\.\s*(.*)$", re.DOTALL)


def load_r3_seeds(bank: list) -> list:
    """Trích nhóm đọc-hiểu R3 (khóa `s3`) từ bank_raw.json của đối tác: đoạn văn + câu hỏi + đáp án."""
    seeds = []
    for rec in bank:
        ma_de = rec.get("ma_de") or rec.get("file") or "?"
        s3_raw = rec.get("s3_raw")
        answers = rec.get("s3_answers") or {}
        if not answers:   # fallback: subset 16-20 của key_reading gộp
            kr = rec.get("key_reading") or {}
            answers = {k: kr[k] for k in R3_Q_NUMS if k in kr}
        if not isinstance(s3_raw, list) or not answers:
            continue
        blocks = [str(b.get("text") or "").strip() for b in s3_raw
                  if isinstance(b, dict) and b.get("kind") == "p"]
        q_positions = [i for i, tx in enumerate(blocks) if _R3_QSTEM_RE.match(tx)]
        if not q_positions:
            continue
        # đoạn văn = block không rỗng TRƯỚC câu hỏi đầu, bỏ tiêu đề/hướng dẫn
        passage_blocks = [tx for tx in blocks[:q_positions[0]]
                          if tx and not tx.startswith("Section 3") and not tx.startswith("Read the text")]
        passage = "\n".join(passage_blocks)
        questions = []
        for qi in q_positions:
            qm = _R3_QSTEM_RE.match(blocks[qi])
            num, stem = qm.group(1), qm.group(2).strip()
            opts = {}
            j = qi + 1
            while j < len(blocks):
                if not blocks[j]:      # bỏ block rỗng
                    j += 1
                    continue
                om = _R3_OPT_RE.match(blocks[j])
                if not om:             # gặp câu hỏi kế / block khác → hết options
                    break
                opts[om.group(1)] = om.group(2).strip()
                j += 1
            ans = answers.get(num)
            if stem and sorted(opts.keys()) == R3_OPTION_KEYS and ans in R3_OPTION_KEYS:
                questions.append({"num": num, "stem": stem, "options": opts, "answer": ans})
        if len(questions) != len(answers):   # cảnh báo (như R2) nếu tách hụt so với số đáp án
            logger.warning(f"R3 {ma_de}: tách được {len(questions)}/{len(answers)} câu hỏi (s3_raw không chuẩn?).")
        if passage and questions:
            seeds.append({"ma_de": ma_de, "passage": passage, "questions": questions})
    return seeds


def _mock_r3_variant(seed: dict, idx: int) -> dict:
    """Biến thể MOCK tất định (không gọi mạng) — stand-in cho test (song song _mock_variant R1).

    Đoạn văn + N câu hỏi (N = số câu của seed) MỚI, token duy nhất theo (seed, idx) → không near-dup."""
    diff = ["easy", "medium", "hard"][idx % 3]
    tag = seed.get("ma_de") or "seed"
    n = len(seed.get("questions") or []) or 5
    passage = (f"Đoạn đọc mẫu {tag} phiên {idx + 1}. "
               + " ".join(f"Ý số {tag}-{idx + 1}-{k}." for k in range(1, n + 1)))
    questions = []
    for k in range(n):
        questions.append({
            "stem": f"Câu hỏi hiểu {tag}-{idx + 1}-{k + 1}?",
            "options": {L: f"Phương án {L} của {tag}/{idx + 1}/{k + 1}" for L in R3_OPTION_KEYS},
            "answer": R3_OPTION_KEYS[k % 4],
        })
    return {"passage": passage, "questions": questions, "difficulty": diff,
            "explanation": f"Nhóm đọc-hiểu mock từ {tag}."}


def _real_r3_variant(generator, seed: dict, idx: int) -> Optional[dict]:
    """Sinh nhóm đọc-hiểu R3 THẬT qua Gemini: đoạn văn MỚI + N câu hỏi hiểu (4 lựa chọn), không copy."""
    qs = seed.get("questions") or []
    n = len(qs) or 5
    seed_qs = "\n".join(
        f"Q{q.get('num')}: {q.get('stem')} "
        f"[A:{q.get('options', {}).get('A', '')} | B:{q.get('options', {}).get('B', '')} | "
        f"C:{q.get('options', {}).get('C', '')} | D:{q.get('options', {}).get('D', '')}] ans={q.get('answer')}"
        for q in qs
    )
    system = (
        "You are a VSTEP B1 (CEFR B1) English item writer for Reading Part 3 (a short text + "
        "multiple-choice comprehension questions). Given a seed passage with its questions, write "
        f"ONE NEW, parallel item at the SAME B1 level: a FRESH passage (~180-230 words, NOT a copy) "
        f"on a similar everyday topic, plus EXACTLY {n} comprehension questions, each with 4 options "
        "A, B, C, D and exactly one correct answer clearly supported by YOUR passage. Return ONLY "
        "JSON: {\"passage\": str, \"questions\": [{\"stem\": str, \"options\": {\"A\": str, \"B\": "
        "str, \"C\": str, \"D\": str}, \"answer\": \"A|B|C|D\"}], \"difficulty\": "
        "\"easy|medium|hard\", \"explanation\": str}."
    )
    user = (
        f"SEED passage (write a NEW one on a similar topic, do NOT copy it):\n{seed.get('passage')}\n\n"
        f"SEED questions:\n{seed_qs}\n\nGenerate parallel variant #{idx + 1}."
    )
    raw = generator._call_gemini(system, user)
    data = _loads_lenient(raw)
    return data if isinstance(data, dict) else None


def qc_r3(variant: dict, seed: dict) -> list:
    """Cổng QC cho nhóm đọc-hiểu R3. Trả danh sách lỗi (rỗng = đạt). GV vẫn PHẢI soát ngữ nghĩa."""
    issues = []
    passage = str(variant.get("passage") or "").strip()
    questions = variant.get("questions") or []
    if not passage:
        issues.append("passage rỗng")
    n_seed = len(seed.get("questions") or []) or 5
    if len(questions) != n_seed:
        issues.append(f"phải đúng {n_seed} câu hỏi (đang {len(questions)})")
    for qi, q in enumerate(questions, 1):
        stem = str((q or {}).get("stem") or "").strip()
        options = (q or {}).get("options") or {}
        answer = (q or {}).get("answer")
        if not stem:
            issues.append(f"câu {qi}: stem rỗng")
        if sorted(options.keys()) != R3_OPTION_KEYS:
            issues.append(f"câu {qi}: options phải đủ A,B,C,D (đang {sorted(options.keys())})")
        else:
            vals = [str(v).strip().lower() for v in options.values()]
            if len(set(vals)) < len(vals):
                issues.append(f"câu {qi}: có phương án trùng nội dung")
            if any(not str(v).strip() for v in options.values()):
                issues.append(f"câu {qi}: có phương án rỗng")
        if answer not in options:
            issues.append(f"câu {qi}: answer không thuộc options")
    if passage and _norm_topic(passage) == _norm_topic(seed.get("passage")):
        issues.append("trùng nguyên văn passage seed (bản quyền)")
    return issues


def _assemble_s3_raw(passage, questions: list) -> list:
    """Dựng lại block list s3_raw đúng cấu trúc đối tác (tiêu đề · hướng dẫn · passage · câu 16-20 + options)."""
    blocks = [
        {"kind": "p", "text": "Section 3 Questions 16-20 (5 points)"},
        {"kind": "p", "text": "Read the text and questions below. For each question, circle the letter next to the correct answer (A, B, C or D)"},
    ]
    for para in str(passage).split("\n"):
        if para.strip():
            blocks.append({"kind": "p", "text": para.strip()})
    for k, q in enumerate(questions):
        num = str(16 + k)
        blocks.append({"kind": "p", "text": f"{num}. {q.get('stem', '')}"})
        for opt in R3_OPTION_KEYS:
            blocks.append({"kind": "p", "text": f"{opt}. {q.get('options', {}).get(opt, '')}"})
    return blocks


def build_r3_variants(seeds: list, per_seed: int = 1, generator=None, dup_threshold: float = 0.85) -> list:
    """Sinh biến thể nhóm đọc-hiểu R3 (song song build_r1_variants, đơn vị = nhóm passage+câu hỏi).

    Mỗi item ra: `s3_item` {passage, questions:[{stem,options{A-D},answer}]} + `s3_raw`(block list) +
    `s3_answers` (16-20) đúng shape đối tác + metadata. Phát hiện+gắn nhãn near-dup passage toàn-lô."""
    use_mock = generator is None or getattr(generator, "client", None) is None
    accepted_passages = []
    out = []
    for seed in seeds:
        for i in range(per_seed):
            try:
                v = _mock_r3_variant(seed, i) if use_mock else _real_r3_variant(generator, seed, i)
            except Exception as e:   # sinh lỗi 1 nhóm không làm hỏng cả lô
                logger.warning(f"Sinh nhóm R3 lỗi seed {seed['ma_de']}#{i}: {e}")
                continue
            if not v:
                continue
            diff_en = (v.get("difficulty") or "medium").lower()
            if diff_en not in DIFF_MAP:
                diff_en = "medium"
            passage = str(v.get("passage") or "").strip()
            questions = []
            qs_src = v.get("questions")
            for q in (qs_src if isinstance(qs_src, list) else []):   # phòng thủ: Gemini có thể trả shape méo
                q = q if isinstance(q, dict) else {}
                opts_src = q.get("options")
                opts = opts_src if isinstance(opts_src, dict) else {}
                questions.append({
                    "stem": str(q.get("stem") or "").strip(),
                    "options": {k: str(val) for k, val in opts.items()},
                    "answer": q.get("answer"),
                })
            issues = qc_r3({"passage": passage, "questions": questions}, seed)
            # chống copy near-verbatim đoạn văn seed (gate qc_r3 chỉ bắt trùng NGUYÊN VĂN)
            if passage and _jaccard(passage, seed.get("passage")) >= dup_threshold:
                issues.append("near-duplicate passage seed (bản quyền)")
            for prev in accepted_passages:
                if _jaccard(passage, prev) >= dup_threshold:
                    issues.append("near-duplicate passage (trùng lặp gần với nhóm khác trong lô)")
                    break
            accepted_passages.append(passage)
            s3_answers = {str(16 + k): q["answer"] for k, q in enumerate(questions)}
            out.append({
                "s3_item": {"passage": passage, "questions": questions},
                "s3_raw": _assemble_s3_raw(passage, questions),
                "s3_answers": s3_answers,
                "do_kho": DIFF_MAP[diff_en],
                "difficulty_en": diff_en,
                "explanation": v.get("explanation"),
                "nguon_seed": seed["ma_de"],
                "seed_passage": seed["passage"],
                "qc_issues": issues,
                "qc_ok": len(issues) == 0,
            })
    return out


def export_r3_bundle(items: list) -> dict:
    """Gói bàn giao (JSON) cho đối tác: nhóm đọc-hiểu R3 (passage + câu hỏi) + metadata + độ khó."""
    return {
        "skill": "reading_s3_comprehension",
        "spec": "SPEC-FACTORY-005",
        "note": (
            "Nhóm đọc-hiểu R3 (đoạn văn + câu hỏi 4 lựa chọn) sinh từ bank_raw.json của đối tác; "
            "s3_item {passage, questions} + s3_raw(blocks) + s3_answers (16-20) để merge. "
            "SLICE NGỮ-NGHĨA-NẶNG — GV tiếng Anh BẮT BUỘC soát kỹ đáp án đọc-hiểu trước khi dùng."
        ),
        "count": len(items),
        "count_qc_ok": sum(1 for it in items if it["qc_ok"]),
        "items": items,
    }


def r3_review_sheet(items: list) -> str:
    """Bảng GV soát/ký (Markdown) cho R3: seed | đoạn mới (rút gọn) | số câu | đáp án | độ khó | QC | ô ký."""
    header = (
        "| # | Nguồn seed | Đoạn văn MỚI (rút gọn) | Số câu | Đáp án | Độ khó | QC | GV duyệt (Đạt/Không + chữ ký) |\n"
        "|---|---|---|---|---|---|---|---|"
    )
    rows = [header]
    for i, it in enumerate(items, 1):
        qc = "OK" if it["qc_ok"] else "⚠ " + "; ".join(it["qc_issues"])
        passage = (it["s3_item"]["passage"] or "").replace("|", "/").replace("\n", " ")[:70]
        ans = "; ".join(f"{k}:{it['s3_answers'][k]}" for k in sorted(it["s3_answers"], key=int)).replace("|", "/")
        rows.append(
            f"| {i} | {it['nguon_seed']} | {passage} | {len(it['s3_item']['questions'])} | {ans} | {it['do_kho']} | {qc} |  |"
        )
    return "\n".join(rows)


# ======================================================================
# SLICE W1 (Viết lại câu giữ nghĩa — Viết phần 1) — SPEC-FACTORY-006
# ----------------------------------------------------------------------
# Mở rộng ngân hàng W1 của đối tác (khóa `w1` trong bank_raw.json). Cấu trúc THẬT:
#   w1_raw = list block "p": tiêu đề/hướng dẫn + Example/Answer → các CẶP (câu GỐC + câu VIẾT-LẠI
#   có chỗ trống '……' cho sẵn phần đầu). key_w1 == w1_answers = {"1": <câu mẫu hoàn chỉnh>, ...} (5 câu).
# Đơn vị = 1 câu biến đổi ngữ pháp (bị động/tường thuật/điều kiện/nominalization...). Biến thể =
# câu MỚI cùng KIỂU biến đổi + phần đầu cho sẵn + câu mẫu. Song song pattern R1 (khác: có 'prompt').

_W1_BLANK_RE = re.compile(r"…|_{2,}|\.{3,}")   # chỗ trống '……'/'____'/'...' trong câu viết-lại


def load_w1_seeds(bank: list) -> list:
    """Trích câu viết-lại W1 (khóa `w1`) từ bank_raw.json của đối tác: câu gốc + phần đầu + câu mẫu."""
    seeds = []
    for rec in bank:
        ma_de = rec.get("ma_de") or rec.get("file") or "?"
        w1_raw = rec.get("w1_raw")
        answers = rec.get("w1_answers") or rec.get("key_w1") or {}
        if not isinstance(w1_raw, list) or not answers:
            continue
        content = []
        for b in w1_raw:
            if not isinstance(b, dict) or b.get("kind") != "p":
                continue
            tx = str(b.get("text") or "").strip()
            if not tx or tx.startswith("Section 1") or tx.startswith("Finish each") \
                    or tx.startswith("Example:") or tx.startswith("Answer:"):
                continue
            content.append(tx)
        # ghép cặp NGHIÊM NGẶT theo cửa sổ 2 block: (câu GỐC không-chỗ-trống + câu VIẾT-LẠI có-chỗ-trống).
        # Cấu trúc lệch (block lẻ / gốc có chỗ trống / prompt thiếu chỗ trống / số cặp != số đáp án) →
        # BỎ CẢ RECORD, KHÔNG emit seed lệch key (tránh gán nhầm câu mẫu — bài học review đối kháng).
        pairs, structural_ok = [], (len(content) % 2 == 0)
        if structural_ok:
            for j in range(0, len(content), 2):
                original, prompt = content[j], content[j + 1]
                if _W1_BLANK_RE.search(original) or not _W1_BLANK_RE.search(prompt):
                    structural_ok = False
                    break
                pairs.append((original, prompt))
        if not structural_ok or len(pairs) != len(answers):
            logger.warning(f"W1 {ma_de}: cấu trúc w1_raw lệch (ghép {len(pairs)} cặp / {len(answers)} đáp án) → BỎ record.")
            continue
        for k, (original, prompt) in enumerate(pairs, 1):
            ans = answers.get(str(k))
            if original and prompt and ans:
                seeds.append({"ma_de": ma_de, "num": str(k), "original": original,
                              "prompt": prompt, "answer": str(ans)})
    return seeds


def _w1_lead(prompt: str) -> str:
    """Phần ĐẦU cho sẵn của câu viết-lại (trước chỗ trống) — câu mẫu phải bắt đầu bằng phần này."""
    return _W1_BLANK_RE.split(str(prompt or ""))[0].strip().rstrip(".,:;")


def _w1_prefix_ok(answer, lead) -> bool:
    """Câu mẫu có bắt đầu bằng phần đầu cho sẵn KHÔNG — so theo TOKEN (bỏ dấu câu, không phân biệt hoa/thường).

    So token tránh: (a) false-reject do dấu phẩy/nháy nội dung ('At the moment, Mr. Lazylion's...'),
    (b) false-pass do khớp giữa-từ ('If' khớp 'Iffy')."""
    def toks(s):
        return re.sub(r"[^0-9a-z ]", " ", _norm_topic(s)).split()
    a, lead_t = toks(answer), toks(lead)
    return bool(lead_t) and a[: len(lead_t)] == lead_t


def _mock_w1_variant(seed: dict, idx: int) -> dict:
    """Biến thể MOCK tất định (không gọi mạng) — stand-in cho test (song song _mock_variant R1)."""
    diff = ["easy", "medium", "hard"][idx % 3]
    tag = f"{seed.get('ma_de')}#{seed.get('num')}"
    lead = f"Rewrite {tag} v{idx + 1}"
    return {
        "original": f"Original sentence {tag} version {idx + 1}.",
        "prompt": f"{lead} ______.",
        "answer": f"{lead} means the same thing here.",
        "difficulty": diff,
        "explanation": f"Biến thể viết-lại từ {tag} (cùng kiểu biến đổi).",
    }


def _real_w1_variant(generator, seed: dict, idx: int) -> Optional[dict]:
    """Sinh câu viết-lại W1 THẬT qua Gemini: câu MỚI cùng KIỂU biến đổi + phần đầu + câu mẫu."""
    system = (
        "You are a VSTEP B1 (CEFR B1) English item writer for Writing Part 1 (sentence "
        "transformation: rewrite a sentence so it keeps the same meaning, given the start). Given a "
        "seed (original sentence, the given start, and the model answer), infer the grammar point "
        "being tested (e.g. passive, reported speech, conditional, comparative, nominalisation) and "
        "write ONE NEW, parallel item testing the SAME grammar point at B1 level: a FRESH original "
        "sentence (NOT a copy), a given start ending with a blank '______', and the full model "
        "answer that begins with that given start. Return ONLY JSON: {\"original\": str, "
        "\"prompt\": \"<start> ______.\", \"answer\": \"<full rewritten sentence>\", "
        "\"difficulty\": \"easy|medium|hard\", \"explanation\": str}."
    )
    user = (
        f"SEED (write a NEW one testing the SAME grammar point, do NOT copy it):\n"
        f"Original: {seed.get('original')}\n"
        f"Given start: {seed.get('prompt')}\n"
        f"Model answer: {seed.get('answer')}\n"
        f"Generate parallel variant #{idx + 1}."
    )
    raw = generator._call_gemini(system, user)
    data = _loads_lenient(raw)
    return data if isinstance(data, dict) else None


def qc_w1(variant: dict, seed: dict) -> list:
    """Cổng QC cho câu viết-lại W1. Trả danh sách lỗi (rỗng = đạt)."""
    issues = []
    original = str(variant.get("original") or "").strip()
    prompt = str(variant.get("prompt") or "").strip()
    answer = str(variant.get("answer") or "").strip()
    if not original:
        issues.append("câu gốc rỗng")
    if not prompt:
        issues.append("phần đầu (prompt) rỗng")
    elif not _W1_BLANK_RE.search(prompt):
        issues.append("phần đầu (prompt) thiếu chỗ trống")
    if not answer:
        issues.append("câu mẫu (answer) rỗng")
    if original and answer and _norm_topic(original) == _norm_topic(answer):
        issues.append("câu mẫu trùng câu gốc (chưa biến đổi)")
    lead = _w1_lead(prompt)
    if prompt and _W1_BLANK_RE.search(prompt) and not lead:
        issues.append("prompt thiếu phần đầu trước chỗ trống")
    elif lead and answer and not _w1_prefix_ok(answer, lead):
        issues.append("câu mẫu KHÔNG bắt đầu bằng phần đầu cho sẵn")
    if answer and _norm_topic(answer) == _norm_topic(seed.get("answer")):
        issues.append("trùng nguyên văn câu mẫu seed (bản quyền)")
    return issues


def build_w1_variants(seeds: list, per_seed: int = 1, generator=None, dup_threshold: float = 0.85) -> list:
    """Sinh biến thể câu viết-lại W1 (song song build_r1_variants). Output w1_item {original,prompt,answer}."""
    use_mock = generator is None or getattr(generator, "client", None) is None
    accepted_answers = []
    out = []
    for seed in seeds:
        for i in range(per_seed):
            try:
                v = _mock_w1_variant(seed, i) if use_mock else _real_w1_variant(generator, seed, i)
            except Exception as e:
                logger.warning(f"Sinh câu W1 lỗi seed {seed['ma_de']}#{seed.get('num')}#{i}: {e}")
                continue
            if not v:
                continue
            diff_en = (v.get("difficulty") or "medium").lower()
            if diff_en not in DIFF_MAP:
                diff_en = "medium"
            original = str(v.get("original") or "").strip()
            prompt = str(v.get("prompt") or "").strip()
            answer = str(v.get("answer") or "").strip()
            issues = qc_w1({"original": original, "prompt": prompt, "answer": answer}, seed)
            for prev in accepted_answers:
                if _jaccard(answer, prev) >= dup_threshold:
                    issues.append("near-duplicate answer (trùng lặp gần với câu khác trong lô)")
                    break
            accepted_answers.append(answer)
            out.append({
                "w1_item": {"original": original, "prompt": prompt, "answer": answer},
                "do_kho": DIFF_MAP[diff_en],
                "difficulty_en": diff_en,
                "explanation": v.get("explanation"),
                "nguon_seed": f"{seed['ma_de']}#{seed.get('num')}",
                "seed_answer": seed.get("answer"),
                "qc_issues": issues,
                "qc_ok": len(issues) == 0,
            })
    return out


def export_w1_bundle(items: list) -> dict:
    """Gói bàn giao (JSON) cho đối tác: câu viết-lại W1 (gốc + phần đầu + câu mẫu) + metadata."""
    return {
        "skill": "writing_w1_rewrite",
        "spec": "SPEC-FACTORY-006",
        "note": (
            "Câu viết-lại W1 (giữ nghĩa) paraphrase từ bank_raw.json của đối tác; w1_item {original, "
            "prompt (phần đầu + chỗ trống), answer (câu mẫu)} — merge vào w1_raw (cặp block) + key_w1. "
            "CẦN GV tiếng Anh duyệt+ký (đặc biệt tính đúng ngữ pháp của câu mẫu)."
        ),
        "count": len(items),
        "count_qc_ok": sum(1 for it in items if it["qc_ok"]),
        "items": items,
    }


def w1_review_sheet(items: list) -> str:
    """Bảng GV soát/ký (Markdown) cho W1: seed | câu gốc | phần đầu | câu mẫu | độ khó | QC | ô ký."""
    header = (
        "| # | Nguồn seed | Câu gốc (mới) | Phần đầu cho sẵn | Câu mẫu (answer) | Độ khó | QC | GV duyệt (Đạt/Không + chữ ký) |\n"
        "|---|---|---|---|---|---|---|---|"
    )
    rows = [header]
    for i, it in enumerate(items, 1):
        w = it["w1_item"]
        qc = "OK" if it["qc_ok"] else "⚠ " + "; ".join(it["qc_issues"])
        original = (w.get("original") or "").replace("|", "/")[:45]
        prompt = (w.get("prompt") or "").replace("|", "/")[:35]
        answer = (w.get("answer") or "").replace("|", "/")[:55]
        rows.append(
            f"| {i} | {it['nguon_seed']} | {original} | {prompt} | {answer} | {it['do_kho']} | {qc} |  |"
        )
    return "\n".join(rows)


# ======================================================================
# SLICE W2 (Viết thư ~100 từ — Viết phần 2) — SPEC-FACTORY-007
# ----------------------------------------------------------------------
# Mở rộng ngân hàng W2 của đối tác (khóa `w2` trong bank_raw.json). Cấu trúc THẬT:
#   w2_raw = list block "p": tiêu đề "Section 2 (20 points)" + VAI ("You are <tên>. This is part
#   of a letter you have received from <bạn>, your English penfriend.") + BỐI CẢNH thư nhận (thông
#   điệp + 2-3 ý/câu hỏi cần trả lời) + hướng dẫn "Now write a letter ... about 100 words." + "--- The end ---".
#   W2 KHÔNG có đáp án (tự luận — chấm AI/GV). Đơn vị = 1 đề viết thư. Biến thể = đề thư MỚI theo
#   14 chủ đề B1 (vai + bối cảnh + 2-3 ý mới). GV/AI chấm theo tiêu chí, không có key.

W2_INSTRUCTION = "Now write a letter to this pen-friend on the answer sheet. You should write about 100 words."


def load_w2_seeds(bank: list) -> list:
    """Trích đề viết thư W2 (khóa `w2`) từ bank_raw.json của đối tác: vai + bối cảnh + hướng dẫn."""
    seeds = []
    for rec in bank:
        ma_de = rec.get("ma_de") or rec.get("file") or "?"
        w2_raw = rec.get("w2_raw")
        if not isinstance(w2_raw, list):
            continue
        content = []
        for b in w2_raw:
            if not isinstance(b, dict) or b.get("kind") != "p":
                continue
            tx = str(b.get("text") or "").strip()
            if not tx or tx.startswith("Section 2") or tx.startswith("---"):
                continue
            content.append(tx)
        if not content:
            continue
        role = next((tx for tx in content if tx.lower().startswith("you are")), content[0])
        instr = next((tx for tx in content if tx.lower().startswith("now write")), "")
        ri = content.index(role)
        ii = content.index(instr) if instr in content else len(content)
        situation = "\n".join(content[ri + 1:ii])
        if role and situation:
            seeds.append({"ma_de": ma_de, "role": role, "situation": situation,
                          "instruction": instr or W2_INSTRUCTION,
                          "prompt_text": "\n".join(content)})
    return seeds


def _mock_w2_variant(seed: dict, idx: int) -> dict:
    """Biến thể MOCK tất định (không gọi mạng) — stand-in cho test (song song _mock_variant R1)."""
    diff = ["easy", "medium", "hard"][idx % 3]
    domain = DOMAINS_14[idx % len(DOMAINS_14)]
    tag = seed.get("ma_de") or "seed"
    return {
        "role": f"You are Minh. This is part of a letter from your penfriend about {domain} ({tag}/{idx + 1}).",
        "situation": f"Bối cảnh mẫu {tag} phiên {idx + 1}: penfriend viết về chủ đề {domain}.",
        "points": [f"Ý 1 về {domain} ({tag}/{idx + 1})", f"Ý 2 về {domain} ({tag}/{idx + 1})"],
        "instruction": W2_INSTRUCTION,
        "domain_guess": domain,
        "difficulty": diff,
        "explanation": f"Đề thư mock từ {tag} (chủ đề {domain}).",
    }


def _real_w2_variant(generator, seed: dict, idx: int) -> Optional[dict]:
    """Sinh đề viết thư W2 THẬT qua Gemini: đề MỚI theo 1 trong 14 chủ đề B1, không copy seed."""
    system = (
        "You are a VSTEP B1 (CEFR B1) English item writer for Writing Part 2 (an informal letter "
        "of about 100 words replying to a penfriend). Given a seed letter task, write ONE NEW, "
        "parallel task at B1 level on a DIFFERENT everyday topic (choose ONE B1 topic): a role line "
        "('You are <name>. This is part of a letter you have received from <penfriend>, your English "
        "penfriend.'), a short SITUATION (the penfriend's message), and 2-3 POINTS the candidate "
        "must address. Do NOT copy the seed. Return ONLY JSON: {\"role\": str, \"situation\": str, "
        "\"points\": [str, str, ...], \"instruction\": str, \"domain_guess\": \"<one B1 topic>\", "
        "\"difficulty\": \"easy|medium|hard\", \"explanation\": str}."
    )
    user = (
        f"SEED letter task (write a NEW one on a DIFFERENT topic, do NOT copy it):\n"
        f"{seed.get('prompt_text')}\n\n"
        f"Valid B1 topics: {', '.join(DOMAINS_14)}\n"
        f"Generate parallel variant #{idx + 1}."
    )
    raw = generator._call_gemini(system, user)
    data = _loads_lenient(raw)
    return data if isinstance(data, dict) else None


def qc_w2(variant: dict, seed: dict) -> list:
    """Cổng QC cho đề viết thư W2 (không có đáp án — chấm tự luận). Trả danh sách lỗi (rỗng = đạt)."""
    issues = []
    role = str(variant.get("role") or "").strip()
    situation = str(variant.get("situation") or "").strip()
    points = variant.get("points") or []
    instruction = str(variant.get("instruction") or "").strip()
    domain = variant.get("domain_guess")
    if not role:
        issues.append("vai (role) rỗng")
    if not situation:
        issues.append("bối cảnh thư (situation) rỗng")
    if not isinstance(points, list) or len(points) < 2:
        issues.append(f"cần >=2 ý phải trả lời (đang {len(points) if isinstance(points, list) else 'N/A'})")
    elif any(not str(p).strip() for p in points):
        issues.append("có ý cần trả lời bị rỗng")
    if not instruction:
        issues.append("hướng dẫn (instruction) rỗng")
    if domain is not None and _norm_domain(domain) not in _DOMAINS_14_NORM:
        issues.append(f"domain_guess ngoài 14 chủ đề B1 ({domain!r})")
    if situation and _norm_topic(situation) == _norm_topic(seed.get("situation")):
        issues.append("trùng nguyên văn bối cảnh seed (bản quyền)")
    return issues


def _assemble_w2_raw(item: dict) -> list:
    """Dựng lại block list w2_raw đúng cấu trúc đối tác (tiêu đề · vai · bối cảnh · các ý · hướng dẫn · end)."""
    blocks = [
        {"kind": "p", "text": "Section 2 (20 points)"},
        {"kind": "p", "text": str(item.get("role") or "")},
    ]
    for para in str(item.get("situation") or "").split("\n"):
        if para.strip():
            blocks.append({"kind": "p", "text": para.strip()})
    for p in (item.get("points") or []):
        if str(p).strip():
            blocks.append({"kind": "p", "text": str(p).strip()})
    blocks.append({"kind": "p", "text": str(item.get("instruction") or W2_INSTRUCTION)})
    blocks.append({"kind": "p", "text": "--- The end ---"})
    return blocks


def build_w2_variants(seeds: list, per_seed: int = 1, generator=None, dup_threshold: float = 0.85) -> list:
    """Sinh biến thể đề viết thư W2 (song song build_r1_variants). Output w2_item (KHÔNG có đáp án)."""
    use_mock = generator is None or getattr(generator, "client", None) is None
    accepted = []
    out = []
    for seed in seeds:
        for i in range(per_seed):
            try:
                v = _mock_w2_variant(seed, i) if use_mock else _real_w2_variant(generator, seed, i)
            except Exception as e:
                logger.warning(f"Sinh đề W2 lỗi seed {seed['ma_de']}#{i}: {e}")
                continue
            if not v:
                continue
            diff_en = (v.get("difficulty") or "medium").lower()
            if diff_en not in DIFF_MAP:
                diff_en = "medium"
            # type-gate iteration (Gemini có thể trả points là số → tránh crash cả lô) + chỉ nhận ý là
            # CHUỖI không-rỗng (loại junk [None,None]/[1,2] khỏi lọt QC).
            pts = v.get("points")
            points = [str(p).strip() for p in pts if isinstance(p, str) and p.strip()] if isinstance(pts, list) else []
            w2_item = {
                "role": str(v.get("role") or "").strip(),
                "situation": str(v.get("situation") or "").strip(),
                "points": points,
                "instruction": str(v.get("instruction") or W2_INSTRUCTION).strip(),
                "domain_guess": v.get("domain_guess"),
            }
            issues = qc_w2(w2_item, seed)
            # chống copy near-verbatim bối cảnh seed (qc_w2 chỉ bắt trùng NGUYÊN VĂN)
            if w2_item["situation"] and _jaccard(w2_item["situation"], seed.get("situation")) >= dup_threshold:
                issues.append("near-duplicate situation seed (bản quyền)")
            for prev in accepted:
                if _jaccard(w2_item["situation"], prev) >= dup_threshold:
                    issues.append("near-duplicate situation (trùng lặp gần với đề khác trong lô)")
                    break
            accepted.append(w2_item["situation"])
            out.append({
                "w2_item": w2_item,
                "w2_raw": _assemble_w2_raw(w2_item),
                "do_kho": DIFF_MAP[diff_en],
                "difficulty_en": diff_en,
                "explanation": v.get("explanation"),
                "nguon_seed": seed["ma_de"],
                "seed_situation": seed.get("situation"),
                "qc_issues": issues,
                "qc_ok": len(issues) == 0,
            })
    return out


def export_w2_bundle(items: list) -> dict:
    """Gói bàn giao (JSON) cho đối tác: đề viết thư W2 (KHÔNG có đáp án — tự luận) + metadata."""
    return {
        "skill": "writing_w2_letter",
        "spec": "SPEC-FACTORY-007",
        "note": (
            "Đề viết thư W2 (~100 từ, KHÔNG có đáp án — tự luận chấm AI/GV) sinh từ bank_raw.json của "
            "đối tác; w2_item {role, situation, points, instruction, domain_guess} + w2_raw(blocks) để "
            "merge. CẦN GV tiếng Anh duyệt+ký (đề phù hợp B1, rõ ràng, đúng chủ đề)."
        ),
        "count": len(items),
        "count_qc_ok": sum(1 for it in items if it["qc_ok"]),
        "items": items,
    }


def w2_review_sheet(items: list) -> str:
    """Bảng GV soát/ký (Markdown) cho W2: seed | vai | bối cảnh (rút gọn) | số ý | chủ đề | độ khó | QC | ô ký."""
    header = (
        "| # | Nguồn seed | Vai (role) | Bối cảnh MỚI (rút gọn) | Số ý | Chủ đề | Độ khó | QC | GV duyệt (Đạt/Không + chữ ký) |\n"
        "|---|---|---|---|---|---|---|---|---|"
    )
    rows = [header]
    for i, it in enumerate(items, 1):
        w = it["w2_item"]
        qc = "OK" if it["qc_ok"] else "⚠ " + "; ".join(it["qc_issues"])
        role = (w.get("role") or "").replace("|", "/").replace("\n", " ")[:35]
        situation = (w.get("situation") or "").replace("|", "/").replace("\n", " ")[:50]
        rows.append(
            f"| {i} | {it['nguon_seed']} | {role} | {situation} | {len(w.get('points') or [])} | {w.get('domain_guess')} | {it['do_kho']} | {qc} |  |"
        )
    return "\n".join(rows)


# ======================================================================
# SLICE NGHE (Listening) — SPEC-FACTORY-008
# ----------------------------------------------------------------------
# Mở rộng ngân hàng Nghe của đối tác (pool_lis.json). Format = Cambridge B1 Preliminary (PET):
#   L1 = 5 câu CHỌN-TRANH (hội thoại ngắn 2 người) · L2 = 10 câu ĐIỀN-TỪ (1 monologue, điền vào notes).
# KHÁC BIỆT LỚN: pool_lis KHÔNG có transcript (chỉ l1_stems[5], l2_gaps, answers{1-15}, audio path) →
# đây là SINH-NGƯỢC-TỪ-ĐÁP-ÁN (không paraphrase). Tách 5 tầng để verify từng tầng, và tách khâu
# TEXT (sinh kịch bản + VALIDATE đáp án bằng string-match — RẺ, tất định, test được) khỏi khâu
# TTS/AUDIO (đắt, cần Gemini + nghe tai — chạy real-mode, KHÔNG vào unit test).
# Đa-giọng: Gemini native MultiSpeakerVoiceConfig (≤2 speaker) cho hội thoại L1; single cho L2.
# ⚠️ Khuyết điểm ghi rõ cho GV: audio MÁY (accent/timbre chưa bằng người thật); GV BẮT BUỘC nghe duyệt.

L1_OPTION_KEYS = ["A", "B", "C"]
# Bảng pause (giây) lấy verbatim từ tapescript Cambridge B1 Preliminary (mỗi đoạn đọc 2 LẦN).
# Dùng khi dựng audio real-mode. L2 look-time nội suy 45s cho 10 gap (Cambridge cho 20s/6 gap);
# review cuối 2 phút = 60+60 (tách để chèn câu nhắc "one more minute"). Nghiên cứu S54.
LIS_PAUSES = {
    # Calibrate S54: giọng Gemini TTS đo THẬT ~210wpm (nhanh hơn 140) → nới pause + tăng content
    # (L1 115 từ / L2 360 từ) để trọn bài ~17.1' (band 16.3-18.2' ở 190-230wpm). Tổng pause = 441s.
    "after_part_title": 5,      # sau "Part One."
    "after_instruction": 5,     # sau "For each question, choose the correct answer."
    "before_dialogue": 5,       # sau khi đọc stem, trước khi phát hội thoại
    "after_play": 8,            # sau mỗi lần phát (cả lần 1 và lần 2)
    "between_plays_l1": 5,      # sau "Now listen again." (L1)
    "end_of_part": 10,          # sau "That is the end of Part ..."
    "l2_look_time": 60,         # nhìn Part Two trước khi nghe (10 gap)
    "between_plays_l2": 30,     # sau "Now listen again." (L2 — bài dài)
    "review_half": 90,          # nửa thời gian soát cuối (×2 = 3 phút)
}
# Cặp giọng tương phản mạnh cho hội thoại (Google KHÔNG gắn nhãn giới tính chính thức — chọn theo nghe).
LIS_VOICES = {"A": "Kore", "B": "Puck"}   # A ~ nữ, B ~ nam (cần nghe kiểm)

# Sinh kịch bản Nghe = prompt DÀI NHẤT nhà máy (5 hội thoại ~113 từ + monologue ~355 từ + gaps →
# JSON ~2500 token). Ở Gemini 2.5/3.x thinking (~9500 token đo thật) + JSON dùng CHUNG budget → phải
# đặt trần RỘNG kẻo cắt/méo JSON (SPEC-FACTORY-013). thinking_budget nhỏ để nhường chỗ cho JSON.
LIS_MAX_OUTPUT_TOKENS = 24576
LIS_THINKING_BUDGET = 512

# Ảnh chọn-tranh L1 (SPEC-FACTORY-011) — model CONFIGURABLE (giữ 2.5-flash-image proven S43; đổi Nano
# Banana 2 = set env B1_IMAGE_MODEL=gemini-3.1-flash-image). ⚠️ Free-tier API image = 0 IPM (chặn cứng
# từ ~12/2025) → cần BẬT BILLING ($0-limit OK → Tier 1) mới sinh ảnh thật (khác 503 text: retry vô ích).
IMAGE_MODEL = os.getenv("B1_IMAGE_MODEL", "gemini-2.5-flash-image")
# Style preamble KHOÁ CỨNG (paste GIỐNG HỆT cho A/B/C → 3 ảnh chỉ khác chủ thể, so sánh công bằng).
LIS_IMG_STYLE = (
    "A single simple flat vector illustration for an English exam, in a clean minimalist style. "
    "One clear central subject on a plain solid white background, soft even lighting, no shadows. "
    "Simple bold outlines, flat pastel colours, centered composition, square 1:1 aspect ratio, "
    "the same drawing style for every picture in this set so the options differ ONLY in subject."
)
LIS_IMG_NEGATIVE = (
    "Must NOT contain: text, letters, words, numbers, digits, captions, labels, speech bubbles, "
    "watermark, signature, logo, typography, option letters A B C. All signs and screens are blank."
)


def build_lis_image_prompt(option_text: str) -> str:
    """Prompt sinh 1 ảnh minh hoạ 1 option (GROUNDED theo option text, cấm bịa/chữ). answer KHÔNG vào."""
    subject = str(option_text or "").strip().rstrip(".")
    if not subject:                    # fail-fast: không có chủ thể → prompt vô nghĩa (grounded)
        raise ValueError("build_lis_image_prompt: option_text rỗng — không có chủ thể để vẽ.")
    return (f"{LIS_IMG_STYLE}\n\nThe subject to depict is exactly this and nothing more: {subject}. "
            f"Draw only what is described; do not invent extra objects, words or details.\n\n"
            f"{LIS_IMG_NEGATIVE}")


def _lis_norm_pad(s) -> str:
    """Chuẩn hoá + đệm khoảng trắng 2 đầu để so 'đáp án ∈ transcript' theo ranh giới TỪ (bỏ dấu câu)."""
    return " " + " ".join(re.sub(r"[^0-9a-z ]", " ", _norm_topic(s)).split()) + " "


def _lis_contains(transcript, answer) -> bool:
    """Đáp án (kể cả dạng '12/twelve') có xuất hiện như CỤM TỪ trong transcript không (bỏ hoa/dấu câu)."""
    tx = _lis_norm_pad(transcript)
    for alt in str(answer or "").split("/"):
        a = _lis_norm_pad(alt).strip()
        if a and f" {a} " in tx:
            return True
    return False


def load_lis_seeds(pool) -> list:
    """Trích bài Nghe từ pool_lis.json của đối tác (DICT keyed by code 'LB1.26xx') thành seed sạch."""
    records = pool.values() if isinstance(pool, dict) else pool
    seeds = []
    for rec in records:
        if not isinstance(rec, dict):
            continue
        code = rec.get("code") or "?"
        answers = rec.get("answers") or {}
        l1_stems = rec.get("l1_stems") or []
        l2_gaps = rec.get("l2_gaps") or []
        if answers and l1_stems and l2_gaps:
            seeds.append({
                "code": code, "src_code": rec.get("src_code") or code,
                "set_file": rec.get("audio_name") or rec.get("paper_path"),
                "answers": {str(k): v for k, v in answers.items()},
                "l1_stems": list(l1_stems), "l2_gaps": [int(n) for n in l2_gaps],
                "audio_duration_s": rec.get("audio_duration_s"),
            })
    return seeds


def _mock_lis_variant(seed: dict, idx: int) -> dict:
    """Biến thể MOCK tất định (không gọi mạng) — stand-in cho test. Đáp án khớp transcript, unique theo (seed,idx)."""
    diff = ["easy", "medium", "hard"][idx % 3]
    code = str(seed.get("code") or "seed")
    srcnum = code.split(".")[-1]
    l2_nums = [int(n) for n in (seed.get("l2_gaps") or list(range(6, 16)))]
    l1 = []
    for k in range(5):
        ans = L1_OPTION_KEYS[k % 3]
        tag = f"{srcnum}v{idx + 1}q{k + 1}"
        opts = {"A": f"choice a {tag}", "B": f"choice b {tag}", "C": f"choice c {tag}"}
        l1.append({
            "stem": f"L1 question about topic {tag}?", "options": opts, "answer": ans,
            "transcript": f"Speaker A: What about {tag}? Speaker B: I think {opts[ans]} is right.",
            "speakers": ["Speaker A", "Speaker B"],
        })
    l2_ans = {n: f"kw{n}s{srcnum}v{idx + 1}" for n in l2_nums}
    l2_transcript = (f"Hello, welcome to talk {srcnum} version {idx + 1}. "
                     + " ".join(f"Number {n} is {l2_ans[n]}." for n in l2_nums))
    return {
        "l1_scripts": l1,
        "l2_transcript": l2_transcript,
        "l2_gaps": [{"n": n, "answer": l2_ans[n]} for n in l2_nums],
        "difficulty": diff,
        "explanation": f"Bài nghe mock từ {code}.",
    }


def _real_lis_variant(generator, seed: dict, idx: int) -> Optional[dict]:
    """Sinh kịch bản Nghe THẬT qua Gemini TEXT (không phải TTS): 5 hội thoại L1 + 1 monologue L2."""
    n_l2 = len(seed.get("l2_gaps") or list(range(6, 16)))
    system = (
        "You are a Cambridge B1 Preliminary (PET) Listening item writer. Create ONE NEW listening "
        "content set at B1 level (NOT a copy). Return ONLY JSON. PART 1 'l1_scripts' = 5 items, each a "
        "2-speaker conversation (or announcement) of ABOUT 110-115 WORDS (exam-length, not a one-liner) "
        "with a picture-choice question: {\"stem\": str, "
        "\"options\": {\"A\": str, \"B\": str, \"C\": str}, \"answer\": \"A|B|C\", \"transcript\": "
        "\"Speaker A: ...\\nSpeaker B: ...\", \"speakers\": [\"Speaker A\", \"Speaker B\"]}. The correct "
        "option MUST be clearly supported by the transcript; the two distractors are mentioned then "
        "rejected. IMPORTANT: each option A/B/C must be a SHORT, CONCRETE, DRAWABLE noun phrase (an "
        "object/action/scene, e.g. 'a woman riding a bicycle') so it can be illustrated as a picture. "
        "PART 2 = one monologue 'l2_transcript' (ABOUT 350-360 WORDS, natural talk — long "
        "enough for a ~17-minute exam when read twice) plus 'l2_gaps' "
        f"= {n_l2} note gaps, each {{\"n\": <6..>, \"answer\": \"<1-2 words>\"}} where EACH answer appears "
        "VERBATIM in l2_transcript. Return: {\"l1_scripts\": [..5..], \"l2_transcript\": str, "
        "\"l2_gaps\": [..], \"difficulty\": \"easy|medium|hard\", \"explanation\": str}."
    )
    user = (
        f"Seed listening test to parallel (same PET style/level, do NOT copy):\n"
        f"L1 question stems: {json.dumps(seed.get('l1_stems'), ensure_ascii=False)}\n"
        f"Number of L2 gaps: {n_l2}\nGenerate parallel variant #{idx + 1}."
    )
    # Trần token rộng + thinking nhỏ để JSON kịch bản dài KHÔNG bị cắt/méo (SPEC-FACTORY-013).
    raw = generator._call_gemini(system, user, max_output_tokens=LIS_MAX_OUTPUT_TOKENS,
                                 thinking_budget=LIS_THINKING_BUDGET)
    try:
        data = _loads_lenient(raw)
    except Exception as e:
        logger.warning("Nghe: JSON méo/không parse được (%s); raw[:120]=%r", e, (raw or "")[:120])
        return None
    if not isinstance(data, dict):
        logger.warning("Nghe: JSON không phải object; raw[:120]=%r", (raw or "")[:120])
        return None
    return data


def qc_lis(variant: dict, seed: dict) -> list:
    """Cổng QC cho bài Nghe. Trả danh sách lỗi (rỗng = đạt). GV vẫn PHẢI nghe duyệt audio + ngữ nghĩa."""
    issues = []
    l1 = variant.get("l1_scripts") or []
    l2_transcript = str(variant.get("l2_transcript") or "")
    l2_gaps = variant.get("l2_gaps") or []
    if len(l1) != 5:
        issues.append(f"L1 phải đúng 5 câu (đang {len(l1)})")
    for i, q in enumerate(l1, 1):
        q = q if isinstance(q, dict) else {}
        opts = q.get("options") if isinstance(q.get("options"), dict) else {}
        if not str(q.get("stem") or "").strip():
            issues.append(f"L1 câu {i}: stem rỗng")
        if sorted(opts.keys()) != L1_OPTION_KEYS:
            issues.append(f"L1 câu {i}: options phải đủ A,B,C (đang {sorted(opts.keys())})")
        else:
            vals = [str(v).strip().lower() for v in opts.values()]
            if len(set(vals)) < len(vals):
                issues.append(f"L1 câu {i}: có phương án trùng nội dung")
            if any(not str(v).strip() for v in opts.values()):
                issues.append(f"L1 câu {i}: có phương án rỗng")
            if q.get("answer") not in opts:
                issues.append(f"L1 câu {i}: answer không thuộc options")
        if not str(q.get("transcript") or "").strip():
            issues.append(f"L1 câu {i}: transcript rỗng")
    exp_gaps = [int(n) for n in (seed.get("l2_gaps") or list(range(6, 16)))]
    if len(l2_gaps) != len(exp_gaps):
        issues.append(f"L2 phải đúng {len(exp_gaps)} chỗ điền (đang {len(l2_gaps)})")
    # CỔNG số-thứ-tự gap L2: n phải khớp seed (6-15), không None/trùng/đè key L1 (1-5) → tránh
    # answers.update ghi đè đáp án L1 âm thầm (bài học review; song song gate của R4).
    got_n = [g.get("n") for g in l2_gaps if isinstance(g, dict)]
    if any(n is None for n in got_n) or sorted(str(n) for n in got_n) != sorted(str(n) for n in exp_gaps):
        issues.append(f"L2 số thứ tự gap phải đúng {sorted(exp_gaps)} (đang {got_n})")
    if not l2_transcript.strip():
        issues.append("L2 transcript rỗng")
    for g in l2_gaps:   # CỔNG cốt lõi: mọi đáp án L2 phải NẰM TRONG transcript (chống lệch đáp án)
        g = g if isinstance(g, dict) else {}
        ans = str(g.get("answer") or "").strip()
        if not ans:
            issues.append(f"L2 chỗ {g.get('n')}: đáp án rỗng")
        elif not _lis_contains(l2_transcript, ans):
            issues.append(f"L2 chỗ {g.get('n')}: đáp án {ans!r} KHÔNG có trong transcript")
    return issues


def _next_lis_code(seed: dict, idx: int, used: set) -> str:
    """Cấp code MỚI dải LB1.90-* (tách khỏi LB1.26xx thật), nhúng code seed để truy vết + ổn định."""
    src_num = str(seed.get("code") or "seed").split(".")[-1]
    base = f"LB1.90-{src_num}-{idx + 1}"
    code, n = base, 1
    while code in used:
        n += 1
        code = f"{base}.{n}"
    used.add(code)
    return code


def build_lis_variants(seeds: list, per_seed: int = 1, generator=None, dup_threshold: float = 0.85) -> list:
    """Sinh biến thể bài Nghe (kịch bản + đáp án, CHƯA render audio). Output lis_item shape pool_lis."""
    use_mock = generator is None or getattr(generator, "client", None) is None
    used_codes = {s["code"] for s in seeds}
    accepted = []
    out = []
    for seed in seeds:
        for i in range(per_seed):
            try:
                v = _mock_lis_variant(seed, i) if use_mock else _real_lis_variant(generator, seed, i)
            except Exception as e:
                logger.warning(f"Sinh bài Nghe lỗi seed {seed['code']}#{i}: {e}")
                continue
            if not v:
                continue
            diff_en = (v.get("difficulty") or "medium").lower()
            if diff_en not in DIFF_MAP:
                diff_en = "medium"
            l1 = [q if isinstance(q, dict) else {} for q in (v.get("l1_scripts") or [])]
            l2_transcript = str(v.get("l2_transcript") or "").strip()
            l2_gaps = [g if isinstance(g, dict) else {} for g in (v.get("l2_gaps") or [])]
            issues = qc_lis({"l1_scripts": l1, "l2_transcript": l2_transcript, "l2_gaps": l2_gaps}, seed)
            for prev in accepted:
                if _jaccard(l2_transcript, prev) >= dup_threshold:
                    issues.append("near-duplicate transcript (trùng lặp gần với bài khác trong lô)")
                    break
            accepted.append(l2_transcript)
            code = _next_lis_code(seed, i, used_codes)
            answers = {str(k): q.get("answer") for k, q in enumerate(l1, 1)}
            for g in l2_gaps:   # KHÔNG ghi đè đáp án L1 (key 1-5) dù n lệch — phòng thủ (qc_lis đã gắn nhãn)
                key = str(g.get("n"))
                if key not in answers:
                    answers[key] = g.get("answer")
            out.append({
                # shape pool_lis của đối tác (audio CHƯA render → audio_status='pending_tts').
                "lis_item": {
                    "code": code, "src_code": seed["code"], "set_file": seed.get("set_file"),
                    "audio_path": None, "audio_name": f"{code}.mp3", "audio_duration_s": None,
                    "answers": answers, "n_answers": len(answers),
                    "l1_stems": [q.get("stem") for q in l1], "l1_count": len(l1),
                    "l2_gaps": [g.get("n") for g in l2_gaps], "l2_count": len(l2_gaps),
                    "media_ext": {}, "flags": [],
                    "audio_status": "pending_tts", "needs_audio_verify": True,
                    "image_status": "pending_image", "needs_image_verify": True,
                },
                "transcripts": {"l1": l1, "l2": l2_transcript},
                "do_kho": DIFF_MAP[diff_en],
                "difficulty_en": diff_en,
                "explanation": v.get("explanation"),
                "nguon_seed": seed["code"],
                "qc_issues": issues,
                "qc_ok": len(issues) == 0,
            })
    return out


def export_lis_bundle(items: list) -> dict:
    """Gói bàn giao (JSON) cho đối tác: bài Nghe (kịch bản + đáp án + shape pool_lis) + metadata."""
    return {
        "skill": "listening",
        "spec": "SPEC-FACTORY-008",
        "note": (
            "Bài Nghe (5 chọn-tranh L1 + 10 điền-từ L2, format PET) sinh từ pool_lis.json của đối tác; "
            "lis_item = shape pool_lis (audio_name='.mp3'). Audio render bằng CLI --audio: ghép TRỌN "
            "bài ~17' (16-18' theo dải giọng, calibrate S54) theo lịch pause Cambridge (đọc-2-lần, cache per-chunk) → MP3 (lameenc, fallback WAV ~6-8× lớn). "
            "⚠️ AUDIO là GIỌNG MÁY (Gemini TTS đa-giọng) — GV tiếng Anh BẮT BUỘC nghe duyệt + soát đáp án "
            "trước khi dùng. Ảnh chọn-tranh L1 = asset giao RIÊNG (media_ext.l1_images + transcripts.l1[].image_urls, "
            "sinh Gemini image real-mode) — GV duyệt ảnh; đối tác có thể thay audio/ảnh người thật."
        ),
        "count": len(items),
        "count_qc_ok": sum(1 for it in items if it["qc_ok"]),
        "items": items,
    }


def lis_review_sheet(items: list) -> str:
    """Bảng GV soát/ký (Markdown) cho Nghe + CHECKLIST nghe duyệt audio máy. GV BẮT BUỘC nghe từng
    file trước khi dùng: audio là giọng MÁY (Gemini TTS đa-giọng) — soát accent/tốc độ/độ rõ + đáp án khớp."""
    header = (
        "| # | Nguồn seed | Mã | L1 (1-5) | L2 (6-15) | Transcript L2 (rút gọn) | Audio file | Thời lượng | Trạng thái | Độ khó | QC | GV duyệt (Đạt/Không + chữ ký) |\n"
        "|---|---|---|---|---|---|---|---|---|---|---|---|"
    )
    rows = [header]
    for i, it in enumerate(items, 1):
        li = it["lis_item"]
        qc = "OK" if it["qc_ok"] else "⚠ " + "; ".join(it["qc_issues"])
        l1a = "/".join(str(li["answers"].get(str(k))) for k in range(1, 6))
        l2a = "; ".join(f"{n}:{li['answers'].get(str(n))}" for n in li["l2_gaps"]).replace("|", "/")[:50]
        tx = (it["transcripts"]["l2"] or "").replace("|", "/").replace("\n", " ")[:45]
        dur = li.get("audio_duration_s")
        dur_s = f"{int(dur // 60)}'{int(dur % 60):02d}\"" if isinstance(dur, (int, float)) else "—"
        audio_f = os.path.basename(str(li.get("audio_path") or li.get("audio_name") or "—")).replace("|", "/")
        rows.append(
            f"| {i} | {it['nguon_seed']} | {li['code']} | {l1a} | {l2a} | {tx} | {audio_f} | {dur_s} | "
            f"{li['audio_status']} | {it['do_kho']} | {qc} |  |"
        )
    checklist = (
        "\n\n**Checklist GV nghe duyệt audio MÁY (từng bài — bắt buộc trước khi dùng):**\n"
        "- [ ] Nghe hết file: giọng rõ, tốc độ hợp thí sinh B1 (~135-140 wpm), accent chấp nhận được\n"
        "- [ ] Hội thoại L1 tách ĐÚNG 2 giọng (không lẫn/na ná), đọc **2 lần** + khoảng lặng đủ\n"
        "- [ ] Monologue L2 đọc 2 lần, mỗi đáp án điền-từ nghe RÕ + đúng thứ tự trong bài\n"
        "- [ ] Đáp án (L1 A/B/C + L2 điền-từ) KHỚP nội dung nghe được\n"
        "- [ ] Tổng thời lượng hợp lý (mục tiêu ~17'; thực tế 16-18' theo dải giọng 190-230wpm — calibrate S54) + pause đủ\n"
        "- [ ] (Nếu audio_status='wav_generated') file WAV lớn ~6-8× MP3 — cân nhắc cài lameenc để xuất MP3\n"
        "- [ ] ẢNH chọn-tranh L1 (nếu có): mỗi câu 3 tranh A/B/C rõ, ĐÚNG option, cùng style, KHÔNG dính chữ/số/nhãn\n"
        "- [ ] (Nếu chưa đạt) ghi lý do + đề nghị chỉnh hoặc thay bằng audio/ảnh người thật\n"
    )
    return "\n".join(rows) + checklist


# --- TTS + GHÉP AUDIO (chạy REAL-MODE / CLI --audio; KHÔNG vào unit test vì cần Gemini/nghe tai) ---

def silence_pcm(ms: int, rate: int = 24000, channels: int = 1, sampwidth: int = 2) -> bytes:
    """Khoảng lặng PCM 16-bit = bytes 0. Độ dài tính THEO rate (không hardcode) — tránh lệch khi đổi rate."""
    return b"\x00" * (int(rate * ms / 1000) * channels * sampwidth)


def concat_wavs(input_paths: list, output_path: str, gap_ms: int = 0) -> str:
    """Nối nhiều WAV cùng format + chèn khoảng lặng gap_ms giữa các đoạn (stdlib wave). Raise nếu lệch format."""
    frames, params = [], None
    for pth in input_paths:
        with wave.open(pth, "rb") as w:
            p = w.getparams()
            if params is None:
                params = p
            elif (p.nchannels, p.sampwidth, p.framerate) != (params.nchannels, params.sampwidth, params.framerate):
                raise ValueError(f"WAV format lệch: {pth} ({p.nchannels},{p.sampwidth},{p.framerate}) != gốc")
            frames.append(w.readframes(w.getnframes()))
    if params is None:
        raise ValueError("Không có WAV đầu vào để nối.")
    gap = silence_pcm(gap_ms, params.framerate, params.nchannels, params.sampwidth) if gap_ms else b""
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with wave.open(output_path, "wb") as w:
        w.setnchannels(params.nchannels)
        w.setsampwidth(params.sampwidth)
        w.setframerate(params.framerate)
        for i, fr in enumerate(frames):
            if i and gap:
                w.writeframes(gap)
            w.writeframes(fr)
    return output_path


def assemble_wav_segments(segments: list, output_path: str,
                          rate: int = 24000, channels: int = 1, sampwidth: int = 2) -> str:
    """Ghép danh sách segment XEN KẼ audio + khoảng lặng thành 1 WAV (stdlib wave).

    segments: list tuple ('audio', wav_path) | ('silence', ms). Khác concat_wavs (1 gap chung),
    hàm này cho pause KHÁC NHAU ở từng vị trí — cần cho lịch pause PET (đọc-2-lần, review cuối).
    Mọi WAV 'audio' phải cùng (channels, sampwidth, rate); raise nếu lệch để không ghép rác."""
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with wave.open(output_path, "wb") as out:
        out.setnchannels(channels)
        out.setsampwidth(sampwidth)
        out.setframerate(rate)
        for i, (kind, val) in enumerate(segments):
            if kind == "silence":
                out.writeframes(silence_pcm(int(val), rate, channels, sampwidth))
            elif kind == "audio":
                with wave.open(val, "rb") as w:
                    if (w.getnchannels(), w.getsampwidth(), w.getframerate()) != (channels, sampwidth, rate):
                        raise ValueError(
                            f"segment {i}/{len(segments)}: WAV format lệch: {val} ({w.getnchannels()},"
                            f"{w.getsampwidth()},{w.getframerate()}) != ({channels},{sampwidth},{rate})")
                    out.writeframes(w.readframes(w.getnframes()))
            else:
                raise ValueError(f"segment {i}/{len(segments)}: segment kind không hợp lệ: {kind!r}")
    return output_path


def wav_to_mp3(wav_path: str, mp3_path: Optional[str] = None,
               bitrate_kbps: int = 64, quality: int = 2) -> Optional[str]:
    """WAV 16-bit → MP3 (LAME qua lameenc). OPTIONAL: lameenc lazy-import; nếu CHƯA cài → log +
    trả None (caller giữ WAV) ⇒ base requirements.txt + pytest + CI KHÔNG phá (văn hoá 0-dep).

    64 kbps CBR đủ trong suốt cho speech mono 24kHz (~6-8× nhỏ hơn WAV). quality: 2=tốt, 7=nhanh."""
    try:
        import lameenc  # noqa: PLC0415 — lazy: chỉ nạp khi thực sự encode MP3
    except ImportError:
        logger.warning("lameenc chưa cài — bỏ qua MP3, giữ WAV %s (pip install -r requirements-audio.txt)", wav_path)
        return None
    if mp3_path is None:
        mp3_path = os.path.splitext(wav_path)[0] + ".mp3"
    with wave.open(wav_path, "rb") as w:
        channels, rate = w.getnchannels(), w.getframerate()
        if w.getsampwidth() != 2:
            raise ValueError("wav_to_mp3 cần PCM 16-bit (sampwidth=2)")
        pcm = w.readframes(w.getnframes())
    enc = lameenc.Encoder()
    enc.set_bit_rate(bitrate_kbps)
    enc.set_in_sample_rate(rate)      # 24000 được lameenc hỗ trợ native (không resample)
    enc.set_channels(channels)
    enc.set_quality(quality)
    mp3 = enc.encode(pcm) + enc.flush()   # encode cả buffer 1 lần — OK cho ~17'
    os.makedirs(os.path.dirname(mp3_path) or ".", exist_ok=True)
    with open(mp3_path, "wb") as f:
        f.write(mp3)
    return mp3_path


def _lis_tts(generator, text: str, output_path: str, speakers=None) -> str:
    """TTS Gemini → WAV 24kHz mono. speakers=None: 1 giọng 'Puck'; speakers=[(label,voice),...]: đa-giọng.

    CHỈ chạy real-mode (cần generator.client). Lazy-import google types để core logic không phụ thuộc SDK."""
    from google.genai import types  # noqa: PLC0415
    client = getattr(generator, "client", None)
    if client is None:
        raise RuntimeError("Gemini client chưa khởi tạo (cần GEMINI_API_KEY) cho TTS.")
    if speakers:
        speech = types.SpeechConfig(multi_speaker_voice_config=types.MultiSpeakerVoiceConfig(
            speaker_voice_configs=[
                types.SpeakerVoiceConfig(speaker=lab, voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice)))
                for lab, voice in speakers
            ]))
    else:
        speech = types.SpeechConfig(voice_config=types.VoiceConfig(
            prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Puck")))
    resp = client.models.generate_content(
        model="gemini-2.5-flash-preview-tts", contents=text,
        config=types.GenerateContentConfig(response_modalities=["AUDIO"], speech_config=speech))
    audio = None
    for c in (resp.candidates or []):
        for p in ((c.content.parts if c.content else None) or []):
            if p.inline_data and p.inline_data.mime_type.startswith("audio/"):
                audio = p.inline_data.data
                break
    if audio is None:
        raise ValueError("Không có phần audio trong phản hồi Gemini TTS.")
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    # Ghi ATOMIC (temp cùng thư mục → os.replace) để cache KHÔNG bao giờ chứa WAV ghi-dở khi
    # crash/interrupt giữa chừng (review S54: file >44 byte hỏng vẫn lọt qua check cũ).
    tmp_path = f"{output_path}.tmp{os.getpid()}"
    try:
        with wave.open(tmp_path, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(24000)
            w.writeframes(audio)
        os.replace(tmp_path, output_path)
    except BaseException:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise
    return output_path


# Lỗi transient free-tier Gemini (retry được); khác lỗi thật (raise ngay).
_TTS_TRANSIENT = ("429", "503", "resource_exhausted", "unavailable", "overloaded", "rate limit", "quota")


def _tts_with_retry(generator, text: str, output_path: str, speakers=None,
                    max_retries: int = 5, base_delay: float = 2.0) -> str:
    """Gọi _lis_tts với exponential backoff + jitter cho lỗi transient (429/503). Lỗi khác raise
    ngay. Dựng bài dài = 20-30 call → free-tier rất dễ 429, backoff giúp không rơi cả bài."""
    for attempt in range(max_retries):
        try:
            return _lis_tts(generator, text, output_path, speakers)
        except Exception as e:
            transient = any(t in str(e).lower() for t in _TTS_TRANSIENT)
            if not transient or attempt == max_retries - 1:
                raise
            delay = min(60.0, base_delay * (2 ** attempt)) + random.uniform(0, 1)
            logger.warning("TTS transient (%s) — thử lại sau %.1fs (lần %d/%d)", e, delay, attempt + 1, max_retries)
            time.sleep(delay)


def _valid_wav(path: str) -> bool:
    """WAV ĐỌC ĐƯỢC + đủ frames (không chỉ >44 byte header)? Chống cache file ghi-dở/hỏng (review S54)."""
    try:
        with wave.open(path, "rb") as w:
            n = w.getnframes()
            return n > 0 and len(w.readframes(n)) == n * w.getsampwidth() * w.getnchannels()
    except (wave.Error, EOFError, OSError):
        return False


def _lis_tts_cached(generator, text: str, cache_dir: str, speakers=None) -> str:
    """TTS có CACHE theo hash(text+speakers): đoạn lặp lại (lời dẫn, 'Now listen again', đọc-lần-2)
    chỉ gọi Gemini 1 lần → giảm mạnh số call, tránh cạn free-tier khi dựng trọn bài + re-run rẻ.
    Cache theo NỘI DUNG: cùng text+giọng → cùng audio (dedup hợp lệ; item trùng nội dung đã bị
    near-dup + qc gate loại render nên không lẫn bài)."""
    key = hashlib.md5((text + "|" + json.dumps(speakers or [], ensure_ascii=False)).encode("utf-8")).hexdigest()[:16]
    os.makedirs(cache_dir, exist_ok=True)
    cached = os.path.join(cache_dir, f"{key}.wav")
    if _valid_wav(cached):       # đọc-được + đủ frames (không chỉ >44 byte) → dùng lại an toàn
        return cached
    return _tts_with_retry(generator, text, cached, speakers)


# Lời dẫn chuẩn (phỏng theo tapescript Cambridge B1 Preliminary; khung "hai phần" cho bản rút gọn đối tác).
LIS_OPENING = ("B1 Preliminary, Listening. There are two parts to the test. "
               "You will hear each recording twice. You will have time at the end to check your answers.")


def _build_listening_segments(l1: list, l2: str, pauses: dict = None) -> list:
    """Dựng KẾ HOẠCH segment cho TRỌN bài Nghe theo lịch Cambridge PET: 5 hội thoại L1 (đọc-2-lần,
    đa-giọng) + monologue L2 (đọc-2-lần) + lời dẫn + pause đúng bảng. Tách khỏi TTS thật để test
    OFFLINE được cấu trúc/pause. Trả list [('audio', (text, speakers)) | ('silence', ms)]."""
    p = pauses or LIS_PAUSES
    voices = list(LIS_VOICES.values())
    seg = []

    def say(text, speakers=None):
        seg.append(("audio", (text, speakers)))

    def pause(sec):
        seg.append(("silence", int(sec) * 1000))

    say(LIS_OPENING)
    say("Part One.")
    pause(p["after_part_title"])
    say("For each question, choose the correct answer.")
    pause(p["after_instruction"])
    for i, q in enumerate(l1, 1):
        say(f"Question {i}. {str((q or {}).get('stem') or '')}")
        pause(p["before_dialogue"])
        dlg = str((q or {}).get("transcript") or "")
        # gán giọng theo NHÃN THẬT trong transcript (config PHẢI khớp label 'X:' trong text) để tách
        # đúng 2 giọng (bài học review S53); ≤2 giọng = giới hạn MultiSpeakerVoiceConfig.
        labels = []
        for line in dlg.splitlines():
            m = re.match(r"\s*([^:]{1,40}):\s", line)   # nới 25→40: tên dài ("Professor ...") vẫn tách 2 giọng
            if m and m.group(1).strip() and m.group(1).strip() not in labels:
                labels.append(m.group(1).strip())
        labels = labels[:2]
        if len(labels) < 2 and sum(": " in ln for ln in dlg.splitlines()) >= 2:
            logger.warning("Nghe: tách <2 nhãn giọng từ hội thoại (sẽ đọc MONO): %s", dlg.replace("\n", " ")[:60])
        speakers = ([(lab, voices[j % len(voices)]) for j, lab in enumerate(labels)]
                    if len(labels) >= 2 else None)
        say(dlg, speakers)                    # đọc lần 1
        pause(p["after_play"])
        say("Now listen again.")
        pause(p["between_plays_l1"])
        say(dlg, speakers)                    # đọc lần 2 (GIỐNG HỆT → cache trúng, 1 call)
        pause(p["after_play"])
    say("That is the end of Part One.")
    pause(p["end_of_part"])
    say("Now look at Part Two.")
    pause(p["after_part_title"])
    say("You will hear a talk. For each question, write the correct answer in the gap. "
        "Write one or two words or a number or a date or a time. "
        "You now have forty-five seconds to look at Part Two.")
    pause(p["l2_look_time"])
    say(str(l2 or ""))                        # monologue đọc lần 1
    pause(p["after_play"])
    say("Now listen again.")
    pause(p["between_plays_l2"])
    say(str(l2 or ""))                        # monologue đọc lần 2 (cache trúng)
    pause(p["after_play"])
    say("That is the end of Part Two. You now have two minutes to check your answers.")
    pause(p["review_half"])
    say("You now have one more minute.")
    pause(p["review_half"])
    say("That is the end of the test.")
    return seg


def build_listening_audio(generator, item: dict, out_dir: str, to_mp3: bool = True) -> dict:
    """Dựng TRỌN bài Nghe ~17' (real-mode): 5 hội thoại L1 (đa-giọng, đọc-2-lần) + monologue L2
    (đọc-2-lần) + lời dẫn + pause theo lịch Cambridge PET → 1 file. Encode MP3 (lameenc) nếu có,
    fallback WAV. TTS có cache per-chunk + retry/backoff 429/503 free-tier.

    Thời lượng ~17' (calibrate S54 cho giọng Gemini đo ~210wpm: L1 115 từ / L2 360 từ + pause 441s →
    ~17.1', band 16-18' ở 190-230wpm; GV kiểm duration_s). Trả {audio_path, wav_path, mp3_path, duration_s, format, n_segments}."""
    tr = item.get("transcripts") or {}
    l1 = tr.get("l1") or []
    l2 = tr.get("l2") or ""
    code = item.get("lis_item", {}).get("code", "lis")
    cache_dir = os.path.join(out_dir, "_tts_cache")
    plan = _build_listening_segments(l1, l2)

    rendered, n_audio = [], 0
    for kind, val in plan:
        if kind == "silence":
            rendered.append(("silence", val))
        else:
            text, speakers = val
            rendered.append(("audio", _lis_tts_cached(generator, text, cache_dir, speakers)))
            n_audio += 1

    final_wav = os.path.join(out_dir, f"{code}.wav")
    assemble_wav_segments(rendered, final_wav)
    with wave.open(final_wav, "rb") as w:
        duration = w.getnframes() / float(w.getframerate())

    result = {"audio_path": final_wav, "wav_path": final_wav, "mp3_path": None,
              "duration_s": round(duration, 1), "format": "wav", "n_segments": n_audio}
    if to_mp3:
        mp3 = wav_to_mp3(final_wav)
        if mp3:
            result.update({"audio_path": mp3, "mp3_path": mp3, "format": "mp3"})
    return result


def _lis_image(generator, prompt: str, output_path: str) -> str:
    """Sinh 1 ảnh PNG qua Gemini image (real-mode, atomic write). Raise nếu lỗi/không có ảnh.
    Lazy-import google types (core không phụ thuộc SDK). Model = IMAGE_MODEL (configurable qua env)."""
    from google.genai import types  # noqa: PLC0415
    client = getattr(generator, "client", None)
    if client is None:
        raise RuntimeError("Gemini client chưa khởi tạo (cần GEMINI_API_KEY) cho image.")
    resp = client.models.generate_content(
        model=IMAGE_MODEL, contents=prompt,
        config=types.GenerateContentConfig(response_modalities=["IMAGE"]))
    data = None
    for c in (resp.candidates or []):
        for p in ((c.content.parts if c.content else None) or []):
            if p.inline_data and str(p.inline_data.mime_type or "").startswith("image/"):
                data = p.inline_data.data
                break
    if data is None:
        raise ValueError("Không có phần ảnh trong phản hồi Gemini image.")
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    tmp = f"{output_path}.tmp{os.getpid()}"          # atomic (như _lis_tts) → không lưu ảnh ghi-dở
    try:
        with open(tmp, "wb") as f:
            f.write(data)
        os.replace(tmp, output_path)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise
    return output_path


_IMG_BILLING_HINT = ("429/IPM: free-tier API image = 0 IPM (từ ~12/2025) — PHẢI bật BILLING "
                     "($0-limit OK) → Tier 1 mới sinh ảnh. Retry KHÔNG cứu (khác 503 text).")


def build_listening_images(generator, item: dict, out_dir: str) -> dict:
    """Sinh 3 ảnh A/B/C (từ options text) cho MỖI câu L1 → PNG `<code>_L1q<n>_<K>.png`. GRACEFUL:
    1 ảnh lỗi → skip + đếm, KHÔNG crash cả bài; 429/IPM (free-tier=0) → log gợi ý billing, KHÔNG retry.
    Cập nhật transcripts.l1[j].image_urls + lis_item.media_ext.l1_images + image_status.
    Trả {n_images, n_failed, needs_billing}."""
    tr = item.get("transcripts") or {}
    l1 = tr.get("l1") if isinstance(tr.get("l1"), list) else []
    li = item.get("lis_item") or {}
    code = li.get("code", "lis")
    os.makedirs(out_dir, exist_ok=True)
    manifest, n_ok, n_fail, billing = [], 0, 0, False
    for j, q in enumerate(l1, 1):
        q = q if isinstance(q, dict) else {}
        opts = q.get("options") if isinstance(q.get("options"), dict) else {}
        files = {}
        for key in L1_OPTION_KEYS:      # A, B, C
            text = str(opts.get(key) or "").strip()
            if not text:
                continue
            fn = f"{code}_L1q{j}_{key}.png"
            try:
                _lis_image(generator, build_lis_image_prompt(text), os.path.join(out_dir, fn))
                files[key] = fn
                n_ok += 1
            except Exception as e:
                n_fail += 1
                if any(t in str(e).lower() for t in ("429", "ipm", "quota", "resource_exhausted")):
                    billing = True
                    logger.error("Ảnh L1 %s — %s (%s)", fn, _IMG_BILLING_HINT, e)
                else:
                    logger.warning("Ảnh L1 %s lỗi: %s", fn, e)
        # image_urls chỉ điền khi ĐỦ 3 ảnh A/B/C (frontend chọn-tranh cần đủ 3); thiếu → "" (render
        # fallback placeholder, tránh chuỗi 'A,,C' lệch). manifest LUÔN ghi ảnh đã có để GV soát ảnh nào thiếu.
        q["image_urls"] = (",".join(files[k] for k in L1_OPTION_KEYS)
                           if len(files) == len(L1_OPTION_KEYS) else "")
        if files:
            manifest.append({"q": j, **files})
    li.setdefault("media_ext", {})["l1_images"] = manifest
    li["image_status"] = ("images_generated" if n_fail == 0 and n_ok > 0
                          else "partial" if n_ok > 0 else "pending_image")
    li["needs_image_verify"] = not (n_fail == 0 and n_ok > 0)     # đồng bộ với image_status
    if billing:
        li.setdefault("flags", []).append("needs_billing")        # persist vào JSON (không chỉ stdout)
    return {"n_images": n_ok, "n_failed": n_fail, "needs_billing": billing}


# ======================================================================
# SLICE KIỂM ĐÁP ÁN — SPEC-FACTORY-014
# ----------------------------------------------------------------------
# Cổng "AI kiểm AI" NGỮ NGHĨA (bổ trợ QC cấu trúc qc_r*): với mỗi item R1/R2/R3/R4,
# gọi Gemini GIẢI ĐỘC LẬP câu hỏi (KHÔNG cho biết đáp án ta gắn → không anchor/nịnh)
# rồi SO BẰNG CODE với đáp án ta gắn. Khớp = PASS · lệch / checker chọn ngoài phương án
# (nghi ảo giác) / mơ hồ / lỗi = gắn cờ SUSPECT cho GV. KHÔNG tự xoá — GV vẫn là cổng cuối
# (cùng-model có thể chung điểm mù → PASS vẫn cần GV chấm mẫu). Additive: chỉ THÊM field
# answer_verify (+ answer_verify_flag khi nghi), KHÔNG sửa build_*/export/qc. W1/W2/Nói/Nghe
# KHÔNG có đáp án đóng duy nhất → BỎ QUA. Grounded: giảm ảo giác (yêu cầu #1 sếp) + giảm tải GV (D4).

CHECKER_MAX_OUTPUT_TOKENS = 4096   # reasoning nằm ở OUTPUT field (không cần thinking lớn)
CHECKER_THINKING_BUDGET = 512      # thinking nhỏ để nhường chỗ output (SPEC-FACTORY-013)

_CHECKER_SYSTEM = (
    "You are a meticulous VSTEP B1 (CEFR B1) English test reviewer. A colleague drafted the exam "
    "item below. Do NOT assume it is correct. Independently work out the answer YOURSELF from the "
    "item alone. Use ONLY the text/options (and passage/word box if given) — do NOT rely on outside "
    "facts. Reason step by step FIRST; if something feels off, recheck before deciding. Always commit "
    "to the SINGLE BEST option. Use ambiguity_note ONLY if two or more options are EQUALLY correct as "
    "the best answer — NOT for an option that is merely grammatically possible but clearly weaker. Return "
    "ONLY JSON with fields IN THIS ORDER: {\"reasoning\": str, \"derived_answer\": <as instructed>, "
    "\"confidence\": <0-100 integer>, \"ambiguity_note\": str}."
)


def _solve_mcq(generator, stem, options: dict, passage=None) -> dict:
    """Gemini GIẢI ĐỘC LẬP 1 câu MCQ → {ok, letter, confidence, ambiguity} | {ok:False, error}. Graceful."""
    opt_keys = sorted(options.keys())
    opts_txt = "\n".join(f"{k}. {options[k]}" for k in opt_keys)
    ctx = (f"Read the passage, then answer BASED ONLY ON THE PASSAGE.\nPassage:\n{passage}\n\n"
           if passage else "")
    user = (f"{ctx}Question:\n{stem}\n{opts_txt}\n\nIndependently choose the single correct option. "
            f"derived_answer must be EXACTLY one of these letters: {', '.join(opt_keys)}.")
    try:
        raw = generator._call_gemini(_CHECKER_SYSTEM, user,
                                     max_output_tokens=CHECKER_MAX_OUTPUT_TOKENS,
                                     thinking_budget=CHECKER_THINKING_BUDGET)
        data = _loads_lenient(raw)
    except Exception as e:
        return {"ok": False, "error": str(e)}
    if not isinstance(data, dict):
        return {"ok": False, "error": "checker JSON không phải object"}
    letter = str(data.get("derived_answer") or "").strip().upper()[:1]
    return {"ok": True, "letter": letter, "confidence": data.get("confidence"),
            "ambiguity": str(data.get("ambiguity_note") or "").strip()}


def _mcq_verdict(generator, stem, options: dict, marked, passage=None) -> dict:
    """answer_verify cho 1 MCQ: solve độc lập + so với 'marked' (đáp án ta gắn). Không gọi mạng nếu thiếu field."""
    if not stem or not isinstance(options, dict) or not options or not marked:
        return {"checked": False, "agree": False, "checker_answer": None, "confidence": None,
                "note": "item thiếu stem/options/answer — không kiểm được", "checker_call_error": None}
    r = _solve_mcq(generator, stem, options, passage)
    if not r.get("ok"):
        return {"checked": False, "agree": False, "checker_answer": None, "confidence": None,
                "note": "checker lỗi/không parse được", "checker_call_error": r.get("error")}
    letter = r["letter"]
    conf = r.get("confidence")
    if letter not in options:      # guard checker ảo giác: chọn phương án KHÔNG tồn tại → nghi
        return {"checked": True, "agree": False, "checker_answer": letter or None, "confidence": conf,
                "note": f"checker chọn {letter!r} KHÔNG thuộc phương án — nghi checker ảo giác",
                "checker_call_error": None}
    agree = letter == str(marked).strip().upper()[:1]
    note = "khớp đáp án đã gắn" if agree else f"checker chọn {letter}, ta gắn {marked}"
    if r.get("ambiguity"):
        # Ambiguity chỉ GHI CHÚ cho GV, KHÔNG tự flag khi đã KHỚP letter. ĐO THẬT (S55b, bộ B1 curated):
        # ép agree=False ở đây làm false-positive 50% (model hay hedge "phương án khác cũng được" dù đã
        # chọn ĐÚNG letter) → ngập GV. SUSPECT chỉ dành cho LỆCH letter / checker ngoài phương án / lỗi;
        # GV vẫn thấy lưu ý trong note. Recall giữ 100% (đáp án sai = lệch letter → vẫn flag).
        note += f" · checker lưu ý có phương án khác đáng cân nhắc: {r['ambiguity'][:70]}"
    return {"checked": True, "agree": agree, "checker_answer": letter, "confidence": conf,
            "note": note, "checker_call_error": None}


def _verify_r1_item(item, generator) -> dict:
    s = item.get("s1_item") or {}
    return _mcq_verdict(generator, s.get("stem"), s.get("options") or {}, s.get("answer"))


def _verify_r2_item(item, generator) -> dict:
    s = item.get("s2_item") or {}
    return _mcq_verdict(generator, s.get("stem"), s.get("options") or {}, s.get("answer"))


def _verify_r3_item(item, generator) -> dict:
    """R3: kiểm TỪNG câu hỏi kèm passage (đáp án phụ thuộc đoạn văn). Item nghi nếu BẤT KỲ câu lệch/lỗi."""
    s3 = item.get("s3_item") or {}
    passage = str(s3.get("passage") or "")
    ctx = passage if len(passage) <= 2000 else passage[:1800] + "..."   # chặn token cho đoạn dài
    qs = s3.get("questions") or []
    if not qs:
        return {"checked": False, "agree": False, "checker_answer": None, "confidence": None,
                "note": "R3 không có câu hỏi", "checker_call_error": None}
    per_q, all_agree, any_err = [], True, None
    for idx, q in enumerate(qs, 1):
        v = _mcq_verdict(generator, q.get("stem"), q.get("options") or {}, q.get("answer"), passage=ctx)
        per_q.append({"q": idx, "checker": v.get("checker_answer"), "ours": q.get("answer"),
                      "agree": v.get("agree"), "note": v.get("note")})
        if not v.get("checked"):
            any_err = v.get("checker_call_error") or any_err
        all_agree = all_agree and v.get("checked") and v.get("agree")
    return {"checked": True, "agree": bool(all_agree), "checker_answer": per_q, "confidence": None,
            "note": ("tất cả câu khớp" if all_agree else "có câu lệch/nghi/lỗi — xem chi tiết"),
            "checker_call_error": any_err}


def _r4_passage_from_raw(s4_raw: list) -> str:
    """Tái tạo passage-có-chỗ-trống từ s4_raw (bỏ header/hướng dẫn cố định + block tbl hộp từ)."""
    return "\n".join(str(b.get("text") or "") for b in s4_raw
                     if b.get("kind") == "p" and b.get("text") not in (R4_HEADER, R4_INSTRUCTION))


def _verify_r4_item(item, generator) -> dict:
    """R4 cloze: checker điền MỌI chỗ từ hộp → so từng chỗ (chuẩn hoá hoa/thường) + KIỂM ∈ hộp từ.
    KHÔNG tự nhận synonym: checker điền từ khác (dù hợp nghĩa) → lệch → nghi (GV quyết, tránh sai âm thầm)."""
    box = [str(w) for w in (item.get("word_box") or [])]
    marked = {str(k): str(v) for k, v in (item.get("answers") or {}).items()}
    if not box or not marked:
        return {"checked": False, "agree": False, "checker_answer": None, "confidence": None,
                "note": "item R4 thiếu hộp từ/đáp án", "checker_call_error": None}
    box_norm = {_norm_topic(w) for w in box}
    passage = _r4_passage_from_raw((item.get("s4_item") or {}).get("s4_raw") or [])
    user = (f"Fill EACH numbered blank in the passage with EXACTLY ONE word from the word box.\n"
            f"Passage:\n{passage}\n\nWord box: {' '.join(box)}\n\n"
            "derived_answer must be a JSON object mapping each blank number (string) to one box word.")
    try:
        raw = generator._call_gemini(_CHECKER_SYSTEM, user,
                                     max_output_tokens=CHECKER_MAX_OUTPUT_TOKENS,
                                     thinking_budget=CHECKER_THINKING_BUDGET)
        data = _loads_lenient(raw)
    except Exception as e:
        return {"checked": False, "agree": False, "checker_answer": None, "confidence": None,
                "note": "checker lỗi/không parse được", "checker_call_error": str(e)}
    derived = data.get("derived_answer") if isinstance(data, dict) else None
    if not isinstance(derived, dict):
        return {"checked": False, "agree": False, "checker_answer": None, "confidence": None,
                "note": "checker không trả dict đáp án", "checker_call_error": None}
    per_blank, all_agree = {}, True
    for k, our in marked.items():
        cw = str(derived.get(k) or "").strip()
        cw_norm = _norm_topic(cw)
        in_box = cw_norm in box_norm
        agree = bool(cw) and in_box and cw_norm == _norm_topic(our)
        per_blank[k] = {"checker": cw, "ours": our, "agree": agree,
                        "note": ("" if agree else ("ngoài hộp từ (nghi ảo giác)" if (cw and not in_box)
                                                   else "lệch/synonym"))}
        all_agree = all_agree and agree
    return {"checked": True, "agree": bool(all_agree), "checker_answer": per_blank,
            "confidence": (data.get("confidence") if isinstance(data, dict) else None),
            "note": ("mọi chỗ khớp" if all_agree else "có chỗ lệch/ngoài hộp — xem chi tiết"),
            "checker_call_error": None}


# Các skill (tên bundle) có đáp án đóng → kiểm được bằng cổng. W/Nói/Nghe KHÔNG (ngoài phạm vi).
VERIFY_SUPPORTED_SKILLS = ("reading_s1", "reading_s2_notice", "reading_s3_comprehension", "reading_s4_cloze")

_VERIFY_DISPATCH = {
    "reading_s1": _verify_r1_item, "r1": _verify_r1_item,
    "reading_s2_notice": _verify_r2_item, "r2": _verify_r2_item,
    "reading_s3_comprehension": _verify_r3_item, "r3": _verify_r3_item,
    "reading_s4_cloze": _verify_r4_item, "r4": _verify_r4_item,
}


def verify_bundle_answers(items: list, skill: str, generator=None) -> list:
    """Cổng kiểm đáp án AI (SPEC-FACTORY-014). Với mỗi item: solve độc lập + so đáp án → gắn
    answer_verify (+ answer_verify_flag='SUSPECT' khi nghi). ADDITIVE + KHÔNG tự xoá (GV quyết).
    generator=None/không client → MOCK (coi như đồng thuận, chỉ test plumbing). skill ngoài R1-R4
    (W/Nói/Nghe) → đánh dấu 'không có đáp án đóng' + KHÔNG cờ. Trả về chính items (đã mutate)."""
    fn = _VERIFY_DISPATCH.get(str(skill or "").strip().lower())
    use_mock = generator is None or getattr(generator, "client", None) is None
    for it in items:
        if fn is None:                 # W1/W2/Nói/Nghe: không có đáp án đóng duy nhất → ngoài phạm vi
            it["answer_verify"] = {"checked": False, "agree": False, "checker_answer": None,
                                   "confidence": None, "note": f"skill {skill!r} không có đáp án đóng "
                                   "duy nhất — GV soát tay", "checker_call_error": None}
            it.pop("answer_verify_flag", None)
            continue
        if use_mock:
            av = {"checked": True, "agree": True, "checker_answer": None, "confidence": None,
                  "note": "mock (offline) — không gọi checker thật", "checker_call_error": None}
        else:
            try:
                av = fn(it, generator)
            except Exception as e:     # lưới cuối: 1 item lỗi KHÔNG làm hỏng cả lô
                logger.warning("verify item lỗi (%s): %s", it.get("nguon_seed"), e)
                av = {"checked": False, "agree": False, "checker_answer": None, "confidence": None,
                      "note": "lỗi khi kiểm", "checker_call_error": str(e)}
        it["answer_verify"] = av
        if av.get("checked") and av.get("agree"):
            it.pop("answer_verify_flag", None)
        else:
            it["answer_verify_flag"] = "SUSPECT"      # lệch / chưa kiểm được / mơ hồ → GV soát
    return items


def verify_cell(item) -> str:
    """Ô 'Kiểm đáp án AI' cho bảng GV (rỗng nếu chưa bật kiểm)."""
    av = item.get("answer_verify")
    if not av:
        return ""
    if not av.get("checked"):
        return "CHƯA KIỂM"
    return "PASS" if av.get("agree") else "⚠ NGHI"


def verify_report(items: list) -> str:
    """Báo cáo kiểm đáp án (Markdown): liệt kê item NGHI để GV soát TRƯỚC (giảm tải). PASS chỉ là gợi ý."""
    flagged = [it for it in items if it.get("answer_verify_flag") == "SUSPECT"]
    n_checked = sum(1 for it in items if (it.get("answer_verify") or {}).get("checked"))
    n_pass = sum(1 for it in items if (it.get("answer_verify") or {}).get("agree"))
    lines = [
        f"# Kiểm đáp án AI (SPEC-FACTORY-014) — {len(flagged)} NGHI / {len(items)} item "
        f"(kiểm được {n_checked}, PASS {n_pass})",
        "",
        "GV BẮT BUỘC soát kỹ các item NGHI dưới đây (AI-solve lệch / mơ hồ / nghi checker ảo giác / "
        "lỗi). PASS chỉ là GỢI Ý — cùng-model có thể chung điểm mù nên GV vẫn nên chấm MẪU. Cổng cuối là GV.",
        "",
    ]
    if not flagged:
        lines.append("_Không có item NGHI (mọi item checker đồng thuận, hoặc chưa bật kiểm)._")
        return "\n".join(lines)
    lines += ["| # | Nguồn seed | Vì sao NGHI |", "|---|---|---|"]
    for i, it in enumerate(flagged, 1):
        av = it.get("answer_verify") or {}
        why = f"chưa kiểm được (lỗi checker: {av['checker_call_error'][:50]})" if av.get("checker_call_error") \
            else (av.get("note") or "?")
        lines.append(f"| {i} | {it.get('nguon_seed', '?')} | {str(why).replace('|', '/')[:100]} |")
    return "\n".join(lines)
