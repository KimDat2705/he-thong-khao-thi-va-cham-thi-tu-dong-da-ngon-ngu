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

