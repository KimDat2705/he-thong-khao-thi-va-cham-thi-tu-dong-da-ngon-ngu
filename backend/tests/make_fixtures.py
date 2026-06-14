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
def create_real_listening_docx(filepath):
    import zlib
    import struct
    # Ảnh PNG 1x1 sinh bằng stdlib — KHÔNG dùng Pillow (Pillow không có trong requirements/CI).
    def _png_1px():
        def _chunk(tag, data):
            c = tag + data
            return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)
        sig = b"\x89PNG\r\n\x1a\n"
        ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
        idat = zlib.compress(b"\x00\xff\x00\x00")
        return sig + _chunk(b"IHDR", ihdr) + _chunk(b"IDAT", idat) + _chunk(b"IEND", b"")
    temp_img_path = os.path.join(os.path.dirname(filepath), "temp_mock_img.png")
    with open(temp_img_path, "wb") as f:
        f.write(_png_1px())
    
    doc = docx.Document()
    
    # 1. Header table (Table 0)
    t0 = doc.add_table(rows=1, cols=2)
    t0.cell(0, 0).text = "BỘ GIÁO DỤC & ĐÀO TẠO TRƯỜNG ĐẠI HỌC THÀNH ĐÔNG"
    t0.cell(0, 1).text = "ĐỀ THI CHUẨN ĐẦU RA TIẾNG ANH Môn: Listening"
    
    # Empty paragraph
    doc.add_paragraph("")
    
    # 2. Set ID table (Table 1)
    t1 = doc.add_table(rows=1, cols=2)
    t1.cell(0, 0).text = ""
    t1.cell(0, 1).text = "Mã đề thi LT.9999"
    
    doc.add_paragraph("")
    doc.add_paragraph("(Đề thi gồm 11 trang...)")
    doc.add_paragraph("Họ và tên thí sinh: ...")
    
    # 3. Directions table (Table 2) with "PART 1"
    t2 = doc.add_table(rows=1, cols=1)
    t2.cell(0, 0).text = "LISTENING TEST\nPART 1\nDirections: ..."
    t2.cell(0, 0).paragraphs[0].add_run().add_picture(temp_img_path)
    
    # Part 1 questions
    p1 = doc.add_paragraph("1.")
    p1.add_run().add_picture(temp_img_path)
    doc.add_paragraph("")
    
    p2 = doc.add_paragraph("2.")
    p2.add_run().add_picture(temp_img_path)
    
    doc.add_paragraph("3.")
    p4 = doc.add_paragraph("")
    p4.add_run().add_picture(temp_img_path)
    
    t3 = doc.add_table(rows=1, cols=2)
    t3.cell(0, 0).text = "4."
    t3.cell(0, 1).paragraphs[0].add_run().add_picture(temp_img_path)
    doc.add_paragraph("")
    
    # Part 2 directions
    t5_dir = doc.add_table(rows=1, cols=1)
    t5_dir.cell(0, 0).text = "PART 2\nDirections: ..."
    doc.add_paragraph("")
    
    # Table 6: grid for Part 2 questions (Mini Part 2: 2 questions: Q5 and Q6)
    t6 = doc.add_table(rows=1, cols=2)
    t6.cell(0, 0).text = "5. Mark your answer on your answer sheet."
    t6.cell(0, 1).text = "6. Mark your answer on your answer sheet."
    doc.add_paragraph("")
    
    # Part 3
    doc.add_paragraph("Part 3:")
    doc.add_paragraph("Directions: ...")
    
    # Table 7: Part 3 grouped questions
    # 1 cell containing 2 groups (Q7-Q9 and Q10-Q12) separated by "---"
    t7 = doc.add_table(rows=1, cols=1)
    cell = t7.cell(0, 0)
    
    # Group 1 (Q7-Q9)
    cell.paragraphs[0].text = "7. Question seven text?"
    cell.add_paragraph("(A) Option A")
    cell.add_paragraph("(B) Option B")
    cell.add_paragraph("(C) Option C")
    cell.add_paragraph("(D) Option D")
    cell.add_paragraph("")
    
    cell.add_paragraph("8. Question eight text?")
    cell.add_paragraph("(A) Go to")
    cell.add_paragraph("the conference center")
    cell.add_paragraph("(B) Option B")
    cell.add_paragraph("(C) Option C")
    cell.add_paragraph("(D) Option D")
    cell.add_paragraph("")
    
    cell.add_paragraph("9. Question nine text?")
    cell.add_paragraph("(A) Option A")
    cell.add_paragraph("(B) Option B")
    cell.add_paragraph("(C) Option C")
    cell.add_paragraph("(D) Option D")
    
    cell.add_paragraph("--------------------------------------------------")
    
    # Group 2 (Q10-Q12)
    cell.add_paragraph("10. Question ten text?")
    cell.add_paragraph("(A) Option A")
    cell.add_paragraph("(B) Option B")
    cell.add_paragraph("(C) Option C")
    cell.add_paragraph("(D) Option D")
    cell.add_paragraph("")
    
    cell.add_paragraph("11. Question eleven text?")
    cell.add_paragraph("(A) Option A")
    cell.add_paragraph("(B) Option B")
    cell.add_paragraph("(C) Option C")
    cell.add_paragraph("(D) Option D")
    cell.add_paragraph("")
    
    cell.add_paragraph("12. Question twelve text?")
    cell.add_paragraph("(A) Option A")
    cell.add_paragraph("(B) Option B")
    cell.add_paragraph("(C) Option C")
    cell.add_paragraph("(D) Option D")
    
    cell.paragraphs[-1].add_run().add_picture(temp_img_path)
    
    doc.add_paragraph("")
    
    # Part 4
    doc.add_paragraph("Part 4:")
    doc.add_paragraph("Directions: ...")
    
    # Table 8: Part 4 grouped questions (Group 3: Q13-Q15)
    t8 = doc.add_table(rows=1, cols=1)
    cell8 = t8.cell(0, 0)
    cell8.paragraphs[0].text = "13. Question thirteen text?"
    cell8.add_paragraph("(A) Option A")
    cell8.add_paragraph("(B) Option B")
    cell8.add_paragraph("(C) Option C")
    cell8.add_paragraph("(D) Option D")
    cell8.add_paragraph("")
    
    cell8.add_paragraph("14. Question fourteen text?")
    cell8.add_paragraph("(A) Option A")
    cell8.add_paragraph("(B) Option B")
    cell8.add_paragraph("(C) Option C")
    cell8.add_paragraph("(D) Option D")
    cell8.add_paragraph("")
    
    cell8.add_paragraph("15. Question fifteen text?")
    cell8.add_paragraph("(A) Option A")
    cell8.add_paragraph("(B) Option B")
    cell8.add_paragraph("(C) Option C")
    cell8.add_paragraph("(D) Option D")
    
    cell8.paragraphs[-1].add_run().add_picture(temp_img_path)
    
    doc.add_paragraph("THE END")
    doc.save(filepath)
    
    if os.path.exists(temp_img_path):
        os.remove(temp_img_path)


def create_real_answer_key_xlsx(filepath):
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "LT9999 Key"
    
    # Title
    ws["A1"] = "TOEIC - LISTENING -  LT9999"
    
    # Block 1 headers
    ws["A3"] = "Câu"
    ws["B3"] = "Đáp án"
    # Block 2 headers
    ws["D3"] = "Câu"
    ws["E3"] = "Đáp án"
    
    answers = ["A", "B", "C", "D"]
    
    # Write Q1-Q8 (Block 1)
    for idx in range(1, 9):
        row = idx + 3
        ws[f"A{row}"] = idx
        ws[f"B{row}"] = answers[idx % 4]
        
    # Write Q9-Q15 (Block 2)
    for idx in range(9, 16):
        row = (idx - 9) + 4
        ws[f"D{row}"] = idx
        ws[f"E{row}"] = answers[idx % 4]
        
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
    create_real_listening_docx(os.path.join(dir_path, "LT_real_sample.docx"))
    create_real_answer_key_xlsx(os.path.join(dir_path, "Key_LT9999.xlsx"))
    
    # Create mock audio files
    for audio_file in ["LT_sample_valid_P1_01.mp3", "LT_sample_valid_P3_01.mp3"]:
        with open(os.path.join(dir_path, audio_file), "wb") as f:
            f.write(b"MOCK MP3 DATA")
            
    print("Test fixtures generated successfully in:", dir_path)

if __name__ == "__main__":
    main()



