"""CLI (SPEC-FACTORY-004): sinh biến thể thông báo/biển báo R2 (3 phương án A/B/C) từ
bank_raw.json của đối tác → gói bàn giao JSON (s2_item clean + s2_raw_fragment) + bảng GV
soát/ký. Dùng Gemini thật nếu có GEMINI_API_KEY, mock nếu không.

    python scripts/make_r2_variants.py --bank <bank_raw.json> [--limit N] [--per-seed K] [--out DIR]

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
    ap.add_argument("--limit", type=int, default=5, help="số thông báo R2 seed lấy (từ đầu)")
    ap.add_argument("--per-seed", type=int, default=1, help="số biến thể mỗi seed")
    ap.add_argument("--out", default=".", help="thư mục xuất")
    ap.add_argument("--verify", action="store_true",
                    help="cổng kiểm đáp án AI đối kháng (SPEC-FACTORY-014) — gắn cờ item NGHI cho GV; cần GEMINI_API_KEY")
    args = ap.parse_args()

    with open(args.bank, encoding="utf-8") as f:
        bank = json.load(f)
    seeds = boss_factory.load_r2_seeds(bank)
    print(f"Trích {len(seeds)} thông báo R2 từ {len(bank)} đề; dùng {min(args.limit, len(seeds))} seed đầu.")
    seeds = seeds[: args.limit]

    gen = B1QuestionGenerator()
    print("Chế độ sinh:", "REAL Gemini (" + str(gen.model_name) + ")" if gen.client else "MOCK")

    items = boss_factory.build_r2_variants(seeds, per_seed=args.per_seed, generator=gen)
    if args.verify and gen.client:
        boss_factory.verify_bundle_answers(items, skill="reading_s2_notice", generator=gen)
        os.makedirs(args.out, exist_ok=True)
        report_path = os.path.join(args.out, "r2_verify_report.md")
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(boss_factory.verify_report(items))
        n_susp = sum(1 for it in items if it.get("answer_verify_flag") == "SUSPECT")
        print(f"Kiểm đáp án AI: {n_susp}/{len(items)} NGHI (xem {report_path}) — GV soát item NGHI trước.")
    bundle = boss_factory.export_r2_bundle(items)

    os.makedirs(args.out, exist_ok=True)
    bundle_path = os.path.join(args.out, "r2_variants_bundle.json")
    sheet_path = os.path.join(args.out, "r2_review_sheet.md")
    with open(bundle_path, "w", encoding="utf-8") as f:
        json.dump(bundle, f, ensure_ascii=False, indent=2)
    with open(sheet_path, "w", encoding="utf-8") as f:
        f.write(boss_factory.r2_review_sheet(items))

    print(f"Sinh {len(items)} thông báo, {bundle['count_qc_ok']}/{len(items)} đạt QC.")
    print(f"Xuất: {bundle_path} · {sheet_path}")
    for it in items[:3]:
        s = it["s2_item"]
        print(f"\n[{it['nguon_seed']} · độ khó {it['do_kho']}]  {s['stem']}")
        for k in ("A", "B", "C"):
            print(f"   {k}. {s['options'].get(k)}")
        print(f"   Đáp án: {s['answer']}  |  QC: {'OK' if it['qc_ok'] else it['qc_issues']}")


if __name__ == "__main__":
    main()
