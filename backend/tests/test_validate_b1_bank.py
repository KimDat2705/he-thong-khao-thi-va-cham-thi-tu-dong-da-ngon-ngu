import os
import wave

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.question import Question
from scripts.validate_b1_bank import find_b1_bank_issues


def _make_valid_wav(path, seconds=4, rate=24000):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with wave.open(path, "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x00\x00" * int(rate * seconds))  # ~192KB, 4s -> hợp lệ


def test_validate_b1_bank_flags_broken_audio_and_conflicting_keys(tmp_path):
    """Cổng kiểm chất lượng phải: (a) BỎ QUA audio hợp lệ; (b) CỜ audio thiếu/hỏng;
    (c) CỜ câu trùng nội dung nhưng đáp án mâu thuẫn (đúng 2 lớp lỗi đã sửa tay ở S45)."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine)()
    static_root = str(tmp_path)
    _make_valid_wav(os.path.join(static_root, "static", "audio_gen", "good.wav"))
    try:
        # q1: audio HỢP LỆ (không được cờ)
        db.add(Question(exam_id=None, group_id=None, part=7, type="choice",
                        content="L1 good", options={"A": "a"}, reference_answer="A",
                        audio_url="/static/audio_gen/good.wav",
                        status="approved", exam_type="VSTEP_B1", language="EN"))
        # q2: audio THIẾU (phải cờ)
        db.add(Question(exam_id=None, group_id=None, part=7, type="choice",
                        content="L1 broken", options={"A": "a"}, reference_answer="A",
                        audio_url="/static/audio_gen/missing.wav",
                        status="approved", exam_type="VSTEP_B1", language="EN"))
        # q3,q4: cùng nội dung, đáp án MÂU THUẪN (phải cờ)
        for ans in ("A", "C"):
            db.add(Question(exam_id=None, group_id=None, part=1, type="choice",
                            content="arrive ___ the destination",
                            options={"A": "at", "C": "on"}, reference_answer=ans,
                            status="approved", exam_type="VSTEP_B1", language="EN"))
        db.commit()

        issues = find_b1_bank_issues(db, static_root=static_root)

        # audio thiếu bị cờ; audio tốt KHÔNG bị cờ
        assert any(i["type"] == "audio" and i["why"] == "missing" for i in issues)
        assert not any(i["type"] == "audio" and "good.wav" in i.get("path", "") for i in issues)
        # đáp án mâu thuẫn bị cờ
        conflicts = [i for i in issues if i["type"] == "conflicting_answer"]
        assert len(conflicts) == 1
        assert conflicts[0]["answers"] == ["A", "C"]
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
