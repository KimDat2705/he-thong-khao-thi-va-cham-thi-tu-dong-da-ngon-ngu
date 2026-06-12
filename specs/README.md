# Specs — Harness Engineering

Thư mục này chứa **catalog spec** của hệ thống: [`specs.json`](specs.json) là **nguồn sự thật duy nhất** cho mọi bảo chứng kiến trúc. Mỗi spec là một cam kết có thể kiểm chứng tự động — không phải mô tả mong muốn chung chung.

## Triết lý

> 1 bảo chứng kiến trúc = 1 mã SPEC + tiêu chí chấp nhận + test tự động.

- Tài liệu kiến trúc (`docs/kien_truc_he_thong_v2.html`, mục 9) chỉ **render** nội dung catalog này — khi sửa spec, sửa `specs.json` trước rồi cập nhật tài liệu.
- Meta-test `backend/tests/test_specs_traceability.py` kiểm tra truy vết **2 chiều**: mọi spec `verification: pytest` phải trỏ tới test tồn tại, và mọi mã SPEC xuất hiện trong file test phải có trong catalog. CI fail nếu lệch.

## Schema một spec

| Trường | Ý nghĩa |
|---|---|
| `id` | `SPEC-<DOMAIN>-<NNN>`, ví dụ `SPEC-GEN-001`. 4 ID legacy từ tài liệu v1 giữ nguyên văn (`SPEC-PARSE-001`, `SPEC-MATRIX-002`, `SPEC-ISOLATE-003`, `SPEC-COLLATE-004`, đánh dấu `"legacy": true`). |
| `domain` | Nhóm logic: `PARSE` (nạp liệu), `BANK` (ngân hàng câu hỏi), `GEN` (sinh đề), `GRADE` (chấm thi), `I18N` (đa ngôn ngữ), `SCALE` (chịu tải/cấu hình). |
| `statement` | Phát biểu cam kết, một đoạn, kiểm chứng được. |
| `acceptance_criteria` | Danh sách tiêu chí chấp nhận cụ thể — test phải assert đúng các tiêu chí này. |
| `verification` | `pytest` \| `load-test` \| `manual`. |
| `status` | Xem bảng dưới. |
| `tests` | Danh sách `tests/<file>.py::<hàm test>` (đường dẫn tương đối từ `backend/`). |
| `notes` | Bối cảnh: vì sao gap, cần gì để chuyển trạng thái. |

## Ba trạng thái

| Trạng thái | Ý nghĩa | Marker pytest |
|---|---|---|
| `active` | Code hiện tại **đạt** bảo chứng — test PASS hôm nay | (không marker) |
| `gap` | Đã đặc tả nhưng code hiện tại **chưa đạt** — assertion vẫn chạy, tự phát hiện khi được sửa | `@pytest.mark.xfail(strict=False, reason="GAP: ...")` |
| `planned` | Subsystem chưa tồn tại (vd: Parser Engine) — hợp đồng ghi trong docstring | `@pytest.mark.skip(reason="...")` |

Suite luôn phải **exit 0**: `fail` thật là lỗi chặn merge; `xfail`/`skip` là trạng thái được quản lý.

## Quy ước đặt tên test

```
test_SPEC_<DOMAIN>_<NNN>_<mô_tả_ngắn>
```

Ví dụ: `test_SPEC_GEN_001_blueprint_part_counts` trong `backend/tests/test_specs_generation.py`. Meta-test dựa vào token `SPEC_<DOMAIN>_<NNN>` trong tên hàm/docstring để đối chiếu ngược về catalog.

## Thêm một spec mới (4 bước)

1. **Thêm entry vào `specs.json`**: chọn `domain`, lấy số `NNN` kế tiếp trong domain đó, viết `statement` + `acceptance_criteria` đo được.
2. **Viết test** trong `backend/tests/test_specs_<domain>.py` theo quy ước tên; gắn marker đúng trạng thái (`xfail` nếu code chưa đạt, `skip` nếu subsystem chưa có).
3. **Khai `tests[]`** trong entry spec trỏ tới test vừa viết.
4. **Chạy kiểm tra**: `cd backend && python -m pytest tests -q` — meta-test traceability sẽ xác nhận liên kết 2 chiều; cập nhật bảng spec trong `docs/kien_truc_he_thong_v2.html` mục 9.

## Vòng đời chuyển trạng thái

- `planned → active`: triển khai xong subsystem → bỏ `skip`, hoàn thiện assertion, chạy pass → đổi `status` trong catalog.
- `gap → active`: sửa code → test tự chuyển **XPASS** (nhờ `strict=False`) → bỏ marker `xfail`, đổi `status`.
- Spec sai/lỗi thời: không xóa lặng lẽ — chuyển `status` về ghi chú deprecated trong `notes` kèm lý do, gỡ test tương ứng trong cùng commit.
