"""CLI (SPEC-FACTORY-001): sinh biến thể câu R1 từ bank_raw.json của đối tác → gói bàn giao
JSON (shape s1) + bảng GV soát/ký. Dùng Gemini thật nếu có GEMINI_API_KEY, mock nếu không.

    python scripts/make_r1_variants.py --bank <bank_raw.json> [--limit N] [--per-seed K] [--out DIR]

Dữ liệu bank của đối tác KHÔNG nằm trong repo (đọc theo đường dẫn truyền vào).
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
    ap.add_argument("--bank", required=True, help="đường dẫn bank_raw.json của đối tác")
    ap.add_argument("--limit", type=int, default=5, help="số seed R1 lấy (từ đầu)")
    ap.add_argument("--per-seed", type=int, default=1, help="số biến thể mỗi seed")
    ap.add_argument("--out", default=".", help="thư mục xuất")
    args = ap.parse_args()

    with open(args.bank, encoding="utf-8") as f:
        bank = json.load(f)
    seeds = boss_factory.load_r1_seeds(bank)
    print(f"Trích {len(seeds)} seed R1 từ {len(bank)} đề; dùng {min(args.limit, len(seeds))} seed đầu.")
    seeds = seeds[: args.limit]

    gen = B1QuestionGenerator()
    print("Chế độ sinh:", "REAL Gemini (" + str(gen.model_name) + ")" if gen.client else "MOCK")

    items = boss_factory.build_r1_variants(seeds, per_seed=args.per_seed, generator=gen)
    bundle = boss_factory.export_bundle(items)

    os.makedirs(args.out, exist_ok=True)
    bundle_path = os.path.join(args.out, "r1_variants_bundle.json")
    sheet_path = os.path.join(args.out, "r1_review_sheet.md")
    with open(bundle_path, "w", encoding="utf-8") as f:
        json.dump(bundle, f, ensure_ascii=False, indent=2)
    with open(sheet_path, "w", encoding="utf-8") as f:
        f.write(boss_factory.review_sheet(items))

    print(f"Sinh {len(items)} biến thể, {bundle['count_qc_ok']}/{len(items)} đạt QC.")
    print(f"Xuất: {bundle_path} · {sheet_path}")
    for it in items[:3]:
        s = it["s1_item"]
        print(f"\n[{it['nguon_seed']} · độ khó {it['do_kho']}]  {s['stem']}")
        for k in ("A", "B", "C", "D"):
            print(f"   {k}. {s['options'].get(k)}")
        print(f"   Đáp án: {s['answer']}  |  QC: {'OK' if it['qc_ok'] else it['qc_issues']}")


if __name__ == "__main__":
    main()
