from sqlalchemy import Column, Integer, Float, ForeignKey, DateTime, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base

class Grade(Base):
    __tablename__ = "grades"

    id = Column(Integer, primary_key=True, index=True)
    submission_id = Column(Integer, ForeignKey("submissions.id", ondelete="CASCADE"), unique=True, nullable=False)
    score_multiple_choice = Column(Float, default=0.0)
    # Objective L&R scaled scores (TOEIC). Stored in semantically-named columns
    # rather than borrowing score_speaking/score_writing (SPEC-GRADE-002).
    score_listening = Column(Float, default=0.0)
    score_reading = Column(Float, default=0.0)
    # Essay grades (Writing/Speaking) — used by the AI/Celery grading path.
    score_writing = Column(Float, default=0.0)
    score_speaking = Column(Float, default=0.0)
    score_total = Column(Float, default=0.0)
    feedback_writing = Column(JSON, nullable=True)   # AI detailed text grammar errors, structures
    feedback_speaking = Column(JSON, nullable=True)  # AI speech analysis transcription, pronunciation, fluency
    graded_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    submission = relationship("Submission", back_populates="grade")
