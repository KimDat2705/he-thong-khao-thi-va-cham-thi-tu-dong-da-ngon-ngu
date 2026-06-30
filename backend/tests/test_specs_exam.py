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
            exam_type="VSTEP_B1",
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


def test_SPEC_GEN_008_exam_generation(db_session: Session, admin_auth_headers: dict):
    from fastapi.testclient import TestClient
    from app.main import app as fastapi_app
    from app.core.database import get_db
    from app.models.question import Question
    from app.models.question_group import QuestionGroup

    fastapi_app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(fastapi_app)

    try:
        # Seed VSTEP B1 Question Bank
        # Part 1 (R1): 10 questions
        for i in range(12):
            db_session.add(Question(
                exam_id=None, group_id=None, part=1, type="choice",
                content=f"R1 Question {i}", reference_answer="A",
                difficulty="medium", status="approved", exam_type="VSTEP_B1", language="EN",
                options={"A": "Ans A", "B": "Ans B", "C": "Ans C", "D": "Ans D"}
            ))

        # Part 2 (R2): 5 questions
        for i in range(7):
            db_session.add(Question(
                exam_id=None, group_id=None, part=2, type="choice",
                content=f"R2 Question {i}", reference_answer="B",
                difficulty="easy", status="approved", exam_type="VSTEP_B1", language="EN",
                options={"A": "Ans A", "B": "Ans B", "C": "Ans C"}
            ))

        # Part 3 (R3): 1 group of 5 questions
        g3 = QuestionGroup(
            exam_id=None, part=3, topic="Travel", difficulty="medium", status="approved"
        )
        db_session.add(g3)
        db_session.commit()
        db_session.refresh(g3)
        for i in range(5):
            db_session.add(Question(
                exam_id=None, group_id=g3.id, part=3, type="choice",
                content=f"R3 Question {i}", reference_answer="C",
                difficulty="medium", status="approved", exam_type="VSTEP_B1", language="EN",
                options={"A": "A", "B": "B", "C": "C", "D": "D"}
            ))

        # Part 4 (R4): 1 group of 10 questions
        g4 = QuestionGroup(
            exam_id=None, part=4, topic="Meetings", difficulty="hard", status="approved"
        )
        db_session.add(g4)
        db_session.commit()
        db_session.refresh(g4)
        for i in range(10):
            db_session.add(Question(
                exam_id=None, group_id=g4.id, part=4, type="choice",
                content=f"R4 Question {i}", reference_answer="D",
                difficulty="hard", status="approved", exam_type="VSTEP_B1", language="EN",
                options={"A": "A", "B": "B", "C": "C", "D": "D"}
            ))

        # Part 5 (W1): 1 writing question
        db_session.add(Question(
            exam_id=None, group_id=None, part=5, type="writing",
            content="Rewrite the sentence: I haven't seen her for years.",
            difficulty="medium", status="approved", exam_type="VSTEP_B1", language="EN"
        ))

        # Part 6 (W2): 1 writing question
        db_session.add(Question(
            exam_id=None, group_id=None, part=6, type="writing",
            content="Write a letter to your friend.",
            difficulty="hard", status="approved", exam_type="VSTEP_B1", language="EN"
        ))

        # Part 7 (L1): 5 listening choice questions
        for i in range(6):
            db_session.add(Question(
                exam_id=None, group_id=None, part=7, type="choice",
                content=f"L1 Question {i}", reference_answer="A",
                audio_url=f"/static/audio_gen/l1_{i}.wav",
                image_url=f"/static/img/l1_{i}_A.png",
                difficulty="easy", status="approved", exam_type="VSTEP_B1", language="EN",
                options={"A": "A", "B": "B", "C": "C"}
            ))

        # Part 8 (L2): 1 group with 10 questions
        g8 = QuestionGroup(
            exam_id=None, part=8, topic="Logistics", difficulty="medium", status="approved",
            audio_url="/static/audio_gen/l2_group.wav"
        )
        db_session.add(g8)
        db_session.commit()
        db_session.refresh(g8)
        for i in range(10):
            db_session.add(Question(
                exam_id=None, group_id=g8.id, part=8, type="fill",
                content=f"L2 Blank {i+1}", reference_answer="correct",
                difficulty="medium", status="approved", exam_type="VSTEP_B1", language="EN"
            ))

        # Part 9 (S1): 1 speaking question
        db_session.add(Question(
            exam_id=None, group_id=None, part=9, type="speaking",
            content="Introduce yourself.",
            difficulty="easy", status="approved", exam_type="VSTEP_B1", language="EN"
        ))

        # Part 10 (S2): 1 speaking question
        db_session.add(Question(
            exam_id=None, group_id=None, part=10, type="speaking",
            content="Describe a picture.",
            difficulty="medium", status="approved", exam_type="VSTEP_B1", language="EN"
        ))

        # Part 11 (S3): 1 speaking question
        db_session.add(Question(
            exam_id=None, group_id=None, part=11, type="speaking",
            content="Give your opinion on a topic.",
            difficulty="hard", status="approved", exam_type="VSTEP_B1", language="EN"
        ))

        db_session.commit()

        # 2. Call the generator API to generate VSTEP B1 exam
        resp = client.post(
            "/api/v1/exams/generate",
            json={"title": "VSTEP B1 Test", "seed": 123, "exam_type": "VSTEP_B1"},
            headers=admin_auth_headers
        )
        assert resp.status_code == 200, resp.text
        summary = resp.json()
        assert summary["title"] == "VSTEP B1 Test"
        assert summary["exam_type"] == "VSTEP_B1"
        assert summary["question_count"] == 50, f"Expected 50 questions, got {summary['question_count']}"

        # 3. Retrieve detail and verify parts structure & cloning of assets
        exam_id = summary["id"]
        resp = client.get(f"/api/v1/exams/{exam_id}?include_answers=true", headers=admin_auth_headers)
        assert resp.status_code == 200
        detail = resp.json()
        assert detail["total_questions"] == 50

        # Check parts 1 to 11
        parts = {p["part"]: p for p in detail["parts"]}
        assert set(parts.keys()) == set(range(1, 12))

        # Part 1: standalone
        assert parts[1]["part_type"] == "standalone"
        assert parts[1]["question_count"] == 10

        # Part 2: standalone
        assert parts[2]["part_type"] == "standalone"
        assert parts[2]["question_count"] == 5

        # Part 3: grouped
        assert parts[3]["part_type"] == "grouped"
        assert parts[3]["question_count"] == 5
        assert len(parts[3]["groups"]) == 1

        # Part 4: grouped
        assert parts[4]["part_type"] == "grouped"
        assert parts[4]["question_count"] == 10
        assert len(parts[4]["groups"]) == 1

        # Part 5: W1
        assert parts[5]["part_type"] == "standalone"
        assert parts[5]["question_count"] == 1
        assert parts[5]["standalone_questions"][0]["type"] == "writing"

        # Part 6: W2
        assert parts[6]["part_type"] == "standalone"
        assert parts[6]["question_count"] == 1
        assert parts[6]["standalone_questions"][0]["type"] == "writing"

        # Part 7: L1 with audio & image assets
        assert parts[7]["part_type"] == "standalone"
        assert parts[7]["question_count"] == 5
        for q in parts[7]["standalone_questions"]:
            assert q["type"] == "choice"
            assert q["audio_url"] is not None
            assert q["image_url"] is not None

        # Part 8: L2 grouped fill
        assert parts[8]["part_type"] == "grouped"
        assert parts[8]["question_count"] == 10
        assert len(parts[8]["groups"]) == 1
        assert parts[8]["groups"][0]["audio_url"] is not None
        for q in parts[8]["groups"][0]["questions"]:
            assert q["type"] == "fill"

        # Parts 9, 10, 11: Speaking S1, S2, S3
        for p in (9, 10, 11):
            assert parts[p]["part_type"] == "standalone"
            assert parts[p]["question_count"] == 1
            assert parts[p]["standalone_questions"][0]["type"] == "speaking"

        # 4. Non-regression: Generate TOEIC exam and verify it selects only TOEIC questions (which has 200 questions seeded in conftest)
        resp_toeic = client.post(
            "/api/v1/exams/generate",
            json={"title": "TOEIC Non-Regression", "seed": 456, "exam_type": "TOEIC"},
            headers=admin_auth_headers
        )
        assert resp_toeic.status_code == 200, resp_toeic.text
        summary_toeic = resp_toeic.json()
        assert summary_toeic["exam_type"] == "TOEIC"
        assert summary_toeic["question_count"] == 200

        # Retrieve detail of TOEIC exam and verify no VSTEP questions are present
        resp_toeic_detail = client.get(f"/api/v1/exams/{summary_toeic['id']}", headers=admin_auth_headers)
        assert resp_toeic_detail.status_code == 200
        toeic_detail = resp_toeic_detail.json()
        assert toeic_detail["total_questions"] == 200
        for p in toeic_detail["parts"]:
            for q in p["standalone_questions"]:
                assert q["type"] not in ("writing", "speaking")
            for g in p["groups"]:
                for q in g["questions"]:
                    assert q["type"] not in ("writing", "speaking")

    finally:
        fastapi_app.dependency_overrides.clear()


