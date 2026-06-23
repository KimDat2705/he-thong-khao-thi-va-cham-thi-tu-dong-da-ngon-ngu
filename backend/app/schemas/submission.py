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
    # Scores are None when grading is asynchronous (essay/Writing/Speaking via
    # Celery): the submit endpoint returns immediately with status "grading" and
    # the worker fills in the scores later (SPEC-GRADE-003). For synchronous TOEIC
    # grading these are populated in the response.
    listening_score: Optional[float] = None
    reading_score: Optional[float] = None
    total_score: Optional[float] = None
    listening_correct: Optional[int] = None
    reading_correct: Optional[int] = None


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
    # Essay scores from the AI/Celery grading path (SPEC-GRADE-003)
    score_writing: Optional[float] = None
    score_speaking: Optional[float] = None
    total_score: Optional[float] = None
    feedback_speaking: Optional[Any] = None
    feedback_writing: Optional[Any] = None


class SubmissionListItem(BaseModel):
    submission_id: int
    user_id: int
    username: str
    full_name: Optional[str] = None
    exam_type: Optional[str] = None
    total_score: Optional[float] = None
    listening_score: Optional[float] = None
    reading_score: Optional[float] = None
    writing_score: Optional[float] = None
    status: str
    submitted_at: Optional[datetime] = None


class MySubmissionListItem(BaseModel):
    submission_id: int
    exam_id: int
    exam_title: str
    exam_type: Optional[str] = None
    total_score: Optional[float] = None
    listening_score: Optional[float] = None
    reading_score: Optional[float] = None
    writing_score: Optional[float] = None
    status: str
    submitted_at: Optional[datetime] = None

