import os
import docx

def create_valid_docx(filepath):
    doc = docx.Document()
    lines = [
        "[Group]",
        "Part: 3",
        "Topic: Meetings",
        "Audio: 2601_Part3_01.mp3",
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
        "Audio: 2601_Part1.mp3",
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
        "Audio: non_existent_file.mp3",
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

def main():
    # Make sure we are writing to the correct absolute directory
    dir_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "parser"))
    os.makedirs(dir_path, exist_ok=True)
    
    create_valid_docx(os.path.join(dir_path, "LT_sample_valid.docx"))
    create_missing_audio_docx(os.path.join(dir_path, "LT_sample_missing_audio.docx"))
    create_missing_answer_docx(os.path.join(dir_path, "LT_sample_missing_answer.docx"))
    
    # Create mock audio files
    for audio_file in ["2601_Part1.mp3", "2601_Part3_01.mp3"]:
        with open(os.path.join(dir_path, audio_file), "wb") as f:
            f.write(b"MOCK MP3 DATA")
            
    print("Test fixtures generated successfully in:", dir_path)

if __name__ == "__main__":
    main()
