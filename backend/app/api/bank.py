from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
import logging

from app.core.database import get_db
from app.core.deps import require_role
from app.models.user import User
from app.schemas.bank import QuestionRead, QuestionUpdate, ApproveRequest, ApproveResult, BankStats, QuestionListResponse, EnrichRequest, EnrichResult, EnrichAsyncResult, EnrichJobStatus
from app.services import bank_admin, enrich_jobs

router = APIRouter(prefix="/api/v1/bank", tags=["Bank Admin"])

@router.get("/questions", response_model=QuestionListResponse)
def list_questions(
    part: Optional[int] = None,
    status: Optional[str] = None,
    topic: Optional[str] = None,
    difficulty: Optional[str] = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    exam_type: Optional[str] = Query("VSTEP_B1"),
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
    exam_type: str = Query("VSTEP_B1"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "teacher"))
):
    """
    Get bank statistics and blueprint sufficiency mapping.
    """
    return bank_admin.compute_bank_stats(db, exam_type=exam_type)


@router.post("/enrich", response_model=EnrichResult)
def enrich_questions(
    payload: EnrichRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "teacher"))
):
    """
    AI sinh câu hỏi nháp VSTEP B1 (đồng bộ) lưu vào ngân hàng câu hỏi.
    Giới hạn 5 câu/lần để tránh timeout HTTP — dùng /enrich-async cho lô lớn.
    """
    if payload.count > 5:
        raise HTTPException(status_code=400, detail="Mỗi lần sinh bằng AI trên Web tối đa là 5 câu để tránh timeout mạng.")
    if payload.part not in enrich_jobs.VALID_PARTS:
        raise HTTPException(status_code=400, detail="Vui lòng chọn cụ thể từng Part (1-11) để sinh trên giao diện.")

    from app.services.b1_question_gen import B1QuestionGenerator
    try:
        generator = B1QuestionGenerator()
        generated_count = enrich_jobs.run_generator(
            generator, db, payload.part, payload.count, payload.topic, payload.difficulty
        )
        return EnrichResult(success=True, generated_count=generated_count)
    except HTTPException:
        raise
    except Exception as e:
        logging.getLogger(__name__).error(f"AI Generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"AI Generation failed: {str(e)}")


@router.post("/enrich-async", response_model=EnrichAsyncResult)
def enrich_questions_async(
    payload: EnrichRequest,
    current_user: User = Depends(require_role("admin", "teacher"))
):
    """
    SPEC-BANK-006: AI sinh câu hỏi B1 BẤT ĐỒNG BỘ — chấp nhận lô lớn (tới 50 câu),
    đẩy công việc chạy nền và trả về ngay job_id để client theo dõi tiến độ qua
    GET /api/v1/bank/tasks/{job_id}, tránh timeout HTTP.
    """
    if payload.part not in enrich_jobs.VALID_PARTS:
        raise HTTPException(status_code=400, detail="Vui lòng chọn cụ thể từng Part (1-11) để sinh trên giao diện.")
    if payload.count < 1 or payload.count > enrich_jobs.MAX_ASYNC_COUNT:
        raise HTTPException(
            status_code=400,
            detail=f"Số lượng sinh bất đồng bộ phải từ 1 đến {enrich_jobs.MAX_ASYNC_COUNT} câu/lần."
        )

    job_id = enrich_jobs.create_job(payload.part, payload.count)
    enrich_jobs.dispatch_enrich_job(job_id, payload.part, payload.count, payload.topic, payload.difficulty)
    job = enrich_jobs.get_job(job_id)
    return EnrichAsyncResult(job_id=job_id, status=job["status"] if job else "pending")


@router.get("/tasks/{task_id}", response_model=EnrichJobStatus)
def get_enrich_task(
    task_id: str,
    current_user: User = Depends(require_role("admin", "teacher"))
):
    """
    SPEC-BANK-006: kiểm tra tiến độ một job sinh câu hỏi bất đồng bộ.
    """
    job = enrich_jobs.get_job(task_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy tác vụ sinh câu hỏi (job_id không tồn tại hoặc đã hết hạn).")
    return EnrichJobStatus(**job)

