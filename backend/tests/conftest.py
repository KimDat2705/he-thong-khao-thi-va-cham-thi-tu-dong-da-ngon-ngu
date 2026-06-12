import pytest
import sys
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Ensure backend directory is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Override database URL to SQLite for testing
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from app.core.database import Base
from app.models.user import User
from app.models.exam import Exam
from app.models.question import Question
from app.models.question_group import QuestionGroup
from app.models.submission import Submission, SubmissionDetail
from app.models.grade import Grade

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

@pytest.fixture(scope="function")
def db_session():
    # Setup database
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
    )
    TestingSessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=engine
    )
    Base.metadata.create_all(bind=engine)
    
    db = TestingSessionLocal()
    try:
        # 1. Create a test candidate user
        user = User(
            username="testcandidate",
            hashed_password="mockhashedpassword",
            full_name="Test Candidate",
            role="candidate"
        )
        db.add(user)
        db.commit()
        
        # 2. Populate mock Question Bank
        # Part 1: Standalone - needs 6. Create 10.
        for i in range(10):
            db.add(Question(
                exam_id=None, group_id=None, part=1, type="choice",
                content=f"Part 1 Photo Question {i}", reference_answer="A" if i % 2 == 0 else "B",
                difficulty="easy" if i < 3 else ("medium" if i < 7 else "hard"),
                options={"A": "Option A", "B": "Option B", "C": "Option C", "D": "Option D"}
            ))
            
        # Part 2: Standalone - needs 25. Create 30.
        for i in range(30):
            db.add(Question(
                exam_id=None, group_id=None, part=2, type="choice",
                content=f"Part 2 Question {i}", reference_answer="A" if i % 3 == 0 else "C",
                difficulty="easy" if i < 8 else ("medium" if i < 22 else "hard"),
                options={"A": "Option A", "B": "Option B", "C": "Option C"}
            ))
            
        # Part 3: Grouped - needs 13 groups of 3. Create 15 groups.
        for i in range(15):
            group = QuestionGroup(
                exam_id=None, part=3, topic="Meetings", audio_url=f"http://example.com/audio/p3_{i}.mp3",
                difficulty="easy" if i < 4 else ("medium" if i < 11 else "hard")
            )
            db.add(group)
            db.commit()
            db.refresh(group)
            
            for j in range(3):
                db.add(Question(
                    exam_id=None, group_id=group.id, part=3, type="choice",
                    content=f"Part 3 Group {i} Question {j}", reference_answer="D",
                    difficulty=group.difficulty,
                    options={"A": "Option A", "B": "Option B", "C": "Option C", "D": "Option D"}
                ))
                
        # Part 4: Grouped - needs 10 groups of 3. Create 12 groups.
        for i in range(12):
            group = QuestionGroup(
                exam_id=None, part=4, topic="Talk", audio_url=f"http://example.com/audio/p4_{i}.mp3",
                difficulty="easy" if i < 3 else ("medium" if i < 9 else "hard")
            )
            db.add(group)
            db.commit()
            db.refresh(group)
            
            for j in range(3):
                db.add(Question(
                    exam_id=None, group_id=group.id, part=4, type="choice",
                    content=f"Part 4 Group {i} Question {j}", reference_answer="B",
                    difficulty=group.difficulty,
                    options={"A": "Option A", "B": "Option B", "C": "Option C", "D": "Option D"}
                ))
                
        # Part 5: Standalone - needs 30. Create 35.
        for i in range(35):
            db.add(Question(
                exam_id=None, group_id=None, part=5, type="choice",
                content=f"Part 5 Question {i}", reference_answer="C",
                difficulty="easy" if i < 10 else ("medium" if i < 28 else "hard"),
                options={"A": "Option A", "B": "Option B", "C": "Option C", "D": "Option D"}
            ))
            
        # Part 6: Grouped - needs 4 groups of 4. Create 5 groups.
        for i in range(5):
            group = QuestionGroup(
                exam_id=None, part=6, topic="Memo", passage_text=f"Memo content {i}",
                difficulty="easy" if i < 2 else ("medium" if i < 4 else "hard")
            )
            db.add(group)
            db.commit()
            db.refresh(group)
            
            for j in range(4):
                db.add(Question(
                    exam_id=None, group_id=group.id, part=6, type="choice",
                    content=f"Part 6 Group {i} Question {j}", reference_answer="A",
                    difficulty=group.difficulty,
                    options={"A": "Option A", "B": "Option B", "C": "Option C", "D": "Option D"}
                ))
                
        # Part 7: Grouped - needs total 54 questions. Create 15 groups, each with 4 questions (total 60 questions).
        for i in range(15):
            group = QuestionGroup(
                exam_id=None, part=7, topic="Article", passage_text=f"Article content {i}",
                difficulty="easy" if i < 3 else ("medium" if i < 11 else "hard")
            )
            db.add(group)
            db.commit()
            db.refresh(group)
            
            for j in range(4):
                db.add(Question(
                    exam_id=None, group_id=group.id, part=7, type="choice",
                    content=f"Part 7 Group {i} Question {j}", reference_answer="C",
                    difficulty=group.difficulty,
                    options={"A": "Option A", "B": "Option B", "C": "Option C", "D": "Option D"}
                ))
        db.commit()
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
