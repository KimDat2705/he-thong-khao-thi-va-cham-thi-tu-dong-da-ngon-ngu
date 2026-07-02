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
