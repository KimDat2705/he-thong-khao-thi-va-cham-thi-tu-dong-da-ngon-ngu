from typing import List, Optional
from sqlalchemy.orm import Session
import datetime

from app.models.exam import Exam
from app.models.question import Question
from app.models.submission import Submission, SubmissionDetail
from app.models.grade import Grade
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

    # 3. Reuse an in-progress server-side attempt (from POST /start + autosave) if
    #    one exists for this candidate+exam; otherwise create a fresh submission.
    #    Backward compatible: a direct submit without /start finds no attempt and
    #    creates one as before.
    now = datetime.datetime.utcnow()
    sub = (
        db.query(Submission)
        .filter(
            Submission.exam_id == exam_id,
            Submission.user_id == user_id,
            Submission.submitted_at.is_(None),
        )
        .order_by(Submission.id.desc())
        .first()
    )
    if sub is None:
        sub = Submission(
            exam_id=exam_id,
            user_id=user_id,
            status="pending",
            started_at=now,
            submitted_at=now,
        )
        db.add(sub)
        db.commit()
        db.refresh(sub)
    else:
        # Finalize the in-progress attempt; keep its authoritative started_at.
        sub.submitted_at = now
        sub.status = "pending"
        db.commit()
        # The submit payload is authoritative — drop any autosaved details first.
        db.query(SubmissionDetail).filter(
            SubmissionDetail.submission_id == sub.id
        ).delete()
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


def _naive(dt: datetime.datetime) -> datetime.datetime:
    """Drop tzinfo so naive utcnow() arithmetic never raises (SQLite may return
    either naive or aware datetimes for DateTime(timezone=True) columns)."""
    return dt.replace(tzinfo=None) if dt and dt.tzinfo else dt


def start_attempt(db: Session, exam_id: int, user_id: int) -> dict:
    """Server-authoritative exam session (SPEC-SCALE-003 AC /start).

    Resumes an existing in-progress attempt (so a reload keeps the same countdown
    and restores autosaved answers) or starts a new one. remaining_seconds is
    computed from the authoritative started_at — it cannot be reset client-side.
    """
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if not exam:
        raise ValueError("Exam not found")
    if not exam.is_active:
        raise ValueError("Exam is retired")

    sub = (
        db.query(Submission)
        .filter(
            Submission.exam_id == exam_id,
            Submission.user_id == user_id,
            Submission.submitted_at.is_(None),
        )
        .order_by(Submission.id.desc())
        .first()
    )
    now = datetime.datetime.utcnow()
    if sub is None:
        sub = Submission(
            exam_id=exam_id,
            user_id=user_id,
            status="in_progress",
            started_at=now,
            submitted_at=None,
        )
        db.add(sub)
        db.commit()
        db.refresh(sub)

    duration = exam.duration_minutes or 0
    elapsed = (now - _naive(sub.started_at or now)).total_seconds()
    remaining = max(0, int(duration * 60 - elapsed))

    return {
        "submission_id": sub.id,
        "exam_id": exam_id,
        "started_at": sub.started_at,
        "server_time": now,
        "duration_minutes": exam.duration_minutes,
        "remaining_seconds": remaining,
        "answers": [
            {
                "question_id": d.question_id,
                "candidate_text": d.candidate_text,
                "audio_url": d.audio_url,
            }
            for d in sub.details
        ],
    }


def autosave_attempt(
    db: Session, submission_id: int, user_id: int, answers: List[dict]
) -> Optional[dict]:
    """Persist in-progress answers so a disconnect/crash does not lose work.

    Owner-gated; only an attempt that has NOT been submitted can be autosaved.
    Returns None (-> 404 at the API) if the attempt is missing, not owned, or
    already submitted. Upserts SubmissionDetail rows by question_id.
    """
    sub = db.query(Submission).filter(Submission.id == submission_id).first()
    if sub is None or sub.user_id != user_id or sub.submitted_at is not None:
        return None

    existing = {d.question_id: d for d in sub.details}
    saved = 0
    for ans in answers:
        qid = ans["question_id"]
        text = ans.get("answer", "")
        audio = ans.get("audio_url")
        d = existing.get(qid)
        if d is None:
            d = SubmissionDetail(
                submission_id=sub.id,
                question_id=qid,
                candidate_text=text,
                audio_url=audio,
            )
            db.add(d)
            existing[qid] = d
        else:
            d.candidate_text = text
            if audio is not None:
                d.audio_url = audio
        saved += 1
    db.commit()
    return {"submission_id": sub.id, "saved": saved}


def list_active_attempts(db: Session, user_id: int) -> List[dict]:
    """In-progress (started, not-yet-submitted) attempts for a candidate, so the
    exam list can offer "resume". Only attempts on still-active exams are returned
    (a retired exam can't be resumed — /start would 404)."""
    subs = (
        db.query(Submission)
        .filter(Submission.user_id == user_id, Submission.submitted_at.is_(None))
        .order_by(Submission.id.desc())
        .all()
    )
    now = datetime.datetime.utcnow()
    result = []
    for sub in subs:
        exam = sub.exam
        if exam is None or not exam.is_active:
            continue
        duration = exam.duration_minutes or 0
        elapsed = (now - _naive(sub.started_at or now)).total_seconds()
        result.append({
            "submission_id": sub.id,
            "exam_id": sub.exam_id,
            "exam_title": exam.title,
            "started_at": sub.started_at,
            "remaining_seconds": max(0, int(duration * 60 - elapsed)),
        })
    return result


def list_exam_active_attempts(db: Session, exam_id: int) -> List[dict]:
    """In-progress attempts for one exam (teacher live invigilation): who is
    currently taking the exam, when they started, and how much time is left.
    Raises ValueError if the exam does not exist."""
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if not exam:
        raise ValueError("Exam not found")
    subs = (
        db.query(Submission)
        .filter(Submission.exam_id == exam_id, Submission.submitted_at.is_(None))
        .order_by(Submission.started_at.asc())
        .all()
    )
    now = datetime.datetime.utcnow()
    duration = exam.duration_minutes or 0
    result = []
    for sub in subs:
        elapsed = (now - _naive(sub.started_at or now)).total_seconds()
        result.append({
            "submission_id": sub.id,
            "user_id": sub.user_id,
            "username": sub.user.username,
            "full_name": sub.user.full_name,
            "started_at": sub.started_at,
            "remaining_seconds": max(0, int(duration * 60 - elapsed)),
        })
    return result


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


def override_grade(
    db: Session,
    submission_id: int,
    score_writing: Optional[float] = None,
    score_speaking: Optional[float] = None,
    teacher_note: Optional[str] = None,
) -> Optional[dict]:
    """
    Teacher/admin moderation of AI grades (human-in-the-loop): adjust the essay
    Writing/Speaking scores and/or attach a note. The total is recomputed from all
    components. Returns the updated submission detail, or None if the submission /
    its grade does not exist.
    """
    grade = (
        db.query(Grade)
        .filter(Grade.submission_id == submission_id)
        .first()
    )
    if grade is None:
        return None

    if score_writing is not None:
        grade.score_writing = float(score_writing)
    if score_speaking is not None:
        grade.score_speaking = float(score_speaking)
    # Recompute the total from every component (MCQ + Writing + Speaking).
    grade.score_total = (
        (grade.score_multiple_choice or 0.0)
        + (grade.score_writing or 0.0)
        + (grade.score_speaking or 0.0)
    )
    if teacher_note is not None:
        # Store the teacher note in the writing-feedback JSON under a reserved key
        # (reassign a new dict so SQLAlchemy persists the JSON change).
        fw = dict(grade.feedback_writing) if isinstance(grade.feedback_writing, dict) else {}
        fw["teacher_note"] = teacher_note
        grade.feedback_writing = fw

    db.commit()
    return get_submission(db, submission_id)


def list_exam_submissions(db: Session, exam_id: int) -> List[dict]:
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if not exam:
        raise ValueError("Exam not found")

    submissions = (
        db.query(Submission)
        .filter(Submission.exam_id == exam_id, Submission.submitted_at.isnot(None))
        .order_by(Submission.submitted_at.desc())
        .all()
    )
    
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
    submissions = (
        db.query(Submission)
        .filter(Submission.user_id == user_id, Submission.submitted_at.isnot(None))
        .order_by(Submission.submitted_at.desc())
        .all()
    )
    
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


def get_exam_analytics(db: Session, exam_id: int) -> dict:
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if not exam:
        raise ValueError("Exam not found")

    submissions = (
        db.query(Submission)
        .filter(Submission.exam_id == exam_id, Submission.submitted_at.isnot(None))
        .all()
    )
    submission_count = len(submissions)

    scores = [
        sub.grade.score_total
        for sub in submissions
        if sub.grade is not None and sub.grade.score_total is not None
    ]
    if scores:
        score_summary = {
            "mean": sum(scores) / len(scores),
            "min": min(scores),
            "max": max(scores)
        }
    else:
        score_summary = {
            "mean": None,
            "min": None,
            "max": None
        }

    questions = (
        db.query(Question)
        .filter(Question.exam_id == exam_id)
        .order_by(Question.id.asc())
        .all()
    )

    sub_ids = [sub.id for sub in submissions]
    details = (
        db.query(SubmissionDetail)
        .filter(SubmissionDetail.submission_id.in_(sub_ids))
        .all()
    ) if sub_ids else []

    details_by_question = {}
    for d in details:
        details_by_question.setdefault(d.question_id, []).append(d)

    items = []
    for q in questions:
        q_details = details_by_question.get(q.id, [])

        # answered_count chỉ đếm câu có candidate_text KHÔNG rỗng
        answered_details = [d for d in q_details if d.candidate_text is not None and d.candidate_text != ""]
        answered_count = len(answered_details)

        correct_count = 0
        correct_rate = None
        option_distribution = None
        avg_score = None

        if q.type == "choice":
            for d in answered_details:
                if d.candidate_text == q.reference_answer:
                    correct_count += 1
            if answered_count > 0:
                correct_rate = correct_count / answered_count
            else:
                correct_rate = None

            option_distribution = {}
            if q.options:
                for opt in q.options.keys():
                    option_distribution[opt] = 0
            for d in answered_details:
                ans = d.candidate_text
                if ans in option_distribution:
                    option_distribution[ans] += 1
        elif q.type in ("writing", "speaking"):
            # calculate average score of writing/speaking
            q_scores = []
            for sub in submissions:
                grade = sub.grade
                if not grade:
                    continue
                if q.type == "writing":
                    fw = grade.feedback_writing
                    if isinstance(fw, dict):
                        q_fb = fw.get(f"question_{q.id}")
                        if isinstance(q_fb, dict):
                            score = q_fb.get("score")
                            if score is not None:
                                try:
                                    q_scores.append(float(score))
                                except (ValueError, TypeError):
                                    pass
                elif q.type == "speaking":
                    fs = grade.feedback_speaking
                    if isinstance(fs, dict):
                        q_fb = fs.get(f"question_{q.id}")
                        if isinstance(q_fb, dict):
                            score = q_fb.get("score")
                            if score is not None:
                                try:
                                    q_scores.append(float(score))
                                except (ValueError, TypeError):
                                    pass
            if q_scores:
                avg_score = sum(q_scores) / len(q_scores)

        content_summary = q.content[:80] if q.content else ""

        items.append({
            "question_id": q.id,
            "part": q.part,
            "type": q.type,
            "content": content_summary,
            "answered_count": answered_count,
            "correct_count": correct_count,
            "correct_rate": correct_rate,
            "option_distribution": option_distribution,
            "avg_score": avg_score
        })

    return {
        "submission_count": submission_count,
        "score_summary": score_summary,
        "items": items
    }


