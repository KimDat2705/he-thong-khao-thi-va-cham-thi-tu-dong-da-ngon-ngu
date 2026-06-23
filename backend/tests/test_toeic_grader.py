import pytest
import json
import os
from sqlalchemy.orm import Session
from app.models.exam import Exam
from app.models.question import Question
from app.models.submission import Submission, SubmissionDetail
from app.models.grade import Grade
from app.services.toeic_generator import generate_toeic_exam
from app.services.toeic_grader import grade_toeic_submission

def test_grade_toeic_submission_success(db_session: Session):
    # 1. Generate an exam first
    exam = generate_toeic_exam(db_session, title="Test Exam for Grader")
    
    # Get the test user
    from app.models.user import User
    user = db_session.query(User).filter(User.username == "testcandidate").first()
    assert user is not None

    # 2. Create a submission
    submission = Submission(exam_id=exam.id, user_id=user.id, status="pending")
    db_session.add(submission)
    db_session.commit()
    db_session.refresh(submission)

    # Fetch all questions in this exam
    questions = db_session.query(Question).filter(Question.exam_id == exam.id).all()
    assert len(questions) > 0

    # Sort questions into listening and reading
    listening_qs = [q for q in questions if q.part in [1, 2, 3, 4]]
    reading_qs = [q for q in questions if q.part in [5, 6, 7]]

    # 3. Simulate answers:
    # Let's make exactly 40 listening questions CORRECT
    # Let's make exactly 30 reading questions CORRECT
    correct_l_count = 40
    correct_r_count = 30

    # We will submit answers
    for i, q in enumerate(listening_qs):
        ans = q.reference_answer if i < correct_l_count else "WRONG"
        db_session.add(SubmissionDetail(
            submission_id=submission.id,
            question_id=q.id,
            candidate_text=ans
        ))

    for i, q in enumerate(reading_qs):
        ans = q.reference_answer if i < correct_r_count else "WRONG"
        db_session.add(SubmissionDetail(
            submission_id=submission.id,
            question_id=q.id,
            candidate_text=ans
        ))

    db_session.commit()

    # 4. Grade the submission
    grade = grade_toeic_submission(db_session, submission_id=submission.id)

    # 5. Assert results
    db_session.refresh(submission)
    assert submission.status == "completed"
    assert grade.submission_id == submission.id

    # Load scoring table for verification
    dir_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    table_path = os.path.join(dir_path, "app", "core", "toeic_scoring_table.json")
    with open(table_path, "r") as f:
        table = json.load(f)

    # Compute expected scaled scores based on proportions since the test might not have exactly 100 questions
    l_idx = int(round(correct_l_count * 100 / len(listening_qs)))
    r_idx = int(round(correct_r_count * 100 / len(reading_qs)))

    expected_l_score = table["listening"][l_idx]
    expected_r_score = table["reading"][r_idx]
    expected_total = expected_l_score + expected_r_score

    assert grade.score_listening == expected_l_score  # Listening score (SPEC-GRADE-002)
    assert grade.score_reading == expected_r_score    # Reading score (SPEC-GRADE-002)
    assert grade.score_total == expected_total

    # Verify breakdown info
    assert grade.feedback_speaking["correct_answers"] == correct_l_count
    assert grade.feedback_writing["correct_answers"] == correct_r_count
