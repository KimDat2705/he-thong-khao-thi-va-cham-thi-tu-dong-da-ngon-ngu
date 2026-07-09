"""Chuyển bài VOA (voa_raw.json) → seed Nghe (Listening B1) đúng khuôn loader.

Vá nghiệm thu S57m: (1) LÀM SẠCH rác scraper (voa_clean) trước khi đưa vào Gemini; (2) VALIDATE
l1_stems (5) + answers đủ khóa 1-15 trước khi ghi (trước đây record thiếu bị load_lis_seeds bỏ lặng);
(3) l2_gaps LẤY TỪ answers thay vì hardcode; (4) requests.get có timeout + User-Agent (tránh treo).
Ghi cờ nguồn minh bạch. Seed hợp lệ KHÔNG phụ thuộc tải được audio (audio là bước render riêng).
"""
import json
import os
import sys

import requests

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.insert(0, os.path.dirname(__file__))

from app.services.b1_question_gen import B1QuestionGenerator  # noqa: E402
from voa_clean import clean_paragraphs, wire_source  # noqa: E402

_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
_N_LIS = 3   # số bài đầu làm Nghe (PoC)


def download_audio(url, code, media_dir):
    """Tải MP3 VOA (best-effort, có timeout). Lỗi → None, KHÔNG làm hỏng seed."""
    try:
        resp = requests.get(url, stream=True, headers=_HEADERS, timeout=(10, 60))
        resp.raise_for_status()
        path = os.path.join(media_dir, f"{code}.mp3")
        with open(path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
        return f"{code}.mp3"
    except Exception as exc:
        print(f"  ! tải audio lỗi: {exc}")
        return None


def generate_lis(generator, transcript, title):
    system = (
        "You are a VSTEP B1 English item writer. Given a short talk transcript, write a B1 listening set:\n"
        "Part 1: 5 short comprehension questions, each with options A, B, C (one correct).\n"
        "Part 2: a short summary with 10 numbered blanks (6..15), each filled by ONE word from the talk.\n"
        'Output ONLY JSON: {"l1_stems": ["Q1".."Q5"], "l1_options": {"1": {"A":"..","B":"..","C":".."}, ...}, '
        '"l2_summary": "... (6) ___ ...", "answers": {"1":"A", ..., "5":"C", "6":"word", ..., "15":"word"}}'
    )
    user = f"Title: {title}\nTranscript:\n{transcript}\n\nWrite 5 MCQs (A/B/C) and 10 one-word gap-fills (6-15)."
    try:
        raw = generator._call_gemini(system, user)
        raw = raw.strip()
        s, e = raw.find("{"), raw.rfind("}")
        if s != -1 and e > s:
            raw = raw[s:e + 1]
        return json.loads(raw)
    except Exception as exc:
        print(f"  ! lỗi sinh Nghe: {exc}")
        return None


def _valid_lis(data):
    """Hợp lệ: l1_stems=5; answers có đủ khóa '1'..'5' (A/B/C) + '6'..'15' (từ không rỗng)."""
    if not isinstance(data, dict):
        return False
    stems = data.get("l1_stems") or []
    ans = data.get("answers") or {}
    if len(stems) != 5:
        return False
    for k in range(1, 6):
        if str(ans.get(str(k), "")).strip().upper() not in ("A", "B", "C"):
            return False
    for k in range(6, 16):
        if not str(ans.get(str(k), "")).strip():
            return False
    return True


def main():
    voa_path = os.path.join(os.path.dirname(__file__), "..", "app", "data", "factory_seeds", "voa_raw.json")
    if not os.path.exists(voa_path):
        print("voa_raw.json not found!")
        return
    with open(voa_path, encoding="utf-8") as f:
        articles = json.load(f)
    generator = B1QuestionGenerator()
    media_dir = os.path.join(os.path.dirname(__file__), "..", "audio_data")
    os.makedirs(media_dir, exist_ok=True)

    out = []
    for i, art in enumerate(articles[:_N_LIS]):
        code = f"VOA.LIS.{1000 + i}"
        transcript = " ".join(clean_paragraphs(art.get("content", "")))
        print(f"[{i + 1}/{_N_LIS}] {art.get('title', '')[:45]}")
        data = generate_lis(generator, transcript, art.get("title", ""))
        if not _valid_lis(data):
            print("  ! Nghe không hợp lệ (thiếu l1_stems/answers) → bỏ")
            continue
        audio_name = download_audio(art["audio_url"], code, media_dir) if art.get("audio_url") else None
        out.append({
            "code": code, "src_code": code, "audio_name": audio_name or "",
            "l1_stems": data["l1_stems"], "l1_options": data.get("l1_options", {}),
            "l2_summary": data.get("l2_summary", ""),
            "l2_gaps": [n for n in range(6, 16) if str(data["answers"].get(str(n), "")).strip()],
            "answers": {str(k): v for k, v in data["answers"].items()},
            "source_url": art.get("url"),
            "source_attribution": wire_source(art.get("content", "")) or "VOA Learning English",
        })
        print("  -> OK")
    out_path = os.path.join(os.path.dirname(__file__), "..", "app", "data", "factory_seeds", "pool_voa_lis.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"Saved {len(out)} clean Listening items → {out_path}")


if __name__ == "__main__":
    main()
