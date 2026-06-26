from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional

from app.core.database import get_db
from app.core.deps import require_role, get_current_user_optional
from app.models.user import User
from app.schemas.exam import (
    ExamGenerateRequest,
    ExamSummary,
    ExamDetail,
    ExamBatchGenerateRequest,
    ExamBatchGenerateResponse,
    ExamUpdate,
)
from app.services import exam_admin
from app.services.exam_admin import InsufficientBankError
from app.services.exam_validator import ExamValidationError

router = APIRouter(prefix="/api/v1/exams", tags=["Exams"])


@router.post("/generate", response_model=ExamSummary)
def generate_exam(
    payload: ExamGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "teacher"))
):
    """
    Generate a full TOEIC exam from the approved question bank.
    TODO: Add Authentication & Role-based Authorization check here (Milestone 3+)
    """
    try:
        exam = exam_admin.generate_demo_exam(
            db,
            title=payload.title,
            seed=payload.seed,
            duration_minutes=payload.duration_minutes,
            exam_type=payload.exam_type or "TOEIC",
        )
    except InsufficientBankError as e:
        raise HTTPException(status_code=409, detail=f"Ngân hàng câu hỏi chưa đủ để sinh đề: {e}")

    count = sum(1 for _ in exam.questions)
    return ExamSummary(
        id=exam.id,
        title=exam.title,
        language=exam.language,
        exam_type=exam.exam_type,
        duration_minutes=exam.duration_minutes,
        is_active=exam.is_active,
        created_at=exam.created_at,
        question_count=count,
    )


@router.get("", response_model=List[ExamSummary])
def list_exams(
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """List all generated exams (newest first)."""
    include_inactive = False
    if current_user and current_user.role in ("admin", "teacher"):
        include_inactive = True
    return exam_admin.list_exams(db, include_inactive=include_inactive)


@router.get("/{exam_id}", response_model=ExamDetail)
def get_exam(
    exam_id: int,
    include_answers: bool = False,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """
    Retrieve a generated exam organized by part for display.
    By default answers are hidden (candidate view). Pass include_answers=true for
    the teacher/answer-key view.
    """
    include_inactive = False
    if current_user and current_user.role in ("admin", "teacher"):
        include_inactive = True

    detail = exam_admin.get_exam_detail(
        db, exam_id, include_answers=include_answers, include_inactive=include_inactive
    )
    if detail is None:
        raise HTTPException(status_code=404, detail="Exam not found")

    if include_answers:
        if current_user is None:
            raise HTTPException(
                status_code=401,
                detail="Authentication credentials were not provided or are invalid."
            )
        if current_user.role not in ("admin", "teacher"):
            raise HTTPException(
                status_code=403,
                detail="Not enough permissions to access answer keys."
            )

    return detail


@router.post("/generate-batch", response_model=ExamBatchGenerateResponse)
def generate_exam_batch(
    payload: ExamBatchGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "teacher"))
):
    """
    Generate a batch of TOEIC or custom exams from the approved question bank.
    Includes pairwise overlap check report to verify diversity.
    TODO: Add Authentication & Role-based Authorization check here (Milestone 3+)
    """
    try:
        result = exam_admin.generate_batch_exams(
            db,
            count=payload.count,
            exam_type=payload.exam_type,
            structure=payload.structure,
            base_seed=payload.seed,
            max_overlap_limit=payload.max_overlap_limit
        )
    except InsufficientBankError as e:
        raise HTTPException(status_code=409, detail=f"Ngân hàng câu hỏi chưa đủ để sinh đề: {e}")
    except ExamValidationError as e:
        raise HTTPException(status_code=422, detail=f"Kiểm định đề thi thất bại trong quá trình sinh lô: {e}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    summaries = []
    from app.models.question import Question
    for exam in result["exams"]:
        q_count = db.query(Question).filter(Question.exam_id == exam.id).count()
        summaries.append(ExamSummary(
            id=exam.id,
            title=exam.title,
            language=exam.language,
            exam_type=exam.exam_type,
            duration_minutes=exam.duration_minutes,
            is_active=exam.is_active,
            created_at=exam.created_at,
            question_count=q_count
        ))

    return ExamBatchGenerateResponse(
        exams=summaries,
        overlap_report=result["overlap_report"],
        validation_summary=result["validation_summary"]
    )

@router.patch("/{exam_id}", response_model=ExamDetail)
def update_exam(
    exam_id: int,
    payload: ExamUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "teacher"))
):
    """Update exam metadata. Only admin/teacher allowed."""
    updated = exam_admin.update_exam(
        db,
        exam_id,
        title=payload.title,
        duration_minutes=payload.duration_minutes,
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="Exam not found")
    return updated


@router.post("/{exam_id}/release", response_model=ExamDetail)
def release_exam(
    exam_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "teacher"))
):
    """Release an exam (make active). Only admin/teacher allowed."""
    updated = exam_admin.set_exam_active(db, exam_id, active=True)
    if updated is None:
        raise HTTPException(status_code=404, detail="Exam not found")
    return updated


@router.post("/{exam_id}/retire", response_model=ExamDetail)
def retire_exam(
    exam_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "teacher"))
):
    """Retire an exam (make inactive). Only admin/teacher allowed."""
    updated = exam_admin.set_exam_active(db, exam_id, active=False)
    if updated is None:
        raise HTTPException(status_code=404, detail="Exam not found")
    return updated
