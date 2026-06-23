"""
SPEC-GRADE-* — Bảo chứng phân hệ Chấm thi (trắc nghiệm tức thì + tự luận AI).

Trắc nghiệm: so khớp đáp án + quy đổi qua bảng chuẩn toeic_scoring_table.json.
Tự luận (Writing/Speaking): chấm bằng Gemini, mục tiêu bất đồng bộ qua Celery.
"""
import json
import os

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


def test_SPEC_GRADE_003_async_grading_via_celery(db_session: Session, monkeypatch):
    """SPEC-GRADE-003: Bài Writing/Speaking phải được chấm bất đồng bộ: API nộp
    bài đẩy task vào hàng đợi Redis và phản hồi ngay trạng thái grading; Celery
    worker chấm ngầm qua Gemini rồi ghi kết quả vào bảng grades.

    Cô lập: chạy Celery ở eager mode (không cần Redis), ép AI grading về mock mode
    (không gọi mạng), và trỏ SessionLocal của worker về engine test (StaticPool
    in-memory) để worker thấy submission vừa tạo.
    """
    from fastapi.testclient import TestClient
    from sqlalchemy.orm import sessionmaker

    from app.main import app as fastapi_app
    from app.core.database import get_db
    from app.core.security import create_access_token
    from app.core.celery import celery_app
    from app.models.exam import Exam
    import app.workers.tasks as tasks_module

    # Worker mở session riêng (SessionLocal) -> trỏ về engine test để thấy dữ liệu.
    test_engine = db_session.get_bind()
    WorkerSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    monkeypatch.setattr(tasks_module, "SessionLocal", WorkerSession)

    # Ép AI grading về mock mode (không gọi Gemini/mạng) — model=None -> nhánh mock.
    monkeypatch.setattr(tasks_module.ai_grading_service, "model", None)

    # Celery eager: task chạy đồng bộ trong tiến trình test, không cần broker Redis.
    monkeypatch.setattr(celery_app.conf, "task_always_eager", True)
    monkeypatch.setattr(celery_app.conf, "task_eager_propagates", True)

    candidate_token = create_access_token(data={"sub": "testcandidate", "role": "candidate"})
    candidate_headers = {"Authorization": f"Bearer {candidate_token}"}

    fastapi_app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(fastapi_app)
    try:
        # Đề Writing (VSTEP) — có câu tự luận -> phải đi đường chấm bất đồng bộ.
        exam = Exam(
            title="VSTEP Writing — SPEC-GRADE-003",
            language="EN",
            exam_type="VSTEP",
            duration_minutes=60,
            is_active=True,
        )
        db_session.add(exam)
        db_session.commit()
        db_session.refresh(exam)

        writing_q = Question(
            exam_id=exam.id, part=1, type="writing",
            content="Write an email of about 120 words about protecting the environment.",
            reference_answer=None, status="approved",
        )
        db_session.add(writing_q)
        db_session.commit()
        db_session.refresh(writing_q)

        essay = "Dear Sir, I am writing to share some ideas about protecting our environment..."
        resp = client.post(
            f"/api/v1/exams/{exam.id}/submit",
            json={"answers": [{"question_id": writing_q.id, "answer": essay}]},
            headers=candidate_headers,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        sub_id = body["submission_id"]

        # API phản hồi NGAY trạng thái grading, KHÔNG chờ điểm Gemini.
        assert body["status"] == "grading"
        assert body["total_score"] is None
        assert body["listening_score"] is None

        # Worker eager đã chạy ngầm -> grades có bản ghi, submission completed.
        db_session.expire_all()
        from app.models.submission import Submission as SubmissionModel
        sub = db_session.query(SubmissionModel).filter(SubmissionModel.id == sub_id).first()
        assert sub is not None
        assert sub.status == "completed"
        assert sub.grade is not None
        assert sub.grade.score_writing > 0
        assert sub.grade.score_total > 0
    finally:
        fastapi_app.dependency_overrides.clear()


def test_async_grading_mixed_choice_and_writing(db_session: Session, monkeypatch):
    """Guard cho đề HỖN HỢP (trắc nghiệm + tự luận, vd VSTEP B1 Reading+Writing) đi
    qua đường chấm bất đồng bộ (SPEC-GRADE-003): worker phải chấm CẢ phần trắc
    nghiệm (score_multiple_choice = số câu đúng) lẫn phần tự luận (score_writing).
    """
    from fastapi.testclient import TestClient
    from sqlalchemy.orm import sessionmaker

    from app.main import app as fastapi_app
    from app.core.database import get_db
    from app.core.security import create_access_token
    from app.core.celery import celery_app
    from app.models.exam import Exam
    import app.workers.tasks as tasks_module

    test_engine = db_session.get_bind()
    WorkerSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    monkeypatch.setattr(tasks_module, "SessionLocal", WorkerSession)
    monkeypatch.setattr(tasks_module.ai_grading_service, "model", None)
    monkeypatch.setattr(celery_app.conf, "task_always_eager", True)
    monkeypatch.setattr(celery_app.conf, "task_eager_propagates", True)

    candidate_token = create_access_token(data={"sub": "testcandidate", "role": "candidate"})
    candidate_headers = {"Authorization": f"Bearer {candidate_token}"}

    fastapi_app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(fastapi_app)
    try:
        exam = Exam(title="VSTEP Mixed", language="EN", exam_type="VSTEP",
                    duration_minutes=90, is_active=True)
        db_session.add(exam)
        db_session.commit()
        db_session.refresh(exam)

        q1 = Question(exam_id=exam.id, part=1, type="choice", content="R1",
                      reference_answer="A", options={"A": "a", "B": "b"}, status="approved")
        q2 = Question(exam_id=exam.id, part=1, type="choice", content="R2",
                      reference_answer="B", options={"A": "a", "B": "b"}, status="approved")
        qw = Question(exam_id=exam.id, part=2, type="writing",
                      content="Write ~150 words about working from home.", status="approved")
        db_session.add_all([q1, q2, qw])
        db_session.commit()
        for q in (q1, q2, qw):
            db_session.refresh(q)

        # One MCQ correct (q1=A), one wrong (q2: send A but answer is B), plus an essay.
        resp = client.post(
            f"/api/v1/exams/{exam.id}/submit",
            json={"answers": [
                {"question_id": q1.id, "answer": "A"},
                {"question_id": q2.id, "answer": "A"},
                {"question_id": qw.id, "answer": "Working from home saves commuting time but can feel isolating..."},
            ]},
            headers=candidate_headers,
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == "grading"

        db_session.expire_all()
        from app.models.submission import Submission as SubmissionModel
        sub = db_session.query(SubmissionModel).filter(
            SubmissionModel.id == resp.json()["submission_id"]
        ).first()
        assert sub.status == "completed"
        assert sub.grade is not None
        assert sub.grade.score_multiple_choice == 1.0, "đúng 1/2 câu trắc nghiệm"
        assert sub.grade.score_writing > 0, "phần tự luận phải được chấm AI"
    finally:
        fastapi_app.dependency_overrides.clear()


def test_async_grading_speaking(db_session: Session, monkeypatch):
    """Đề Speaking (audio) đi qua đường chấm bất đồng bộ (SPEC-GRADE-003): worker gọi
    ai_grading_service.grade_speaking (mock mode, không tải audio) -> ghi
    score_speaking + feedback_speaking[question_X].
    """
    from fastapi.testclient import TestClient
    from sqlalchemy.orm import sessionmaker

    from app.main import app as fastapi_app
    from app.core.database import get_db
    from app.core.security import create_access_token
    from app.core.celery import celery_app
    from app.models.exam import Exam
    import app.workers.tasks as tasks_module

    test_engine = db_session.get_bind()
    WorkerSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    monkeypatch.setattr(tasks_module, "SessionLocal", WorkerSession)
    monkeypatch.setattr(tasks_module.ai_grading_service, "model", None)  # mock, no network
    monkeypatch.setattr(celery_app.conf, "task_always_eager", True)
    monkeypatch.setattr(celery_app.conf, "task_eager_propagates", True)

    candidate_token = create_access_token(data={"sub": "testcandidate", "role": "candidate"})
    fastapi_app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(fastapi_app)
    try:
        exam = Exam(title="VSTEP Speaking", language="EN", exam_type="VSTEP",
                    duration_minutes=60, is_active=True)
        db_session.add(exam)
        db_session.commit()
        db_session.refresh(exam)
        qs = Question(exam_id=exam.id, part=3, type="speaking",
                      content="Talk about your hometown for 1 minute.", status="approved")
        db_session.add(qs)
        db_session.commit()
        db_session.refresh(qs)

        resp = client.post(
            f"/api/v1/exams/{exam.id}/submit",
            json={"answers": [{"question_id": qs.id, "answer": "", "audio_url": "/static/uploads/x.webm"}]},
            headers={"Authorization": f"Bearer {candidate_token}"},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == "grading"

        db_session.expire_all()
        from app.models.submission import Submission as SubmissionModel
        sub = db_session.query(SubmissionModel).filter(
            SubmissionModel.id == resp.json()["submission_id"]
        ).first()
        assert sub.status == "completed"
        assert sub.grade is not None
        assert sub.grade.score_speaking > 0, "phần Nói phải được chấm AI"
        assert f"question_{qs.id}" in (sub.grade.feedback_speaking or {})
    finally:
        fastapi_app.dependency_overrides.clear()


def test_async_grading_falls_back_to_inline_without_broker(db_session: Session, monkeypatch):
    """Khi KHÔNG có broker/worker Celery (vd Render free không Redis): submit đề tự
    luận vẫn phải chấm xong — endpoint bắt lỗi enqueue và chấm nội tuyến (.apply).
    Mô phỏng bằng cách ép grade_submission_task.delay() raise.
    """
    from fastapi.testclient import TestClient
    from sqlalchemy.orm import sessionmaker

    from app.main import app as fastapi_app
    from app.core.database import get_db
    from app.core.security import create_access_token
    from app.models.exam import Exam
    import app.workers.tasks as tasks_module

    test_engine = db_session.get_bind()
    WorkerSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    monkeypatch.setattr(tasks_module, "SessionLocal", WorkerSession)
    monkeypatch.setattr(tasks_module.ai_grading_service, "model", None)

    # Giả lập KHÔNG có broker: .delay() ném lỗi -> service phải fallback .apply().
    def _boom(*a, **k):
        raise RuntimeError("no broker reachable")
    monkeypatch.setattr(tasks_module.grade_submission_task, "delay", _boom)

    candidate_token = create_access_token(data={"sub": "testcandidate", "role": "candidate"})
    fastapi_app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(fastapi_app)
    try:
        exam = Exam(title="VSTEP fallback", language="EN", exam_type="VSTEP",
                    duration_minutes=60, is_active=True)
        db_session.add(exam)
        db_session.commit()
        db_session.refresh(exam)
        qw = Question(exam_id=exam.id, part=1, type="writing",
                      content="Write about your hometown.", status="approved")
        db_session.add(qw)
        db_session.commit()
        db_session.refresh(qw)

        resp = client.post(
            f"/api/v1/exams/{exam.id}/submit",
            json={"answers": [{"question_id": qw.id, "answer": "My hometown is a quiet coastal town..."}]},
            headers={"Authorization": f"Bearer {candidate_token}"},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == "grading"

        db_session.expire_all()
        from app.models.submission import Submission as SubmissionModel
        sub = db_session.query(SubmissionModel).filter(
            SubmissionModel.id == resp.json()["submission_id"]
        ).first()
        assert sub.status == "completed", "fallback inline phải chấm xong dù không có broker"
        assert sub.grade is not None and sub.grade.score_writing > 0
    finally:
        fastapi_app.dependency_overrides.clear()


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
