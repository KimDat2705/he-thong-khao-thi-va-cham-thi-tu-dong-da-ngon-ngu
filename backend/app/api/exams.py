from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.schemas.exam import (
    ExamGenerateRequest,
    ExamSummary,
    ExamDetail,
    ExamBatchGenerateRequest,
    ExamBatchGenerateResponse,
)
from app.services import exam_admin
from app.services.exam_admin import InsufficientBankError
from app.services.exam_validator import ExamValidationError

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
def get_exam(exam_id: int, include_answers: bool = False, db: Session = Depends(get_db)):
    """
    Retrieve a generated exam organized by part for display.
    By default answers are hidden (candidate view). Pass include_answers=true for
    the teacher/answer-key view.
    TODO: gate include_answers behind teacher auth (auth-api, Milestone 3+).
    """
    detail = exam_admin.get_exam_detail(db, exam_id, include_answers=include_answers)
    if detail is None:
        raise HTTPException(status_code=404, detail="Exam not found")
    return detail


@router.post("/generate-batch", response_model=ExamBatchGenerateResponse)
def generate_exam_batch(payload: ExamBatchGenerateRequest, db: Session = Depends(get_db)):
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

