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


def test_grade_speaking_real_mode_loads_local_static_audio():
    """Bug-fix guard (real-mode Speaking): khi CÓ Gemini key, grade_speaking phải
    đọc được file ghi âm lưu cục bộ tại /static/uploads/... bằng cách đọc ĐĨA, không
    gọi httpx với URL tương đối (trước đây raise UnsupportedProtocol -> điểm 0).

    Non-tautological: dùng FakeModel để vào nhánh real-mode (model != None); nếu
    audio không nạp được, FakeModel không nhận đúng bytes và assert sẽ đỏ.
    """
    from app.services.ai_grading import AIGradingService

    backend_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # backend/
    uploads = os.path.join(backend_root, "static", "uploads")
    os.makedirs(uploads, exist_ok=True)
    fname = "test_speaking_guard.webm"
    fpath = os.path.join(uploads, fname)
    with open(fpath, "wb") as f:
        f.write(b"FAKE-AUDIO-BYTES")

    captured = {}

    class _FakeResponse:
        text = json.dumps({
            "score": 7.0,
            "transcription": "hello",
            "feedback": "ok",
            "pronunciation_issues": [],
        })

    class _FakeModelsService:
        def generate_content(self, model, contents, config=None):
            # contents = [audio_part, prompt]
            part = contents[0]
            if hasattr(part, "inline_data") and part.inline_data:
                captured["data"] = part.inline_data.data
                captured["mime"] = part.inline_data.mime_type
            else:
                captured["data"] = getattr(part, "data", None)
                captured["mime"] = getattr(part, "mime_type", None)
            return _FakeResponse()

    class _FakeClient:
        def __init__(self):
            self.models = _FakeModelsService()

    try:
        service = AIGradingService()
        service.client = _FakeClient()
        service.model = service.client  # ép nhánh real-mode (không gọi mạng thật)
        result = service.grade_speaking(
            audio_url=f"/static/uploads/{fname}",
            prompt_requirements="Talk about your hometown.",
            language="EN",
        )
        assert result["score"] == 7.0, "real-mode phải trả điểm từ model, không phải nhánh lỗi (0.0)"
        assert captured.get("data") == b"FAKE-AUDIO-BYTES", "phải đọc đúng bytes file ghi âm cục bộ từ đĩa"
        assert captured.get("mime") == "audio/webm", "mime suy từ đuôi .webm"
    finally:
        os.remove(fpath)


def test_grade_speaking_without_audio_does_not_crash():
    """Bug-fix guard: câu Nói nộp KHÔNG có bản ghi (audio_url=None) phải trả về 0
    điểm một cách an toàn, KHÔNG ném lỗi — kể cả ở real-mode (trước đây
    _load_audio_bytes(None) gây AttributeError 'NoneType'... .startswith).

    Non-tautological: gắn FakeModel (real-mode); guard phải chặn TRƯỚC khi gọi model
    nên model.generate_content không bao giờ được gọi.
    """
    from app.services.ai_grading import AIGradingService

    class _BoomModelsService:
        def generate_content(self, *a, **k):
            raise AssertionError("không được gọi model khi không có audio")

    class _BoomClient:
        def __init__(self):
            self.models = _BoomModelsService()

    service = AIGradingService()
    service.client = _BoomClient()
    service.model = service.client  # real-mode, nhưng guard phải chặn trước
    for missing in (None, ""):
        result = service.grade_speaking(
            audio_url=missing,
            prompt_requirements="Giới thiệu bản thân.",
            language="EN",
        )
        assert result["score"] == 0.0
        assert {"score", "transcription", "feedback", "pronunciation_issues"} <= set(result.keys())


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


def test_SPEC_GRADE_005_ai_grading_retry_and_backoff(monkeypatch):
    """SPEC-GRADE-005: Thêm retry + backoff cho chấm AI khi Gemini trả lỗi tạm thời (503/429),
    fail-fast với lỗi vĩnh viễn (404/401/403/JSON parse), có chặn thời gian (<= 20s), không bao giờ crash.
    """
    import time
    from app.services.ai_grading import AIGradingService
    from google.genai.errors import ServerError, ClientError

    # Mock settings
    monkeypatch.setattr(settings, "GEMINI_MAX_RETRIES", 4)
    monkeypatch.setattr(settings, "GEMINI_RETRY_BASE_DELAY", 0.001)

    # Mock sleep to prevent delays in test
    sleep_calls = []
    def mock_sleep(seconds):
        sleep_calls.append(seconds)
    monkeypatch.setattr("app.services.ai_grading.time.sleep", mock_sleep)

    # Case 1: Transient 503 (ServerError) twice, then success
    call_count = 0
    class _FakeTransientModelsService:
        def generate_content(self, model, contents, config=None):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ServerError(code=503, response_json={"error": {"status": "UNAVAILABLE", "message": "Service Unavailable"}})
            
            # Return valid JSON response on 3rd attempt
            class _FakeResponse:
                text = json.dumps({
                    "score": 8.5,
                    "feedback": "Good essay after retry",
                    "grammar_errors": []
                })
            return _FakeResponse()

    class _FakeTransientClient:
        def __init__(self):
            self.models = _FakeTransientModelsService()

    service = AIGradingService()
    service.client = _FakeTransientClient()
    service.model = service.client # Force real-mode mock

    res = service.grade_writing(
        essay_text="Environment protection essay...",
        prompt_requirements="Write an email about the environment."
    )

    # Assertions
    assert call_count == 3, "Should retry and succeed on the 3rd attempt"
    assert res["score"] == 8.5
    assert len(sleep_calls) == 2, "Should sleep twice"
    assert sleep_calls[0] > 0

    # Case 2: Permanent 404 (ClientError)
    call_count_perm = 0
    class _FakePermanentModelsService:
        def generate_content(self, model, contents, config=None):
            nonlocal call_count_perm
            call_count_perm += 1
            raise ClientError(code=404, response_json={"error": {"status": "NOT_FOUND", "message": "Model not found"}})

    class _FakePermanentClient:
        def __init__(self):
            self.models = _FakePermanentModelsService()

    service_perm = AIGradingService()
    service_perm.client = _FakePermanentClient()
    service_perm.model = service_perm.client

    res_perm = service_perm.grade_writing(
        essay_text="Environment protection essay...",
        prompt_requirements="Write an email about the environment."
    )

    assert call_count_perm == 1, "Should fail fast and not retry permanent error"
    assert res_perm["score"] == 0.0, "Should return score 0 gracefully"
    assert "NOT_FOUND" in res_perm["feedback"] or "404" in res_perm["feedback"]

    # Case 3: Transient 429 (ClientError) exceeds limit
    call_count_limit = 0
    class _FakeLimitModelsService:
        def generate_content(self, model, contents, config=None):
            nonlocal call_count_limit
            call_count_limit += 1
            raise ClientError(code=429, response_json={"error": {"status": "RESOURCE_EXHAUSTED", "message": "Rate limit exceeded"}})

    class _FakeLimitClient:
        def __init__(self):
            self.models = _FakeLimitModelsService()

    service_limit = AIGradingService()
    service_limit.client = _FakeLimitClient()
    service_limit.model = service_limit.client

    sleep_calls.clear()

    res_limit = service_limit.grade_writing(
        essay_text="Environment protection essay...",
        prompt_requirements="Write an email about the environment."
    )

    # GEMINI_MAX_RETRIES is 4, so first try + 4 retries = 5 calls total
    assert call_count_limit == 5, f"Should try exactly 5 times (1 original + 4 retries), got {call_count_limit}"
    assert len(sleep_calls) == 4, f"Should sleep 4 times, got {len(sleep_calls)}"
    assert res_limit["score"] == 0.0

    # Case 4: Time budget cap (20s)
    call_count_budget = 0
    class _FakeBudgetModelsService:
        def generate_content(self, model, contents, config=None):
            nonlocal call_count_budget
            call_count_budget += 1
            raise ServerError(code=503, response_json={"error": {"status": "UNAVAILABLE", "message": "Service Unavailable"}})

    class _FakeBudgetClient:
        def __init__(self):
            self.models = _FakeBudgetModelsService()

    service_budget = AIGradingService()
    service_budget.client = _FakeBudgetClient()
    service_budget.model = service_budget.client

    # Set base delay large enough to exceed 20s budget quickly
    monkeypatch.setattr(settings, "GEMINI_RETRY_BASE_DELAY", 15.0)
    sleep_calls.clear()

    res_budget = service_budget.grade_writing(
        essay_text="Environment protection essay...",
        prompt_requirements="Write an email about the environment."
    )

    # Assert cumulative sleep time is clamped to <= 20s
    total_sleep = sum(sleep_calls)
    assert total_sleep <= 20.0, f"Total sleep time should be capped under 20.0s, got {total_sleep}"
    assert total_sleep >= 10.0, f"Total sleep time should be significant, got {total_sleep}"
    assert call_count_budget >= 2, f"Should try at least twice, got {call_count_budget}"


def test_SPEC_GRADE_006_vstep_b1_grading(db_session: Session, monkeypatch):
    """SPEC-GRADE-006: Kiểm tra chấm đề VSTEP B1 thang 100 điểm, so khớp điền từ
    chuẩn hoá, và tính điều kiện đạt/rớt.
    """
    from sqlalchemy.orm import sessionmaker
    from app.core.celery import celery_app
    from app.models.exam import Exam
    from app.models.question import Question
    from app.models.submission import Submission as SubmissionModel, SubmissionDetail
    from app.models.grade import Grade as GradeModel
    from app.models.user import User
    import app.workers.tasks as tasks_module

    # Worker Session trỏ về engine test
    test_engine = db_session.get_bind()
    WorkerSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    monkeypatch.setattr(tasks_module, "SessionLocal", WorkerSession)

    # Mock AI grading
    def fake_grade_writing(essay_text, prompt_requirements, reference_answer=None, language="EN"):
        if "Task 1" in prompt_requirements:
            return {"score": 8.0, "feedback": "Good task 1", "grammar_errors": []}
        return {"score": 9.0, "feedback": "Excellent task 2", "grammar_errors": []}

    def fake_grade_speaking(audio_url, prompt_requirements, reference_answer=None, language="EN"):
        if "Part 1" in prompt_requirements:
            return {"score": 7.0, "feedback": "Good part 1", "pronunciation_issues": []}
        elif "Part 2" in prompt_requirements:
            return {"score": 8.0, "feedback": "Good part 2", "pronunciation_issues": []}
        return {"score": 9.0, "feedback": "Good part 3", "pronunciation_issues": []}

    monkeypatch.setattr(tasks_module.ai_grading_service, "grade_writing", fake_grade_writing)
    monkeypatch.setattr(tasks_module.ai_grading_service, "grade_speaking", fake_grade_speaking)

    # Celery eager mode
    monkeypatch.setattr(celery_app.conf, "task_always_eager", True)
    monkeypatch.setattr(celery_app.conf, "task_eager_propagates", True)

    user = db_session.query(User).filter(User.username == "testcandidate").first()

    # ── Test Case 1: Thí sinh trượt (Không đạt) do thiếu điểm (Tổng 47.0 < 50.0) ──
    exam_fail = Exam(
        title="VSTEP B1 Exam - Failing",
        language="EN",
        exam_type="VSTEP_B1",
        duration_minutes=135,
        is_active=True,
    )
    db_session.add(exam_fail)
    db_session.commit()

    # Tạo câu hỏi
    q_read_mcq = Question(exam_id=exam_fail.id, part=1, type="choice", reference_answer="A", content="Q1 MCQ")
    q_read_fill = Question(exam_id=exam_fail.id, part=4, type="fill", reference_answer="12/twelve", content="Q2 Fill")
    q_write_1 = Question(exam_id=exam_fail.id, part=5, type="writing", content="Task 1 prompt")
    q_write_2 = Question(exam_id=exam_fail.id, part=6, type="writing", content="Task 2 prompt")
    q_listen_mcq = Question(exam_id=exam_fail.id, part=7, type="choice", reference_answer="B", content="Q5 MCQ")
    q_listen_fill = Question(exam_id=exam_fail.id, part=8, type="fill", reference_answer="3/ three", content="Q6 Fill")
    q_speak_1 = Question(exam_id=exam_fail.id, part=9, type="speaking", content="Part 1 prompt")
    q_speak_2 = Question(exam_id=exam_fail.id, part=10, type="speaking", content="Part 2 prompt")
    q_speak_3 = Question(exam_id=exam_fail.id, part=11, type="speaking", content="Part 3 prompt")

    db_session.add_all([
        q_read_mcq, q_read_fill, q_write_1, q_write_2,
        q_listen_mcq, q_listen_fill, q_speak_1, q_speak_2, q_speak_3
    ])
    db_session.commit()

    sub_fail = SubmissionModel(exam_id=exam_fail.id, user_id=user.id, status="pending")
    db_session.add(sub_fail)
    db_session.commit()

    # Thêm câu trả lời
    db_session.add_all([
        SubmissionDetail(submission_id=sub_fail.id, question_id=q_read_mcq.id, candidate_text="A"), # correct -> 1
        SubmissionDetail(submission_id=sub_fail.id, question_id=q_read_fill.id, candidate_text="twelve"), # correct variation -> 1. Total Reading = 2.0 (Failed threshold < 9.0)
        SubmissionDetail(submission_id=sub_fail.id, question_id=q_write_1.id, candidate_text="Writing 1 text"), # AI score -> 8.0
        SubmissionDetail(submission_id=sub_fail.id, question_id=q_write_2.id, candidate_text="Writing 2 text"), # AI score -> 9.0 * 2 = 18.0. Total Writing = 26.0
        SubmissionDetail(submission_id=sub_fail.id, question_id=q_listen_mcq.id, candidate_text="B"), # correct choice -> 2
        SubmissionDetail(submission_id=sub_fail.id, question_id=q_listen_fill.id, candidate_text="  three  "), # correct variation + spaces -> 1. Total Listening = 3.0 (Failed threshold < 6.0)
        SubmissionDetail(submission_id=sub_fail.id, question_id=q_speak_1.id, audio_url="/static/uploads/s1.webm"), # AI score -> 7.0
        SubmissionDetail(submission_id=sub_fail.id, question_id=q_speak_2.id, audio_url="/static/uploads/s2.webm"), # AI score -> 8.0
        SubmissionDetail(submission_id=sub_fail.id, question_id=q_speak_3.id, audio_url="/static/uploads/s3.webm"), # AI score -> 9.0. Total Speaking = (24/30)*20 = 16.0
    ])
    db_session.commit()

    # Chạy grading task
    tasks_module.grade_submission_task(submission_id=sub_fail.id)

    db_session.expire_all()
    sub_res = db_session.query(SubmissionModel).filter(SubmissionModel.id == sub_fail.id).first()
    assert sub_res.status == "completed"
    assert sub_res.grade is not None
    assert sub_res.grade.score_reading == 2.0
    assert sub_res.grade.score_listening == 3.0
    assert sub_res.grade.score_writing == 26.0
    assert sub_res.grade.score_speaking == 16.0
    assert sub_res.grade.score_total == 47.0
    
    # Check result
    result_fail = sub_res.grade.feedback_writing["vstep_result"]
    assert result_fail["status"] == "Không đạt"
    assert result_fail["conditions"]["total_passed"] is False
    assert result_fail["conditions"]["reading_passed"] is False
    assert result_fail["conditions"]["listening_passed"] is False
    assert result_fail["conditions"]["writing_passed"] is True
    assert result_fail["conditions"]["speaking_passed"] is True

    # ── Test Case 2: Thí sinh Đỗ (Đạt) ──
    exam_pass = Exam(
        title="VSTEP B1 Exam - Passing",
        language="EN",
        exam_type="VSTEP_B1",
        duration_minutes=135,
        is_active=True,
    )
    db_session.add(exam_pass)
    db_session.commit()

    # Reading: tạo 10 câu choice, 2 câu fill (Đọc >= 9.0). Ta tạo 9 câu MCQ và 1 câu Fill
    read_qs = []
    for idx in range(9):
        read_qs.append(Question(exam_id=exam_pass.id, part=1, type="choice", reference_answer="A", content=f"R MCQ {idx}"))
    read_qs.append(Question(exam_id=exam_pass.id, part=4, type="fill", reference_answer="12/twelve", content="R Fill"))

    # Listening: tạo 3 câu MCQ (worth 6 pts) + 1 fill
    listen_qs = [
        Question(exam_id=exam_pass.id, part=7, type="choice", reference_answer="A", content="L MCQ 1"),
        Question(exam_id=exam_pass.id, part=7, type="choice", reference_answer="A", content="L MCQ 2"),
        Question(exam_id=exam_pass.id, part=7, type="choice", reference_answer="A", content="L MCQ 3"),
        Question(exam_id=exam_pass.id, part=8, type="fill", reference_answer="3/ three", content="L Fill")
    ]

    q_write_1_p = Question(exam_id=exam_pass.id, part=5, type="writing", content="Task 1 prompt")
    q_write_2_p = Question(exam_id=exam_pass.id, part=6, type="writing", content="Task 2 prompt")
    q_speak_1_p = Question(exam_id=exam_pass.id, part=9, type="speaking", content="Part 1 prompt")
    q_speak_2_p = Question(exam_id=exam_pass.id, part=10, type="speaking", content="Part 2 prompt")
    q_speak_3_p = Question(exam_id=exam_pass.id, part=11, type="speaking", content="Part 3 prompt")

    db_session.add_all(read_qs + listen_qs + [q_write_1_p, q_write_2_p, q_speak_1_p, q_speak_2_p, q_speak_3_p])
    db_session.commit()

    sub_pass = SubmissionModel(exam_id=exam_pass.id, user_id=user.id, status="pending")
    db_session.add(sub_pass)
    db_session.commit()

    # Thí sinh làm đúng hết
    details = []
    for rq in read_qs[:-1]:
        details.append(SubmissionDetail(submission_id=sub_pass.id, question_id=rq.id, candidate_text="A")) # 9 correct -> 9 pts
    details.append(SubmissionDetail(submission_id=sub_pass.id, question_id=read_qs[-1].id, candidate_text="12")) # correct fill -> 1 pt. Total Reading = 10.0 (PASS)
    
    for lq in listen_qs[:3]:
        details.append(SubmissionDetail(submission_id=sub_pass.id, question_id=lq.id, candidate_text="A")) # 3 correct MCQ x 2 -> 6 pts
    details.append(SubmissionDetail(submission_id=sub_pass.id, question_id=listen_qs[-1].id, candidate_text="three")) # correct fill -> 1 pt. Total Listening = 7.0 (PASS)

    details.extend([
        SubmissionDetail(submission_id=sub_pass.id, question_id=q_write_1_p.id, candidate_text="Writing 1 text"), # AI score -> 8.0
        SubmissionDetail(submission_id=sub_pass.id, question_id=q_write_2_p.id, candidate_text="Writing 2 text"), # AI score -> 9.0 * 2 = 18.0. Total Writing = 26.0 (PASS)
        SubmissionDetail(submission_id=sub_pass.id, question_id=q_speak_1_p.id, audio_url="/static/uploads/s1.webm"), # AI score -> 7.0
        SubmissionDetail(submission_id=sub_pass.id, question_id=q_speak_2_p.id, audio_url="/static/uploads/s2.webm"), # AI score -> 8.0
        SubmissionDetail(submission_id=sub_pass.id, question_id=q_speak_3_p.id, audio_url="/static/uploads/s3.webm"), # AI score -> 9.0. Total Speaking = 16.0 (PASS)
    ])
    db_session.add_all(details)
    db_session.commit()

    # Chạy grading task
    tasks_module.grade_submission_task(submission_id=sub_pass.id)

    db_session.expire_all()
    sub_res_p = db_session.query(SubmissionModel).filter(SubmissionModel.id == sub_pass.id).first()
    assert sub_res_p.status == "completed"
    assert sub_res_p.grade.score_reading == 10.0
    assert sub_res_p.grade.score_listening == 7.0
    assert sub_res_p.grade.score_writing == 26.0
    assert sub_res_p.grade.score_speaking == 16.0
    assert sub_res_p.grade.score_total == 59.0

    # Check result
    result_pass = sub_res_p.grade.feedback_writing["vstep_result"]
    assert result_pass["status"] == "Đạt"
    assert result_pass["conditions"]["total_passed"] is True
    assert result_pass["conditions"]["reading_passed"] is True
    assert result_pass["conditions"]["listening_passed"] is True
    assert result_pass["conditions"]["writing_passed"] is True
    assert result_pass["conditions"]["speaking_passed"] is True


