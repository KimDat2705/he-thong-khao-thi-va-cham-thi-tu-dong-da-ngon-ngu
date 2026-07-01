"""
SPEC-GEN-*, SPEC-VALIDATE-001 — Bảo chứng Thuật toán Sinh đề VSTEP B1
(phân hệ Ra đề — trọng tâm hiện tại của dự án).

Blueprint VSTEP B1 (VSTEP_B1_BLUEPRINT):
  Đọc: R1=10, R2=5, R3=1 nhóm x5, R4=1 nhóm x10 (30 câu);
  Viết: W1=1, W2=1 (2 câu); Nghe: L1=5, L2=1 nhóm x10 (15 câu);
  Nói: S1=1, S2=1, S3=1 (3 câu) — tổng 50 câu.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import Base
from app.models.exam import Exam
from app.models.question import Question
from app.models.question_group import QuestionGroup
from app.services.exam_validator import validate_exam, ExamValidationError
from app.services.exam_generator import generate_exam, InsufficientBankError, VSTEP_B1_BLUEPRINT


def generate_b1_exam(db, title, duration_minutes=120, seed=None):
    return generate_exam(db, VSTEP_B1_BLUEPRINT, title, duration_minutes, seed)


def exam_questions(db: Session, exam_id: int):
    return db.query(Question).filter(Question.exam_id == exam_id).all()


def test_SPEC_GEN_005_seeded_generation_reproducible(db_session: Session):
    """SPEC-GEN-005: Hàm sinh đề nhận tham số seed; cùng seed và cùng trạng thái
    bank phải cho ra đề giống hệt nhau (phục vụ debug, audit, kiểm định).
    """
    exam_a = generate_b1_exam(db_session, title="Đề seed A", seed=42)
    exam_b = generate_b1_exam(db_session, title="Đề seed B", seed=42)

    sources_a = [q.source_question_id for q in exam_questions(db_session, exam_a.id)]
    sources_b = [q.source_question_id for q in exam_questions(db_session, exam_b.id)]
    assert sources_a == sources_b, "Cùng seed + cùng bank nhưng hai đề khác nhau"


def test_SPEC_GEN_006_insufficient_bank_raises():
    """SPEC-GEN-006: Nếu ngân hàng không đủ câu/nhóm đạt blueprint, sinh đề phải
    raise lỗi rõ ràng (nêu part và số lượng thiếu) thay vì âm thầm tạo đề thiếu câu.

    Dùng DB rỗng cục bộ (không seed bank) — fixture db_session chung luôn có bank
    nên không tái hiện được kịch bản thiếu.
    """
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    EmptySession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = EmptySession()
    try:
        with pytest.raises(InsufficientBankError):
            generate_b1_exam(db, title="Đề từ bank rỗng — phải raise")
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


def test_SPEC_GEN_007_data_driven_generation(db_session: Session):
    """SPEC-GEN-007: Sinh đề data-driven theo Blueprint structure cấu hình trong DB.
    """
    # Create a mini blueprint structure satisfiable by the conftest.py VSTEP B1 bank
    mini_structure = {
        "exam_type": "VSTEP_B1",
        "language": "EN",
        "parts": {
            "1": {
                "type": "standalone",
                "count": 2
            },
            "3": {
                "type": "grouped",
                "groups": 1,
                "q_per_group": 5
            }
        },
        "balance_answers": False
    }

    # Save the Blueprint to DB
    from app.models.blueprint import Blueprint
    bp = Blueprint(
        exam_type="MINI_B1",
        language="EN",
        structure=mini_structure,
        is_active=True
    )
    db_session.add(bp)
    db_session.commit()
    db_session.refresh(bp)

    # Generate exam using the structure from the saved Blueprint record
    from app.services.exam_generator import generate_exam
    exam = generate_exam(db_session, bp.structure, title="Đề Mini Data-Driven", seed=42)

    # Assertions to prove data-driven works
    assert exam.exam_type == "VSTEP_B1"
    assert exam.language == "EN"

    # Use validate_exam to prove data-driven exam matches blueprint structure completely
    report = validate_exam(db_session, exam.id, bp.structure)
    assert report["is_valid"], f"Data-driven validation failed: {report['errors']}"


def test_generate_exam_robust_against_orphan_clones():
    """Hardening: nếu DB còn ORPHAN clone (Question/QuestionGroup có exam_id trỏ một exam
    đã bị xoá, và id đó bị SQLite TÁI DÙNG cho exam mới), post-check validator KHÔNG được
    đếm nhầm orphan thành câu của đề mới (gây gấp đôi số câu -> ExamValidationError).
    generate_exam phải dọn sạch mọi hàng trỏ exam_id của chính nó TRƯỚC khi clone.

    Tái hiện deterministic: engine in-memory rỗng -> đề đầu tiên luôn nhận id=1; chèn sẵn
    orphan có exam_id=1 -> collision chắc chắn. Không có guard thì generate_exam raise.
    """
    from app.services.exam_generator import generate_exam

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Sess = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = Sess()
    try:
        structure = {
            "exam_type": "TINY",
            "language": "EN",
            "parts": {"1": {"type": "standalone", "count": 2}},
            "balance_answers": False,
        }
        opts = {"A": "a", "B": "b", "C": "c", "D": "d"}
        # Bank: 3 câu approved standalone part 1 (bank_exam_type khớp exam_type của structure)
        for i in range(3):
            db.add(Question(
                exam_id=None, group_id=None, part=1, type="choice",
                content=f"bank q{i}", options=opts, reference_answer="A",
                difficulty="medium", status="approved", exam_type="TINY",
            ))
        # ORPHAN clones có exam_id=1 (id mà đề đầu tiên sẽ nhận) — KHÔNG tồn tại exam id=1
        for i in range(2):
            db.add(Question(
                exam_id=1, group_id=None, part=1, type="choice",
                content=f"orphan {i}", options=opts, reference_answer="A",
                difficulty="medium", status="approved", exam_type="TINY",
            ))
        db.commit()

        # Không guard: validator đếm part 1 = 2 orphan + 2 clone = 4 != 2 -> raise.
        # Có guard: orphan (exam_id=1) bị dọn trước clone -> đúng 2 câu, hợp lệ.
        exam = generate_exam(db, structure, title="orphan-collision", seed=42)
        assert exam.id == 1
        n = db.query(Question).filter(Question.exam_id == exam.id).count()
        assert n == 2, f"đề phải có đúng 2 câu (không gấp đôi từ orphan), got {n}"
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


def test_SPEC_VALIDATE_001_post_check_cleanup(db_session: Session, monkeypatch):
    """SPEC-VALIDATE-001: Nếu validate_exam trả về invalid, hàm generate_exam phải:
    1. Xoá tất cả Question, QuestionGroup, Exam đã tạo (theo thứ tự tránh FK constraint).
    2. Commit việc xoá.
    3. Raise ExamValidationError.
    """
    initial_exams = db_session.query(Exam).count()
    initial_groups = db_session.query(QuestionGroup).count()
    initial_questions = db_session.query(Question).count()

    from app.services import exam_generator

    # Mock validate_exam trả về invalid
    def mock_validate_exam(db, exam_id, structure):
        return {
            "is_valid": False,
            "errors": ["Mock validation failure for testing cleanup"],
            "details": {}
        }

    monkeypatch.setattr(exam_generator.exam_validator, "validate_exam", mock_validate_exam)

    with pytest.raises(ExamValidationError) as excinfo:
        generate_b1_exam(db_session, title="Đề kiểm tra cleanup")

    assert "Mock validation failure for testing cleanup" in str(excinfo.value)

    # Đảm bảo số lượng records trong DB quay lại đúng như cũ
    assert db_session.query(Exam).count() == initial_exams
    assert db_session.query(QuestionGroup).count() == initial_groups
    assert db_session.query(Question).count() == initial_questions


def test_validate_exam_catches_violations(db_session: Session):
    """SPEC-VALIDATE-001: validate_exam phải phát hiện chính xác các vi phạm ràng buộc:
    - GEN-001: Sai số câu/nhóm/part.
    - MATRIX-002: Sai phân phối độ khó per-part.
    - GEN-003: Vượt topic cap.
    - GEN-002: Lệch tỷ lệ đáp án A/B/C/D.
    - ISOLATE-003: Câu mồ côi, nhóm trống, sai exam_id.
    """
    # 1. Tạo Exam giả lập trong DB
    test_exam = Exam(
        title="Đề lỗi phục vụ test validate_exam",
        language="EN",
        exam_type="VSTEP_B1",
        duration_minutes=120,
        is_active=True
    )
    db_session.add(test_exam)
    db_session.commit()
    db_session.refresh(test_exam)

    # 2. Ràng buộc GEN-001: Thiếu/Thừa số câu
    # Giả sử blueprint yêu cầu Part 1 có 6 câu standalone
    mini_blueprint = {
        "exam_type": "VSTEP_B1",
        "language": "EN",
        "parts": {
            "1": {
                "type": "standalone",
                "count": 6,
                "difficulty": {"easy": 2, "medium": 3, "hard": 1}
            }
        },
        "balance_answers": False
    }

    # Thêm chỉ 3 câu vào Part 1 (thiếu 3 câu)
    for i in range(3):
        q = Question(
            exam_id=test_exam.id,
            part=1,
            type="choice",
            content=f"Q{i}",
            options={"A": "1", "B": "2", "C": "3", "D": "4"},
            reference_answer="A",
            difficulty="medium",
            status="approved"
        )
        db_session.add(q)
    db_session.commit()

    report = validate_exam(db_session, test_exam.id, mini_blueprint)
    assert not report["is_valid"]
    assert not report["details"]["GEN_001"]["valid"]
    assert any("Part 1 (standalone): expected 6 questions, got 3" in err for err in report["errors"])

    # Dọn dẹp câu hỏi Part 1 vừa tạo
    db_session.query(Question).filter(Question.exam_id == test_exam.id).delete()
    db_session.commit()

    # 3. Ràng buộc MATRIX-002: Sai phân phối độ khó per-part
    # Blueprint yêu cầu Part 1: 2E/3M/1H. Chúng ta thêm 6 câu toàn Easy.
    for i in range(6):
        q = Question(
            exam_id=test_exam.id,
            part=1,
            type="choice",
            content=f"Q{i}",
            options={"A": "1", "B": "2", "C": "3", "D": "4"},
            reference_answer="A",
            difficulty="easy",
            status="approved"
        )
        db_session.add(q)
    db_session.commit()

    report = validate_exam(db_session, test_exam.id, mini_blueprint)
    assert not report["is_valid"]
    assert not report["details"]["MATRIX_002"]["valid"]
    assert any("difficulty 'medium': expected 3, got 0" in err for err in report["errors"])

    # Dọn dẹp
    db_session.query(Question).filter(Question.exam_id == test_exam.id).delete()
    db_session.commit()

    # 4. Ràng buộc GEN-003: Topic Diversity
    # Giả sử Part 3 (grouped): có 2 groups (3 câu/group). Max group size = 3. Part total = 6 câu.
    # Topic cap = max(0.20, 3/6) = 0.50 (50%).
    # Nếu cả 2 groups cùng chung topic "Tech" -> topic "Tech" chiếm 100% (>50%) -> LỖI.
    part3_blueprint = {
        "exam_type": "VSTEP_B1",
        "language": "EN",
        "parts": {
            "3": {
                "type": "grouped",
                "groups": 2,
                "q_per_group": 3,
                "difficulty": {"easy": 1, "medium": 1, "hard": 0}
            }
        },
        "balance_answers": False
    }

    g1 = QuestionGroup(exam_id=test_exam.id, part=3, topic="Tech", difficulty="easy", status="approved")
    g2 = QuestionGroup(exam_id=test_exam.id, part=3, topic="Tech", difficulty="medium", status="approved")
    db_session.add_all([g1, g2])
    db_session.commit()
    db_session.refresh(g1)
    db_session.refresh(g2)

    for g in [g1, g2]:
        for i in range(3):
            q = Question(
                exam_id=test_exam.id,
                group_id=g.id,
                part=3,
                type="choice",
                content=f"Q_g{g.id}_{i}",
                options={"A": "1", "B": "2", "C": "3", "D": "4"},
                reference_answer="A",
                difficulty="medium",
                status="approved"
            )
            db_session.add(q)
    db_session.commit()

    report = validate_exam(db_session, test_exam.id, part3_blueprint)
    assert not report["is_valid"]
    assert not report["details"]["GEN_003"]["valid"]
    assert any("ratio 100.0% exceeds cap 50.0%" in err for err in report["errors"])

    # Dọn dẹp
    db_session.query(Question).filter(Question.exam_id == test_exam.id).delete()
    db_session.query(QuestionGroup).filter(QuestionGroup.exam_id == test_exam.id).delete()
    db_session.commit()

    # 5. Ràng buộc GEN-002: Answer Balance
    # Blueprint yêu cầu cân bằng đáp án. Có 4 câu 4 lựa chọn. Tỷ lệ kỳ vọng mỗi đáp án: 20%-28%.
    # 4 câu toàn đáp án A -> tỷ lệ A = 100% -> vi phạm.
    balance_blueprint = {
        "exam_type": "VSTEP_B1",
        "language": "EN",
        "parts": {
            "1": {
                "type": "standalone",
                "count": 4,
                "difficulty": {"easy": 1, "medium": 2, "hard": 1}
            }
        },
        "balance_answers": True
    }
    for i in range(4):
        q = Question(
            exam_id=test_exam.id,
            part=1,
            type="choice",
            content=f"Q{i}",
            options={"A": "1", "B": "2", "C": "3", "D": "4"},
            reference_answer="A",
            difficulty="medium",
            status="approved"
        )
        db_session.add(q)
    db_session.commit()

    report = validate_exam(db_session, test_exam.id, balance_blueprint)
    assert not report["is_valid"]
    assert not report["details"]["GEN_002"]["valid"]
    assert any("Correct answer 'A': ratio 100.0% is outside range" in err for err in report["errors"])

    # Dọn dẹp
    db_session.query(Question).filter(Question.exam_id == test_exam.id).delete()
    db_session.commit()

    # 6. Ràng buộc ISOLATE-003: Orphans (câu hỏi mồ côi trong grouped part)
    # Thêm 1 câu thuộc Part 3 nhưng không gán group_id.
    q_orphan = Question(
        exam_id=test_exam.id,
        part=3,
        type="choice",
        content="Orphan",
        options={"A": "1", "B": "2", "C": "3", "D": "4"},
        reference_answer="A",
        difficulty="medium",
        status="approved"
    )
    db_session.add(q_orphan)
    db_session.commit()

    report = validate_exam(db_session, test_exam.id, part3_blueprint)
    assert not report["is_valid"]
    assert not report["details"]["ISOLATE_003"]["valid"]
    assert any("does not have a group" in err for err in report["errors"])

    # Dọn dẹp cuối cùng
    db_session.query(Question).filter(Question.exam_id == test_exam.id).delete()
    db_session.query(QuestionGroup).filter(QuestionGroup.exam_id == test_exam.id).delete()
    db_session.query(Exam).filter(Exam.id == test_exam.id).delete()
    db_session.commit()
