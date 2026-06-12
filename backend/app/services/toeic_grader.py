import json
import os
from sqlalchemy.orm import Session
from app.models.submission import Submission
from app.models.grade import Grade
from app.models.question import Question

def grade_toeic_submission(db: Session, submission_id: int) -> Grade:
    """
    Grades a TOEIC L&R submission automatically.
    Calculates correct answers in Listening (Parts 1-4) and Reading (Parts 5-7),
    applies the scaled score lookup from toeic_scoring_table.json, and saves to Grade.
    """
    # 1. Fetch submission
    submission = db.query(Submission).filter(Submission.id == submission_id).first()
    if not submission:
        raise ValueError(f"Submission with ID {submission_id} not found")
        
    # 2. Verify it's a TOEIC exam
    exam = submission.exam
    if exam.exam_type.upper() != "TOEIC":
        raise ValueError(f"Exam type '{exam.exam_type}' is not TOEIC")

    # 3. Load conversion table
    dir_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    table_path = os.path.join(dir_path, "core", "toeic_scoring_table.json")
    try:
        with open(table_path, "r") as f:
            scoring_table = json.load(f)
    except FileNotFoundError:
        # Fallback if file doesn't exist (e.g. during testing)
        scoring_table = {
            "listening": [min(495, max(5, int(i * 4.95))) for i in range(101)],
            "reading": [min(495, max(5, int(i * 4.95))) for i in range(101)]
        }

    listening_table = scoring_table["listening"]
    reading_table = scoring_table["reading"]

    # 4. Score student answers
    listening_correct = 0
    reading_correct = 0
    listening_total = 0
    reading_total = 0

    breakdown = []

    for detail in submission.details:
        question = detail.question
        if not question:
            continue
            
        student_ans = (detail.candidate_text or "").strip().upper()
        correct_ans = (question.reference_answer or "").strip().upper()
        
        is_correct = (student_ans == correct_ans) and (correct_ans != "")
        
        part = question.part or 1
        is_listening = part in [1, 2, 3, 4]
        
        if is_listening:
            listening_total += 1
            if is_correct:
                listening_correct += 1
        else:
            reading_total += 1
            if is_correct:
                reading_correct += 1
                
        breakdown.append({
            "question_id": question.id,
            "part": part,
            "section": "listening" if is_listening else "reading",
            "student_answer": student_ans,
            "correct_answer": correct_ans,
            "is_correct": is_correct,
            "explanation": question.explanation
        })

    # Standard TOEIC has exactly 100 questions per section.
    # If the database exam has a different number, scale correct count to 100.
    l_idx = listening_correct
    if listening_total > 0 and listening_total != 100:
        l_idx = int(round(listening_correct * 100 / listening_total))
    l_idx = max(0, min(100, l_idx))
    
    r_idx = reading_correct
    if reading_total > 0 and reading_total != 100:
        r_idx = int(round(reading_correct * 100 / reading_total))
    r_idx = max(0, min(100, r_idx))

    listening_score = listening_table[l_idx]
    reading_score = reading_table[r_idx]
    total_score = listening_score + reading_score

    # Save to Grade
    grade = db.query(Grade).filter(Grade.submission_id == submission_id).first()
    if not grade:
        grade = Grade(submission_id=submission_id)
        db.add(grade)

    grade.score_multiple_choice = float(total_score)
    grade.score_writing = float(reading_score)    # Stores Reading score
    grade.score_speaking = float(listening_score)  # Stores Listening score
    grade.score_total = float(total_score)
    
    # Store detailed breakdown in feedback fields
    grade.feedback_writing = {
        "section": "Reading",
        "correct_answers": reading_correct,
        "total_questions": reading_total,
        "scaled_score": reading_score,
        "breakdown": [b for b in breakdown if b["section"] == "reading"]
    }
    grade.feedback_speaking = {
        "section": "Listening",
        "correct_answers": listening_correct,
        "total_questions": listening_total,
        "scaled_score": listening_score,
        "breakdown": [b for b in breakdown if b["section"] == "listening"]
    }
    
    db.commit()
    db.refresh(grade)
    
    # Update submission status to completed
    submission.status = "completed"
    db.commit()
    
    return grade
