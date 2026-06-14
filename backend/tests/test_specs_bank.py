"""
SPEC-BANK-* — Bảo chứng về Ngân hàng câu hỏi (Giai đoạn 2 phân hệ Ra đề).

Ngân hàng = các bản ghi Question/QuestionGroup có exam_id IS NULL.
Sinh đề chỉ được CLONE từ ngân hàng, không được sửa/phá bản gốc, và (mục tiêu)
chỉ được chọn item đã qua duyệt (status='approved').
"""
import pytest
from sqlalchemy.orm import Session

from app.models.question import Question
from app.models.question_group import QuestionGroup
from app.services.toeic_generator import generate_toeic_exam, InsufficientBankError


def test_SPEC_BANK_001_only_approved_items_generated(db_session: Session):
    """SPEC-BANK-001: Thuật toán sinh đề chỉ được chọn câu hỏi/nhóm có
    status='approved' từ ngân hàng; item draft/retired không bao giờ xuất hiện
    trong đề sinh ra.

    Kịch bản: chuyển TOÀN BỘ câu Part 5 trong bank về status='draft' rồi sinh đề.
    Đề hợp lệ không được chứa câu Part 5 nào (hoặc raise lỗi thiếu bank theo
    SPEC-GEN-006).
    """
    db_session.query(Question).filter(
        Question.exam_id.is_(None), Question.part == 5
    ).update({"status": "draft"}, synchronize_session=False)
    db_session.commit()
    db_session.expire_all()

    try:
        exam = generate_toeic_exam(db_session, title="Đề kiểm tra SPEC-BANK-001")
        p5_in_exam = db_session.query(Question).filter(
            Question.exam_id == exam.id, Question.part == 5
        ).count()
        assert p5_in_exam == 0, (
            f"Đề chứa {p5_in_exam} câu Part 5 được clone từ item chưa duyệt (draft)"
        )
    except InsufficientBankError:
        # Lỗi thiếu bank là hành vi hợp lệ khi toàn bộ Part 5 là draft
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

    generate_toeic_exam(db_session, title="Đề kiểm tra SPEC-BANK-002")
    db_session.expire_all()

    questions_after, groups_after = bank_snapshot()
    assert questions_after == questions_before, "Sinh đề làm thay đổi câu hỏi trong bank"
    assert groups_after == groups_before, "Sinh đề làm thay đổi nhóm trong bank"


def test_SPEC_BANK_003_bank_admin_api(db_session: Session):
    """
    SPEC-BANK-003: API quản trị ngân hàng câu hỏi.
    Kiểm tra các endpoint:
    - GET /api/v1/bank/stats (thống kê & đối chiếu blueprint ban đầu)
    - GET /api/v1/bank/questions (lọc status draft, part, difficulty, topic...)
    - PATCH /api/v1/bank/questions/{id} (sửa câu bank, 404 cho clone/không tồn tại)
    - POST /api/v1/bank/questions/approve (duyệt draft -> approved, kiểm tra propagation)
    """
    from fastapi.testclient import TestClient
    from app.main import app as fastapi_app
    from app.core.database import get_db
    from app.models.question import Question
    from app.models.question_group import QuestionGroup
    from app.models.exam import Exam

    fastapi_app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(fastapi_app)


    try:
        # Step 1: Query stats before any modification (deterministic assertion)
        response = client.get("/api/v1/bank/stats")
        assert response.status_code == 200
        stats = response.json()
        assert "question_counts" in stats
        assert "group_counts" in stats
        assert "blueprint_sufficiency" in stats
        
        # Verify that all 7 parts are sufficient based on conftest approved seeding
        suff_map = {item["part"]: item["is_sufficient"] for item in stats["blueprint_sufficiency"]}
        for part in range(1, 8):
            assert suff_map.get(part) is True, f"Part {part} should be sufficient in initial stats"

        # Step 2: Seed manual draft data to avoid test tautology
        # standalone draft question
        draft_standalone = Question(
            exam_id=None,
            group_id=None,
            part=5,
            type="choice",
            content="Draft Standalone P5 Question",
            status="draft",
            options={"A": "Opt A", "B": "Opt B", "C": "Opt C", "D": "Opt D"},
            reference_answer="A"
        )
        db_session.add(draft_standalone)
        
        # draft group and questions
        draft_group = QuestionGroup(
            exam_id=None,
            part=3,
            topic="Dining",
            difficulty="medium",
            status="draft"
        )
        db_session.add(draft_group)
        db_session.commit()
        db_session.refresh(draft_group)
        
        draft_grouped_q = Question(
            exam_id=None,
            group_id=draft_group.id,
            part=3,
            type="choice",
            content="Draft Grouped P3 Question",
            status="draft",
            options={"A": "Opt A", "B": "Opt B", "C": "Opt C", "D": "Opt D"},
            reference_answer="B"
        )
        db_session.add(draft_grouped_q)
        db_session.commit()
        db_session.refresh(draft_standalone)
        db_session.refresh(draft_grouped_q)

        # Step 3: Test GET /questions with status=draft filtering
        response = client.get("/api/v1/bank/questions?status=draft")
        assert response.status_code == 200
        data = response.json()
        # Should return exactly 2 draft questions we just inserted
        assert data["total"] == 2
        draft_ids = {item["id"] for item in data["items"]}
        assert draft_standalone.id in draft_ids
        assert draft_grouped_q.id in draft_ids

        # Step 4: Test PATCH /questions/{id} (valid bank question)
        response = client.patch(f"/api/v1/bank/questions/{draft_standalone.id}", json={"clo": "CLO_DRAFT_TEST"})
        assert response.status_code == 200
        updated_q = response.json()
        assert updated_q["clo"] == "CLO_DRAFT_TEST"

        # Step 5: Test PATCH on a cloned question (belonging to an exam) should return 404
        exam = Exam(title="Test Exam For A5", language="EN", exam_type="TOEIC", duration_minutes=120)
        db_session.add(exam)
        db_session.commit()
        db_session.refresh(exam)
        
        cloned_q = Question(
            exam_id=exam.id,
            part=1,
            type="choice",
            content="Cloned question content",
            status="approved"
        )
        db_session.add(cloned_q)
        db_session.commit()

        response = client.patch(f"/api/v1/bank/questions/{cloned_q.id}", json={"content": "Modified cloned content"})
        assert response.status_code == 404

        # Step 6: Test PATCH on non-existent question
        response = client.patch("/api/v1/bank/questions/999999", json={"content": "None"})
        assert response.status_code == 404

        # Step 7: Test POST /questions/approve (approving the draft questions)
        # Call approve for the draft standalone and draft grouped questions
        response = client.post("/api/v1/bank/questions/approve", json={"ids": [draft_standalone.id, draft_grouped_q.id]})
        assert response.status_code == 200
        res = response.json()
        assert res["updated"] == 2

        # Verify in DB that status is approved for both questions and the parent group
        db_session.refresh(draft_standalone)
        db_session.refresh(draft_grouped_q)
        db_session.refresh(draft_group)
        
        assert draft_standalone.status == "approved"
        assert draft_grouped_q.status == "approved"
        assert draft_group.status == "approved"

    finally:
        fastapi_app.dependency_overrides.clear()

