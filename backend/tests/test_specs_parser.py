"""
Bảo chứng cho Parser/Ingestion Engine (phân hệ Ra đề VSTEP B1).

Parser Engine nạp ngân hàng câu hỏi từ dữ liệu nguồn thực tế của đối tác cho
kỳ thi VSTEP B1:
- B1 VSTEP Đọc & Viết: EB1 - xxxx.docx + phiếu đáp án.
- B1 VSTEP Nghe: LB1.xxxx.docx + phiếu đáp án; Speaking Cards.
- Converter .doc -> .docx (LibreOffice headless) dùng chung cho các phiếu đáp án
  và Speaking Card định dạng .doc legacy.
"""
import pytest

@pytest.fixture(scope="module", autouse=True)
def setup_parser_fixtures():
    from tests.make_fixtures import main as generate_fixtures
    generate_fixtures()


def test_SPEC_PARSE_008_doc_converter(tmp_path):
    """SPEC-PARSE-008: Chuyển đổi tệp tin Word .doc legacy sang .docx.
    Kiểm tra passthrough, missing-tool (ném lỗi) và cache (không chạy soffice).
    """
    from app.services.parser import convert_doc_to_docx
    import os
    import docx
    from unittest.mock import patch

    # 1. Passthrough Test: .docx file
    # We use the existing B1_exam_sample.docx fixture path
    fixture_docx = os.path.abspath(os.path.join(os.path.dirname(__file__), "fixtures", "parser", "B1_exam_sample.docx"))
    assert os.path.exists(fixture_docx)
    
    res_docx = convert_doc_to_docx(fixture_docx)
    assert res_docx == fixture_docx
    # Verify we can open it
    doc = docx.Document(res_docx)
    assert len(doc.paragraphs) > 0

    # 2. Missing Tool Test
    # Create a real dummy.doc file in tmp_path to pass os.path.exists check
    dummy_doc = tmp_path / "dummy.doc"
    dummy_doc.write_text("dummy doc content", encoding="utf-8")
    
    # We mock shutil.which to return None and verify FileNotFoundError is raised.
    # To bypass Windows fallback search, we also mock os.path.exists to return False for LibreOffice paths.
    orig_exists = os.path.exists
    def mock_exists(p):
        if "LibreOffice" in str(p):
            return False
        return orig_exists(p)
        
    with patch("shutil.which", return_value=None), patch("os.path.exists", side_effect=mock_exists):
        import pytest
        with pytest.raises(FileNotFoundError) as exc_info:
            convert_doc_to_docx(str(dummy_doc), out_dir=str(tmp_path))
        assert "LibreOffice" in str(exc_info.value)
        assert "soffice" in str(exc_info.value)

    # 3. Cache Test
    # Create a dummy.doc and a cached dummy.docx in tmp_path
    cached_doc = tmp_path / "cached.doc"
    cached_doc.write_text("cached doc content", encoding="utf-8")
    cached_docx = tmp_path / "cached.docx"
    cached_docx.write_text("cached docx content", encoding="utf-8")

    # If cache works, it will skip calling subprocess entirely
    with patch("subprocess.run") as mock_run:
        res_cache = convert_doc_to_docx(str(cached_doc), out_dir=str(tmp_path))
        assert res_cache == str(cached_docx)
        mock_run.assert_not_called()


def test_SPEC_PARSE_012_parse_b1_exam_and_answer_key():
    """SPEC-PARSE-012: Kiểm tra phân tích đề B1 Đọc+Viết và tệp đáp án.
    """
    from app.services.parser import parse_b1_reading_docx, parse_b1_answer_key
    import os

    fixtures_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "fixtures", "parser"))
    docx_path = os.path.join(fixtures_dir, "B1_exam_sample.docx")
    key_path = os.path.join(fixtures_dir, "B1_key_sample.docx")

    assert os.path.exists(docx_path), f"File {docx_path} không tồn tại"
    assert os.path.exists(key_path), f"File {key_path} không tồn tại"

    # 1. Parse B1 Exam
    exam_data = parse_b1_reading_docx(docx_path)
    assert exam_data["set_id"] == "EB19999"
    
    items = exam_data["items"]
    assert len(items) == 32  # 30 Reading (Q1-30) + 2 Writing (Q31-32)

    # Check S1 (Q1-10)
    for idx in range(10):
        item = items[idx]
        assert item["number"] == idx + 1
        assert item["part"] == 1
        assert item["section"] == 1
        assert item["type"] == "choice"
        assert len(item["options"]) == 4
        assert set(item["options"].keys()) == {"A", "B", "C", "D"}
        assert f"Question content {idx + 1}" in item["content"]

    # Check S2 (Q11-15)
    for idx in range(10, 15):
        item = items[idx]
        assert item["number"] == idx + 1
        assert item["part"] == 2
        assert item["section"] == 2
        assert item["type"] == "choice"
        assert len(item["options"]) == 3
        assert set(item["options"].keys()) == {"A", "B", "C"}
        assert f"Signboard text for question {idx + 1}" in item["content"]

    # Check S3 (Q16-20)
    for idx in range(15, 20):
        item = items[idx]
        assert item["number"] == idx + 1
        assert item["part"] == 3
        assert item["section"] == 3
        assert item["type"] == "choice"
        assert len(item["options"]) == 4
        assert set(item["options"].keys()) == {"A", "B", "C", "D"}
        assert f"Question dental {idx + 1}" in item["content"]

    # Check S4 (Q21-30)
    for idx in range(20, 30):
        item = items[idx]
        q_num = idx + 1
        assert item["number"] == q_num
        assert item["part"] == 4
        assert item["section"] == 4
        assert item["type"] == "fill"
        assert len(item["options"]) == 0
        assert f"({q_num})" in item["content"]

    # Check Writing Section 1 (Q31)
    w1 = items[30]
    assert w1["number"] == 31
    assert w1["part"] == 5
    assert w1["section"] == 1
    assert w1["type"] == "writing"
    assert "How is your surname spelt?" in w1["content"]

    # Check Writing Section 2 (Q32)
    w2 = items[31]
    assert w2["number"] == 32
    assert w2["part"] == 6
    assert w2["section"] == 2
    assert w2["type"] == "writing"
    assert "You are Hoa Tran. Write a letter" in w2["content"]

    # 2. Parse B1 Answer Key
    answers = parse_b1_answer_key(key_path)
    assert len(answers) == 30
    assert sorted(answers.keys()) == list(range(1, 31))

    # Q1-20 should be choice uppercase answers
    sec1_ans = {1: "A", 2: "B", 3: "B", 4: "A", 5: "A", 6: "B", 7: "A", 8: "D", 9: "B", 10: "A"}
    sec2_ans = {11: "A", 12: "C", 13: "C", 14: "B", 15: "A"}
    sec3_ans = {16: "D", 17: "A", 18: "D", 19: "B", 20: "C"}
    for q_num in range(1, 11):
        assert answers[q_num] == sec1_ans[q_num]
    for q_num in range(11, 16):
        assert answers[q_num] == sec2_ans[q_num]
    for q_num in range(16, 21):
        assert answers[q_num] == sec3_ans[q_num]

    # Q21-30 should be the correct text answers
    sec4_ans = {
        21: "fact", 22: "frighten", 23: "most", 24: "weigh", 25: "Both",
        26: "spend", 27: "search", 28: "left", 29: "which", 30: "must"
    }
    for q_num in range(21, 31):
        assert answers[q_num] == sec4_ans[q_num]


def test_SPEC_PARSE_013_parse_b1_listening_and_speaking():
    """SPEC-PARSE-013: Kiểm tra parse đề Nghe B1, đáp án Nghe B1, và Speaking card.
    """
    from app.services.parser import parse_b1_listening_docx, parse_b1_listening_key, parse_b1_speaking_card
    import os

    fixtures_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "fixtures", "parser"))
    listening_path = os.path.join(fixtures_dir, "B1_listening_sample.docx")
    key_path = os.path.join(fixtures_dir, "B1_listening_key_sample.docx")
    speaking_path = os.path.join(fixtures_dir, "B1_speaking_sample.docx")

    assert os.path.exists(listening_path), f"File {listening_path} không tồn tại"
    assert os.path.exists(key_path), f"File {key_path} không tồn tại"
    assert os.path.exists(speaking_path), f"File {speaking_path} không tồn tại"

    # 1. Parse B1 Listening Exam
    listening_data = parse_b1_listening_docx(listening_path)
    assert listening_data["set_id"] == "LB12601"
    
    items = listening_data["items"]
    assert len(items) == 15  # 5 Choice + 10 Fill

    # Check Choice Q1-5
    for idx in range(5):
        item = items[idx]
        assert item["number"] == idx + 1
        assert item["part"] == 1
        assert item["section"] == 1
        assert item["type"] == "choice"
        assert item["options"] == {"A": "", "B": "", "C": ""}
        assert item["image_url"] is not None
        assert "Which dish did Mark cook in the competition?" in item["content"]

    # Check Fill Q6-15
    for idx in range(5, 15):
        item = items[idx]
        q_num = idx + 1
        assert item["number"] == q_num
        assert item["part"] == 2
        assert item["section"] == 2
        assert item["type"] == "fill"
        assert item["options"] == {}
        assert f"({q_num})" in item["content"]

    # 2. Parse B1 Listening Key
    answers = parse_b1_listening_key(key_path)
    assert len(answers) == 15
    assert sorted(answers.keys()) == list(range(1, 16))
    
    # Q1-5 should be choice uppercase answers
    expected_ans = {
        1: "C", 2: "B", 3: "A", 4: "B", 5: "C",
        6: "Nature", 7: "wildlife", 8: "forest", 9: "12/twelve", 10: "wood",
        11: "waysbury", 12: "Brokley", 13: "blue", 14: "receptionist", 15: "3/ three"
    }
    for q_num in range(1, 16):
        assert answers[q_num] == expected_ans[q_num]

    # 3. Parse Speaking Card
    speaking_items = parse_b1_speaking_card(speaking_path, "LB12601")
    assert len(speaking_items) == 3
    
    # Part 1
    assert speaking_items[0]["number"] == 1
    assert speaking_items[0]["part"] == 1
    assert speaking_items[0]["type"] == "speaking"
    assert "Introducing yourself" in speaking_items[0]["content"]

    # Part 2
    assert speaking_items[1]["number"] == 2
    assert speaking_items[1]["part"] == 2
    assert speaking_items[1]["type"] == "speaking"
    assert "favourite season" in speaking_items[1]["content"]

    # Part 3
    assert speaking_items[2]["number"] == 3
    assert speaking_items[2]["part"] == 3
    assert speaking_items[2]["type"] == "speaking"
    assert "Interaction" in speaking_items[2]["content"]
