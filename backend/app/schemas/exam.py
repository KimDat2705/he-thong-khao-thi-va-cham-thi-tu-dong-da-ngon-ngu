from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional, Any, List


class ExamGenerateRequest(BaseModel):
    """Payload to generate a new TOEIC exam from the approved bank."""
    title: Optional[str] = None
    seed: Optional[int] = None
    duration_minutes: int = 120


class ExamSummary(BaseModel):
    id: int
    title: str
    language: str
    exam_type: str
    duration_minutes: int
    is_active: bool
    created_at: Optional[datetime] = None
    question_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class QuestionOut(BaseModel):
    id: int
    group_id: Optional[int] = None
    part: Optional[int] = None
    type: str
    content: str
    options: Optional[Any] = None
    reference_answer: Optional[str] = None
    audio_url: Optional[str] = None
    image_url: Optional[str] = None
    difficulty: Optional[str] = None
    topic: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class GroupOut(BaseModel):
    id: int
    part: Optional[int] = None
    topic: Optional[str] = None
    passage_text: Optional[str] = None
    audio_url: Optional[str] = None
    image_url: Optional[str] = None
    difficulty: Optional[str] = None
    questions: List[QuestionOut] = []

    model_config = ConfigDict(from_attributes=True)


class PartOut(BaseModel):
    """One TOEIC part: standalone questions and/or grouped passages."""
    part: int
    part_type: str  # "standalone" | "grouped" | "subset_sum"
    question_count: int
    audio_url: Optional[str] = None  # consolidated Listening audio for the part (if any)
    standalone_questions: List[QuestionOut] = []
    groups: List[GroupOut] = []


class ExamDetail(BaseModel):
    id: int
    title: str
    language: str
    exam_type: str
    duration_minutes: int
    created_at: Optional[datetime] = None
    total_questions: int
    parts: List[PartOut] = []
