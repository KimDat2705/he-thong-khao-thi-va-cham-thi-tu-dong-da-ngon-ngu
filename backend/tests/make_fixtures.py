import os
import docx

def create_valid_docx(filepath):
    doc = docx.Document()
    lines = [
        "[Group]",
        "Part: 3",
        "Topic: Meetings",
        "Audio: LT_sample_valid_P3_01.mp3",
        "Passage: Hello, this is a talk about meetings.",
        "Difficulty: medium",
        "",
        "[Question]",
        "Part: 3",
        "Content: What is being discussed?",
        "A: Meetings",
        "B: HR",
        "C: Finance",
        "D: Marketing",
        "Answer: A",
        "",
        "[Question]",
        "Part: 1",
        "Content: Look at the picture.",
        "A: They are sitting down.",
        "B: They are standing up.",
        "C: They are talking.",
        "D: They are writing.",
        "Answer: C",
        "Audio: LT_sample_valid_P1_01.mp3",
        "Difficulty: easy"
    ]
    for line in lines:
        doc.add_paragraph(line)
    doc.save(filepath)

def create_missing_audio_docx(filepath):
    doc = docx.Document()
    lines = [
        "[Group]",
        "Part: 3",
        "Topic: Talk",
        "Audio: LT_sample_missing_audio_P3_01.mp3",
        "Passage: Hello.",
        "",
        "[Question]",
        "Part: 3",
        "Content: What is this?",
        "A: Option A",
        "B: Option B",
        "C: Option C",
        "D: Option D",
        "Answer: A"
    ]
    for line in lines:
        doc.add_paragraph(line)
    doc.save(filepath)

def create_missing_answer_docx(filepath):
    doc = docx.Document()
    lines = [
        "[Question]",
        "Part: 1",
        "Content: Look at the picture.",
        "A: They are sitting down.",
        "B: They are standing up.",
        "C: They are talking.",
        "D: They are writing.",
        "Answer: ",
        "Difficulty: easy"
    ]
    for line in lines:
        doc.add_paragraph(line)
    doc.save(filepath)


def create_answer_key_xlsx(filepath):
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "LT2601 Key"
    
    # Row 1: Title
    ws["A1"] = "TOEIC - LISTENING -  LT2601"
    
    col_pairs = [
        ("A", "B"),
        ("D", "E"),
        ("G", "H"),
        ("J", "K"),
        ("M", "N")
    ]
    
    for c_col, a_col in col_pairs:
        ws[f"{c_col}3"] = "Câu"
        ws[f"{a_col}3"] = "Đáp án"
        
    answers = ["A", "B", "C", "D"]
    
    for row_idx in range(4, 24):
        offset = row_idx - 4
        for block_idx, (c_col, a_col) in enumerate(col_pairs):
            q_num = block_idx * 20 + offset + 1
            ans = answers[q_num % 4]
            ws[f"{c_col}{row_idx}"] = q_num
            ws[f"{a_col}{row_idx}"] = ans
            
    wb.save(filepath)
    wb.close()


def main():
    # Make sure we are writing to the correct absolute directory
    dir_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "fixtures", "parser"))
    os.makedirs(dir_path, exist_ok=True)
    
    create_valid_docx(os.path.join(dir_path, "LT_sample_valid.docx"))
    create_missing_audio_docx(os.path.join(dir_path, "LT_sample_missing_audio.docx"))
    create_missing_answer_docx(os.path.join(dir_path, "LT_sample_missing_answer.docx"))
    create_answer_key_xlsx(os.path.join(dir_path, "Key_LT2601.xlsx"))
    
    # Create mock audio files
    for audio_file in ["LT_sample_valid_P1_01.mp3", "LT_sample_valid_P3_01.mp3"]:
        with open(os.path.join(dir_path, audio_file), "wb") as f:
            f.write(b"MOCK MP3 DATA")
            
    print("Test fixtures generated successfully in:", dir_path)

if __name__ == "__main__":
    main()

