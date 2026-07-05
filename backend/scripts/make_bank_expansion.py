"""CLI (SPEC-FACTORY-012): chạy TOÀN BỘ nhà máy sinh câu từ các file ngân hàng của đối tác trong 1
lượt → xuất bundle JSON + .docx (đề + đáp án + ô GV ký) cho MỌI dạng + báo cáo roundtrip
(merge-ready / đủ pool). Làm đủ để TEST nhiệm vụ chính "mở rộng ngân hàng" end-to-end.

    python scripts/make_bank_expansion.py [--bank-raw bank_raw.json] [--pool-speak pool_speak.json]
        [--pool-lis pool_lis.json] [--per-seed K] [--limit N] [--n-target N] [--out DIR]

Cần ít nhất 1 file ngân hàng. Dữ liệu đối tác KHÔNG nằm trong repo (đọc theo đường dẫn truyền vào).
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services import boss_factory, boss_pipeline, boss_render  # noqa: E402
from app.services.b1_question_gen import B1QuestionGenerator  # noqa: E402


def _load(path):
    if not path:
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--bank-raw", help="bank_raw.json (Đọc + Viết: R1/R2/R3/R4/W1/W2)")
    ap.add_argument("--pool-speak", help="pool_speak.json (Nói)")
    ap.add_argument("--pool-lis", help="pool_lis.json (Nghe)")
    ap.add_argument("--per-seed", type=int, default=1, help="số biến thể mỗi seed")
    ap.add_argument("--limit", type=int, default=None, help="số seed lấy mỗi dạng (mặc định tất cả)")
    ap.add_argument("--n-target", type=int, default=0, help="số biến thể mục tiêu để kiểm đủ-pool")
    ap.add_argument("--out", default="bank_expansion", help="thư mục xuất")
    ap.add_argument("--verify", action="store_true",
                    help="chạy cổng kiểm đáp án AI (SPEC-FACTORY-014/015) cho R1/R2/R3/R4 — gắn cờ item NGHI cho GV")
    args = ap.parse_args()

    if not (args.bank_raw or args.pool_speak or args.pool_lis):
        ap.error("cần ít nhất 1 file ngân hàng: --bank-raw / --pool-speak / --pool-lis")

    gen = B1QuestionGenerator()
    print("Chế độ sinh:", ("REAL Gemini (" + str(gen.model_name) + ")") if gen.client else "MOCK")
    if args.verify and not gen.client:
        print("⚠ Bỏ qua kiểm đáp án (--verify): đang chạy MOCK — chưa có GEMINI_API_KEY.")
    bundles = boss_pipeline.run_bank_expansion(
        _load(args.bank_raw), _load(args.pool_speak), _load(args.pool_lis),
        per_seed=args.per_seed, generator=gen, limit=args.limit, verify=args.verify and bool(gen.client))

    os.makedirs(args.out, exist_ok=True)
    report = boss_pipeline.roundtrip_report(bundles, args.n_target)
    susp_line = f" · item NGHI đáp án (GV soát): {report.get('total_answer_suspect', 0)}" if args.verify else ""
    print(f"\nSinh {len(bundles)} dạng. Tổng item merge-ready: {report['total_merge_ready']} · all_ok={report['all_ok']}{susp_line}")
    for skill, bundle in bundles.items():
        json_path = os.path.join(args.out, f"{skill}_bundle.json")
        docx_path = os.path.join(args.out, f"{skill}.docx")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(bundle, f, ensure_ascii=False, indent=2)
        try:
            boss_render.render_bundle_docx(bundle, docx_path)
        except Exception as e:                     # docx lỗi 1 dạng không chặn cả lượt
            docx_path = f"(docx lỗi: {e})"
        rt = report["skills"][skill]
        susp = f" · NGHI đáp án {rt.get('count_answer_suspect', 0)}" if args.verify else ""
        print(f"  [{skill}] {bundle['count']} item · QC {bundle['count_qc_ok']} · merge-ready "
              f"{rt['count_merge_ready']} · {rt['by_difficulty']} · đủ-pool={rt['enough_for_n']}{susp}"
              + (f" · ⚠ {rt['issues']}" if rt["issues"] else ""))
        print(f"     → {json_path} · {docx_path}")
        if args.verify and skill in boss_factory.VERIFY_SUPPORTED_SKILLS:
            rep_path = os.path.join(args.out, f"{skill}_verify_report.md")
            with open(rep_path, "w", encoding="utf-8") as f:
                f.write(boss_factory.verify_report(bundle["items"]))
            print(f"     → {rep_path} (item NGHI để GV soát)")


if __name__ == "__main__":
    main()
