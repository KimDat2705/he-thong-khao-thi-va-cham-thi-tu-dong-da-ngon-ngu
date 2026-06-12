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

pytestmark = pytest.mark.skip(
    reason="Parser Engine (app/services/parser.py) chưa được triển khai — "
    "hợp đồng SPEC-PARSE-001..004 được đặc tả trong docstring từng test, "
    "dự kiến triển khai ở giai đoạn Nạp liệu (Tuần 1-2 theo system_plan.md)"
)


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
