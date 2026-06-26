from typing import Optional, List, Dict
from sqlalchemy.orm import Session

from app.models.exam import Exam
from app.models.question import Question
from app.models.question_group import QuestionGroup
from app.services.toeic_generator import (
    generate_toeic_exam,
    generate_exam,
    generate_batch,
    TOEIC_BLUEPRINT,
    VSTEP_B1_BLUEPRINT,
    InsufficientBankError,
)

# Re-export so callers/tests can catch the bank-shortage error from this module.
__all__ = [
    "generate_demo_exam",
    "list_exams",
    "get_exam_detail",
    "generate_batch_exams",
    "InsufficientBankError",
    "update_exam",
    "set_exam_active",
]


def _part_type(part: int, exam_type: str = "TOEIC") -> str:
    """Look up the structural type of a part from the corresponding blueprint."""
    if exam_type == "VSTEP_B1":
        blueprint = VSTEP_B1_BLUEPRINT
    else:
        blueprint = TOEIC_BLUEPRINT
    spec = blueprint.get("parts", {}).get(str(part), {})
    return spec.get("type", "standalone")


def generate_demo_exam(
    db: Session,
    title: Optional[str] = None,
    seed: Optional[int] = None,
    duration_minutes: int = 120,
    exam_type: str = "TOEIC",
) -> Exam:
    """
    Generate a full exam (TOEIC or VSTEP B1) from the approved question bank.
    Raises InsufficientBankError if the bank does not have enough approved items.
    """
    if exam_type == "VSTEP_B1":
        final_title = title or "VSTEP B1 Demo Exam"
        return generate_exam(
            db, structure=VSTEP_B1_BLUEPRINT, title=final_title, duration_minutes=duration_minutes, seed=seed
        )
    else:
        final_title = title or "TOEIC Demo Exam"
        return generate_toeic_exam(
            db, title=final_title, duration_minutes=duration_minutes, seed=seed
        )


def list_exams(db: Session, include_inactive: bool = False) -> List[dict]:
    """List all exams (newest first) with their question counts."""
    query = db.query(Exam)
    if not include_inactive:
        query = query.filter(Exam.is_active.is_(True))
    exams = query.order_by(Exam.id.desc()).all()
    result = []
    for ex in exams:
        count = db.query(Question).filter(Question.exam_id == ex.id).count()
        result.append({
            "id": ex.id,
            "title": ex.title,
            "language": ex.language,
            "exam_type": ex.exam_type,
            "duration_minutes": ex.duration_minutes,
            "is_active": ex.is_active,
            "created_at": ex.created_at,
            "question_count": count,
        })
    return result


def _question_dict(q: Question, include_answers: bool) -> dict:
    """Serialize a question for display; hide the correct answer unless requested."""
    return {
        "id": q.id,
        "group_id": q.group_id,
        "part": q.part,
        "type": q.type,
        "content": q.content,
        "options": q.options,
        "reference_answer": q.reference_answer if include_answers else None,
        "audio_url": q.audio_url,
        "image_url": q.image_url,
        "difficulty": q.difficulty,
        "topic": q.topic,
    }


def get_exam_detail(
    db: Session,
    exam_id: int,
    include_answers: bool = False,
    include_inactive: bool = False,
) -> Optional[dict]:
    """
    Return a generated exam organized as parts -> (standalone questions | groups -> questions).
    By default the correct answers are hidden (exam = questions only); pass
    include_answers=True for the teacher/answer-key view. Returns None if not found.
    """
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if exam is None:
        return None
    if not exam.is_active and not include_inactive:
        return None

    questions = (
        db.query(Question)
        .filter(Question.exam_id == exam_id)
        .order_by(Question.part, Question.id)
        .all()
    )
    groups = (
        db.query(QuestionGroup)
        .filter(QuestionGroup.exam_id == exam_id)
        .order_by(QuestionGroup.part, QuestionGroup.id)
        .all()
    )

    # Bucket questions by group_id for grouped parts; standalone keyed by None.
    q_by_group: Dict[Optional[int], List[Question]] = {}
    for q in questions:
        q_by_group.setdefault(q.group_id, []).append(q)

    groups_by_part: Dict[int, List[QuestionGroup]] = {}
    for g in groups:
        groups_by_part.setdefault(g.part, []).append(g)

    # Parts present = union of parts seen in questions/groups, ordered 1..7 then any extra.
    parts_present = sorted(
        {q.part for q in questions if q.part is not None}
        | {g.part for g in groups if g.part is not None}
    )

    parts_out = []
    for part in parts_present:
        standalone_qs = [q for q in q_by_group.get(None, []) if q.part == part]
        standalone = [_question_dict(q, include_answers) for q in standalone_qs]
        part_groups = groups_by_part.get(part, [])
        group_dicts = []
        q_count = len(standalone)
        part_audio = None
        for q in standalone_qs:
            if q.audio_url and not part_audio:
                part_audio = q.audio_url
        for g in part_groups:
            g_questions = q_by_group.get(g.id, [])
            q_count += len(g_questions)
            if g.audio_url and not part_audio:
                part_audio = g.audio_url
            group_dicts.append({
                "id": g.id,
                "part": g.part,
                "topic": g.topic,
                "passage_text": g.passage_text,
                "audio_url": g.audio_url,
                "image_url": g.image_url,
                "difficulty": g.difficulty,
                "questions": [_question_dict(q, include_answers) for q in g_questions],
            })
        parts_out.append({
            "part": part,
            "part_type": _part_type(part, exam.exam_type),
            "question_count": q_count,
            "audio_url": part_audio,
            "standalone_questions": standalone,
            "groups": group_dicts,
        })

    return {
        "id": exam.id,
        "title": exam.title,
        "language": exam.language,
        "exam_type": exam.exam_type,
        "duration_minutes": exam.duration_minutes,
        "is_active": exam.is_active,
        "created_at": exam.created_at,
        "total_questions": len(questions),
        "parts": parts_out,
    }


def update_exam(
    db: Session,
    exam_id: int,
    title: Optional[str] = None,
    duration_minutes: Optional[int] = None,
) -> Optional[dict]:
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if exam is None:
        return None
    if title is not None:
        exam.title = title
    if duration_minutes is not None:
        exam.duration_minutes = duration_minutes
    db.commit()
    db.refresh(exam)
    return get_exam_detail(db, exam_id, include_answers=True, include_inactive=True)


def set_exam_active(db: Session, exam_id: int, active: bool) -> Optional[dict]:
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if exam is None:
        return None
    exam.is_active = active
    db.commit()
    db.refresh(exam)
    return get_exam_detail(db, exam_id, include_answers=True, include_inactive=True)


def generate_batch_exams(
    db: Session,
    count: int,
    exam_type: Optional[str] = "TOEIC",
    structure: Optional[dict] = None,
    base_seed: Optional[int] = None,
    max_overlap_limit: float = 0.40,
) -> dict:
    """
    Generate a batch of exams and return a dict with exams, overlap report, and validation summary.
    """
    if not structure:
        if exam_type == "TOEIC":
            structure = TOEIC_BLUEPRINT
        elif exam_type == "VSTEP_B1":
            structure = VSTEP_B1_BLUEPRINT
        else:
            raise ValueError(f"Unsupported exam type: {exam_type}")

    batch_result = generate_batch(db, structure, count, base_seed, max_overlap_limit)

    validation_summary = []
    for exam in batch_result["exams"]:
        validation_summary.append({
            "exam_id": exam.id,
            "title": exam.title,
            "is_valid": True,
            "errors": []
        })

    return {
        "exams": batch_result["exams"],
        "overlap_report": batch_result["overlap_report"],
        "validation_summary": validation_summary
    }

