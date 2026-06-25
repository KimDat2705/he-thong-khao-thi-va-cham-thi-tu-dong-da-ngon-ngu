from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base

class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True, index=True)
    exam_id = Column(Integer, ForeignKey("exams.id", ondelete="CASCADE"), nullable=True)
    group_id = Column(Integer, ForeignKey("question_groups.id", ondelete="SET NULL"), nullable=True)
    part = Column(Integer, nullable=True)  # TOEIC part (1 to 7)
    type = Column(String, nullable=False, default="choice")  # "choice" | "writing" | "speaking"
    content = Column(Text, nullable=False)  # Question prompt
    audio_url = Column(Text, nullable=True)  # URL to audio prompts (listening/speaking)
    image_url = Column(Text, nullable=True)  # For Part 1 photo or Part 7 graphics
    options = Column(JSON, nullable=True)  # Options dict: {"A": "...", "B": "...", "C": "...", "D": "..."}
    reference_answer = Column(Text, nullable=True)  # E.g., "A", "B", "C" or "D"
    difficulty = Column(String, nullable=True)  # "easy" | "medium" | "hard"
    clo = Column(String, nullable=True)  # Course Learning Outcome / competency
    topic = Column(String, nullable=True)  # Topic domain
    status = Column(String, default="approved")  # "draft" | "approved"
    explanation = Column(Text, nullable=True)  # AI/Teacher explanation for grading feedback
    exam_type = Column(String, default="TOEIC", server_default="TOEIC", nullable=False)
    language = Column(String, default="EN", server_default="EN", nullable=False)
    
    # New columns for M2
    source_question_id = Column(Integer, ForeignKey("questions.id", ondelete="SET NULL"), nullable=True, index=True)
    content_hash = Column(String, nullable=True, index=True)
    import_batch_id = Column(Integer, ForeignKey("import_batches.id", ondelete="SET NULL"), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    exam = relationship("Exam", back_populates="questions")
    group = relationship("QuestionGroup", back_populates="questions")
    details = relationship("SubmissionDetail", back_populates="question", cascade="all, delete-orphan")
    
    # New relationships for M2
    source_question = relationship("Question", remote_side=[id])
    import_batch = relationship("ImportBatch", back_populates="questions")

