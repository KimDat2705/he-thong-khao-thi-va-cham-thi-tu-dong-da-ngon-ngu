"""CLI (SPEC-FACTORY-008): sinh biến thể bài Nghe B1 (PET: 5 chọn-tranh + 10 điền-từ) từ
pool_lis.json của đối tác → gói bàn giao JSON (kịch bản + đáp án, shape pool_lis) + bảng GV
soát/ký. Mặc định CHỈ sinh kịch bản+JSON; cờ --audio bật TTS đa-giọng + ghép TRỌN bài ~17'
theo lịch pause Cambridge PET (đọc-2-lần, cache per-chunk) → MP3 (lameenc, fallback WAV).

    python scripts/make_lis_variants.py --pool <pool_lis.json> [--limit N] [--per-seed K] [--out DIR] [--audio]

Dữ liệu pool của đối tác KHÔNG nằm trong repo (đọc theo đường dẫn truyền vào). --audio cần GEMINI_API_KEY.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services import boss_factory  # noqa: E402
from app.services.b1_question_gen import B1QuestionGenerator  # noqa: E402


def main():
    if hasattr(sys.stdout, "reconfigure"):   # tránh UnicodeEncodeError khi stdout không UTF-8 (cp1252)
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--pool", required=True, help="đường dẫn pool_lis.json của đối tác")
    ap.add_argument("--limit", type=int, default=3, help="số bài Nghe seed lấy (từ đầu)")
    ap.add_argument("--per-seed", type=int, default=1, help="số biến thể mỗi seed")
    ap.add_argument("--out", default=".", help="thư mục xuất")
    ap.add_argument("--audio", action="store_true", help="render audio TTS đa-giọng (PoC 1 phần) — cần GEMINI_API_KEY")
    args = ap.parse_args()

    with open(args.pool, encoding="utf-8") as f:
        pool = json.load(f)
    seeds = boss_factory.load_lis_seeds(pool)
    n_total = len(pool) if hasattr(pool, "__len__") else len(seeds)
    print(f"Trích {len(seeds)} bài Nghe từ {n_total} bản ghi; dùng {min(args.limit, len(seeds))} seed đầu.")
    seeds = seeds[: args.limit]

    gen = B1QuestionGenerator()
    print("Chế độ sinh:", "REAL Gemini (" + str(gen.model_name) + ")" if gen.client else "MOCK")

    items = boss_factory.build_lis_variants(seeds, per_seed=args.per_seed, generator=gen)
    bundle = boss_factory.export_lis_bundle(items)

    os.makedirs(args.out, exist_ok=True)
    bundle_path = os.path.join(args.out, "lis_variants_bundle.json")
    sheet_path = os.path.join(args.out, "lis_review_sheet.md")
    with open(bundle_path, "w", encoding="utf-8") as f:
        json.dump(bundle, f, ensure_ascii=False, indent=2)
    with open(sheet_path, "w", encoding="utf-8") as f:
        f.write(boss_factory.lis_review_sheet(items))

    print(f"Sinh {len(items)} bài, {bundle['count_qc_ok']}/{len(items)} đạt QC.")
    print(f"Xuất: {bundle_path} · {sheet_path}")

    if args.audio and gen.client:
        audio_dir = os.path.join(args.out, "audio")
        for it in items:
            if not it["qc_ok"]:
                print(f"  Bỏ render audio (QC chưa đạt): {it['lis_item']['code']}")
                continue
            try:
                info = boss_factory.build_listening_audio(gen, it, audio_dir)   # ghép TRỌN bài ~17' + MP3
                li = it["lis_item"]
                li["audio_path"] = info["audio_path"]
                li["audio_name"] = os.path.basename(info["audio_path"])
                li["audio_duration_s"] = info["duration_s"]
                li["audio_status"] = f"{info['format']}_generated"    # mp3_generated | wav_generated (fallback)
                mm, ss = divmod(int(info["duration_s"]), 60)
                print(f"  🔊 {li['code']}: {info['audio_path']} ({mm}'{ss:02d}\", {info['format']}, {info['n_segments']} đoạn)")
            except Exception as e:
                print(f"  ⚠ Audio lỗi {it['lis_item']['code']}: {e}")
        with open(bundle_path, "w", encoding="utf-8") as f:
            json.dump(boss_factory.export_lis_bundle(items), f, ensure_ascii=False, indent=2)

    for it in items[:2]:
        li = it["lis_item"]
        print(f"\n[{it['nguon_seed']} → {li['code']} · độ khó {it['do_kho']} · {li['audio_status']}]")
        print(f"   L1 (1-5): {[li['answers'].get(str(k)) for k in range(1, 6)]}")
        print(f"   L2 (6-15): {[li['answers'].get(str(n)) for n in li['l2_gaps']]}")
        print(f"   QC: {'OK' if it['qc_ok'] else it['qc_issues']}")


if __name__ == "__main__":
    main()
