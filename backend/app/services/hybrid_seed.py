"""SPEC-BANK-007: Hybrid Seed & Paraphrase.

Store vetted "seed" questions (status='seed') from authoritative sources as an
academic reference (AC1), then use AI to paraphrase them into fresh draft variants —
rewording the stem and distractors (AC2), regenerating illustrations for picture
items (AC3), and AI-labelling difficulty against CEFR B1 (AC4). The bank grows
without reproducing the original wording/image (copyright-safe) while each variant
stays pedagogically anchored to its seed via source_question_id.

Seeds live in the frozen Question model (no schema change): a seed is a bank row
(exam_id IS NULL) with status='seed'; it is never used verbatim in an exam — only
its paraphrased drafts (status='draft') are, after teacher approval.
"""
import logging

from sqlalchemy.orm import Session

from app.models.question import Question
from app.services.parser import calculate_question_hash

logger = logging.getLogger(__name__)

SEED_STATUS = "seed"


def create_seed_question(
    db: Session,
    part: int,
    qtype: str,
    content: str,
    options: dict,
    reference_answer: str,
    topic: str = None,
    difficulty: str = None,
    image_url: str = None,
) -> Question:
    """AC1: store a vetted seed question (status='seed'). Idempotent by content_hash."""
    if qtype != "choice" or not isinstance(options, dict) or len(options) < 2:
        raise ValueError("Seed phải là câu trắc nghiệm (choice) có >= 2 phương án.")
    if reference_answer not in options:
        raise ValueError("reference_answer phải nằm trong options.")
    content = (content or "").strip()
    if not content:
        raise ValueError("content không được rỗng.")

    # set_id='seed' keeps a seed's hash distinct from a paraphrased draft's, so a seed
    # never collides with (or is dedup-skipped by) its own variants.
    q_hash = calculate_question_hash({
        "set_id": "seed", "number": "", "part": part, "type": "choice",
        "content": content, "options": options, "reference_answer": reference_answer,
    })
    existing = db.query(Question).filter(
        Question.exam_id.is_(None), Question.content_hash == q_hash
    ).first()
    if existing:
        return existing

    seed = Question(
        exam_id=None, group_id=None, part=part, type="choice",
        content=content, options=options, reference_answer=reference_answer,
        difficulty=difficulty, topic=topic, status=SEED_STATUS,
        content_hash=q_hash, exam_type="VSTEP_B1", language="EN", image_url=image_url,
    )
    db.add(seed)
    db.commit()
    db.refresh(seed)
    return seed


def paraphrase_seed(db: Session, seed_question_id: int, count: int) -> dict:
    """AC2/AC3/AC4: paraphrase a bank seed into `count` fresh draft variants."""
    seed = db.query(Question).filter(
        Question.id == seed_question_id, Question.exam_id.is_(None)
    ).first()
    if seed is None:
        raise LookupError("Không tìm thấy câu seed trong ngân hàng.")

    from app.services.b1_question_gen import B1QuestionGenerator

    generator = B1QuestionGenerator()
    generated = generator.paraphrase_from_seed(db, seed, count)
    return {"success": True, "generated_count": generated, "seed_question_id": seed_question_id}
