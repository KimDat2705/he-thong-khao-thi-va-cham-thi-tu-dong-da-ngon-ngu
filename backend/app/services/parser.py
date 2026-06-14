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
    content_str = f"{g_data.get('part')}|{g_data.get('passage_text') or ''}|{g_data.get('audio_url') or ''}"
    return hashlib.sha256(content_str.encode("utf-8")).hexdigest()

def calculate_question_hash(q_data: dict) -> str:
    """Calculate SHA256 hash of a Question's core content."""
    sorted_options = json.dumps(q_data.get("options") or {}, sort_keys=True)
    content_str = f"{q_data.get('part')}|{q_data.get('type')}|{q_data.get('content') or ''}|{sorted_options}|{q_data.get('reference_answer') or ''}"
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


