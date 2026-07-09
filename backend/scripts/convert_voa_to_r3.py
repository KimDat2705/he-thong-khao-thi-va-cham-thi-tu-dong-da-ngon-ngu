import json
import os
import sys

# Thêm thư mục gốc backend vào sys.path để import được app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.b1_question_gen import B1QuestionGenerator

def generate_r3_from_voa(generator, article, index):
    system = (
        "You are a VSTEP B1 English item writer. "
        "Given a reading passage, write 5 reading comprehension multiple-choice questions "
        "that test understanding of the text at the B1 level. "
        "Each question must have exactly 4 options A, B, C, D and exactly one correct answer. "
        "Output ONLY JSON: {\"questions\": [{\"stem\": \"...\", \"options\": {\"A\": \"...\", \"B\": \"...\", \"C\": \"...\", \"D\": \"...\"}, \"answer\": \"A|B|C|D\"}]}"
    )
    user = (
        f"Passage Title: {article['title']}\n"
        f"Passage Content:\n{article['content']}\n\n"
        f"Generate 5 multiple choice questions for this passage."
    )
    
    try:
        raw = generator._call_gemini(system, user)
        # Parse JSON
        raw = raw.strip()
        start = raw.find("{")
        end = raw.rfind("}")
        if start != -1 and end > start:
            raw = raw[start:end + 1]
        data = json.loads(raw)
        return data.get("questions", [])
    except Exception as e:
        print(f"Error generating for article {article['url']}: {e}")
        return []

def format_to_s3(article, questions, start_qnum=16):
    s3_raw = [
        {"kind": "p", "text": "Section 3 Questions 16-20 (5 points)"},
        {"kind": "p", "text": "Read the text and questions below. For each question, circle the letter next to the correct answer (A, B, C or D)."},
        {"kind": "p", "text": ""},
        {"kind": "p", "text": article["content"]},
        {"kind": "p", "text": ""}
    ]
    
    s3_answers = {}
    
    qnum = start_qnum
    for q in questions:
        s3_raw.append({"kind": "p", "text": f"{qnum}. {q['stem']}"})
        s3_raw.append({"kind": "p", "text": f"A. {q['options']['A']}"})
        s3_raw.append({"kind": "p", "text": f"B. {q['options']['B']}"})
        s3_raw.append({"kind": "p", "text": f"C. {q['options']['C']}"})
        s3_raw.append({"kind": "p", "text": f"D. {q['options']['D']}"})
        s3_raw.append({"kind": "p", "text": ""})
        
        s3_answers[str(qnum)] = q['answer']
        qnum += 1
        
    return s3_raw, s3_answers

def main():
    voa_raw_path = os.path.join(os.path.dirname(__file__), "..", "app", "data", "factory_seeds", "voa_raw.json")
    if not os.path.exists(voa_raw_path):
        print("voa_raw.json not found!")
        return
        
    with open(voa_raw_path, "r", encoding="utf-8") as f:
        articles = json.load(f)
        
    print(f"Loaded {len(articles)} articles from VOA.")
    
    generator = B1QuestionGenerator()
    out_bank = []
    
    for i, article in enumerate(articles):
        print(f"Processing article {i+1}/{len(articles)}: {article['title']}")
        questions = generate_r3_from_voa(generator, article, i)
        
        if len(questions) == 5:
            s3_raw, s3_answers = format_to_s3(article, questions)
            record = {
                "ma_de": f"VOA.R3.{1000 + i}",
                "s3_raw": s3_raw,
                "s3_answers": s3_answers,
                "s3_complete": True,
                "s3_has_image": False,
                "source_url": article["url"]
            }
            out_bank.append(record)
            print(" -> Success.")
        else:
            print(f" -> Failed to get exactly 5 questions (got {len(questions)}).")
            
    out_path = os.path.join(os.path.dirname(__file__), "..", "app", "data", "factory_seeds", "bank_voa_r3.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out_bank, f, ensure_ascii=False, indent=2)
    print(f"Saved {len(out_bank)} R3 items to {out_path}")

if __name__ == "__main__":
    main()
