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
from app.models.question import Question
from app.models.question_group import QuestionGroup
from app.services.toeic_generator import generate_toeic_exam

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


@pytest.mark.xfail(
    strict=False,
    reason="GAP SPEC-GEN-001: thuật toán greedy Part 7 với bank toàn nhóm 4 câu "
    "chỉ đạt 52 câu (tổng 198/200) — cần thuật toán tổ hợp cho Part 7",
)
def test_SPEC_GEN_001_blueprint_part_counts(db_session: Session):
    """SPEC-GEN-001: Đề TOEIC sinh ra phải có đúng số câu từng part theo blueprint:
    P1=6, P2=25, P3=39, P4=30, P5=30, P6=16, P7=54 — tổng 200 câu.
    """
    exam = generate_toeic_exam(db_session, title="Đề kiểm tra SPEC-GEN-001")
    questions = exam_questions(db_session, exam.id)

    counts = {}
    for q in questions:
        counts[q.part] = counts.get(q.part, 0) + 1

    for part, target in PART_TARGETS.items():
        assert counts.get(part, 0) == target, (
            f"Part {part}: kỳ vọng {target} câu, thực tế {counts.get(part, 0)}"
        )
    assert len(questions) == TOTAL_TARGET, f"Tổng câu: kỳ vọng 200, thực tế {len(questions)}"


def test_SPEC_MATRIX_002_per_part_difficulty_targets(db_session: Session):
    """SPEC-MATRIX-002 (per-part): Ma trận độ khó từng part phải đúng target
    của blueprint — câu lẻ đếm theo câu, part nhóm đếm theo độ khó của nhóm.
      P1: 2E/3M/1H   P2: 6E/13M/6H   P5: 8E/15M/7H   (theo câu)
      P3: 3E/7M/3H   P4: 2E/5M/3H    P6: 1E/2M/1H    (theo nhóm)
    """
    exam = generate_toeic_exam(db_session, title="Đề kiểm tra SPEC-MATRIX-002 per-part")

    standalone_targets = {
        1: {"easy": 2, "medium": 3, "hard": 1},
        2: {"easy": 6, "medium": 13, "hard": 6},
        5: {"easy": 8, "medium": 15, "hard": 7},
    }
    for part, targets in standalone_targets.items():
        qs = db_session.query(Question).filter(
            Question.exam_id == exam.id, Question.part == part
        ).all()
        for diff, expected in targets.items():
            actual = sum(1 for q in qs if (q.difficulty or "medium") == diff)
            assert actual == expected, (
                f"Part {part} độ khó '{diff}': kỳ vọng {expected}, thực tế {actual}"
            )

    group_targets = {
        3: {"easy": 3, "medium": 7, "hard": 3},
        4: {"easy": 2, "medium": 5, "hard": 3},
        6: {"easy": 1, "medium": 2, "hard": 1},
    }
    for part, targets in group_targets.items():
        groups = exam_groups(db_session, exam.id, part)
        for diff, expected in targets.items():
            actual = sum(1 for g in groups if (g.difficulty or "medium") == diff)
            assert actual == expected, (
                f"Part {part} nhóm độ khó '{diff}': kỳ vọng {expected}, thực tế {actual}"
            )


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
    questions = exam_questions(db_session, exam.id)
    groups = {g.id: g for g in exam_groups(db_session, exam.id)}

    for q in questions:
        if q.part in (3, 4, 6, 7):
            assert q.group_id is not None, f"Câu mồ côi: question {q.id} part {q.part} không có nhóm"
        if q.group_id is not None:
            group = groups.get(q.group_id)
            assert group is not None, f"Question {q.id} trỏ tới nhóm không thuộc đề"
            assert group.exam_id == exam.id, f"Nhóm {group.id} không cùng đề với câu {q.id}"
            assert group.part == q.part, f"Nhóm {group.id} (part {group.part}) lệch part với câu {q.id} (part {q.part})"

    for group in groups.values():
        assert len(group.questions) > 0, f"Nhóm {group.id} trong đề không có câu hỏi nào"


@pytest.mark.xfail(
    strict=False,
    reason="GAP SPEC-GEN-002: generator chưa có bước cân bằng/hoán vị đáp án A/B/C/D",
)
def test_SPEC_GEN_002_answer_balance(db_session: Session):
    """SPEC-GEN-002: Trong các phần dùng 4 lựa chọn, mỗi đáp án đúng (A/B/C/D)
    phải chiếm 20%-28% tổng số câu để tránh mẫu đoán mò.
    """
    exam = generate_toeic_exam(db_session, title="Đề kiểm tra SPEC-GEN-002")
    four_option_qs = [
        q for q in exam_questions(db_session, exam.id)
        if isinstance(q.options, dict) and len(q.options) == 4 and q.reference_answer
    ]
    assert len(four_option_qs) > 0

    counts = {"A": 0, "B": 0, "C": 0, "D": 0}
    for q in four_option_qs:
        answer = q.reference_answer.strip().upper()
        if answer in counts:
            counts[answer] += 1

    total = len(four_option_qs)
    for letter, count in counts.items():
        ratio = count / total
        assert 0.20 <= ratio <= 0.28, (
            f"Đáp án '{letter}' chiếm {ratio:.1%} ({count}/{total}) — ngoài khoảng [20%, 28%]"
        )


@pytest.mark.xfail(
    strict=False,
    reason="GAP SPEC-GEN-003: generator chưa ràng buộc đa dạng chủ đề khi chọn nhóm",
)
def test_SPEC_GEN_003_topic_diversity(db_session: Session):
    """SPEC-GEN-003: Trong mỗi part nhiều nhóm (P3/P4/P6/P7), không chủ đề (topic)
    nào chiếm quá 20% số câu của part đó.
    """
    exam = generate_toeic_exam(db_session, title="Đề kiểm tra SPEC-GEN-003")

    for part in (3, 4, 6, 7):
        groups = exam_groups(db_session, exam.id, part)
        topic_counts = {}
        part_total = 0
        for g in groups:
            topic = g.topic or "(không có chủ đề)"
            n = len(g.questions)
            topic_counts[topic] = topic_counts.get(topic, 0) + n
            part_total += n
        assert part_total > 0

        worst_topic, worst_count = max(topic_counts.items(), key=lambda kv: kv[1])
        ratio = worst_count / part_total
        assert ratio <= 0.20, (
            f"Part {part}: chủ đề '{worst_topic}' chiếm {ratio:.0%} ({worst_count}/{part_total} câu) — vượt 20%"
        )


@pytest.mark.skip(
    reason="SPEC-GEN-004 cần cột questions.source_question_id (thêm qua Alembic) "
    "để truy vết câu nguồn giữa các đề trong lô — schema hiện tại chưa có"
)
def test_SPEC_GEN_004_cross_exam_overlap(db_session: Session):
    """SPEC-GEN-004: Khi sinh lô 100 đề, hai đề bất kỳ không được trùng nhau quá
    40% câu hỏi nguồn (truy vết qua source_question_id).

    Kế hoạch test khi schema sẵn sàng: sinh N đề (N nhỏ trong test, 100 ở script
    kiểm định), so source_question_id từng cặp: |giao| / 200 <= 0.40.
    """
    exams = [generate_toeic_exam(db_session, title=f"Đề lô {i}") for i in range(5)]
    source_sets = []
    for exam in exams:
        qs = exam_questions(db_session, exam.id)
        source_sets.append({q.source_question_id for q in qs})

    for i in range(len(source_sets)):
        for j in range(i + 1, len(source_sets)):
            overlap = len(source_sets[i] & source_sets[j]) / TOTAL_TARGET
            assert overlap <= 0.40, f"Đề {i} và {j} trùng {overlap:.0%} câu nguồn — vượt 40%"


@pytest.mark.skip(
    reason="SPEC-GEN-005: generate_toeic_exam chưa nhận tham số seed "
    "(đang dùng random module-level không kiểm soát được)"
)
def test_SPEC_GEN_005_seeded_generation_reproducible(db_session: Session):
    """SPEC-GEN-005: Hàm sinh đề nhận tham số seed; cùng seed và cùng trạng thái
    bank phải cho ra đề giống hệt nhau (phục vụ debug, audit, kiểm định).
    """
    exam_a = generate_toeic_exam(db_session, title="Đề seed A", seed=42)
    exam_b = generate_toeic_exam(db_session, title="Đề seed B", seed=42)

    sources_a = [q.source_question_id for q in exam_questions(db_session, exam_a.id)]
    sources_b = [q.source_question_id for q in exam_questions(db_session, exam_b.id)]
    assert sources_a == sources_b, "Cùng seed + cùng bank nhưng hai đề khác nhau"


@pytest.mark.xfail(
    strict=False,
    reason="GAP SPEC-GEN-006: generator hiện âm thầm sinh đề thiếu câu khi bank "
    "không đủ, thay vì raise lỗi rõ ràng",
)
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
        with pytest.raises(Exception):
            generate_toeic_exam(db, title="Đề từ bank rỗng — phải raise")
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
