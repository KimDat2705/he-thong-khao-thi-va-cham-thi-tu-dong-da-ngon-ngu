from sqlalchemy.orm import Session

from app.models.question import Question
from app.models.question_group import QuestionGroup

class ExamValidationError(ValueError):
    """Raised when post-check validation fails for a generated exam."""
    pass

def validate_exam(db: Session, exam_id: int, structure: dict) -> dict:
    """
    Validates a generated exam against business constraints.
    Returns a report dictionary containing detailed validation errors if any.
    """
    questions = db.query(Question).filter(Question.exam_id == exam_id).all()
    groups = db.query(QuestionGroup).filter(QuestionGroup.exam_id == exam_id).all()
    
    qs_by_part = {}
    for q in questions:
        qs_by_part.setdefault(q.part, []).append(q)
        
    groups_by_part = {}
    for g in groups:
        groups_by_part.setdefault(g.part, []).append(g)
        
    report = {
        "is_valid": True,
        "errors": [],
        "details": {
            "GEN_001": {"valid": True, "errors": []},
            "MATRIX_002": {"valid": True, "errors": []},
            "GEN_003": {"valid": True, "errors": []},
            "GEN_002": {"valid": True, "errors": []},
            "ISOLATE_003": {"valid": True, "errors": []},
        }
    }
    
    def add_error(key: str, msg: str):
        report["is_valid"] = False
        report["errors"].append(msg)
        report["details"][key]["valid"] = False
        report["details"][key]["errors"].append(msg)
        
    # --- 1. GEN-001 (Blueprint Part Counts) ---
    expected_total = 0
    parts_config = structure.get("parts", {})
    
    for part_str, part_spec in parts_config.items():
        part = int(part_str)
        part_type = part_spec.get("type")
        
        if part_type == "standalone":
            expected_count = part_spec.get("count", 0)
            expected_total += expected_count
            actual_count = len(qs_by_part.get(part, []))
            if actual_count != expected_count:
                add_error(
                    "GEN_001",
                    f"Part {part} (standalone): expected {expected_count} questions, got {actual_count}"
                )
                
        elif part_type == "grouped":
            expected_groups = part_spec.get("groups", 0)
            q_per_group = part_spec.get("q_per_group", 0)
            expected_count = expected_groups * q_per_group
            expected_total += expected_count
            
            actual_groups = groups_by_part.get(part, [])
            actual_questions = qs_by_part.get(part, [])
            
            if len(actual_groups) != expected_groups:
                add_error(
                    "GEN_001",
                    f"Part {part} (grouped): expected {expected_groups} groups, got {len(actual_groups)}"
                )
            if len(actual_questions) != expected_count:
                add_error(
                    "GEN_001",
                    f"Part {part} (grouped): expected {expected_count} questions in total, got {len(actual_questions)}"
                )
            for g in actual_groups:
                # Count associated questions belonging to this exam
                g_qs = [q for q in actual_questions if q.group_id == g.id]
                if len(g_qs) != q_per_group:
                    add_error(
                        "GEN_001",
                        f"Part {part} (grouped) Group {g.id}: expected {q_per_group} questions, got {len(g_qs)}"
                    )
                    
        elif part_type == "subset_sum":
            expected_count = part_spec.get("target_questions", 0)
            expected_total += expected_count
            actual_questions = qs_by_part.get(part, [])
            if len(actual_questions) != expected_count:
                add_error(
                    "GEN_001",
                    f"Part {part} (subset_sum): expected {expected_count} questions, got {len(actual_questions)}"
                )
                
    if len(questions) != expected_total:
        add_error(
            "GEN_001",
            f"Total exam questions: expected {expected_total}, got {len(questions)}"
        )
        
    # --- 2. MATRIX-002 (Per-part Difficulty) ---
    for part_str, part_spec in parts_config.items():
        part = int(part_str)
        part_type = part_spec.get("type")
        difficulty_spec = part_spec.get("difficulty")
        
        # Skip subset_sum (Part 7) entirely from difficulty checks
        if part_type == "subset_sum":
            continue
            
        if not difficulty_spec:
            continue
            
        if part_type == "standalone":
            part_qs = qs_by_part.get(part, [])
            actual_diff_counts = {"easy": 0, "medium": 0, "hard": 0}
            for q in part_qs:
                diff = (q.difficulty or "medium").lower()
                if diff in actual_diff_counts:
                    actual_diff_counts[diff] += 1
            for diff, expected in difficulty_spec.items():
                if actual_diff_counts.get(diff, 0) != expected:
                    add_error(
                        "MATRIX_002",
                        f"Part {part} (standalone) difficulty '{diff}': expected {expected}, got {actual_diff_counts.get(diff, 0)}"
                    )
                    
        elif part_type == "grouped":
            part_groups = groups_by_part.get(part, [])
            actual_diff_counts = {"easy": 0, "medium": 0, "hard": 0}
            for g in part_groups:
                diff = (g.difficulty or "medium").lower()
                if diff in actual_diff_counts:
                    actual_diff_counts[diff] += 1
            for diff, expected in difficulty_spec.items():
                if actual_diff_counts.get(diff, 0) != expected:
                    add_error(
                        "MATRIX_002",
                        f"Part {part} (grouped) difficulty '{diff}': expected {expected}, got {actual_diff_counts.get(diff, 0)}"
                    )
                    
    # --- 3. GEN-003 (Topic Diversity) ---
    for part_str, part_spec in parts_config.items():
        part = int(part_str)
        part_groups = groups_by_part.get(part, [])
        
        if not part_groups:
            continue
            
        # Total questions in this part
        part_qs = qs_by_part.get(part, [])
        part_total = len(part_qs)
        if part_total == 0:
            continue
            
        # Max group size in this part (using questions belonging to the exam)
        group_sizes = []
        for g in part_groups:
            g_qs_count = sum(1 for q in part_qs if q.group_id == g.id)
            group_sizes.append(g_qs_count)
            
        max_group_size = max(group_sizes) if group_sizes else 5
        cap = max(0.20, max_group_size / part_total)
        
        # Count questions per topic in this part
        topic_counts = {}
        for g in part_groups:
            topic = g.topic or "(không có chủ đề)"
            g_qs_count = sum(1 for q in part_qs if q.group_id == g.id)
            topic_counts[topic] = topic_counts.get(topic, 0) + g_qs_count
            
        for topic, count in topic_counts.items():
            ratio = count / part_total
            if ratio > cap + 1e-9:
                add_error(
                    "GEN_003",
                    f"Part {part} topic '{topic}': ratio {ratio:.1%} exceeds cap {cap:.1%} ({count}/{part_total} questions)"
                )
                
    # --- 4. GEN-002 (Answer Balance) ---
    if structure.get("balance_answers", False):
        four_option_qs = [
            q for q in questions
            if isinstance(q.options, dict) and len(q.options) == 4 and q.reference_answer
        ]
        n_four_opt = len(four_option_qs)
        if n_four_opt > 0:
            ans_counts = {"A": 0, "B": 0, "C": 0, "D": 0}
            for q in four_option_qs:
                ans = q.reference_answer.strip().upper()
                if ans in ans_counts:
                    ans_counts[ans] += 1
                    
            for letter, count in ans_counts.items():
                ratio = count / n_four_opt
                if not (0.20 <= ratio <= 0.28):
                    add_error(
                        "GEN_002",
                        f"Correct answer '{letter}': ratio {ratio:.1%} is outside range [20%, 28%] ({count}/{n_four_opt} questions)"
                    )
                    
    # --- 5. ISOLATE-003 (Group Isolation & Orphans) ---
    groups_map = {g.id: g for g in groups}
    
    for q in questions:
        if q.exam_id != exam_id:
            add_error(
                "ISOLATE_003",
                f"Question {q.id} has incorrect exam_id: expected {exam_id}, got {q.exam_id}"
            )
        if q.group_id is not None:
            g = groups_map.get(q.group_id)
            if not g:
                add_error(
                    "ISOLATE_003",
                    f"Question {q.id} refers to group {q.group_id} not belonging to the exam"
                )
            else:
                if g.exam_id != exam_id:
                    add_error(
                        "ISOLATE_003",
                        f"Group {g.id} of question {q.id} has incorrect exam_id: expected {exam_id}, got {g.exam_id}"
                    )
                if g.part != q.part:
                    add_error(
                        "ISOLATE_003",
                        f"Group {g.id} (part {g.part}) does not match question {q.id} (part {q.part})"
                    )
                    
    for g in groups:
        if g.exam_id != exam_id:
            add_error(
                "ISOLATE_003",
                f"Group {g.id} has incorrect exam_id: expected {exam_id}, got {g.exam_id}"
            )
        # Check if group has at least one question in the exam
        g_qs = [q for q in questions if q.group_id == g.id]
        if not g_qs:
            add_error(
                "ISOLATE_003",
                f"Group {g.id} in exam has 0 questions"
            )
            
    # Check that grouped/subset_sum parts have no orphan questions
    for part_str, part_spec in parts_config.items():
        part = int(part_str)
        part_type = part_spec.get("type")
        if part_type in ("grouped", "subset_sum"):
            part_qs = qs_by_part.get(part, [])
            for q in part_qs:
                if q.group_id is None:
                    add_error(
                        "ISOLATE_003",
                        f"Question {q.id} in part {part} ({part_type}) does not have a group"
                    )
                    
    return report
