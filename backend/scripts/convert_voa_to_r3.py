"""Chuyển bài VOA (voa_raw.json) → seed R3 (Đọc-hiểu B1) đúng khuôn loader.

Vá nghiệm thu S57m: (1) LÀM SẠCH rác scraper + RÚT GỌN passage về ngữ liệu B1 (~130-150 từ) bằng
voa_clean (trước đây dùng NGUYÊN bài 444-945 từ → quá dài); (2) VALIDATE từng câu Gemini trả (câu
méo → bỏ, KHÔNG sập cả run); (3) ghi cờ nguồn (source_attribution) minh bạch.
"""
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.insert(0, os.path.dirname(__file__))

from app.services.b1_question_gen import B1QuestionGenerator  # noqa: E402
from voa_clean import b1_excerpt, clean_paragraphs, wire_source  # noqa: E402

_LETTERS = ("A", "B", "C", "D")


def _valid_question(q: dict) -> bool:
    """Câu hợp lệ: có stem, đủ 4 phương án A-D không rỗng, answer ∈ {A,B,C,D}."""
    if not isinstance(q, dict):
        return False
    opts = q.get("options")
    if not isinstance(opts, dict) or any(not str(opts.get(k, "")).strip() for k in _LETTERS):
        return False
    return bool(str(q.get("stem", "")).strip()) and str(q.get("answer", "")).strip().upper() in _LETTERS


def generate_r3(generator, passage: str, title: str) -> list:
    """Sinh 5 câu Đọc-hiểu B1 TỪ passage đã rút gọn (không phải nguyên bài). Trả list câu HỢP LỆ."""
    system = (
        "You are a VSTEP B1 English item writer. Given a SHORT B1-level reading passage, write 5 "
        "reading-comprehension multiple-choice questions answerable ONLY from the passage, at B1 level. "
        "Each question has exactly 4 options A, B, C, D and exactly one correct answer. "
        'Output ONLY JSON: {"questions": [{"stem": "...", "options": {"A": "...", "B": "...", '
        '"C": "...", "D": "..."}, "answer": "A|B|C|D"}]}'
    )
    user = f"Title: {title}\nPassage:\n{passage}\n\nWrite exactly 5 B1 comprehension questions."
    try:
        raw = generator._call_gemini(system, user)
        raw = raw.strip()
        s, e = raw.find("{"), raw.rfind("}")
        if s != -1 and e > s:
            raw = raw[s:e + 1]
        qs = json.loads(raw).get("questions", [])
    except Exception as exc:
        print(f"  ! lỗi sinh câu: {exc}")
        return []
    return [q for q in qs if _valid_question(q)]


def format_to_s3(passage: str, questions: list) -> tuple:
    """Dựng s3_raw (header + passage NGẮN + 5 câu 16-20 mỗi phương án 1 block) + s3_answers."""
    s3_raw = [
        {"kind": "p", "text": "Section 3 Questions 16-20 (5 points)"},
        {"kind": "p", "text": "Read the text and questions below. For each question, circle the "
                              "letter next to the correct answer (A, B, C or D)."},
        {"kind": "p", "text": ""},
        {"kind": "p", "text": passage},
        {"kind": "p", "text": ""},
    ]
    s3_answers = {}
    for i, q in enumerate(questions[:5]):
        n = 16 + i
        s3_raw.append({"kind": "p", "text": f"{n}. {str(q['stem']).strip()}"})
        for k in _LETTERS:
            s3_raw.append({"kind": "p", "text": f"{k}. {str(q['options'][k]).strip()}"})
        s3_raw.append({"kind": "p", "text": ""})
        s3_answers[str(n)] = str(q["answer"]).strip().upper()
    return s3_raw, s3_answers


def main():
    voa_path = os.path.join(os.path.dirname(__file__), "..", "app", "data", "factory_seeds", "voa_raw.json")
    if not os.path.exists(voa_path):
        print("voa_raw.json not found!")
        return
    with open(voa_path, encoding="utf-8") as f:
        articles = json.load(f)
    print(f"Loaded {len(articles)} VOA articles.")

    generator = B1QuestionGenerator()
    out = []
    for i, art in enumerate(articles):
        passage = b1_excerpt(clean_paragraphs(art.get("content", "")))
        wc = len(passage.split())
        print(f"[{i + 1}/{len(articles)}] {art.get('title', '')[:45]} (passage {wc} từ)")
        if wc < 60:
            print("  ! passage quá ngắn sau lọc → bỏ")
            continue
        questions = generate_r3(generator, passage, art.get("title", ""))
        if len(questions) < 5:
            print(f"  ! chỉ {len(questions)}/5 câu hợp lệ → bỏ")
            continue
        s3_raw, s3_answers = format_to_s3(passage, questions)
        out.append({
            "ma_de": f"VOA.R3.{1000 + i}",
            "s3_raw": s3_raw, "s3_answers": s3_answers,
            "s3_complete": True, "s3_has_image": False,
            "source_url": art.get("url"),
            "source_attribution": wire_source(art.get("content", "")) or "VOA Learning English",
        })
        print("  -> OK")
    out_path = os.path.join(os.path.dirname(__file__), "..", "app", "data", "factory_seeds", "bank_voa_r3.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"Saved {len(out)} clean R3 items → {out_path}")


if __name__ == "__main__":
    main()
