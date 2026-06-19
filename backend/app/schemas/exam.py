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


class ExamBatchGenerateRequest(BaseModel):
    """Payload to generate a batch of exams."""
    exam_type: Optional[str] = "TOEIC"
    structure: Optional[dict] = None
    count: int
    seed: Optional[int] = None
    max_overlap_limit: Optional[float] = 0.40


class OverlapPair(BaseModel):
    exam_1_id: int
    exam_1_title: str
    exam_2_id: int
    exam_2_title: str
    overlap_ratio: float
    common_questions_count: int


class OverlapReport(BaseModel):
    pairwise_overlaps: List[OverlapPair]
    max_overlap: float
    average_overlap: float
    threshold: float
    resample_count: int


class ValidationSummaryItem(BaseModel):
    exam_id: int
    title: str
    is_valid: bool
    errors: List[str] = []


class ExamBatchGenerateResponse(BaseModel):
    exams: List[ExamSummary]
    overlap_report: OverlapReport
    validation_summary: List[ValidationSummaryItem]

