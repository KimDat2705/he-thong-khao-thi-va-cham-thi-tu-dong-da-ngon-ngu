from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.core.database import get_db
from app.core.deps import require_role
from app.models.user import User
from app.schemas.bank import QuestionRead, QuestionUpdate, ApproveRequest, ApproveResult, BankStats, QuestionListResponse
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

