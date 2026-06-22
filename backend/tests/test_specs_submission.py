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
