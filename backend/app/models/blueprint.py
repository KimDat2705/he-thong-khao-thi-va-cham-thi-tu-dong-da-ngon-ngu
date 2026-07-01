from sqlalchemy import Column, Integer, String, Boolean, DateTime, JSON
from sqlalchemy.sql import func
from app.core.database import Base

class Blueprint(Base):
    __tablename__ = "blueprints"

    id = Column(Integer, primary_key=True, index=True)
    exam_type = Column(String, index=True, nullable=False)  # e.g., "VSTEP_B1"
    language = Column(String, nullable=False)                # e.g., "EN", "CN"
    structure = Column(JSON, nullable=False)                 # Blueprint structure json
    is_active = Column(Boolean, default=True, nullable=False)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
