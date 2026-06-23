from typing import List, Optional
from sqlalchemy.orm import Session
import datetime

from app.models.exam import Exam
from app.models.question import Question
from app.models.submission import Submission, SubmissionDetail
from app.services.toeic_grader import grade_toeic_submission


def create_submission_and_grade(
    db: Session,
    exam_id: int,
    user_id: int,
    answers: List[dict]
) -> dict:
    # 1. Validate exam exists and is active
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if not exam:
        raise ValueError("Exam not found")
    if not exam.is_active:
        raise ValueError("Exam is retired")

    # 2. Decide grading mode by question type (BEFORE writing any record):
    #    - exams containing Writing/Speaking questions are graded asynchronously
    #      by the Celery worker via Gemini (SPEC-GRADE-003);
    #    - pure multiple-choice TOEIC exams keep synchronous scaled grading (SPEC-SUBMIT-001);
    #    - anything else (non-TOEIC, no essays) is unsupported -> 400.
    has_essay = db.query(Question).filter(
        Question.exam_id == exam_id,
        Question.type.in_(("writing", "speaking"))
    ).first() is not None

    if not has_essay and exam.exam_type.upper() != "TOEIC":
        raise ValueError("Exam type is not TOEIC")

    # 3. Create Submission
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

    # 4. Create SubmissionDetail records
    for ans in answers:
        detail = SubmissionDetail(
            submission_id=sub.id,
            question_id=ans["question_id"],
            candidate_text=ans.get("answer", ""),
            audio_url=ans.get("audio_url"),
        )
        db.add(detail)
    db.commit()
    db.refresh(sub)

    # 5a. ASYNC path (SPEC-GRADE-003): enqueue AI grading and return immediately.
    if has_essay:
        sub.status = "grading"
        db.commit()
        db.refresh(sub)
        # Lazy import keeps the synchronous TOEIC path free of the Celery/Redis
        # stack and avoids import cycles.
        from app.workers.tasks import grade_submission_task
        # Enqueue AI grading for a Celery worker. If no broker/worker is reachable
        # (e.g. Render free tier has no Redis), fall back to grading inline so the
        # result still completes. Either way the response below returns "grading"
        # first; with eager/inline the grade is already written by the time the
        # candidate polls.
        try:
            grade_submission_task.delay(submission_id=sub.id)
        except Exception:
            grade_submission_task.apply(args=[sub.id])
        return {
            "submission_id": sub.id,
            "status": sub.status,  # "grading" — worker fills scores later
            "listening_score": None,
            "reading_score": None,
            "total_score": None,
            "listening_correct": None,
            "reading_correct": None,
        }

    # 5b. SYNC path: grade TOEIC L&R immediately.
    grade = grade_toeic_submission(db, sub.id)
    db.refresh(sub)

    # Extract scores from semantically-named columns (SPEC-GRADE-002)
    listening_correct = grade.feedback_speaking.get("correct_answers", 0) if grade.feedback_speaking else 0
    reading_correct = grade.feedback_writing.get("correct_answers", 0) if grade.feedback_writing else 0

    return {
        "submission_id": sub.id,
        "status": sub.status,
        "listening_score": grade.score_listening,
        "reading_score": grade.score_reading,
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
            "listening_score": sub.grade.score_listening,
            "reading_score": sub.grade.score_reading,
            "score_writing": sub.grade.score_writing,
            "score_speaking": sub.grade.score_speaking,
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
            "exam_type": exam.exam_type,
            "total_score": grade.score_total if grade else None,
            "listening_score": grade.score_listening if grade else None,
            "reading_score": grade.score_reading if grade else None,
            "writing_score": grade.score_writing if grade else None,
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
            "exam_type": sub.exam.exam_type,
            "total_score": grade.score_total if grade else None,
            "listening_score": grade.score_listening if grade else None,
            "reading_score": grade.score_reading if grade else None,
            "writing_score": grade.score_writing if grade else None,
            "status": sub.status,
            "submitted_at": sub.submitted_at
        })
    return result

