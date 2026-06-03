from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base

class Submission(Base):
    __tablename__ = "submissions"

    id = Column(Integer, primary_key=True, index=True)
    exam_id = Column(Integer, ForeignKey("exams.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    submitted_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String, default="pending")  # "pending" | "grading" | "completed"

    # Relationships
    exam = relationship("Exam", back_populates="submissions")
    user = relationship("User", back_populates="submissions")
    details = relationship("SubmissionDetail", back_populates="submission", cascade="all, delete-orphan")
    grade = relationship("Grade", uselist=False, back_populates="submission", cascade="all, delete-orphan")


class SubmissionDetail(Base):
    __tablename__ = "submission_details"

    id = Column(Integer, primary_key=True, index=True)
    submission_id = Column(Integer, ForeignKey("submissions.id", ondelete="CASCADE"), nullable=False)
    question_id = Column(Integer, ForeignKey("questions.id", ondelete="CASCADE"), nullable=False)
    candidate_text = Column(Text, nullable=True)  # Used for writing essays or multiple-choice answers
    audio_url = Column(Text, nullable=True)       # Used for uploaded speaking responses

    # Relationships
    submission = relationship("Submission", back_populates="details")
    question = relationship("Question", back_populates="details")
