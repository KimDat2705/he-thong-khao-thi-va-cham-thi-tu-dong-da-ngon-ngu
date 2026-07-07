"""Harness ĐO giọng TTS A/B (SPEC-FACTORY-021 — bước ĐO, KHÔNG tích hợp).

Sinh CÙNG 1 đoạn hội thoại L1 mẫu bằng nhiều BIẾN THỂ kỹ thuật (giọng hiện tại vs style-prompt
vs đổi giọng vs inline-tag vs model pro) → xuất WAV/MP3 để Đạt + giáo viên NGHE TAI người chấm MÙ
theo 10 tiêu chí, rồi mới chọn biến thể thắng để tích hợp sau.

Vì sao harness RIÊNG (không sửa boss_factory._lis_tts): (1) đây là bước đo, chưa đổi production;
(2) style-preamble phải vào cache-key nếu tích hợp — làm sau; (3) tách để chạy lại/so sánh gọn
(song song eval_answer_gate.py). Chẩn đoán gốc (nghiên cứu S57): _lis_tts truyền contents=TEXT THÔ,
không có chỉ dẫn giọng điệu → Gemini đọc trung tính = 'đều đều'. Đòn bẩy rẻ nhất ($0) = prepend
style-preamble tiếng-tự-nhiên (Gemini 2.5 TTS hỗ trợ chính thức cho cả multi-speaker).

Chạy:  cd backend && python scripts/eval_lis_voices.py [--out DIR] [--sleep 4] [--pro]
  --pro : thử THÊM biến thể model 'gemini-2.5-pro-preview-tts' (có thể TÍNH PHÍ / cần billing — Đạt duyệt).
"""
import argparse
import os
import random
import sys
import time
import wave

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services import boss_factory  # noqa: E402
from app.services.b1_question_gen import B1QuestionGenerator  # noqa: E402

FLASH_TTS = "gemini-2.5-flash-preview-tts"
PRO_TTS = "gemini-2.5-pro-preview-tts"

# MỘT hội thoại L1 mẫu — DÙNG Y HỆT cho mọi biến thể (chênh lệch chỉ do kỹ thuật → chấm công bằng).
# Chủ đề B1 đời thường (kể lại cuối tuần), 2 người, ~110 từ, có contraction + discourse marker +
# câu hỏi (ngữ điệu lên) + chi tiết mang đáp án (lake / two hours / camping).
SAMPLE_TRANSCRIPT = (
    "Anna: Hi Ben! Did you have a good weekend?\n"
    "Ben: Yeah, it was great, thanks. I went camping with my brother.\n"
    "Anna: Camping? Oh, lovely! Where did you go?\n"
    "Ben: We drove up to the lake. It's about two hours from here.\n"
    "Anna: Wow. Wasn't it cold at night?\n"
    "Ben: A bit, but we had a proper fire, so we were fine. How about you?\n"
    "Anna: Oh, I just stayed home and finished my art project. Nothing exciting!\n"
    "Ben: That sounds relaxing, actually. Sometimes a quiet weekend is exactly what you need.\n"
)

# Biến thể v4: cùng transcript nhưng chèn inline tag nhịp/cảm xúc nhẹ (best-effort — Gemini có thể
# honor hoặc bỏ qua; nghiên cứu: [short pause]/[laughs] tồn tại nhưng steering không đảm bảo).
SAMPLE_TRANSCRIPT_TAGS = (
    "Anna: Hi Ben! [short pause] Did you have a good weekend?\n"
    "Ben: [warmly] Yeah, it was great, thanks. I went camping with my brother.\n"
    "Anna: Camping? [surprised] Oh, lovely! Where did you go?\n"
    "Ben: We drove up to the lake. [short pause] It's about two hours from here.\n"
    "Anna: Wow. Wasn't it cold at night?\n"
    "Ben: A bit, but we had a proper fire, so we were fine. [short pause] How about you?\n"
    "Anna: Oh, I just stayed home and finished my art project. [lightly] Nothing exciting!\n"
    "Ben: That sounds relaxing, actually. Sometimes a quiet weekend is exactly what you need.\n"
)

SPEAKERS_DEFAULT = [("Anna", "Kore"), ("Ben", "Puck")]         # đúng LIS_VOICES production
SPEAKERS_SWAP = [("Anna", "Sulafat"), ("Ben", "Charon")]       # cặp tương phản (cần audition tai người)

STYLE_V2 = (
    "Read the following as a natural, friendly everyday English conversation for a B1 listening exam. "
    "Speak at a clear, measured pace with natural rising intonation on questions and short natural "
    "pauses between turns. Make Anna sound warm and relaxed, and Ben sound casual and easygoing."
)
STYLE_V3 = (
    "Read the following as a natural, friendly everyday English conversation for a B1 listening exam, "
    "in a clear standard British English accent as heard in southern England. Keep a measured exam pace "
    "with natural, expressive intonation and short pauses between turns. Make Anna sound warm and "
    "cheerful, and Ben sound calm and easygoing."
)

# Định nghĩa các biến thể: (khoá, model, style-preamble|None, transcript, speakers, mô tả)
VARIANTS = [
    ("v1_current_baseline", FLASH_TTS, None, SAMPLE_TRANSCRIPT, SPEAKERS_DEFAULT,
     "HIỆN TẠI (mốc): text thô, giọng Kore/Puck — đây chính là cái 'đều đều'."),
    ("v2_styleprompt", FLASH_TTS, STYLE_V2, SAMPLE_TRANSCRIPT, SPEAKERS_DEFAULT,
     "Thêm chỉ dẫn giọng tự nhiên (giữ nguyên giọng Kore/Puck) — đo tác động của prompt một mình."),
    ("v3_style_british_voiceswap", FLASH_TTS, STYLE_V3, SAMPLE_TRANSCRIPT, SPEAKERS_SWAP,
     "Chỉ dẫn giọng + accent Anh + đổi cặp giọng tương phản (Sulafat/Charon)."),
    ("v4_style_inline_tags", FLASH_TTS, STYLE_V3, SAMPLE_TRANSCRIPT_TAGS, SPEAKERS_SWAP,
     "Như v3 + chèn tag nhịp/cảm xúc [short pause]/[warmly] (best-effort)."),
]


def synthesize(client, model, style_preamble, transcript, speakers, out_wav):
    """Gọi Gemini TTS đa-giọng → WAV 24kHz mono. Song song boss_factory._lis_tts nhưng THAM SỐ HOÁ
    model + style-preamble (production _lis_tts hard-code model + không có preamble)."""
    from google.genai import types  # noqa: PLC0415
    contents = f"{style_preamble}\n\n{transcript}" if style_preamble else transcript
    speech = types.SpeechConfig(multi_speaker_voice_config=types.MultiSpeakerVoiceConfig(
        speaker_voice_configs=[
            types.SpeakerVoiceConfig(speaker=lab, voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice)))
            for lab, voice in speakers
        ]))
    resp = client.models.generate_content(
        model=model, contents=contents,
        config=types.GenerateContentConfig(response_modalities=["AUDIO"], speech_config=speech))
    audio = None
    for c in (resp.candidates or []):
        for p in ((c.content.parts if c.content else None) or []):
            if p.inline_data and (p.inline_data.mime_type or "").startswith("audio/"):
                audio = p.inline_data.data
                break
    if audio is None:
        raise ValueError("Không có phần audio trong phản hồi Gemini TTS.")
    os.makedirs(os.path.dirname(out_wav) or ".", exist_ok=True)
    with wave.open(out_wav, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(24000)
        w.writeframes(audio)
    return out_wav


def _wav_seconds(path):
    with wave.open(path, "rb") as w:
        return w.getnframes() / float(w.getframerate())


def main():
    ap = argparse.ArgumentParser()
    default_out = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "tts_samples"))
    ap.add_argument("--out", default=default_out, help="thư mục xuất mẫu (mặc định: <repo>/tts_samples)")
    ap.add_argument("--sleep", type=float, default=4.0, help="giãn cách giữa các call TTS (chống 429)")
    ap.add_argument("--pro", action="store_true", help="thử thêm model pro (có thể tính phí — Đạt duyệt)")
    args = ap.parse_args()

    gen = B1QuestionGenerator()
    client = getattr(gen, "client", None)
    if client is None:
        print("CẦN GEMINI_API_KEY để sinh audio (bước nghe-tai không dùng mock). Dừng.")
        sys.exit(1)

    variants = list(VARIANTS)
    if args.pro:
        variants.append(("v5_pro_model", PRO_TTS, STYLE_V3, SAMPLE_TRANSCRIPT, SPEAKERS_SWAP,
                         "Model 'pro' chất lượng cao hơn (có thể TÍNH PHÍ) + cấu hình như v3."))

    os.makedirs(args.out, exist_ok=True)
    # Nghe MÙ: gán nhãn A/B/C/... ngẫu nhiên; bản đồ thật ghi ở CUỐI README (mở sau khi chấm).
    letters = [chr(ord("A") + i) for i in range(len(variants))]
    order = list(range(len(variants)))
    random.shuffle(order)
    key_lines, results = [], []

    for letter, vi in zip(letters, order):
        vkey, model, style, transcript, speakers, desc = variants[vi]
        wav = os.path.join(args.out, f"giong_{letter}.wav")
        print(f"[{letter}] sinh {vkey} (model={model}) ...", flush=True)
        try:
            synthesize(client, model, style, transcript, speakers, wav)
            mp3 = boss_factory.wav_to_mp3(wav)   # None nếu chưa cài lameenc → giữ WAV
            fpath = mp3 or wav
            dur = _wav_seconds(wav)
            words = len(transcript.replace("[short pause]", "").replace("[warmly]", "")
                        .replace("[surprised]", "").replace("[lightly]", "").split())
            wpm = round(words / (dur / 60.0)) if dur else 0
            print(f"    OK: {os.path.basename(fpath)} — {dur:.1f}s (~{wpm} wpm)", flush=True)
            results.append((letter, vkey, os.path.basename(fpath), f"{dur:.1f}s / ~{wpm} wpm", desc))
            key_lines.append(f"- Giọng **{letter}** = `{vkey}` — {desc}")
        except Exception as e:
            print(f"    LỖI {vkey}: {type(e).__name__}: {str(e)[:160]}", flush=True)
            key_lines.append(f"- Giọng **{letter}** = `{vkey}` — ❌ LỖI: {str(e)[:120]}")
        time.sleep(args.sleep)

    _write_readme(args.out, results, key_lines)
    print(f"\nXONG. Mở thư mục: {args.out}\n  → nghe các file giong_*.mp3/.wav + đọc HUONG_DAN_NGHE.md")


def _write_readme(out_dir, results, key_lines):
    lines = [
        "# Nghe thử giọng đọc bài Nghe (A/B) — chọn giọng cho phần Nghe",
        "",
        "Cùng MỘT đoạn hội thoại được đọc bằng nhiều kỹ thuật khác nhau. Hãy **nghe từng file**",
        "(`giong_A`, `giong_B`, ...) và chấm theo bảng bên dưới. **Chưa mở phần ĐÁP ÁN ở cuối**",
        "cho tới khi chấm xong (nghe mù cho khách quan). Nên có **1 giáo viên tiếng Anh** nghe cùng,",
        "và so với **audio đề thật** (`giong_MOC_VANG_de_that.*` nếu có) làm mốc.",
        "",
        "## Các file cần nghe",
        "| Giọng | File | Thời lượng |",
        "|---|---|---|",
    ]
    for letter, _vkey, fname, dur, _desc in results:
        lines.append(f"| {letter} | `{fname}` | {dur} |")
    lines += [
        "",
        "## Bảng chấm (mỗi tiêu chí: Có = 1, Không = 0)",
        "| # | Tiêu chí (nghe kỹ) | A | B | C | D |",
        "|---|---|---|---|---|---|",
        "| 1 | **Tốc độ** hợp B1 — kịp bắt từ khóa, không liến thoắng | | | | |",
        "| 2 | ⭐**BẮT BUỘC** — hai giọng KHÁC RÕ (nhắm mắt vẫn phân biệt được) | | | | |",
        "| 3 | Accent chuẩn, nhất quán, dễ nghe | | | | |",
        "| 4 | Ngữ điệu lên/xuống tự nhiên (hỏi lên, kể xuống) — không phẳng lì | | | | |",
        "| 5 | Biểu cảm đúng liều — như trò chuyện thật, không đọc chán cũng không diễn lố | | | | |",
        "| 6 | Có pause/ngắt nghỉ tự nhiên giữa các lượt lời | | | | |",
        "| 7 | Luyến láy / nối âm tự nhiên (I'm, don't...) — không đánh vần từng từ | | | | |",
        "| 8 | ⭐**BẮT BUỘC** — nghe RÕ mọi chi tiết đáp án (không nuốt/méo) | | | | |",
        "| 9 | Thu sạch — không tạp âm, âm lượng đều | | | | |",
        "| 10 | Ra tình huống đời thường thật (bạn bè kể chuyện) | | | | |",
        "| | **TỔNG /10** | | | | |",
        "",
        "**Ngưỡng chọn:** tổng ≥ 8/10 **VÀ** tiêu chí #2 + #8 đều phải Có (thiếu 1 trong 2 là loại dù tổng cao).",
        "Chọn giọng thắng → báo lại để tích hợp vào hệ thống. Giáo viên tiếng Anh ký duyệt cuối.",
        "",
        "---",
        "## 🔒 ĐÁP ÁN — chỉ mở SAU khi đã chấm xong",
        "",
        "<details><summary>Bấm để xem giọng nào là kỹ thuật gì</summary>",
        "",
    ] + key_lines + [
        "",
        "Giải thích: `v1` = giọng đang dùng (mốc). `v2` = thêm chỉ dẫn giọng tự nhiên (giữ nguyên giọng).",
        "`v3` = chỉ dẫn + accent Anh + đổi cặp giọng. `v4` = như v3 + chèn tag nhịp/cảm xúc. `v5` (nếu có)",
        "= model 'pro' chất lượng cao hơn (có thể tính phí).",
        "</details>",
        "",
    ]
    with open(os.path.join(out_dir, "HUONG_DAN_NGHE.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    main()
