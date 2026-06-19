"""
SPEC-EXAM-001: Exam generation & retrieval HTTP API.

Exercises the /api/v1/exams endpoints end-to-end against the approved bank seeded
by the conftest db_session fixture, using FastAPI TestClient with the get_db
dependency overridden to the in-memory test session (StaticPool — see conftest).
"""
from sqlalchemy.orm import Session


def test_SPEC_EXAM_001_exam_generation_api(db_session: Session, admin_auth_headers: dict):
    from fastapi.testclient import TestClient
    from app.main import app as fastapi_app
    from app.core.database import get_db

    fastapi_app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(fastapi_app)

    try:
        # 1. Generate a full TOEIC exam from the approved bank.
        resp = client.post("/api/v1/exams/generate", json={"title": "Demo TOEIC", "seed": 42}, headers=admin_auth_headers)
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

        # 4. Default view hides answers (exam = questions only).
        def all_questions(d):
            for p in d["parts"]:
                yield from p["standalone_questions"]
                for g in p["groups"]:
                    yield from g["questions"]
        assert all(q["reference_answer"] is None for q in all_questions(detail)), \
            "Đề mặc định KHÔNG được lộ đáp án"

        # 5. Teacher view (include_answers=true) exposes the answer key.
        resp = client.get(f"/api/v1/exams/{exam_id}?include_answers=true", headers=admin_auth_headers)
        assert resp.status_code == 200
        assert any(q["reference_answer"] for q in all_questions(resp.json())), \
            "include_answers=true phải trả đáp án"

        # 6. Unknown exam id -> 404.
        resp = client.get("/api/v1/exams/999999")
        assert resp.status_code == 404

    finally:
        fastapi_app.dependency_overrides.clear()


def test_SPEC_EXAM_002_exam_lifecycle(db_session: Session, admin_auth_headers: dict):
    from fastapi.testclient import TestClient
    from app.main import app as fastapi_app
    from app.core.database import get_db
    from app.core.security import create_access_token
    from app.models.exam import Exam

    # 1. Reuse 'testcandidate' user defined in db_session fixture and sign token
    candidate_username = "testcandidate"
    candidate_token = create_access_token(data={"sub": candidate_username, "role": "candidate"})
    candidate_auth_headers = {"Authorization": f"Bearer {candidate_token}"}

    fastapi_app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(fastapi_app)

    try:
        # 2. Insert mock exam directly in DB session to avoid slow generation
        db_exam = Exam(
            title="Lifecycle TOEIC",
            language="EN",
            exam_type="TOEIC",
            duration_minutes=60,
            is_active=True
        )
        db_session.add(db_exam)
        db_session.commit()
        db_session.refresh(db_exam)
        exam_id = db_exam.id

        # 3. Candidate can view the active exam
        # List candidate view (no token)
        resp = client.get("/api/v1/exams")
        assert resp.status_code == 200
        exams = resp.json()
        assert any(e["id"] == exam_id for e in exams)

        # GET candidate view (no token)
        resp = client.get(f"/api/v1/exams/{exam_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == exam_id

        # 4. GATING: Candidates and unauthenticated requests are blocked
        # Candidate token -> 403 Forbidden
        resp = client.patch(f"/api/v1/exams/{exam_id}", json={"title": "Bad update"}, headers=candidate_auth_headers)
        assert resp.status_code == 403

        resp = client.post(f"/api/v1/exams/{exam_id}/retire", headers=candidate_auth_headers)
        assert resp.status_code == 403

        resp = client.post(f"/api/v1/exams/{exam_id}/release", headers=candidate_auth_headers)
        assert resp.status_code == 403

        # No token -> 401 Unauthorized
        resp = client.patch(f"/api/v1/exams/{exam_id}", json={"title": "Unauth update"})
        assert resp.status_code == 401

        resp = client.post(f"/api/v1/exams/{exam_id}/retire")
        assert resp.status_code == 401

        resp = client.post(f"/api/v1/exams/{exam_id}/release")
        assert resp.status_code == 401

        # 5. Retire exam via Admin token
        resp = client.post(f"/api/v1/exams/{exam_id}/retire", headers=admin_auth_headers)
        assert resp.status_code == 200
        assert resp.json()["is_active"] is False

        # 6. Candidate view filters out the retired exam
        # List candidate view (no token)
        resp = client.get("/api/v1/exams")
        assert resp.status_code == 200
        exams = resp.json()
        assert not any(e["id"] == exam_id for e in exams)

        # GET candidate view (no token) -> 404
        resp = client.get(f"/api/v1/exams/{exam_id}")
        assert resp.status_code == 404

        # GET candidate view with token -> 404
        resp = client.get(f"/api/v1/exams/{exam_id}", headers=candidate_auth_headers)
        assert resp.status_code == 404

        # GET candidate view with retired + include_answers=true -> 404 (early exit before permissions check)
        resp = client.get(f"/api/v1/exams/{exam_id}?include_answers=true", headers=candidate_auth_headers)
        assert resp.status_code == 404

        resp = client.get(f"/api/v1/exams/{exam_id}?include_answers=true")
        assert resp.status_code == 404

        # 7. Admin can still view the retired exam
        # List admin view
        resp = client.get("/api/v1/exams", headers=admin_auth_headers)
        assert resp.status_code == 200
        exams = resp.json()
        assert any(e["id"] == exam_id for e in exams)

        # GET admin view
        resp = client.get(f"/api/v1/exams/{exam_id}", headers=admin_auth_headers)
        assert resp.status_code == 200
        assert resp.json()["is_active"] is False

        # 8. Update metadata via Admin token
        resp = client.patch(f"/api/v1/exams/{exam_id}", json={"title": "Updated Title", "duration_minutes": 80}, headers=admin_auth_headers)
        assert resp.status_code == 200
        updated = resp.json()
        assert updated["title"] == "Updated Title"
        assert updated["duration_minutes"] == 80
        assert updated["is_active"] is False

        # Update non-existent exam -> 404
        resp = client.patch("/api/v1/exams/99999", json={"title": "No exam"}, headers=admin_auth_headers)
        assert resp.status_code == 404

        # 9. Release exam via Admin token
        resp = client.post(f"/api/v1/exams/{exam_id}/release", headers=admin_auth_headers)
        assert resp.status_code == 200
        assert resp.json()["is_active"] is True

        # 10. Candidate can view the released exam again
        # List candidate view (no token)
        resp = client.get("/api/v1/exams")
        assert resp.status_code == 200
        exams = resp.json()
        assert any(e["id"] == exam_id and e["title"] == "Updated Title" for e in exams)

        # GET candidate view (no token)
        resp = client.get(f"/api/v1/exams/{exam_id}")
        assert resp.status_code == 200
        assert resp.json()["title"] == "Updated Title"

    finally:
        fastapi_app.dependency_overrides.clear()

