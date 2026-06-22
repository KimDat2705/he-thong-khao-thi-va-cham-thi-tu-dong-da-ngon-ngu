from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional, Any


class AnswerItem(BaseModel):
    question_id: int
    answer: str


class SubmitRequest(BaseModel):
    answers: List[AnswerItem]


class SubmissionResult(BaseModel):
    submission_id: int
    status: str
    listening_score: float
    reading_score: float
    total_score: float
    listening_correct: int
    reading_correct: int


class AnswerDetailOut(BaseModel):
    question_id: int
    candidate_text: Optional[str] = None
    audio_url: Optional[str] = None


class SubmissionDetailOut(BaseModel):
    id: int
    exam_id: int
    user_id: int
    started_at: Optional[datetime] = None
    submitted_at: Optional[datetime] = None
    status: str
    answers: List[AnswerDetailOut] = []
    
    # Grading results (if completed)
    score_multiple_choice: Optional[float] = None
    listening_score: Optional[float] = None
    reading_score: Optional[float] = None
    total_score: Optional[float] = None
    feedback_speaking: Optional[Any] = None
    feedback_writing: Optional[Any] = None
