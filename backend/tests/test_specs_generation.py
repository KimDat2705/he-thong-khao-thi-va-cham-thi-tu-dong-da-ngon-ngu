"""
SPEC-GEN-*, SPEC-MATRIX-002, SPEC-ISOLATE-003 — Bảo chứng Thuật toán Sinh đề
(Giai đoạn 3 phân hệ Ra đề — trọng tâm hiện tại của dự án).

Blueprint TOEIC chuẩn (ke_hoach_trien_khai_toeic_b1.md):
  P1=6, P2=25, P3=39 (13 nhóm x3), P4=30 (10 nhóm x3), P5=30,
  P6=16 (4 nhóm x4), P7=54 — tổng 200 câu, ma trận độ khó 25/50/25.
"""
import random

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import Base
from app.models.exam import Exam
from app.models.question import Question
from app.models.question_group import QuestionGroup
from app.services.exam_validator import validate_exam, ExamValidationError
from app.services.toeic_generator import generate_toeic_exam, InsufficientBankError, TOEIC_BLUEPRINT

# Blueprint chuẩn dùng chung cho các assertion
PART_TARGETS = {1: 6, 2: 25, 3: 39, 4: 30, 5: 30, 6: 16, 7: 54}
TOTAL_TARGET = 200


def exam_questions(db: Session, exam_id: int):
    return db.query(Question).filter(Question.exam_id == exam_id).all()


def exam_groups(db: Session, exam_id: int, part: int = None):
    q = db.query(QuestionGroup).filter(QuestionGroup.exam_id == exam_id)
    if part is not None:
        q = q.filter(QuestionGroup.part == part)
    return q.all()


def test_SPEC_GEN_001_blueprint_part_counts(db_session: Session):
    """SPEC-GEN-001: Đề TOEIC sinh ra phải có đúng số câu từng part theo blueprint:
    P1=6, P2=25, P3=39, P4=30, P5=30, P6=16, P7=54 — tổng 200 câu.
    """
    exam = generate_toeic_exam(db_session, title="Đề kiểm tra SPEC-GEN-001")
    report = validate_exam(db_session, exam.id, TOEIC_BLUEPRINT)
    assert report["details"]["GEN_001"]["valid"], f"GEN-001 validation failed: {report['details']['GEN_001']['errors']}"
    assert report["is_valid"], f"Exam validation failed: {report['errors']}"


def test_SPEC_MATRIX_002_per_part_difficulty_targets(db_session: Session):
    """SPEC-MATRIX-002 (per-part): Ma trận độ khó từng part phải đúng target
    của blueprint — câu lẻ đếm theo câu, part nhóm đếm theo độ khó của nhóm.
      P1: 2E/3M/1H   P2: 6E/13M/6H   P5: 8E/15M/7H   (theo câu)
      P3: 3E/7M/3H   P4: 2E/5M/3H    P6: 1E/2M/1H    (theo nhóm)
    """
    exam = generate_toeic_exam(db_session, title="Đề kiểm tra SPEC-MATRIX-002 per-part")
    report = validate_exam(db_session, exam.id, TOEIC_BLUEPRINT)
    assert report["details"]["MATRIX_002"]["valid"], f"MATRIX-002 validation failed: {report['details']['MATRIX_002']['errors']}"


@pytest.mark.xfail(
    strict=False,
    reason="GAP SPEC-MATRIX-002 (toàn đề): Part 7 chọn nhóm ngẫu nhiên không ràng "
    "buộc độ khó nên tỷ lệ 25/50/25 toàn đề không được đảm bảo",
)
def test_SPEC_MATRIX_002_whole_exam_ratio(db_session: Session):
    """SPEC-MATRIX-002 (toàn đề): Tổng độ khó toàn đề phải đạt Easy [45,55] /
    Medium [95,105] / Hard [45,55] — quy theo tổng câu thực tế nếu khác 200.

    Bảo chứng phải đúng với MỌI lần sinh đề, không chỉ một lần may mắn — test
    sinh đề với nhiều seed cố định (tái lập được) và yêu cầu tất cả đều đạt.
    """
    bounds = {"easy": (45, 55), "medium": (95, 105), "hard": (45, 55)}
    violations = []

    for seed in (1, 2, 3, 4, 5):
        random.seed(seed)  # seed cố định: tái lập được, phủ nhiều kết cục shuffle Part 7
        exam = generate_toeic_exam(db_session, title=f"Đề SPEC-MATRIX-002 toàn đề (seed {seed})")
        questions = exam_questions(db_session, exam.id)
        total = len(questions)

        counts = {"easy": 0, "medium": 0, "hard": 0}
        for q in questions:
            counts[(q.difficulty or "medium")] += 1

        for diff, (low, high) in bounds.items():
            scaled_low = low * total / TOTAL_TARGET
            scaled_high = high * total / TOTAL_TARGET
            if not (scaled_low <= counts[diff] <= scaled_high):
                violations.append(
                    f"seed {seed}: độ khó '{diff}' = {counts[diff]} câu, ngoài "
                    f"[{scaled_low:.1f}, {scaled_high:.1f}] (tổng {total} câu)"
                )

    assert not violations, "Ma trận toàn đề vi phạm:\n" + "\n".join(violations)


def test_SPEC_ISOLATE_003_group_isolation_no_orphans(db_session: Session):
    """SPEC-ISOLATE-003: Câu hỏi thuộc nhóm phải đi nguyên nhóm vào đề — mọi câu
    có group_id tham chiếu nhóm tồn tại, cùng đề, cùng part; mọi nhóm trong đề có
    đủ câu hỏi; câu Part 3/4/6/7 bắt buộc thuộc nhóm (không câu lẻ mồ côi).
    """
    exam = generate_toeic_exam(db_session, title="Đề kiểm tra SPEC-ISOLATE-003")
    report = validate_exam(db_session, exam.id, TOEIC_BLUEPRINT)
    assert report["details"]["ISOLATE_003"]["valid"], f"ISOLATE-003 validation failed: {report['details']['ISOLATE_003']['errors']}"


def test_SPEC_GEN_002_answer_balance(db_session: Session):
    """SPEC-GEN-002: Trong các phần dùng 4 lựa chọn, mỗi đáp án đúng (A/B/C/D)
    phải chiếm 20%-28% tổng số câu để tránh mẫu đoán mò.
    """
    exam = generate_toeic_exam(db_session, title="Đề kiểm tra SPEC-GEN-002")
    report = validate_exam(db_session, exam.id, TOEIC_BLUEPRINT)
    assert report["details"]["GEN_002"]["valid"], f"GEN-002 validation failed: {report['details']['GEN_002']['errors']}"


def test_SPEC_GEN_003_topic_diversity(db_session: Session):
    """SPEC-GEN-003: Trong mỗi part nhiều nhóm (P3/P4/P6/P7), không chủ đề (topic)
    nào chiếm quá cap thích ứng số câu của part đó.
    """
    for seed in (1, 2, 3, 4, 5):
        exam = generate_toeic_exam(db_session, title=f"Đề kiểm tra SPEC-GEN-003 (seed {seed})", seed=seed)
        report = validate_exam(db_session, exam.id, TOEIC_BLUEPRINT)
        assert report["details"]["GEN_003"]["valid"], f"Seed {seed} GEN-003 validation failed: {report['details']['GEN_003']['errors']}"


def test_SPEC_GEN_004_cross_exam_overlap():
    """SPEC-GEN-004: Khi sinh lô đề, hai đề bất kỳ không được trùng nhau quá 40% câu nguồn.
    Dùng DB rỗng cục bộ để seed bank dư riêng biệt nhằm đảm bảo đa dạng hóa đề thi và không đụng conftest.
    """
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSession()
    try:
        # Seed surplus question bank
        # Part 1: needs 6. Seed 30.
        for i in range(30):
            diff = "easy" if i < 10 else ("medium" if i < 20 else "hard")
            db.add(Question(
                part=1, type="choice", content=f"P1Q_{i}", reference_answer="A", difficulty=diff,
                options={"A": "1", "B": "2", "C": "3", "D": "4"}, status="approved"
            ))

        # Part 2: needs 25. Seed 100.
        for i in range(100):
            diff = "easy" if i < 30 else ("medium" if i < 70 else "hard")
            db.add(Question(
                part=2, type="choice", content=f"P2Q_{i}", reference_answer="B", difficulty=diff,
                options={"A": "1", "B": "2", "C": "3", "D": "4"}, status="approved"
            ))

        # Part 3: needs 13 groups of 3. Seed 50 groups.
        for i in range(50):
            diff = "easy" if i < 15 else ("medium" if i < 35 else "hard")
            group = QuestionGroup(part=3, topic=f"P3Topic_{i}", difficulty=diff, status="approved")
            db.add(group)
            db.commit()
            db.refresh(group)
            for j in range(3):
                db.add(Question(
                    group_id=group.id, part=3, type="choice", content=f"P3G{i}Q{j}", reference_answer="C", difficulty=diff,
                    options={"A": "1", "B": "2", "C": "3", "D": "4"}, status="approved"
                ))

        # Part 4: needs 10 groups of 3. Seed 40 groups.
        for i in range(40):
            diff = "easy" if i < 12 else ("medium" if i < 28 else "hard")
            group = QuestionGroup(part=4, topic=f"P4Topic_{i}", difficulty=diff, status="approved")
            db.add(group)
            db.commit()
            db.refresh(group)
            for j in range(3):
                db.add(Question(
                    group_id=group.id, part=4, type="choice", content=f"P4G{i}Q{j}", reference_answer="D", difficulty=diff,
                    options={"A": "1", "B": "2", "C": "3", "D": "4"}, status="approved"
                ))

        # Part 5: needs 30. Seed 120.
        for i in range(120):
            diff = "easy" if i < 35 else ("medium" if i < 85 else "hard")
            db.add(Question(
                part=5, type="choice", content=f"P5Q_{i}", reference_answer="A", difficulty=diff,
                options={"A": "1", "B": "2", "C": "3", "D": "4"}, status="approved"
            ))

        # Part 6: needs 4 groups of 4. Seed 20 groups.
        for i in range(20):
            diff = "easy" if i < 5 else ("medium" if i < 15 else "hard")
            group = QuestionGroup(part=6, topic=f"P6Topic_{i}", difficulty=diff, status="approved")
            db.add(group)
            db.commit()
            db.refresh(group)
            for j in range(4):
                db.add(Question(
                    group_id=group.id, part=6, type="choice", content=f"P6G{i}Q{j}", reference_answer="B", difficulty=diff,
                    options={"A": "1", "B": "2", "C": "3", "D": "4"}, status="approved"
                ))

        # Part 7: needs 54 questions. Seed 50 groups of sizes 2, 3, 4, 5, 6 (10 groups each).
        # Total: 10*2 + 10*3 + 10*4 + 10*5 + 10*6 = 20 + 30 + 40 + 50 + 60 = 200 questions in bank.
        p7_idx = 0
        for size in (2, 3, 4, 5, 6):
            for i in range(10):
                diff = "easy" if p7_idx % 3 == 0 else ("medium" if p7_idx % 3 == 1 else "hard")
                group = QuestionGroup(part=7, topic=f"P7Topic_sz{size}_{i}", difficulty=diff, status="approved")
                db.add(group)
                db.commit()
                db.refresh(group)
                for j in range(size):
                    db.add(Question(
                        group_id=group.id, part=7, type="choice", content=f"P7G{p7_idx}Q{j}", reference_answer="C", difficulty=diff,
                        options={"A": "1", "B": "2", "C": "3", "D": "4"}, status="approved"
                    ))
                p7_idx += 1

        db.commit()

        # Call generate_batch with different base_seeds to verify enforcement works
        from app.services.toeic_generator import generate_batch, TOEIC_BLUEPRINT
        
        for base_seed in [5, 8, 21, 23]:
            result = generate_batch(db, TOEIC_BLUEPRINT, count=5, base_seed=base_seed)
            exams = result["exams"]
            report = result["overlap_report"]
            
            # Verify details
            assert len(exams) == 5
            for exam in exams:
                qs = db.query(Question).filter(Question.exam_id == exam.id).all()
                assert len(qs) == 200
                assert all(q.source_question_id is not None for q in qs)
                
            print(f"Seed {base_seed} -> Max Overlap: {report['max_overlap']:.2%} | Resamples: {report['resample_count']}")
            assert report["max_overlap"] > 0.0, f"Seed {base_seed}: Overlap should be non-trivial"
            assert report["max_overlap"] <= 0.40, f"Seed {base_seed}: Max overlap {report['max_overlap']:.2%} exceeds 40%"
            
            # Clean up generated exams for this seed loop
            for exam in exams:
                db.query(Question).filter(Question.exam_id == exam.id).delete(synchronize_session=False)
                db.query(QuestionGroup).filter(QuestionGroup.exam_id == exam.id).delete(synchronize_session=False)
                db.query(Exam).filter(Exam.id == exam.id).delete(synchronize_session=False)
            db.commit()
            db.expunge_all()

    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


def test_SPEC_GEN_005_seeded_generation_reproducible(db_session: Session):
    """SPEC-GEN-005: Hàm sinh đề nhận tham số seed; cùng seed và cùng trạng thái
    bank phải cho ra đề giống hệt nhau (phục vụ debug, audit, kiểm định).
    """
    exam_a = generate_toeic_exam(db_session, title="Đề seed A", seed=42)
    exam_b = generate_toeic_exam(db_session, title="Đề seed B", seed=42)

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
            generate_toeic_exam(db, title="Đề từ bank rỗng — phải raise")
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


def test_SPEC_GEN_007_data_driven_generation(db_session: Session):
    """SPEC-GEN-007: Sinh đề data-driven theo Blueprint structure cấu hình trong DB.
    """
    # Create a mini blueprint structure that is satisfiable by the conftest.py bank
    mini_structure = {
        "exam_type": "MINI_TOEIC",
        "language": "EN",
        "parts": {
            "1": {
                "type": "standalone",
                "count": 2,
                "difficulty": {"easy": 1, "medium": 1, "hard": 0}
            },
            "3": {
                "type": "grouped",
                "groups": 2,
                "q_per_group": 3,
                "difficulty": {"easy": 1, "medium": 1, "hard": 0}
            },
            "7": {
                "type": "subset_sum",
                "target_questions": 10,
                "difficulty": {"easy": 2, "medium": 0, "hard": 0}
            }
        },
        "balance_answers": True
    }
    
    # Save the Blueprint to DB
    from app.models.blueprint import Blueprint
    bp = Blueprint(
        exam_type="MINI_TOEIC",
        language="EN",
        structure=mini_structure,
        is_active=True
    )
    db_session.add(bp)
    db_session.commit()
    db_session.refresh(bp)
    
    # Generate exam using the structure from the saved Blueprint record
    from app.services.toeic_generator import generate_exam
    exam = generate_exam(db_session, bp.structure, title="Đề Mini Data-Driven", seed=42)
    
    # Assertions to prove data-driven works
    assert exam.exam_type == "MINI_TOEIC"
    assert exam.language == "EN"
    
    # Use validate_exam to prove data-driven exam matches blueprint structure completely
    report = validate_exam(db_session, exam.id, bp.structure)
    assert report["is_valid"], f"Data-driven validation failed: {report['errors']}"


def test_SPEC_VALIDATE_001_post_check_cleanup(db_session: Session, monkeypatch):
    """SPEC-VALIDATE-001: Nếu validate_exam trả về invalid, hàm generate_exam phải:
    1. Xoá tất cả Question, QuestionGroup, Exam đã tạo (theo thứ tự tránh FK constraint).
    2. Commit việc xoá.
    3. Raise ExamValidationError.
    """
    initial_exams = db_session.query(Exam).count()
    initial_groups = db_session.query(QuestionGroup).count()
    initial_questions = db_session.query(Question).count()

    from app.services import toeic_generator

    # Mock validate_exam trả về invalid
    def mock_validate_exam(db, exam_id, structure):
        return {
            "is_valid": False,
            "errors": ["Mock validation failure for testing cleanup"],
            "details": {}
        }

    monkeypatch.setattr(toeic_generator.exam_validator, "validate_exam", mock_validate_exam)

    with pytest.raises(ExamValidationError) as excinfo:
        generate_toeic_exam(db_session, title="Đề kiểm tra cleanup")

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
        exam_type="TOEIC",
        duration_minutes=120,
        is_active=True
    )
    db_session.add(test_exam)
    db_session.commit()
    db_session.refresh(test_exam)
    
    # 2. Ràng buộc GEN-001: Thiếu/Thừa số câu
    # Giả sử blueprint yêu cầu Part 1 có 6 câu standalone
    mini_blueprint = {
        "exam_type": "TOEIC",
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
        "exam_type": "TOEIC",
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
        "exam_type": "TOEIC",
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

