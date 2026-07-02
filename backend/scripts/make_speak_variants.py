"""CLI (SPEC-FACTORY-002): sinh biến thể thẻ Nói (part2_topic) từ pool_speak.json của đối tác
→ gói bàn giao JSON (shape pool_speak) + bảng GV soát/ký. Dùng Gemini thật nếu có
GEMINI_API_KEY, mock nếu không.

    python scripts/make_speak_variants.py --pool <pool_speak.json> [--limit N] [--per-seed K] [--out DIR]

Dữ liệu pool của đối tác KHÔNG nằm trong repo (đọc theo đường dẫn truyền vào).
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services import boss_factory  # noqa: E402
from app.services.b1_question_gen import B1QuestionGenerator  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pool", required=True, help="đường dẫn pool_speak.json của đối tác")
    ap.add_argument("--limit", type=int, default=5, help="số thẻ Nói seed lấy (từ đầu)")
    ap.add_argument("--per-seed", type=int, default=1, help="số biến thể mỗi seed")
    ap.add_argument("--out", default=".", help="thư mục xuất")
    args = ap.parse_args()

    with open(args.pool, encoding="utf-8") as f:
        pool = json.load(f)
    seeds = boss_factory.load_speak_seeds(pool)
    n_total = len(pool) if hasattr(pool, "__len__") else len(seeds)
    print(f"Trích {len(seeds)} thẻ Nói từ {n_total} bản ghi; dùng {min(args.limit, len(seeds))} seed đầu.")
    seeds = seeds[: args.limit]

    gen = B1QuestionGenerator()
    print("Chế độ sinh:", "REAL Gemini (" + str(gen.model_name) + ")" if gen.client else "MOCK")

    items = boss_factory.build_speak_variants(seeds, per_seed=args.per_seed, generator=gen)
    bundle = boss_factory.export_speak_bundle(items)

    os.makedirs(args.out, exist_ok=True)
    bundle_path = os.path.join(args.out, "speak_variants_bundle.json")
    sheet_path = os.path.join(args.out, "speak_review_sheet.md")
    with open(bundle_path, "w", encoding="utf-8") as f:
        json.dump(bundle, f, ensure_ascii=False, indent=2)
    with open(sheet_path, "w", encoding="utf-8") as f:
        f.write(boss_factory.speak_review_sheet(items))

    print(f"Sinh {len(items)} thẻ, {bundle['count_qc_ok']}/{len(items)} đạt QC.")
    print(f"Xuất: {bundle_path} · {sheet_path}")
    for it in items[:3]:
        c = it["speak_card"]
        print(f"\n[{it['nguon_seed']} → {c['code']} · domain {it['domain']} · độ khó {it['do_kho']}]")
        print(f"   part2_topic: {c['part2_topic']}")
        print(f"   QC: {'OK' if it['qc_ok'] else it['qc_issues']}")


if __name__ == "__main__":
    main()
