"""SPEC-FACTORY-* — Nhà máy sinh câu B1 xuất ĐÚNG định dạng ngân hàng của đối tác (bàn giao).

Định hướng S52: việc mình = mở rộng ngân hàng của sếp (không phải generate đề). Slice P1-R1:
paraphrase câu Đọc phần 1 (R1) từ đề thật của đối tác → shape s1 {stem, options{A-D}, answer}.
Slice P3-NÓI: paraphrase part2_topic từ pool_speak.json → shape thẻ Nói (7 field).
Test dùng seed TỔNG HỢP + mock tất định (không gọi Gemini/mạng).
"""
import json

from app.services import boss_factory


class _StubGen:
    """Generator giả (song song B1QuestionGenerator): có `client` truthy → đi nhánh REAL,
    nhưng `_call_gemini` trả payload CỐ ĐỊNH → test nhánh real tất định, không gọi mạng."""

    client = object()
    model_name = "stub"

    def __init__(self, payload: dict):
        self._payload = payload

    def _call_gemini(self, system_instruction: str, user_prompt: str) -> str:
        return json.dumps(self._payload, ensure_ascii=False)


def test_SPEC_FACTORY_001_r1_variants_boss_format():
    # Một record kiểu bank_raw.json của đối tác (2 câu R1 seed, shape s1 thật).
    bank = [{
        "ma_de": "EB1.2601",
        "s1": {
            "1": {"stem": "She ...... to school every day.",
                  "options": {"A": "go", "B": "goes", "C": "going", "D": "went"}, "answer": "B"},
            "2": {"stem": "Each of the players ...... over 200 pounds.",
                  "options": {"A": "weigh", "B": "weighs", "C": "were weighing", "D": "weights"},
                  "answer": "B"},
        },
    }]

    # AC1: trích seed R1 từ bank của đối tác.
    seeds = boss_factory.load_r1_seeds(bank)
    assert len(seeds) == 2
    assert seeds[0]["ma_de"] == "EB1.2601" and seeds[0]["answer"] == "B"
    assert sorted(seeds[0]["options"].keys()) == ["A", "B", "C", "D"]

    # AC2+AC3: sinh biến thể (mock tất định, generator=None) — đúng shape s1 + độ khó + truy vết.
    items = boss_factory.build_r1_variants(seeds, per_seed=2, generator=None)
    assert len(items) == 4
    for it in items:
        s = it["s1_item"]
        assert set(s.keys()) == {"stem", "options", "answer"}            # ĐÚNG 3 field s1
        assert sorted(s["options"].keys()) == ["A", "B", "C", "D"]       # 4 phương án
        assert s["answer"] in s["options"]
        assert s["stem"] and s["stem"] != it["seed_stem"]                # KHÁC nguyên văn (bản quyền)
        assert it["do_kho"] in ("Dễ", "TB", "Khó")                       # nhãn độ khó cho quota
        assert it["nguon_seed"].startswith("EB1.2601#Q")                 # truy vết seed
        assert it["qc_ok"] is True                                       # QC đạt

    # AC4: qc_r1 bắt lỗi item hỏng.
    bad = {"stem": "x", "options": {"A": "a", "B": "b", "C": "c"}, "answer": "D"}  # thiếu D + answer ngoài
    issues = boss_factory.qc_r1(bad, seeds[0])
    assert any("A,B,C,D" in i for i in issues)
    assert any("answer" in i for i in issues)
    dup = {"stem": seeds[0]["stem"], "options": seeds[0]["options"], "answer": seeds[0]["answer"]}
    assert any("nguyên văn" in i for i in boss_factory.qc_r1(dup, seeds[0]))

    # AC5: gói bàn giao + bảng GV soát/ký.
    bundle = boss_factory.export_bundle(items)
    assert bundle["skill"] == "reading_s1" and bundle["count"] == 4
    assert bundle["count_qc_ok"] == 4
    assert bundle["items"] == items
    sheet = boss_factory.review_sheet(items)
    assert "GV duyệt" in sheet and "Nguồn seed" in sheet
    assert sheet.count("\n") >= 4  # header + >=4 dòng biến thể


def test_SPEC_FACTORY_002_speak_variants_boss_format():
    # pool_speak.json của đối tác là DICT thẻ (KHÁC bank_raw của R1 là LIST). 7 field/thẻ.
    pool = {
        "SB1.2601": {
            "code": "SB1.2601", "src_code": "SB1.2601", "set_file": "SB1_2601.docx",
            "part2_topic": "Describe a hobby you enjoy in your free time.",
            "domain_guess": "Vui chơi-giải trí",
            "part1": ["Where are you from?", "Do you work or study?"],
            "part3": "Discuss the importance of leisure activities in modern life.",
        },
        "SB1.2602": {
            "code": "SB1.2602", "src_code": "SB1.2602", "set_file": "SB1_2602.docx",
            "part2_topic": "Talk about a memorable trip you have taken.",
            "domain_guess": "Đi lại-du lịch",
            "part1": ["What is your name?", "Where do you live?"],
            "part3": "Discuss how travelling affects people's view of other cultures.",
        },
    }

    # AC1: trích seed Nói từ pool DICT của đối tác (duyệt .values(), giữ 7 field).
    seeds = boss_factory.load_speak_seeds(pool)
    assert len(seeds) == 2
    assert seeds[0]["code"] == "SB1.2601"
    assert seeds[0]["domain_guess"] == "Vui chơi-giải trí"
    assert seeds[0]["part1"] and seeds[0]["part3"]

    # AC2+AC3: sinh biến thể (mock tất định, generator=None) — shape pool_speak thuần + metadata.
    items = boss_factory.build_speak_variants(seeds, per_seed=2, generator=None)
    assert len(items) == 4
    real_codes = set(pool.keys())
    seeds_by_code = {s["code"]: s for s in seeds}
    seen_new_codes = set()
    for it in items:
        c = it["speak_card"]
        assert set(c.keys()) == set(boss_factory.SPEAK_CARD_FIELDS)         # ĐÚNG 7 field pool_speak
        assert c["part2_topic"] and c["part2_topic"] != it["seed_part2_topic"]  # KHÁC seed (bản quyền)
        assert c["domain_guess"] in boss_factory.DOMAINS_14                 # domain hợp lệ (∈14)
        src = seeds_by_code[c["src_code"]]                                  # neo về seed gốc qua src_code
        assert c["part1"] == src["part1"]                                  # GIỮ NGUYÊN part1 của seed (không tráo)
        assert c["part3"] == src["part3"]                                  # GIỮ NGUYÊN part3 của seed
        assert c["code"].startswith("SB1.90-")                             # code thuộc dải mở rộng (không đụng thật)
        assert c["code"] not in real_codes                                 # KHÔNG đụng code seed thật
        assert c["code"] not in seen_new_codes                             # code sinh là duy nhất
        seen_new_codes.add(c["code"])
        assert c["src_code"] in real_codes                                 # truy vết grounded về seed
        assert it["do_kho"] in ("Dễ", "TB", "Khó")                         # nhãn độ khó (metadata)
        assert it["nguon_seed"].startswith("SB1.26")                       # truy vết seed
        assert it["qc_ok"] is True                                         # QC đạt (mock đa dạng → 0 near-dup)

    # AC4: qc_speak bắt lỗi thẻ hỏng.
    good_seed = seeds[0]
    base_card = items[0]["speak_card"]
    assert any("rỗng" in i for i in boss_factory.qc_speak({**base_card, "part2_topic": ""}, good_seed))
    assert any("14 chủ đề" in i for i in boss_factory.qc_speak({**base_card, "domain_guess": "XYZ"}, good_seed))
    dup = {**base_card, "part2_topic": good_seed["part2_topic"]}
    assert any("nguyên văn" in i for i in boss_factory.qc_speak(dup, good_seed))
    assert any("part3" in i for i in boss_factory.qc_speak({**base_card, "part3": ""}, good_seed))

    # AC4b: domain khoan dung định dạng (dấu/hyphen/space) — thẻ grounded KHÔNG bị QC oan,
    # nhưng domain BỊA thì vẫn bắt.
    drift = {**base_card, "domain_guess": "Vui chơi - giải trí"}           # lệch spacing quanh hyphen
    assert not any("14 chủ đề" in i for i in boss_factory.qc_speak(drift, good_seed))
    assert any("14 chủ đề" in i
               for i in boss_factory.qc_speak({**base_card, "domain_guess": "Chủ đề bịa"}, good_seed))

    # AC-dedup (non-tautology): nhánh REAL (_StubGen) trả CÙNG topic 2 lần → thẻ thứ 2 near-dup.
    stub = _StubGen({"part2_topic": "Talk about a sport you like watching.", "difficulty": "medium"})
    dupd = boss_factory.build_speak_variants(seeds[:1], per_seed=2, generator=stub)
    assert len(dupd) == 2
    assert dupd[0]["qc_ok"] is True                                        # thẻ đầu sạch
    assert any("near-duplicate" in i for i in dupd[1]["qc_issues"])        # thẻ 2 bị bắt near-dup
    assert dupd[0]["speak_card"]["domain_guess"] == "Vui chơi-giải trí"    # domain giữ của seed (không bịa)

    # Regression (review finding): 2 seed CÙNG domain trong mock KHÔNG bị near-dup oan
    # (mock nhúng part2_topic của seed → topic khác nhau dù cùng domain).
    same_domain = [
        {"code": "SB1.2611", "src_code": "SB1.2611", "set_file": "a.docx",
         "part2_topic": "Describe a game you often play with your friends.",
         "domain_guess": "Vui chơi-giải trí", "part1": ["Q1?"], "part3": "P3 a."},
        {"code": "SB1.2612", "src_code": "SB1.2612", "set_file": "b.docx",
         "part2_topic": "Talk about a concert or show you attended last year.",
         "domain_guess": "Vui chơi-giải trí", "part1": ["Q2?"], "part3": "P3 b."},
    ]
    sd_items = boss_factory.build_speak_variants(same_domain, per_seed=1, generator=None)
    assert len(sd_items) == 2
    assert all(it["qc_ok"] for it in sd_items)                             # cùng domain, base khác → 0 near-dup oan

    # AC5: gói bàn giao + bảng GV soát/ký.
    bundle = boss_factory.export_speak_bundle(items)
    assert bundle["skill"] == "speaking" and bundle["count"] == 4
    assert bundle["count_qc_ok"] == 4
    assert bundle["items"] == items
    sheet = boss_factory.speak_review_sheet(items)
    assert "GV duyệt" in sheet and "Domain" in sheet and "part2_topic" in sheet
    assert sheet.count("\n") >= 4


def test_SPEC_FACTORY_003_r4_cloze_variants_boss_format():
    # bank_raw.json thật: s4_raw = list block (tbl = HỘP TỪ) + s4_answers 21-30.
    # (Đáp án "Both" viết hoa vs hộp từ "both" thường — quirk THẬT của đối tác.)
    bank = [
        {
            "ma_de": "EB1.2601",
            "s4_raw": [
                {"kind": "p", "text": "Section 4 Questions 21-30 (10 points)"},
                {"kind": "p", "text": "Read the text below and fill each of the blanks with ONE suitable word from the box."},
                {"kind": "tbl", "text": "frighten where must most search weigh left both spend fact all which waste have heavy"},
                {"kind": "p", "text": "THE GORILLA"},
                {"kind": "p", "text": "The gorilla is shy. In (21) ...... it wants to (22) ...... an enemy. It is the (23) ...... powerful ape and can (24) ...... a lot. (25) ...... sexes are strong; they (26) ...... days in a (27) ...... for food. Few are (28) ...... where (29) ...... they live, so we (30) ...... act now."},
            ],
            "s4_answers": {"21": "fact", "22": "frighten", "23": "most", "24": "weigh",
                           "25": "Both", "26": "spend", "27": "search", "28": "left",
                           "29": "which", "30": "must"},
        },
        {
            "ma_de": "EB1.2602",
            "s4_raw": [
                {"kind": "p", "text": "Section 4 Questions 21-30 (10 points)"},
                {"kind": "tbl", "text": "since because money learn friend often early water quiet plan visit help study rain travel"},
                {"kind": "p", "text": "MY WEEK"},
                {"kind": "p", "text": "I (21) ...... English (22) ...... I want to (23) ...... abroad. I (24) ...... start (25) ...... to save (26) ...... , (27) ...... a (28) ...... place to (29) ...... and (30) ...... hard."},
            ],
            "key_cloze": {"21": "learn", "22": "because", "23": "travel", "24": "often",
                          "25": "early", "26": "money", "27": "visit", "28": "quiet",
                          "29": "study", "30": "plan"},
        },
    ]

    # AC1: trích seed R4 — hộp từ (từ block tbl) + passage + đáp án 21-30.
    seeds = boss_factory.load_r4_seeds(bank)
    assert len(seeds) == 2
    assert len(seeds[0]["box"]) == 15 and "both" in seeds[0]["box"]
    assert seeds[0]["answers"]["25"] == "Both"                             # giữ nguyên hoa/thường của đối tác
    assert "THE GORILLA" in seeds[0]["passage"]
    seeds_by_ma = {s["ma_de"]: s for s in seeds}

    # AC2+AC3: sinh biến thể (mock tất định) — s4_item đúng shape đối tác + đáp án ∈ hộp.
    items = boss_factory.build_r4_variants(seeds, per_seed=1, generator=None)
    assert len(items) == 2
    for it in items:
        s4 = it["s4_item"]
        assert set(s4.keys()) == {"s4_raw", "s4_answers", "key_cloze"}
        assert s4["s4_answers"] == s4["key_cloze"]                         # 2 khóa đáp án khớp
        assert set(s4["s4_answers"].keys()) == set(boss_factory.R4_BLANK_KEYS)  # đủ 21-30
        assert any(b["kind"] == "tbl" for b in s4["s4_raw"])              # có block hộp từ
        box_norm = {boss_factory._norm_word(w) for w in it["word_box"]}
        assert all(boss_factory._norm_word(v) in box_norm for v in it["answers"].values())  # đáp án ∈ hộp
        # passage sinh ra KHÁC nguyên văn passage seed (non-tautology, chống copy)
        tbl_i = next(i for i, b in enumerate(s4["s4_raw"]) if b["kind"] == "tbl")
        prod_passage = "\n".join(b["text"] for b in s4["s4_raw"][tbl_i + 1:] if b["kind"] == "p")
        assert prod_passage.strip() != seeds_by_ma[it["nguon_seed"]]["passage"].strip()
        assert it["nguon_seed"].startswith("EB1.26")                      # truy vết seed
        assert it["do_kho"] in ("Dễ", "TB", "Khó")
        assert it["qc_ok"] is True                                        # 2 seed khác → không near-dup oan

    # AC4: qc_r4 bắt lỗi cloze hỏng.
    good = seeds[0]
    ok_variant = {"passage": " ".join(f"({n}) ______" for n in boss_factory.R4_BLANK_KEYS),
                  "word_box": list(good["box"]), "answers": dict(good["answers"])}
    assert boss_factory.qc_r4(ok_variant, good) == []                     # baseline hợp lệ
    # (a) đáp án ngoài hộp từ (cổng kiem_hop_tu)
    bad_box = {**ok_variant, "answers": {**good["answers"], "21": "zzznotinbox"}}
    assert any("hộp từ" in i for i in boss_factory.qc_r4(bad_box, good))
    # (b) passage thiếu chỗ trống
    bad_blank = {**ok_variant, "passage": " ".join(f"({n}) ______" for n in boss_factory.R4_BLANK_KEYS[:-1])}
    assert any("chỗ trống" in i for i in boss_factory.qc_r4(bad_blank, good))
    # (c) thiếu/thừa đáp án
    bad_count = {**ok_variant, "answers": {k: good["answers"][k] for k in boss_factory.R4_BLANK_KEYS[:9]}}
    assert any("10 chỗ" in i for i in boss_factory.qc_r4(bad_count, good))
    # (d) đáp án lặp
    dup_ans = dict(good["answers"])
    dup_ans["22"] = dup_ans["21"]
    assert any("lặp lại" in i for i in boss_factory.qc_r4({**ok_variant, "answers": dup_ans}, good))
    # (e) chỗ trống LẶP trong passage ((21) hai lần) — cổng dùng multiset, không phải set
    dup_blank = {**ok_variant, "passage": "(21) ______ " + " ".join(f"({n}) ______" for n in boss_factory.R4_BLANK_KEYS)}
    assert any("chỗ trống" in i for i in boss_factory.qc_r4(dup_blank, good))
    # (f) chỗ trống THỪA ((31))
    extra_blank = {**ok_variant, "passage": " ".join(f"({n}) ______" for n in boss_factory.R4_BLANK_KEYS) + " (31) ______"}
    assert any("chỗ trống" in i for i in boss_factory.qc_r4(extra_blank, good))
    # (g) trùng nguyên văn passage seed (bản quyền) — non-tautology cho nhánh copyright
    dup_passage = {"passage": good["passage"], "word_box": list(good["box"]), "answers": dict(good["answers"])}
    assert any("nguyên văn" in i for i in boss_factory.qc_r4(dup_passage, good))

    # AC4b: cổng kiem_hop_tu KHÔNG phân biệt hoa/thường (quirk 'Both' vs 'both' của đối tác).
    case_variant = {**ok_variant, "answers": {**good["answers"], "21": "Fact"}}  # box có 'fact'
    assert not any("hộp từ" in i for i in boss_factory.qc_r4(case_variant, good))

    # Regression (review): mock per_seed=2 CÙNG seed KHÔNG near-dup oan (token duy nhất theo idx).
    multi = boss_factory.build_r4_variants(seeds[:1], per_seed=2, generator=None)
    assert len(multi) == 2 and all(it["qc_ok"] for it in multi)
    # Regression (review): 2 seed CÙNG hộp từ (per_seed=1) KHÔNG near-dup oan (token duy nhất theo seed).
    shared_box = "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu nu xi pi"
    ans10 = ["alpha", "beta", "gamma", "delta", "epsilon", "zeta", "eta", "theta", "iota", "kappa"]
    same_box_bank = [
        {"ma_de": f"EB1.270{j}", "s4_raw": [
            {"kind": "tbl", "text": shared_box},
            {"kind": "p", "text": f"Đoạn {j} " + " ".join(f"({n}) ______" for n in boss_factory.R4_BLANK_KEYS)}],
         "s4_answers": dict(zip(boss_factory.R4_BLANK_KEYS, ans10))}
        for j in (1, 2)
    ]
    sb_seeds = boss_factory.load_r4_seeds(same_box_bank)
    sb_items = boss_factory.build_r4_variants(sb_seeds, per_seed=1, generator=None)
    assert len(sb_items) == 2 and all(it["qc_ok"] for it in sb_items)

    # AC-dedup (non-tautology): nhánh REAL (_StubGen) trả CÙNG cloze 2 lần → cloze 2 near-dup.
    stub_cloze = {
        "title": "T",
        "passage": "Intro " + " ".join(f"({n}) ______" for n in boss_factory.R4_BLANK_KEYS) + " end.",
        "word_box": ["aa", "bb", "cc", "dd", "ee", "ff", "gg", "hh", "ii", "jj", "kk", "ll"],
        "answers": {n: w for n, w in zip(boss_factory.R4_BLANK_KEYS,
                                         ["aa", "bb", "cc", "dd", "ee", "ff", "gg", "hh", "ii", "jj"])},
        "difficulty": "medium",
    }
    dupd = boss_factory.build_r4_variants(seeds[:1], per_seed=2, generator=_StubGen(stub_cloze))
    assert len(dupd) == 2
    assert dupd[0]["qc_ok"] is True
    assert any("near-duplicate" in i for i in dupd[1]["qc_issues"])

    # AC5: gói bàn giao + bảng GV soát/ký.
    bundle = boss_factory.export_r4_bundle(items)
    assert bundle["skill"] == "reading_s4_cloze" and bundle["count"] == 2
    assert bundle["count_qc_ok"] == 2
    sheet = boss_factory.r4_review_sheet(items)
    assert "GV duyệt" in sheet and "Hộp từ" in sheet and "Đáp án" in sheet


# tbl s2 THẬT của EB1.2601 (3 thông báo 11-13) — dạng gộp "NN. <notice> A. .. B. .. C. .." của đối tác.
_R2_REAL_TBL = (
    "11. Wash dark colors separately at 40oC. Dry flat away from direct sunlight "
    "A. This must not be washed in water hotter than 40oC or hung up to dry. "
    "B. This can safely be washed with white things and dried outside in the sun. "
    "C. This should be dry cleaned and not washed even at a temperature of 40oC. "
    "12. Karen, This book is due back at the library today but if you want to read it, "
    "I will get it out for another week. Tracy. "
    "A. Tracy is asking Karen if she can borrow her library book. "
    "B. Tracy is telling Karen to take her book back to the library. "
    "C. Tracy is offering to let Karen read her library book. "
    "13. POSTCARD My time spent studying Greek has been well worth it! Everyone here in this "
    "Greek village understands me although they often talk too fast for me to understand Jessica "
    "A. Jessica is disappointed the Greek people cannot understand her. "
    "B. Jessica feels she did not spend enough time studying Greek. "
    "C. Jessica is pleased with her success in speaking Greek."
)


def test_SPEC_FACTORY_004_r2_notice_variants_boss_format():
    # bank_raw.json thật: s2_raw = block "tbl" gộp 5 thông báo; s2_answers = 3 lựa chọn A/B/C.
    bank = [{
        "ma_de": "EB1.2601",
        "s2_raw": [
            {"kind": "p", "text": "Section 2 Questions 11-15 (5 points)"},
            {"kind": "p", "text": "Look at the text in each question. What does it say? Circle the letter next to the correct explanation (A, B or C)."},
            {"kind": "tbl", "text": _R2_REAL_TBL},
        ],
        "s2_answers": {"11": "A", "12": "C", "13": "C"},
        "s2_has_image": False,
    }]

    # AC1: trích seed R2 — tách theo mốc 11-13, từng notice + đáp án A/B/C.
    seeds = boss_factory.load_r2_seeds(bank)
    assert len(seeds) == 3
    assert [s["num"] for s in seeds] == ["11", "12", "13"]
    assert seeds[0]["answer"] == "A" and seeds[1]["answer"] == "C"
    assert "Wash dark colors" in seeds[0]["notice"]                     # phần thông báo (trước A.)
    assert "A." not in seeds[0]["notice"]                               # đã cắt trước phương án A

    # AC2+AC3: sinh biến thể (mock tất định) — s2_item clean {stem, options{A,B,C}, answer}.
    items = boss_factory.build_r2_variants(seeds, per_seed=1, generator=None)
    assert len(items) == 3
    for it in items:
        s = it["s2_item"]
        assert set(s.keys()) == {"stem", "options", "answer"}
        assert sorted(s["options"].keys()) == ["A", "B", "C"]          # ĐÚNG 3 phương án
        assert s["answer"] in s["options"]
        assert s["stem"] and s["stem"] != it["seed_notice"]            # KHÁC nguyên văn seed
        assert it["nguon_seed"].startswith("EB1.2601#")               # truy vết seed (theo câu)
        assert it["do_kho"] in ("Dễ", "TB", "Khó")
        assert it["qc_ok"] is True                                     # notice khác nhau → 0 near-dup oan
        assert it["s2_raw_fragment"].startswith(it["nguon_seed"].split("#")[1] + ".")  # "11." đầu fragment
        assert " A. " in it["s2_raw_fragment"] and " B. " in it["s2_raw_fragment"]

    # AC4: qc_r2 bắt lỗi thông báo hỏng.
    good = seeds[0]
    base = items[0]["s2_item"]
    assert any("A,B,C" in i for i in boss_factory.qc_r2({**base, "options": {"A": "x", "B": "y"}}, good))  # thiếu C
    assert any("answer" in i for i in boss_factory.qc_r2({**base, "answer": "D"}, good))                    # answer ngoài
    dupopt = {**base, "options": {"A": "same", "B": "same", "C": "diff"}, "answer": "A"}
    assert any("trùng nội dung" in i for i in boss_factory.qc_r2(dupopt, good))
    copy = {"stem": good["notice"], "options": {"A": "a", "B": "b", "C": "c"}, "answer": "A"}
    assert any("nguyên văn" in i for i in boss_factory.qc_r2(copy, good))

    # AC-dedup (non-tautology): nhánh REAL (_StubGen) trả CÙNG stem 2 lần → thông báo 2 near-dup.
    stub = _StubGen({"stem": "No parking at any time on this street.",
                     "options": {"A": "You can park briefly.", "B": "Parking is never allowed here.",
                                 "C": "Parking costs money."}, "answer": "B", "difficulty": "easy"})
    dupd = boss_factory.build_r2_variants(seeds[:1], per_seed=2, generator=stub)
    assert len(dupd) == 2
    assert dupd[0]["qc_ok"] is True
    assert any("near-duplicate" in i for i in dupd[1]["qc_issues"])

    # Regression: mock per_seed=2 CÙNG seed KHÔNG near-dup oan (token duy nhất theo idx).
    multi = boss_factory.build_r2_variants(seeds[:1], per_seed=2, generator=None)
    assert len(multi) == 2 and all(it["qc_ok"] for it in multi)

    # Regression (review, verify data thật EB1.2605): số 11-15 trong THÂN câu SAU KHÔNG tách nhầm.
    embedded = [{
        "ma_de": "EB1.2605",
        "s2_raw": [{"kind": "tbl", "text":
            "11. No entry after 6 pm. A. Do not enter in the evening. B. Enter only after 6. C. Entry is free. "
            "12. Meeting moved to room 5. A. The room changed. B. The time changed. C. The meeting is off. "
            "13. Riding classes will no longer take place at 12. A. Classes stop at noon now. "
            "B. Classes moved earlier. C. Jane would be the only rider at 12, so she should come later."}],
        "s2_answers": {"11": "A", "12": "A", "13": "A"},
    }]
    emb = boss_factory.load_r2_seeds(embedded)
    assert [s["num"] for s in emb] == ["11", "12", "13"]                    # KHÔNG có seed rác num='12' từ "at 12."
    assert "Riding classes" in emb[2]["notice"]                             # câu 13 nguyên vẹn

    # Regression (review): ' A. ' trong THÂN thông báo (vd 'grade A.') KHÔNG cắt cụt notice.
    internal_a = [{
        "ma_de": "EB1.2699",
        "s2_raw": [{"kind": "tbl", "text":
            "11. You got grade A. This means you passed the exam. "
            "A. The student failed. B. The student passed. C. The exam was cancelled."}],
        "s2_answers": {"11": "B"},
    }]
    ia = boss_factory.load_r2_seeds(internal_a)
    assert len(ia) == 1 and "This means you passed the exam" in ia[0]["notice"]
    assert ia[0]["options"]["B"] == "The student passed."

    # Regression (review): fallback key_reading khi thiếu s2_answers — subset 11-15, bỏ key ngoài dải.
    kr_rec = [{
        "ma_de": "EB1.2698",
        "s2_raw": [{"kind": "tbl", "text":
            "11. Closed on Sunday. A. Open all week. B. Shut on Sundays. C. Open Sundays only."}],
        "key_reading": {"1": "A", "11": "B", "21": "fact"},
    }]
    kr = boss_factory.load_r2_seeds(kr_rec)
    assert len(kr) == 1 and kr[0]["num"] == "11" and kr[0]["answer"] == "B"

    # AC5: gói bàn giao + bảng GV soát/ký.
    bundle = boss_factory.export_r2_bundle(items)
    assert bundle["skill"] == "reading_s2_notice" and bundle["count"] == 3
    assert bundle["count_qc_ok"] == 3
    sheet = boss_factory.r2_review_sheet(items)
    assert "GV duyệt" in sheet and "Thông báo" in sheet and "Đáp án" in sheet


def test_SPEC_FACTORY_005_r3_comprehension_variants_boss_format():
    # bank_raw.json thật: s3_raw = block "p" RIÊNG (passage + từng câu 16-20 + 4 option A-D).
    bank = [{
        "ma_de": "EB1.2601",
        "s3_raw": [
            {"kind": "p", "text": "Section 3 Questions 16-20 (5 points)"},
            {"kind": "p", "text": "Read the text and questions below. For each question, circle the letter next to the correct answer (A, B, C or D)"},
            {"kind": "p", "text": ""},
            {"kind": "p", "text": "I am sure I am not the only person my age who hates going to the dentist. Channel 4's documentary Open Wide last Tuesday was excellent, but none of my school friends watched it because it did not appear in the TV Guide."},
            {"kind": "p", "text": "The programme showed how methods for treating toothache have developed over the centuries, and it completely changed my attitude to looking after my teeth."},
            {"kind": "p", "text": ""},
            {"kind": "p", "text": "Sophia Ashley, Oxford."},
            {"kind": "p", "text": ""},
            {"kind": "p", "text": "16. Why has Sophia written this text?"},
            {"kind": "p", "text": "A. to complain about the time a programme was shown."},
            {"kind": "p", "text": "B. to ask for more programmes for school children."},
            {"kind": "p", "text": "C. to advise people to watch a particular programme."},
            {"kind": "p", "text": "D. to persuade a television company to show a programme again."},
            {"kind": "p", "text": ""},
            {"kind": "p", "text": "17. Why did not Sophia's school friends see Open Wide?"},
            {"kind": "p", "text": "A. They did not know it was on."},
            {"kind": "p", "text": "B. They do not enjoy that type of programme."},
            {"kind": "p", "text": "C. Their parents would not let them."},
            {"kind": "p", "text": "D. It was not shown on a channel they can receive."},
        ],
        "s3_answers": {"16": "D", "17": "A"},
    }]

    # AC1: trích nhóm đọc-hiểu — đoạn văn + câu hỏi (mỗi câu 4 option A-D) + đáp án.
    seeds = boss_factory.load_r3_seeds(bank)
    assert len(seeds) == 1
    seed = seeds[0]
    assert "dentist" in seed["passage"] and "Section 3" not in seed["passage"]  # passage sạch (bỏ header)
    assert len(seed["questions"]) == 2
    assert seed["questions"][0]["num"] == "16" and seed["questions"][0]["answer"] == "D"
    assert sorted(seed["questions"][0]["options"].keys()) == ["A", "B", "C", "D"]
    assert seed["questions"][1]["num"] == "17" and seed["questions"][1]["answer"] == "A"

    # AC2+AC3: sinh biến thể (mock tất định) — s3_item {passage, questions} + s3_raw + s3_answers.
    items = boss_factory.build_r3_variants(seeds, per_seed=1, generator=None)
    assert len(items) == 1
    it = items[0]
    s3 = it["s3_item"]
    assert set(s3.keys()) == {"passage", "questions"}
    assert len(s3["questions"]) == 2                                       # đúng số câu của seed
    assert s3["passage"] and s3["passage"] != it["seed_passage"]          # KHÁC nguyên văn seed
    for q in s3["questions"]:
        assert sorted(q["options"].keys()) == ["A", "B", "C", "D"]        # 4 lựa chọn
        assert q["answer"] in q["options"]
    assert set(it["s3_answers"].keys()) == {"16", "17"}                    # đáp án key 16.. theo vị trí
    assert any(b["kind"] == "p" and b["text"].startswith("16.") for b in it["s3_raw"])
    assert it["do_kho"] in ("Dễ", "TB", "Khó") and it["qc_ok"] is True

    # AC4: qc_r3 bắt lỗi nhóm hỏng.
    good_qs = s3["questions"]
    assert any("passage rỗng" in i for i in boss_factory.qc_r3({"passage": "", "questions": good_qs}, seed))
    assert any("câu hỏi" in i for i in boss_factory.qc_r3({"passage": "P", "questions": good_qs[:1]}, seed))  # sai số câu
    miss_d = {**good_qs[0], "options": {"A": "a", "B": "b", "C": "c"}}
    assert any("A,B,C,D" in i for i in boss_factory.qc_r3({"passage": "P", "questions": [miss_d, good_qs[1]]}, seed))
    bad_ans = {**good_qs[0], "answer": "Z"}
    assert any("answer" in i for i in boss_factory.qc_r3({"passage": "P", "questions": [bad_ans, good_qs[1]]}, seed))
    assert any("nguyên văn" in i
               for i in boss_factory.qc_r3({"passage": seed["passage"], "questions": good_qs}, seed))

    # AC-dedup (non-tautology): nhánh REAL (_StubGen) trả CÙNG passage 2 lần → nhóm 2 near-dup.
    stub = _StubGen({
        "passage": "A short new passage about cooking simple meals at home for beginners.",
        "questions": [
            {"stem": "What is the text about?", "options": {"A": "cooking", "B": "driving", "C": "sleeping", "D": "singing"}, "answer": "A"},
            {"stem": "Who is it for?", "options": {"A": "experts", "B": "beginners", "C": "children", "D": "chefs"}, "answer": "B"},
        ], "difficulty": "easy"})
    dupd = boss_factory.build_r3_variants(seeds[:1], per_seed=2, generator=stub)
    assert len(dupd) == 2
    assert dupd[0]["qc_ok"] is True
    assert any("near-duplicate" in i for i in dupd[1]["qc_issues"])

    # Regression: mock per_seed=2 CÙNG seed KHÔNG near-dup oan (token duy nhất theo idx).
    multi = boss_factory.build_r3_variants(seeds[:1], per_seed=2, generator=None)
    assert len(multi) == 2 and all(m["qc_ok"] for m in multi)

    # Regression (review): số THẬP PHÂN "16.2" trong passage KHÔNG bị nhầm thành câu hỏi (cắt cụt passage).
    decimal_bank = [{
        "ma_de": "EB1.2690",
        "s3_raw": [
            {"kind": "p", "text": "Recycling has become a major issue in many cities around the world today."},
            {"kind": "p", "text": "16.2 million tonnes of household waste were recycled last year across the region."},
            {"kind": "p", "text": "Experts say the figure will keep rising as more families join local schemes."},
            {"kind": "p", "text": "16. What is the text mainly about?"},
            {"kind": "p", "text": "A. cooking"}, {"kind": "p", "text": "B. recycling"},
            {"kind": "p", "text": "C. driving"}, {"kind": "p", "text": "D. sleeping"},
            {"kind": "p", "text": "17. How much waste was recycled last year?"},
            {"kind": "p", "text": "A. 16.2 million tonnes"}, {"kind": "p", "text": "B. none"},
            {"kind": "p", "text": "C. a little"}, {"kind": "p", "text": "D. unknown"},
        ],
        "s3_answers": {"16": "B", "17": "A"},
    }]
    dec = boss_factory.load_r3_seeds(decimal_bank)
    assert len(dec) == 1
    assert "16.2 million tonnes" in dec[0]["passage"]                     # KHÔNG cắt trước số thập phân
    assert "Experts say" in dec[0]["passage"]                            # đoạn sau số thập phân còn nguyên
    assert len(dec[0]["questions"]) == 2                                  # vẫn parse đúng câu 16,17

    # Regression (review): Gemini trả group MÉO (options là list) KHÔNG crash cả lô — item bị QC loại.
    malformed = _StubGen({"passage": "Some new passage about gardening in spring for beginners.",
                          "questions": [{"stem": "Q?", "options": ["a", "b", "c", "d"], "answer": "A"},
                                        {"stem": "Q2?", "options": {"A": "1", "B": "2", "C": "3", "D": "4"}, "answer": "B"}],
                          "difficulty": "easy"})
    mf = boss_factory.build_r3_variants(seeds[:1], per_seed=1, generator=malformed)
    assert len(mf) == 1 and mf[0]["qc_ok"] is False                       # không crash; câu options-list bị bắt lỗi

    # Regression (review): near-copy đoạn văn seed (thêm 1 câu) bị gắn near-dup (chống copy near-verbatim).
    nc = _StubGen({"passage": seed["passage"] + " Extra sentence.",
                   "questions": [{"stem": q["stem"], "options": q["options"], "answer": q["answer"]}
                                 for q in seed["questions"]], "difficulty": "medium"})
    ncr = boss_factory.build_r3_variants([dict(seed)], per_seed=1, generator=nc)
    assert any("near-duplicate" in i for i in ncr[0]["qc_issues"])

    # AC5: gói bàn giao + bảng GV soát/ký.
    bundle = boss_factory.export_r3_bundle(items)
    assert bundle["skill"] == "reading_s3_comprehension" and bundle["count"] == 1
    assert bundle["count_qc_ok"] == 1
    sheet = boss_factory.r3_review_sheet(items)
    assert "GV duyệt" in sheet and "Đoạn văn" in sheet and "Số câu" in sheet
