"""
SPEC-STATS-001: Phân tích kết quả thi và thống kê chi tiết từng câu hỏi.
"""

import pytest
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from app.main import app as fastapi_app
from app.core.database import get_db
from app.core.security import create_access_token, hash_password
from app.models.exam import Exam
from app.models.question import Question
from app.models.user import User

def test_SPEC_STATS_001_exam_analytics(db_session: Session, monkeypatch):
    """
    SPEC-STATS-001: Phân tích kết quả thi và thống kê chi tiết từng câu.
    Test avg_score đi qua worker thật bằng Celery eager + AI mock.
    """
    from sqlalchemy.orm import sessionmaker
    from app.core.celery import celery_app
    import app.workers.tasks as tasks_module

    # 1. Set up eager Celery and AI mock
    test_engine = db_session.get_bind()
    WorkerSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    monkeypatch.setattr(tasks_module, "SessionLocal", WorkerSession)
    monkeypatch.setattr(tasks_module.ai_grading_service, "model", None)
    monkeypatch.setattr(celery_app.conf, "task_always_eager", True)
    monkeypatch.setattr(celery_app.conf, "task_eager_propagates", True)

    # 2. Seed Users
    # We create a teacher, and candidates. Note that testcandidate already exists via conftest.
    teacher = User(
        username="teacher_stats",
        hashed_password=hash_password("password"),
        full_name="Teacher Stats",
        role="teacher",
        is_active=True
    )
    candidate2 = User(
        username="candidate_stats2",
        hashed_password=hash_password("password"),
        full_name="Candidate 2",
        role="candidate",
        is_active=True
    )
    candidate3 = User(
        username="candidate_stats3",
        hashed_password=hash_password("password"),
        full_name="Candidate 3",
        role="candidate",
        is_active=True
    )
    db_session.add_all([teacher, candidate2, candidate3])
    db_session.commit()
    for u in (teacher, candidate2, candidate3):
        db_session.refresh(u)

    # Tokens and headers
    teacher_token = create_access_token(data={"sub": teacher.username, "role": "teacher"})
    teacher_headers = {"Authorization": f"Bearer {teacher_token}"}
    
    candidate1_token = create_access_token(data={"sub": "testcandidate", "role": "candidate"})
    candidate1_headers = {"Authorization": f"Bearer {candidate1_token}"}
    
    candidate2_token = create_access_token(data={"sub": candidate2.username, "role": "candidate"})
    candidate2_headers = {"Authorization": f"Bearer {candidate2_token}"}
    
    candidate3_token = create_access_token(data={"sub": candidate3.username, "role": "candidate"})
    candidate3_headers = {"Authorization": f"Bearer {candidate3_token}"}

    # 3. Seed Exam
    exam = Exam(
        title="VSTEP Statistics Exam",
        language="EN",
        exam_type="VSTEP_B1",
        duration_minutes=90,
        is_active=True
    )
    db_session.add(exam)
    db_session.commit()
    db_session.refresh(exam)

    # Seed 2 Choice, 1 Writing, 1 Speaking questions
    q1 = Question(
        exam_id=exam.id, part=1, type="choice", content="Choice Q1",
        reference_answer="A", options={"A": "opt A", "B": "opt B", "C": "opt C", "D": "opt D"},
        status="approved"
    )
    q2 = Question(
        exam_id=exam.id, part=1, type="choice", content="Choice Q2",
        reference_answer="B", options={"A": "opt A", "B": "opt B", "C": "opt C", "D": "opt D"},
        status="approved"
    )
    qw = Question(
        exam_id=exam.id, part=5, type="writing", content="Essay on Environment",
        status="approved"
    )
    qs = Question(
        exam_id=exam.id, part=9, type="speaking", content="Describe your favorite city",
        status="approved"
    )
    db_session.add_all([q1, q2, qw, qs])
    db_session.commit()
    for q in (q1, q2, qw, qs):
        db_session.refresh(q)

    # 4. Submit answers for 3 candidates
    fastapi_app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(fastapi_app)

    try:
        # Candidate 1: Q1="A" (correct), Q2="B" (correct), Q3="essay content 1", Q4="" with audio_url
        resp1 = client.post(
            f"/api/v1/exams/{exam.id}/submit",
            json={
                "answers": [
                    {"question_id": q1.id, "answer": "A"},
                    {"question_id": q2.id, "answer": "B"},
                    {"question_id": qw.id, "answer": "This is candidate 1 essay content about environment."},
                    {"question_id": qs.id, "answer": "", "audio_url": "/static/uploads/x.webm"}
                ]
            },
            headers=candidate1_headers
        )
        assert resp1.status_code == 200, resp1.text

        # Candidate 2: Q1="A" (correct), Q2="A" (incorrect), Q3="essay content 2", Q4="" with audio_url
        resp2 = client.post(
            f"/api/v1/exams/{exam.id}/submit",
            json={
                "answers": [
                    {"question_id": q1.id, "answer": "A"},
                    {"question_id": q2.id, "answer": "A"},
                    {"question_id": qw.id, "answer": "This is candidate 2 essay content about environment."},
                    {"question_id": qs.id, "answer": "", "audio_url": "/static/uploads/y.webm"}
                ]
            },
            headers=candidate2_headers
        )
        assert resp2.status_code == 200, resp2.text

        # Candidate 3: Q1="" (empty), Q2="" (empty), Q3="essay content 3", Q4="" (no audio_url)
        resp3 = client.post(
            f"/api/v1/exams/{exam.id}/submit",
            json={
                "answers": [
                    {"question_id": q1.id, "answer": ""},
                    {"question_id": q2.id, "answer": ""},
                    {"question_id": qw.id, "answer": "This is candidate 3 essay content about environment."},
                    {"question_id": qs.id, "answer": ""} # no audio_url
                ]
            },
            headers=candidate3_headers
        )
        assert resp3.status_code == 200, resp3.text

        # Verify Celery worker eager finished and populated DB
        db_session.expire_all()

        # Now test the stats endpoint
        resp_stats = client.get(
            f"/api/v1/exams/{exam.id}/analytics",
            headers=teacher_headers
        )
        assert resp_stats.status_code == 200, resp_stats.text
        data = resp_stats.json()

        assert data["submission_count"] == 3
        # score_summary: mean = (15.0 + 14.0 + 8.0) / 3 = 12.33333, min = 8.0, max = 15.0
        assert data["score_summary"]["mean"] == pytest.approx(12.33333, abs=1e-2)
        assert data["score_summary"]["min"] == pytest.approx(8.0)
        assert data["score_summary"]["max"] == pytest.approx(15.0)

        items = {item["question_id"]: item for item in data["items"]}
        
        # Verify Q1 (choice, correct A)
        # Candidate 1="A" (correct), Candidate 2="A" (correct), Candidate 3="" (empty, skipped)
        # answered = 2, correct = 2, rate = 1.0, option_dist = {"A": 2, "B": 0, "C": 0, "D": 0}
        item1 = items[q1.id]
        assert item1["answered_count"] == 2
        assert item1["correct_count"] == 2
        assert item1["correct_rate"] == pytest.approx(1.0)
        assert item1["option_distribution"]["A"] == 2
        assert item1["option_distribution"]["B"] == 0
        assert item1["avg_score"] is None

        # Verify Q2 (choice, correct B)
        # Candidate 1="B" (correct), Candidate 2="A" (incorrect), Candidate 3="" (empty, skipped)
        # answered = 2, correct = 1, rate = 0.5, option_dist = {"A": 1, "B": 1, "C": 0, "D": 0}
        item2 = items[q2.id]
        assert item2["answered_count"] == 2
        assert item2["correct_count"] == 1
        assert item2["correct_rate"] == pytest.approx(0.5)
        assert item2["option_distribution"]["A"] == 1
        assert item2["option_distribution"]["B"] == 1
        assert item2["avg_score"] is None

        # Verify Qw (writing)
        # Three candidate essays, each should score 8.0.
        # correct_rate & option_distribution should be None, avg_score = 8.0
        item_w = items[qw.id]
        assert item_w["answered_count"] == 3
        assert item_w["correct_count"] == 0
        assert item_w["correct_rate"] is None
        assert item_w["option_distribution"] is None
        assert item_w["avg_score"] == pytest.approx(8.0)

        # Verify Qs (speaking)
        # Two audio clips (7.5, 7.5), one empty/missing audio (0.0).
        # correct_rate & option_distribution should be None, avg_score = (7.5+7.5+0.0)/3 = 5.0
        # answered_count is 0 because all candidates submitted empty text "" for speaking
        item_s = items[qs.id]
        assert item_s["answered_count"] == 0
        assert item_s["correct_count"] == 0
        assert item_s["correct_rate"] is None
        assert item_s["option_distribution"] is None
        assert item_s["avg_score"] == pytest.approx(5.0)

    finally:
        fastapi_app.dependency_overrides.clear()


def test_exam_analytics_gating(db_session: Session):
    """
    Test gating / permissions for GET /api/v1/exams/{exam_id}/analytics
    """
    # Create an exam
    exam = Exam(
        title="Gating Test Exam",
        language="EN",
        exam_type="VSTEP",
        duration_minutes=60,
        is_active=True
    )
    db_session.add(exam)
    db_session.commit()
    db_session.refresh(exam)

    # Seed users
    teacher = User(
        username="teacher_stats_gate",
        hashed_password=hash_password("password"),
        full_name="Teacher Gate",
        role="teacher",
        is_active=True
    )
    candidate = db_session.query(User).filter(User.username == "testcandidate").first()
    db_session.add(teacher)
    db_session.commit()
    db_session.refresh(teacher)

    teacher_token = create_access_token(data={"sub": teacher.username, "role": "teacher"})
    candidate_token = create_access_token(data={"sub": candidate.username, "role": "candidate"})

    fastapi_app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(fastapi_app)

    try:
        # Teacher/admin should be allowed (returns 200)
        resp_teacher = client.get(
            f"/api/v1/exams/{exam.id}/analytics",
            headers={"Authorization": f"Bearer {teacher_token}"}
        )
        assert resp_teacher.status_code == 200

        # Candidate should be Forbidden (403)
        resp_candidate = client.get(
            f"/api/v1/exams/{exam.id}/analytics",
            headers={"Authorization": f"Bearer {candidate_token}"}
        )
        assert resp_candidate.status_code == 403

        # Unauthenticated should be Unauthorized (401)
        resp_no_auth = client.get(f"/api/v1/exams/{exam.id}/analytics")
        assert resp_no_auth.status_code == 401

        # Non-existent exam should return 404 for teacher
        resp_not_found = client.get(
            "/api/v1/exams/99999/analytics",
            headers={"Authorization": f"Bearer {teacher_token}"}
        )
        assert resp_not_found.status_code == 404
        assert "Exam not found" in resp_not_found.json()["detail"]

    finally:
        fastapi_app.dependency_overrides.clear()
