"""SPEC-FACTORY-016 — Nhà máy sinh câu (boss_factory) chạy trên WEB → lưu ngân hàng.

Nối nhà máy (sinh biến thể bám seed thật + cổng kiểm đáp án AI) vào ngân hàng câu hỏi DB:
câu sinh vào dạng nháp (draft) cho giáo viên soát/duyệt tại /admin/bank, cờ cổng kiểm đáp án
(NGHI/PASS) nhét vào explanation. API async admin/teacher. Phạm vi: ĐỌC R1-R4.

Test offline tất định: mock (generator=None) cho luồng sinh+lưu; _StubGen cho cổng kiểm đáp án.
"""
import json

import pytest

from app.models.import_batch import ImportBatch
from app.models.question import Question
from app.models.question_group import QuestionGroup
from app.services import boss_factory, factory_service, factory_to_bank


class _StubChecker:
    """Generator giả cho cổng kiểm đáp án: client truthy → nhánh real; _call_gemini trả payload cố định."""

    client = object()
    model_name = "stub"

    def __init__(self, payload: dict):
        self._payload = payload

    def _call_gemini(self, system_instruction: str, user_prompt: str,
                     max_output_tokens=None, thinking_budget=None) -> str:
        return json.dumps(self._payload, ensure_ascii=False)


def test_SPEC_FACTORY_016_factory_to_bank_web(db_session):
    """AC1+AC2: chạy nhà máy R1-R4 (mock) → câu vào ngân hàng dạng draft, đúng part/type, kèm cờ PASS."""
    # R1 (đơn part 1) + R2 (đơn part 2)
    for skill, part in (("reading_s1", 1), ("reading_s2_notice", 2)):
        res = factory_service.run_factory_to_bank(db_session, skill, limit=2, per_seed=1,
                                                  verify=True, generator=None)
        assert res["saved_questions"] >= 1, res
        db_session.expire_all()
        qs = db_session.query(Question).filter(
            Question.exam_id.is_(None), Question.part == part, Question.status == "draft"
        ).all()
        assert qs, f"{skill}: không có câu draft part {part}"
        q = qs[0]
        assert q.type == "choice"
        assert q.options and q.reference_answer in q.options
        assert q.exam_type == "VSTEP_B1"
        assert "Cổng kiểm đáp án AI" in (q.explanation or "")   # cờ kiểm đáp án nằm trong explanation

    # R3 (nhóm part 3) + R4 (nhóm part 4)
    res3 = factory_service.run_factory_to_bank(db_session, "reading_s3_comprehension",
                                               limit=1, per_seed=1, verify=True, generator=None)
    assert res3["saved_groups"] >= 1
    res4 = factory_service.run_factory_to_bank(db_session, "reading_s4_cloze",
                                               limit=1, per_seed=1, verify=True, generator=None)
    assert res4["saved_groups"] >= 1

    db_session.expire_all()
    g3 = db_session.query(QuestionGroup).filter(
        QuestionGroup.exam_id.is_(None), QuestionGroup.part == 3, QuestionGroup.status == "draft"
    ).first()
    assert g3 and g3.passage_text and len(g3.questions) >= 1
    assert all(c.type == "choice" for c in g3.questions)

    g4 = db_session.query(QuestionGroup).filter(
        QuestionGroup.exam_id.is_(None), QuestionGroup.part == 4, QuestionGroup.status == "draft"
    ).first()
    assert g4 and g4.questions
    fill = g4.questions[0]
    assert fill.type == "fill" and fill.reference_answer  # điền từ, có đáp án


def test_factory_answer_gate_flags_suspect_into_bank_rows():
    """AC2+AC3: cấy đáp án SAI (checker chọn phương án ngoài options) → item NGHI → explanation câu chứa 'NGHI'."""
    bank = [{
        "ma_de": "EB1.9001",
        "s1": {
            "1": {"stem": "She ...... to school every day.",
                  "options": {"A": "go", "B": "goes", "C": "going", "D": "went"}, "answer": "B"},
            "2": {"stem": "They ...... football on Sundays.",
                  "options": {"A": "plays", "B": "playing", "C": "play", "D": "played"}, "answer": "C"},
        },
    }]
    seeds = boss_factory.load_r1_seeds(bank)
    items = boss_factory.build_r1_variants(seeds, per_seed=1, generator=None)   # mock → item sạch
    assert items and all(it["qc_ok"] for it in items)

    # Checker "ảo giác" chọn 'Z' (ngoài A-D) → cổng gắn SUSPECT cho MỌI item, tất định.
    stub = _StubChecker({"derived_answer": "Z", "confidence": 0.4})
    boss_factory.verify_bundle_answers(items, "reading_s1", stub)
    assert all(it.get("answer_verify_flag") == "SUSPECT" for it in items)

    rows = factory_to_bank.bundle_items_to_rows("reading_s1", items)
    assert rows and all("NGHI" in (r["explanation"] or "") for r in rows)


def test_SPEC_FACTORY_016_api_gating_and_inline_job(db_session, admin_auth_headers, monkeypatch):
    """AC4: API phân quyền (401/403), chặn skill lạ (400) + job lạ (404); job chạy xong → câu vào ngân hàng."""
    from fastapi.testclient import TestClient
    from sqlalchemy.orm import sessionmaker

    from app.main import app as fastapi_app
    from app.core.database import get_db
    from app.core.security import create_access_token
    from app.core.config import settings
    import app.services.enrich_jobs as enrich_jobs

    # Job runner mở session riêng → trỏ về engine test; chạy inline + ép mock (không gọi mạng).
    test_engine = db_session.get_bind()
    WorkerSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    monkeypatch.setattr(enrich_jobs, "SessionLocal", WorkerSession)
    monkeypatch.setattr(enrich_jobs, "RUN_JOBS_INLINE", True)
    monkeypatch.setattr(settings, "GEMINI_API_KEY", None)

    fastapi_app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(fastapi_app)
    try:
        # Phân quyền: ẩn danh → 401; candidate → 403.
        assert client.post("/api/v1/factory/generate-async", json={"skill": "reading_s1"}).status_code == 401
        cand = create_access_token(data={"sub": "testcandidate", "role": "candidate"})
        assert client.post("/api/v1/factory/generate-async", json={"skill": "reading_s1"},
                           headers={"Authorization": f"Bearer {cand}"}).status_code == 403

        # skill lạ → 400.
        assert client.post("/api/v1/factory/generate-async", json={"skill": "bogus"},
                           headers=admin_auth_headers).status_code == 400

        # lô quá lớn (limit*per_seed > MAX_ASYNC_COUNT) → 400.
        assert client.post("/api/v1/factory/generate-async",
                           json={"skill": "reading_s1", "limit": 30, "per_seed": 3},
                           headers=admin_auth_headers).status_code == 400

        # admin, engine=mock → job hoàn tất, câu vào ngân hàng.
        resp = client.post("/api/v1/factory/generate-async",
                           json={"skill": "reading_s1", "limit": 2, "engine": "mock", "verify": True},
                           headers=admin_auth_headers)
        assert resp.status_code == 200, resp.text
        job_id = resp.json()["job_id"]

        st = client.get(f"/api/v1/factory/tasks/{job_id}", headers=admin_auth_headers)
        assert st.status_code == 200, st.text
        body = st.json()
        assert body["status"] == "completed", body
        assert body["saved_questions"] >= 1

        # job lạ → 404.
        assert client.get("/api/v1/factory/tasks/khong-co", headers=admin_auth_headers).status_code == 404

        # Câu draft part 1 thật sự có trong ngân hàng (không tautology).
        db_session.expire_all()
        n_draft = db_session.query(Question).filter(
            Question.exam_id.is_(None), Question.part == 1, Question.status == "draft"
        ).count()
        assert n_draft >= 1
    finally:
        fastapi_app.dependency_overrides.clear()


def test_factory_r4_no_child_hash_collision(db_session):
    """Regression (review #2): R4 per_seed=2 → 2 nhóm, KHÔNG nhóm nào bị dedup nuốt hết câu con.

    Trước khi vá: câu con dùng chung 'Chỗ trống (21)' → trùng content_hash giữa 2 đoạn → nhóm 2 rỗng
    (đo thật: nhóm1=10 câu, nhóm2=0). Sau khi vá (thêm mã đoạn): mỗi nhóm giữ đủ câu con.
    """
    res = factory_service.run_factory_to_bank(
        db_session, "reading_s4_cloze", limit=1, per_seed=2, verify=False, generator=None
    )
    assert res["saved_groups"] == 2, res
    db_session.expire_all()
    groups = db_session.query(QuestionGroup).filter(
        QuestionGroup.exam_id.is_(None), QuestionGroup.part == 4, QuestionGroup.status == "draft"
    ).all()
    assert len(groups) == 2
    counts = [len(g.questions) for g in groups]
    assert all(c >= 1 for c in counts), f"nhóm R4 bị mất câu con do trùng content_hash: {counts}"
    assert sum(counts) == res["saved_questions"]   # không câu con nào bị nuốt


def test_factory_r1_coerces_option_values_to_str():
    """Regression (review #1): giá trị phương án non-string (list/số) từ Gemini được ép str khi vào ngân hàng."""
    items = [{
        "s1_item": {"stem": "She ...... home.",
                    "options": {"A": ["go"], "B": 42, "C": "going", "D": "gone"}, "answer": "B"},
        "difficulty_en": "medium", "explanation": "x", "qc_ok": True,
    }]
    rows = factory_to_bank.bundle_items_to_rows("reading_s1", items)
    assert rows and all(isinstance(v, str) for v in rows[0]["options"].values())


def test_factory_batch_marked_failed_on_save_error(db_session, monkeypatch):
    """Regression (review #3): lưu lỗi giữa chừng → ImportBatch đánh 'failed' (không mồ côi 'imported')."""
    from app.services import parser as parser_mod

    def _boom(*a, **k):
        raise RuntimeError("save lỗi giả")

    monkeypatch.setattr(parser_mod, "save_parsed_items", _boom)
    with pytest.raises(RuntimeError):
        factory_service.run_factory_to_bank(
            db_session, "reading_s1", limit=1, per_seed=1, verify=False, generator=None
        )
    db_session.expire_all()
    batches = db_session.query(ImportBatch).filter(ImportBatch.source_file == "factory:reading_s1").all()
    assert batches and all(b.status == "failed" for b in batches)
