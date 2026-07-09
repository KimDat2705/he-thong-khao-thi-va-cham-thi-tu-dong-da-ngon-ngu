"""SPEC-FACTORY-016/017 — Nhà máy sinh câu (boss_factory) chạy trên WEB → lưu ngân hàng.

Nối nhà máy (sinh biến thể bám seed thật + cổng kiểm đáp án AI) vào ngân hàng câu hỏi DB:
câu sinh vào dạng nháp (draft) cho giáo viên soát/duyệt tại /admin/bank, cờ cổng kiểm đáp án
(NGHI/PASS) nhét vào explanation. API async admin/teacher.
Phạm vi: ĐỌC R1-R4 (016) + VIẾT W1/W2 (017: W1 khối 5 câu/đề 2601 + cổng kiểm viết-lại-độc-lập;
W2 tự luận → converter chèn note GV soát tay).

Test offline tất định: mock (generator=None) cho luồng sinh+lưu; _StubChecker cho cổng kiểm đáp án.
"""
import json
import os

import pytest

from app.models.import_batch import ImportBatch
from app.models.question import Question
from app.models.question_group import QuestionGroup
from app.services import bank_admin, boss_factory, factory_service, factory_to_bank


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


def test_SPEC_FACTORY_017_w1_w2_to_bank(db_session):
    """AC1+AC2: W1 mock → khối 5 câu/1 Question part 5 type writing (format đề 2601), khối lẻ có
    CẢNH BÁO; W2 mock → Question part 6 tự luận (reference_answer=None) + note GV soát tay."""
    # W1: fixture 3 seed × per_seed 2 = 6 item qc_ok → 1 khối đủ 5 câu + 1 khối lẻ 1 câu.
    res = factory_service.run_factory_to_bank(db_session, "writing_w1_rewrite", limit=3, per_seed=2,
                                              verify=True, generator=None)
    assert res["saved_questions"] == 2, res
    db_session.expire_all()
    blocks = db_session.query(Question).filter(
        Question.exam_id.is_(None), Question.part == 5, Question.status == "draft"
    ).order_by(Question.id).all()
    assert len(blocks) == 2
    full = blocks[0]
    assert full.type == "writing" and full.exam_type == "VSTEP_B1"
    assert full.content.startswith(factory_to_bank.W1_BLOCK_INSTRUCTION)
    for i in range(1, 6):                                   # đủ 5 câu đánh số + 5 câu mẫu đánh số
        assert f"\n{i}. " in "\n" + full.content
        assert f"{i}. " in (full.reference_answer or "")
    assert "Kiểm theo câu" in (full.explanation or "")      # kết quả cổng kiểm liệt kê THEO CÂU
    assert "Nguồn seed" in (full.explanation or "")         # truy vết seed
    # Review S57: chế độ mock PHẢI lộ chỉ dấu trong explanation — khối mock không được hiển thị
    # như đã-qua-kiểm-AI-thật (đồng bộ hành vi _verify_prefix của R1-R4).
    assert "mock (offline)" in (full.explanation or "")
    # Review S57: khối trộn biến thể cùng seed (fixture 3 seed lấy × 2 biến thể) → cảnh báo rõ.
    assert "TRÙNG nguồn seed" in (full.explanation or "")
    partial = blocks[1]
    assert "1/5 câu" in (partial.explanation or "")         # khối lẻ: cảnh báo rõ cho GV

    # W2: 1 seed × per_seed 2 → 2 Question part 6, KHÔNG đáp án + note GV soát tay (converter chèn).
    res2 = factory_service.run_factory_to_bank(db_session, "writing_w2_letter", limit=1, per_seed=2,
                                               verify=True, generator=None)
    assert res2["saved_questions"] == 2, res2
    db_session.expire_all()
    letters = db_session.query(Question).filter(
        Question.exam_id.is_(None), Question.part == 6, Question.status == "draft"
    ).all()
    assert len(letters) == 2
    for q in letters:
        assert q.type == "writing" and q.reference_answer is None
        assert "CHƯA QUA CỔNG KIỂM" in (q.explanation or "")     # không hiển thị nhầm PASS
        assert "GIÁO VIÊN SOÁT TAY" in (q.explanation or "")
        assert "You are" in q.content                            # vai + bối cảnh đủ cho grade_writing


def test_SPEC_FACTORY_017_w1_answer_gate():
    """AC3: cổng kiểm W1 (viết-lại-độc-lập, không thấy câu mẫu): trùng mặt chữ → PASS 1 vòng;
    khác + giám khảo vòng 2 xác nhận → PASS; giám khảo bác/không trả lời → SUSPECT; thiếu field →
    checked=False + SUSPECT (graceful, không crash)."""
    def w1(answer="He goes to school every day."):
        return {"w1_item": {"original": "He attends school daily.",
                            "prompt": "He goes ______.", "answer": answer},
                "nguon_seed": "EB1.2901#1", "qc_ok": True}

    # (1) checker trùng mặt chữ (lệch dấu câu/hoa thường vẫn là TRÙNG) → PASS.
    stub = _StubChecker({"derived_answer": "he goes to school every day"})
    it = boss_factory.verify_bundle_answers([w1()], "writing_w1_rewrite", stub)[0]
    assert it["answer_verify"]["agree"] is True and "answer_verify_flag" not in it
    assert "TRÙNG câu mẫu" in it["answer_verify"]["note"]

    # (2) checker viết BẢN KHÁC + giám khảo vòng 2 xác nhận câu mẫu đúng → PASS + note nêu bản checker.
    stub = _StubChecker({"derived_answer": "He is at school daily.",
                         "answer_a_correct": True, "answer_b_correct": True, "note": "both valid"})
    it = boss_factory.verify_bundle_answers([w1()], "w1", stub)[0]
    assert it["answer_verify"]["agree"] is True and "answer_verify_flag" not in it
    assert "giám khảo xác nhận" in it["answer_verify"]["note"]

    # (3) giám khảo KHÔNG xác nhận (answer_b_correct=False) → SUSPECT (GV soát, không tự xoá).
    stub = _StubChecker({"derived_answer": "He is at school daily.", "answer_b_correct": False})
    it = boss_factory.verify_bundle_answers([w1()], "w1", stub)[0]
    assert it["answer_verify_flag"] == "SUSPECT"
    assert "KHÔNG xác nhận" in it["answer_verify"]["note"]

    # (3b) giám khảo không trả field (payload thiếu answer_b_correct) → coi như KHÔNG xác nhận → SUSPECT.
    stub = _StubChecker({"derived_answer": "He is at school daily."})
    it = boss_factory.verify_bundle_answers([w1()], "w1", stub)[0]
    assert it["answer_verify_flag"] == "SUSPECT"

    # (3c) Review S57: judge trả "true" dạng CHUỖI (JSON kiểu lỏng) → vẫn nhận PASS, không SUSPECT oan.
    stub = _StubChecker({"derived_answer": "He is at school daily.", "answer_b_correct": "true"})
    it = boss_factory.verify_bundle_answers([w1()], "w1", stub)[0]
    assert it["answer_verify"]["agree"] is True and "answer_verify_flag" not in it

    # (3d) Review S57: lệch CHỈ dấu NỘI câu (dấu phẩy đổi nghĩa) KHÔNG short-circuit PASS vòng 1 —
    # phải qua vòng 2 giám khảo (payload thiếu answer_b_correct → SUSPECT, chứng tỏ đã vào vòng 2).
    it2 = {"w1_item": {"original": "My father is fifty and works in a bank.",
                       "prompt": "My father, ______.",
                       "answer": "My father, who is fifty, works in a bank."},
           "nguon_seed": "EB1.2901#2", "qc_ok": True}
    stub = _StubChecker({"derived_answer": "My father who is fifty works in a bank."})
    it = boss_factory.verify_bundle_answers([it2], "w1", stub)[0]
    assert it["answer_verify_flag"] == "SUSPECT"

    # (4) item thiếu answer → checked=False + SUSPECT, không crash lô.
    it = boss_factory.verify_bundle_answers([w1(answer="")], "w1", stub)[0]
    assert it["answer_verify"]["checked"] is False and it["answer_verify_flag"] == "SUSPECT"

    # (5) cờ NGHI lan vào explanation của KHỐI khi vào ngân hàng (GV thấy ngay).
    items = [w1() for _ in range(2)]
    boss_factory.verify_bundle_answers(items, "w1", _StubChecker({"derived_answer": "X.", "answer_b_correct": False}))
    rows = factory_to_bank.bundle_items_to_rows("writing_w1_rewrite", items)
    assert rows and "NGHI" in (rows[0]["explanation"] or "")


def test_SPEC_FACTORY_017_skills_endpoint_metadata(db_session, admin_auth_headers):
    """AC4: GET /factory/skills trả đủ 6 skill kèm parts (FE auto-filter) + gate (ai|manual)."""
    from fastapi.testclient import TestClient

    from app.main import app as fastapi_app
    from app.core.database import get_db

    fastapi_app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(fastapi_app)
    try:
        resp = client.get("/api/v1/factory/skills", headers=admin_auth_headers)
        assert resp.status_code == 200
        skills = {s["skill"]: s for s in resp.json()["skills"]}
        # R1-R4 + W1/W2 (017) + speaking (018). Nghe = slice sau.
        assert {"reading_s1", "reading_s2_notice", "reading_s3_comprehension",
                "reading_s4_cloze", "writing_w1_rewrite", "writing_w2_letter"} <= set(skills)
        assert skills["writing_w1_rewrite"]["parts"] == [5]
        assert skills["writing_w1_rewrite"]["gate"] == "ai"        # W1 CÓ cổng kiểm
        assert skills["writing_w2_letter"]["parts"] == [6]
        assert skills["writing_w2_letter"]["gate"] == "manual"     # W2 tự luận — GV soát tay
        assert all(s["gate"] == "ai" and len(s["parts"]) == 1 for k, s in skills.items()
                   if k.startswith("reading_"))
    finally:
        fastapi_app.dependency_overrides.clear()


def test_SPEC_FACTORY_018_speaking_to_bank(db_session):
    """AC1-AC3: Nói (mock) → mỗi thẻ CHỈ import part2_topic thành 1 Question part 11 type speaking,
    KHÔNG đáp án, note GV soát tay; part1/part3 KHÔNG import (không tạo câu part 9/10)."""
    res = factory_service.run_factory_to_bank(db_session, "speaking", limit=2, per_seed=1,
                                              verify=True, generator=None)
    assert res["saved_questions"] == 2, res
    assert res["answer_suspect"] == 0            # dạng tự luận — verify bỏ qua, không gắn cờ/không crash
    db_session.expire_all()

    qs = db_session.query(Question).filter(
        Question.exam_id.is_(None), Question.part == 11, Question.status == "draft"
    ).all()
    assert len(qs) == 2, "mỗi thẻ = 1 câu Nói part 11"
    for q in qs:
        assert q.type == "speaking" and q.exam_type == "VSTEP_B1"
        assert q.reference_answer is None            # KHÔNG có đáp án đóng
        assert not q.options                          # {} — không phải trắc nghiệm
        assert q.content and "chủ đề" in q.content    # đề nói + hướng dẫn (grade_speaking dùng content)
        assert "CHƯA QUA CỔNG KIỂM" in (q.explanation or "")   # note GV soát tay (converter chèn)
        assert "Nguồn seed" in (q.explanation or "")           # truy vết seed
        assert q.topic                                # domain gắn nhãn

    # part1/part3 seed lặp → KHÔNG import: không có câu Nói part 9/10 nào được tạo.
    n_other = db_session.query(Question).filter(
        Question.exam_id.is_(None), Question.part.in_([9, 10]), Question.status == "draft"
    ).count()
    assert n_other == 0


def test_SPEC_FACTORY_018_speaking_skill_metadata(db_session, admin_auth_headers):
    """AC4: /factory/skills liệt kê 'speaking' part 11 gate 'manual' (Nói không có cổng kiểm đáp án)."""
    from fastapi.testclient import TestClient

    from app.main import app as fastapi_app
    from app.core.database import get_db

    fastapi_app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(fastapi_app)
    try:
        skills = {s["skill"]: s for s in client.get("/api/v1/factory/skills",
                                                    headers=admin_auth_headers).json()["skills"]}
        assert "speaking" in skills
        assert skills["speaking"]["parts"] == [11]
        assert skills["speaking"]["gate"] == "manual"
    finally:
        fastapi_app.dependency_overrides.clear()


def _load_lis_items(limit=1, per_seed=1):
    """Sinh items Nghe (mock, tất định) từ seed fixture pool_lis.json — dùng chung cho các test 019."""
    seeds = boss_factory.load_lis_seeds(factory_service._load_seed_bank("listening"))[:limit]
    return boss_factory.build_lis_variants(seeds, per_seed=per_seed, generator=None)


def test_SPEC_FACTORY_019_listening_to_bank(db_session):
    """AC1: Nghe (mock) → 5 Question part 7 (choice, chọn-tranh) + 1 nhóm part 8 (10 con fill), draft,
    audio_url=None; answer_suspect=0 (Nghe không có cổng kiểm đáp án đóng → verify bỏ qua, không crash)."""
    res = factory_service.run_factory_to_bank(db_session, "listening", limit=1, per_seed=1,
                                              verify=True, generator=None)
    assert res["saved_questions"] == 15, res     # 5 part 7 + 10 con part 8
    assert res["saved_groups"] == 1, res
    # verify=True trên skill gate 'manual' (Nghe) = kiểm CRASH-SAFETY: không route qua cổng kiểm đáp án,
    # không crash, không gắn cờ SUSPECT (answer_suspect luôn 0 vì listening ∉ VERIFY_SUPPORTED_SKILLS).
    assert res["answer_suspect"] == 0
    db_session.expire_all()

    p7 = db_session.query(Question).filter(
        Question.exam_id.is_(None), Question.part == 7, Question.status == "draft"
    ).all()
    assert len(p7) == 5, "L1 → 5 câu chọn-tranh part 7"
    for q in p7:
        assert q.type == "choice" and q.exam_type == "VSTEP_B1"
        assert q.audio_url is None                              # audio = slice sau
        assert q.reference_answer in ("A", "B", "C")           # chọn-tranh 3 phương án
        assert q.options and q.reference_answer in q.options
        assert "CHƯA QUA CỔNG KIỂM" in (q.explanation or "")   # note GV nghe soát tay (converter chèn)

    g8 = db_session.query(QuestionGroup).filter(
        QuestionGroup.exam_id.is_(None), QuestionGroup.part == 8, QuestionGroup.status == "draft"
    ).first()
    assert g8 is not None
    assert "______" in (g8.passage_text or "")                 # notes-template đục lỗ
    assert len(g8.questions) == 10, "L2 → nhóm 10 câu điền-từ part 8"
    for c in g8.questions:
        assert c.type == "fill" and c.audio_url is None
        assert c.reference_answer and not c.options            # điền từ: có đáp án, không phương án
        assert c.group_id == g8.id


def test_SPEC_FACTORY_019_listening_no_answer_leak():
    """AC2 (ĐIỀU KIỆN NGHIỆM THU): thứ thí sinh THẤY (content câu + passage_text nhóm) KHÔNG chứa
    transcript/đáp án; transcript + đáp án CHỈ nằm trong explanation (admin — không serialize cho thí sinh)."""
    items = _load_lis_items(limit=1, per_seed=1)
    assert items and items[0]["qc_ok"]
    rows = factory_to_bank.bundle_items_to_rows("listening", items)

    p7 = [r for r in rows if r.get("part") == 7 and "questions" not in r]
    groups8 = [r for r in rows if r.get("part") == 8 and "questions" in r]
    assert len(p7) == 5 and len(groups8) == 1
    grp = groups8[0]
    children = grp["questions"]
    assert len(children) == 10

    tr = items[0]["transcripts"]
    l1, l2_transcript = tr["l1"], tr["l2"]
    answers = items[0]["lis_item"]["answers"]

    # (a) L1 part 7: transcript hội thoại (lộ đáp án) KHÔNG lọt content/options thí sinh thấy, nhưng
    #     PHẢI nằm trong explanation (GV soát).
    for i, r in enumerate(p7):
        visible = r["content"] + " " + " ".join(str(v) for v in r["options"].values())
        assert l1[i]["transcript"] not in visible
        assert l1[i]["transcript"] in (r["explanation"] or "")

    # (b) L2 part 8: đáp án (từ) + transcript độc thoại KHÔNG lọt passage_text / content thí sinh thấy.
    student_visible = grp["passage_text"] + " " + " ".join(c["content"] for c in children)
    assert l2_transcript not in student_visible
    for n in range(6, 16):
        assert str(answers[str(n)]) not in student_visible     # đáp án không lộ
    # đáp án + transcript nằm trong explanation (admin — không serialize cho thí sinh).
    for c in children:
        assert "Đáp án chỗ" in (c["explanation"] or "")
        assert l2_transcript in (c["explanation"] or "")
    # reference_answer câu con = đúng từ đáp án L2 (giữ đủ cho GV/chấm).
    assert {c["reference_answer"] for c in children} == {str(answers[str(n)]) for n in range(6, 16)}


def test_SPEC_FACTORY_019_listening_skill_metadata(db_session, admin_auth_headers):
    """AC3: /factory/skills liệt kê 'listening' parts=[7,8] gate 'manual'."""
    from fastapi.testclient import TestClient

    from app.main import app as fastapi_app
    from app.core.database import get_db

    fastapi_app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(fastapi_app)
    try:
        skills = {s["skill"]: s for s in client.get("/api/v1/factory/skills",
                                                    headers=admin_auth_headers).json()["skills"]}
        assert "listening" in skills
        assert skills["listening"]["parts"] == [7, 8]
        assert skills["listening"]["gate"] == "manual"
    finally:
        fastapi_app.dependency_overrides.clear()


def test_SPEC_FACTORY_019_approve_blocks_listening_without_audio(db_session):
    """AC4: cổng approve chặn duyệt câu Nghe (part 7/8) CHƯA có audio; có audio (cấp câu HOẶC cấp nhóm) → duyệt được."""
    factory_service.run_factory_to_bank(db_session, "listening", limit=1, per_seed=1,
                                        verify=False, generator=None)
    db_session.expire_all()
    ids = [q.id for q in db_session.query(Question).filter(
        Question.exam_id.is_(None), Question.part.in_([7, 8]), Question.status == "draft"
    ).all()]
    assert len(ids) == 15

    # Chưa có audio → chặn (raise); KHÔNG câu nào bị flip approved (nguyên khối).
    with pytest.raises(ValueError, match="audio"):
        bank_admin.approve_questions(db_session, ids)
    db_session.expire_all()
    assert db_session.query(Question).filter(
        Question.id.in_(ids), Question.status == "approved"
    ).count() == 0

    # Gắn audio: part 7 ở CẤP CÂU, part 8 ở CẤP NHÓM (audio dùng chung cả bài) → cổng cho duyệt.
    # Nhắm ĐÚNG nhóm của câu con vừa sinh (theo group_id) — conftest seed sẵn vài nhóm part 8 khác.
    for q in db_session.query(Question).filter(Question.id.in_(ids), Question.part == 7).all():
        q.audio_url = "/media/listening/clip.mp3"
    g8_ids = {q.group_id for q in db_session.query(Question).filter(
        Question.id.in_(ids), Question.part == 8).all()}
    for g in db_session.query(QuestionGroup).filter(QuestionGroup.id.in_(g8_ids)).all():
        g.audio_url = "/media/listening/full.mp3"
    db_session.commit()
    assert bank_admin.approve_questions(db_session, ids) == 15


def test_SPEC_FACTORY_019_approve_blocks_short_w1_block(db_session):
    """AC5: cổng approve chặn duyệt khối W1 (part 5, type writing) <5 câu; khối đủ 5 câu duyệt được.

    Chặn TRƯỚC khi flip status (nguyên khối) — khối lẻ trong lô làm cả lô không duyệt (GV bỏ chọn rồi duyệt lại)."""
    short = Question(part=5, type="writing", content="Viết lại:\n1. ...\n2. ...\n3. ...",
                     reference_answer="1. a\n2. b\n3. c", status="draft", exam_type="VSTEP_B1")
    full = Question(part=5, type="writing", content="Viết lại 5 câu",
                    reference_answer="1. a\n2. b\n3. c\n4. d\n5. e", status="draft", exam_type="VSTEP_B1")
    db_session.add_all([short, full])
    db_session.commit()
    db_session.refresh(short)
    db_session.refresh(full)

    with pytest.raises(ValueError, match="THIẾU câu"):
        bank_admin.approve_questions(db_session, [short.id, full.id])
    db_session.expire_all()
    assert db_session.query(Question).filter(
        Question.id.in_([short.id, full.id]), Question.status == "approved"
    ).count() == 0            # nguyên khối: khối đủ 5 câu cũng KHÔNG bị duyệt khi lô có câu vướng

    # Chỉ khối đủ 5 câu → duyệt được (guard không over-block).
    assert bank_admin.approve_questions(db_session, [full.id]) == 1


def test_SPEC_FACTORY_019_lis_group_hash_content_derived():
    """Review [HIGH]: 2 bài Nghe CÙNG mã bài (mô phỏng re-run cùng seed) nhưng NỘI DUNG khác → hash
    nhóm part 8 KHÁC (phái sinh nội dung, không chỉ mã) → không bị dedup content_hash nuốt trọn khối
    mới (đúng lỗi lớp R4). Chặn hồi quy nếu bỏ ltag khỏi content câu con."""
    from app.services.parser import calculate_group_hash

    def _item(code, base):
        answers = {str(k): "A" for k in range(1, 6)}
        answers.update({str(n): f"{base}{n}" for n in range(6, 16)})
        l1 = [{"stem": f"{base} stem {i}", "options": {"A": "a", "B": "b", "C": "c"},
               "answer": "A", "transcript": f"{base} talk {i}"} for i in range(1, 6)]
        return {"lis_item": {"code": code, "src_code": code, "answers": answers,
                             "l2_gaps": list(range(6, 16))},
                "transcripts": {"l1": l1,
                                "l2": f"{base} monologue " + " ".join(answers[str(n)] for n in range(6, 16))},
                "difficulty_en": "medium", "qc_ok": True}

    ga = [r for r in factory_to_bank.bundle_items_to_rows("listening", [_item("LB1.90-X-1", "AAA")])
          if "questions" in r][0]
    gb = [r for r in factory_to_bank.bundle_items_to_rows("listening", [_item("LB1.90-X-1", "BBB")])
          if "questions" in r][0]
    assert calculate_group_hash(ga) != calculate_group_hash(gb), \
        "nhóm part 8 phải hash theo NỘI DUNG, không chỉ theo mã bài (chống dedup nuốt khối re-run)"


def test_SPEC_FACTORY_019_listening_multi_bundle_no_dedup_loss(db_session):
    """AC6 (bài học R4): 2 bài Nghe → 2 nhóm part 8 RIÊNG, KHÔNG bị dedup content_hash nuốt câu con."""
    res = factory_service.run_factory_to_bank(db_session, "listening", limit=1, per_seed=2,
                                              verify=False, generator=None)
    assert res["saved_groups"] == 2, res
    assert res["saved_questions"] == 30, res       # 2 × (5 part 7 + 10 con part 8)
    assert res["skipped_questions"] == 0, res
    db_session.expire_all()
    groups = db_session.query(QuestionGroup).filter(
        QuestionGroup.exam_id.is_(None), QuestionGroup.part == 8, QuestionGroup.status == "draft"
    ).all()
    assert len(groups) == 2
    assert all(len(g.questions) == 10 for g in groups), [len(g.questions) for g in groups]


def test_SPEC_FACTORY_019_approve_guard_not_bypassable_via_patch(db_session):
    """Review [LOW]: PATCH status='approved' cũng bị cổng an toàn thi chặn (không lách qua approve_questions)."""
    from app.schemas.bank import QuestionUpdate

    factory_service.run_factory_to_bank(db_session, "listening", limit=1, per_seed=1,
                                        verify=False, generator=None)
    db_session.expire_all()
    q = db_session.query(Question).filter(
        Question.exam_id.is_(None), Question.part == 7, Question.status == "draft"
    ).first()
    assert q is not None and not (q.audio_url or "")

    # PATCH duyệt câu Nghe thiếu audio → chặn (ValueError → 400 ở endpoint).
    with pytest.raises(ValueError, match="audio"):
        bank_admin.update_bank_question(db_session, q.id, QuestionUpdate(status="approved"))
    db_session.expire_all()
    assert db_session.get(Question, q.id).status == "draft"        # không bị duyệt lén

    # PATCH sửa nội dung (không đụng status) vẫn chạy bình thường.
    updated = bank_admin.update_bank_question(db_session, q.id, QuestionUpdate(difficulty="hard"))
    assert updated.difficulty == "hard"


def test_SPEC_FACTORY_023_listening_bundle_sidecar(db_session, monkeypatch):
    """Slice 6 nền tảng: khi Storage cấu hình, mỗi bài Nghe cất bundle THÔ (transcripts l1/l2 + lis_item) lên
    listening/{code}.bundle.json để slice render audio đọc lại transcript gốc. Thiếu cấu hình → bỏ qua, không crash."""
    from app.services import media_store

    # (1) Thiếu cấu hình Storage → bỏ qua, sidecars_stored=0, KHÔNG crash cả lượt sinh.
    monkeypatch.setattr(media_store, "is_configured", lambda: False)
    res0 = factory_service.run_factory_to_bank(db_session, "listening", limit=1, per_seed=1,
                                               verify=False, generator=None)
    assert res0["sidecars_stored"] == 0

    # (2) Có cấu hình → upload đúng path + content-type + payload chứa transcript gốc để render.
    captured = []
    monkeypatch.setattr(media_store, "is_configured", lambda: True)
    monkeypatch.setattr(media_store, "upload_bytes",
                        lambda path, data, content_type=None: captured.append((path, data, content_type)) or "url")
    res1 = factory_service.run_factory_to_bank(db_session, "listening", limit=1, per_seed=1,
                                               verify=False, generator=None)
    assert res1["sidecars_stored"] == 1 and len(captured) == 1
    path, data, ctype = captured[0]
    assert path.startswith("listening/") and path.endswith(".bundle.json")
    assert ctype == "application/json"
    payload = json.loads(data.decode("utf-8"))
    assert payload["transcripts"]["l1"] and payload["transcripts"]["l2"]     # transcript gốc (build_listening_audio cần)
    assert payload["lis_item"]["code"]

    # Skill khác (không phải Nghe) → KHÔNG cất sidecar.
    res2 = factory_service.run_factory_to_bank(db_session, "reading_s1", limit=1, per_seed=1,
                                               verify=False, generator=None)
    assert res2["sidecars_stored"] == 0


def _seed_listening_group(db_session):
    """Sinh 1 bộ Nghe text-only vào bank (mock) → trả nhóm part 8 draft vừa tạo."""
    factory_service.run_factory_to_bank(db_session, "listening", limit=1, per_seed=1,
                                        verify=False, generator=None)
    db_session.expire_all()
    return db_session.query(QuestionGroup).filter(
        QuestionGroup.exam_id.is_(None), QuestionGroup.part == 8, QuestionGroup.status == "draft"
    ).first()


def test_SPEC_FACTORY_024_render_listening_audio(db_session, monkeypatch):
    """Render (mock TTS/Storage): audio 1 file trọn bài → gắn audio_url lên nhóm part 8 + 5 câu part 7;
    SAU render cổng approve KHÔNG còn chặn (audio đủ) → duyệt cả bộ 15 câu được."""
    from app.services import boss_factory as bf
    from app.services import listening_render, media_store

    group = _seed_listening_group(db_session)
    assert group is not None

    fake_bundle = {"lis_item": {"code": "X"}, "transcripts": {
        "l1": [{"stem": f"Q{i}", "transcript": f"A: hi {i}\nB: yes {i}",
                "options": {"A": "a", "B": "b", "C": "c"}, "answer": "A"} for i in range(5)],
        "l2": "monologue " * 40}}
    monkeypatch.setattr(media_store, "download_bytes",
                        lambda path: json.dumps(fake_bundle).encode("utf-8"))
    monkeypatch.setattr(bf, "build_listening_audio",
                        lambda gen, item, out_dir, to_mp3=True: {
                            "audio_path": "/fake/x.mp3", "wav_path": "/fake/x.wav", "mp3_path": "/fake/x.mp3",
                            "duration_s": 1020.0, "format": "mp3", "n_segments": 20})
    monkeypatch.setattr(media_store, "upload_file",
                        lambda local, obj, content_type=None: f"https://cdn/{obj}")

    res = listening_render.render_listening_media(db_session, group.id, generator=object(), with_images=False)
    assert res["n_part7"] == 5
    assert res["audio_url"].endswith(".mp3") and res["duration_min"] == 17.0    # 1020s = 17'
    db_session.expire_all()

    g = db_session.get(QuestionGroup, group.id)
    assert g.audio_url == res["audio_url"]                                       # audio cấp NHÓM part 8
    p7 = db_session.query(Question).filter(
        Question.exam_id.is_(None), Question.part == 7, Question.status == "draft").all()
    assert len(p7) == 5 and all(q.audio_url == res["audio_url"] for q in p7)     # audio CẢ 5 câu part 7

    # Cổng approve TRƯỚC render chặn (audio trống); SAU render mở khoá → duyệt cả bộ 15 câu.
    ids = [q.id for q in p7] + [c.id for c in g.questions]
    assert bank_admin.approve_questions(db_session, ids) == 15


def test_SPEC_FACTORY_024_render_missing_sidecar_raises(db_session, monkeypatch):
    """Bộ Nghe sinh TRƯỚC khi có Storage (thiếu sidecar) → download lỗi → ValueError rõ (không crash job câm)."""
    from app.services import listening_render, media_store

    group = _seed_listening_group(db_session)

    def _boom(path):
        raise media_store.MediaStoreError("HTTP 404")

    monkeypatch.setattr(media_store, "download_bytes", _boom)
    with pytest.raises(ValueError, match="sidecar|Storage|bundle"):
        listening_render.render_listening_media(db_session, group.id, generator=object(), with_images=False)


def test_SPEC_FACTORY_024_render_endpoint_gating(db_session, admin_auth_headers):
    """API render: ẩn danh 401 · candidate 403 · nhóm không tồn tại/không phải part 8 → 400."""
    from fastapi.testclient import TestClient

    from app.core.database import get_db
    from app.core.security import create_access_token
    from app.main import app as fastapi_app

    fastapi_app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(fastapi_app)
    try:
        assert client.post("/api/v1/factory/render-listening-media",
                           json={"group_id": 1}).status_code == 401
        cand = create_access_token(data={"sub": "testcandidate", "role": "candidate"})
        assert client.post("/api/v1/factory/render-listening-media", json={"group_id": 1},
                           headers={"Authorization": f"Bearer {cand}"}).status_code == 403
        assert client.post("/api/v1/factory/render-listening-media", json={"group_id": 999999},
                           headers=admin_auth_headers).status_code == 400
    finally:
        fastapi_app.dependency_overrides.clear()


def _lis_item_same_code(base, l2seed):
    """Item Nghe hand-built CÙNG code 'LB1.90-Z-1' nhưng NỘI DUNG khác (base) → ltag khác."""
    answers = {str(k): "A" for k in range(1, 6)}
    answers.update({str(n): f"{base}w{n}" for n in range(6, 16)})
    l1 = [{"stem": f"{base} stem {i}", "options": {"A": "a", "B": "b", "C": "c"},
           "answer": "A", "transcript": f"{base} talk {i}"} for i in range(1, 6)]
    return {"lis_item": {"code": "LB1.90-Z-1", "src_code": "LB1.90-Z-1",
                         "answers": answers, "l2_gaps": list(range(6, 16))},
            "transcripts": {"l1": l1,
                            "l2": f"{l2seed} " + " ".join(answers[str(n)] for n in range(6, 16))},
            "difficulty_en": "medium", "qc_ok": True}


def test_SPEC_FACTORY_024_sidecar_slug_distinguishes_same_code():
    """Review [HIGH #2]: 2 bài CÙNG code khác nội dung → slug Storage KHÁC (ltag) → sidecar KHÔNG đè nhau."""
    ca, la = factory_to_bank.lis_bundle_identity(_lis_item_same_code("AAA", "one"))
    cb, lb = factory_to_bank.lis_bundle_identity(_lis_item_same_code("BBB", "two"))
    assert ca == cb and la != lb                                    # cùng code, khác ltag
    assert factory_to_bank.lis_storage_slug(ca, la) != factory_to_bank.lis_storage_slug(cb, lb)


def test_SPEC_FACTORY_024_render_scoped_to_own_bundle(db_session, monkeypatch):
    """Review [HIGH #1]: 2 bài Nghe CÙNG code, khác nội dung trong bank → render 1 bài chỉ gắn audio lên
    câu part 7 CỦA CHÍNH BÀI ĐÓ (theo token code·ltag), KHÔNG vớ nhầm part 7 bài kia."""
    from app.models.import_batch import ImportBatch
    from app.services import boss_factory as bf
    from app.services import listening_render, media_store, parser

    itemA, itemB = _lis_item_same_code("AAA", "one"), _lis_item_same_code("BBB", "two")
    batch = ImportBatch(source_file="test:lis", content_hash="lis-x", status="pending")
    db_session.add(batch)
    db_session.commit()
    db_session.refresh(batch)
    rows = (factory_to_bank.bundle_items_to_rows("listening", [itemA])
            + factory_to_bank.bundle_items_to_rows("listening", [itemB]))
    parser.save_parsed_items(db_session, rows, batch.id)
    db_session.expire_all()

    codeB, ltagB = factory_to_bank.lis_bundle_identity(itemB)
    tokenB = f"{codeB}·{ltagB}"
    groups = db_session.query(QuestionGroup).filter(
        QuestionGroup.exam_id.is_(None), QuestionGroup.part == 8, QuestionGroup.status == "draft").all()
    group_b = next(g for g in groups if any(f"(Bài {tokenB})" in (c.content or "") for c in g.questions))

    monkeypatch.setattr(media_store, "download_bytes", lambda path: json.dumps(itemB).encode("utf-8"))
    monkeypatch.setattr(bf, "build_listening_audio", lambda gen, item, out_dir, to_mp3=True: {
        "audio_path": "/f/x.mp3", "wav_path": "/f/x.wav", "mp3_path": "/f/x.mp3",
        "duration_s": 1000.0, "format": "mp3", "n_segments": 20})
    monkeypatch.setattr(media_store, "upload_file", lambda local, obj, content_type=None: f"https://cdn/{obj}")

    res = listening_render.render_listening_media(db_session, group_b.id, generator=object(), with_images=False)
    assert res["n_part7"] == 5                                      # CHỈ 5 câu part 7 của bài B
    db_session.expire_all()
    p7 = db_session.query(Question).filter(Question.part == 7, Question.status == "draft").all()
    p7a = [q for q in p7 if "AAA stem" in (q.content or "")]
    p7b = [q for q in p7 if "BBB stem" in (q.content or "")]
    assert len(p7a) == 5 and len(p7b) == 5
    assert all(q.audio_url == res["audio_url"] for q in p7b)        # bài B có audio
    assert all(not (q.audio_url or "") for q in p7a)                # bài A KHÔNG bị gắn NHẦM audio


def test_SPEC_FACTORY_024_render_with_images(db_session, monkeypatch):
    """AC4: with_images → image_url = 3 URL nối phẩy CHỈ khi đủ 3 tranh; câu thiếu tranh → bỏ qua (graceful)."""
    from app.services import boss_factory as bf
    from app.services import listening_render, media_store

    group = _seed_listening_group(db_session)
    fake_bundle = {"lis_item": {"code": "X"}, "transcripts": {
        "l1": [{"stem": f"Q{i}", "transcript": f"A: {i}", "options": {"A": "a", "B": "b", "C": "c"},
                "answer": "A"} for i in range(5)], "l2": "m " * 40}}
    monkeypatch.setattr(media_store, "download_bytes", lambda path: json.dumps(fake_bundle).encode("utf-8"))
    monkeypatch.setattr(bf, "build_listening_audio", lambda gen, item, out_dir, to_mp3=True: {
        "audio_path": "/f.mp3", "wav_path": "/f.wav", "mp3_path": "/f.mp3",
        "duration_s": 1000.0, "format": "mp3", "n_segments": 20})
    monkeypatch.setattr(media_store, "upload_file", lambda local, obj, content_type=None: f"https://cdn/{obj}")

    def fake_images(gen, item, out_dir):
        for j, q in enumerate(item["transcripts"]["l1"]):
            q["image_urls"] = "a.png,b.png,c.png" if j < 4 else "a.png,b.png"   # câu 5 THIẾU 1 tranh
        return {"n_images": 14, "n_failed": 1, "needs_billing": False}

    monkeypatch.setattr(bf, "build_listening_images", fake_images)

    res = listening_render.render_listening_media(db_session, group.id, generator=object(), with_images=True)
    assert res["images"]["questions_with_images"] == 4             # chỉ 4 câu đủ 3 tranh
    db_session.expire_all()
    p7 = db_session.query(Question).filter(Question.part == 7, Question.status == "draft").all()
    with_img = [q for q in p7 if q.image_url]
    assert len(with_img) == 4 and all(len(q.image_url.split(",")) == 3 for q in with_img)


def test_SPEC_FACTORY_020_db_persist_config_and_media_store(monkeypatch):
    """AC1-AC5: cấu hình DB bền (Supabase Postgres) + helper media_store — offline tất định.

    (1) scheme postgres:// → postgresql:// (SQLAlchemy 2 từ chối dạng cũ); (2) pool đọc từ env
    (Supavisor free hạn mức thấp); (3) thiếu cấu hình Storage → báo rõ, không crash; (4) upload
    đúng endpoint/headers/upsert → public URL; (5) HTTP lỗi → MediaStoreError (không nuốt)."""
    from app.core.config import Settings
    from app.services import media_store

    # (1) chuẩn hoá scheme — dán chuỗi kiểu Heroku/Supabase cũ vào env vẫn chạy.
    s = Settings(DATABASE_URL="postgres://u:p@host:5432/db")
    assert s.DATABASE_URL == "postgresql://u:p@host:5432/db"
    s = Settings(DATABASE_URL="postgresql://u:p@host:5432/db")
    assert s.DATABASE_URL == "postgresql://u:p@host:5432/db"      # đã đúng → giữ nguyên
    s = Settings(DATABASE_URL="sqlite:///./x.db")
    assert s.DATABASE_URL == "sqlite:///./x.db"                    # sqlite không đụng

    # (2) pool mặc định 5+10=15 (đúng cap client Supavisor free) + override được qua env/kwargs.
    assert Settings().DB_POOL_SIZE == 5 and Settings().DB_MAX_OVERFLOW == 10
    s = Settings(DB_POOL_SIZE=12, DB_MAX_OVERFLOW=3)
    assert s.DB_POOL_SIZE == 12 and s.DB_MAX_OVERFLOW == 3

    # (3) chưa cấu hình Storage → is_configured False + upload raise thông điệp rõ.
    monkeypatch.setattr(media_store.settings, "SUPABASE_URL", None)
    monkeypatch.setattr(media_store.settings, "SUPABASE_SERVICE_KEY", None)
    assert media_store.is_configured() is False
    with pytest.raises(media_store.MediaStoreError, match="chưa cấu hình"):
        media_store.upload_bytes("x.txt", b"1")

    # (4) upload: đúng endpoint bucket + Bearer key + x-upsert + content-type đoán từ đuôi.
    monkeypatch.setattr(media_store.settings, "SUPABASE_URL", "https://demo.supabase.co")
    monkeypatch.setattr(media_store.settings, "SUPABASE_SERVICE_KEY", "sk-test")
    monkeypatch.setattr(media_store.settings, "SUPABASE_BUCKET", "media")
    captured = {}

    class _Ok:
        status_code = 200
        text = "ok"

    def fake_post(url, content=None, headers=None, timeout=None):
        captured.update(url=url, headers=headers, size=len(content))
        return _Ok()

    monkeypatch.setattr(media_store.httpx, "post", fake_post)
    url = media_store.upload_bytes("listening/LB1.90-1.mp3", b"abc")
    assert url == "https://demo.supabase.co/storage/v1/object/public/media/listening/LB1.90-1.mp3"
    assert captured["url"] == "https://demo.supabase.co/storage/v1/object/media/listening/LB1.90-1.mp3"
    assert captured["headers"]["Authorization"] == "Bearer sk-test"
    assert captured["headers"]["x-upsert"] == "true"               # re-render cùng path không lỗi trùng
    assert captured["headers"]["Content-Type"] == "audio/mpeg"
    assert captured["size"] == 3

    # (5) HTTP lỗi → MediaStoreError kèm mã (caller graceful-skip, KHÔNG silent-pass).
    class _Denied:
        status_code = 403
        text = "denied"

    monkeypatch.setattr(media_store.httpx, "post", lambda *a, **k: _Denied())
    with pytest.raises(media_store.MediaStoreError, match="403"):
        media_store.upload_bytes("img/a.png", b"1")


def test_SPEC_FACTORY_021_tts_ab_harness_variants():
    """SPEC-FACTORY-021: harness ĐO giọng TTS A/B (bước đo, chưa tích hợp) — cấu trúc biến thể đúng
    + KHÔNG sửa production _lis_tts. Test tĩnh (không gọi Gemini): mốc v1 = baseline không style,
    v2+ có style-preamble, transcript đa-giọng có nhãn Anna/Ben, baseline giữ giọng production."""
    import importlib.util
    import os

    path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts", "eval_lis_voices.py")
    spec = importlib.util.spec_from_file_location("eval_lis_voices", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    keys = [v[0] for v in mod.VARIANTS]
    assert keys[0] == "v1_current_baseline"                 # mốc control đứng đầu
    assert mod.VARIANTS[0][2] is None                       # baseline v1 = KHÔNG style-preamble (hành vi production CŨ, trước 022)
    assert mod.VARIANTS[0][4] == mod.SPEAKERS_DEFAULT       # baseline v1 dùng Kore/Puck (giọng production CŨ = mốc 'trước')
    assert all(v[2] for v in mod.VARIANTS[1:])              # v2+ đều có style-preamble
    assert len(mod.VARIANTS) >= 3                           # đủ biến thể để so
    assert "Anna:" in mod.SAMPLE_TRANSCRIPT and "Ben:" in mod.SAMPLE_TRANSCRIPT  # nhãn đa-giọng
    # Harness ĐỘC LẬP: có hàm synthesize riêng, KHÔNG gọi production _lis_tts (đo tách khỏi tích hợp).
    # (Production _lis_tts SAU ĐÓ đã nhận style_preamble + đổi giọng ở SPEC-FACTORY-022 — harness vẫn tự dựng call.)
    assert callable(getattr(mod, "synthesize", None))


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


# ============================================================================
# SPEC-FACTORY-025 — Giao diện nhà máy căn theo Bản 1: Số lượng + Chủ đề/Độ khó
# (gợi ý mềm Cách A) + báo rõ khi sinh 0 câu + retry lỗi Gemini tạm thời.
# ============================================================================

def test_SPEC_FACTORY_025_count_derivation_and_result_fields(db_session):
    """AC1: count (Số lượng cần sinh) → quy đổi seed×biến-thể theo n_seeds; result có 'generated' + 'n_seeds'."""
    r1 = factory_service.run_factory_to_bank(db_session, "reading_s1", count=1, verify=False, generator=None)
    assert r1["generated"] == 1                          # count=1 → đúng 1 biến thể
    assert isinstance(r1.get("n_seeds"), int) and r1["n_seeds"] >= 1

    n = r1["n_seeds"]
    r2 = factory_service.run_factory_to_bank(db_session, "reading_s1", count=n * 3 + 10,
                                             verify=False, generator=None)
    assert 1 <= r2["generated"] <= n * 3, r2             # kẹp trần n_seeds×3 (per_seed cap 3)

    # KHÔNG over-generate: count giữa dải (n_seeds < count < n_seeds×3) → generated KHÔNG vượt count
    # (review S57i: derivation ceil cũ làm count=6/n_seeds=5 → 10; nay bám sát + cắt items[:count]).
    if n >= 2:
        mid = n + 1
        rm = factory_service.run_factory_to_bank(db_session, "reading_s1", count=mid,
                                                 verify=False, generator=None)
        assert rm["generated"] <= mid, rm

    # count=None → đường gọi cũ (limit/per_seed) vẫn chạy (giữ tương thích test/gọi cũ).
    r3 = factory_service.run_factory_to_bank(db_session, "reading_s1", limit=2, per_seed=1,
                                             verify=False, generator=None)
    assert r3["generated"] >= 1


def test_SPEC_FACTORY_025_steer_appends_and_gate_uses_base():
    """AC2: _build_steer rỗng khi không chọn; _SteeredGenerator nhét steer vào CUỐI user_prompt khi SINH,
    uỷ quyền thuộc tính khác về generator gốc (cổng kiểm dùng generator GỐC — KHÔNG steer)."""
    assert factory_service._build_steer(None, None) == ""
    steer = factory_service._build_steer("Sức khỏe", "easy")
    assert "Sức khỏe" in steer and "easy" in steer

    class _Fake:
        client = "real-client"

        def _call_gemini(self, system_instruction, user_prompt, **kw):
            return user_prompt   # echo để soi prompt

    base = _Fake()
    wrapped = factory_service._SteeredGenerator(base, "\n\nSTEER-MARK")
    assert wrapped.client == "real-client"                             # uỷ quyền thuộc tính về gốc
    out = wrapped._call_gemini("sys", "PROMPT-GỐC")
    assert out.startswith("PROMPT-GỐC") and out.endswith("STEER-MARK")  # steer ở CUỐI prompt
    assert base._call_gemini("sys", "PROMPT-GỐC") == "PROMPT-GỐC"       # generator gốc KHÔNG bị steer


def test_SPEC_FACTORY_025_call_gemini_retries_transient(monkeypatch):
    """AC4: _call_gemini thử lại lỗi Gemini TẠM THỜI (500/503/429) rồi mới raise (không rớt ngay 1 lần)."""
    from app.services import b1_question_gen as bq
    gen = bq.B1QuestionGenerator.__new__(bq.B1QuestionGenerator)
    gen.model_name = "test-model"
    calls = {"n": 0}

    class _Models:
        def generate_content(self, **kw):
            calls["n"] += 1
            raise RuntimeError("503 UNAVAILABLE: model overloaded")

    gen.client = type("C", (), {"models": _Models()})()
    monkeypatch.setattr(bq.time, "sleep", lambda s: None)   # bỏ sleep thật
    with pytest.raises(Exception):
        gen._call_gemini("sys", "user", max_output_tokens=256, thinking_budget=0)
    assert calls["n"] == bq._GEMINI_TRANSIENT_RETRIES + 1   # đã thử lại nhiều lần


def test_SPEC_FACTORY_025_call_gemini_no_retry_on_non_transient(monkeypatch):
    """AC4: lỗi KHÔNG phải tạm thời (safety/bad-request) → raise NGAY, KHÔNG thử lại."""
    from app.services import b1_question_gen as bq
    gen = bq.B1QuestionGenerator.__new__(bq.B1QuestionGenerator)
    gen.model_name = "test-model"
    calls = {"n": 0}

    class _Models:
        def generate_content(self, **kw):
            calls["n"] += 1
            raise ValueError("SAFETY: blocked prompt")

    gen.client = type("C", (), {"models": _Models()})()
    monkeypatch.setattr(bq.time, "sleep", lambda s: None)
    with pytest.raises(Exception):
        gen._call_gemini("sys", "user", max_output_tokens=256, thinking_budget=0)
    assert calls["n"] == 1   # không thử lại


def test_SPEC_FACTORY_025_skill_labels_part_prefix_and_group():
    """AC5: nhãn skill hiện rõ Part + đánh dấu '(nhóm)' cho R3/R4/Nghe; Nghe giữ GỘP part 7+8 (chung audio)."""
    labels = factory_service.SKILL_LABELS
    assert labels["reading_s1"].startswith("Part 1")
    assert "nhóm" in labels["reading_s3_comprehension"] and "nhóm" in labels["reading_s4_cloze"]
    assert "Part 7+8" in labels["listening"] and "audio" in labels["listening"].lower()


def test_SPEC_FACTORY_025_apply_user_labels_rows_and_children():
    """AC6: _apply_user_labels gắn nhãn CHỦ ĐỀ + ĐỘ KHÓ cho row + câu con khi có giá trị; rỗng/None → GIỮ
    NGUYÊN (không xoá domain_guess W2/Nói, không đổi độ khó seed). Độ khó NGOÀI enum easy|medium|hard →
    BỎ QUA (giữ seed). Hàm thuần — không đụng nội dung/đáp án/content_hash."""
    def _rows():
        return [
            {"part": 1, "topic": None, "difficulty": "medium"},                       # câu đơn (R1-R4/Nghe)
            {"part": 3, "topic": None, "difficulty": "medium",
             "questions": [{"part": 3, "topic": None, "difficulty": "medium"},
                           {"part": 3, "topic": None, "difficulty": "medium"}]},      # nhóm + câu con
            {"part": 11, "topic": "health", "difficulty": "easy"},                    # nhãn seed sẵn (Nói/W2)
        ]

    # rỗng/None/khoảng-trắng → GIỮ NGUYÊN (không ghi đè), kể cả domain_guess + độ khó seed.
    for empty in ("", None, "   "):
        rows = _rows()
        factory_to_bank._apply_user_labels(rows, empty, empty)
        assert rows[0]["topic"] is None and rows[0]["difficulty"] == "medium"
        assert all(c["topic"] is None and c["difficulty"] == "medium" for c in rows[1]["questions"])
        assert rows[2]["topic"] == "health" and rows[2]["difficulty"] == "easy"

    # Độ khó NGOÀI enum → bỏ qua (giữ độ khó seed); chủ đề vẫn gắn bình thường.
    rows = _rows()
    factory_to_bank._apply_user_labels(rows, "Môi trường", "expert")
    assert rows[0]["topic"] == "Môi trường" and rows[0]["difficulty"] == "medium"

    # Có chủ đề + độ khó hợp lệ → gắn HẾT (row + câu con, ghi đè seed); trim + chuẩn hoá chữ thường.
    rows = _rows()
    factory_to_bank._apply_user_labels(rows, "  Du lịch  ", "  HARD  ")
    for r in (rows[0], rows[1], rows[2]):
        assert r["topic"] == "Du lịch" and r["difficulty"] == "hard"
    assert all(c["topic"] == "Du lịch" and c["difficulty"] == "hard" for c in rows[1]["questions"])


def test_SPEC_FACTORY_025_labels_reach_bank(db_session):
    """AC6 (end-to-end): chủ đề + độ khó người dùng chọn được GẮN vào cột topic/difficulty của câu ĐƠN +
    NHÓM + câu con khi lưu ngân hàng (không chỉ steer prompt); không chọn → giữ nhãn mặc định.

    Cô lập bằng sentinel ('Sức khỏe'+'hard' / 'Du lịch'+'easy' — seed conftest dùng 'Family'/'Work'/None,
    difficulty toàn 'medium') + đối chiếu số câu gắn nhãn với saved_questions/saved_groups của LƯỢT sinh.
    """
    # Câu đơn (R1): chủ đề 'Sức khỏe' + độ khó 'hard' → đúng số câu sinh mang CẢ 2 nhãn (không lẫn seed).
    res1 = factory_service.run_factory_to_bank(db_session, "reading_s1", count=1,
                                               topic="Sức khỏe", difficulty="hard",
                                               verify=False, generator=None)
    labeled1 = db_session.query(Question).filter(
        Question.exam_id.is_(None), Question.topic == "Sức khỏe").all()
    assert res1["saved_questions"] >= 1
    assert len(labeled1) == res1["saved_questions"]
    assert all(q.part == 1 and q.difficulty == "hard" for q in labeled1)

    # Nhóm (R3): chủ đề 'Du lịch' + độ khó 'easy' gắn cả NHÓM + câu con (skill khác → không đụng dedup lượt trên).
    res3 = factory_service.run_factory_to_bank(db_session, "reading_s3_comprehension", count=1,
                                               topic="Du lịch", difficulty="easy",
                                               verify=False, generator=None)
    g3 = db_session.query(QuestionGroup).filter(
        QuestionGroup.exam_id.is_(None), QuestionGroup.topic == "Du lịch").all()
    assert res3["saved_groups"] >= 1 and len(g3) == res3["saved_groups"]
    assert all(g.difficulty == "easy" for g in g3)
    qg3 = db_session.query(Question).filter(
        Question.exam_id.is_(None), Question.topic == "Du lịch").all()
    assert qg3 and all(q.part == 3 and q.difficulty == "easy" for q in qg3)
    assert len(qg3) == res3["saved_questions"]

    # Nhóm R4 (part 4 điền-từ) — ĐÚNG CA màn hình Đạt gặp None: câu CON part 4 phải mang nhãn (giá trị
    # chủ đề y như FE gửi: 'Thực phẩm-đồ uống') + độ khó 'hard'.
    res4 = factory_service.run_factory_to_bank(db_session, "reading_s4_cloze", count=1,
                                               topic="Thực phẩm-đồ uống", difficulty="hard",
                                               verify=False, generator=None)
    g4 = db_session.query(QuestionGroup).filter(
        QuestionGroup.exam_id.is_(None), QuestionGroup.topic == "Thực phẩm-đồ uống").all()
    assert res4["saved_groups"] >= 1 and len(g4) == res4["saved_groups"]
    qg4 = db_session.query(Question).filter(
        Question.exam_id.is_(None), Question.topic == "Thực phẩm-đồ uống").all()
    assert qg4 and all(q.part == 4 and q.difficulty == "hard" for q in qg4)
    assert len(qg4) == res4["saved_questions"]

    # KHÔNG chọn nhãn → KHÔNG câu mới nào bị gắn chủ đề (mọi câu R2 giữ topic None mặc định).
    before = db_session.query(Question).filter(
        Question.exam_id.is_(None), Question.topic.isnot(None)).count()
    res2 = factory_service.run_factory_to_bank(db_session, "reading_s2_notice", count=1,
                                               verify=False, generator=None)
    after = db_session.query(Question).filter(
        Question.exam_id.is_(None), Question.topic.isnot(None)).count()
    assert res2["saved_questions"] >= 1
    assert after == before   # lượt không-nhãn không thêm câu gắn chủ đề → giữ mặc định


def test_SPEC_FACTORY_025_labels_serialized_and_filterable(db_session, admin_auth_headers):
    """AC6 (HTTP end-to-end): sau khi sinh có chủ đề + độ khó, GET /api/v1/bank/questions serialize cột
    topic/difficulty + LỌC được theo ?topic=&difficulty= — đúng chuỗi FE dựa vào (cột + bộ lọc 'cho tiện')."""
    from fastapi.testclient import TestClient
    from app.main import app as fastapi_app
    from app.core.database import get_db

    factory_service.run_factory_to_bank(db_session, "reading_s1", count=1,
                                        topic="Sức khỏe", difficulty="hard",
                                        verify=False, generator=None)

    fastapi_app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(fastapi_app)
    try:
        resp = client.get("/api/v1/bank/questions?topic=Sức khỏe&difficulty=hard&limit=100",
                          headers=admin_auth_headers)
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert items, "phải có câu gắn nhãn 'Sức khỏe'/'hard' trả về"
        assert all(it["topic"] == "Sức khỏe" and it["difficulty"] == "hard" for it in items)
        assert all(it["part"] == 1 for it in items)
    finally:
        fastapi_app.dependency_overrides.clear()


def test_SPEC_FACTORY_025_labels_not_in_content_hash():
    """AC6 (REGRESSION GUARD — mệnh đề rủi ro nhất của thay đổi): topic + difficulty NẰM NGOÀI content_hash
    → gắn nhãn KHÔNG đổi chống-trùng/dedup. Nếu dev sau này nhét topic/difficulty vào calculate_*_hash, câu/
    nhóm CÙNG nội dung KHÁC nhãn sẽ hết dedup → nhân đôi ngân hàng (re-import/re-run cùng bộ khác nhãn); test
    này KHOÁ bất biến đó (không có nó, chỉnh hash vẫn để suite xanh — review đối kháng đã tái hiện)."""
    from app.services.parser import calculate_group_hash, calculate_question_hash

    q = {"set_id": "S", "number": 1, "part": 1, "type": "choice",
         "content": "Cùng một nội dung câu hỏi", "options": {"A": "a", "B": "b"},
         "reference_answer": "A", "topic": None, "difficulty": "medium"}
    base_q = calculate_question_hash(q)
    assert base_q == calculate_question_hash({**q, "topic": "Sức khỏe"})
    assert base_q == calculate_question_hash({**q, "difficulty": "hard"})

    g = {"set_id": "S", "part": 3, "passage_text": "Cùng một đoạn văn", "audio_url": None,
         "topic": None, "difficulty": "medium", "questions": [{"content": "câu con 1"}, {"content": "câu con 2"}]}
    base_g = calculate_group_hash(g)
    assert base_g == calculate_group_hash({**g, "topic": "Du lịch"})
    assert base_g == calculate_group_hash({**g, "difficulty": "hard"})


# ============================================================================
# SPEC-FACTORY-026 — Corpus SEED B1 production (tự soạn nguyên gốc, 14 chủ đề) làm seed nhà máy
# thay/bổ sung fixture 2-đề. Tách seed test↔production qua env FACTORY_SEED_DIR.
# ============================================================================

_CORPUS_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "app", "data", "factory_seeds"))


def _load_corpus(fname):
    with open(os.path.join(_CORPUS_DIR, fname), encoding="utf-8") as f:
        return json.load(f)


def test_SPEC_FACTORY_026_corpus_parses_all_skills():
    """AC1: corpus production backend/app/data/factory_seeds/ parse được qua MỌI loader boss_factory,
    đủ 8 dạng + ĐA DẠNG hơn hẳn fixture 2-đề (fixture: R1=5,R3=1,R4=1,W1=1) → nhà máy sinh phong phú hơn."""
    from app.services import boss_factory as bf
    bank = _load_corpus("bank_raw.json")
    assert len(bank) >= 10                                   # ~14 đề (1/chủ đề)
    r1, r2, r3, r4 = (bf.load_r1_seeds(bank), bf.load_r2_seeds(bank),
                      bf.load_r3_seeds(bank), bf.load_r4_seeds(bank))
    w1, w2 = bf.load_w1_seeds(bank), bf.load_w2_seeds(bank)
    sp = bf.load_speak_seeds(_load_corpus("pool_speak.json"))
    ls = bf.load_lis_seeds(_load_corpus("pool_lis.json"))
    # Mọi dạng có seed + nhiều hơn hẳn fixture (chống corpus vô tình rỗng/mất dạng khi build fresh).
    assert len(r1) >= 20 and len(r2) >= 20 and len(r3) >= 10 and len(r4) >= 10
    assert len(w1) >= 10 and len(w2) >= 10 and len(sp) >= 10 and len(ls) >= 5


def test_SPEC_FACTORY_026_corpus_internal_consistency():
    """AC2: đáp án corpus nhất quán nội bộ (chống seed hỏng đẩy câu lỗi vào nhà máy) — R1 answer∈options;
    R4 answers∈hộp-từ & đủ 10 chỗ 21-30; Nói domain∈14 chủ đề; Nghe l2_gaps khớp khóa L2 (10 chỗ)."""
    from app.services import boss_factory as bf
    bank = _load_corpus("bank_raw.json")
    for s in bf.load_r1_seeds(bank):
        assert s["answer"] in s["options"], f"R1 {s['ma_de']}"
    for s in bf.load_r4_seeds(bank):
        boxn = {bf._norm_word(w) for w in s["box"]}
        assert len(s["answers"]) == 10 and all(bf._norm_word(v) in boxn for v in s["answers"].values()), s["ma_de"]
    for s in bf.load_speak_seeds(_load_corpus("pool_speak.json")):
        assert bf._norm_domain(s["domain_guess"]) in bf._DOMAINS_14_NORM, s["domain_guess"]
    for s in bf.load_lis_seeds(_load_corpus("pool_lis.json")):
        gaps = [int(n) for n in s["l2_gaps"]]
        assert len(gaps) == 10 and all(str(n) in s["answers"] for n in gaps), s["code"]


def test_SPEC_FACTORY_026_seed_dir_env_resolution(monkeypatch):
    """AC3: _seed_dir() resolve TẠI CALL-TIME — env FACTORY_SEED_DIR override → dùng; unset → default =
    corpus production (backend/app/data/factory_seeds). Nhờ vậy conftest ép fixture, prod dùng corpus."""
    from app.services import factory_service as fs
    monkeypatch.setenv("FACTORY_SEED_DIR", os.path.join("X", "seed-override"))
    assert fs._seed_dir().endswith(os.path.join("X", "seed-override"))
    monkeypatch.delenv("FACTORY_SEED_DIR", raising=False)
    assert fs._seed_dir() == fs._DEFAULT_SEED_DIR
    assert fs._seed_dir().endswith(os.path.join("app", "data", "factory_seeds"))


def test_SPEC_FACTORY_026_factory_generates_from_corpus(db_session, monkeypatch):
    """AC4: nhà máy chạy end-to-end trên CORPUS production (mock) → sinh + lưu draft; n_seeds phản ánh
    corpus (>=20 R1), sinh nhiều câu KHÁC nhau (đa dạng cấu trúc — mục tiêu corpus). GUARD chống 'sập
    còn 1' do near-dup: W2/Nói mock phải giữ ĐA DẠNG theo seed (review 026 HIGH: mock W2 chọn domain
    theo idx → 14 đề đều 'Bản thân' → near-dup loại 13/14)."""
    from app.services import factory_service as fs
    monkeypatch.delenv("FACTORY_SEED_DIR", raising=False)   # bỏ override fixture → dùng corpus prod

    res = fs.run_factory_to_bank(db_session, "reading_s1", count=8, verify=False, generator=None)
    assert res["n_seeds"] >= 20 and res["saved_questions"] >= 5      # 8 seed khác nhau → nhiều câu
    res2 = fs.run_factory_to_bank(db_session, "reading_s2_notice", count=8, verify=False, generator=None)
    assert res2["saved_questions"] >= 5
    res3 = fs.run_factory_to_bank(db_session, "reading_s3_comprehension", count=2,
                                  verify=False, generator=None)
    assert res3["n_seeds"] >= 10 and res3["saved_groups"] >= 1

    # W2 (Viết thư) + Nói: mỗi seed 1 đề → KHÔNG được near-dup nuốt về 1 (guard mock đa-dạng-theo-seed).
    resw2 = fs.run_factory_to_bank(db_session, "writing_w2_letter", count=10, verify=False, generator=None)
    assert resw2["n_seeds"] >= 10 and resw2["saved_questions"] >= 8, resw2   # KHÔNG sập còn 1
    resspk = fs.run_factory_to_bank(db_session, "speaking", count=8, verify=False, generator=None)
    assert resspk["saved_questions"] >= 6, resspk
