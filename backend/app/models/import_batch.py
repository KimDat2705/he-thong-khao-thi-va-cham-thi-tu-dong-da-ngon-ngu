from sqlalchemy import Column, Integer, String, DateTime, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base

class ImportBatch(Base):
    __tablename__ = "import_batches"

    id = Column(Integer, primary_key=True, index=True)
    source_file = Column(String, nullable=False)
    content_hash = Column(String, index=True, nullable=False)
    status = Column(String, nullable=False, default="pending")  # pending/imported/failed
    error_report = Column(JSON, nullable=True)
    
    imported_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    questions = relationship("Question", back_populates="import_batch")
    question_groups = relationship("QuestionGroup", back_populates="import_batch")
