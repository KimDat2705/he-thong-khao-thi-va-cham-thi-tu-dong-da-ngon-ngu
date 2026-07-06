"""API Nhà máy sinh câu (boss_factory) → ngân hàng.

Chạy nhà máy bám seed thật + cổng kiểm đáp án AI, lưu câu sinh vào ngân hàng dưới dạng nháp
cho giáo viên soát/duyệt. Job chạy nền (lô sinh + kiểm đáp án lâu) → trả job_id ngay, client poll.

Phạm vi: ĐỌC R1–R4 (Viết/Nói/Nghe = slice sau). Chỉ admin/teacher.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.deps import require_role
from app.models.user import User
from app.services import enrich_jobs, factory_service

router = APIRouter(prefix="/api/v1/factory", tags=["Factory"])


class FactoryGenerateRequest(BaseModel):
    skill: str                                      # reading_s1 | reading_s2_notice | reading_s3_comprehension | reading_s4_cloze
    limit: int = Field(3, ge=1, le=30)              # số seed lấy để sinh
    per_seed: int = Field(1, ge=1, le=3)            # số biến thể mỗi seed
    engine: str = "gemini"                          # "gemini" (thật) | "mock" (test luồng)
    verify: bool = True                             # bật cổng kiểm đáp án AI (R1–R4)


@router.get("/skills")
def list_skills(current_user: User = Depends(require_role("admin", "teacher"))):
    """Danh sách dạng câu nhà máy sinh được (cho dropdown giao diện)."""
    return {"skills": factory_service.supported_skills()}


@router.post("/generate-async")
def generate_async(
    payload: FactoryGenerateRequest,
    current_user: User = Depends(require_role("admin", "teacher")),
):
    """Chạy nhà máy sinh câu (bám seed thật + cổng kiểm đáp án) → lưu ngân hàng dạng nháp.

    Trả job_id ngay; theo dõi tiến độ qua GET /api/v1/factory/tasks/{job_id}.
    """
    if payload.skill not in factory_service.FACTORY_SKILLS:
        raise HTTPException(
            status_code=400,
            detail=f"Dạng câu không hỗ trợ: {payload.skill}. Hiện hỗ trợ Đọc R1–R4.",
        )
    # Cùng trần lô với /enrich-async (chia sẻ job store): số đề × biến thể/đề ≤ MAX_ASYNC_COUNT.
    if payload.limit * payload.per_seed > enrich_jobs.MAX_ASYNC_COUNT:
        raise HTTPException(
            status_code=400,
            detail=f"Mỗi lượt tối đa {enrich_jobs.MAX_ASYNC_COUNT} câu (số đề × biến thể/đề).",
        )
    engine = payload.engine if payload.engine in ("gemini", "mock") else "gemini"

    job_id = enrich_jobs.create_job(payload.skill, payload.limit * payload.per_seed)
    enrich_jobs.dispatch_factory_job(
        job_id, payload.skill, payload.limit, payload.per_seed, engine, payload.verify
    )
    return {"job_id": job_id, "status": "pending"}


@router.get("/tasks/{job_id}")
def get_task(job_id: str, current_user: User = Depends(require_role("admin", "teacher"))):
    """Trạng thái + kết quả một job nhà máy (poll)."""
    job = enrich_jobs.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Không tìm thấy job.")
    return job
