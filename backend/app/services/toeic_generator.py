import random
from sqlalchemy.orm import Session
from app.models.exam import Exam
from app.models.question import Question
from app.models.question_group import QuestionGroup
from app.services import exam_validator

class InsufficientBankError(ValueError):
    """Raised when the question bank does not have enough questions to generate an exam."""
    pass

TOEIC_BLUEPRINT = {
    "exam_type": "TOEIC",
    "language": "EN",
    "parts": {
        "1": {
            "type": "standalone",
            "count": 6,
            "difficulty": {"easy": 2, "medium": 3, "hard": 1}
        },
        "2": {
            "type": "standalone",
            "count": 25,
            "difficulty": {"easy": 6, "medium": 13, "hard": 6}
        },
        "3": {
            "type": "grouped",
            "groups": 13,
            "q_per_group": 3,
            "difficulty": {"easy": 3, "medium": 7, "hard": 3}
        },
        "4": {
            "type": "grouped",
            "groups": 10,
            "q_per_group": 3,
            "difficulty": {"easy": 2, "medium": 5, "hard": 3}
        },
        "5": {
            "type": "standalone",
            "count": 30,
            "difficulty": {"easy": 8, "medium": 15, "hard": 7}
        },
        "6": {
            "type": "grouped",
            "groups": 4,
            "q_per_group": 4,
            "difficulty": {"easy": 1, "medium": 2, "hard": 1}
        },
        "7": {
            "type": "subset_sum",
            "target_questions": 54,
            "difficulty": {"easy": 9, "medium": 28, "hard": 17}
        }
    },
    "balance_answers": True
}

def generate_toeic_exam(db: Session, title: str, duration_minutes: int = 120, seed: int = None) -> Exam:
    """
    Wrapper for generating a TOEIC exam using the standard TOEIC blueprint.
    """
    return generate_exam(db, TOEIC_BLUEPRINT, title, duration_minutes, seed)

def generate_exam(db: Session, structure: dict, title: str, duration_minutes: int = 120, seed: int = None) -> Exam:
    """
    Generates an exam dynamically based on the provided Blueprint structure dict.
    """
    local_random = random.Random(seed)
    parts_config = structure.get("parts", {})

    # --- Pre-check bank sufficiency (Fail-Fast) ---
    for part_str, part_spec in parts_config.items():
        part = int(part_str)
        part_type = part_spec.get("type")
        
        if part_type == "standalone":
            available_count = db.query(Question).filter(
                Question.exam_id.is_(None),
                Question.group_id.is_(None),
                Question.part == part,
                Question.status == "approved"
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
            ).count()
            needed = part_spec.get("groups", 0)
            if available_groups < needed:
                raise InsufficientBankError(
                    f"Insufficient groups in bank for Part {part}: needed {needed}, available {available_groups}"
                )
        elif part_type == "subset_sum":
            p_groups_in_bank = db.query(QuestionGroup).filter(
                QuestionGroup.exam_id.is_(None),
                QuestionGroup.part == part,
                QuestionGroup.status == "approved"
            ).all()
            total_qs = sum(len(g.questions) for g in p_groups_in_bank)
            needed = part_spec.get("target_questions", 0)
            if total_qs < needed:
                raise InsufficientBankError(
                    f"Insufficient questions in bank for Part {part}: needed {needed}, available {total_qs}"
                )

    # --- Create the Exam (Only after all pre-checks pass) ---
    new_exam = Exam(
        title=title,
        language=structure.get("language", "EN"),
        exam_type=structure.get("exam_type", "TOEIC"),
        duration_minutes=duration_minutes,
        is_active=True
    )
    db.add(new_exam)
    db.commit()
    db.refresh(new_exam)

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
            source_question_id=orig_q.id  # Link to the original question
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

    # Helper to validate topic diversity constraint
    def is_topic_distribution_valid(groups):
        if not groups:
            return True
        total_qs = sum(len(g.questions) for g in groups)
        if total_qs == 0:
            return True
        max_group = max(len(g.questions) for g in groups)
        cap = max(0.20, max_group / total_qs)
        
        topic_counts = {}
        for g in groups:
            topic = g.topic
            q_count = len(g.questions)
            topic_counts[topic] = topic_counts.get(topic, 0) + q_count
            
        for topic, count in topic_counts.items():
            if count / total_qs > cap + 1e-9:
                return False
        return True

    # Backtracking selection for Part 3, 4, 6
    def select_groups_for_part(easy_groups, medium_groups, hard_groups, part_spec):
        local_random.shuffle(easy_groups)
        local_random.shuffle(medium_groups)
        local_random.shuffle(hard_groups)
        
        target_easy = part_spec.get("difficulty", {}).get("easy", 0)
        target_medium = part_spec.get("difficulty", {}).get("medium", 0)
        target_hard = part_spec.get("difficulty", {}).get("hard", 0)
        total_needed = part_spec.get("groups", 0)
        
        n_easy = min(len(easy_groups), target_easy)
        n_medium = min(len(medium_groups), target_medium)
        n_hard = min(len(hard_groups), target_hard)
        
        shortfall = total_needed - (n_easy + n_medium + n_hard)
        
        def get_combinations(items, k):
            if k == 0:
                yield []
                return
            if not items:
                return
            for c in get_combinations(items[1:], k - 1):
                yield [items[0]] + c
            for c in get_combinations(items[1:], k):
                yield c

        for easy_comb in get_combinations(easy_groups, n_easy):
            leftover_easy = [g for g in easy_groups if g not in easy_comb]
            for med_comb in get_combinations(medium_groups, n_medium):
                leftover_med = [g for g in medium_groups if g not in med_comb]
                for hard_comb in get_combinations(hard_groups, n_hard):
                    leftover_hard = [g for g in hard_groups if g not in hard_comb]
                    
                    base_selection = easy_comb + med_comb + hard_comb
                    
                    if shortfall > 0:
                        leftover_pool = leftover_easy + leftover_med + leftover_hard
                        for shortfall_comb in get_combinations(leftover_pool, shortfall):
                            candidate = base_selection + shortfall_comb
                            if is_topic_distribution_valid(candidate):
                                return candidate
                    else:
                        if is_topic_distribution_valid(base_selection):
                            return base_selection
        return None

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
                Question.status == "approved"
            ).order_by(Question.id).all()

            # Group by difficulty
            diff_map = {"easy": [], "medium": [], "hard": []}
            for q in bank_qs:
                diff = (q.difficulty or "medium").lower()
                if diff in diff_map:
                    diff_map[diff].append(q)
                else:
                    diff_map["medium"].append(q)

            selected_qs = []
            diff_spec = part_spec.get("difficulty", {})
            for diff in ["easy", "medium", "hard"]:
                needed = diff_spec.get(diff, 0)
                available = diff_map[diff]
                if len(available) >= needed:
                    selected_qs.extend(local_random.sample(available, needed))
                else:
                    selected_qs.extend(available)

            # Fill shortfall
            still_needed = part_spec.get("count", 0) - len(selected_qs)
            if still_needed > 0:
                remaining = [q for q in bank_qs if q not in selected_qs]
                if len(remaining) >= still_needed:
                    selected_qs.extend(local_random.sample(remaining, still_needed))
                else:
                    selected_qs.extend(remaining)

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
            ).order_by(QuestionGroup.id).all()

            # Group by difficulty
            diff_map = {"easy": [], "medium": [], "hard": []}
            for g in bank_groups:
                diff = (g.difficulty or "medium").lower()
                if diff in diff_map:
                    diff_map[diff].append(g)
                else:
                    diff_map["medium"].append(g)

            selected_groups = select_groups_for_part(
                diff_map["easy"], diff_map["medium"], diff_map["hard"],
                part_spec
            )
            if selected_groups is None:
                raise InsufficientBankError(
                    f"Insufficient questions in bank for Part {part}: "
                    f"could not find a combination of groups satisfying the topic diversity constraints"
                )

            # Clone the groups and their questions
            for g in selected_groups:
                clone_group(g)

        elif part_type == "subset_sum":
            part_groups = db.query(QuestionGroup).filter(
                QuestionGroup.exam_id.is_(None),
                QuestionGroup.part == part,
                QuestionGroup.status == "approved"
            ).order_by(QuestionGroup.id).all()

            # Shuffle to ensure randomness, using local_random for reproducibility
            local_random.shuffle(part_groups)

            target_qs = part_spec.get("target_questions", 0)

            # Use backtracking to find a subset of groups that sum to exactly target_qs and satisfy topic cap
            def find_subset_sum(groups, target, start_idx=0, current_sum=0, path=None):
                if path is None:
                    path = []
                    
                # Early pruning: calculate allowed count dynamically based on current max group size
                max_group_sz = max(len(g.questions) for g in groups) if groups else 5
                cap = max(0.20, max_group_sz / target)
                max_allowed = int(target * cap + 1e-9)
                
                topic_counts = {}
                for g in path:
                    topic = g.topic
                    topic_counts[topic] = topic_counts.get(topic, 0) + len(g.questions)
                    if topic_counts[topic] > max_allowed:
                        return None
                        
                if current_sum == target:
                    if is_topic_distribution_valid(path):
                        return path
                    return None
                if current_sum > target or start_idx >= len(groups):
                    return None
                
                # Try including the current group
                g = groups[start_idx]
                g_q_count = len(g.questions)
                if g_q_count > 0:
                    result = find_subset_sum(groups, target, start_idx + 1, current_sum + g_q_count, path + [g])
                    if result is not None:
                        return result
                        
                # Try excluding the current group
                return find_subset_sum(groups, target, start_idx + 1, current_sum, path)

            selected_p_groups = find_subset_sum(part_groups, target_qs)

            if selected_p_groups is None:
                raise InsufficientBankError(
                    f"Insufficient questions in bank for Part {part}: could not find a combination of groups summing to exactly {target_qs} questions satisfying the topic diversity constraints"
                )

            # Clone selected groups
            for g in selected_p_groups:
                clone_group(g)

    # --- Balance correct answers (A/B/C/D) ---
    if structure.get("balance_answers", False):
        # Query all cloned questions of the exam
        cloned_qs = db.query(Question).filter(Question.exam_id == new_exam.id).all()
        # Identify 4-option questions
        four_option_qs = [
            q for q in cloned_qs
            if isinstance(q.options, dict) and len(q.options) == 4 and q.reference_answer
        ]
        # Sort them by Question.id for stability and reproducibility
        four_option_qs = sorted(four_option_qs, key=lambda q: q.id)
        
        n_qs = len(four_option_qs)
        if n_qs > 0:
            # Generate balanced target letters
            target_letters = ["A", "B", "C", "D"] * (n_qs // 4) + ["A", "B", "C", "D"][:n_qs % 4]
            # Shuffle target letters using local_random for reproducibility
            local_random.shuffle(target_letters)
            
            # Permute options for each question
            for i, q in enumerate(four_option_qs):
                target_ans = target_letters[i]
                orig_ans = q.reference_answer.strip().upper()
                
                # Reconstruct options with new answer letter
                correct_text = q.options.get(orig_ans)
                if correct_text is not None:
                    incorrect_texts = [q.options[letter] for letter in ["A", "B", "C", "D"] if letter != orig_ans]
                    # Shuffle incorrect options using local_random
                    local_random.shuffle(incorrect_texts)
                    
                    # Reconstruct options dict
                    new_options = {}
                    inc_idx = 0
                    for letter in ["A", "B", "C", "D"]:
                        if letter == target_ans:
                            new_options[letter] = correct_text
                        else:
                            new_options[letter] = incorrect_texts[inc_idx]
                            inc_idx += 1
                            
                    q.options = new_options
                    q.reference_answer = target_ans
            db.commit()

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
