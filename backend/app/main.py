from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.database import Base, engine
# Import models to register them on Base metadata
from app.models.user import User
from app.models.exam import Exam
from app.models.question import Question
from app.models.submission import Submission, SubmissionDetail
from app.models.grade import Grade
from app.models.blueprint import Blueprint
from app.models.import_batch import ImportBatch


# Auto-create tables (SQLite will create file grading_db.db if it doesn't exist)
Base.metadata.create_all(bind=engine)


app = FastAPI(
    title="Multi-language Automated Examination and Grading System API",
    description="API for managing courses, exams, submissions, auto-grading, and AI evaluation feedback.",
    version="1.0.0",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "Welcome to the AI-Powered Grading System API"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "grading-api"}
