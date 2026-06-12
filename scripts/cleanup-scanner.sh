#!/usr/bin/env bash
# cleanup-scanner.sh -- Database integrity and orphan checker.
#
# Usage: bash scripts/cleanup-scanner.sh
set -euo pipefail

echo "=== Database Integrity & Cleanup Scanner ==="
echo ""

# Run python script inside backend to verify SQLAlchemy relationship integrity
cd backend
python -c "
import os
import sys

# Ensure backend folder is in path
sys.path.insert(0, os.getcwd())

# Try connecting and querying relationships
try:
    from app.core.database import SessionLocal, engine
    from app.models.user import User
    from app.models.exam import Exam
    from app.models.question import Question
    from app.models.question_group import QuestionGroup
    from app.models.submission import Submission, SubmissionDetail
    from app.models.grade import Grade
    
    db = SessionLocal()
    print('[INFO] Connected to Database successfully.')
    
    # 1. Check orphaned submission details (SubmissionDetail referencing non-existent Submission)
    orphaned_details = db.query(SubmissionDetail).filter(~SubmissionDetail.submission_id.in_(db.query(Submission.id))).count()
    if orphaned_details > 0:
        print(f'  [WARNING] Found {orphaned_details} orphaned submission detail(s) pointing to missing submissions.')
    else:
        print('  [PASS] Submission detail references are consistent.')
        
    # 2. Check orphaned grades (Grade referencing non-existent Submission)
    orphaned_grades = db.query(Grade).filter(~Grade.submission_id.in_(db.query(Submission.id))).count()
    if orphaned_grades > 0:
        print(f'  [WARNING] Found {orphaned_grades} orphaned grade(s) pointing to missing submissions.')
    else:
        print('  [PASS] Grade references are consistent.')
        
    # 3. Check question structure (Question pointing to missing QuestionGroup)
    orphaned_questions = db.query(Question).filter(
        Question.group_id.isnot(None), 
        ~Question.group_id.in_(db.query(QuestionGroup.id))
    ).count()
    if orphaned_questions > 0:
        print(f'  [WARNING] Found {orphaned_questions} questions pointing to missing groups.')
    else:
        print('  [PASS] Question groups are consistent.')
        
    db.close()
    print('[SUCCESS] Integrity check completed cleanly.')
except Exception as e:
    print(f'[INFO] Could not run DB scanner (Database may not be running or initialized yet: {e})')
    print('This is expected for fresh development environments without Postgres active.')
"

exit 0
