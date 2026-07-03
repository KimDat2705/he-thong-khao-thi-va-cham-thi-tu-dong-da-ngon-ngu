"""ĐO precision/recall CỔNG KIỂM ĐÁP ÁN (SPEC-FACTORY-014/015) — harness tái dùng.

Mỗi item chạy 2 lần: (A) đáp án ĐÚNG (kỳ vọng PASS) · (B) đáp án SAI cài (kỳ vọng SUSPECT).
  recall = % item-cài-sai bị bắt (flag)          → cao = tốt
  FP     = % item-đúng bị flag oan               → thấp = tốt (= false-positive HOẶC lỗi đáp án thật)
Item đúng bị flag được LIỆT KÊ để GV/sếp soát (có thể là lỗi đáp án THẬT trong bank).

    python scripts/eval_answer_gate.py               # bộ B1 curated (reproducible, không cần dữ liệu đối tác)
    python scripts/eval_answer_gate.py --items x.json # item ngoài (đề THẬT); shape mỗi item:
        {"skill":"R1|R2|R3", "ma_de":.., "num":.., "stem"/"passage":.., "options":{..}, "answer":".."}

Cần GEMINI_API_KEY (không có key → MOCK, chỉ để smoke). ĐO THẬT (S55c): bộ curated recall 100%/FP 10%;
đề sếp THẬT (14 item) recall 100%/flag-đáp-án-thật 14% (cả 2 là R3: 1 do cắt passage, 1 item khó → GV).
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services import boss_factory  # noqa: E402
from app.services.b1_question_gen import B1QuestionGenerator  # noqa: E402

_SKILL = {"R1": "reading_s1", "R2": "reading_s2_notice", "R3": "reading_s3_comprehension"}

# Bộ B1 CURATED (đáp án kiểm kỹ; gồm bẫy ngữ pháp + 2 R3) — reproducible, KHÔNG chứa dữ liệu đối tác.
CURATED = [
    {"skill": "R1", "stem": "If I ...... rich, I would travel the world.",
     "options": {"A": "am", "B": "was", "C": "were", "D": "will be"}, "answer": "C"},
    {"skill": "R1", "stem": "He has worked here ...... 2015.",
     "options": {"A": "for", "B": "since", "C": "from", "D": "during"}, "answer": "B"},
    {"skill": "R1", "stem": "I'm looking forward ...... you again.",
     "options": {"A": "to see", "B": "seeing", "C": "to seeing", "D": "see"}, "answer": "C"},
    {"skill": "R1", "stem": "Neither of the students ...... ready for the exam.",
     "options": {"A": "are", "B": "is", "C": "were", "D": "have been"}, "answer": "B"},
    {"skill": "R1", "stem": "By the time we arrived, the film ...... .",
     "options": {"A": "started", "B": "has started", "C": "had already started", "D": "was starting"}, "answer": "C"},
    {"skill": "R1", "stem": "The report ...... to the manager yesterday.",
     "options": {"A": "sent", "B": "was sent", "C": "is sent", "D": "has sent"}, "answer": "B"},
    {"skill": "R2", "stem": "SWIMMING POOL. Closed for cleaning every Monday morning until 12:00. Members only after 6 p.m.",
     "options": {"A": "The pool never opens on Mondays.", "B": "Non-members cannot swim after 6 p.m.",
                 "C": "Cleaning happens every afternoon."}, "answer": "B"},
    {"skill": "R3", "passage": "Tom loves football. He plays every Saturday with his friends in the local park, never on Sundays.",
     "stem": "When does Tom play football?",
     "options": {"A": "every day", "B": "every Sunday", "C": "every Saturday", "D": "never"}, "answer": "C"},
]


def _make_item(rec, answer):
    seed = f"{rec.get('ma_de', 'CUR')}#{rec.get('num', '?')}"
    sk = rec["skill"]
    if sk == "R1":
        return {"s1_item": {"stem": rec["stem"], "options": rec["options"], "answer": answer}, "nguon_seed": seed}
    if sk == "R2":
        return {"s2_item": {"stem": rec["stem"], "options": rec["options"], "answer": answer}, "nguon_seed": seed}
    if sk == "R3":
        return {"s3_item": {"passage": rec["passage"],
                            "questions": [{"stem": rec["stem"], "options": rec["options"], "answer": answer}]},
                "nguon_seed": seed}
    raise ValueError(f"skill lạ: {sk}")


def _wrong(rec):
    return next((k for k in sorted(rec["options"]) if k != rec["answer"]), rec["answer"])


def _verify(item, skill, gen, tries=3):
    for k in range(tries):
        boss_factory.verify_bundle_answers([item], skill, generator=gen)
        av = item.get("answer_verify") or {}
        if av.get("checked") or not av.get("checker_call_error"):
            break
        time.sleep(3 * (k + 1))
    return item.get("answer_verify_flag") == "SUSPECT", item.get("answer_verify") or {}


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--items", help="JSON item ngoài (đề THẬT); mặc định = bộ curated")
    args = ap.parse_args()
    recs = json.load(open(args.items, encoding="utf-8")) if args.items else CURATED

    gen = B1QuestionGenerator()
    print(f"gen: {'REAL ' + str(gen.model_name) if gen.client else 'MOCK'} · {len(recs)} item")
    tp = fn = fp = tn = 0
    flagged_correct = []
    for r in recs:
        sk = _SKILL.get(r.get("skill"))
        if not sk or "answer" not in r or "options" not in r:
            continue
        fl_w, _ = _verify(_make_item(r, _wrong(r)), sk, gen)
        fl_c, av_c = _verify(_make_item(r, r["answer"]), sk, gen)
        seed = f"{r.get('ma_de', 'CUR')}#{r.get('num', '?')}"
        print(f"[{r['skill']}] {seed:16} đúng={r['answer']} | SAI→flag={fl_w} | ĐÚNG→flag={fl_c}")
        tp += int(fl_w)
        fn += int(not fl_w)
        fp += int(fl_c)
        tn += int(not fl_c)
        if fl_c:
            flagged_correct.append((seed, r["skill"], r["answer"], av_c.get("note")))
    n = tp + fn
    print("\n===== KẾT QUẢ =====")
    if n:
        print(f"recall (bắt đáp án SAI) = {tp}/{n} = {tp / n * 100:.0f}%")
        print(f"flag-khi-đáp-án-ĐÚNG    = {fp}/{fp + tn} = {fp / (fp + tn) * 100:.0f}%  "
              f"(false-positive HOẶC lỗi đáp án thật trong bank)")
    for seed, sk, ans, note in flagged_correct:
        print(f"  ⚠ {seed} [{sk}] đáp-án={ans} · {note}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
