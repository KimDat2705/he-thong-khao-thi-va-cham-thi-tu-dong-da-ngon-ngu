from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base

class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True, index=True)
    exam_id = Column(Integer, ForeignKey("exams.id", ondelete="CASCADE"), nullable=False)
    type = Column(String, nullable=False)  # "choice" | "writing" | "speaking"
    content = Column(Text, nullable=False)
    audio_url = Column(Text, nullable=True)  # URL to audio prompts (listening/speaking)
    reference_answer = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    exam = relationship("Exam", back_populates="questions")
    details = relationship("SubmissionDetail", back_populates="question", cascade="all, delete-orphan")
