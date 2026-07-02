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
import re
import unicodedata
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
