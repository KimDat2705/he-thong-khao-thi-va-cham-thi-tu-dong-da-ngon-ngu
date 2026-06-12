# Pull Request Template

## Spec liên quan
<!-- Ghi rõ spec ID liên quan từ specs/specs.json, ví dụ: Closes #12 - SPEC-GEN-006 gap→active -->

## Thay đổi
<!-- Liệt kê chi tiết các thay đổi trong PR này (file nào tạo mới, hàm nào sửa đổi, logic thuật toán nào thêm mới) -->

## Cách verify
<!-- Mô tả chi tiết cách kiểm chứng sự thay đổi của bạn (ví dụ: chạy pytest test_SPEC_GEN_006, test thủ công bằng cURL/Postman, hoặc test client) -->

## Checklist
- [ ] Pytest chạy xanh tại backend (không có test `failed`)
- [ ] Cập nhật trạng thái spec tương ứng trong `specs/specs.json` (nếu có spec đổi trạng thái)
- [ ] Không đụng vào code/test của phân hệ Chấm (grading)
- [ ] Code mới tuân thủ các quy tắc chất lượng trong `quality-document.md` (SQLAlchemy 2.0 style, v.v.)
- [ ] Đã chạy `clean-state-checklist.md` và cập nhật `claude-progress.md` + `session-handoff.md` (nếu PR kết thúc session)
