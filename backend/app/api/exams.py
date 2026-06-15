from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.schemas.exam import ExamGenerateRequest, ExamSummary, ExamDetail
from app.services import exam_admin
from app.services.exam_admin import InsufficientBankError

router = APIRouter(prefix="/api/v1/exams", tags=["Exams"])


@router.post("/generate", response_model=ExamSummary)
def generate_exam(payload: ExamGenerateRequest, db: Session = Depends(get_db)):
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
def list_exams(db: Session = Depends(get_db)):
    """List all generated exams (newest first)."""
    return exam_admin.list_exams(db)


@router.get("/{exam_id}", response_model=ExamDetail)
def get_exam(exam_id: int, db: Session = Depends(get_db)):
    """Retrieve a generated exam organized by part for display."""
    detail = exam_admin.get_exam_detail(db, exam_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Exam not found")
    return detail
