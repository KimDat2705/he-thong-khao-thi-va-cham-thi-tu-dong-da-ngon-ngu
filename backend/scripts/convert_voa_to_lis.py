import json
import os
import sys
import uuid
import requests

# Thêm thư mục gốc backend vào sys.path để import được app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.b1_question_gen import B1QuestionGenerator

def download_audio(url, code, media_dir):
    try:
        resp = requests.get(url, stream=True)
        resp.raise_for_status()
        filename = f"{code}.mp3"
        path = os.path.join(media_dir, filename)
        with open(path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
        return filename
    except Exception as e:
        print(f"Error downloading audio: {e}")
        return None

def generate_lis_from_voa(generator, article, index):
    system = (
        "You are a VSTEP B1 English item writer. "
        "Given a listening transcript, write questions in two parts matching VSTEP B1 format:\n"
        "Part 1: 5 multiple-choice questions (options A, B, C). \n"
        "Part 2: 10 gap-fill questions (short answers, exactly 1-3 words each) that test listening for details. "
        "The gap fills should represent missing words from a summary of the text. "
        "Output ONLY JSON: {\"l1_stems\": [\"Q1\", \"Q2\", \"Q3\", \"Q4\", \"Q5\"], "
        "\"l1_options\": {\"1\": {\"A\":\"..\",\"B\":\"..\",\"C\":\"..\"}, ...}, "
        "\"l2_summary\": \"A short summary with _____ (6) _____ (7)...\", "
        "\"answers\": {\"1\": \"A\", ..., \"6\": \"word\", \"7\": \"word\"}}"
    )
    user = (
        f"Transcript:\n{article['content']}\n\n"
        f"Generate 5 MCQs and 10 gap-fills."
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
        return data
    except Exception as e:
        print(f"Error generating for article {article['url']}: {e}")
        return None

def main():
    voa_raw_path = os.path.join(os.path.dirname(__file__), "..", "app", "data", "factory_seeds", "voa_raw.json")
    if not os.path.exists(voa_raw_path):
        print("voa_raw.json not found!")
        return
        
    with open(voa_raw_path, "r", encoding="utf-8") as f:
        articles = json.load(f)
        
    print(f"Loaded {len(articles)} articles from VOA.")
    
    generator = B1QuestionGenerator()
    out_lis = []
    
    media_dir = os.path.join(os.path.dirname(__file__), "..", "audio_data")
    os.makedirs(media_dir, exist_ok=True)
    
    # Process only 3 articles for Listening as a Proof of Concept
    for i, article in enumerate(articles[:3]):
        print(f"Processing Listening for article {i+1}/3: {article['title']}")
        
        # Audio
        code = f"VOA.LIS.{1000+i}"
        audio_name = None
        if article.get("audio_url"):
            print(f"Downloading audio: {article['audio_url']}")
            audio_name = download_audio(article["audio_url"], code, media_dir)
            
        # Questions
        data = generate_lis_from_voa(generator, article, i)
        
        if data and "answers" in data:
            record = {
                "code": code,
                "src_code": code,
                "audio_name": audio_name or "",
                "l1_stems": data.get("l1_stems", []),
                "l1_options": data.get("l1_options", {}),
                "l2_summary": data.get("l2_summary", ""),
                "l2_gaps": [6,7,8,9,10,11,12,13,14,15],
                "answers": data.get("answers", {}),
                "source_url": article["url"]
            }
            out_lis.append(record)
            print(" -> Success.")
        else:
            print(" -> Failed to generate questions.")
            
    out_path = os.path.join(os.path.dirname(__file__), "..", "app", "data", "factory_seeds", "pool_voa_lis.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out_lis, f, ensure_ascii=False, indent=2)
    print(f"Saved {len(out_lis)} Listening items to {out_path}")

if __name__ == "__main__":
    main()
