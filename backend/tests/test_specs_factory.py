"""SPEC-FACTORY-* — Nhà máy sinh câu B1 xuất ĐÚNG định dạng ngân hàng của đối tác (bàn giao).

Định hướng S52: việc mình = mở rộng ngân hàng của sếp (không phải generate đề). Slice P1-R1:
paraphrase câu Đọc phần 1 (R1) từ đề thật của đối tác → shape s1 {stem, options{A-D}, answer}.
Test dùng seed TỔNG HỢP + mock tất định (không gọi Gemini/mạng).
"""
from app.services import boss_factory


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
