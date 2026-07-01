from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional, Dict, Any, List

class QuestionRead(BaseModel):
    id: int
    exam_id: Optional[int] = None
    group_id: Optional[int] = None
    part: Optional[int] = None
    type: str
    content: str
    audio_url: Optional[str] = None
    image_url: Optional[str] = None
    options: Optional[Any] = None
    reference_answer: Optional[str] = None
    difficulty: Optional[str] = None
    clo: Optional[str] = None
    topic: Optional[str] = None
    status: str
    explanation: Optional[str] = None
    source_question_id: Optional[int] = None
    content_hash: Optional[str] = None
    import_batch_id: Optional[int] = None
    exam_type: Optional[str] = None
    language: Optional[str] = None
    group_passage: Optional[str] = None
    group_audio_url: Optional[str] = None
    group_image_url: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

class QuestionUpdate(BaseModel):
    content: Optional[str] = None
    audio_url: Optional[str] = None
    image_url: Optional[str] = None
    options: Optional[Any] = None
    reference_answer: Optional[str] = None
    difficulty: Optional[str] = None
    clo: Optional[str] = None
    topic: Optional[str] = None
    status: Optional[str] = None
    explanation: Optional[str] = None
    exam_type: Optional[str] = None
    language: Optional[str] = None

class ApproveRequest(BaseModel):
    ids: List[int]

class ApproveResult(BaseModel):
    updated: int

class PartStats(BaseModel):
    part: int
    type: str
    approved_count: int
    needed_count: int
    is_sufficient: bool

class BankStats(BaseModel):
    question_counts: Dict[str, Dict[str, int]]
    group_counts: Dict[str, Dict[str, int]]
    blueprint_sufficiency: List[PartStats]

class QuestionListResponse(BaseModel):
    total: int
    items: List[QuestionRead]

class EnrichRequest(BaseModel):
    count: int
    part: str
    topic: Optional[str] = None
    difficulty: Optional[str] = None

class EnrichResult(BaseModel):
    success: bool
    generated_count: int

class EnrichAsyncResult(BaseModel):
    """Trả về ngay khi nhận yêu cầu sinh câu hỏi bất đồng bộ (SPEC-BANK-006)."""
    job_id: str
    status: str

class EnrichJobStatus(BaseModel):
    """Trạng thái tiến độ của một job sinh câu hỏi bất đồng bộ (SPEC-BANK-006)."""
    job_id: str
    status: str  # pending | running | completed | error
    part: str
    requested: int
    generated_count: int
    error: Optional[str] = None

class SeedCreate(BaseModel):
    """SPEC-BANK-007 AC1: lưu câu Seed chuẩn (trắc nghiệm) làm tham chiếu học thuật."""
    part: int
    type: str = "choice"
    content: str
    options: Dict[str, str]
    reference_answer: str
    topic: Optional[str] = None
    difficulty: Optional[str] = None
    image_url: Optional[str] = None

class ParaphraseRequest(BaseModel):
    """SPEC-BANK-007 AC2/3/4: paraphrase một câu Seed thành các biến thể nháp."""
    seed_question_id: int
    count: int = 3

class ParaphraseResult(BaseModel):
    success: bool
    generated_count: int
    seed_question_id: int

