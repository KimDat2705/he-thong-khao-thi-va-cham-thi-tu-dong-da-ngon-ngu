from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional, List

from app.models.question import Question
from app.models.question_group import QuestionGroup
from app.services.exam_generator import VSTEP_B1_BLUEPRINT
from app.schemas.bank import QuestionUpdate, BankStats, PartStats

def list_bank_questions(
    db: Session,
    part: Optional[int] = None,
    status: Optional[str] = None,
    topic: Optional[str] = None,
    difficulty: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    exam_type: Optional[str] = "VSTEP_B1"
):
    """
    List bank questions (where exam_id is NULL) with pagination and filters.
    """
    query = db.query(Question).filter(Question.exam_id.is_(None))
    
    if exam_type is not None:
        query = query.filter(Question.exam_type == exam_type)
    
    if part is not None:
        query = query.filter(Question.part == part)
    if status is not None:
        query = query.filter(Question.status == status)
    if topic is not None:
        query = query.filter(Question.topic == topic)
    if difficulty is not None:
        query = query.filter(Question.difficulty == difficulty)
        
    total = query.count()
    items = query.order_by(Question.id).offset(offset).limit(limit).all()
    
    return {"total": total, "items": items}

def update_bank_question(db: Session, id: int, patch: QuestionUpdate) -> Optional[Question]:
    """
    Update a bank question (where exam_id is NULL) using patch fields.
    Returns None if not found or if it is a clone (exam_id is NOT NULL).
    """
    q = db.query(Question).filter(Question.id == id).first()
    if not q or q.exam_id is not None:
        return None
        
    update_data = patch.model_dump(exclude_unset=True)
    for key, val in update_data.items():
        setattr(q, key, val)
        
    db.commit()
    db.refresh(q)
    return q

def approve_questions(db: Session, ids: List[int]) -> int:
    """
    Approves draft questions (where exam_id is NULL).
    Also propagates status="approved" to their parent QuestionGroup records if they belong to any group.
    Returns the number of updated questions.
    """
    # Find draft questions in the bank matching the provided IDs
    q_list = db.query(Question).filter(
        Question.id.in_(ids),
        Question.exam_id.is_(None),
        Question.status != "approved"
    ).all()
    
    updated_count = len(q_list)
    if updated_count > 0:
        group_ids = {q.group_id for q in q_list if q.group_id is not None}
        
        # Update question status to approved
        for q in q_list:
            q.status = "approved"
            
        # Update parent group status to approved
        if group_ids:
            db.query(QuestionGroup).filter(
                QuestionGroup.id.in_(list(group_ids)),
                QuestionGroup.exam_id.is_(None),
                QuestionGroup.status != "approved"
            ).update({"status": "approved"}, synchronize_session=False)
            
        db.commit()
        
    return updated_count

def compute_bank_stats(db: Session, exam_type: str = "VSTEP_B1") -> BankStats:
    """
    Computes statistics of the question bank and evaluates blueprint sufficiency.
    """
    # 1. Count questions by part and status (only bank questions)
    q_stats = db.query(Question.part, Question.status, func.count(Question.id))\
        .filter(Question.exam_id.is_(None), Question.exam_type == exam_type)\
        .group_by(Question.part, Question.status).all()
        
    question_counts = {}
    for part, status, count in q_stats:
        part_str = str(part)
        if part_str not in question_counts:
            question_counts[part_str] = {}
        question_counts[part_str][status] = count
        
    # 2. Count groups by part and status (only bank groups)
    g_stats = db.query(QuestionGroup.part, QuestionGroup.status, func.count(QuestionGroup.id))\
        .filter(QuestionGroup.exam_id.is_(None), QuestionGroup.questions.any(Question.exam_type == exam_type))\
        .group_by(QuestionGroup.part, QuestionGroup.status).all()
        
    group_counts = {}
    for part, status, count in g_stats:
        part_str = str(part)
        if part_str not in group_counts:
            group_counts[part_str] = {}
        group_counts[part_str][status] = count
        
    # 3. Cross-reference with Blueprint
    blueprint_sufficiency = []
    blueprint = VSTEP_B1_BLUEPRINT
    parts_config = blueprint.get("parts", {})
    
    for part_str, part_spec in parts_config.items():
        part = int(part_str)
        part_type = part_spec.get("type")
        
        if part_type == "standalone":
            approved_count = db.query(Question).filter(
                Question.exam_id.is_(None),
                Question.group_id.is_(None),
                Question.part == part,
                Question.status == "approved",
                Question.exam_type == exam_type
            ).count()
            needed_count = part_spec.get("count", 0)
            
        elif part_type == "grouped":
            approved_count = db.query(QuestionGroup).filter(
                QuestionGroup.exam_id.is_(None),
                QuestionGroup.part == part,
                QuestionGroup.status == "approved",
                QuestionGroup.questions.any(Question.exam_type == exam_type)
            ).count()
            needed_count = part_spec.get("groups", 0)
            
        elif part_type == "subset_sum":
            approved_groups = db.query(QuestionGroup).filter(
                QuestionGroup.exam_id.is_(None),
                QuestionGroup.part == part,
                QuestionGroup.status == "approved",
                QuestionGroup.questions.any(Question.exam_type == exam_type)
            ).all()
            approved_count = sum(len(g.questions) for g in approved_groups)
            needed_count = part_spec.get("target_questions", 0)
            
        else:
            approved_count = 0
            needed_count = 0
            
        is_sufficient = approved_count >= needed_count
        
        blueprint_sufficiency.append(PartStats(
            part=part,
            type=part_type,
            approved_count=approved_count,
            needed_count=needed_count,
            is_sufficient=is_sufficient
        ))
        
    # Ensure all parts have at least empty dict in counts for API response consistency
    max_parts = 11 if exam_type == "VSTEP_B1" else 7
    for part in range(1, max_parts + 1):
        part_str = str(part)
        if part_str not in question_counts:
            question_counts[part_str] = {}
        if part_str not in group_counts:
            group_counts[part_str] = {}
            
    return BankStats(
        question_counts=question_counts,
        group_counts=group_counts,
        blueprint_sufficiency=blueprint_sufficiency
    )
