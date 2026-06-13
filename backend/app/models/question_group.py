from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base

class QuestionGroup(Base):
    __tablename__ = "question_groups"

    id = Column(Integer, primary_key=True, index=True)
    exam_id = Column(Integer, ForeignKey("exams.id", ondelete="CASCADE"), nullable=True)
    part = Column(Integer, nullable=False)  # 3, 4, 6, or 7
    topic = Column(String, nullable=True)   # E.g., "Meetings", "HR"
    passage_text = Column(Text, nullable=True)  # Passage text for Part 6/7
    audio_url = Column(Text, nullable=True)     # Shared audio prompt for Part 3/4
    image_url = Column(Text, nullable=True)     # Graphic prompt for Part 7 if any
    
    # QC & Metadata details
    passage_type = Column(String, nullable=True)  # E.g., "email", "memo", "notice", "article"
    speaker_count = Column(Integer, nullable=True) # E.g., 2 or 3 for Part 3
    speech_rate = Column(String, nullable=True)    # E.g., "slow", "normal", "fast"
    accent = Column(String, nullable=True)         # E.g., "American", "British", "Mixed"
    difficulty = Column(String, nullable=True)     # E.g., "easy", "medium", "hard"
    status = Column(String, default="approved")    # E.g., "draft", "approved"
    
    # New columns for M2
    content_hash = Column(String, nullable=True, index=True)
    import_batch_id = Column(Integer, ForeignKey("import_batches.id", ondelete="SET NULL"), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    exam = relationship("Exam", back_populates="question_groups")
    questions = relationship("Question", back_populates="group", cascade="all, delete-orphan")

    # New relationships for M2
    import_batch = relationship("ImportBatch", back_populates="question_groups")

