"""API Nhà máy sinh câu (boss_factory) → ngân hàng.

Chạy nhà máy bám seed thật + cổng kiểm đáp án AI, lưu câu sinh vào ngân hàng dưới dạng nháp
cho giáo viên soát/duyệt. Job chạy nền (lô sinh + kiểm đáp án lâu) → trả job_id ngay, client poll.

Phạm vi: ĐỌC R1–R4 + VIẾT W1/W2 + NÓI (Nghe = slice sau). Chỉ admin/teacher.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_role
from app.models.question_group import QuestionGroup
from app.models.user import User
from app.services import enrich_jobs, factory_service

router = APIRouter(prefix="/api/v1/factory", tags=["Factory"])


class FactoryGenerateRequest(BaseModel):
    skill: str                                      # khóa trong factory_service.FACTORY_SKILLS (R1-R4 + W1/W2 + Nói + Nghe)
    count: Optional[int] = Field(None, ge=1, le=30) # Số lượng cần sinh (giao diện như Bản 1); None → dùng limit/per_seed
    limit: int = Field(3, ge=1, le=30)              # (nội bộ/back-compat) số seed lấy để sinh
    per_seed: int = Field(1, ge=1, le=3)            # (nội bộ/back-compat) số biến thể mỗi seed
    engine: str = "gemini"                          # "gemini" (thật) | "mock" (test luồng)
    verify: bool = True                             # bật cổng kiểm đáp án AI (R1–R4 + W1; W2/Nói/Nghe không áp dụng)
    topic: Optional[str] = None                     # Cách A: gợi ý mềm chủ đề cho AI khi sinh biến thể
    difficulty: Optional[str] = None                # Cách A: gợi ý mềm độ khó (easy|medium|hard)


class RenderListeningRequest(BaseModel):
    group_id: int                                   # nhóm Nghe part 8 (anchor) của bộ cần render audio
    with_images: bool = False                       # sinh thêm ảnh chọn-tranh part 7 (opt-in, billing)


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
        supported = ", ".join(factory_service.FACTORY_SKILLS)
        raise HTTPException(
            status_code=400,
            detail=f"Dạng câu không hỗ trợ: {payload.skill}. Hiện hỗ trợ: {supported}.",
        )
    # Cùng trần lô với /enrich-async (chia sẻ job store). count (Số lượng cần sinh) ưu tiên; nếu không
    # có thì dùng số đề × biến thể/đề (đường gọi cũ/test).
    effective = payload.count if payload.count is not None else payload.limit * payload.per_seed
    if effective > enrich_jobs.MAX_ASYNC_COUNT:
        raise HTTPException(
            status_code=400,
            detail=f"Mỗi lượt tối đa {enrich_jobs.MAX_ASYNC_COUNT} câu.",
        )
    engine = payload.engine if payload.engine in ("gemini", "mock") else "gemini"

    job_id = enrich_jobs.create_job(payload.skill, effective)
    enrich_jobs.dispatch_factory_job(
        job_id, payload.skill, payload.limit, payload.per_seed, engine, payload.verify,
        topic=payload.topic, difficulty=payload.difficulty, count=payload.count,
    )
    return {"job_id": job_id, "status": "pending"}


@router.post("/render-listening-media")
def render_listening_media(
    payload: RenderListeningRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "teacher")),
):
    """Render AUDIO (+ảnh opt-in) cho bộ Nghe của nhóm part 8 → gắn audio_url cả bộ (mở khoá duyệt).

    Op DÀI (nhiều call TTS) → chạy nền, trả job_id ngay; poll GET /api/v1/factory/tasks/{job_id}.
    Nghe audio là 1 file trọn bài (đọc-2-lần, pause Cambridge, giọng C). Ảnh chọn-tranh = opt-in (billing).
    """
    group = (db.query(QuestionGroup)
             .filter(QuestionGroup.id == payload.group_id, QuestionGroup.exam_id.is_(None),
                     QuestionGroup.part == 8).first())
    if group is None:
        raise HTTPException(
            status_code=400,
            detail=f"Không tìm thấy nhóm Nghe (part 8) id={payload.group_id} trong ngân hàng.",
        )

    job_id = enrich_jobs.create_job("render_listening", 1)
    enrich_jobs.dispatch_render_lis_job(job_id, payload.group_id, payload.with_images)
    return {"job_id": job_id, "status": "pending"}


@router.get("/tasks/{job_id}")
def get_task(job_id: str, current_user: User = Depends(require_role("admin", "teacher"))):
    """Trạng thái + kết quả một job nhà máy (poll)."""
    job = enrich_jobs.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Không tìm thấy job.")
    return job
