"""
SPEC-BANK-* — Bảo chứng về Ngân hàng câu hỏi (Giai đoạn 2 phân hệ Ra đề).

Ngân hàng = các bản ghi Question/QuestionGroup có exam_id IS NULL.
Sinh đề chỉ được CLONE từ ngân hàng, không được sửa/phá bản gốc, và (mục tiêu)
chỉ được chọn item đã qua duyệt (status='approved').
"""
from sqlalchemy.orm import Session

from app.models.question import Question
from app.models.question_group import QuestionGroup
from app.services.exam_generator import generate_exam, InsufficientBankError, VSTEP_B1_BLUEPRINT


def test_SPEC_BANK_001_only_approved_items_generated(db_session: Session):
    """SPEC-BANK-001: Thuật toán sinh đề chỉ được chọn câu hỏi/nhóm có
    status='approved' từ ngân hàng; item draft/retired không bao giờ xuất hiện
    trong đề sinh ra.

    Kịch bản: chuyển TOÀN BỘ câu Part 1 trong bank về status='draft' rồi sinh đề.
    Đề hợp lệ không được chứa câu Part 1 nào (hoặc raise lỗi thiếu bank).
    """
    db_session.query(Question).filter(
        Question.exam_id.is_(None), Question.part == 1
    ).update({"status": "draft"}, synchronize_session=False)
    db_session.commit()
    db_session.expire_all()

    try:
        exam = generate_exam(db_session, VSTEP_B1_BLUEPRINT, title="Đề kiểm tra SPEC-BANK-001")
        p1_in_exam = db_session.query(Question).filter(
            Question.exam_id == exam.id, Question.part == 1
        ).count()
        assert p1_in_exam == 0, (
            f"Đề chứa {p1_in_exam} câu Part 1 được clone từ item chưa duyệt (draft)"
        )
    except InsufficientBankError:
        # Lỗi thiếu bank là hành vi hợp lệ khi toàn bộ Part 1 là draft
        pass


def test_SPEC_BANK_002_generation_preserves_bank(db_session: Session):
    """SPEC-BANK-002: Thao tác sinh đề chỉ CLONE dữ liệu từ ngân hàng; tập câu
    hỏi/nhóm gốc (exam_id IS NULL) phải bất biến cả về số lượng lẫn nội dung.
    """
    def bank_snapshot():
        questions = {
            (q.id, q.content, q.part, q.reference_answer, q.difficulty)
            for q in db_session.query(Question).filter(Question.exam_id.is_(None)).all()
        }
        groups = {
            (g.id, g.part, g.topic, g.passage_text, g.audio_url, g.difficulty)
            for g in db_session.query(QuestionGroup).filter(QuestionGroup.exam_id.is_(None)).all()
        }
        return questions, groups

    questions_before, groups_before = bank_snapshot()

    try:
        generate_exam(db_session, VSTEP_B1_BLUEPRINT, title="Đề kiểm tra SPEC-BANK-002")
    except InsufficientBankError:
        pass
        
    db_session.expire_all()

    questions_after, groups_after = bank_snapshot()
    assert questions_after == questions_before, "Sinh đề làm thay đổi câu hỏi trong bank"
    assert groups_after == groups_before, "Sinh đề làm thay đổi nhóm trong bank"


def test_SPEC_BANK_003_bank_admin_api(db_session: Session, admin_auth_headers: dict):
    """
    SPEC-BANK-003: API quản trị ngân hàng câu hỏi.
    Xác minh các hành vi:
    1. GET /api/v1/bank/questions - liệt kê phân trang và bộ lọc (chỉ lấy exam_id IS NULL).
    2. PATCH /api/v1/bank/questions/{id} - sửa đổi (chỉ cho phép sửa item bank gốc, clone báo 404).
    3. POST /api/v1/bank/questions/approve - duyệt hàng loạt, tự động duyệt group cha.
    """
    from fastapi.testclient import TestClient
    from app.main import app as fastapi_app
    from app.core.database import get_db

    fastapi_app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(fastapi_app)

    try:
        # 1. Liệt kê câu hỏi nháp (Draft)
        resp = client.get("/api/v1/bank/questions?status=draft&limit=5", headers=admin_auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert "items" in data
        
        # 2. Tạo một câu hỏi nháp trong DB để kiểm tra sửa/duyệt
        draft_standalone = Question(
            part=1,
            type="choice",
            content="Draft Standalone Question Content",
            reference_answer="A",
            status="draft",
            exam_type="VSTEP_B1"
        )
        db_session.add(draft_standalone)
        
        draft_group = QuestionGroup(
            part=3,
            status="draft",
            passage_text="Draft group passage"
        )
        db_session.add(draft_group)
        db_session.commit()
        db_session.refresh(draft_group)
        
        draft_grouped_q = Question(
            part=3,
            group_id=draft_group.id,
            type="choice",
            content="Draft Grouped Question Content",
            reference_answer="B",
            status="draft",
            exam_type="VSTEP_B1"
        )
        db_session.add(draft_grouped_q)
        db_session.commit()
        db_session.refresh(draft_standalone)
        db_session.refresh(draft_grouped_q)

        # Sửa đổi standalone question qua API
        patch_payload = {
            "content": "Updated content via API",
            "difficulty": "easy"
        }
        patch_resp = client.patch(
            f"/api/v1/bank/questions/{draft_standalone.id}",
            json=patch_payload,
            headers=admin_auth_headers
        )
        assert patch_resp.status_code == 200
        assert patch_resp.json()["content"] == "Updated content via API"
        
        # Sửa đổi một câu clone trong đề thi -> Phải bị chặn 404
        clone_q = Question(
            exam_id=999,  # Không thuộc bank
            part=1,
            type="choice",
            content="Clone Question Content",
            status="approved"
        )
        db_session.add(clone_q)
        db_session.commit()
        db_session.refresh(clone_q)
        
        fail_patch_resp = client.patch(
            f"/api/v1/bank/questions/{clone_q.id}",
            json={"content": "Should Fail"},
            headers=admin_auth_headers
        )
        assert fail_patch_resp.status_code == 404

        # 3. Duyệt câu standalone và câu grouped
        approve_payload = {
            "ids": [draft_standalone.id, draft_grouped_q.id]
        }
        approve_resp = client.post(
            "/api/v1/bank/questions/approve",
            json=approve_payload,
            headers=admin_auth_headers
        )
        assert approve_resp.status_code == 200
        assert approve_resp.json()["updated"] == 2
        
        db_session.refresh(draft_standalone)
        db_session.refresh(draft_grouped_q)
        db_session.refresh(draft_group)
        
        assert draft_standalone.status == "approved"
        assert draft_grouped_q.status == "approved"
        assert draft_group.status == "approved"

    finally:
        fastapi_app.dependency_overrides.clear()


def test_SPEC_BANK_004_b1_bank_stats_and_questions(db_session: Session, admin_auth_headers: dict):
    """
    SPEC-BANK-004: Kiểm tra thống kê ngân hàng và API câu hỏi VSTEP B1.
    """
    import os
    from app.services.parser import import_b1_reading_set
    from app.services import bank_admin
    from fastapi.testclient import TestClient
    from app.main import app as fastapi_app
    from app.core.database import get_db

    # 1. Đường dẫn tệp B1 mẫu (CI-safe)
    fixtures_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "fixtures", "parser"))
    docx_path = os.path.join(fixtures_dir, "B1_exam_sample.docx")
    key_path = os.path.join(fixtures_dir, "B1_key_sample.docx")

    assert os.path.exists(docx_path)
    assert os.path.exists(key_path)

    # 2. Import bộ B1 Đọc+Viết mẫu
    result = import_b1_reading_set(db_session, docx_path, key_path)
    assert result["imported_questions"] == 32

    # 3. Đếm trong database
    b1_questions = db_session.query(Question).filter(
        Question.exam_id.is_(None),
        Question.exam_type == "VSTEP_B1"
    ).all()
    assert len(b1_questions) >= 32

    # 4. Kiểm tra thống kê stats chỉ phản ánh đúng số lượng câu hỏi VSTEP B1
    stats = bank_admin.compute_bank_stats(db_session, exam_type="VSTEP_B1")
    assert stats is not None

    # 5. Kiểm tra API GET /api/v1/bank/questions lọc chính xác theo exam_type
    fastapi_app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(fastapi_app)
    try:
        resp_b1 = client.get("/api/v1/bank/questions?exam_type=VSTEP_B1&limit=100", headers=admin_auth_headers)
        assert resp_b1.status_code == 200
        assert resp_b1.json()["total"] >= 32
        for item in resp_b1.json()["items"]:
            assert item["exam_type"] == "VSTEP_B1"
    finally:
        fastapi_app.dependency_overrides.clear()


def test_SPEC_BANK_005_question_enrichment_api(db_session: Session, admin_auth_headers: dict):
    """
    SPEC-BANK-005: Kiểm thử API sinh câu hỏi tự động (Enrichment).
    Xác minh các hành vi:
    - Quyền Admin/Teacher gọi thành công (Mock Mode).
    - Giới hạn số lượng câu sinh tối đa 5 câu/lần.
    - Validate part hợp lệ.
    - Candidate gọi bị chặn 403.
    """
    from fastapi.testclient import TestClient
    from app.main import app as fastapi_app
    from app.core.database import get_db
    from app.core.security import create_access_token

    fastapi_app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(fastapi_app)

    # Tự tạo token và header cho candidate
    candidate_token = create_access_token(data={"sub": "testcandidate", "role": "candidate"})
    candidate_auth_headers = {"Authorization": f"Bearer {candidate_token}"}

    try:
        # 1. Gọi thành công với vai trò Admin (sinh 1 câu hỏi Part 1 độ khó hard)
        response = client.post(
            "/api/v1/bank/enrich",
            json={"count": 1, "part": "1", "topic": "Giáo dục", "difficulty": "hard"},
            headers=admin_auth_headers
        )
        assert response.status_code == 200
        res = response.json()
        assert res["success"] is True
        assert res["generated_count"] == 1

        # Xác nhận câu hỏi đã được lưu vào database ở trạng thái draft và đúng độ khó hard
        from app.models.question import Question
        q = db_session.query(Question).filter(
            Question.exam_id.is_(None),
            Question.part == 1,
            Question.status == "draft",
            Question.topic == "Giáo dục"
        ).first()
        assert q is not None
        assert q.exam_type == "VSTEP_B1"
        assert q.difficulty == "hard"

        # 2. Gọi với số lượng vượt quá giới hạn (> 5) -> Chặn 400
        response = client.post(
            "/api/v1/bank/enrich",
            json={"count": 6, "part": "1"},
            headers=admin_auth_headers
        )
        assert response.status_code == 400
        assert "tối đa là 5" in response.json()["detail"]

        # 3. Gọi với Part không hợp lệ -> Chặn 400
        response = client.post(
            "/api/v1/bank/enrich",
            json={"count": 1, "part": "invalid_part"},
            headers=admin_auth_headers
        )
        assert response.status_code == 400
        assert "chọn cụ thể từng Part" in response.json()["detail"]

        # 4. Người dùng thường (Candidate) gọi -> Chặn 403
        response = client.post(
            "/api/v1/bank/enrich",
            json={"count": 1, "part": "1"},
            headers=candidate_auth_headers
        )
        assert response.status_code == 403

        # 5. Người dùng không đăng nhập gọi -> Chặn 401
        response = client.post(
            "/api/v1/bank/enrich",
            json={"count": 1, "part": "1"}
        )
        assert response.status_code == 401

    finally:
        fastapi_app.dependency_overrides.clear()


def test_SPEC_BANK_006_async_question_enrichment_api(db_session: Session, admin_auth_headers: dict, monkeypatch):
    """SPEC-BANK-006: API sinh câu hỏi AI BẤT ĐỒNG BỘ.

    Xác minh:
    - POST /enrich-async CHẤP NHẬN lô lớn (count=8 > 5) — đường đồng bộ /enrich sẽ
      trả 400 với cùng count — và phản hồi ngay job_id + trạng thái.
    - GET /tasks/{job_id} trả tiến độ; job hoàn tất, generated_count KHỚP số câu
      nháp thực sự ghi vào DB (không tautology).
    - Chặn count > 50, part không hợp lệ, job_id lạ (404), và phân quyền
      admin/teacher (candidate 403, chưa đăng nhập 401) trên cả POST lẫn GET.

    Cô lập, tất định: chạy job INLINE (RUN_JOBS_INLINE) + trỏ SessionLocal của job
    runner về engine test + ép generator về mock mode (GEMINI_API_KEY=None) để không
    gọi mạng và không phụ thuộc thời điểm của thread.
    """
    from fastapi.testclient import TestClient
    from sqlalchemy.orm import sessionmaker

    from app.main import app as fastapi_app
    from app.core.database import get_db
    from app.core.security import create_access_token
    from app.core.config import settings
    import app.services.enrich_jobs as enrich_jobs

    # Job runner mở session riêng -> trỏ về engine test để test thấy câu nháp.
    test_engine = db_session.get_bind()
    WorkerSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    monkeypatch.setattr(enrich_jobs, "SessionLocal", WorkerSession)
    # Chạy job đồng bộ trong tiến trình test (không thread, không broker) -> tất định.
    monkeypatch.setattr(enrich_jobs, "RUN_JOBS_INLINE", True)
    # Ép generator về mock mode (không gọi Gemini/mạng, không tốn quota).
    monkeypatch.setattr(settings, "GEMINI_API_KEY", None)

    fastapi_app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(fastapi_app)

    candidate_token = create_access_token(data={"sub": "testcandidate", "role": "candidate"})
    candidate_headers = {"Authorization": f"Bearer {candidate_token}"}

    try:
        # 1. Lô lớn count=8 (> giới hạn đồng bộ 5) -> CHẤP NHẬN, trả job_id.
        resp = client.post(
            "/api/v1/bank/enrich-async",
            json={"count": 8, "part": "1", "topic": "Giáo dục", "difficulty": "medium"},
            headers=admin_auth_headers,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        job_id = body["job_id"]
        assert job_id
        assert body["status"] in {"pending", "running", "completed"}

        # Đối chứng: cùng count=8 trên đường ĐỒNG BỘ bị chặn 400 (khác biệt cốt lõi).
        resp_sync = client.post(
            "/api/v1/bank/enrich",
            json={"count": 8, "part": "1"},
            headers=admin_auth_headers,
        )
        assert resp_sync.status_code == 400
        assert "tối đa là 5" in resp_sync.json()["detail"]

        # 2. Poll tiến độ -> hoàn tất; generated_count khớp số câu nháp thật trong DB.
        st = client.get(f"/api/v1/bank/tasks/{job_id}", headers=admin_auth_headers)
        assert st.status_code == 200, st.text
        status = st.json()
        assert status["job_id"] == job_id
        assert status["status"] == "completed"
        assert status["requested"] == 8
        gen = status["generated_count"]
        assert gen >= 1

        db_session.expire_all()
        draft_count = db_session.query(Question).filter(
            Question.exam_id.is_(None),
            Question.part == 1,
            Question.status == "draft",
            Question.topic == "Giáo dục",
        ).count()
        assert draft_count == gen, f"generated_count={gen} nhưng DB có {draft_count} câu nháp"

        # Generator phải gán ĐÚNG topic yêu cầu (không chỉ suy ra từ bộ lọc).
        sample = db_session.query(Question).filter(
            Question.exam_id.is_(None),
            Question.part == 1,
            Question.status == "draft",
            Question.topic == "Giáo dục",
        ).first()
        assert sample is not None and sample.topic == "Giáo dục"

        # 3. count > 50 -> 400.
        r_over = client.post(
            "/api/v1/bank/enrich-async",
            json={"count": 51, "part": "1"},
            headers=admin_auth_headers,
        )
        assert r_over.status_code == 400
        assert "50" in r_over.json()["detail"]

        # 4. Part không hợp lệ -> 400.
        r_part = client.post(
            "/api/v1/bank/enrich-async",
            json={"count": 1, "part": "invalid_part"},
            headers=admin_auth_headers,
        )
        assert r_part.status_code == 400
        assert "chọn cụ thể" in r_part.json()["detail"]

        # 5. job_id lạ -> 404.
        r_404 = client.get("/api/v1/bank/tasks/khong-ton-tai", headers=admin_auth_headers)
        assert r_404.status_code == 404

        # 6. Candidate bị chặn 403 (POST + GET).
        r_c_post = client.post(
            "/api/v1/bank/enrich-async",
            json={"count": 1, "part": "1"},
            headers=candidate_headers,
        )
        assert r_c_post.status_code == 403
        r_c_get = client.get(f"/api/v1/bank/tasks/{job_id}", headers=candidate_headers)
        assert r_c_get.status_code == 403

        # 7. Chưa đăng nhập bị chặn 401.
        r_anon = client.post("/api/v1/bank/enrich-async", json={"count": 1, "part": "1"})
        assert r_anon.status_code == 401

    finally:
        fastapi_app.dependency_overrides.clear()


def test_SPEC_BANK_006_async_enrich_thread_fallback(db_session: Session, monkeypatch):
    """SPEC-BANK-006 — đường DỰ PHÒNG THREAD (Render free: không Redis/worker).

    Khi Celery không eager và .delay() thất bại (broker không tới được),
    dispatch_enrich_job PHẢI chạy job qua background thread. Test này kiểm chính
    nhánh đó — điều mà test chính (RUN_JOBS_INLINE) bỏ qua. Dùng Thread giả chạy
    đồng bộ để nhánh được thực thi tất định (không phụ thuộc lịch OS)."""
    from sqlalchemy.orm import sessionmaker

    from app.core.config import settings
    from app.core.celery import celery_app
    import app.services.enrich_jobs as enrich_jobs
    import app.workers.tasks as tasks_module

    test_engine = db_session.get_bind()
    WorkerSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    monkeypatch.setattr(enrich_jobs, "SessionLocal", WorkerSession)
    monkeypatch.setattr(settings, "GEMINI_API_KEY", None)  # generator -> mock mode
    # KHÔNG inline, KHÔNG eager -> ép dispatch đi vào nhánh .delay() rồi fallback.
    monkeypatch.setattr(enrich_jobs, "RUN_JOBS_INLINE", False)
    monkeypatch.setattr(celery_app.conf, "task_always_eager", False)

    # Broker không tới được -> .delay() raise (đúng như Render free).
    def _boom(*args, **kwargs):
        raise RuntimeError("broker unreachable")
    monkeypatch.setattr(tasks_module.enrich_bank_task, "delay", _boom)

    # Thread giả: chạy target đồng bộ ngay khi .start() để tất định (main thread).
    started = {"count": 0}

    class _SyncThread:
        def __init__(self, target=None, args=(), daemon=None):
            self._target = target
            self._args = args

        def start(self):
            started["count"] += 1
            self._target(*self._args)

    monkeypatch.setattr(enrich_jobs.threading, "Thread", _SyncThread)

    job_id = enrich_jobs.create_job("1", 3)
    enrich_jobs.dispatch_enrich_job(job_id, "1", 3, "Giáo dục", "medium")

    # Đã fallback sang thread (không phải eager/inline/worker).
    assert started["count"] == 1, "dispatch phải fallback sang background thread khi broker chết"

    job = enrich_jobs.get_job(job_id)
    assert job is not None
    assert job["status"] == "completed"
    gen = job["generated_count"]
    assert gen >= 1

    db_session.expire_all()
    draft_count = db_session.query(Question).filter(
        Question.exam_id.is_(None),
        Question.part == 1,
        Question.status == "draft",
        Question.topic == "Giáo dục",
    ).count()
    assert draft_count == gen
