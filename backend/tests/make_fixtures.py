import os
import io
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
    png_data = _png_1px()
    
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
    t2.cell(0, 0).paragraphs[0].add_run().add_picture(io.BytesIO(png_data))
    
    # Part 1 questions
    p1 = doc.add_paragraph("1.")
    p1.add_run().add_picture(io.BytesIO(png_data))
    doc.add_paragraph("")
    
    p2 = doc.add_paragraph("2.")
    p2.add_run().add_picture(io.BytesIO(png_data))
    
    doc.add_paragraph("3.")
    p4 = doc.add_paragraph("")
    p4.add_run().add_picture(io.BytesIO(png_data))
    
    t3 = doc.add_table(rows=1, cols=2)
    t3.cell(0, 0).text = "4."
    t3.cell(0, 1).paragraphs[0].add_run().add_picture(io.BytesIO(png_data))
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
    
    cell.paragraphs[-1].add_run().add_picture(io.BytesIO(png_data))
    
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
    
    cell8.paragraphs[-1].add_run().add_picture(io.BytesIO(png_data))
    
    doc.add_paragraph("THE END")
    doc.save(filepath)


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
        if idx in (5, 6):
            ws[f"B{row}"] = "A"
        else:
            ws[f"B{row}"] = answers[idx % 4]
        
    # Write Q9-Q15 (Block 2)
    for idx in range(9, 16):
        row = (idx - 9) + 4
        ws[f"D{row}"] = idx
        ws[f"E{row}"] = answers[idx % 4]
        
    wb.save(filepath)
    wb.close()


def create_real_reading_answer_key_xlsx(filepath):
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "RT9999 Key"
    
    # Title
    ws["A1"] = "TOEIC - READING -  RT9999"
    
    # Block 1 headers
    ws["A3"] = "Câu"
    ws["B3"] = "Đáp án"
    # Block 2 headers
    ws["D3"] = "Câu"
    ws["E3"] = "Đáp án"
    
    answers = ["A", "B", "C", "D"]
    
    # Write Q1-Q6 (Block 1)
    for idx in range(1, 7):
        row = idx + 3
        ws[f"A{row}"] = idx
        ws[f"B{row}"] = answers[idx % 4]
        
    # Write Q7-Q12 (Block 2)
    for idx in range(7, 13):
        row = (idx - 7) + 4
        ws[f"D{row}"] = idx
        ws[f"E{row}"] = answers[idx % 4]
        
    wb.save(filepath)
    wb.close()


def create_real_reading_docx(filepath):
    import zlib
    import struct
    # PNG 1px
    def _png_1px():
        def _chunk(tag, data):
            c = tag + data
            return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)
        sig = b"\x89PNG\r\n\x1a\n"
        ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
        idat = zlib.compress(b"\x00\xff\x00\x00")
        return sig + _chunk(b"IHDR", ihdr) + _chunk(b"IDAT", idat) + _chunk(b"IEND", b"")
    png_data = _png_1px()
    
    doc = docx.Document()
    
    # 1. Header table (Table 0)
    t0 = doc.add_table(rows=1, cols=2)
    t0.cell(0, 0).text = "BỘ GIÁO DỤC & ĐÀO TẠO TRƯỜNG ĐẠI HỌC THÀNH ĐÔNG"
    t0.cell(0, 1).text = "ĐỀ THI CHUẨN ĐẦU RA TIẾNG ANH Môn: Reading"
    
    doc.add_paragraph("")
    
    # 2. Set ID table (Table 1)
    t1 = doc.add_table(rows=1, cols=2)
    t1.cell(0, 0).text = ""
    t1.cell(0, 1).text = "Mã đề thi RT.9999"
    
    doc.add_paragraph("")
    
    # --- PART 5 ---
    doc.add_paragraph("READING TEST\nPART 5\nDirections: ...")
    
    doc.add_paragraph("1. Question one content here _______.")
    doc.add_paragraph("(A) Option A1")
    doc.add_paragraph("(B) Option B1")
    doc.add_paragraph("(C) Option C1")
    doc.add_paragraph("(D) Option D1")
    
    # Q2: Option-A-inline format
    doc.add_paragraph("2. Question two content here _______ (A) Option A2")
    doc.add_paragraph("(B) Option B2")
    doc.add_paragraph("(C) Option C2")
    doc.add_paragraph("(D) Option D2")
    
    doc.add_paragraph("")
    
    # --- PART 6 ---
    doc.add_paragraph("PART 6\nDirections: ...")
    doc.add_paragraph("Questions 3-6 refer to the following email.")
    
    # Passage text paragraphs
    doc.add_paragraph("To: employee@company.com")
    doc.add_paragraph("From: hr@company.com")
    doc.add_paragraph("Subject: Policy change")
    doc.add_paragraph("Dear staff, we are writing to inform you that the policy will _______ (3) change next week. Please _______ (4) the new rules.")
    doc.add_paragraph("This is very _______ (5) for everyone. If you have questions, please _______ (6) us.")
    
    # Part 6 4x2 table for options
    t_opt6 = doc.add_table(rows=4, cols=2)
    t_opt6.cell(0, 0).text = "3."
    t_opt6.cell(0, 1).text = "(A) quick (B) quickly (C) quicker (D) quickest"
    
    t_opt6.cell(1, 0).text = "4."
    t_opt6.cell(1, 1).text = "(A) read (B) reads (C) reading (D) to read"
    
    t_opt6.cell(2, 0).text = "5."
    t_opt6.cell(2, 1).text = "(A) important (B) import (C) importance (D) importantly"
    
    t_opt6.cell(3, 0).text = "6."
    t_opt6.cell(3, 1).text = "(A) contact (B) contacts (C) contacting (D) contacted"
    
    doc.add_paragraph("")
    
    # --- PART 7 ---
    doc.add_paragraph("PART 7\nDirections: ...")
    
    # Group 1 (Q7-8) - 1x1 table passage + inline drawing + all-inline paragraph options
    doc.add_paragraph("Questions 7-8 refer to the following announcement.")
    
    t_passage1 = doc.add_table(rows=1, cols=1)
    p_cell = t_passage1.cell(0, 0).paragraphs[0]
    p_cell.text = "ANNOUNCEMENT: Office renovation is starting tomorrow."
    p_cell.add_run().add_picture(io.BytesIO(png_data))
    
    # All-options-inline paragraph format
    doc.add_paragraph("7. What is starting tomorrow?\n(A) Renovation\n(B) Class\n(C) Holiday\n(D) Meeting")
    doc.add_paragraph("8. Who is affected?\n(A) Staff\n(B) Students\n(C) Visitors\n(D) Clients")
    
    doc.add_paragraph("")
    
    # Group 2 (Q9-12) - Double passage + sandwich question (Q9) + table options (Q10-12)
    doc.add_paragraph("Questions 9-12 refer to the following advertisement and review.")
    doc.add_paragraph("Advertisement:")
    doc.add_paragraph("Buy our product. It is the best.")
    doc.add_paragraph("Review:")
    doc.add_paragraph("I bought it and it works great.")
    
    # Q9: Sandwich layout (question paragraph, quote paragraph, options paragraph)
    doc.add_paragraph("9. What is being advertised?")
    doc.add_paragraph("“Buy our product. It is the best.”")
    doc.add_paragraph("(A) A product\n(B) A service\n(C) A company\n(D) A store")
    
    # Q10
    doc.add_paragraph("10. What does the review say?")
    t_opt10 = doc.add_table(rows=4, cols=2)
    t_opt10.cell(0, 0).text = "(A)"
    t_opt10.cell(0, 1).text = "It works great"
    t_opt10.cell(1, 0).text = "(B)"
    t_opt10.cell(1, 1).text = "It is bad"
    t_opt10.cell(2, 0).text = "(C)"
    t_opt10.cell(2, 1).text = "It is cheap"
    t_opt10.cell(3, 0).text = "(D)"
    t_opt10.cell(3, 1).text = "It is expensive"
    
    # Q11
    doc.add_paragraph("11. Question eleven content?")
    t_opt11 = doc.add_table(rows=4, cols=2)
    t_opt11.cell(0, 0).text = "(A)"
    t_opt11.cell(0, 1).text = "Option A"
    t_opt11.cell(1, 0).text = "(B)"
    t_opt11.cell(1, 1).text = "Option B"
    t_opt11.cell(2, 0).text = "(C)"
    t_opt11.cell(2, 1).text = "Option C"
    t_opt11.cell(3, 0).text = "(D)"
    t_opt11.cell(3, 1).text = "Option D"
    
    # Q12
    doc.add_paragraph("12. Question twelve content?")
    t_opt12 = doc.add_table(rows=4, cols=2)
    t_opt12.cell(0, 0).text = "(A)"
    t_opt12.cell(0, 1).text = "Option A"
    t_opt12.cell(1, 0).text = "(B)"
    t_opt12.cell(1, 1).text = "Option B"
    t_opt12.cell(2, 0).text = "(C)"
    t_opt12.cell(2, 1).text = "Option C"
    t_opt12.cell(3, 0).text = "(D)"
    t_opt12.cell(3, 1).text = "Option D"
    
    doc.save(filepath)


def create_b1_reading_docx(filepath):
    doc = docx.Document()
    
    # Header Table
    t0 = doc.add_table(rows=1, cols=2)
    t0.cell(0, 0).text = "BỘ GIÁO DỤC VÀ ĐÀO TẠO TRƯỜNG ĐẠI HỌC THÀNH ĐÔNG"
    t0.cell(0, 1).text = "ĐỀ THI TIẾNG ANH B1 CHÂU ÂU"
    
    # Set ID Table
    t1 = doc.add_table(rows=1, cols=1)
    t1.cell(0, 0).text = "Mã đề:   EB1.9999"
    
    doc.add_paragraph("PART ONE 		READING")
    
    # Section 1
    doc.add_paragraph("Section 1		Questions 1-10 (10 points)")
    doc.add_paragraph("Circle the letter next to the word or phrase which best completes each sentence (A, B, C or D)")
    for q in range(1, 11):
        doc.add_paragraph(f"{q}. Question content {q} _______")
        doc.add_paragraph(f"\tA. Option A\tB. Option B\t\tC. Option C\t\tD. Option D")
        
    # Section 2
    doc.add_paragraph("Section 2	Questions 11-15 (5 points)")
    doc.add_paragraph("Look at the text in each question. What does it say?")
    
    t2 = doc.add_table(rows=5, cols=3)
    for q in range(11, 16):
        r = q - 11
        t2.cell(r, 0).text = f"{q}."
        t2.cell(r, 1).text = f"Signboard text for question {q}"
        t2.cell(r, 2).text = f"A. Explanation A\nB. Explanation B\nC. Explanation C"
        
    # Section 3
    doc.add_paragraph("Section 3	Questions 16-20 (5 points)")
    doc.add_paragraph("Read the text and questions below.")
    doc.add_paragraph("Passage paragraph 1 of dentist text.")
    doc.add_paragraph("Passage paragraph 2. Sophia Ashley, Oxford.")
    
    for q in range(16, 21):
        doc.add_paragraph(f"{q}. Question dental {q}?")
        doc.add_paragraph("A. dentist A")
        doc.add_paragraph("B. dentist B")
        doc.add_paragraph("C. dentist C")
        doc.add_paragraph("D. dentist D")
        
    # Section 4
    doc.add_paragraph("Section 4	Questions 21-30 (10 points)")
    doc.add_paragraph("Read the text below and fill each of the blanks with ONE suitable word.")
    doc.add_paragraph("THE GORILLA")
    doc.add_paragraph("The gorilla is a shy creature. In (21) ……………, it is quite different. It stands up if it wants to (22) ………………… an enemy.")
    doc.add_paragraph("Gorillas are the largest and (23) …………….… powerful. Adult males (24) ……………… from 135 to 230 kg.")
    doc.add_paragraph("Females are smaller. (25) ……………………. males and females are strong. They (26) ……………… their days in search (27) …………….for food.")
    doc.add_paragraph("Unfortunately, few animals are (28) …………….. in the wild. This is because people cut forests in (29) …………………. gorillas live. If we want to save them, we (30) …………… take action.")
    
    doc.add_paragraph("PART TWO		WRITING")
    
    # Writing Section 1
    doc.add_paragraph("Section 1 (10 points)")
    doc.add_paragraph("Finish each of the following sentences...")
    doc.add_paragraph("Example:	I haven’t enjoyed myself so much")
    doc.add_paragraph("Answer:	It’s years since...")
    doc.add_paragraph("How is your surname spelt?")
    doc.add_paragraph("How do ……………………………………………………………………………………?")
    doc.add_paragraph("At the moment, they are cleaning Mr. Lazylion’s car.")
    doc.add_paragraph("At the moment Mr. Lazylion ……………………………..………………………………..")
    
    # Writing Section 2
    doc.add_paragraph("Section 2 (20 points)")
    doc.add_paragraph("You are Hoa Tran. Write a letter to your penfriend.")
    doc.add_paragraph("Dear friend, I’ve got flu. What should I do?")
    doc.add_paragraph("Now write a letter. You should write about 100 words.")
    doc.add_paragraph("--- The end ---")
    
    doc.save(filepath)


def create_b1_answer_key_docx(filepath):
    doc = docx.Document()
    
    doc.add_paragraph("MÃ PHÁCH: ………………; MÃ ĐỀ: EB1.9999")
    doc.add_paragraph("PART 1: READING")
    doc.add_paragraph("Câu 1 - 20:")
    
    # Table 1: Section 1, 2, 3 answers
    # 8 rows, 19 columns
    t1 = doc.add_table(rows=8, cols=19)
    # Row 0: Merged header blocks
    for c in range(9):
        t1.cell(0, c).text = "SECTION 1"
    t1.cell(0, 9).text = ""
    for c in range(10, 14):
        t1.cell(0, c).text = "SECTION 2"
    t1.cell(0, 14).text = ""
    for c in range(15, 19):
        t1.cell(0, c).text = "SECTION 3"
        
    # Row 1: Subheaders
    headers = ['Câu', 'Đáp án', 'Thang điểm', 'Điểm chấm', '']
    row1 = headers * 3 + ['Câu', 'Đáp án', 'Thang điểm', 'Điểm chấm']
    for c, val in enumerate(row1):
        t1.cell(1, c).text = val
        
    # Rows 2-6: Data
    sec1_ans = {1: "A", 2: "B", 3: "B", 4: "A", 5: "A", 6: "B", 7: "A", 8: "D", 9: "B", 10: "A"}
    sec2_ans = {11: "A", 12: "C", 13: "C", 14: "B", 15: "A"}
    sec3_ans = {16: "D", 17: "A", 18: "D", 19: "B", 20: "C"}
    
    for r in range(2, 7):
        offset = r - 2
        # Section 1 block 1 (Q1-5)
        t1.cell(r, 0).text = str(offset + 1)
        t1.cell(r, 1).text = sec1_ans[offset + 1]
        t1.cell(r, 2).text = "1"
        
        # Section 1 block 2 (Q6-10)
        t1.cell(r, 5).text = str(offset + 6)
        t1.cell(r, 6).text = sec1_ans[offset + 6]
        t1.cell(r, 7).text = "1"
        
        # Section 2 (Q11-15)
        t1.cell(r, 10).text = str(offset + 11)
        t1.cell(r, 11).text = sec2_ans[offset + 11]
        t1.cell(r, 12).text = "1"
        
        # Section 3 (Q16-20)
        t1.cell(r, 15).text = str(offset + 16)
        t1.cell(r, 16).text = sec3_ans[offset + 16]
        t1.cell(r, 17).text = "1"
        
    # Row 7: Totals
    t1.cell(7, 0).text = "Tổng"
    t1.cell(7, 2).text = "5"
    t1.cell(7, 5).text = "Tổng"
    t1.cell(7, 7).text = "5"
    t1.cell(7, 10).text = "Tổng"
    t1.cell(7, 12).text = "5"
    t1.cell(7, 15).text = "Tổng"
    t1.cell(7, 17).text = "5"
    
    doc.add_paragraph("Câu 21 - 30:")
    
    # Table 2: Section 4 answers
    # 8 rows, 9 columns
    t2 = doc.add_table(rows=8, cols=9)
    for c in range(9):
        t2.cell(0, c).text = "SECTION 4"
    headers_t2 = ['Câu', 'Đáp án', 'Thang điểm', 'Điểm chấm', '']
    row1_t2 = headers_t2 + ['Câu', 'Đáp án', 'Thang điểm', 'Điểm chấm']
    for c, val in enumerate(row1_t2):
        t2.cell(1, c).text = val
        
    sec4_ans = {
        21: "fact", 22: "frighten", 23: "most", 24: "weigh", 25: "Both",
        26: "spend", 27: "search", 28: "left", 29: "which", 30: "must"
    }
    for r in range(2, 7):
        offset = r - 2
        # Q21-25
        t2.cell(r, 0).text = str(offset + 21)
        t2.cell(r, 1).text = sec4_ans[offset + 21]
        t2.cell(r, 2).text = "1"
        
        # Q26-30
        t2.cell(r, 5).text = str(offset + 26)
        t2.cell(r, 6).text = sec4_ans[offset + 26]
        t2.cell(r, 7).text = "1"
        
    t2.cell(7, 0).text = "Tổng"
    t2.cell(7, 2).text = "5"
    t2.cell(7, 5).text = "Tổng"
    t2.cell(7, 7).text = "5"
    
    doc.add_paragraph("PART 2: WRITING")
    doc.add_paragraph("Tổng điểm bài thi: 60")
    
    doc.save(filepath)


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
    create_real_reading_docx(os.path.join(dir_path, "RT_real_sample.docx"))
    create_real_reading_answer_key_xlsx(os.path.join(dir_path, "Key_RT9999.xlsx"))
    create_b1_reading_docx(os.path.join(dir_path, "B1_exam_sample.docx"))
    create_b1_answer_key_docx(os.path.join(dir_path, "B1_key_sample.docx"))
    
    # Create mock audio files
    mock_audios = [
        "LT_sample_valid_P1_01.mp3",
        "LT_sample_valid_P3_01.mp3",
        "9990 - 9999.mp3",
        "9998 - 9999.mp3"
    ]
    for audio_file in mock_audios:
        with open(os.path.join(dir_path, audio_file), "wb") as f:
            f.write(b"MOCK MP3 DATA")
            
    print("Test fixtures generated successfully in:", dir_path)

if __name__ == "__main__":
    main()



