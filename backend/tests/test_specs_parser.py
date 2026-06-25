"""
SPEC-PARSE-001..004 — Hợp đồng cho Parser/Ingestion Engine (CHƯA TRIỂN KHAI).

Parser Engine là Giai đoạn 1 của phân hệ Ra đề: nạp ngân hàng câu hỏi từ dữ liệu
nguồn thực tế của đối tác:
- TOEIC Listening: LT2601.docx .. LT2629.docx (chỉ số lẻ) + Excel đáp án
  + thư mục "File nghe tong hop" (MP3, liên kết theo quy ước tên file).
- TOEIC Reading:  CDR TOEIC - RT2601.doc .. RT2615.doc (định dạng .doc nhị phân,
  cần convert sang .docx trước khi parse bằng python-docx) + Excel đáp án.
- B1 VSTEP: ~30 bộ LB1.xxxx.docx (Nghe) + EB1 - xxxx.docx (Đọc & Viết)
  + Speaking Cards + phiếu tiêu chí chấm.

Mỗi test dưới đây ghi nguyên văn hợp đồng spec trong docstring và chứa assertion
dự kiến. Toàn bộ module SKIP cho đến khi app/services/parser.py ra đời —
khi đó bỏ pytestmark, hoàn thiện fixture trong tests/fixtures/ và chạy thật.
"""
import pytest

@pytest.fixture(scope="module", autouse=True)
def setup_parser_fixtures():
    from tests.make_fixtures import main as generate_fixtures
    generate_fixtures()


def test_SPEC_PARSE_001_no_incomplete_questions_after_import(db_session):
    """SPEC-PARSE-001: Sau khi Parser Engine import một file nguồn (Word/Excel),
    không tồn tại bất kỳ câu hỏi trắc nghiệm nào trong ngân hàng thiếu
    reference_answer hoặc thiếu options.

    Fixture tương lai: tests/fixtures/parser/LT_sample_valid.docx (file chuẩn)
    và LT_sample_missing_answer.docx (file hỏng — thiếu đáp án câu 3).
    """
    from app.services.parser import import_file  # noqa: F401 — module chưa tồn tại
    from app.models.question import Question

    import_file(db_session, "tests/fixtures/parser/LT_sample_valid.docx")

    incomplete = db_session.query(Question).filter(
        Question.type == "choice",
        (Question.reference_answer.is_(None)) | (Question.reference_answer == "")
        | (Question.options.is_(None)),
    ).count()
    assert incomplete == 0, "Tồn tại câu hỏi trắc nghiệm khuyết đáp án/options sau import"


def test_SPEC_PARSE_002_listening_audio_link_resolves(db_session):
    """SPEC-PARSE-002: Mỗi nhóm câu hỏi Listening import từ LTxxxx.docx phải được
    liên kết tới file MP3 tồn tại theo quy ước đặt tên; nếu file âm thanh thiếu,
    import phải thất bại (raise + rollback, 0 bản ghi được ghi).

    Fixture tương lai: bộ LT_sample_valid.docx kèm thư mục audio đầy đủ,
    và LT_sample_missing_audio.docx trỏ tới MP3 không tồn tại.
    """
    from app.services.parser import import_file, ImportError as ParserImportError  # noqa: F401
    from app.models.question_group import QuestionGroup

    before = db_session.query(QuestionGroup).count()
    with pytest.raises(ParserImportError, match="MP3"):
        import_file(db_session, "tests/fixtures/parser/LT_sample_missing_audio.docx")
    assert db_session.query(QuestionGroup).count() == before, "Import lỗi nhưng vẫn ghi bản ghi"


def test_SPEC_PARSE_003_reimport_is_idempotent(db_session):
    """SPEC-PARSE-003: Import lại cùng một file nguồn không tạo bản ghi trùng lặp
    trong ngân hàng (nhận diện trùng bằng content-hash của câu hỏi/nhóm).
    """
    from app.services.parser import import_file  # noqa: F401
    from app.models.question import Question
    from app.models.question_group import QuestionGroup

    import_file(db_session, "tests/fixtures/parser/LT_sample_valid.docx")
    q_count = db_session.query(Question).count()
    g_count = db_session.query(QuestionGroup).count()

    import_file(db_session, "tests/fixtures/parser/LT_sample_valid.docx")
    assert db_session.query(Question).count() == q_count, "Re-import nhân bản câu hỏi"
    assert db_session.query(QuestionGroup).count() == g_count, "Re-import nhân bản nhóm"


def test_SPEC_PARSE_004_failed_import_writes_nothing(db_session):
    """SPEC-PARSE-004: Import theo đơn vị file là giao dịch nguyên tử (all-or-nothing):
    file không qua validation thì 0 bản ghi được ghi vào DB, đồng thời sinh báo cáo
    lỗi JSON liệt kê từng vi phạm (tên file, vị trí, loại lỗi, mô tả). Mọi item
    import thành công vào bank ở trạng thái status='draft' chờ duyệt.
    """
    from app.services.parser import import_file, ImportError as ParserImportError  # noqa: F401
    from app.models.question import Question

    before = db_session.query(Question).count()
    with pytest.raises(ParserImportError) as exc_info:
        import_file(db_session, "tests/fixtures/parser/LT_sample_missing_answer.docx")

    assert db_session.query(Question).count() == before, "Import lỗi nhưng vẫn ghi bản ghi"
    report = exc_info.value.report  # báo cáo lỗi dạng dict/JSON
    assert report["file"].endswith("LT_sample_missing_answer.docx")
    assert len(report["errors"]) > 0
    assert {"location", "type", "message"} <= set(report["errors"][0].keys())


def test_SPEC_PARSE_005_answer_key_import():
    """SPEC-PARSE-005: Đọc và parse tệp đáp án từ Excel (*.xlsx) theo đúng cấu trúc.
    """
    from app.services.parser import parse_answer_key
    import os

    filepath = os.path.abspath(os.path.join(os.path.dirname(__file__), "fixtures", "parser", "Key_LT2601.xlsx"))
    assert os.path.exists(filepath), f"File fixture {filepath} không tồn tại"

    answers = parse_answer_key(filepath)

    assert len(answers) == 100, f"Kỳ vọng 100 đáp án, thực tế nhận được {len(answers)}"
    for q_num in range(1, 101):
        assert q_num in answers, f"Thiếu đáp án cho câu {q_num}"
        assert answers[q_num] in {"A", "B", "C", "D"}, f"Đáp án câu {q_num} không hợp lệ: {answers[q_num]}"


def test_SPEC_PARSE_006_parse_real_listening_docx():
    """SPEC-PARSE-006: Đọc và parse tệp câu hỏi .docx đề Nghe TOEIC định dạng thật (table-based).
    """
    from app.services.parser import parse_listening_docx
    import os

    filepath = os.path.abspath(os.path.join(os.path.dirname(__file__), "fixtures", "parser", "LT_real_sample.docx"))
    assert os.path.exists(filepath), f"File fixture {filepath} không tồn tại"

    result = parse_listening_docx(filepath)
    assert result["set_id"] == "LT9999"
    items = result["items"]

    # Tổng số câu
    q_count = 0
    part_counts = {1: 0, 2: 0, 3: 0, 4: 0}
    q_by_num = {}

    for item in items:
        p = item["part"]
        if "questions" in item:
            part_counts[p] += len(item["questions"])
            q_count += len(item["questions"])
            assert item["difficulty"] == "medium"
            # Cell image_url can be None or string
            for q in item["questions"]:
                assert q["part"] == p
                assert len(q["options"]) == 4
                assert set(q["options"].keys()) == {"A", "B", "C", "D"}
                assert q["reference_answer"] is None
                q_by_num[q["number"]] = q
        else:
            part_counts[p] += 1
            q_count += 1
            assert item["part"] == p
            assert item["reference_answer"] is None
            q_by_num[item["number"]] = item
            if p == 1:
                assert item["image_url"] is not None
                assert item["options"] == {}
            elif p == 2:
                assert item["options"] == {}
                assert item["image_url"] is None
                assert "Mark your answer" in item["content"]

    # Verify counts per part (Mini structure)
    assert q_count == 15
    assert part_counts[1] == 4
    assert part_counts[2] == 2
    assert part_counts[3] == 6
    assert part_counts[4] == 3

    # Check question number range
    assert sorted(q_by_num.keys()) == list(range(1, 16))

    # Dash-split: 1 cell Part 3 phải tách ĐÚNG 2 nhóm × 3 câu (guard chống regression gộp nhóm)
    p3_groups = [it for it in items if it.get("part") == 3 and "questions" in it]
    assert len(p3_groups) == 2, f"Part 3 phải tách thành 2 nhóm theo dấu '---', thực tế {len(p3_groups)}"
    assert all(len(g["questions"]) == 3 for g in p3_groups), "Mỗi nhóm Part 3 phải có đúng 3 câu"

    # Verify option wrap logic for Q8 Option A
    q8 = q_by_num[8]
    assert q8["options"]["A"] == "Go to the conference center"


def test_SPEC_PARSE_007_import_listening_set_success(db_session):
    """SPEC-PARSE-007: Đọc đề nghe thực tế + file Excel đáp án, ghép đúng câu trả lời và ghi DB.
    """
    from app.services.parser import import_listening_set
    from app.models.question import Question
    from app.models.question_group import QuestionGroup
    import os

    docx_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "fixtures", "parser", "LT_real_sample.docx"))
    key_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "fixtures", "parser", "Key_LT9999.xlsx"))

    assert os.path.exists(docx_path)
    assert os.path.exists(key_path)

    # Clean DB before test
    db_session.query(Question).delete()
    db_session.query(QuestionGroup).delete()
    db_session.commit()

    # Import
    res = import_listening_set(db_session, docx_path, key_path)
    
    # Assert return counts
    assert res["imported_questions"] == 15
    assert res["imported_groups"] == 3  # Part 3: 2 groups, Part 4: 1 group

    # Query database and verify
    questions = db_session.query(Question).all()
    groups = db_session.query(QuestionGroup).all()

    assert len(questions) == 15
    assert len(groups) == 3

    # Check that all questions have reference answer in {A, B, C, D} and status == "draft"
    q_map = {}
    for q in questions:
        assert q.status == "draft"
        assert q.reference_answer in {"A", "B", "C", "D"}
        q_map[q.part] = q_map.get(q.part, 0) + 1

    # Check question counts per part
    assert q_map[1] == 4
    assert q_map[2] == 2
    assert q_map[3] == 6
    assert q_map[4] == 3

    # Check group status == "draft"
    for g in groups:
        assert g.status == "draft"

    # Test idempotency (Re-importing the same files shouldn't duplicate)
    res2 = import_listening_set(db_session, docx_path, key_path)
    assert res2["imported_questions"] == 0
    assert res2["imported_groups"] == 0
    assert res2["skipped_questions"] == 15
    assert res2["skipped_groups"] == 3

    assert db_session.query(Question).count() == 15
    assert db_session.query(QuestionGroup).count() == 3


def test_SPEC_PARSE_008_doc_converter(tmp_path):
    """SPEC-PARSE-008: Chuyển đổi tệp tin Word .doc legacy sang .docx.
    Kiểm tra passthrough, missing-tool (ném lỗi) và cache (không chạy soffice).
    """
    from app.services.parser import convert_doc_to_docx
    import os
    import docx
    from unittest.mock import patch

    # 1. Passthrough Test: .docx file
    # We will use the existing LT_real_sample.docx fixture path
    fixture_docx = os.path.abspath(os.path.join(os.path.dirname(__file__), "fixtures", "parser", "LT_real_sample.docx"))
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


def test_SPEC_PARSE_009_parse_real_reading_docx():
    """SPEC-PARSE-009: Đọc và parse tệp câu hỏi .docx đề Đọc TOEIC định dạng thật.
    """
    from app.services.parser import parse_reading_docx
    import os

    filepath = os.path.abspath(os.path.join(os.path.dirname(__file__), "fixtures", "parser", "RT_real_sample.docx"))
    assert os.path.exists(filepath), f"File fixture {filepath} không tồn tại"

    result = parse_reading_docx(filepath)
    assert result["set_id"] == "RT9999"
    items = result["items"]

    # Count questions
    q_count = 0
    part_counts = {5: 0, 6: 0, 7: 0}
    q_by_num = {}

    for item in items:
        p = item["part"]
        if "questions" in item:
            part_counts[p] += len(item["questions"])
            q_count += len(item["questions"])
            assert item["difficulty"] == "medium"
            # Cell image_url can be None or string
            for q in item["questions"]:
                assert q["part"] == p
                assert len(q["options"]) == 4
                assert set(q["options"].keys()) == {"A", "B", "C", "D"}
                assert q["reference_answer"] is None
                q_by_num[q["number"]] = q
        else:
            part_counts[p] += 1
            q_count += 1
            assert item["part"] == p
            assert len(item["options"]) == 4
            assert set(item["options"].keys()) == {"A", "B", "C", "D"}
            assert item["reference_answer"] is None
            q_by_num[item["number"]] = item
            if p == 5:
                assert item["image_url"] is None

    # Verify counts per part
    assert q_count == 12
    assert part_counts[5] == 2
    assert part_counts[6] == 4
    assert part_counts[7] == 6

    # Verify numbers range
    assert sorted(q_by_num.keys()) == list(range(1, 13))

    # Verify Part 5
    q1 = q_by_num[1]
    assert q1["part"] == 5
    assert q1["options"]["A"] == "Option A1"
    assert q1["options"]["B"] == "Option B1"
    assert q1["options"]["C"] == "Option C1"
    assert q1["options"]["D"] == "Option D1"

    # Verify inline options for Q2
    q2 = q_by_num[2]
    assert q2["part"] == 5
    assert q2["options"]["A"] == "Option A2"
    assert q2["options"]["B"] == "Option B2"
    assert q2["options"]["C"] == "Option C2"
    assert q2["options"]["D"] == "Option D2"

    # Verify Part 6 group has passage_text and correct options
    p6_groups = [it for it in items if it.get("part") == 6 and "questions" in it]
    assert len(p6_groups) == 1
    p6_g = p6_groups[0]
    assert p6_g["passage_text"] is not None
    assert "Policy change" in p6_g["passage_text"]
    assert "Dear staff" in p6_g["passage_text"]
    
    q3 = q_by_num[3]
    assert q3["content"] == ""  # blank completion
    assert q3["options"]["A"] == "quick"
    assert q3["options"]["B"] == "quickly"
    assert q3["options"]["C"] == "quicker"
    assert q3["options"]["D"] == "quickest"

    # Verify Part 7 groups
    p7_groups = [it for it in items if it.get("part") == 7 and "questions" in it]
    assert len(p7_groups) == 2

    # Group 1 (Q7-8): text box (1x1 table) + paragraph options + image_url
    g1 = p7_groups[0]
    assert "Office renovation" in g1["passage_text"]
    assert g1["image_url"] is not None  # drawing found
    
    q7 = q_by_num[7]
    assert q7["options"]["A"] == "Renovation"
    assert q7["options"]["B"] == "Class"
    assert q7["options"]["C"] == "Holiday"
    assert q7["options"]["D"] == "Meeting"

    # Group 2 (Q9-12): advertisement and review + 4x2 tables
    g2 = p7_groups[1]
    assert "Advertisement:" in g2["passage_text"]
    assert "Review:" in g2["passage_text"]
    assert g2["image_url"] is None
    
    # Q9: Sandwich layout
    q9 = q_by_num[9]
    assert "What is being advertised?" in q9["content"]
    assert "Buy our product" in q9["content"]
    assert q9["options"]["A"] == "A product"
    assert q9["options"]["B"] == "A service"
    assert q9["options"]["C"] == "A company"
    assert q9["options"]["D"] == "A store"


def test_SPEC_PARSE_010_import_reading_set_success(db_session):
    """SPEC-PARSE-010: Nhập đề Đọc thực tế + file Excel đáp án, ghép đúng câu trả lời và ghi DB.
    """
    from app.services.parser import import_reading_set
    from app.models.question import Question
    from app.models.question_group import QuestionGroup
    import os

    docx_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "fixtures", "parser", "RT_real_sample.docx"))
    key_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "fixtures", "parser", "Key_RT9999.xlsx"))

    assert os.path.exists(docx_path)
    assert os.path.exists(key_path)

    # Clean DB before test
    db_session.query(Question).delete()
    db_session.query(QuestionGroup).delete()
    db_session.commit()

    # Import
    res = import_reading_set(db_session, docx_path, key_path)

    # Assert return counts
    assert res["imported_questions"] == 12
    assert res["imported_groups"] == 3  # Part 6: 1 group, Part 7: 2 groups

    # Query database and verify
    questions = db_session.query(Question).all()
    groups = db_session.query(QuestionGroup).all()

    assert len(questions) == 12
    assert len(groups) == 3

    # Check that all questions have reference answer in {A, B, C, D} and status == "draft"
    q_map = {}
    for q in questions:
        assert q.status == "draft"
        assert q.reference_answer in {"A", "B", "C", "D"}
        q_map[q.part] = q_map.get(q.part, 0) + 1

    # Check question counts per part
    assert q_map[5] == 2
    assert q_map[6] == 4
    assert q_map[7] == 6

    # Check group status == "draft"
    for g in groups:
        assert g.status == "draft"

    # Test idempotency (Re-importing the same files shouldn't duplicate)
    res2 = import_reading_set(db_session, docx_path, key_path)
    assert res2["imported_questions"] == 0
    assert res2["imported_groups"] == 0
    assert res2["skipped_questions"] == 12
    assert res2["skipped_groups"] == 3

    assert db_session.query(Question).count() == 12
    assert db_session.query(QuestionGroup).count() == 3


def test_SPEC_PARSE_011_listening_audio_linking(db_session, tmp_path):
    """SPEC-PARSE-011: Kiểm tra liên kết tệp âm thanh cấp file cho đề Listening.
    """
    from app.services.parser import import_listening_set
    from app.models.question import Question
    from app.models.question_group import QuestionGroup
    import os
    import shutil

    # Copy files to temp directory
    fixtures_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "fixtures", "parser"))
    orig_docx = os.path.join(fixtures_dir, "LT_real_sample.docx")
    orig_key = os.path.join(fixtures_dir, "Key_LT9999.xlsx")

    temp_docx = os.path.join(tmp_path, "LT_real_sample.docx")
    temp_key = os.path.join(tmp_path, "Key_LT9999.xlsx")

    shutil.copy(orig_docx, temp_docx)
    shutil.copy(orig_key, temp_key)

    # 1. Non-fatal fallback path: NO MP3 file found
    db_session.query(Question).delete()
    db_session.query(QuestionGroup).delete()
    db_session.commit()

    res_missing = import_listening_set(db_session, temp_docx, temp_key, audio_dir=str(tmp_path))
    assert res_missing["audio_linked"] is None
    assert res_missing["audio_ambiguous"] == []

    questions = db_session.query(Question).all()
    groups = db_session.query(QuestionGroup).all()
    assert len(questions) == 15
    assert len(groups) == 3
    assert all(q.audio_url is None for q in questions)
    assert all(g.audio_url is None for g in groups)

    # 2. Single match path: exactly 1 matching MP3 file
    db_session.query(Question).delete()
    db_session.query(QuestionGroup).delete()
    db_session.commit()

    # Create one matching range MP3 file
    mp3_file_1 = os.path.join(tmp_path, "9990 - 9999.mp3")
    with open(mp3_file_1, "wb") as f:
        f.write(b"MOCK AUDIO")

    res_single = import_listening_set(db_session, temp_docx, temp_key, audio_dir=str(tmp_path))
    assert res_single["audio_linked"] == "9990 - 9999.mp3"
    assert res_single["audio_ambiguous"] == []

    questions = db_session.query(Question).all()
    groups = db_session.query(QuestionGroup).all()
    assert len(questions) == 15
    assert len(groups) == 3
    assert all(q.audio_url == "9990 - 9999.mp3" for q in questions)
    assert all(g.audio_url == "9990 - 9999.mp3" for g in groups)

    # 3. Ambiguity path: multiple matching MP3 files
    db_session.query(Question).delete()
    db_session.query(QuestionGroup).delete()
    db_session.commit()

    # Create a second matching range MP3 file (alphabetically larger, so "9990 - 9999.mp3" is chosen)
    mp3_file_2 = os.path.join(tmp_path, "9998 - 9999.mp3")
    with open(mp3_file_2, "wb") as f:
        f.write(b"MOCK AUDIO")

    res_ambig = import_listening_set(db_session, temp_docx, temp_key, audio_dir=str(tmp_path))
    assert res_ambig["audio_linked"] == "9990 - 9999.mp3"
    assert sorted(res_ambig["audio_ambiguous"]) == ["9990 - 9999.mp3", "9998 - 9999.mp3"]

    questions = db_session.query(Question).all()
    groups = db_session.query(QuestionGroup).all()
    assert len(questions) == 15
    assert len(groups) == 3
    assert all(q.audio_url == "9990 - 9999.mp3" for q in questions)
    assert all(g.audio_url == "9990 - 9999.mp3" for g in groups)


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






