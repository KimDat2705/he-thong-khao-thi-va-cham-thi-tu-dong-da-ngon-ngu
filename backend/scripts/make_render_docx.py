"""CLI (SPEC-FACTORY-010): render 1 bundle JSON (từ make_*_variants.py) → .docx THAM CHIẾU
(đề + đáp án + ô GV ký). De-risk D2 Option (a): chứng minh item JSON dùng được + spec mẫu
để đối tác copy nhánh "render item từ JSON" vào pipeline của họ.

    python scripts/make_render_docx.py --bundle <bundle.json> [--out <file.docx>]
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services import boss_render  # noqa: E402


def main():
    if hasattr(sys.stdout, "reconfigure"):   # tránh UnicodeEncodeError cp1252 khi in tiếng Việt
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--bundle", required=True, help="đường dẫn bundle JSON (từ make_*_variants.py)")
    ap.add_argument("--out", help="đường dẫn .docx xuất (mặc định = <bundle>.docx)")
    args = ap.parse_args()
    out = args.out or (os.path.splitext(args.bundle)[0] + ".docx")
    path = boss_render.render_bundle_file(args.bundle, out)
    print(f"Đã render đề tham chiếu (GV soát/ký): {path}")


if __name__ == "__main__":
    main()
