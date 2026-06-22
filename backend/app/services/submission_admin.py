from typing import List, Optional
from sqlalchemy.orm import Session
import datetime

from app.models.exam import Exam
from app.models.submission import Submission, SubmissionDetail
from app.services.toeic_grader import grade_toeic_submission


def create_submission_and_grade(
    db: Session,
    exam_id: int,
    user_id: int,
    answers: List[dict]
) -> dict:
    # 1. Validate exam exists, is active, and is TOEIC in service layer
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if not exam:
        raise ValueError("Exam not found")
    if not exam.is_active:
        raise ValueError("Exam is retired")
    if exam.exam_type.upper() != "TOEIC":
        raise ValueError("Exam type is not TOEIC")

    # 2. Create Submission
    now = datetime.datetime.utcnow()
    sub = Submission(
        exam_id=exam_id,
        user_id=user_id,
        status="pending",
        started_at=now,
        submitted_at=now
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)

    # 3. Create SubmissionDetail records
    for ans in answers:
        detail = SubmissionDetail(
            submission_id=sub.id,
            question_id=ans["question_id"],
            candidate_text=ans["answer"]
        )
        db.add(detail)
    db.commit()
    db.refresh(sub)

    # 4. Grade the submission
    grade = grade_toeic_submission(db, sub.id)
    db.refresh(sub)

    # 5. Extract scores using convention:
    # listening = score_speaking, reading = score_writing
    listening_correct = grade.feedback_speaking.get("correct_answers", 0) if grade.feedback_speaking else 0
    reading_correct = grade.feedback_writing.get("correct_answers", 0) if grade.feedback_writing else 0

    return {
        "submission_id": sub.id,
        "status": sub.status,
        "listening_score": grade.score_speaking,
        "reading_score": grade.score_writing,
        "total_score": grade.score_total,
        "listening_correct": listening_correct,
        "reading_correct": reading_correct
    }


def get_submission(db: Session, submission_id: int) -> Optional[dict]:
    sub = db.query(Submission).filter(Submission.id == submission_id).first()
    if not sub:
        return None

    grade_info = {}
    if sub.grade:
        grade_info = {
            "score_multiple_choice": sub.grade.score_multiple_choice,
            "listening_score": sub.grade.score_speaking,
            "reading_score": sub.grade.score_writing,
            "total_score": sub.grade.score_total,
            "feedback_speaking": sub.grade.feedback_speaking,
            "feedback_writing": sub.grade.feedback_writing,
        }

    return {
        "id": sub.id,
        "exam_id": sub.exam_id,
        "user_id": sub.user_id,
        "started_at": sub.started_at,
        "submitted_at": sub.submitted_at,
        "status": sub.status,
        "answers": [
            {
                "question_id": d.question_id,
                "candidate_text": d.candidate_text,
                "audio_url": d.audio_url
            }
            for d in sub.details
        ],
        **grade_info
    }


def list_exam_submissions(db: Session, exam_id: int) -> List[dict]:
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if not exam:
        raise ValueError("Exam not found")

    submissions = db.query(Submission).filter(Submission.exam_id == exam_id).order_by(Submission.submitted_at.desc()).all()
    
    result = []
    for sub in submissions:
        grade = sub.grade
        result.append({
            "submission_id": sub.id,
            "user_id": sub.user_id,
            "username": sub.user.username,
            "full_name": sub.user.full_name,
            "total_score": grade.score_total if grade else None,
            "listening_score": grade.score_speaking if grade else None,
            "reading_score": grade.score_writing if grade else None,
            "status": sub.status,
            "submitted_at": sub.submitted_at
        })
    return result


def list_my_submissions(db: Session, user_id: int) -> List[dict]:
    submissions = db.query(Submission).filter(Submission.user_id == user_id).order_by(Submission.submitted_at.desc()).all()
    
    result = []
    for sub in submissions:
        grade = sub.grade
        result.append({
            "submission_id": sub.id,
            "exam_id": sub.exam_id,
            "exam_title": sub.exam.title,
            "total_score": grade.score_total if grade else None,
            "listening_score": grade.score_speaking if grade else None,
            "reading_score": grade.score_writing if grade else None,
            "status": sub.status,
            "submitted_at": sub.submitted_at
        })
    return result

