"""
SPEC-EXAM-001: Exam generation & retrieval HTTP API.

Exercises the /api/v1/exams endpoints end-to-end against the approved bank seeded
by the conftest db_session fixture, using FastAPI TestClient with the get_db
dependency overridden to the in-memory test session (StaticPool — see conftest).
"""
from sqlalchemy.orm import Session


def test_SPEC_EXAM_001_exam_generation_api(db_session: Session):
    from fastapi.testclient import TestClient
    from app.main import app as fastapi_app
    from app.core.database import get_db

    fastapi_app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(fastapi_app)

    try:
        # 1. Generate a full TOEIC exam from the approved bank.
        resp = client.post("/api/v1/exams/generate", json={"title": "Demo TOEIC", "seed": 42})
        assert resp.status_code == 200, resp.text
        summary = resp.json()
        exam_id = summary["id"]
        assert summary["title"] == "Demo TOEIC"
        assert summary["exam_type"] == "TOEIC"
        assert summary["question_count"] == 200

        # 2. List exams contains the generated one.
        resp = client.get("/api/v1/exams")
        assert resp.status_code == 200
        exams = resp.json()
        assert any(e["id"] == exam_id for e in exams)

        # 3. Retrieve full detail organized by part.
        resp = client.get(f"/api/v1/exams/{exam_id}")
        assert resp.status_code == 200
        detail = resp.json()
        assert detail["total_questions"] == 200
        parts = {p["part"]: p for p in detail["parts"]}
        assert set(parts.keys()) == {1, 2, 3, 4, 5, 6, 7}

        # Standalone parts expose standalone_questions; grouped parts expose groups.
        assert parts[1]["part_type"] == "standalone"
        assert parts[1]["question_count"] == 6
        assert len(parts[1]["standalone_questions"]) == 6

        assert parts[3]["part_type"] == "grouped"
        assert len(parts[3]["groups"]) == 13
        # Every grouped question carries its 4 options.
        sample_q = parts[3]["groups"][0]["questions"][0]
        assert sample_q["options"] is not None

        assert parts[7]["part_type"] == "subset_sum"
        assert parts[7]["question_count"] == 54

        # 4. Unknown exam id -> 404.
        resp = client.get("/api/v1/exams/999999")
        assert resp.status_code == 404

    finally:
        fastapi_app.dependency_overrides.clear()
