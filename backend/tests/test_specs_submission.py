from sqlalchemy.orm import Session
import pytest

def test_SPEC_SUBMIT_001_exam_grading_flow(db_session: Session, admin_auth_headers: dict):
    from fastapi.testclient import TestClient
    from app.main import app as fastapi_app
    from app.core.database import get_db
    from app.core.security import create_access_token, hash_password
    from app.models.exam import Exam
    from app.models.question import Question
    from app.models.user import User

    # 1. Access token for 'testcandidate'
    candidate_username = "testcandidate"
    candidate_token = create_access_token(data={"sub": candidate_username, "role": "candidate"})
    candidate_headers = {"Authorization": f"Bearer {candidate_token}"}

    # 2. Access token for another candidate
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
        # 3. Create mock TOEIC exam directly in DB session
        exam = Exam(
            title="Grading Test TOEIC",
            language="EN",
            exam_type="TOEIC",
            duration_minutes=120,
            is_active=True
        )
        db_session.add(exam)
        db_session.commit()
        db_session.refresh(exam)
        exam_id = exam.id

        # Insert 4 Listening questions (parts 1-4)
        questions = []
        for i in range(1, 5):
            q = Question(
                exam_id=exam_id, part=i, type="choice", content=f"LQ {i}",
                reference_answer="A" if i % 2 == 1 else "B",
                options={"A": "Opt A", "B": "Opt B", "C": "Opt C", "D": "Opt D"},
                status="approved"
            )
            db_session.add(q)
            questions.append(q)

        # Insert 4 Reading questions (parts 5-7)
        for i in range(5, 9):
            q = Question(
                exam_id=exam_id, part=7 if i > 6 else i, type="choice", content=f"RQ {i}",
                reference_answer="C" if i % 2 == 1 else "D",
                options={"A": "Opt A", "B": "Opt B", "C": "Opt C", "D": "Opt D"},
                status="approved"
            )
            db_session.add(q)
            questions.append(q)

        db_session.commit()
        for q in questions:
            db_session.refresh(q)

        q_listening = questions[:4]
        q_reading = questions[4:]

        # Test Case A: Submit 100% correct answers
        answers_all_correct = []
        for q in questions:
            answers_all_correct.append({"question_id": q.id, "answer": q.reference_answer})

        resp = client.post(f"/api/v1/exams/{exam_id}/submit", json={"answers": answers_all_correct}, headers=candidate_headers)
        assert resp.status_code == 200, resp.text
        res_data = resp.json()
        assert res_data["status"] == "completed"
        assert res_data["listening_score"] == 495
        assert res_data["reading_score"] == 495
        assert res_data["total_score"] == 990
        assert res_data["listening_correct"] == 4
        assert res_data["reading_correct"] == 4
        sub_id_all_correct = res_data["submission_id"]

        # Test Case B: Submit 50% correct answers
        answers_half_correct = [
            {"question_id": q_listening[0].id, "answer": "A"},
            {"question_id": q_listening[1].id, "answer": "A"},
            {"question_id": q_listening[2].id, "answer": "A"},
            {"question_id": q_listening[3].id, "answer": "A"},
            {"question_id": q_reading[0].id, "answer": "C"},
            {"question_id": q_reading[1].id, "answer": "C"},
            {"question_id": q_reading[2].id, "answer": "C"},
            {"question_id": q_reading[3].id, "answer": "C"}
        ]
        resp = client.post(f"/api/v1/exams/{exam_id}/submit", json={"answers": answers_half_correct}, headers=candidate_headers)
        assert resp.status_code == 200
        res_data = resp.json()
        assert res_data["status"] == "completed"
        assert res_data["listening_correct"] == 2
        assert res_data["reading_correct"] == 2
        assert res_data["listening_score"] == 245
        assert res_data["reading_score"] == 225
        assert res_data["total_score"] == 470


        # Test Case C: Submit 0% correct answers
        answers_all_wrong = []
        for q in questions:
            answers_all_wrong.append({"question_id": q.id, "answer": "X"})
        resp = client.post(f"/api/v1/exams/{exam_id}/submit", json={"answers": answers_all_wrong}, headers=candidate_headers)
        assert resp.status_code == 200
        res_data = resp.json()
        assert res_data["status"] == "completed"
        assert res_data["listening_correct"] == 0
        assert res_data["reading_correct"] == 0
        assert res_data["listening_score"] == 5
        assert res_data["reading_score"] == 5
        assert res_data["total_score"] == 10

        # Test Case D: GET submission details
        # 1. Owner can view details
        resp = client.get(f"/api/v1/submissions/{sub_id_all_correct}", headers=candidate_headers)
        assert resp.status_code == 200
        sub_detail = resp.json()
        assert sub_detail["user_id"] == db_session.query(User).filter(User.username == candidate_username).first().id
        assert len(sub_detail["answers"]) == 8
        assert sub_detail["total_score"] == 990

        # 2. Admin can view details
        resp = client.get(f"/api/v1/submissions/{sub_id_all_correct}", headers=admin_auth_headers)
        assert resp.status_code == 200

        # 3. GATING: Candidate 2 cannot view Candidate 1's details -> 403 Forbidden
        resp = client.get(f"/api/v1/submissions/{sub_id_all_correct}", headers=candidate2_headers)
        assert resp.status_code == 403

        # 4. GATING: Request without token -> 401 Unauthorized
        resp = client.get(f"/api/v1/submissions/{sub_id_all_correct}")
        assert resp.status_code == 401

        resp = client.post(f"/api/v1/exams/{exam_id}/submit", json={"answers": answers_all_correct})
        assert resp.status_code == 401

        # Test Case E: Retired exam -> 404 Not Found
        exam.is_active = False
        db_session.commit()
        resp = client.post(f"/api/v1/exams/{exam_id}/submit", json={"answers": answers_all_correct}, headers=candidate_headers)
        assert resp.status_code == 404

        # Non-existent exam -> 404 Not Found
        resp = client.post("/api/v1/exams/99999/submit", json={"answers": answers_all_correct}, headers=candidate_headers)
        assert resp.status_code == 404

        # Test Case F: Non-TOEIC exam -> 400 Bad Request
        non_toeic_exam = Exam(
            title="Non-TOEIC Exam",
            language="CN",
            exam_type="HSK",
            duration_minutes=60,
            is_active=True
        )
        db_session.add(non_toeic_exam)
        db_session.commit()
        db_session.refresh(non_toeic_exam)
        resp = client.post(f"/api/v1/exams/{non_toeic_exam.id}/submit", json={"answers": answers_all_correct}, headers=candidate_headers)
        assert resp.status_code == 400

    finally:
        fastapi_app.dependency_overrides.clear()


def test_upload_audio_endpoint(db_session: Session):
    """POST /submissions/upload-audio lưu file ghi âm và trả audio_url phục vụ phần Nói
    (Speaking). Yêu cầu đăng nhập (401 nếu thiếu token).
    """
    import os
    from fastapi.testclient import TestClient
    from app.main import app as fastapi_app
    from app.core.database import get_db
    from app.core.security import create_access_token

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

        # File thực sự được ghi
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "static", url.replace("/static/", "", 1))
        assert os.path.isfile(path)
        os.remove(path)  # dọn artifact

        # Thiếu token -> 401
        resp = client.post("/api/v1/submissions/upload-audio", files=files)
        assert resp.status_code == 401
    finally:
        fastapi_app.dependency_overrides.clear()


def test_SPEC_SUBMIT_003_teacher_grade_override(db_session: Session, monkeypatch):
    """SPEC-SUBMIT-003: giáo viên/admin điều chỉnh điểm AI tự luận + ghi nhận xét;
    tổng tính lại; candidate không được sửa (403), không token (401), không có (404).
    """
    from fastapi.testclient import TestClient
    from sqlalchemy.orm import sessionmaker

    from app.main import app as fastapi_app
    from app.core.database import get_db
    from app.core.security import create_access_token, hash_password
    from app.core.celery import celery_app
    from app.models.exam import Exam
    from app.models.question import Question
    from app.models.user import User
    import app.workers.tasks as tasks_module

    # Eager + mock AI so the essay gets an AI grade to override.
    test_engine = db_session.get_bind()
    WorkerSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    monkeypatch.setattr(tasks_module, "SessionLocal", WorkerSession)
    monkeypatch.setattr(tasks_module.ai_grading_service, "model", None)
    monkeypatch.setattr(celery_app.conf, "task_always_eager", True)
    monkeypatch.setattr(celery_app.conf, "task_eager_propagates", True)

    teacher = User(username="teacher_s3", hashed_password=hash_password("x"),
                   full_name="Teacher S3", role="teacher", is_active=True)
    db_session.add(teacher)
    db_session.commit()

    cand_h = {"Authorization": f"Bearer {create_access_token(data={'sub': 'testcandidate', 'role': 'candidate'})}"}
    teach_h = {"Authorization": f"Bearer {create_access_token(data={'sub': 'teacher_s3', 'role': 'teacher'})}"}

    fastapi_app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(fastapi_app)
    try:
        exam = Exam(title="VSTEP Override", language="EN", exam_type="VSTEP",
                    duration_minutes=60, is_active=True)
        db_session.add(exam)
        db_session.commit()
        db_session.refresh(exam)
        qw = Question(exam_id=exam.id, part=1, type="writing",
                      content="Write about your favourite book.", status="approved")
        db_session.add(qw)
        db_session.commit()
        db_session.refresh(qw)

        resp = client.post(f"/api/v1/exams/{exam.id}/submit",
                           json={"answers": [{"question_id": qw.id, "answer": "My favourite book is..."}]},
                           headers=cand_h)
        assert resp.status_code == 200
        sid = resp.json()["submission_id"]

        # Mock AI gave 8.0; teacher lowers to 6.5 and adds a note.
        resp = client.patch(f"/api/v1/submissions/{sid}/grade",
                            json={"score_writing": 6.5, "teacher_note": "Cần cải thiện ngữ pháp."},
                            headers=teach_h)
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["score_writing"] == 6.5
        assert data["total_score"] == 6.5  # mc 0 + writing 6.5 + speaking 0
        assert (data["feedback_writing"] or {}).get("teacher_note") == "Cần cải thiện ngữ pháp."

        # Gating: candidate -> 403
        resp = client.patch(f"/api/v1/submissions/{sid}/grade", json={"score_writing": 9.0}, headers=cand_h)
        assert resp.status_code == 403
        # No token -> 401
        resp = client.patch(f"/api/v1/submissions/{sid}/grade", json={"score_writing": 9.0})
        assert resp.status_code == 401
        # Non-existent -> 404
        resp = client.patch("/api/v1/submissions/99999/grade", json={"score_writing": 9.0}, headers=teach_h)
        assert resp.status_code == 404
    finally:
        fastapi_app.dependency_overrides.clear()


def test_SPEC_SUBMIT_002_submissions_listing(db_session: Session):
    from fastapi.testclient import TestClient
    from app.main import app as fastapi_app
    from app.core.database import get_db
    from app.core.security import create_access_token, hash_password
    from app.models.exam import Exam
    from app.models.question import Question
    from app.models.user import User
    from app.models.submission import Submission
    import datetime

    # 1. Create candidate and teacher users
    db_user1 = User(
        username="testcandidate_c4",
        hashed_password=hash_password("password"),
        full_name="Candidate One",
        role="candidate",
        is_active=True
    )
    db_user2 = User(
        username="testcandidate2_c4",
        hashed_password=hash_password("password"),
        full_name="Candidate Two",
        role="candidate",
        is_active=True
    )
    db_teacher = User(
        username="testteacher_c4",
        hashed_password=hash_password("password"),
        full_name="Teacher One",
        role="teacher",
        is_active=True
    )
    db_session.add(db_user1)
    db_session.add(db_user2)
    db_session.add(db_teacher)
    db_session.commit()

    db_session.refresh(db_user1)
    db_session.refresh(db_user2)
    db_session.refresh(db_teacher)

    # Access tokens and headers
    token1 = create_access_token(data={"sub": "testcandidate_c4", "role": "candidate"})
    token2 = create_access_token(data={"sub": "testcandidate2_c4", "role": "candidate"})
    token_teacher = create_access_token(data={"sub": "testteacher_c4", "role": "teacher"})

    headers1 = {"Authorization": f"Bearer {token1}"}
    headers2 = {"Authorization": f"Bearer {token2}"}
    headers_teacher = {"Authorization": f"Bearer {token_teacher}"}

    fastapi_app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(fastapi_app)

    try:
        # 2. Create mock TOEIC exam
        exam = Exam(
            title="C4 Test Exam",
            language="EN",
            exam_type="TOEIC",
            duration_minutes=120,
            is_active=True
        )
        db_session.add(exam)
        db_session.commit()
        db_session.refresh(exam)
        exam_id = exam.id

        # Add a question
        q = Question(
            exam_id=exam_id, part=1, type="choice", content="Q1",
            reference_answer="A",
            options={"A": "Opt A", "B": "Opt B", "C": "Opt C", "D": "Opt D"},
            status="approved"
        )
        db_session.add(q)
        db_session.commit()
        db_session.refresh(q)

        # 3. Submit answers to generate graded submissions
        resp = client.post(f"/api/v1/exams/{exam_id}/submit", json={"answers": [{"question_id": q.id, "answer": "A"}]}, headers=headers1)
        assert resp.status_code == 200
        sub_id_c1 = resp.json()["submission_id"]

        resp = client.post(f"/api/v1/exams/{exam_id}/submit", json={"answers": [{"question_id": q.id, "answer": "B"}]}, headers=headers2)
        assert resp.status_code == 200

        # 4. Create an ungraded submission (submission with no grade object)
        sub_no_grade = Submission(
            exam_id=exam_id,
            user_id=db_user1.id,
            status="pending",
            started_at=datetime.datetime.utcnow() - datetime.timedelta(minutes=10),
            submitted_at=datetime.datetime.utcnow() - datetime.timedelta(minutes=10)
        )
        db_session.add(sub_no_grade)
        db_session.commit()
        db_session.refresh(sub_no_grade)

        # 5. Verify GET /api/v1/exams/{exam_id}/submissions gating & response
        # Candidate 1 -> 403
        resp = client.get(f"/api/v1/exams/{exam_id}/submissions", headers=headers1)
        assert resp.status_code == 403

        # Guest -> 401
        resp = client.get(f"/api/v1/exams/{exam_id}/submissions")
        assert resp.status_code == 401

        # Non-existent exam -> 404
        resp = client.get("/api/v1/exams/99999/submissions", headers=headers_teacher)
        assert resp.status_code == 404

        # Teacher -> 200, return all 3 submissions
        resp = client.get(f"/api/v1/exams/{exam_id}/submissions", headers=headers_teacher)
        assert resp.status_code == 200
        data_all = resp.json()
        assert len(data_all) == 3
        # Check mapping of fields
        for item in data_all:
            assert "submission_id" in item
            assert "user_id" in item
            assert "username" in item
            assert "full_name" in item
            assert "status" in item
            assert "submitted_at" in item
            assert "exam_type" in item
            assert "writing_score" in item
            if item["submission_id"] == sub_no_grade.id:
                # Ungraded submission has null scores
                assert item["total_score"] is None
                assert item["listening_score"] is None
                assert item["reading_score"] is None
                assert item["username"] == "testcandidate_c4"
                assert item["full_name"] == "Candidate One"
            elif item["submission_id"] == sub_id_c1:
                # Graded submission has actual scores
                assert item["total_score"] is not None
                assert item["listening_score"] is not None
                assert item["reading_score"] is not None

        # 6. Verify GET /api/v1/submissions/me gating & response
        # Guest -> 401
        resp = client.get("/api/v1/submissions/me")
        assert resp.status_code == 401

        # Candidate 1 -> 200, returns their own 2 submissions ordered desc
        resp = client.get("/api/v1/submissions/me", headers=headers1)
        assert resp.status_code == 200
        my_data = resp.json()
        assert len(my_data) == 2
        # Verify ordering (newest first)
        dt_first = datetime.datetime.fromisoformat(my_data[0]["submitted_at"].replace("Z", "+00:00"))
        dt_second = datetime.datetime.fromisoformat(my_data[1]["submitted_at"].replace("Z", "+00:00"))
        assert dt_first >= dt_second
        assert my_data[0]["exam_title"] == "C4 Test Exam"

        # Check null grades in personal history
        ungraded_my_item = next(item for item in my_data if item["submission_id"] == sub_no_grade.id)
        assert ungraded_my_item["total_score"] is None
        assert ungraded_my_item["listening_score"] is None
        assert ungraded_my_item["reading_score"] is None

    finally:
        fastapi_app.dependency_overrides.clear()


def test_exam_session_start_autosave_resume_submit(db_session: Session):
    """Phiên thi bền server-side (C15 — SPEC-SCALE-003 AC /start + /autosave):
    /start tạo attempt in_progress + trả remaining_seconds tính ở SERVER (không reset
    được phía client) + answers rỗng; /start lại (reload) trả ĐÚNG attempt cũ; /autosave
    lưu đáp án -> /start sau đó khôi phục được; attempt chưa nộp KHÔNG hiện trong
    /submissions/me; /submit TÁI DÙNG attempt (cùng submission_id) + hoàn tất, KHÔNG
    tạo bản ghi trùng.
    """
    from fastapi.testclient import TestClient
    from app.main import app as fastapi_app
    from app.core.database import get_db
    from app.core.security import create_access_token
    from app.models.exam import Exam
    from app.models.question import Question
    from app.models.user import User
    from app.models.submission import Submission

    cand_headers = {
        "Authorization": f"Bearer {create_access_token(data={'sub': 'testcandidate', 'role': 'candidate'})}"
    }
    fastapi_app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(fastapi_app)
    try:
        exam = Exam(title="Session TOEIC", language="EN", exam_type="TOEIC",
                    duration_minutes=120, is_active=True)
        db_session.add(exam)
        db_session.commit()
        db_session.refresh(exam)
        q1 = Question(exam_id=exam.id, part=1, type="choice", content="Q1",
                      reference_answer="A", options={"A": "a", "B": "b"}, status="approved")
        q2 = Question(exam_id=exam.id, part=2, type="choice", content="Q2",
                      reference_answer="B", options={"A": "a", "B": "b"}, status="approved")
        db_session.add_all([q1, q2])
        db_session.commit()
        for q in (q1, q2):
            db_session.refresh(q)

        # START -> new in_progress attempt, full time, no saved answers.
        r = client.post(f"/api/v1/exams/{exam.id}/start", headers=cand_headers)
        assert r.status_code == 200, r.text
        s = r.json()
        sub_id = s["submission_id"]
        assert 120 * 60 - 60 < s["remaining_seconds"] <= 120 * 60
        assert s["answers"] == []

        # START again (reload) -> SAME attempt (idempotent resume).
        again = client.post(f"/api/v1/exams/{exam.id}/start", headers=cand_headers)
        assert again.json()["submission_id"] == sub_id

        # AUTOSAVE q1=A.
        ra = client.post(
            f"/api/v1/submissions/{sub_id}/autosave",
            json={"answers": [{"question_id": q1.id, "answer": "A"}]},
            headers=cand_headers,
        )
        assert ra.status_code == 200, ra.text
        assert ra.json()["saved"] == 1

        # RESUME via /start restores the saved answer.
        resumed = client.post(f"/api/v1/exams/{exam.id}/start", headers=cand_headers).json()
        saved = {a["question_id"]: a["candidate_text"] for a in resumed["answers"]}
        assert saved.get(q1.id) == "A"

        # in_progress attempt is hidden from /submissions/me until submitted.
        me = client.get("/api/v1/submissions/me", headers=cand_headers).json()
        assert all(m["submission_id"] != sub_id for m in me)

        # SUBMIT reuses the SAME attempt and finalizes.
        rs = client.post(
            f"/api/v1/exams/{exam.id}/submit",
            json={"answers": [
                {"question_id": q1.id, "answer": "A"},
                {"question_id": q2.id, "answer": "B"},
            ]},
            headers=cand_headers,
        )
        assert rs.status_code == 200, rs.text
        assert rs.json()["submission_id"] == sub_id, "submit phải TÁI DÙNG attempt từ /start"
        assert rs.json()["status"] == "completed"

        # Now visible in /submissions/me.
        me2 = client.get("/api/v1/submissions/me", headers=cand_headers).json()
        assert any(m["submission_id"] == sub_id for m in me2)

        # Exactly ONE submission row for this candidate+exam (no duplicate).
        cand = db_session.query(User).filter(User.username == "testcandidate").first()
        rows = db_session.query(Submission).filter(
            Submission.exam_id == exam.id, Submission.user_id == cand.id
        ).all()
        assert len(rows) == 1, "start + submit chỉ được tạo 1 bản ghi submission"
    finally:
        fastapi_app.dependency_overrides.clear()


def test_autosave_gating(db_session: Session):
    """Autosave bị chặn: người KHÁC (không phải chủ attempt) -> 404; và sau khi attempt
    ĐÃ NỘP -> 404 (không cho ghi đè bài đã nộp)."""
    from fastapi.testclient import TestClient
    from app.main import app as fastapi_app
    from app.core.database import get_db
    from app.core.security import create_access_token, hash_password
    from app.models.exam import Exam
    from app.models.question import Question
    from app.models.user import User

    fastapi_app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(fastapi_app)
    try:
        other = User(username="other_cand", hashed_password=hash_password("x"),
                     full_name="Other", role="candidate", is_active=True)
        db_session.add(other)
        db_session.commit()

        exam = Exam(title="Gate TOEIC", language="EN", exam_type="TOEIC",
                    duration_minutes=60, is_active=True)
        db_session.add(exam)
        db_session.commit()
        db_session.refresh(exam)
        q1 = Question(exam_id=exam.id, part=1, type="choice", content="Q1",
                      reference_answer="A", options={"A": "a", "B": "b"}, status="approved")
        db_session.add(q1)
        db_session.commit()
        db_session.refresh(q1)

        cand_headers = {
            "Authorization": f"Bearer {create_access_token(data={'sub': 'testcandidate', 'role': 'candidate'})}"
        }
        other_headers = {
            "Authorization": f"Bearer {create_access_token(data={'sub': 'other_cand', 'role': 'candidate'})}"
        }

        sub_id = client.post(f"/api/v1/exams/{exam.id}/start", headers=cand_headers).json()["submission_id"]

        # Not the owner -> 404.
        r = client.post(
            f"/api/v1/submissions/{sub_id}/autosave",
            json={"answers": [{"question_id": q1.id, "answer": "A"}]},
            headers=other_headers,
        )
        assert r.status_code == 404

        # Owner autosave OK.
        assert client.post(
            f"/api/v1/submissions/{sub_id}/autosave",
            json={"answers": [{"question_id": q1.id, "answer": "A"}]},
            headers=cand_headers,
        ).status_code == 200

        # Finalize via submit.
        client.post(
            f"/api/v1/exams/{exam.id}/submit",
            json={"answers": [{"question_id": q1.id, "answer": "A"}]},
            headers=cand_headers,
        )

        # Already submitted -> autosave 404.
        r2 = client.post(
            f"/api/v1/submissions/{sub_id}/autosave",
            json={"answers": [{"question_id": q1.id, "answer": "A"}]},
            headers=cand_headers,
        )
        assert r2.status_code == 404
    finally:
        fastapi_app.dependency_overrides.clear()


def test_active_attempts_listing(db_session: Session):
    """GET /submissions/active (C16): liệt kê attempt ĐANG LÀM DỞ của thí sinh để
    resume từ danh sách đề; sau khi NỘP thì không còn; no-token -> 401."""
    from fastapi.testclient import TestClient
    from app.main import app as fastapi_app
    from app.core.database import get_db
    from app.core.security import create_access_token
    from app.models.exam import Exam
    from app.models.question import Question

    cand_headers = {
        "Authorization": f"Bearer {create_access_token(data={'sub': 'testcandidate', 'role': 'candidate'})}"
    }
    fastapi_app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(fastapi_app)
    try:
        exam = Exam(title="Active TOEIC", language="EN", exam_type="TOEIC",
                    duration_minutes=90, is_active=True)
        db_session.add(exam)
        db_session.commit()
        db_session.refresh(exam)
        q1 = Question(exam_id=exam.id, part=1, type="choice", content="Q1",
                      reference_answer="A", options={"A": "a", "B": "b"}, status="approved")
        db_session.add(q1)
        db_session.commit()
        db_session.refresh(q1)

        # No active attempts yet.
        assert client.get("/api/v1/submissions/active", headers=cand_headers).json() == []

        # Guest -> 401.
        assert client.get("/api/v1/submissions/active").status_code == 401

        # Start -> appears in active with the exam + a positive remaining time.
        client.post(f"/api/v1/exams/{exam.id}/start", headers=cand_headers)
        active = client.get("/api/v1/submissions/active", headers=cand_headers).json()
        assert len(active) == 1
        assert active[0]["exam_id"] == exam.id
        assert active[0]["exam_title"] == "Active TOEIC"
        assert active[0]["remaining_seconds"] > 0

        # Submit -> no longer in-progress -> active is empty again.
        client.post(
            f"/api/v1/exams/{exam.id}/submit",
            json={"answers": [{"question_id": q1.id, "answer": "A"}]},
            headers=cand_headers,
        )
        assert client.get("/api/v1/submissions/active", headers=cand_headers).json() == []
    finally:
        fastapi_app.dependency_overrides.clear()

