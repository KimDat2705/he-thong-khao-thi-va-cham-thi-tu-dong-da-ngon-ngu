import logging
from app.core.celery import celery_app
from app.core.database import SessionLocal
from app.models.submission import Submission, SubmissionDetail
from app.models.grade import Grade
from app.services.ai_grading import ai_grading_service

logger = logging.getLogger(__name__)

def compare_fill_answer(candidate: str, reference: str) -> bool:
    if not candidate or not reference:
        return False
    cand_norm = candidate.strip().lower()
    ref_parts = [p.strip().lower() for p in reference.split("/")]
    return cand_norm in ref_parts


@celery_app.task(name="app.workers.tasks.enrich_bank_task", bind=True)
def enrich_bank_task(self, job_id: str, part: str, count: int, topic=None, difficulty=None):
    """Background task (SPEC-BANK-006): sinh câu hỏi B1 cho một job bất đồng bộ.

    Ủy thác cho enrich_jobs.run_enrich_job (mở session riêng + ghi tiến độ vào job
    store) để cùng một đường chạy cho worker Celery lẫn thread dự phòng.
    """
    from app.services.enrich_jobs import run_enrich_job
    run_enrich_job(job_id, part, count, topic, difficulty)


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
        
        exam_type = submission.exam.exam_type
        
        if exam_type == "VSTEP_B1":
            # VSTEP_B1 specific 100-point grading path
            score_reading = 0.0
            score_listening = 0.0
            score_writing = 0.0
            score_speaking = 0.0
            
            feedback_writing = {}
            feedback_speaking = {}
            
            speaking_part_scores = {9: 0.0, 10: 0.0, 11: 0.0}
            
            for detail in submission.details:
                question = detail.question
                part = question.part
                
                # Reading (parts 1-4)
                if part in (1, 2, 3):
                    # Choice (1 point each)
                    is_correct = detail.candidate_text == question.reference_answer
                    if is_correct:
                        score_reading += 1.0
                elif part == 4:
                    # Fill (1 point each)
                    is_correct = compare_fill_answer(detail.candidate_text, question.reference_answer)
                    if is_correct:
                        score_reading += 1.0
                        
                # Listening (parts 7-8)
                elif part == 7:
                    # Choice (2 points each)
                    is_correct = detail.candidate_text == question.reference_answer
                    if is_correct:
                        score_listening += 2.0
                elif part == 8:
                    # Fill (1 point each)
                    is_correct = compare_fill_answer(detail.candidate_text, question.reference_answer)
                    if is_correct:
                        score_listening += 1.0
                        
                # Writing (parts 5-6)
                elif part == 5:
                    # Task 1 (max 10)
                    feedback = ai_grading_service.grade_writing(
                        essay_text=detail.candidate_text or "",
                        prompt_requirements=question.content,
                        reference_answer=question.reference_answer,
                        language=submission.exam.language
                    )
                    score_writing += feedback.get("score", 0.0)
                    feedback_writing[f"question_{question.id}"] = feedback
                elif part == 6:
                    # Task 2 (max 20) - Gemini always scores out of 10.0, so scale by 2.0
                    feedback = ai_grading_service.grade_writing(
                        essay_text=detail.candidate_text or "",
                        prompt_requirements=question.content,
                        reference_answer=question.reference_answer,
                        language=submission.exam.language
                    )
                    score_writing += feedback.get("score", 0.0) * 2.0
                    feedback_writing[f"question_{question.id}"] = feedback
                    
                # Speaking (parts 9-11)
                elif part in (9, 10, 11):
                    # Speaking parts (each out of 10, scaled later)
                    feedback = ai_grading_service.grade_speaking(
                        audio_url=detail.audio_url,
                        prompt_requirements=question.content,
                        reference_answer=question.reference_answer,
                        language=submission.exam.language
                    )
                    speaking_part_scores[part] = feedback.get("score", 0.0)
                    feedback_speaking[f"question_{question.id}"] = feedback
            
            # Scale Speaking score: (sum of 3 parts / 30) * 20
            sum_speaking = sum(speaking_part_scores.values())
            score_speaking = (sum_speaking / 30.0) * 20.0
            
            score_total = score_reading + score_listening + score_writing + score_speaking
            
            # Check pass condition: total >= 50 AND each skill >= 30% of max
            is_passed = (
                score_total >= 50.0 and
                score_reading >= 9.0 and
                score_listening >= 6.0 and
                score_writing >= 9.0 and
                score_speaking >= 6.0
            )
            
            vstep_result = {
                "status": "Đạt" if is_passed else "Không đạt",
                "total_score": score_total,
                "score_reading": score_reading,
                "score_listening": score_listening,
                "score_writing": score_writing,
                "score_speaking": score_speaking,
                "conditions": {
                    "total_passed": score_total >= 50.0,
                    "reading_passed": score_reading >= 9.0,
                    "listening_passed": score_listening >= 6.0,
                    "writing_passed": score_writing >= 9.0,
                    "speaking_passed": score_speaking >= 6.0,
                }
            }
            feedback_writing["vstep_result"] = vstep_result
            feedback_speaking["vstep_result"] = vstep_result
            
            # Create or update Grade
            grade = db.query(Grade).filter(Grade.submission_id == submission_id).first()
            if not grade:
                grade = Grade(submission_id=submission_id)
                db.add(grade)
                
            grade.score_multiple_choice = score_reading + score_listening
            grade.score_reading = score_reading
            grade.score_listening = score_listening
            grade.score_writing = score_writing
            grade.score_speaking = score_speaking
            grade.score_total = score_total
            grade.feedback_writing = feedback_writing
            grade.feedback_speaking = feedback_speaking
            
            submission.status = "completed"
            db.commit()
            
            logger.info(f"Grading completed for submission_id: {submission_id} (VSTEP_B1). Total score: {score_total}")
            return {"status": "success", "score_total": score_total}
            
        else:
            # Generic grading path (e.g. VSTEP demo, HSK)
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
