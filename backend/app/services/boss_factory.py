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
