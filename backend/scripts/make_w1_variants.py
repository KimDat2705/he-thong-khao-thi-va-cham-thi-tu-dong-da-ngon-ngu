"""CLI (SPEC-FACTORY-006): sinh biến thể câu viết-lại W1 (giữ nghĩa) từ bank_raw.json của đối tác
→ gói bàn giao JSON (w1_item {original, prompt, answer}) + bảng GV soát/ký. Dùng Gemini thật nếu
có GEMINI_API_KEY, mock nếu không.

    python scripts/make_w1_variants.py --bank <bank_raw.json> [--limit N] [--per-seed K] [--out DIR]

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
    if hasattr(sys.stdout, "reconfigure"):   # tránh UnicodeEncodeError khi stdout không UTF-8 (cp1252)
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--bank", required=True, help="đường dẫn bank_raw.json của đối tác")
    ap.add_argument("--limit", type=int, default=5, help="số câu W1 seed lấy (từ đầu)")
    ap.add_argument("--per-seed", type=int, default=1, help="số biến thể mỗi seed")
    ap.add_argument("--out", default=".", help="thư mục xuất")
    args = ap.parse_args()

    with open(args.bank, encoding="utf-8") as f:
        bank = json.load(f)
    seeds = boss_factory.load_w1_seeds(bank)
    print(f"Trích {len(seeds)} câu viết-lại W1 từ {len(bank)} đề; dùng {min(args.limit, len(seeds))} seed đầu.")
    seeds = seeds[: args.limit]

    gen = B1QuestionGenerator()
    print("Chế độ sinh:", "REAL Gemini (" + str(gen.model_name) + ")" if gen.client else "MOCK")

    items = boss_factory.build_w1_variants(seeds, per_seed=args.per_seed, generator=gen)
    bundle = boss_factory.export_w1_bundle(items)

    os.makedirs(args.out, exist_ok=True)
    bundle_path = os.path.join(args.out, "w1_variants_bundle.json")
    sheet_path = os.path.join(args.out, "w1_review_sheet.md")
    with open(bundle_path, "w", encoding="utf-8") as f:
        json.dump(bundle, f, ensure_ascii=False, indent=2)
    with open(sheet_path, "w", encoding="utf-8") as f:
        f.write(boss_factory.w1_review_sheet(items))

    print(f"Sinh {len(items)} câu, {bundle['count_qc_ok']}/{len(items)} đạt QC.")
    print(f"Xuất: {bundle_path} · {sheet_path}")
    for it in items[:5]:
        w = it["w1_item"]
        print(f"\n[{it['nguon_seed']} · độ khó {it['do_kho']}]")
        print(f"   Gốc:     {w['original']}")
        print(f"   Phần đầu: {w['prompt']}")
        print(f"   Câu mẫu:  {w['answer']}")
        print(f"   QC: {'OK' if it['qc_ok'] else it['qc_issues']}")


if __name__ == "__main__":
    main()
