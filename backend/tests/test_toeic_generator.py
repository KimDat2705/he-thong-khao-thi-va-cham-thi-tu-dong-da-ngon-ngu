import pytest
from sqlalchemy.orm import Session
from app.models.exam import Exam
from app.models.question import Question
from app.models.question_group import QuestionGroup
from app.services.toeic_generator import generate_toeic_exam

def test_generate_toeic_exam_success(db_session: Session):
    # 1. Generate exam
    title = "Kỳ thi thử TOEIC Đợt 1"
    exam = generate_toeic_exam(db_session, title=title)
    
    # 2. Assert exam details
    assert exam.id is not None
    assert exam.title == title
    assert exam.exam_type == "TOEIC"
    assert exam.language == "EN"
    assert exam.duration_minutes == 120
    assert exam.is_active is True

    # 3. Check standalone questions created
    part1_qs = db_session.query(Question).filter(Question.exam_id == exam.id, Question.part == 1).all()
    part2_qs = db_session.query(Question).filter(Question.exam_id == exam.id, Question.part == 2).all()
    part5_qs = db_session.query(Question).filter(Question.exam_id == exam.id, Question.part == 5).all()

    assert len(part1_qs) == 6
    assert len(part2_qs) == 25
    assert len(part5_qs) == 30

    # 4. Check grouped questions created
    part3_groups = db_session.query(QuestionGroup).filter(QuestionGroup.exam_id == exam.id, QuestionGroup.part == 3).all()
    part4_groups = db_session.query(QuestionGroup).filter(QuestionGroup.exam_id == exam.id, QuestionGroup.part == 4).all()
    part6_groups = db_session.query(QuestionGroup).filter(QuestionGroup.exam_id == exam.id, QuestionGroup.part == 6).all()
    part7_groups = db_session.query(QuestionGroup).filter(QuestionGroup.exam_id == exam.id, QuestionGroup.part == 7).all()

    assert len(part3_groups) == 13
    assert len(part4_groups) == 10
    assert len(part6_groups) == 4
    # Part 7 has diverse group sizes, total count must be exactly 54 questions
    part7_qs_total = sum(len(g.questions) for g in part7_groups)
    assert part7_qs_total == 54

    # Check that each group has correct number of questions
    for g in part3_groups:
        assert len(g.questions) == 3
        for q in g.questions:
            assert q.exam_id == exam.id
            assert q.group_id == g.id
            assert q.part == 3

    for g in part4_groups:
        assert len(g.questions) == 3

    for g in part6_groups:
        assert len(g.questions) == 4

    for g in part7_groups:
        assert len(g.questions) > 0

    # 5. Verify that bank questions (exam_id is None) remain intact
    bank_qs_count = db_session.query(Question).filter(Question.exam_id.is_(None)).count()
    assert bank_qs_count > 0  # Bank should not be cleared or assigned
