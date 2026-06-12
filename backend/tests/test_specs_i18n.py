"""
SPEC-COLLATE-004, SPEC-I18N-001 — Bảo chứng nền tảng Đa ngôn ngữ.

Chiến lược dự án: làm tiếng Anh (TOEIC + B1 VSTEP) trước, tiếng Trung (HSK) sau —
nhưng schema và generator phải trung lập ngôn ngữ NGAY TỪ ĐẦU để thêm tiếng Trung
chỉ là thêm DATA (blueprint + prompt + ngân hàng câu hỏi), không refactor.
"""
from sqlalchemy.orm import Session

from app.models.exam import Exam
from app.models.question import Question
from app.models.question_group import QuestionGroup
from app.services.toeic_generator import generate_toeic_exam


def test_SPEC_COLLATE_004_no_mojibake_in_bank_or_exam(db_session: Session):
    """SPEC-COLLATE-004: Mọi văn bản trong ngân hàng và đề sinh ra (nội dung câu,
    options, đoạn văn, đáp án, giải thích) phải là UTF-8 hợp lệ, không chứa ký tự
    thay thế U+FFFD hay lỗi mã hóa.
    """
    generate_toeic_exam(db_session, title="Đề kiểm tra SPEC-COLLATE-004 — tiếng Việt có dấu")

    def assert_clean(text, origin):
        if text is None:
            return
        assert "�" not in text, f"Ký tự lỗi mã hóa U+FFFD trong {origin}: {text[:80]!r}"
        # Round-trip UTF-8 phải nguyên vẹn
        assert text.encode("utf-8").decode("utf-8") == text, f"UTF-8 round-trip lỗi trong {origin}"

    for q in db_session.query(Question).all():
        assert_clean(q.content, f"Question {q.id}.content")
        assert_clean(q.reference_answer, f"Question {q.id}.reference_answer")
        assert_clean(q.explanation, f"Question {q.id}.explanation")
        if isinstance(q.options, dict):
            for key, value in q.options.items():
                assert_clean(str(value), f"Question {q.id}.options[{key}]")

    for g in db_session.query(QuestionGroup).all():
        assert_clean(g.passage_text, f"QuestionGroup {g.id}.passage_text")
        assert_clean(g.topic, f"QuestionGroup {g.id}.topic")


def test_SPEC_I18N_001_schema_accepts_chinese_hsk(db_session: Session):
    """SPEC-I18N-001: Schema hiện tại phải chứa được đề thi tiếng Trung/HSK không
    cần thay đổi: language/exam_type là dữ liệu, metadata đặc thù ngôn ngữ
    (pinyin, hsk_level) nằm trong JSON, ký tự CJK round-trip nguyên vẹn.
    """
    exam = Exam(
        title="HSK 4 模拟考试 — Đề thi thử HSK 4",
        language="CN",
        exam_type="HSK",
        duration_minutes=105,
        is_active=True,
    )
    db_session.add(exam)
    db_session.commit()
    db_session.refresh(exam)

    question = Question(
        exam_id=exam.id,
        part=1,
        type="choice",
        content="他每天___去上班。",
        options={
            "A": {"text": "骑车", "pinyin": "qí chē"},
            "B": {"text": "跑步", "pinyin": "pǎo bù"},
            "C": {"text": "游泳", "pinyin": "yóu yǒng"},
            "D": {"text": "睡觉", "pinyin": "shuì jiào"},
        },
        reference_answer="A",
        difficulty="medium",
        topic="日常生活",
        explanation="骑车 (qí chē) nghĩa là đạp xe — phương tiện đi làm hằng ngày.",
    )
    db_session.add(question)
    db_session.commit()

    # Đọc lại từ DB (xóa cache ORM) và xác nhận round-trip nguyên vẹn
    db_session.expire_all()
    loaded_exam = db_session.query(Exam).filter(Exam.id == exam.id).one()
    loaded_q = db_session.query(Question).filter(Question.id == question.id).one()

    assert loaded_exam.language == "CN"
    assert loaded_exam.exam_type == "HSK"
    assert "模拟考试" in loaded_exam.title
    assert loaded_q.content == "他每天___去上班。"
    assert loaded_q.options["A"] == {"text": "骑车", "pinyin": "qí chē"}, \
        "Metadata pinyin lồng trong JSON options phải round-trip nguyên vẹn"
    assert loaded_q.topic == "日常生活"
    assert "�" not in loaded_q.content
