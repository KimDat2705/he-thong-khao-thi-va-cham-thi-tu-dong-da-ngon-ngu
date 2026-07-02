"""CLI (SPEC-FACTORY-005): sinh biến thể nhóm đọc-hiểu R3 (đoạn văn + câu hỏi 4 lựa chọn) từ
bank_raw.json của đối tác → gói bàn giao JSON (s3_item + s3_raw + s3_answers) + bảng GV soát/ký.
Dùng Gemini thật nếu có GEMINI_API_KEY, mock nếu không.

    python scripts/make_r3_variants.py --bank <bank_raw.json> [--limit N] [--per-seed K] [--out DIR]

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
    if hasattr(sys.stdout, "reconfigure"):   # tránh UnicodeEncodeError khi stdout không UTF-8 (cp1252 Windows)
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--bank", required=True, help="đường dẫn bank_raw.json của đối tác")
    ap.add_argument("--limit", type=int, default=3, help="số nhóm R3 seed lấy (từ đầu)")
    ap.add_argument("--per-seed", type=int, default=1, help="số biến thể mỗi seed")
    ap.add_argument("--out", default=".", help="thư mục xuất")
    args = ap.parse_args()

    with open(args.bank, encoding="utf-8") as f:
        bank = json.load(f)
    seeds = boss_factory.load_r3_seeds(bank)
    print(f"Trích {len(seeds)} nhóm đọc-hiểu R3 từ {len(bank)} đề; dùng {min(args.limit, len(seeds))} seed đầu.")
    seeds = seeds[: args.limit]

    gen = B1QuestionGenerator()
    print("Chế độ sinh:", "REAL Gemini (" + str(gen.model_name) + ")" if gen.client else "MOCK")

    items = boss_factory.build_r3_variants(seeds, per_seed=args.per_seed, generator=gen)
    bundle = boss_factory.export_r3_bundle(items)

    os.makedirs(args.out, exist_ok=True)
    bundle_path = os.path.join(args.out, "r3_variants_bundle.json")
    sheet_path = os.path.join(args.out, "r3_review_sheet.md")
    with open(bundle_path, "w", encoding="utf-8") as f:
        json.dump(bundle, f, ensure_ascii=False, indent=2)
    with open(sheet_path, "w", encoding="utf-8") as f:
        f.write(boss_factory.r3_review_sheet(items))

    print(f"Sinh {len(items)} nhóm, {bundle['count_qc_ok']}/{len(items)} đạt QC.")
    print(f"Xuất: {bundle_path} · {sheet_path}")
    for it in items[:2]:
        s3 = it["s3_item"]
        print(f"\n[{it['nguon_seed']} · độ khó {it['do_kho']}]  {s3['passage'][:150]}...")
        for k, q in enumerate(s3["questions"]):
            print(f"   {16 + k}. {q['stem']}  (đáp án {q['answer']})")
        print(f"   QC: {'OK' if it['qc_ok'] else it['qc_issues']}")


if __name__ == "__main__":
    main()
