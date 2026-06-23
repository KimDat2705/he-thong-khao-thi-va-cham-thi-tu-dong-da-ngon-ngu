import os
import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from typing import List


from app.core.database import get_db
from app.core.deps import get_current_user, require_role
from app.models.user import User
from app.schemas.submission import (
    SubmitRequest,
    SubmissionResult,
    SubmissionDetailOut,
    SubmissionListItem,
    MySubmissionListItem,
    AudioUploadResult,
)
from app.services import submission_admin

router = APIRouter(tags=["Submissions"])

# Where uploaded Speaking recordings are stored (served at /static/uploads).
_UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "static", "uploads")
_ALLOWED_AUDIO_EXT = {".webm", ".ogg", ".mp3", ".mp4", ".m4a", ".wav"}


@router.post("/api/v1/submissions/upload-audio", response_model=AudioUploadResult)
async def upload_audio(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """
    Upload a Speaking answer recording; returns a served audio_url to attach to the
    submission answer. Any authenticated user (candidate) may upload.
    """
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in _ALLOWED_AUDIO_EXT:
        ext = ".webm"
    os.makedirs(_UPLOAD_DIR, exist_ok=True)
    fname = f"sub_{current_user.id}_{uuid.uuid4().hex}{ext}"
    content = await file.read()
    with open(os.path.join(_UPLOAD_DIR, fname), "wb") as f:
        f.write(content)
    return {"audio_url": f"/static/uploads/{fname}"}


@router.post("/api/v1/exams/{exam_id}/submit", response_model=SubmissionResult)
def submit_exam(
    exam_id: int,
    payload: SubmitRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Submit answers for an exam and perform automated grading.
    Only accessible to authenticated users (e.g. candidate).
    Raises HTTP 404 if the exam is not found or retired, and HTTP 400 for bad exam types.
    """
    try:
        ans_dicts = [
            {"question_id": a.question_id, "answer": a.answer, "audio_url": a.audio_url}
            for a in payload.answers
        ]
        result = submission_admin.create_submission_and_grade(
            db=db,
            exam_id=exam_id,
            user_id=current_user.id,
            answers=ans_dicts
        )
        return result
    except ValueError as e:
        err_msg = str(e)
        if "not found" in err_msg.lower() or "retired" in err_msg.lower():
            raise HTTPException(status_code=404, detail=err_msg)
        raise HTTPException(status_code=400, detail=err_msg)


@router.get("/api/v1/submissions/me", response_model=List[MySubmissionListItem])
def list_my_submissions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List submissions of the current candidate.
    """
    return submission_admin.list_my_submissions(db, current_user.id)


@router.get("/api/v1/submissions/{id}", response_model=SubmissionDetailOut)
def get_submission(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieve details of a submission, including questions breakdown.
    Gated: only the owner of the submission, or admin/teacher can view.
    """
    sub_data = submission_admin.get_submission(db, id)
    if sub_data is None:
        raise HTTPException(status_code=404, detail="Submission not found")

    # Gating check: must be owner or admin/teacher
    if current_user.id != sub_data["user_id"] and current_user.role not in ("admin", "teacher"):
        raise HTTPException(status_code=403, detail="Not enough permissions to access this submission")

    return sub_data


@router.get("/api/v1/exams/{exam_id}/submissions", response_model=List[SubmissionListItem])
def list_exam_submissions(
    exam_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "teacher"))
):
    """
    List all submissions for a given exam.
    Accessible only to admin and teacher.
    """
    try:
        return submission_admin.list_exam_submissions(db, exam_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
