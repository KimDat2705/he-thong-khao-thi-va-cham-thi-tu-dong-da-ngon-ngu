"""Orchestrator + roundtrip cho nhà máy sinh câu (SPEC-FACTORY-012).

Chạy TOÀN BỘ 8 dạng từ các file ngân hàng của đối tác (bank_raw.json / pool_speak.json /
pool_lis.json) trong 1 lượt → {skill: bundle}; và KIỂM đầu ra có merge-được vào bank + đủ pool
cho N biến thể không (mô phỏng NHẸ khâu build_db/tron của sếp). Làm đủ để TEST nhiệm vụ chính
"mở rộng ngân hàng" end-to-end — KHÔNG dựng lại pipeline của sếp.

⚠️ roundtrip_check là sanity phía MÌNH (shape merge-ready + qc + đếm độ khó). Cờ merge chính xác
của sếp (sX_complete...) chờ 1 record `bank_raw` mẫu (D2 open — docs/ke_hoach_mo_rong_bank_b1.md §8).
"""
from app.services import boss_factory as bf

# (skill, loader, builder, exporter) — Đọc/Viết đọc CHUNG bank_raw (LIST 30 đề).
_RW = [
    ("reading_s1", bf.load_r1_seeds, bf.build_r1_variants, bf.export_bundle),
    ("reading_s2_notice", bf.load_r2_seeds, bf.build_r2_variants, bf.export_r2_bundle),
    ("reading_s3_comprehension", bf.load_r3_seeds, bf.build_r3_variants, bf.export_r3_bundle),
    ("reading_s4_cloze", bf.load_r4_seeds, bf.build_r4_variants, bf.export_r4_bundle),
    ("writing_w1_rewrite", bf.load_w1_seeds, bf.build_w1_variants, bf.export_w1_bundle),
    ("writing_w2_letter", bf.load_w2_seeds, bf.build_w2_variants, bf.export_w2_bundle),
]

# (item-key, field-TRONG-item, field-SIBLING-top-level) BẮT BUỘC để 1 item merge-được vào bank của sếp.
# s3 giữ s3_raw/s3_answers ở top-level (sibling) → phải kiểm cả; s4 gộp key_cloze TRONG s4_item.
_MERGE_REQUIRED = {
    "reading_s1": ("s1_item", ("stem", "options", "answer"), ()),
    "reading_s2_notice": ("s2_item", ("stem", "options", "answer"), ()),
    "reading_s3_comprehension": ("s3_item", ("passage", "questions"), ("s3_raw", "s3_answers")),
    "reading_s4_cloze": ("s4_item", ("s4_raw", "s4_answers", "key_cloze"), ()),
    "writing_w1_rewrite": ("w1_item", ("original", "prompt", "answer"), ()),
    "writing_w2_letter": ("w2_item", ("role", "situation", "points", "instruction"), ()),
    "speaking": ("speak_card", ("code", "part2_topic", "domain_guess"), ()),
    "listening": ("lis_item", ("code", "answers", "l1_stems", "l2_gaps"), ()),
}
_EMPTY = (None, "", [], {})


def run_bank_expansion(bank_raw=None, pool_speak=None, pool_lis=None, per_seed: int = 1,
                       generator=None, limit=None, verify: bool = False) -> dict:
    """Chạy TẤT CẢ dạng có seed từ các file ngân hàng → {skill: bundle}. generator=None → mock tất định.
    limit = số seed lấy mỗi dạng (None = tất cả · 0 = lô rỗng). Dạng không có seed thì bỏ qua.
    verify=True → chạy CỔNG KIỂM ĐÁP ÁN AI (SPEC-FACTORY-014) cho dạng đọc/cloze có đáp án đóng
    (R1/R2/R3/R4) → gắn answer_verify + cờ SUSPECT vào item cho GV soát; W/Nói/Nghe bỏ qua."""
    out = {}
    if bank_raw:
        for skill, load, build, export in _RW:
            seeds = load(bank_raw)
            if limit is not None:
                seeds = seeds[:limit]
            if seeds:
                bundle = export(build(seeds, per_seed=per_seed, generator=generator))
                if verify and skill in bf.VERIFY_SUPPORTED_SKILLS:
                    bf.verify_bundle_answers(bundle["items"], skill, generator=generator)
                out[skill] = bundle
    if pool_speak:
        seeds = bf.load_speak_seeds(pool_speak)
        seeds = seeds[:limit] if limit is not None else seeds
        if seeds:
            out["speaking"] = bf.export_speak_bundle(
                bf.build_speak_variants(seeds, per_seed=per_seed, generator=generator))
    if pool_lis:
        seeds = bf.load_lis_seeds(pool_lis)
        seeds = seeds[:limit] if limit is not None else seeds
        if seeds:
            out["listening"] = bf.export_lis_bundle(
                bf.build_lis_variants(seeds, per_seed=per_seed, generator=generator))
    return out


def _missing_merge_fields(skill: str, item) -> list:
    """Field merge còn THIẾU/RỖNG (kể cả sibling top-level) — để báo lỗi RÕ. [] = đủ, merge-được."""
    spec = _MERGE_REQUIRED.get(skill)
    if not spec or not isinstance(item, dict):
        return [f"skill lạ hoặc item không hợp lệ: {skill}"]
    key, fields, siblings = spec
    sub = item.get(key)
    if not isinstance(sub, dict):
        return [key]
    miss = [f"{key}.{f}" for f in fields if sub.get(f) in _EMPTY]
    miss += [s for s in siblings if item.get(s) in _EMPTY]
    return miss


def _item_merge_ready(skill: str, item) -> bool:
    """Item có SHAPE merge-được (đủ field bắt buộc TRONG item + sibling top-level, không rỗng) không?"""
    return not _missing_merge_fields(skill, item)


def roundtrip_check(bundle: dict, n_target: int = 0) -> dict:
    """Mô phỏng NHẸ khâu merge/tron của sếp: mỗi item có shape merge-được + qc_ok; đếm theo độ khó;
    đủ pool cho N biến thể chưa (n_target>0: cần >=N merge-ready; n_target=0: chỉ cần pool KHÔNG rỗng).
    KHÔNG chạy code sếp — sanity phía mình. Trả {skill, count, count_qc_ok, count_merge_ready,
    by_difficulty, enough_for_n, issues}."""
    skill = str(bundle.get("skill") or "?")
    items = [it for it in (bundle.get("items") or []) if isinstance(it, dict)]
    by_diff, n_qc, n_merge, issues = {}, 0, 0, []
    for i, it in enumerate(items, 1):
        if not it.get("qc_ok"):
            continue
        n_qc += 1
        miss = _missing_merge_fields(skill, it)
        if miss:
            issues.append(f"item {i}: qc_ok nhưng thiếu field merge: {miss}")
            continue
        n_merge += 1
        d = it.get("do_kho") or "?"
        by_diff[d] = by_diff.get(d, 0) + 1
    enough = (n_merge >= n_target) if n_target > 0 else (n_merge > 0)
    if n_target > 0 and not enough:
        issues.append(f"chỉ {n_merge} item merge-ready < {n_target} cần cho N biến thể")
    # Trạng thái cổng kiểm đáp án AI (nếu đã bật verify) — KHÔNG chặn merge (structural), chỉ báo GV soát.
    n_ver = sum(1 for it in items if (it.get("answer_verify") or {}).get("checked"))
    n_susp = sum(1 for it in items if it.get("answer_verify_flag") == "SUSPECT")
    return {"skill": skill, "count": len(items), "count_qc_ok": n_qc, "count_merge_ready": n_merge,
            "by_difficulty": by_diff, "enough_for_n": enough,
            "count_answer_checked": n_ver, "count_answer_suspect": n_susp, "issues": issues}


def roundtrip_report(bundles: dict, n_target: int = 0) -> dict:
    """roundtrip_check cho MỌI skill trong {skill: bundle} → {skill: report} + tổng merge-ready."""
    reports = {skill: roundtrip_check(b, n_target) for skill, b in bundles.items()}
    total_ready = sum(r["count_merge_ready"] for r in reports.values())
    total_susp = sum(r.get("count_answer_suspect", 0) for r in reports.values())
    all_ok = all(r["enough_for_n"] and not r["issues"] for r in reports.values())
    return {"skills": reports, "total_merge_ready": total_ready,
            "total_answer_suspect": total_susp, "all_ok": all_ok}
