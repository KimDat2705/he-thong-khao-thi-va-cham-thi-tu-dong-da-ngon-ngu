import logging
from app.core.celery import celery_app
from app.core.database import SessionLocal
from app.models.submission import Submission, SubmissionDetail
from app.models.grade import Grade
from app.services.ai_grading import ai_grading_service

logger = logging.getLogger(__name__)

@celery_app.task(name="app.workers.tasks.grade_submission_task", bind=True, max_retries=3)
def grade_submission_task(self, submission_id: int):
    """
    Background worker task to grade a student submission using Gemini AI.
    """
    logger.info(f"Starting grading task for submission_id: {submission_id}")
    
    db = SessionLocal()
    try:
        submission = db.query(Submission).filter(Submission.id == submission_id).first()
        if not submission:
            logger.error(f"Submission {submission_id} not found.")
            return {"error": "Submission not found"}
            
        submission.status = "grading"
        db.commit()
        
        score_multiple_choice = 0.0
        score_writing = 0.0
        score_speaking = 0.0
        feedback_writing = {}
        feedback_speaking = {}
        
        # Process each answer detail
        for detail in submission.details:
            question = detail.question
            if question.type == "choice":
                # Multiple choice automated grading
                is_correct = detail.candidate_text == question.reference_answer
                if is_correct:
                    score_multiple_choice += 1.0  # Or specific points per question
            
            elif question.type == "writing":
                # AI essay grading
                feedback = ai_grading_service.grade_writing(
                    essay_text=detail.candidate_text,
                    prompt_requirements=question.content,
                    reference_answer=question.reference_answer,
                    language=submission.exam.language
                )
                score_writing += feedback.get("score", 0.0)
                feedback_writing[f"question_{question.id}"] = feedback
                
            elif question.type == "speaking":
                # AI speech grading
                feedback = ai_grading_service.grade_speaking(
                    audio_url=detail.audio_url,
                    prompt_requirements=question.content,
                    reference_answer=question.reference_answer,
                    language=submission.exam.language
                )
                score_speaking += feedback.get("score", 0.0)
                feedback_speaking[f"question_{question.id}"] = feedback
        
        # Aggregate final score
        score_total = score_multiple_choice + score_writing + score_speaking
        
        # Create or update Grade
        grade = db.query(Grade).filter(Grade.submission_id == submission_id).first()
        if not grade:
            grade = Grade(submission_id=submission_id)
            db.add(grade)
            
        grade.score_multiple_choice = score_multiple_choice
        grade.score_writing = score_writing
        grade.score_speaking = score_speaking
        grade.score_total = score_total
        grade.feedback_writing = feedback_writing
        grade.feedback_speaking = feedback_speaking
        
        # Update submission status
        submission.status = "completed"
        db.commit()
        
        logger.info(f"Grading completed for submission_id: {submission_id}. Total score: {score_total}")
        return {"status": "success", "score_total": score_total}
        
    except Exception as exc:
        logger.exception(f"Error during grading task for submission_id: {submission_id}")
        db.rollback()
        # Retry task in case of network issue with Gemini API
        raise self.retry(exc=exc, countdown=60)
    finally:
        db.close()
