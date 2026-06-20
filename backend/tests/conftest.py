import pytest
import sys
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

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
    from sqlalchemy.pool import StaticPool
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
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
        p3_topics = ["Meetings", "HR", "Finance", "Marketing", "Sales", "Travel", "Purchasing", "Dining", "Office", "IT", "Safety", "Legal", "Planning", "Strategy", "Logistics"]
        for i in range(15):
            group = QuestionGroup(
                exam_id=None, part=3, topic=p3_topics[i], audio_url=f"http://example.com/audio/p3_{i}.mp3",
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
        p4_topics = [
            "Intro", "Inst", "Ad",          # Easy (0, 1, 2)
            "Talk", "Talk", "Talk",          # Medium (3, 4, 5)
            "News", "Weather", "Traffic",    # Medium (6, 7, 8)
            "Report", "Tour", "Speech"       # Hard (9, 10, 11)
        ]
        for i in range(12):
            group = QuestionGroup(
                exam_id=None, part=4, topic=p4_topics[i], audio_url=f"http://example.com/audio/p4_{i}.mp3",
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
        p6_topics = ["Memo", "Email", "Notice", "Letter", "Report"]
        for i in range(5):
            group = QuestionGroup(
                exam_id=None, part=6, topic=p6_topics[i], passage_text=f"Memo content {i}",
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
                
        # Part 7: Grouped - needs total 54 questions. Create 15 groups with diverse sizes (2, 3, 4, 5 questions).
        # We create 15 groups in total:
        # - Group 0 to 1: 2 questions each
        # - Group 2 to 3: 3 questions each
        # - Group 4 to 8: 4 questions each
        # - Group 9 to 14: 5 questions each
        # Total questions in bank = (2*2) + (2*3) + (5*4) + (6*5) = 4 + 6 + 20 + 30 = 60 questions.
        p7_topics = [
            "Chat", "Chat",                # Group 0, 1 (size 2)
            "Memo", "Report",              # Group 2, 3 (size 3)
            "Memo", "Memo", "Report", "Report", "Webpage", # Group 4, 5, 6, 7, 8 (size 4)
            "Article", "Article", "Email", "Email", "Notice", "Notice" # Group 9, 10, 11, 12, 13, 14 (size 5)
        ]
        p7_difficulties = [
            "easy", "medium",                  # G0 (size 2), G1 (size 2)
            "medium", "medium",                # G2 (size 3), G3 (size 3)
            "easy", "easy", "hard", "medium", "medium",  # G4 to G8 (size 4)
            "easy", "medium", "hard", "hard", "medium", "medium"  # G9 to G14 (size 5)
        ]
        for i in range(15):
            group = QuestionGroup(
                exam_id=None, part=7, topic=p7_topics[i], passage_text=f"Article content {i}",
                difficulty=p7_difficulties[i]
            )
            db.add(group)
            db.commit()
            db.refresh(group)
            
            # Determine question count based on group index i
            if i < 2:
                q_count = 2
            elif i < 4:
                q_count = 3
            elif i < 9:
                q_count = 4
            else:
                q_count = 5
                
            for j in range(q_count):
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


@pytest.fixture(scope="function")
def admin_auth_headers(db_session: Session):
    from app.core.security import hash_password, create_access_token
    from app.models.user import User

    # Create admin user
    username = "admin_test"
    password = "admin_password"
    
    admin_user = User(
        username=username,
        hashed_password=hash_password(password),
        full_name="Admin Test",
        role="admin",
        is_active=True
    )
    db_session.add(admin_user)
    db_session.commit()
    db_session.refresh(admin_user)

    # Generate token
    token = create_access_token(data={"sub": username, "role": "admin"})
    return {"Authorization": f"Bearer {token}"}

