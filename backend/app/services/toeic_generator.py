import random
from sqlalchemy.orm import Session
from app.models.exam import Exam
from app.models.question import Question
from app.models.question_group import QuestionGroup

class InsufficientBankError(ValueError):
    """Raised when the question bank does not have enough questions to generate an exam."""
    pass

def generate_toeic_exam(db: Session, title: str, duration_minutes: int = 120, seed: int = None) -> Exam:
    """
    Generates a TOEIC exam by selecting questions and question groups from the bank
    (where exam_id is None) according to the TOEIC blueprint and difficulty targets.
    Clones the selected questions and groups into a newly created Exam.
    """
    local_random = random.Random(seed)

    # Define the blueprint
    # Format: (part, total_questions_needed, target_difficulty_dict)
    # Target difficulty dict: {"easy": count, "medium": count, "hard": count}
    standalone_blueprint = {
        1: {"count": 6, "easy": 2, "medium": 3, "hard": 1},
        2: {"count": 25, "easy": 6, "medium": 13, "hard": 6},
        5: {"count": 30, "easy": 8, "medium": 15, "hard": 7}
    }

    # Group blueprints (Part 3, 4, 6)
    # Format: (part, groups_needed, questions_per_group, target_groups_by_difficulty)
    group_blueprint = {
        3: {"groups": 13, "q_per_group": 3, "easy_groups": 3, "medium_groups": 7, "hard_groups": 3},
        4: {"groups": 10, "q_per_group": 3, "easy_groups": 2, "medium_groups": 5, "hard_groups": 3},
        6: {"groups": 4, "q_per_group": 4, "easy_groups": 1, "medium_groups": 2, "hard_groups": 1}
    }

    # --- Pre-check bank sufficiency (Fail-Fast) ---
    # 1. Verify standalone counts
    for part, spec in standalone_blueprint.items():
        available_count = db.query(Question).filter(
            Question.exam_id.is_(None),
            Question.group_id.is_(None),
            Question.part == part,
            Question.status == "approved"
        ).count()
        needed = spec["count"]
        if available_count < needed:
            raise InsufficientBankError(
                f"Insufficient questions in bank for Part {part}: needed {needed}, available {available_count}"
            )

    # 2. Verify group counts
    for part, spec in group_blueprint.items():
        available_groups = db.query(QuestionGroup).filter(
            QuestionGroup.exam_id.is_(None),
            QuestionGroup.part == part,
            QuestionGroup.status == "approved"
        ).count()
        needed = spec["groups"]
        if available_groups < needed:
            raise InsufficientBankError(
                f"Insufficient groups in bank for Part {part}: needed {needed}, available {available_groups}"
            )

    # 3. Verify Part 7 total questions
    p7_groups_in_bank = db.query(QuestionGroup).filter(
        QuestionGroup.exam_id.is_(None),
        QuestionGroup.part == 7,
        QuestionGroup.status == "approved"
    ).all()
    p7_total_qs = sum(len(g.questions) for g in p7_groups_in_bank)
    if p7_total_qs < 54:
        raise InsufficientBankError(
            f"Insufficient questions in bank for Part 7: needed 54, available {p7_total_qs}"
        )

    # --- Create the Exam (Only after all pre-checks pass) ---
    new_exam = Exam(
        title=title,
        language="EN",
        exam_type="TOEIC",
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

    # --- Select and Clone Part 1, 2, 5 (Standalone) ---
    for part, spec in standalone_blueprint.items():
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
        # Try to select the target count for each difficulty
        for diff in ["easy", "medium", "hard"]:
            needed = spec[diff]
            available = diff_map[diff]
            if len(available) >= needed:
                selected_qs.extend(local_random.sample(available, needed))
            else:
                # If not enough of this difficulty, take all and fill from other difficulties later
                selected_qs.extend(available)

        # If we still need more questions, fill with any remaining standalone questions
        still_needed = spec["count"] - len(selected_qs)
        if still_needed > 0:
            remaining = [q for q in bank_qs if q not in selected_qs]
            if len(remaining) >= still_needed:
                selected_qs.extend(local_random.sample(remaining, still_needed))
            else:
                selected_qs.extend(remaining)

        # Clone them into the database
        for q in selected_qs:
            db.add(clone_question(q))
        db.commit()

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
    def select_groups_for_part(easy_groups, medium_groups, hard_groups, spec):
        local_random.shuffle(easy_groups)
        local_random.shuffle(medium_groups)
        local_random.shuffle(hard_groups)
        
        target_easy = spec["easy_groups"]
        target_medium = spec["medium_groups"]
        target_hard = spec["hard_groups"]
        total_needed = spec["groups"]
        
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

    # --- Select and Clone Part 3, 4, 6 (Grouped) ---
    for part, spec in group_blueprint.items():
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
            spec
        )
        if selected_groups is None:
            raise InsufficientBankError(
                f"Insufficient questions in bank for Part {part}: "
                f"could not find a combination of groups satisfying the topic diversity constraints"
            )

        # Clone the groups and their questions
        for g in selected_groups:
            clone_group(g)

    # --- Select and Clone Part 7 (Passages totaling 54 questions) ---
    # Part 7 can have groups with varying number of questions (e.g. 2, 3, 4, 5)
    # Target: 54 questions total. Difficulty target: 9 Easy, 28 Medium, 17 Hard.
    part7_groups = db.query(QuestionGroup).filter(
        QuestionGroup.exam_id.is_(None),
        QuestionGroup.part == 7,
        QuestionGroup.status == "approved"
    ).order_by(QuestionGroup.id).all()

    # Shuffle to ensure randomness, using local_random for reproducibility
    local_random.shuffle(part7_groups)

    # Use backtracking to find a subset of groups that sum to exactly 54 questions and satisfy topic cap
    def find_subset_sum(groups, target, start_idx=0, current_sum=0, path=None):
        if path is None:
            path = []
            
        # Early pruning: no topic can exceed 10 questions in a valid 54-question solution
        topic_counts = {}
        for g in path:
            topic = g.topic
            topic_counts[topic] = topic_counts.get(topic, 0) + len(g.questions)
            if topic_counts[topic] > 10:
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

    selected_p7_groups = find_subset_sum(part7_groups, 54)

    if selected_p7_groups is None:
        raise InsufficientBankError(
            "Insufficient questions in bank for Part 7: could not find a combination of groups summing to exactly 54 questions satisfying the topic diversity constraints"
        )

    # Clone selected Part 7 groups
    for g in selected_p7_groups:
        clone_group(g)

    db.refresh(new_exam)
    return new_exam
