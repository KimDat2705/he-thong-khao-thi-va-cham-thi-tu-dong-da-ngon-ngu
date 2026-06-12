"""
SPEC-BANK-* — Bảo chứng về Ngân hàng câu hỏi (Giai đoạn 2 phân hệ Ra đề).

Ngân hàng = các bản ghi Question/QuestionGroup có exam_id IS NULL.
Sinh đề chỉ được CLONE từ ngân hàng, không được sửa/phá bản gốc, và (mục tiêu)
chỉ được chọn item đã qua duyệt (status='approved').
"""
import pytest
from sqlalchemy.orm import Session

from app.models.question import Question
from app.models.question_group import QuestionGroup
from app.services.toeic_generator import generate_toeic_exam


@pytest.mark.xfail(
    strict=False,
    reason="GAP SPEC-BANK-001: generate_toeic_exam chưa lọc status='approved' "
    "khi chọn câu/nhóm từ bank (backend/app/services/toeic_generator.py)",
)
def test_SPEC_BANK_001_only_approved_items_generated(db_session: Session):
    """SPEC-BANK-001: Thuật toán sinh đề chỉ được chọn câu hỏi/nhóm có
    status='approved' từ ngân hàng; item draft/retired không bao giờ xuất hiện
    trong đề sinh ra.

    Kịch bản: chuyển TOÀN BỘ câu Part 5 trong bank về status='draft' rồi sinh đề.
    Đề hợp lệ không được chứa câu Part 5 nào (hoặc raise lỗi thiếu bank theo
    SPEC-GEN-006).
    """
    db_session.query(Question).filter(
        Question.exam_id.is_(None), Question.part == 5
    ).update({"status": "draft"}, synchronize_session=False)
    db_session.commit()
    db_session.expire_all()

    exam = generate_toeic_exam(db_session, title="Đề kiểm tra SPEC-BANK-001")

    p5_in_exam = db_session.query(Question).filter(
        Question.exam_id == exam.id, Question.part == 5
    ).count()
    assert p5_in_exam == 0, (
        f"Đề chứa {p5_in_exam} câu Part 5 được clone từ item chưa duyệt (draft)"
    )


def test_SPEC_BANK_002_generation_preserves_bank(db_session: Session):
    """SPEC-BANK-002: Thao tác sinh đề chỉ CLONE dữ liệu từ ngân hàng; tập câu
    hỏi/nhóm gốc (exam_id IS NULL) phải bất biến cả về số lượng lẫn nội dung.
    """
    def bank_snapshot():
        questions = {
            (q.id, q.content, q.part, q.reference_answer, q.difficulty)
            for q in db_session.query(Question).filter(Question.exam_id.is_(None)).all()
        }
        groups = {
            (g.id, g.part, g.topic, g.passage_text, g.audio_url, g.difficulty)
            for g in db_session.query(QuestionGroup).filter(QuestionGroup.exam_id.is_(None)).all()
        }
        return questions, groups

    questions_before, groups_before = bank_snapshot()

    generate_toeic_exam(db_session, title="Đề kiểm tra SPEC-BANK-002")
    db_session.expire_all()

    questions_after, groups_after = bank_snapshot()
    assert questions_after == questions_before, "Sinh đề làm thay đổi câu hỏi trong bank"
    assert groups_after == groups_before, "Sinh đề làm thay đổi nhóm trong bank"
