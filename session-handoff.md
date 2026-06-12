# Session Handoff — cập nhật 12/06/2026 cuối ngày (Claude, sau khi hoàn thành 0a + 0b)

## Current State & Achievements

1. **Kiến trúc đã chốt**: `docs/kien_truc_he_thong_v2.html` (tổng thể) + `docs/kien_truc_phan_he_ra_de_tieng_anh.html/.md` (phân hệ Ra đề EN — trọng tâm M2). Tài liệu v1 `system_architecture.html` đông lạnh làm tham chiếu.
2. **Harness hoạt động**: 23 spec trong `specs/specs.json` (8 active / 7 gap / 8 planned) ↔ 7 file test; suite baseline **15 passed / 7 skipped / 7 xfailed / 0 failed**; meta-test traceability 2 chiều xanh; `scripts/check-architecture.sh` PASS.
3. **Git/GitHub đã vào nề nếp**: baseline + toàn bộ tiến độ nằm trên nhánh `Dat` (đồng bộ `origin/Dat`); repo `KimDat2705/he-thong-khao-thi-va-cham-thi-tu-dong-da-ngon-ngu`; 6 labels + milestone M2 + 14 issues (0b→B6) đã tạo trên GitHub; branch protection `main` đã tạo (Not enforced — private repo gói Free).
4. **0a + 0b HOÀN THÀNH** (12/06 chiều-tối): PR template (`2cd7988`), CI GitHub Actions + ruff + pytest-cov (PR #15 → squash `1e139c2`, CI xanh lần đầu). Giao thức mới (plan → `DUYỆT <mã việc>` → code trên nhánh riêng → PR vào `Dat` → Claude nghiệm thu → Đạt merge) đã chạy trơn tru qua 2 việc.
5. **Quy trình duyệt plan**: Antigravity có tính năng auto-proceed làm Anti vượt rào 2 lần đầu ngày — đã vá brief (commit `aab665b`: duyệt = tin nhắn chứa `DUYỆT <mã việc>`, cấm chuyển việc khi chờ duyệt, cấm tự recover) + Đạt chỉnh setting Antigravity bắt hỏi trước khi thực thi.
6. **Sự cố sáng 12/06 — đã khôi phục xong** (chi tiết `claude-progress.md` Session 4): bài học lớn nhất = không bao giờ để repo không có baseline commit khi agent thực thi đang chạy.

## Current Gaps / In Progress

- **Parser Engine**: chưa tồn tại — hợp đồng nằm trong 4 test skip của `tests/test_specs_parser.py` + đặc tả mục 3 tài liệu phân hệ.
- **Generator**: 6 gap có chủ đích (xfail/skip): lọc approved, fail-fast, seed, Part 7 = 52/54 câu, cân bằng đáp án, topic. Bẫy fixture cho B2/B3 đã ghi trong brief (P7 toàn nhóm 4 câu; topic đơn điệu) — cần PR mở rộng `conftest.py` được duyệt trước khi gỡ xfail.
- **Alembic**: chưa init (việc 0c — PR duy nhất được đụng `models/`). Lưu ý sự cố Anti: diff chưa-commit của `grade.py`/`submission.py`/`user.py` đã mất (suite vẫn xanh với bản HEAD); khi làm 0c cần rà schema kỹ.
- **Celery chưa nối API** (SPEC-GRADE-003, thuộc milestone Chấm — NGOÀI phạm vi M2).
- **Chờ bên ngoài**: quy ước tên file MP3 với đối tác (chặn A2); sếp xác nhận quy đổi độ khó câu→nhóm (±1 trong dung sai ±2).

## Next Session Objectives

1. **Review plan 0c (`feat/alembic-foundation`) — KỸ NHẤT chuỗi setup**: PR duy nhất được đụng `backend/app/models/` (Alembic init, env.py đọc settings, migration baseline + migration nền M2: bảng `blueprints`/`import_batches`, cột `content_hash`/`source_question_id`/`import_batch_id`). Soi kỹ: không phá 5 model hiện có, `create_all()` giữ cho test, DoD = `alembic upgrade head` chạy trên PostgreSQL trống + pytest 15/7/7. Sau merge 0c: models ĐÓNG BĂNG.
2. Sau 0c: Anti làm B1 (`feat/generator-hardening` — lọc approved, fail-fast, seed, source_question_id; nhớ gỡ ignore E711 trong `.ruff.toml` khi viết lại query theo SQLAlchemy 2.0) trong lúc chờ quy ước MP3 cho A2.
3. Quy trình chuẩn mỗi việc: Anti nộp plan → Đạt gửi Claude review → Đạt gõ `DUYỆT <mã việc>` → Anti code trên nhánh riêng → PR vào `Dat` → Claude nghiệm thu độc lập (diff + ranh giới file + ruff + pytest 2 lần trong worktree) → Đạt squash merge.
4. Chờ bên ngoài: quy ước tên file MP3 với đối tác (chặn A2); sếp xác nhận quy đổi độ khó câu→nhóm.
