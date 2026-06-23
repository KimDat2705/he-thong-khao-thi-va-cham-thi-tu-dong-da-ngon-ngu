"""
SPEC-GRADE-* — Bảo chứng phân hệ Chấm thi (trắc nghiệm tức thì + tự luận AI).

Trắc nghiệm: so khớp đáp án + quy đổi qua bảng chuẩn toeic_scoring_table.json.
Tự luận (Writing/Speaking): chấm bằng Gemini, mục tiêu bất đồng bộ qua Celery.
"""
import json
import os

import pytest
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.grade import Grade
from app.models.submission import Submission, SubmissionDetail
from app.models.question import Question
from app.models.user import User
from app.services.toeic_generator import generate_toeic_exam
from app.services.toeic_grader import grade_toeic_submission

SCORING_TABLE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "app", "core", "toeic_scoring_table.json",
)


def test_SPEC_GRADE_001_scoring_table_properties():
    """SPEC-GRADE-001: Bảng quy đổi toeic_scoring_table.json — mỗi kỹ năng
    (listening/reading) phủ đủ 0-100% câu đúng (101 phần tử), điểm 5-495,
    dãy đơn điệu không giảm.

    (Phần E2E "điểm chấm khớp tra bảng, tổng = L + R" được xác nhận bởi
    tests/test_toeic_grader.py::test_grade_toeic_submission_success.)
    """
    with open(SCORING_TABLE_PATH, "r", encoding="utf-8") as f:
        table = json.load(f)

    for section in ("listening", "reading"):
        scores = table[section]
        assert len(scores) == 101, f"Bảng {section}: kỳ vọng 101 phần tử (0-100%), thực tế {len(scores)}"
        assert min(scores) >= 5, f"Bảng {section}: điểm nhỏ nhất phải >= 5"
        assert max(scores) <= 495, f"Bảng {section}: điểm lớn nhất phải <= 495"
        for i in range(1, len(scores)):
            assert scores[i] >= scores[i - 1], (
                f"Bảng {section}: không đơn điệu tại index {i} ({scores[i - 1]} -> {scores[i]})"
            )


def test_SPEC_GRADE_002_score_field_semantics(db_session: Session):
    """SPEC-GRADE-002: Điểm Listening và Reading phải được lưu trong trường có
    tên đúng ngữ nghĩa (score_listening/score_reading), không mượn trường
    score_speaking/score_writing.
    """
    assert hasattr(Grade, "score_listening"), "Model Grade thiếu cột score_listening"
    assert hasattr(Grade, "score_reading"), "Model Grade thiếu cột score_reading"

    # Khi cột tồn tại: chấm thật và xác nhận giá trị nằm đúng trường
    exam = generate_toeic_exam(db_session, title="Đề kiểm tra SPEC-GRADE-002")
    user = db_session.query(User).filter(User.username == "testcandidate").first()
    submission = Submission(exam_id=exam.id, user_id=user.id, status="pending")
    db_session.add(submission)
    db_session.commit()
    db_session.refresh(submission)

    questions = db_session.query(Question).filter(Question.exam_id == exam.id).all()
    for q in questions:
        db_session.add(SubmissionDetail(
            submission_id=submission.id, question_id=q.id, candidate_text=q.reference_answer
        ))
    db_session.commit()

    grade = grade_toeic_submission(db_session, submission_id=submission.id)
    assert grade.score_listening > 0, "score_listening phải chứa điểm Nghe"
    assert grade.score_reading > 0, "score_reading phải chứa điểm Đọc"
    assert grade.score_total == grade.score_listening + grade.score_reading


@pytest.mark.skip(
    reason="SPEC-GRADE-003: task grade_submission_task đã định nghĩa trong "
    "app/workers/tasks.py nhưng API đang chấm ĐỒNG BỘ — test sẽ dùng celery "
    "eager mode sau khi endpoint submit được nối vào hàng đợi"
)
def test_SPEC_GRADE_003_async_grading_via_celery(db_session: Session):
    """SPEC-GRADE-003: Bài Writing/Speaking phải được chấm bất đồng bộ: API nộp
    bài đẩy task vào hàng đợi Redis và phản hồi trạng thái pending trong <= 2 giây;
    Celery worker chấm ngầm qua Gemini rồi ghi kết quả vào bảng grades.

    Kế hoạch test khi nối queue: bật task_always_eager, gọi endpoint submit với
    câu writing, assert response trả ngay (status pending/grading) và sau khi task
    eager chạy xong thì grades có bản ghi, submission.status='completed'.
    """
    from app.core.celery import celery_app
    from app.workers.tasks import grade_submission_task

    celery_app.conf.task_always_eager = True
    result = grade_submission_task.delay(submission_id=1)
    assert result.get()["status"] == "success"


def test_SPEC_GRADE_004_ai_grading_degrades_safely(monkeypatch):
    """SPEC-GRADE-004: Khi Gemini API thiếu key hoặc lỗi, dịch vụ chấm AI phải
    trả về kết quả có cấu trúc (mock mode), tuyệt đối không ném exception và
    không gọi mạng ra ngoài.
    """
    monkeypatch.setattr(settings, "GEMINI_API_KEY", None)

    from app.services.ai_grading import AIGradingService
    service = AIGradingService()  # khởi tạo lại để nhận key=None -> mock mode
    assert service.model is None, "Thiếu key nhưng service vẫn khởi tạo model Gemini"

    writing_result = service.grade_writing(
        essay_text="Bài luận thử nghiệm về môi trường.",
        prompt_requirements="Viết email 120 từ về chủ đề môi trường.",
        language="EN",
    )
    assert isinstance(writing_result, dict)
    assert {"score", "feedback", "grammar_errors"} <= set(writing_result.keys()), \
        "grade_writing mock thiếu key bắt buộc"

    speaking_result = service.grade_speaking(
        audio_url="http://localhost/khong-ton-tai.webm",
        prompt_requirements="Giới thiệu bản thân trong 1 phút.",
        language="EN",
    )
    assert isinstance(speaking_result, dict)
    assert {"score", "transcription", "feedback", "pronunciation_issues"} <= set(speaking_result.keys()), \
        "grade_speaking mock thiếu key bắt buộc"
