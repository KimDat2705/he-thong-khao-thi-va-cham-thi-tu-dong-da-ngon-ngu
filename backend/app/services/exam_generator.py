import random
from sqlalchemy.orm import Session
from app.models.exam import Exam
from app.models.question import Question
from app.models.question_group import QuestionGroup
from app.services import exam_validator

class InsufficientBankError(ValueError):
    """Raised when the question bank does not have enough questions to generate an exam."""
    pass

VSTEP_B1_BLUEPRINT = {
    "exam_type": "VSTEP_B1",
    "language": "EN",
    "parts": {
        "1": {
            "type": "standalone",
            "count": 10
        },
        "2": {
            "type": "standalone",
            "count": 5
        },
        "3": {
            "type": "grouped",
            "groups": 1,
            "q_per_group": 5
        },
        "4": {
            "type": "grouped",
            "groups": 1,
            "q_per_group": 10
        },
        "5": {
            "type": "standalone",
            "count": 1
        },
        "6": {
            "type": "standalone",
            "count": 1
        },
        "7": {
            "type": "standalone",
            "count": 5
        },
        "8": {
            "type": "grouped",
            "groups": 1,
            "q_per_group": 10
        },
        "9": {
            "type": "standalone",
            "count": 1
        },
        "10": {
            "type": "standalone",
            "count": 1
        },
        "11": {
            "type": "standalone",
            "count": 1
        }
    },
    "balance_answers": False
}

def generate_exam(db: Session, structure: dict, title: str, duration_minutes: int = 120, seed: int = None) -> Exam:
    """
    Generates an exam dynamically based on the provided Blueprint structure dict.
    """
    local_random = random.Random(seed)
    parts_config = structure.get("parts", {})
    exam_type = structure.get("exam_type", "VSTEP_B1")
    bank_exam_type = exam_type

    # --- Pre-check bank sufficiency (Fail-Fast) ---
    for part_str, part_spec in parts_config.items():
        part = int(part_str)
        part_type = part_spec.get("type")

        if part_type == "standalone":
            available_count = db.query(Question).filter(
                Question.exam_id.is_(None),
                Question.group_id.is_(None),
                Question.part == part,
                Question.status == "approved",
                Question.exam_type == bank_exam_type
            ).count()
            needed = part_spec.get("count", 0)
            if available_count < needed:
                raise InsufficientBankError(
                    f"Insufficient questions in bank for Part {part}: needed {needed}, available {available_count}"
                )
        elif part_type == "grouped":
            available_groups = db.query(QuestionGroup).filter(
                QuestionGroup.exam_id.is_(None),
                QuestionGroup.part == part,
                QuestionGroup.status == "approved"
            ).join(QuestionGroup.questions).filter(Question.exam_type == bank_exam_type).distinct().count()
            needed = part_spec.get("groups", 0)
            if available_groups < needed:
                raise InsufficientBankError(
                    f"Insufficient groups in bank for Part {part}: needed {needed}, available {available_groups}"
                )

    # --- Create the Exam (Only after all pre-checks pass) ---
    new_exam = Exam(
        title=title,
        language=structure.get("language", "EN"),
        exam_type=structure.get("exam_type", "VSTEP_B1"),
        duration_minutes=duration_minutes,
        is_active=True
    )
    db.add(new_exam)
    db.commit()
    db.refresh(new_exam)

    # Defensive hygiene: a freshly-allocated exam id can collide with ORPHAN clones —
    # questions/groups whose exam row was deleted without cascading, leaving exam_id set
    # to an id that SQLite later reuses. Such orphans would be miscounted by the post-check
    # validator as belonging to THIS exam (silent doubling -> ExamValidationError). Clear any
    # stale rows claiming this exam id before cloning. No-op on a clean database.
    db.query(Question).filter(Question.exam_id == new_exam.id).delete(synchronize_session=False)
    db.query(QuestionGroup).filter(QuestionGroup.exam_id == new_exam.id).delete(synchronize_session=False)
    db.commit()

    # Helper function to clone a question
    def clone_question(orig_q: Question, target_group_id: int = None) -> Question:
        return Question(
            exam_id=new_exam.id,
            group_id=target_group_id,
            part=orig_q.part,
            type=orig_q.type or "choice",
            content=orig_q.content,
            audio_url=orig_q.audio_url,
            image_url=orig_q.image_url,
            options=orig_q.options,
            reference_answer=orig_q.reference_answer,
            difficulty=orig_q.difficulty or "medium",
            clo=orig_q.clo,
            topic=orig_q.topic,
            status="approved",
            explanation=orig_q.explanation,
            source_question_id=orig_q.id,  # Link to the original question
            exam_type=orig_q.exam_type,
            language=orig_q.language
        )

    # Helper function to clone a group and its questions
    def clone_group(orig_g: QuestionGroup) -> QuestionGroup:
        cloned_g = QuestionGroup(
            exam_id=new_exam.id,
            part=orig_g.part,
            topic=orig_g.topic,
            passage_text=orig_g.passage_text,
            audio_url=orig_g.audio_url,
            image_url=orig_g.image_url,
            passage_type=orig_g.passage_type,
            speaker_count=orig_g.speaker_count,
            speech_rate=orig_g.speech_rate,
            accent=orig_g.accent,
            difficulty=orig_g.difficulty or "medium",
            status="approved"
        )
        db.add(cloned_g)
        db.commit()
        db.refresh(cloned_g)

        # Clone questions belonging to this group
        for orig_q in orig_g.questions:
            db.add(clone_question(orig_q, cloned_g.id))
        db.commit()
        return cloned_g

    # --- Select and Clone each Part ---
    for part_str in sorted(parts_config.keys(), key=int):
        part = int(part_str)
        part_spec = parts_config[part_str]
        part_type = part_spec.get("type")

        if part_type == "standalone":
            # Query all available standalone questions for this part from the bank
            bank_qs = db.query(Question).filter(
                Question.exam_id.is_(None),
                Question.group_id.is_(None),
                Question.part == part,
                Question.status == "approved",
                Question.exam_type == bank_exam_type
            ).order_by(Question.id).all()

            needed = part_spec.get("count", 0)
            if len(bank_qs) >= needed:
                selected_qs = local_random.sample(bank_qs, needed)
            else:
                selected_qs = bank_qs

            # Clone them
            for q in selected_qs:
                db.add(clone_question(q))
            db.commit()

        elif part_type == "grouped":
            # Query all available groups for this part from the bank
            bank_groups = db.query(QuestionGroup).filter(
                QuestionGroup.exam_id.is_(None),
                QuestionGroup.part == part,
                QuestionGroup.status == "approved"
            ).join(QuestionGroup.questions).filter(Question.exam_type == bank_exam_type).distinct().order_by(QuestionGroup.id).all()

            needed = part_spec.get("groups", 0)
            if len(bank_groups) >= needed:
                selected_groups = local_random.sample(bank_groups, needed)
            else:
                selected_groups = bank_groups

            # Clone the groups and their questions
            for g in selected_groups:
                clone_group(g)

    db.refresh(new_exam)

    # Post-check validation
    report = exam_validator.validate_exam(db, new_exam.id, structure)
    if not report["is_valid"]:
        # Con first, cha next
        db.query(Question).filter(Question.exam_id == new_exam.id).delete(synchronize_session=False)
        db.query(QuestionGroup).filter(QuestionGroup.exam_id == new_exam.id).delete(synchronize_session=False)
        db.query(Exam).filter(Exam.id == new_exam.id).delete(synchronize_session=False)
        db.commit()

        errors_summary = "; ".join(report["errors"])
        raise exam_validator.ExamValidationError(f"Exam validation failed: {errors_summary}")

    return new_exam


def generate_batch(db: Session, structure: dict, count: int, base_seed: int = None, max_overlap_limit: float = 0.40) -> dict:
    """
    Generates a batch of count exams using seeds derived from base_seed.
    Enforces overlap <= max_overlap_limit sequentially.
    Rejected candidates are deleted and resampled within a total budget of 10*count attempts.
    """
    if count <= 0:
        raise ValueError("Batch count must be greater than 0")

    original_expire = db.expire_on_commit
    db.expire_on_commit = False

    max_attempts = 10 * count

    # Generate distinct candidate seeds deterministically
    if base_seed is not None:
        rng = random.Random(base_seed)
        candidate_seeds = [rng.randint(0, 1000000) for _ in range(max_attempts)]
    else:
        candidate_seeds = [None] * max_attempts

    # Calculate expected total questions from the blueprint structure
    expected_total = 0
    for part_str, part_spec in structure.get("parts", {}).items():
        part_type = part_spec.get("type")
        if part_type == "standalone":
            expected_total += part_spec.get("count", 0)
        elif part_type == "grouped":
            expected_total += part_spec.get("groups", 0) * part_spec.get("q_per_group", 0)

    accepted_exams = []
    accepted_source_sets = []
    resample_count = 0
    attempt = 0

    try:
        while len(accepted_exams) < count and attempt < max_attempts:
            seed = candidate_seeds[attempt]
            attempt += 1

            try:
                # Try to generate candidate exam
                candidate = generate_exam(db, structure, title=f"Đề {len(accepted_exams) + 1} (Batch)", duration_minutes=120, seed=seed)
            except (InsufficientBankError, exam_validator.ExamValidationError):
                resample_count += 1
                continue

            # Retrieve source sets to compute overlap
            qs = db.query(Question).filter(Question.exam_id == candidate.id).all()
            candidate_sources = {q.source_question_id for q in qs if q.source_question_id is not None}

            # Check overlap against all previously accepted exams in the batch
            is_overlapping = False
            for prev_set in accepted_source_sets:
                common = len(candidate_sources & prev_set)
                overlap_ratio = common / expected_total if expected_total > 0 else 0.0
                if overlap_ratio > max_overlap_limit:
                    is_overlapping = True
                    break

            if is_overlapping:
                # Overlap exceeded limit, delete candidate and try again
                db.query(Question).filter(Question.exam_id == candidate.id).delete(synchronize_session=False)
                db.query(QuestionGroup).filter(QuestionGroup.exam_id == candidate.id).delete(synchronize_session=False)
                db.query(Exam).filter(Exam.id == candidate.id).delete(synchronize_session=False)
                db.commit()
                db.expunge_all()
                resample_count += 1
                continue

            # Accepted candidate
            accepted_exams.append(candidate)
            accepted_source_sets.append(candidate_sources)

    except Exception as e:
        # Atomic rollback of all accepted exams in this batch session
        for exam in accepted_exams:
            db.query(Question).filter(Question.exam_id == exam.id).delete(synchronize_session=False)
            db.query(QuestionGroup).filter(QuestionGroup.exam_id == exam.id).delete(synchronize_session=False)
            db.query(Exam).filter(Exam.id == exam.id).delete(synchronize_session=False)
        db.commit()
        db.expunge_all()
        raise e
    finally:
        db.expire_on_commit = original_expire

    if len(accepted_exams) < count:
        # Budget exhausted, clean up accepted exams and raise validation error
        for exam in accepted_exams:
            db.query(Question).filter(Question.exam_id == exam.id).delete(synchronize_session=False)
            db.query(QuestionGroup).filter(QuestionGroup.exam_id == exam.id).delete(synchronize_session=False)
            db.query(Exam).filter(Exam.id == exam.id).delete(synchronize_session=False)
        db.commit()
        db.expunge_all()
        raise exam_validator.ExamValidationError(
            f"Exhausted attempt budget ({max_attempts}) without satisfying overlap limit (<= {max_overlap_limit:.1%}). "
            f"Only generated {len(accepted_exams)} of {count} exams."
        )

    # Compute final pairwise overlaps report
    pairwise_overlaps = []
    max_overlap = 0.0
    sum_overlap = 0.0
    pair_count = 0

    for i in range(len(accepted_source_sets)):
        for j in range(i + 1, len(accepted_source_sets)):
            exam_a, set_a = accepted_exams[i], accepted_source_sets[i]
            exam_b, set_b = accepted_exams[j], accepted_source_sets[j]
            common = len(set_a & set_b)
            overlap_ratio = common / expected_total if expected_total > 0 else 0.0

            pairwise_overlaps.append({
                "exam_1_id": exam_a.id,
                "exam_1_title": exam_a.title,
                "exam_2_id": exam_b.id,
                "exam_2_title": exam_b.title,
                "overlap_ratio": round(overlap_ratio, 4),
                "common_questions_count": common
            })

            if overlap_ratio > max_overlap:
                max_overlap = overlap_ratio
            sum_overlap += overlap_ratio
            pair_count += 1

    avg_overlap = sum_overlap / pair_count if pair_count > 0 else 0.0

    overlap_report = {
        "pairwise_overlaps": pairwise_overlaps,
        "max_overlap": round(max_overlap, 4),
        "average_overlap": round(avg_overlap, 4),
        "threshold": max_overlap_limit,
        "resample_count": resample_count
    }

    return {
        "exams": accepted_exams,
        "overlap_report": overlap_report
    }
