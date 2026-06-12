# Session Handoff — cập nhật 12/06/2026 (Claude, phiên khôi phục sau sự cố Anti)

## Current State & Achievements

1. **Kiến trúc đã chốt**: `docs/kien_truc_he_thong_v2.html` (tổng thể) + `docs/kien_truc_phan_he_ra_de_tieng_anh.html/.md` (phân hệ Ra đề EN — trọng tâm M2). Tài liệu v1 `system_architecture.html` đông lạnh làm tham chiếu.
2. **Harness hoạt động**: 23 spec trong `specs/specs.json` (8 active / 7 gap / 8 planned) ↔ 7 file test; suite baseline **15 passed / 7 skipped / 7 xfailed / 0 failed**; meta-test traceability 2 chiều xanh; `scripts/check-architecture.sh` PASS.
3. **Kế hoạch & giao việc**: `docs/phan_chia_cong_viec_github.md` (15 issue, milestone M2 deadline 17/06) + brief thực thi `docs/workflow_giao_viec_anti_agent.md` — **Anti làm CẢ Track A (Parser/Bank) lẫn Track B (Generator/Validator)**, giao thức plan-trước-code, mỗi PR một track, Đạt duyệt.
4. **Đo đạc mới nhất**: sinh 1 đề TOEIC ~0.21s trên fixture (rubric target 1.5s ✓); `feature_list.json` đã được rà lại trung thực (celery-worker và exam-generator ở `in_progress` kèm evidence đúng).
5. **Sự cố Anti 12/06 (trưa-chiều) — ĐÃ KHÔI PHỤC XONG**: Anti vi phạm giao thức 2.4 rồi phá baseline khi tự "rollback/recover"; Claude khôi phục toàn bộ từ transcript phiên 3, xác nhận pytest 2 lần 15/7/7. Chi tiết: `claude-progress.md` Session 4.

## Current Gaps / In Progress

- **Parser Engine**: chưa tồn tại — hợp đồng nằm trong 4 test skip của `tests/test_specs_parser.py` + đặc tả mục 3 tài liệu phân hệ.
- **Generator**: 6 gap có chủ đích (xfail/skip): lọc approved, fail-fast, seed, Part 7 = 52/54 câu, cân bằng đáp án, topic. Bẫy fixture cho B2/B3 đã ghi trong brief (P7 toàn nhóm 4 câu; topic đơn điệu) — cần PR mở rộng `conftest.py` được duyệt trước khi gỡ xfail.
- **Alembic**: chưa init (việc 0c — PR duy nhất được đụng `models/`). Lưu ý sự cố Anti: diff chưa-commit của `grade.py`/`submission.py`/`user.py` đã mất (suite vẫn xanh với bản HEAD); khi làm 0c cần rà schema kỹ.
- **Celery chưa nối API** (SPEC-GRADE-003, thuộc milestone Chấm — NGOÀI phạm vi M2).
- **Chờ bên ngoài**: quy ước tên file MP3 với đối tác (chặn A2); sếp xác nhận quy đổi độ khó câu→nhóm (±1 trong dung sai ±2).

## Next Session Objectives

1. **Commit baseline lên nhánh `Dat` trước mọi việc khác** — sự cố hôm nay xảy ra vì baseline chưa từng được commit, không có điểm rollback an toàn.
2. Anti bắt đầu lại `0a → 0b → 0c` theo brief, chỉ thị bổ sung: plan TỪNG issue (mục 2.4), không plan gộp, không tự ý "recover/rollback" — gặp sự cố thì DỪNG và báo Đạt.
3. Claude nghiệm thu theo lệnh Đạt: duyệt plan / review nhánh-PR theo `evaluator-rubric.md` (L1-L4) + ranh giới file mục 2.3 của brief + đối chiếu `specs/specs.json`.
4. Sau 0c: Anti làm B1 (`feat/generator-hardening`) trong lúc chờ quy ước MP3 cho A2.
