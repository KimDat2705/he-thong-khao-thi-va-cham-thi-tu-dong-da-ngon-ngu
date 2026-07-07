import re

from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional, List

from app.models.question import Question
from app.models.question_group import QuestionGroup
from app.services.exam_generator import VSTEP_B1_BLUEPRINT
from app.schemas.bank import QuestionUpdate, BankStats, PartStats

# Cổng an toàn thi khi DUYỆT (SPEC-FACTORY-019). Đặt ở bank-approve (D7d) — nơi duy nhất flip
# status='approved', áp cho CẢ câu nhà máy lẫn câu import đối tác.
LIS_PARTS = (7, 8)          # part Nghe: 7 = chọn-tranh L1 (đơn), 8 = điền-từ L2 (nhóm — audio dùng chung)
W1_MIN_BLOCK = 5            # khối Viết phần 1 (part 5) chuẩn = 5 câu viết-lại (đúng format đề 2601)
_W1_NUM_LINE = re.compile(r"(?m)^\s*\d+\.")   # dòng câu đánh số '1.'…'5.' trong reference_answer/content


def _question_has_audio(q: Question) -> bool:
    """Câu Nghe có audio ở CẤP CÂU (part 7 standalone) HOẶC CẤP NHÓM (part 8, audio dùng chung cả bài)."""
    return bool((q.audio_url or "").strip()) or bool((q.group_audio_url or "").strip())


def _w1_block_size(q: Question) -> int:
    """Số câu trong 1 khối W1 = số dòng đánh số ('1.'…) trong reference_answer (fallback content).

    _w1_rows gộp CẢ khối 5 câu vào MỘT Question part 5 (không phải group) — mỗi câu là 1 dòng đánh số
    trong reference_answer. Cùng shape với W1 import đề 2601 thật (parser gộp Section 1 thành 1 Question).
    """
    src = q.reference_answer or q.content or ""
    return len(_W1_NUM_LINE.findall(src))


def _assert_batch_approvable(q_list: List[Question]) -> None:
    """Cổng an toàn thi BẰNG CODE (SPEC-FACTORY-019) áp cho MỌI đường chuyển status→'approved'
    (approve hàng loạt VÀ patch lẻ) — raise ValueError nếu có câu vướng (không dựa cảnh báo trong
    explanation vì bulk-approve không hiển thị explanation). Raise TRƯỚC khi flip status → nguyên khối.
    """
    # (b) Câu Nghe (part 7/8) CHƯA có audio → released mà thiếu audio = thí sinh không nghe được để trả lời.
    no_audio = [q for q in q_list if q.part in LIS_PARTS and not _question_has_audio(q)]
    if no_audio:
        ids_str = ", ".join(str(q.id) for q in no_audio[:20]) + ("…" if len(no_audio) > 20 else "")
        raise ValueError(
            f"Không thể duyệt {len(no_audio)} câu Nghe (part 7/8) CHƯA có audio (id: {ids_str}). "
            "Cần render audio cho bộ Nghe trước khi duyệt."
        )
    # (c) Khối Viết phần 1 (part 5) THIẾU câu (<5) — đề chuẩn cần đủ 5 câu viết-lại (review S57 finding 11).
    short_w1 = [q for q in q_list
                if q.part == 5 and (q.type or "") == "writing" and _w1_block_size(q) < W1_MIN_BLOCK]
    if short_w1:
        ids_str = ", ".join(str(q.id) for q in short_w1[:20]) + ("…" if len(short_w1) > 20 else "")
        raise ValueError(
            f"Không thể duyệt {len(short_w1)} khối Viết phần 1 (part 5) THIẾU câu (dưới {W1_MIN_BLOCK}) "
            f"(id: {ids_str}). Khối W1 chuẩn cần đủ {W1_MIN_BLOCK} câu viết-lại."
        )

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
    # PATCH cũng có thể chuyển status→'approved' (bỏ qua approve_questions) → áp CÙNG cổng an toàn thi
    # (SPEC-FACTORY-019) để không lách được. Chỉ kiểm khi thực sự chuyển sang 'approved'.
    if update_data.get("status") == "approved" and q.status != "approved":
        _assert_batch_approvable([q])
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

    # Cổng an toàn thi (SPEC-FACTORY-019): chặn TRƯỚC khi flip status (nguyên khối — có 1 câu vướng
    # thì KHÔNG duyệt câu nào). Cùng helper với update_bank_question để PATCH không lách được cổng.
    _assert_batch_approvable(q_list)

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
