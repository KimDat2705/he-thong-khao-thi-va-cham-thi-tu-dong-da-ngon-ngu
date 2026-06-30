from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
import logging

from app.core.database import get_db
from app.core.deps import require_role
from app.models.user import User
from app.schemas.bank import QuestionRead, QuestionUpdate, ApproveRequest, ApproveResult, BankStats, QuestionListResponse, EnrichRequest, EnrichResult
from app.services import bank_admin

router = APIRouter(prefix="/api/v1/bank", tags=["Bank Admin"])

@router.get("/questions", response_model=QuestionListResponse)
def list_questions(
    part: Optional[int] = None,
    status: Optional[str] = None,
    topic: Optional[str] = None,
    difficulty: Optional[str] = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    exam_type: Optional[str] = Query("TOEIC"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "teacher"))
):
    """
    Retrieve list of questions in the bank.    """
    return bank_admin.list_bank_questions(
        db, part=part, status=status, topic=topic, difficulty=difficulty, limit=limit, offset=offset, exam_type=exam_type
    )

@router.patch("/questions/{id}", response_model=QuestionRead)
def update_question(
    id: int,
    patch: QuestionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "teacher"))
):
    """
    Update details of a bank question.
    Only allows modifying bank items (exam_id IS NULL).    """
    updated = bank_admin.update_bank_question(db, id, patch)
    if updated is None:
        raise HTTPException(status_code=404, detail="Question not found in the bank")
    return updated

@router.post("/questions/approve", response_model=ApproveResult)
def approve_questions(
    payload: ApproveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "teacher"))
):
    """
    Approve draft questions in the bank.
    Propagates the approval status to their parent groups.    """
    updated_count = bank_admin.approve_questions(db, payload.ids)
    return ApproveResult(updated=updated_count)

@router.get("/stats", response_model=BankStats)
def get_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "teacher"))
):
    """
    Get bank statistics and TOEIC blueprint sufficiency mapping.    """
    return bank_admin.compute_bank_stats(db)


@router.post("/enrich", response_model=EnrichResult)
def enrich_questions(
    payload: EnrichRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "teacher"))
):
    """
    AI sinh câu hỏi nháp VSTEP B1 lưu vào ngân hàng câu hỏi.
    """
    from app.services.b1_question_gen import B1QuestionGenerator
    generator = B1QuestionGenerator()
    try:
        generated_count = 0
        part = payload.part
        count = payload.count
        topic = payload.topic

        if count > 5:
            raise HTTPException(status_code=400, detail="Mỗi lần sinh bằng AI trên Web tối đa là 5 câu để tránh timeout mạng.")

        if part == "1":
            generated_count = generator.generate_r1_questions(db, count, topic)
        elif part == "2":
            generated_count = generator.generate_r2_questions(db, count, topic)
        elif part == "3":
            generated_count = generator.generate_r3_groups(db, count, topic)
        elif part == "4":
            generated_count = generator.generate_r4_groups(db, count, topic)
        elif part == "5":
            generated_count = generator.generate_writing_questions(db, count, 5, topic)
        elif part == "6":
            generated_count = generator.generate_writing_questions(db, count, 6, topic)
        elif part == "7":
            generated_count = generator.generate_l1_questions(db, count, topic)
        elif part == "8":
            generated_count = generator.generate_l2_groups(db, count, topic)
        elif part == "9":
            generated_count = generator.generate_speaking_questions(db, count, 9, topic)
        elif part == "10":
            generated_count = generator.generate_speaking_questions(db, count, 10, topic)
        elif part == "11":
            generated_count = generator.generate_speaking_questions(db, count, 11, topic)
        else:
            raise HTTPException(status_code=400, detail="Vui lòng chọn cụ thể từng Part (1-11) để sinh trên giao diện.")

        return EnrichResult(success=True, generated_count=generated_count)
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"AI Generation failed: {e}")
        # Nếu exception là HTTPException thì ném lại
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"AI Generation failed: {str(e)}")

