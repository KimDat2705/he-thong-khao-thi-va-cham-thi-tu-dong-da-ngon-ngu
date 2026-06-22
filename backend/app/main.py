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
from app.api.bank import router as bank_router
from app.api.exams import router as exams_router
from app.api.auth import router as auth_router
from app.api.submissions import router as submissions_router

import os


# Auto-create tables (SQLite will create file grading_db.db if it doesn't exist)
Base.metadata.create_all(bind=engine)


app = FastAPI(
    title="Multi-language Automated Examination and Grading System API",
    description="API for managing courses, exams, submissions, auto-grading, and AI evaluation feedback.",
    version="1.0.0",
)

# Configure CORS. Set ALLOWED_ORIGINS (comma-separated, e.g. the Vercel domain)
# in production; defaults to "*" for local/demo. "*" cannot be combined with
# credentials per the CORS spec, so credentials are only enabled for explicit origins.
_origins_env = os.environ.get("ALLOWED_ORIGINS", "*").strip()
if _origins_env == "*":
    _allow_origins = ["*"]
    _allow_credentials = False
else:
    _allow_origins = [o.strip() for o in _origins_env.split(",") if o.strip()]
    _allow_credentials = True

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allow_origins,
    allow_credentials=_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(bank_router)
app.include_router(exams_router)
app.include_router(auth_router)
app.include_router(submissions_router)

# Serve extracted question images (Part 1 photos, Part 3/4 graphics) for the demo.
from fastapi.staticfiles import StaticFiles  # noqa: E402
_static_dir = os.path.join(os.path.dirname(__file__), "..", "static")
os.makedirs(_static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=_static_dir), name="static")

# Optionally serve consolidated Listening MP3 files for the demo player.
# Set AUDIO_DIR to the folder holding the .mp3 files; mounted read-only at /audio.
_audio_dir = os.environ.get("AUDIO_DIR")
if _audio_dir and os.path.isdir(_audio_dir):
    app.mount("/audio", StaticFiles(directory=_audio_dir), name="audio")

@app.get("/")
async def root():
    return {"message": "Welcome to the AI-Powered Grading System API"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "grading-api"}
