from sqlalchemy.orm import Session, sessionmaker
import pytest
from fastapi.testclient import TestClient
from app.main import app as fastapi_app
from app.core.database import get_db
from app.core.security import create_access_token, hash_password
from app.models.exam import Exam
from app.models.question import Question
from app.models.user import User
from app.models.submission import Submission, SubmissionDetail
from app.models.grade import Grade
from app.core.celery import celery_app
import app.workers.tasks as tasks_module

@pytest.fixture(autouse=True)
def setup_celery_eager(monkeypatch, db_session):
    test_engine = db_session.get_bind()
    WorkerSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    monkeypatch.setattr(tasks_module, "SessionLocal", WorkerSession)
    monkeypatch.setattr(tasks_module.ai_grading_service, "model", None)  # Mock AI
    monkeypatch.setattr(celery_app.conf, "task_always_eager", True)
    monkeypatch.setattr(celery_app.conf, "task_eager_propagates", True)


def test_SPEC_SUBMIT_001_exam_grading_flow(db_session: Session, admin_auth_headers: dict):
    candidate_username = "testcandidate"
    candidate_token = create_access_token(data={"sub": candidate_username, "role": "candidate"})
    candidate_headers = {"Authorization": f"Bearer {candidate_token}"}

    db_user2 = User(
        username="testcandidate2",
        hashed_password=hash_password("password"),
        full_name="Second Candidate",
        role="candidate",
        is_active=True
    )
    db_session.add(db_user2)
    db_session.commit()
    db_session.refresh(db_user2)
    candidate2_token = create_access_token(data={"sub": "testcandidate2", "role": "candidate"})
    candidate2_headers = {"Authorization": f"Bearer {candidate2_token}"}

    fastapi_app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(fastapi_app)

    try:
        # Create mock B1 exam
        exam = Exam(
            title="Grading Test B1",
            language="EN",
            exam_type="VSTEP_B1",
            duration_minutes=120,
            is_active=True
        )
        db_session.add(exam)
        db_session.commit()
        db_session.refresh(exam)
        exam_id = exam.id

        # Insert questions
        q1 = Question(exam_id=exam_id, part=1, type="choice", content="Q1", reference_answer="A", options={"A": "a", "B": "b"}, status="approved")
        q2 = Question(exam_id=exam_id, part=5, type="writing", content="Essay prompt", reference_answer=None, status="approved")
        db_session.add_all([q1, q2])
        db_session.commit()

        # Submit answers
        answers = [
            {"question_id": q1.id, "answer": "A"},
            {"question_id": q2.id, "answer": "This is candidate essay for grading flow."}
        ]
        resp = client.post(f"/api/v1/exams/{exam_id}/submit", json={"answers": answers}, headers=candidate_headers)
        assert resp.status_code == 200
        res_data = resp.json()
        assert res_data["status"] == "grading"
        sub_id = res_data["submission_id"]

        # Poll submission details to verify Celery eager task completed grading
        db_session.expire_all()
        resp = client.get(f"/api/v1/submissions/{sub_id}", headers=candidate_headers)
        assert resp.status_code == 200
        sub_detail = resp.json()
        assert sub_detail["status"] == "completed"
        assert sub_detail["total_score"] is not None

        # Cross-user authorization (SPEC-SUBMIT-001): candidate2 must NOT read candidate1's
        # submission (privacy of exam results); unauthenticated must be rejected.
        resp = client.get(f"/api/v1/submissions/{sub_id}", headers=candidate2_headers)
        assert resp.status_code == 403
        resp = client.get(f"/api/v1/submissions/{sub_id}")
        assert resp.status_code == 401

        # Retired exam -> 404
        exam.is_active = False
        db_session.commit()
        resp = client.post(f"/api/v1/exams/{exam_id}/submit", json={"answers": answers}, headers=candidate_headers)
        assert resp.status_code == 404

    finally:
        fastapi_app.dependency_overrides.clear()


def test_upload_audio_endpoint(db_session: Session):
    import os
    token = create_access_token(data={"sub": "testcandidate", "role": "candidate"})
    fastapi_app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(fastapi_app)
    try:
        files = {"file": ("answer.webm", b"FAKEAUDIOBYTES", "audio/webm")}
        resp = client.post("/api/v1/submissions/upload-audio", files=files,
                           headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200, resp.text
        url = resp.json()["audio_url"]
        assert url.startswith("/static/uploads/") and url.endswith(".webm")

        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "static", url.replace("/static/", "", 1))
        assert os.path.isfile(path)
        os.remove(path)

        resp = client.post("/api/v1/submissions/upload-audio", files=files)
        assert resp.status_code == 401
    finally:
        fastapi_app.dependency_overrides.clear()


def test_SPEC_SUBMIT_003_teacher_grade_override(db_session: Session):
    teacher = User(username="teacher_s3", hashed_password=hash_password("x"),
                   full_name="Teacher S3", role="teacher", is_active=True)
    db_session.add(teacher)
    db_session.commit()

    cand_h = {"Authorization": f"Bearer {create_access_token(data={'sub': 'testcandidate', 'role': 'candidate'})}"}
    teach_h = {"Authorization": f"Bearer {create_access_token(data={'sub': 'teacher_s3', 'role': 'teacher'})}"}

    fastapi_app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(fastapi_app)
    try:
        exam = Exam(title="VSTEP Override", language="EN", exam_type="VSTEP_B1",
                    duration_minutes=90, is_active=True)
        db_session.add(exam)
        db_session.commit()
        db_session.refresh(exam)

        q1 = Question(exam_id=exam.id, part=5, type="writing", content="Essay prompt", status="approved")
        db_session.add(q1)
        db_session.commit()
        db_session.refresh(q1)

        resp = client.post(
            f"/api/v1/exams/{exam.id}/submit",
            json={"answers": [{"question_id": q1.id, "answer": "Writing answer text."}]},
            headers=cand_h,
        )
        sub_id = resp.json()["submission_id"]

        db_session.expire_all()
        # Teacher overrides the score
        override_payload = {
            "score_writing": 25.5,
            "teacher_note": "Improved vocabulary."
        }
        resp = client.patch(f"/api/v1/submissions/{sub_id}/grade", json=override_payload, headers=teach_h)
        assert resp.status_code == 200
        override_res = resp.json()
        assert override_res["score_writing"] == 25.5
        assert override_res["feedback_writing"]["teacher_note"] == "Improved vocabulary."
        assert override_res["total_score"] == 25.5

        # Candidate cannot override
        resp = client.patch(f"/api/v1/submissions/{sub_id}/grade", json=override_payload, headers=cand_h)
        assert resp.status_code == 403

    finally:
        fastapi_app.dependency_overrides.clear()


def test_SPEC_SUBMIT_002_submissions_listing(db_session: Session, admin_auth_headers: dict):
    candidate_headers = {"Authorization": f"Bearer {create_access_token(data={'sub': 'testcandidate', 'role': 'candidate'})}"}
    fastapi_app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(fastapi_app)
    try:
        exam = Exam(title="List Exam B1", language="EN", exam_type="VSTEP_B1", duration_minutes=120, is_active=True)
        db_session.add(exam)
        db_session.commit()
        db_session.refresh(exam)
        q1 = Question(exam_id=exam.id, part=1, type="choice", content="Q1", reference_answer="A",
                      options={"A": "a", "B": "b"}, status="approved")
        db_session.add(q1)
        db_session.commit()
        db_session.refresh(q1)

        # A candidate submits so the listings have a row to verify against.
        resp = client.post(f"/api/v1/exams/{exam.id}/submit",
                           json={"answers": [{"question_id": q1.id, "answer": "A"}]}, headers=candidate_headers)
        assert resp.status_code == 200

        # --- Teacher/admin listing: GET /exams/{id}/submissions ---
        resp = client.get(f"/api/v1/exams/{exam.id}/submissions?limit=10", headers=admin_auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list) and len(data) >= 1
        row = data[0]
        for field in ("submission_id", "user_id", "username", "status", "exam_type"):
            assert field in row, f"missing field {field}"
        assert row["username"] == "testcandidate"
        # Gating: candidate -> 403, guest -> 401, missing exam -> 404
        assert client.get(f"/api/v1/exams/{exam.id}/submissions", headers=candidate_headers).status_code == 403
        assert client.get(f"/api/v1/exams/{exam.id}/submissions").status_code == 401
        assert client.get("/api/v1/exams/999999/submissions", headers=admin_auth_headers).status_code == 404

        # --- Candidate history: GET /submissions/me ---
        assert client.get("/api/v1/submissions/me").status_code == 401  # guest rejected
        resp = client.get("/api/v1/submissions/me", headers=candidate_headers)
        assert resp.status_code == 200
        mine = resp.json()
        assert isinstance(mine, list) and len(mine) >= 1
        for field in ("submission_id", "exam_id", "exam_title", "status"):
            assert field in mine[0], f"missing field {field}"
        assert mine[0]["exam_id"] == exam.id
    finally:
        fastapi_app.dependency_overrides.clear()


def test_exam_session_start_autosave_resume_submit(db_session: Session):
    cand_headers = {"Authorization": f"Bearer {create_access_token(data={'sub': 'testcandidate', 'role': 'candidate'})}"}
    fastapi_app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(fastapi_app)
    try:
        exam = Exam(title="Autosave B1", language="EN", exam_type="VSTEP_B1", duration_minutes=120, is_active=True)
        db_session.add(exam)
        db_session.commit()
        db_session.refresh(exam)

        q1 = Question(exam_id=exam.id, part=1, type="choice", content="Q1", reference_answer="A", status="approved")
        db_session.add(q1)
        db_session.commit()
        db_session.refresh(q1)

        # 1. Start the exam session
        resp = client.post(f"/api/v1/exams/{exam.id}/start", headers=cand_headers)
        assert resp.status_code == 200
        start_data = resp.json()
        sub_id = start_data["submission_id"]

        # 2. Autosave answer
        save_payload = {"answers": [{"question_id": q1.id, "answer": "B"}]}
        resp = client.post(f"/api/v1/submissions/{sub_id}/autosave", json=save_payload, headers=cand_headers)
        assert resp.status_code == 200

        # 3. Resume (GET /exams/{id}/start returns current in-progress details)
        resp = client.post(f"/api/v1/exams/{exam.id}/start", headers=cand_headers)
        assert resp.status_code == 200
        resume_data = resp.json()
        assert resume_data["answers"][0]["candidate_text"] == "B"

        # 4. Submit
        resp = client.post(f"/api/v1/exams/{exam.id}/submit", json={"answers": [{"question_id": q1.id, "answer": "A"}]}, headers=cand_headers)
        assert resp.status_code == 200
    finally:
        fastapi_app.dependency_overrides.clear()


def test_autosave_gating(db_session: Session):
    cand_headers = {"Authorization": f"Bearer {create_access_token(data={'sub': 'testcandidate', 'role': 'candidate'})}"}
    fastapi_app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(fastapi_app)
    try:
        exam = Exam(title="Gating B1", language="EN", exam_type="VSTEP_B1", duration_minutes=120, is_active=True)
        db_session.add(exam)
        db_session.commit()
        db_session.refresh(exam)

        q1 = Question(exam_id=exam.id, part=1, type="choice", content="Q1", reference_answer="A", status="approved")
        db_session.add(q1)
        db_session.commit()
        db_session.refresh(q1)

        resp = client.post(f"/api/v1/exams/{exam.id}/start", headers=cand_headers)
        sub_id = resp.json()["submission_id"]

        # Submit
        client.post(f"/api/v1/exams/{exam.id}/submit", json={"answers": [{"question_id": q1.id, "answer": "A"}]}, headers=cand_headers)

        # Autosave after submit -> 404 Not Found or already submitted
        resp = client.post(f"/api/v1/submissions/{sub_id}/autosave", json={"answers": [{"question_id": q1.id, "answer": "B"}]}, headers=cand_headers)
        assert resp.status_code == 404
    finally:
        fastapi_app.dependency_overrides.clear()


def test_active_attempts_listing(db_session: Session, admin_auth_headers: dict):
    cand_headers = {"Authorization": f"Bearer {create_access_token(data={'sub': 'testcandidate', 'role': 'candidate'})}"}
    fastapi_app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(fastapi_app)
    try:
        exam = Exam(title="Active List B1", language="EN", exam_type="VSTEP_B1", duration_minutes=120, is_active=True)
        db_session.add(exam)
        db_session.commit()
        db_session.refresh(exam)

        # Start attempt -> in progress
        client.post(f"/api/v1/exams/{exam.id}/start", headers=cand_headers)

        # Admin lists active attempts
        resp = client.get("/api/v1/submissions/active", headers=cand_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
    finally:
        fastapi_app.dependency_overrides.clear()


def test_exam_active_attempts_invigilation(db_session: Session, admin_auth_headers: dict):
    cand_headers = {"Authorization": f"Bearer {create_access_token(data={'sub': 'testcandidate', 'role': 'candidate'})}"}
    fastapi_app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(fastapi_app)
    try:
        exam = Exam(title="Invigilation B1", language="EN", exam_type="VSTEP_B1", duration_minutes=120, is_active=True)
        db_session.add(exam)
        db_session.commit()
        db_session.refresh(exam)

        q1 = Question(exam_id=exam.id, part=1, type="choice", content="Q1", reference_answer="A", status="approved")
        db_session.add(q1)
        db_session.commit()

        # Start attempt
        client.post(f"/api/v1/exams/{exam.id}/start", headers=cand_headers)

        # Check invigilation for this specific exam
        resp = client.get(f"/api/v1/exams/{exam.id}/active-attempts", headers=admin_auth_headers)
        assert resp.status_code == 200
        assert len(resp.json()) == 1

        # Submit -> drops off the active attempts list
        client.post(f"/api/v1/exams/{exam.id}/submit", json={"answers": [{"question_id": q1.id, "answer": "A"}]}, headers=cand_headers)
        
        # Clear expire all cache to read fresh DB status
        db_session.expire_all()
        resp = client.get(f"/api/v1/exams/{exam.id}/active-attempts", headers=admin_auth_headers)
        assert len(resp.json()) == 0
    finally:
        fastapi_app.dependency_overrides.clear()


def test_export_exam_results_csv(db_session: Session, admin_auth_headers: dict):
    cand_headers = {"Authorization": f"Bearer {create_access_token(data={'sub': 'testcandidate', 'role': 'candidate'})}"}
    fastapi_app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(fastapi_app)
    try:
        exam = Exam(title="CSV B1", language="EN", exam_type="VSTEP_B1", duration_minutes=120, is_active=True)
        db_session.add(exam)
        db_session.commit()
        db_session.refresh(exam)
        q1 = Question(exam_id=exam.id, part=1, type="choice", content="Q1", reference_answer="A", options={"A": "a", "B": "b"}, status="approved")
        db_session.add(q1)
        db_session.commit()

        # Submit
        client.post(f"/api/v1/exams/{exam.id}/submit", json={"answers": [{"question_id": q1.id, "answer": "A"}]}, headers=cand_headers)

        # Export CSV
        resp = client.get(f"/api/v1/exams/{exam.id}/results.csv", headers=admin_auth_headers)
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]
        body = resp.text
        assert ord(body[0]) == 0xFEFF
        assert "Họ tên" in body
        assert "testcandidate" in body
    finally:
        fastapi_app.dependency_overrides.clear()
