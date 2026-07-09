import pytest
import sys
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

# Ensure backend directory is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Override database URL to SQLite for testing
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

# Nhà máy sinh câu: ép thư mục seed về fixture 2-đề (tất định) cho MỌI test factory; production
# (không set env này) dùng corpus backend/app/data/factory_seeds/. _load_seed_bank đọc env tại
# call-time nên đặt ở module-level (chạy lúc import, trước mọi test) là đủ.
os.environ["FACTORY_SEED_DIR"] = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "fixtures", "factory_sample"))

from app.core.database import Base
from app.models.user import User
from app.models.exam import Exam
from app.models.question import Question
from app.models.question_group import QuestionGroup
from app.models.submission import Submission, SubmissionDetail
from app.models.grade import Grade

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture(scope="session", autouse=True)
def _generate_test_fixtures():
    """Sinh fixture parser (.docx/.mp3, đều gitignored) MỘT LẦN trước mọi test, để các file
    test tiêu thụ chúng (vd test_specs_bank dùng B1_exam_sample.docx) KHÔNG phụ thuộc thứ tự
    chạy alphabet so với test_specs_parser. Vá lỗi CI: bank chạy trước parser (alphabet) ->
    file chưa sinh -> AssertionError (local có file cũ từ lần chạy trước nên không lộ)."""
    from tests.make_fixtures import main as generate_fixtures
    generate_fixtures()


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
        
        # 2. Populate mock VSTEP B1 Question Bank
        # Part 8: Grouped (Listening - fill) - needs 1 group of 10. Create 2 groups.
        for i in range(2):
            group = QuestionGroup(
                exam_id=None, part=8, topic=f"Listening fill topic {i}",
                difficulty="medium", audio_url=f"/static/audio_gen/l2_group_{i}.wav"
            )
            db.add(group)
            db.commit()
            db.refresh(group)
            for j in range(10):
                db.add(Question(
                    exam_id=None, group_id=group.id, part=8, type="fill",
                    content=f"Part 8 Group {i} Question {j}", reference_answer="answer",
                    difficulty=group.difficulty,
                    exam_type="VSTEP_B1"
                ))

        # Part 9: Standalone (Speaking Part 1) - needs 1. Create 3.
        for i in range(3):
            db.add(Question(
                exam_id=None, group_id=None, part=9, type="speaking",
                content=f"Part 9 Speaking Question {i}", reference_answer=None,
                difficulty="medium",
                exam_type="VSTEP_B1"
            ))

        # Part 10: Standalone (Speaking Part 2) - needs 1. Create 3.
        for i in range(3):
            db.add(Question(
                exam_id=None, group_id=None, part=10, type="speaking",
                content=f"Part 10 Speaking Question {i}", reference_answer=None,
                difficulty="medium",
                exam_type="VSTEP_B1"
            ))

        # Part 11: Standalone (Speaking Part 3) - needs 1. Create 3.
        for i in range(3):
            db.add(Question(
                exam_id=None, group_id=None, part=11, type="speaking",
                content=f"Part 11 Speaking Question {i}", reference_answer=None,
                difficulty="medium",
                exam_type="VSTEP_B1"
            ))

        # Bổ sung câu hỏi standalone writing cho Part 5 và Part 6 (VSTEP B1)
        db.add(Question(
            exam_id=None, group_id=None, part=5, type="writing",
            content="Part 5 VSTEP Writing Question", reference_answer=None,
            difficulty="medium",
            exam_type="VSTEP_B1"
        ))
        db.add(Question(
            exam_id=None, group_id=None, part=6, type="writing",
            content="Part 6 VSTEP Writing Question", reference_answer=None,
            difficulty="medium",
            exam_type="VSTEP_B1"
        ))

        # Part 1: Standalone VSTEP_B1 - needs 10. Create 10.
        for i in range(10):
            db.add(Question(
                exam_id=None, group_id=None, part=1, type="choice",
                content=f"Part 1 VSTEP Photo Question {i}", reference_answer="A",
                difficulty="medium", options={"A": "Option A", "B": "Option B"},
                exam_type="VSTEP_B1"
            ))

        # Part 2: Standalone VSTEP_B1 - needs 5. Create 5.
        for i in range(5):
            db.add(Question(
                exam_id=None, group_id=None, part=2, type="choice",
                content=f"Part 2 VSTEP Question {i}", reference_answer="A",
                difficulty="medium", options={"A": "Option A", "B": "Option B"},
                exam_type="VSTEP_B1"
            ))

        # Part 3: Grouped VSTEP_B1 - needs 1 group of 5. Create 1 group.
        group3 = QuestionGroup(exam_id=None, part=3, topic="Family", difficulty="medium")
        db.add(group3)
        db.commit()
        db.refresh(group3)
        for j in range(5):
            db.add(Question(
                exam_id=None, group_id=group3.id, part=3, type="choice",
                content=f"Part 3 VSTEP Grouped Question {j}", reference_answer="A",
                difficulty="medium", options={"A": "a", "B": "b"},
                exam_type="VSTEP_B1"
            ))

        # Part 4: Grouped VSTEP_B1 - needs 1 group of 10. Create 1 group.
        group4 = QuestionGroup(exam_id=None, part=4, topic="Work", difficulty="medium")
        db.add(group4)
        db.commit()
        db.refresh(group4)
        for j in range(10):
            db.add(Question(
                exam_id=None, group_id=group4.id, part=4, type="choice",
                content=f"Part 4 VSTEP Grouped Question {j}", reference_answer="A",
                difficulty="medium", options={"A": "a", "B": "b"},
                exam_type="VSTEP_B1"
            ))

        # Part 7: Standalone VSTEP_B1 - needs 5. Create 5.
        for i in range(5):
            db.add(Question(
                exam_id=None, group_id=None, part=7, type="choice",
                content=f"Part 7 VSTEP Question {i}", reference_answer="A",
                difficulty="medium", options={"A": "Option A", "B": "Option B"},
                audio_url=f"/static/audio_gen/part7_{i}.wav",
                image_url=f"/static/img/part7_{i}.png",
                exam_type="VSTEP_B1"
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

