import os
import docx
import hashlib
import json
from sqlalchemy.orm import Session
from app.models.import_batch import ImportBatch
from app.models.question import Question
from app.models.question_group import QuestionGroup

class ImportError(Exception):
    """Raised when parsing or validation fails during file import."""
    def __init__(self, message: str, report: dict = None):
        super().__init__(message)
        self.report = report or {}

def calculate_file_hash(filepath: str) -> str:
    """Calculate SHA256 hash of a file's binary content."""
    sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(8192):
            sha256.update(chunk)
    return sha256.hexdigest()

def calculate_group_hash(g_data: dict) -> str:
    """Calculate SHA256 hash of a QuestionGroup's core content."""
    q_contents = "|".join(f"{q.get('content') or ''}" for q in g_data.get("questions", []))
    content_str = f"{g_data.get('set_id') or ''}|{g_data.get('part')}|{g_data.get('passage_text') or ''}|{g_data.get('audio_url') or ''}|{q_contents}"
    return hashlib.sha256(content_str.encode("utf-8")).hexdigest()

def calculate_question_hash(q_data: dict) -> str:
    """Calculate SHA256 hash of a Question's core content."""
    sorted_options = json.dumps(q_data.get("options") or {}, sort_keys=True)
    content_str = f"{q_data.get('set_id') or ''}|{q_data.get('number') or ''}|{q_data.get('part')}|{q_data.get('type')}|{q_data.get('content') or ''}|{sorted_options}|{q_data.get('reference_answer') or ''}"
    return hashlib.sha256(content_str.encode("utf-8")).hexdigest()

def parse_docx(filepath: str) -> list:
    """Parse docx paragraphs into a list of raw block dicts."""
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"File not found: {filepath}")

    doc = docx.Document(filepath)
    blocks = []
    current_block = None

    for paragraph in doc.paragraphs:
        text = paragraph.text.strip()
        if not text:
            continue

        if text in ["[Group]", "[Question]"]:
            if current_block:
                blocks.append(current_block)
            current_block = {"type": text[1:-1], "fields": {}}
        elif current_block and ":" in text:
            parts = text.split(":", 1)
            key = parts[0].strip()
            val = parts[1].strip()
            current_block["fields"][key] = val

    if current_block:
        blocks.append(current_block)

    return blocks

def process_blocks(blocks: list, filepath: str, audio_dir: str) -> list:
    """Validate raw blocks and structure them into parsed groups and questions."""
    parsed_items = []
    current_group = None
    errors = []

    for idx, block in enumerate(blocks):
        b_type = block["type"]
        fields = block["fields"]
        location = f"Block {idx + 1} ({b_type})"

        if b_type == "Group":
            part = fields.get("Part")
            if not part:
                errors.append({
                    "location": location,
                    "type": "missing_part",
                    "message": "Group is missing 'Part' field."
                })
                continue
            try:
                part_val = int(part)
            except ValueError:
                errors.append({
                    "location": location,
                    "type": "invalid_part",
                    "message": f"Group Part '{part}' is not an integer."
                })
                continue

            # Validate audio file existence for Listening (Part 1, 2, 3, 4)
            audio = fields.get("Audio")
            if audio and part_val in [1, 2, 3, 4]:
                audio_path = os.path.join(audio_dir, audio)
                if not os.path.exists(audio_path):
                    errors.append({
                        "location": location,
                        "type": "missing_audio",
                        "message": f"Audio file '{audio}' not found in directory '{audio_dir}'."
                    })

            group_data = {
                "part": part_val,
                "topic": fields.get("Topic"),
                "passage_text": fields.get("Passage"),
                "audio_url": fields.get("Audio"),
                "image_url": fields.get("Image"),
                "difficulty": fields.get("Difficulty", "medium"),
                "questions": []
            }
            current_group = group_data
            parsed_items.append(group_data)

        elif b_type == "Question":
            options = {}
            for opt_key in ["A", "B", "C", "D"]:
                if opt_key in fields:
                    options[opt_key] = fields[opt_key]

            part = fields.get("Part")
            if not part:
                errors.append({
                    "location": location,
                    "type": "missing_part",
                    "message": "Question is missing 'Part' field."
                })
                continue
            try:
                part_val = int(part)
            except ValueError:
                errors.append({
                    "location": location,
                    "type": "invalid_part",
                    "message": f"Question Part '{part}' is not an integer."
                })
                continue

            # Validate audio file existence for Listening (Part 1, 2, 3, 4)
            audio = fields.get("Audio")
            if audio and part_val in [1, 2, 3, 4]:
                audio_path = os.path.join(audio_dir, audio)
                if not os.path.exists(audio_path):
                    errors.append({
                        "location": location,
                        "type": "missing_audio",
                        "message": f"Audio file '{audio}' not found in directory '{audio_dir}'."
                    })

            # Validate options
            if not options:
                errors.append({
                    "location": location,
                    "type": "missing_options",
                    "message": "Question is missing options (A, B, C, D)."
                })

            # Validate answer
            answer = fields.get("Answer")
            if not answer:
                errors.append({
                    "location": location,
                    "type": "missing_answer",
                    "message": "Question is missing 'Answer' field."
                })
            elif answer not in options:
                errors.append({
                    "location": location,
                    "type": "invalid_answer",
                    "message": f"Answer '{answer}' is not in options keys {list(options.keys())}."
                })

            q_data = {
                "part": part_val,
                "type": fields.get("Type", "choice"),
                "content": fields.get("Content", ""),
                "audio_url": fields.get("Audio"),
                "image_url": fields.get("Image"),
                "options": options,
                "reference_answer": answer,
                "difficulty": fields.get("Difficulty", "medium"),
                "clo": fields.get("CLO"),
                "topic": fields.get("Topic"),
                "explanation": fields.get("Explanation")
            }

            # Link question to the current group if it is grouped part and matches current group part
            is_grouped = part_val in [3, 4, 6, 7]
            if is_grouped and current_group and current_group["part"] == part_val:
                current_group["questions"].append(q_data)
            else:
                current_group = None
                parsed_items.append(q_data)

    if errors:
        has_mp3_error = any(err["type"] == "missing_audio" for err in errors)
        msg = f"Validation failed for {filepath}"
        if has_mp3_error:
            msg += " (Missing MP3 audio files)"
        raise ImportError(msg, {
            "file": filepath,
            "errors": errors
        })

    return parsed_items

def save_parsed_items(db: Session, parsed_items: list, batch_id: int) -> dict:
    """Save structured parsed items to database, checking content hash for idempotency."""
    skipped_q_count = 0
    skipped_g_count = 0
    imported_q_count = 0
    imported_g_count = 0

    for item in parsed_items:
        if "questions" in item:
            # It's a Group
            g_hash = calculate_group_hash(item)

            existing_g = db.query(QuestionGroup).filter(
                QuestionGroup.exam_id.is_(None),
                QuestionGroup.content_hash == g_hash
            ).first()

            if existing_g:
                skipped_g_count += 1
                skipped_q_count += len(item["questions"])
                continue

            new_g = QuestionGroup(
                exam_id=None,
                part=item["part"],
                topic=item["topic"],
                passage_text=item["passage_text"],
                audio_url=item["audio_url"],
                image_url=item["image_url"],
                difficulty=item["difficulty"],
                status="draft",
                content_hash=g_hash,
                import_batch_id=batch_id
            )
            db.add(new_g)
            db.commit()
            db.refresh(new_g)
            imported_g_count += 1

            for q_data in item["questions"]:
                q_hash = calculate_question_hash(q_data)

                existing_q = db.query(Question).filter(
                    Question.exam_id.is_(None),
                    Question.content_hash == q_hash
                ).first()

                if existing_q:
                    skipped_q_count += 1
                    continue

                new_q = Question(
                    exam_id=None,
                    group_id=new_g.id,
                    part=q_data["part"],
                    type=q_data["type"],
                    content=q_data["content"],
                    audio_url=q_data["audio_url"],
                    image_url=q_data["image_url"],
                    options=q_data["options"],
                    reference_answer=q_data["reference_answer"],
                    difficulty=q_data["difficulty"],
                    clo=q_data["clo"],
                    topic=q_data["topic"],
                    explanation=q_data["explanation"],
                    status="draft",
                    content_hash=q_hash,
                    import_batch_id=batch_id
                )
                db.add(new_q)
                imported_q_count += 1
            db.commit()

        else:
            # It's a Standalone Question
            q_hash = calculate_question_hash(item)

            existing_q = db.query(Question).filter(
                Question.exam_id.is_(None),
                Question.content_hash == q_hash
            ).first()

            if existing_q:
                skipped_q_count += 1
                continue

            new_q = Question(
                exam_id=None,
                group_id=None,
                part=item["part"],
                type=item["type"],
                content=item["content"],
                audio_url=item["audio_url"],
                image_url=item["image_url"],
                options=item["options"],
                reference_answer=item["reference_answer"],
                difficulty=item["difficulty"],
                clo=item["clo"],
                topic=item["topic"],
                explanation=item["explanation"],
                status="draft",
                content_hash=q_hash,
                import_batch_id=batch_id
            )
            db.add(new_q)
            db.commit()
            imported_q_count += 1

    return {
        "imported_questions": imported_q_count,
        "imported_groups": imported_g_count,
        "skipped_questions": skipped_q_count,
        "skipped_groups": skipped_g_count
    }

def import_file(db: Session, filepath: str, audio_dir: str = None) -> dict:
    """Parse, validate, and import a .docx file into the Question Bank."""
    file_hash = calculate_file_hash(filepath)

    if audio_dir is None:
        audio_dir = os.path.dirname(filepath)

    # 1. Parse docx
    blocks = parse_docx(filepath)

    # 2. Validate blocks (raises ImportError if fails)
    parsed_items = process_blocks(blocks, filepath, audio_dir)

    # 3. Create ImportBatch (Atomic database transactions)
    batch = ImportBatch(
        source_file=filepath,
        content_hash=file_hash,
        status="imported"
    )
    db.add(batch)
    db.commit()
    db.refresh(batch)

    # 4. Save items
    try:
        result = save_parsed_items(db, parsed_items, batch.id)
        return result
    except Exception as e:
        db.rollback()
        raise e


def parse_answer_key(filepath: str) -> dict[int, str]:
    """
    Parses answer key from an Excel (.xlsx) file with a header containing 'Câu' and 'Đáp án'.
    Supports multiple column blocks (e.g. 5 blocks of 20 rows each).
    """
    import openpyxl
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"File not found: {filepath}")

    wb = openpyxl.load_workbook(filepath, data_only=True)
    sheet = wb.active

    header_row_idx = None
    column_pairs = []

    for r_idx in range(1, sheet.max_row + 1):
        row_vals = [sheet.cell(row=r_idx, column=c_idx).value for c_idx in range(1, sheet.max_column + 1)]
        norm_vals = []
        for v in row_vals:
            if isinstance(v, str):
                norm_vals.append(v.strip().lower())
            else:
                norm_vals.append("")

        câu_indices = [i for i, val in enumerate(norm_vals) if "câu" in val]
        if len(câu_indices) >= 2:
            header_row_idx = r_idx
            for c_idx in câu_indices:
                for offset in range(1, 4):
                    next_idx = c_idx + offset
                    if next_idx < len(norm_vals) and ("đáp" in norm_vals[next_idx] or "key" in norm_vals[next_idx] or "ans" in norm_vals[next_idx]):
                        column_pairs.append((c_idx + 1, next_idx + 1))
                        break
            if column_pairs:
                break

    if header_row_idx is None or not column_pairs:
        wb.close()
        raise ValueError("Could not find a valid header row with 'Câu' and 'Đáp án' columns in the Excel file.")

    answers = {}
    for r_idx in range(header_row_idx + 1, sheet.max_row + 1):
        for câu_col, ans_col in column_pairs:
            câu_val = sheet.cell(row=r_idx, column=câu_col).value
            ans_val = sheet.cell(row=r_idx, column=ans_col).value

            if câu_val is None or ans_val is None:
                continue

            try:
                if isinstance(câu_val, str):
                    digits = "".join(filter(str.isdigit, câu_val))
                    if not digits:
                        continue
                    q_num = int(digits)
                elif isinstance(câu_val, (int, float)):
                    q_num = int(câu_val)
                else:
                    continue
            except (ValueError, TypeError):
                continue

            if not isinstance(ans_val, str):
                ans_val = str(ans_val)
            ans_str = ans_val.strip().upper()
            if ans_str in {"A", "B", "C", "D"}:
                answers[q_num] = ans_str

    wb.close()
    return answers


def parse_listening_docx(filepath: str) -> dict:
    """
    Parses a TOEIC Listening test .docx file in the real table-based format.
    Returns:
        dict: {
            "set_id": "LT2601",
            "items": [...]
        }
    """
    import os
    import re
    import docx
    from docx.oxml import CT_P, CT_Tbl
    from docx.text.paragraph import Paragraph
    from docx.table import Table

    if not os.path.exists(filepath):
        raise FileNotFoundError(f"File not found: {filepath}")

    doc = docx.Document(filepath)

    # 1. Extract Set ID
    set_id = None
    for p in doc.paragraphs:
        if "Mã đề thi" in p.text:
            set_id = "".join(c for c in p.text.split("Mã đề thi")[-1] if c.isalnum()).upper()
            break
    if not set_id:
        for t in doc.tables:
            for row in t.rows:
                for cell in row.cells:
                    if "Mã đề thi" in cell.text:
                        set_id = "".join(c for c in cell.text.split("Mã đề thi")[-1] if c.isalnum()).upper()
                        break
                if set_id:
                    break
            if set_id:
                break

    # Helper to check if a paragraph/table contains Part header
    def check_part(text):
        m = re.search(r'(?i)part\s*(\d+)', text)
        if m:
            return int(m.group(1))
        return None

    # Helper to check drawings
    def get_drawings(element):
        return element.findall('.//{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}inline') + \
               element.findall('.//{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}anchor')

    current_part = None
    items = []
    part1_questions = {}
    drawings_found = []

    body_elements = list(doc.element.body)
    i = 0
    while i < len(body_elements):
        child = body_elements[i]
        if isinstance(child, CT_P):
            p = Paragraph(child, doc)
            text = p.text.strip()
            
            # Check for part change
            new_part = check_part(text)
            if new_part:
                current_part = new_part
                
            # If we are in Part 1, check for question paragraph
            if current_part == 1:
                q_match = re.match(r'^\s*(\d+)\.', text)
                if q_match:
                    q_num = int(q_match.group(1))
                    if 1 <= q_num <= 3:
                        drawings = get_drawings(p._element)
                        img_idx = None
                        if drawings:
                            img_idx = len(drawings_found)
                            drawings_found.append(drawings[0])
                        else:
                            # Peek next paragraph for drawing
                            if i + 1 < len(body_elements) and isinstance(body_elements[i+1], CT_P):
                                next_p = Paragraph(body_elements[i+1], doc)
                                next_drawings = get_drawings(next_p._element)
                                if next_drawings:
                                    img_idx = len(drawings_found)
                                    drawings_found.append(next_drawings[0])
                        
                        part1_questions[q_num] = {
                            "number": q_num,
                            "part": 1,
                            "type": "choice",
                            "content": "",
                            "options": {},
                            "reference_answer": None,
                            "image_url": str(img_idx) if img_idx is not None else None,
                            "audio_url": None,
                            "difficulty": "medium",
                            "clo": None,
                            "topic": None,
                            "explanation": None
                        }
            
        elif isinstance(child, CT_Tbl):
            t = Table(child, doc)
            first_cell_text = t.rows[0].cells[0].text.strip()
            new_part = check_part(first_cell_text)
            if new_part:
                current_part = new_part
                
            if current_part == 1:
                # Process Part 1 table rows
                for row in t.rows:
                    cell_0_text = row.cells[0].text.strip()
                    q_match = re.match(r'^\s*(\d+)\.', cell_0_text)
                    if q_match:
                        q_num = int(q_match.group(1))
                        if q_num >= 4:
                            row_drawings = []
                            for cell in row.cells:
                                for cp in cell.paragraphs:
                                    row_drawings.extend(get_drawings(cp._element))
                            img_idx = None
                            if row_drawings:
                                img_idx = len(drawings_found)
                                drawings_found.append(row_drawings[0])
                                
                            part1_questions[q_num] = {
                                "number": q_num,
                                "part": 1,
                                "type": "choice",
                                "content": "",
                                "options": {},
                                "reference_answer": None,
                                "image_url": str(img_idx) if img_idx is not None else None,
                                "audio_url": None,
                                "difficulty": "medium",
                                "clo": None,
                                "topic": None,
                                "explanation": None
                            }
                            
            elif current_part == 2:
                # Process Part 2 table
                for row in t.rows:
                    for cell in row.cells:
                        text = cell.text.strip()
                        q_match = re.match(r'^\s*(\d+)\.\s*(.*)', text, re.DOTALL)
                        if q_match:
                            q_num = int(q_match.group(1))
                            q_content = q_match.group(2).strip().replace('\n', ' ')
                            q_content = re.sub(r'\s+', ' ', q_content)
                            items.append({
                                "number": q_num,
                                "part": 2,
                                "type": "choice",
                                "content": q_content,
                                "options": {},
                                "reference_answer": None,
                                "image_url": None,
                                "audio_url": None,
                                "difficulty": "medium",
                                "clo": None,
                                "topic": None,
                                "explanation": None
                            })
                            
            elif current_part in [3, 4]:
                # Process Part 3 and Part 4 tables
                has_questions = False
                for row in t.rows:
                    for cell in row.cells:
                        if re.search(r'^\s*\d+\.', cell.text):
                            has_questions = True
                            break
                    if has_questions:
                        break
                        
                if has_questions:
                    for row in t.rows:
                        for cell in row.cells:
                            cell_drawings = []
                            for cp in cell.paragraphs:
                                cell_drawings.extend(get_drawings(cp._element))
                            
                            img_idx = None
                            if cell_drawings:
                                img_idx = len(drawings_found)
                                drawings_found.append(cell_drawings[0])
                                
                            # Parse groups separated by dash lines
                            blocks_paragraphs = [[]]
                            for p in cell.paragraphs:
                                p_text = p.text.strip()
                                if re.match(r'^[-_]{3,}', p_text):
                                    blocks_paragraphs.append([])
                                else:
                                    blocks_paragraphs[-1].append(p)
                                    
                            for bp_list in blocks_paragraphs:
                                block_questions = []
                                curr_q = None
                                
                                for p in bp_list:
                                    p_text = p.text.strip()
                                    if not p_text:
                                        continue
                                        
                                    q_match = re.match(r'^\s*(\d+)\.\s*(.*)', p_text)
                                    if q_match:
                                        if curr_q:
                                            block_questions.append(curr_q)
                                        q_num = int(q_match.group(1))
                                        q_content = q_match.group(2).strip()
                                        curr_q = {
                                            "number": q_num,
                                            "part": current_part,
                                            "type": "choice",
                                            "content": q_content,
                                            "options": {},
                                            "reference_answer": None,
                                            "image_url": None,
                                            "audio_url": None,
                                            "difficulty": "medium",
                                            "clo": None,
                                            "topic": None,
                                            "explanation": None
                                        }
                                    elif curr_q is not None:
                                        opt_match = re.match(r'^\s*\(([A-D])\)\s*(.*)', p_text)
                                        if opt_match:
                                            opt_letter = opt_match.group(1)
                                            opt_text = opt_match.group(2).strip()
                                            curr_q["options"][opt_letter] = opt_text
                                        else:
                                            if not curr_q["options"]:
                                                curr_q["content"] += " " + p_text
                                            else:
                                                last_opt = list(curr_q["options"].keys())[-1]
                                                curr_q["options"][last_opt] += " " + p_text
                                                
                                if curr_q:
                                    block_questions.append(curr_q)
                                    
                                if block_questions:
                                    group_img = str(img_idx) if img_idx is not None else None
                                    group_data = {
                                        "part": current_part,
                                        "topic": None,
                                        "passage_text": None,
                                        "audio_url": None,
                                        "image_url": group_img,
                                        "difficulty": "medium",
                                        "questions": block_questions
                                    }
                                    items.append(group_data)
                                    
        i += 1

    # Insert Part 1 questions in sorted order at the beginning of items list
    for q_num in sorted(part1_questions.keys(), reverse=True):
        items.insert(0, part1_questions[q_num])

    return {
        "set_id": set_id,
        "items": items
    }


def find_audio_file(audio_dir: str, set_id: str) -> tuple[str | None, list[str]]:
    """
    Search audio_dir for an MP3 file covering set_id.
    Returns:
        tuple[str | None, list[str]]: (selected_audio_filename, ambiguous_matches_list)
    """
    import os
    import re

    if not audio_dir or not os.path.exists(audio_dir):
        return None, []

    # Extract digits from set_id (e.g., 'LT2601' -> 2601)
    m = re.search(r'\d+', set_id)
    if not m:
        return None, []
    set_num = int(m.group(0))

    candidates = []
    try:
        filenames = os.listdir(audio_dir)
    except OSError:
        return None, []

    for filename in filenames:
        if not filename.lower().endswith(".mp3"):
            continue

        filename_clean = filename.strip()
        filename_lower = filename_clean.lower()

        # Try to match range: e.g. "2601 - 2604.mp3" strictly anchored
        range_match = re.match(r'^(\d+)\s*-\s*(\d+)\.mp3$', filename_lower)
        if range_match:
            start = int(range_match.group(1))
            end = int(range_match.group(2))
            if start <= set_num <= end:
                candidates.append(filename_clean)
            continue

        # Try to match single set: e.g. "2601.mp3" strictly anchored
        single_match = re.match(r'^(\d+)\.mp3$', filename_lower)
        if single_match:
            num = int(single_match.group(1))
            if num == set_num:
                candidates.append(filename_clean)
            continue

    if not candidates:
        return None, []

    # Sort alphabetically for deterministic behavior
    candidates.sort()
    selected = candidates[0]
    ambiguous = candidates if len(candidates) > 1 else []
    return selected, ambiguous


def import_exam_set(db: Session, docx_path: str, key_path: str, exam_type: str, audio_dir: str = None) -> dict:
    """
    Parses, merges answers, validates, and imports a real-format TOEIC exam set (listening or reading) into the Question Bank.
    """
    import os
    import re
    
    # 1. Parse docx
    if exam_type == "listening":
        docx_res = parse_listening_docx(docx_path)
    elif exam_type == "reading":
        docx_res = parse_reading_docx(docx_path)
    else:
        raise ValueError(f"Unsupported exam_type: {exam_type}")

    set_id_docx = docx_res["set_id"]
    items = docx_res["items"]

    # Locate and resolve audio file for Listening
    matched_audio = None
    ambiguous_audio = []
    if exam_type == "listening":
        search_dir = audio_dir if audio_dir is not None else os.path.dirname(docx_path)
        matched_audio, ambiguous_audio = find_audio_file(search_dir, set_id_docx)

    # Stamp set_id and audio_url
    for item in items:
        item["set_id"] = set_id_docx
        if exam_type == "listening":
            item["audio_url"] = matched_audio
        if "questions" in item:
            for q in item["questions"]:
                q["set_id"] = set_id_docx
                if exam_type == "listening":
                    q["audio_url"] = matched_audio

    # 2. Parse answer key
    answers = parse_answer_key(key_path)

    # Sanity check: set_id docx should match set_id from key filename if possible
    key_filename = os.path.basename(key_path)
    key_set_id_match = re.search(r'(?i)(LT|RT)\.?\s*(\d+)', key_filename)
    if key_set_id_match and set_id_docx:
        key_set_id = f"{key_set_id_match.group(1).upper()}{key_set_id_match.group(2)}"
        if set_id_docx != key_set_id:
            raise ImportError(
                f"Set ID mismatch between docx '{set_id_docx}' and key '{key_set_id}'",
                {
                    "file": docx_path,
                    "errors": [{
                        "location": "Set ID Check",
                        "type": "set_id_mismatch",
                        "message": f"Set ID mismatch: docx={set_id_docx}, key={key_set_id}"
                    }]
                }
            )

    # 3. Merge and validate answers
    errors = []
    for item_idx, item in enumerate(items):
        if "questions" in item:
            for q in item["questions"]:
                q_num = q["number"]
                location_q = f"Question {q_num}"
                if q_num not in answers:
                    errors.append({
                        "location": location_q,
                        "type": "missing_answer",
                        "message": f"No answer found in KEY for Question {q_num}."
                    })
                else:
                    ans = answers[q_num]
                    q["reference_answer"] = ans
                    if ans not in {"A", "B", "C", "D"}:
                        errors.append({
                            "location": location_q,
                            "type": "invalid_answer",
                            "message": f"Invalid answer '{ans}' in KEY for Question {q_num}."
                        })
        else:
            q_num = item["number"]
            location_q = f"Question {q_num}"
            if q_num not in answers:
                errors.append({
                    "location": location_q,
                    "type": "missing_answer",
                    "message": f"No answer found in KEY for Question {q_num}."
                })
            else:
                ans = answers[q_num]
                item["reference_answer"] = ans
                if ans not in {"A", "B", "C", "D"}:
                    errors.append({
                        "location": location_q,
                        "type": "invalid_answer",
                        "message": f"Invalid answer '{ans}' in KEY for Question {q_num}."
                    })

    if errors:
        raise ImportError(f"Validation failed during merging for {docx_path}", {
            "file": docx_path,
            "errors": errors
        })

    # 4. Create ImportBatch (Atomic database transactions)
    file_hash = calculate_file_hash(docx_path)
    
    batch = ImportBatch(
        source_file=docx_path,
        content_hash=file_hash,
        status="imported"
    )
    db.add(batch)
    db.commit()
    db.refresh(batch)

    try:
        result = save_parsed_items(db, items, batch.id)
        if exam_type == "listening":
            result["audio_linked"] = matched_audio
            result["audio_ambiguous"] = ambiguous_audio
        return result
    except Exception as e:
        db.rollback()
        raise e


def import_listening_set(db: Session, docx_path: str, key_path: str, audio_dir: str = None) -> dict:
    """
    Parses, merges answers, validates, and imports a real-format TOEIC Listening set into the Question Bank.
    """
    return import_exam_set(db, docx_path, key_path, "listening", audio_dir)


def import_reading_set(db: Session, docx_path: str, key_path: str) -> dict:
    """
    Parses, merges answers, validates, and imports a real-format TOEIC Reading set into the Question Bank.
    """
    return import_exam_set(db, docx_path, key_path, "reading")


def convert_doc_to_docx(filepath: str, out_dir: str = None) -> str:
    """
    Convert a legacy Word document (.doc) to XML format (.docx) using headless LibreOffice.
    
    - If the input file already has a .docx extension, returns the input filepath unchanged (passthrough).
    - If the input file has a .doc extension, converts it using `soffice --headless --convert-to docx`.
    - Caches result: if the target .docx file already exists, skips conversion and returns its path immediately.
    - If soffice is missing from PATH, raises a clear, helpful FileNotFoundError.
    """
    import os
    import shutil
    import subprocess
    
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Source file not found: {filepath}")
        
    # Normalize path extension
    _, ext = os.path.splitext(filepath.lower())
    
    # 1. Passthrough: if already docx, return path directly
    if ext == ".docx":
        return filepath
        
    if ext != ".doc":
        raise ValueError(f"Unsupported file format for conversion: {ext} (only .doc is supported)")
        
    # Determine output directory (default to input file's directory)
    if out_dir is None:
        out_dir = os.path.dirname(os.path.abspath(filepath))
    else:
        out_dir = os.path.abspath(out_dir)
        os.makedirs(out_dir, exist_ok=True)
        
    # Determine target docx filename
    base = os.path.basename(filepath)
    stem, _ = os.path.splitext(base)
    target_docx = os.path.join(out_dir, f"{stem}.docx")
    
    # 2. Cache check: if target docx exists, skip conversion
    if os.path.exists(target_docx):
        return target_docx
        
    # 3. Tool presence check
    soffice_path = shutil.which("soffice")
    if soffice_path is None:
        # Check common windows installation folder fallback just in case
        common_paths = [
            r"C:\Program Files\LibreOffice\program\soffice.exe",
            r"C:\Program Files (x86)\LibreOffice\program\soffice.exe"
        ]
        for cp in common_paths:
            if os.path.exists(cp):
                soffice_path = cp
                break
                
    if soffice_path is None:
        raise FileNotFoundError(
            "LibreOffice 'soffice' executable not found on PATH or standard directories.\n"
            "Please install LibreOffice (https://www.libreoffice.org) and make sure 'soffice' "
            "is added to your system environment variables (PATH)."
        )
        
    # 4. Conversion via subprocess (using list of args, no shell=True)
    cmd = [
        soffice_path,
        "--headless",
        "--convert-to",
        "docx",
        "--outdir",
        out_dir,
        filepath
    ]
    
    try:
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(
            f"LibreOffice conversion failed for {filepath}.\n"
            f"Exit code: {e.returncode}\n"
            f"Error output: {e.stderr or e.stdout}"
        ) from e
        
    if not os.path.exists(target_docx):
        raise RuntimeError(
            f"LibreOffice command finished successfully, but target file was not created: {target_docx}"
        )
        
    return target_docx


def parse_reading_docx(filepath: str) -> dict:
    """
    Parses a TOEIC Reading test .docx file in the real table/paragraph-based format.
    Returns:
        dict: {
            "set_id": "RT2605",
            "items": [...]
        }
    """
    import os
    import re
    import docx
    from docx.oxml.table import CT_Tbl
    from docx.oxml.text.paragraph import CT_P
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    if not os.path.exists(filepath):
        raise FileNotFoundError(f"File not found: {filepath}")

    doc = docx.Document(filepath)

    def check_part(text: str) -> int:
        m = re.search(r'(?i)PART\s*(\d+)', text)
        if m:
            return int(m.group(1))
        return None

    def get_drawings(element):
        return element.findall('.//{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}inline') + \
               element.findall('.//{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}anchor')

    set_id = None
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                m = re.search(r'(?i)RT\.?\s*(\d+)', cell.text)
                if m:
                    set_id = f"RT{m.group(1)}"
                    break
            if set_id:
                break
        if set_id:
            break

    if not set_id:
        for p in doc.paragraphs:
            m = re.search(r'(?i)RT\.?\s*(\d+)', p.text)
            if m:
                set_id = f"RT{m.group(1)}"
                break

    if not set_id:
        filename = os.path.basename(filepath)
        m = re.search(r'(?i)RT\.?\s*(\d+)', filename)
        if m:
            set_id = f"RT{m.group(1)}"
        else:
            set_id = "RT9999"

    current_part = None
    items = []
    drawings_found = []

    body_elements = list(doc.element.body)
    i = 0
    while i < len(body_elements):
        child = body_elements[i]
        
        if isinstance(child, CT_P):
            p = Paragraph(child, doc)
            text = p.text.strip()
            
            new_part = check_part(text)
            if new_part:
                current_part = new_part
                i += 1
                continue

            if current_part == 5:
                q_match = re.match(r'^\s*(\d+)\.\s*(.*)', text, re.DOTALL)
                if q_match:
                    q_num = int(q_match.group(1))
                    q_rest = q_match.group(2).strip()
                    
                    q_item = {
                        "number": q_num,
                        "part": 5,
                        "type": "choice",
                        "content": "",
                        "options": {},
                        "reference_answer": None,
                        "audio_url": None,
                        "image_url": None,
                        "difficulty": "medium",
                        "clo": None,
                        "topic": None,
                        "explanation": None
                    }
                    
                    parts = re.split(r'\s*\(([A-D])\)\s*', q_rest)
                    q_item["content"] = parts[0].strip()
                    if len(parts) >= 3:
                        for idx_opt in range(1, len(parts), 2):
                            letter = parts[idx_opt]
                            val = parts[idx_opt+1].strip()
                            q_item["options"][letter] = val
                            
                    opt_count = len(q_item["options"])
                    j = i + 1
                    while j < len(body_elements) and opt_count < 4:
                        next_child = body_elements[j]
                        if isinstance(next_child, CT_P):
                            next_p = Paragraph(next_child, doc)
                            next_text = next_p.text.strip()
                            if re.match(r'^\s*\(([A-D])\)\s*', next_text):
                                opt_parts = re.split(r'\s*\(([A-D])\)\s*', next_text)
                                if len(opt_parts) >= 3:
                                    for idx_opt in range(1, len(opt_parts), 2):
                                        letter = opt_parts[idx_opt]
                                        val = opt_parts[idx_opt+1].strip()
                                        q_item["options"][letter] = val
                                opt_count = len(q_item["options"])
                                j += 1
                                continue
                        break
                    
                    if opt_count > 0:
                        i = j - 1
                    items.append(q_item)

            elif current_part in (6, 7):
                ref_match = re.search(r'(?i)Questions\s+(\d+)\s*[-–]\s*(\d+)', text)
                if ref_match:
                    start_q = int(ref_match.group(1))
                    end_q = int(ref_match.group(2))
                    
                    group_data = {
                        "part": current_part,
                        "topic": None,
                        "passage_text": "",
                        "audio_url": None,
                        "image_url": None,
                        "difficulty": "medium",
                        "questions": []
                    }
                    
                    passage_parts = []
                    group_drawings = []
                    
                    j = i + 1
                    questions_started = False
                    
                    while j < len(body_elements):
                        next_child = body_elements[j]
                        
                        if isinstance(next_child, CT_P):
                            next_p = Paragraph(next_child, doc)
                            next_text = next_p.text.strip()
                            
                            if check_part(next_text):
                                break
                            if re.search(r'(?i)Questions\s+(\d+)\s*[-–]\s*(\d+)', next_text):
                                break
                                
                            q_start_match = re.match(r'^\s*(\d+)\.\s*(.*)', next_text, re.DOTALL)
                            if q_start_match:
                                q_num = int(q_start_match.group(1))
                                if start_q <= q_num <= end_q:
                                    questions_started = True
                                    
                            if questions_started:
                                break
                                
                            if next_text:
                                passage_parts.append(next_text)
                                p_drawings = get_drawings(next_child)
                                if p_drawings:
                                    group_drawings.extend(p_drawings)
                                    
                        elif isinstance(next_child, CT_Tbl):
                            next_t = Table(next_child, doc)
                            if len(next_t.rows) == 1 and len(next_t.columns) == 1:
                                cell_text = next_t.cell(0, 0).text.strip()
                                if cell_text:
                                    passage_parts.append(cell_text)
                                for cp in next_t.cell(0, 0).paragraphs:
                                    p_drawings = get_drawings(cp._element)
                                    if p_drawings:
                                        group_drawings.extend(p_drawings)
                            else:
                                break
                                
                        j += 1
                        
                    group_data["passage_text"] = "\n".join(passage_parts)
                    if group_drawings:
                        img_idx = len(drawings_found)
                        drawings_found.append(group_drawings[0])
                        group_data["image_url"] = str(img_idx)
                        
                    while j < len(body_elements):
                        next_child = body_elements[j]
                        
                        if isinstance(next_child, CT_P):
                            next_p = Paragraph(next_child, doc)
                            next_text = next_p.text.strip()
                            if check_part(next_text):
                                break
                            if re.search(r'(?i)Questions\s+(\d+)\s*[-–]\s*(\d+)', next_text):
                                break
                                
                            q_match = re.match(r'^\s*(\d+)\.\s*(.*)', next_text, re.DOTALL)
                            if q_match:
                                q_num = int(q_match.group(1))
                                q_rest = q_match.group(2).strip()
                                
                                q_item = {
                                    "number": q_num,
                                    "part": current_part,
                                    "type": "choice",
                                    "content": "",
                                    "options": {},
                                    "reference_answer": None,
                                    "audio_url": None,
                                    "image_url": None,
                                    "difficulty": "medium",
                                    "clo": None,
                                    "topic": None,
                                    "explanation": None
                                }
                                
                                parts = re.split(r'\s*\(([A-D])\)\s*', q_rest)
                                q_item["content"] = parts[0].strip()
                                if len(parts) >= 3:
                                    for idx_opt in range(1, len(parts), 2):
                                        letter = parts[idx_opt]
                                        val = parts[idx_opt+1].strip()
                                        q_item["options"][letter] = val
                                        
                                opt_count = len(q_item["options"])
                                k = j + 1
                                while k < len(body_elements) and opt_count < 4:
                                    opt_child = body_elements[k]
                                    if isinstance(opt_child, CT_P):
                                        opt_p = Paragraph(opt_child, doc)
                                        opt_text = opt_p.text.strip()
                                        
                                        if check_part(opt_text):
                                            break
                                        if re.search(r'(?i)Questions\s+(\d+)\s*[-–]\s*(\d+)', opt_text):
                                            break
                                        if re.match(r'^\s*\d+\.', opt_text):
                                            break
                                            
                                        if re.match(r'^\s*\(([A-D])\)\s*', opt_text):
                                            opt_parts = re.split(r'\s*\(([A-D])\)\s*', opt_text)
                                            if len(opt_parts) >= 3:
                                                for idx_opt in range(1, len(opt_parts), 2):
                                                    letter = opt_parts[idx_opt]
                                                    val = opt_parts[idx_opt+1].strip()
                                                    q_item["options"][letter] = val
                                            opt_count = len(q_item["options"])
                                            k += 1
                                            continue
                                            
                                        if opt_count == 0:
                                            if opt_text:
                                                q_item["content"] += "\n" + opt_text
                                            k += 1
                                            continue
                                            
                                    elif isinstance(opt_child, CT_Tbl):
                                        opt_t = Table(opt_child, doc)
                                        if len(opt_t.rows) == 4 and len(opt_t.columns) == 2:
                                            for r_idx, row in enumerate(opt_t.rows):
                                                letter_cell = row.cells[0].text.strip()
                                                text_cell = row.cells[1].text.strip()
                                                letter_match = re.search(r'([A-D])', letter_cell)
                                                if letter_match:
                                                    letter = letter_match.group(1)
                                                    q_item["options"][letter] = text_cell
                                            opt_count = len(q_item["options"])
                                            k += 1
                                            break
                                    break
                                
                                if opt_count > 0:
                                    j = k - 1
                                group_data["questions"].append(q_item)
                                
                        elif isinstance(next_child, CT_Tbl):
                            opt_t = Table(next_child, doc)
                            if len(opt_t.rows) > 0 and len(opt_t.columns) == 2:
                                first_cell_text = opt_t.cell(0, 0).text.strip()
                                if re.match(r'^\s*\d+\.', first_cell_text):
                                    for row in opt_t.rows:
                                        num_text = row.cells[0].text.strip()
                                        opts_text = row.cells[1].text.strip()
                                        num_match = re.match(r'^\s*(\d+)\.', num_text)
                                        if num_match:
                                            q_num = int(num_match.group(1))
                                            
                                            options_dict = {}
                                            opt_parts = re.split(r'\s*\(([A-D])\)\s*', opts_text)
                                            if len(opt_parts) >= 3:
                                                for idx_opt in range(1, len(opt_parts), 2):
                                                    letter = opt_parts[idx_opt]
                                                    val = opt_parts[idx_opt+1].strip()
                                                    options_dict[letter] = val
                                                    
                                            q_item = {
                                                "number": q_num,
                                                "part": current_part,
                                                "type": "choice",
                                                "content": "",
                                                "options": options_dict,
                                                "reference_answer": None,
                                                "audio_url": None,
                                                "image_url": None,
                                                "difficulty": "medium",
                                                "clo": None,
                                                "topic": None,
                                                "explanation": None
                                            }
                                            group_data["questions"].append(q_item)
                        j += 1
                        
                    i = j - 1
                    if group_data["questions"]:
                        items.append(group_data)

        i += 1

    return {
        "set_id": set_id,
        "items": items
    }


def parse_b1_reading_docx(filepath: str) -> dict:
    """
    Parses a B1 Reading and Writing test .docx file.
    Returns:
        dict: {
            "set_id": "EB12601",
            "items": [
                {
                    "number": int,
                    "part": int (1-6),
                    "section": int,
                    "type": str ('choice', 'fill', 'writing'),
                    "content": str,
                    "options": dict
                },
                ...
            ]
        }
    """
    import os
    import re
    import docx
    from docx.oxml.table import CT_Tbl
    from docx.oxml.text.paragraph import CT_P
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    if not os.path.exists(filepath):
        raise FileNotFoundError(f"File not found: {filepath}")

    doc = docx.Document(filepath)

    # 1. Extract set_id
    set_id = None
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                m = re.search(r'(?i)EB1\.?\s*(\d+)', cell.text)
                if m:
                    set_id = f"EB1{m.group(1)}"
                    break
            if set_id:
                break
        if set_id:
            break

    if not set_id:
        for p in doc.paragraphs:
            m = re.search(r'(?i)EB1\.?\s*(\d+)', p.text)
            if m:
                set_id = f"EB1{m.group(1)}"
                break

    if not set_id:
        filename = os.path.basename(filepath)
        m = re.search(r'(?i)EB1\.?\s*(\d+)', filename)
        if m:
            set_id = f"EB1{m.group(1)}"
        else:
            set_id = "EB19999"

    # 2. Traverse body elements
    body_elements = list(doc.element.body)

    current_part = None  # "R" or "W"
    current_section = None  # 1-4 for Reading, 1-2 for Writing
    items = []

    s3_passage_paragraphs = []
    s4_passage_paragraphs = []
    w1_paragraphs = []
    w2_paragraphs = []

    visited_indices = set()

    def extract_inline_options_4(text):
        m = re.match(r'^\s*A[\.\)]\s*(.*?)\s+B[\.\)]\s*(.*?)\s+C[\.\)]\s*(.*?)\s+D[\.\)]\s*(.*)$', text)
        if m:
            return {
                "A": m.group(1).strip(),
                "B": m.group(2).strip(),
                "C": m.group(3).strip(),
                "D": m.group(4).strip()
            }
        pos_a = text.find("A.")
        pos_b = text.find("B.")
        pos_c = text.find("C.")
        pos_d = text.find("D.")
        if pos_a != -1 and pos_b != -1 and pos_c != -1 and pos_d != -1:
            return {
                "A": text[pos_a+2:pos_b].strip(),
                "B": text[pos_b+2:pos_c].strip(),
                "C": text[pos_c+2:pos_d].strip(),
                "D": text[pos_d+2:].strip()
            }
        return {}

    i = 0
    while i < len(body_elements):
        if i in visited_indices:
            i += 1
            continue
            
        child = body_elements[i]
        if isinstance(child, CT_P):
            p = Paragraph(child, doc)
            text = p.text.strip()
            
            # Check part/section transitions
            if re.search(r'(?i)PART\s*ONE|READING', text):
                current_part = "R"
                i += 1
                continue
            elif re.search(r'(?i)PART\s*TWO|WRITING', text):
                current_part = "W"
                i += 1
                continue
                
            sec_m = re.search(r'(?i)Section\s+(\d+)', text)
            if sec_m:
                sec_num = int(sec_m.group(1))
                if current_part == "R":
                    current_section = sec_num
                elif current_part == "W":
                    current_section = sec_num
                i += 1
                continue
                
            # Parse based on current section
            if current_part == "R":
                if current_section == 1:
                    # S1 Q1-10
                    q_m = re.match(r'^\s*(\d+)\.\s*(.*)', text, re.DOTALL)
                    if q_m:
                        q_num = int(q_m.group(1))
                        q_content = q_m.group(2).strip()
                        options = {}
                        j = i + 1
                        while j < len(body_elements):
                            next_child = body_elements[j]
                            if isinstance(next_child, CT_P):
                                next_p = Paragraph(next_child, doc)
                                next_text = next_p.text.strip()
                                if next_text:
                                    options = extract_inline_options_4(next_text)
                                    visited_indices.add(j)
                                    break
                            j += 1
                        items.append({
                            "number": q_num,
                            "part": 1,
                            "section": 1,
                            "type": "choice",
                            "content": q_content,
                            "options": options
                        })
                        
                elif current_section == 3:
                    # S3 Q16-20
                    q_m = re.match(r'^\s*(\d+)\.\s*(.*)', text, re.DOTALL)
                    if q_m:
                        q_num = int(q_m.group(1))
                        q_content = q_m.group(2).strip()
                        options = {}
                        j = i + 1
                        opt_count = 0
                        while j < len(body_elements) and opt_count < 4:
                            next_child = body_elements[j]
                            if isinstance(next_child, CT_P):
                                next_p = Paragraph(next_child, doc)
                                next_text = next_p.text.strip()
                                if next_text:
                                    opt_m = re.match(r'^\s*([A-D])[\.\)]\s*(.*)', next_text)
                                    if opt_m:
                                        options[opt_m.group(1)] = opt_m.group(2).strip()
                                        visited_indices.add(j)
                                        opt_count += 1
                                    else:
                                        break
                                else:
                                    j += 1
                                    continue
                            else:
                                break
                            j += 1
                            
                        items.append({
                            "number": q_num,
                            "part": 3,
                            "section": 3,
                            "type": "choice",
                            "content": q_content,
                            "options": options
                        })
                    else:
                        if text and not text.startswith("Read the text"):
                            s3_passage_paragraphs.append(text)
                            
                elif current_section == 4:
                    # S4 Q21-30
                    if text and not text.startswith("Read the text") and not text.startswith("THE GORILLA"):
                        s4_passage_paragraphs.append(text)
                        
            elif current_part == "W":
                if current_section == 1:
                    # W1 (rewriting)
                    if text and not text.startswith("Finish each of the following sentences") and not text.startswith("Example") and not text.startswith("Answer"):
                        w1_paragraphs.append(text)
                elif current_section == 2:
                    # W2 (essay/letter)
                    if text and not text.startswith("Now write a letter"):
                        w2_paragraphs.append(text)
                        
        elif isinstance(child, CT_Tbl):
            t = Table(child, doc)
            if current_part == "R" and current_section == 2:
                # S2 Q11-15 table
                for row in t.rows:
                    cells = row.cells
                    if len(cells) >= 3:
                        cell0_text = cells[0].text.strip()
                        num_match = re.match(r'^\s*(\d+)\.?\s*$', cell0_text)
                        if num_match:
                            q_num = int(num_match.group(1))
                            if 11 <= q_num <= 15:
                                content = cells[1].text.strip()
                                options_text = cells[2].text.strip()
                                options = {}
                                pos_a = options_text.find("A.")
                                pos_b = options_text.find("B.")
                                pos_c = options_text.find("C.")
                                if pos_a != -1 and pos_b != -1 and pos_c != -1:
                                    options = {
                                        "A": options_text[pos_a+2:pos_b].strip(),
                                        "B": options_text[pos_b+2:pos_c].strip(),
                                        "C": options_text[pos_c+2:].strip()
                                    }
                                else:
                                    for line in options_text.split("\n"):
                                        line = line.strip()
                                        if line:
                                            m_opt = re.match(r'^\s*([A-C])\.\s*(.*)', line)
                                            if m_opt:
                                                options[m_opt.group(1)] = m_opt.group(2).strip()
                                items.append({
                                    "number": q_num,
                                    "part": 2,
                                    "section": 2,
                                    "type": "choice",
                                    "content": content,
                                    "options": options
                                })
                                
        i += 1

    # Post-process S4 (fill blanks)
    s4_text = "\n".join(s4_passage_paragraphs).replace("\n", " ")
    s4_text = re.sub(r'\s+', ' ', s4_text)
    sentences = [s.strip() for s in re.split(r'(?<!\.)\.(?!\.)(?=\s+[A-Z]|\s*\(\d+\)|\s*$)', s4_text) if s.strip()]

    for q_num in range(21, 31):
        blank_str = f"({q_num})"
        content = ""
        for s in sentences:
            if blank_str in s:
                content = s + "."
                break
        if not content:
            content = s4_text
            
        items.append({
            "number": q_num,
            "part": 4,
            "section": 4,
            "type": "fill",
            "content": content,
            "options": {}
        })

    # Add W1 and W2 items
    items.append({
        "number": 31,
        "part": 5,
        "section": 1,
        "type": "writing",
        "content": "\n".join(w1_paragraphs),
        "options": {}
    })

    items.append({
        "number": 32,
        "part": 6,
        "section": 2,
        "type": "writing",
        "content": "\n".join(w2_paragraphs),
        "options": {}
    })

    # Sort items by question number
    items.sort(key=lambda x: x["number"])

    return {
        "set_id": set_id,
        "items": items
    }


def parse_b1_answer_key(filepath: str) -> dict:
    """
    Parses a B1 Reading and Writing answer key .docx file.
    Returns:
        dict: {
            1: "A",
            ...
            21: "fact",
            ...
        }
    """
    import os
    import re
    import docx
    from docx.oxml.table import CT_Tbl
    from docx.oxml.text.paragraph import CT_P
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    if not os.path.exists(filepath):
        raise FileNotFoundError(f"File not found: {filepath}")

    doc = docx.Document(filepath)

    in_writing = False
    answers = {}

    for child in doc.element.body:
        if isinstance(child, CT_P):
            p = Paragraph(child, doc)
            text = p.text.strip()
            if re.search(r'(?i)PART\s*2|WRITING', text):
                in_writing = True
        elif isinstance(child, CT_Tbl) and not in_writing:
            t = Table(child, doc)
            
            question_cols = []
            header_row_idx = None
            
            for r_idx, row in enumerate(t.rows):
                row_texts = [c.text.strip() for c in row.cells]
                if "Câu" in row_texts and "Đáp án" in row_texts:
                    header_row_idx = r_idx
                    for c_idx, val in enumerate(row_texts):
                        if val == "Câu":
                            question_cols.append(c_idx)
                    break
                    
            if header_row_idx is not None:
                for r_idx in range(header_row_idx + 1, len(t.rows)):
                    row = t.rows[r_idx]
                    for c_idx in question_cols:
                        if c_idx + 1 < len(row.cells):
                            q_num_text = row.cells[c_idx].text.strip()
                            q_ans_text = row.cells[c_idx + 1].text.strip()
                            if re.match(r'^\d+$', q_num_text):
                                num = int(q_num_text)
                                if 1 <= num <= 30:
                                    if 1 <= num <= 20:
                                        answers[num] = q_ans_text.strip().upper()
                                    else:
                                        answers[num] = q_ans_text.strip()
                                        
    return answers

