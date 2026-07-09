# Corpus SEED B1 — nguồn gốc & pháp lý (SPEC-FACTORY-026)

Bộ đề mẫu trong thư mục này (`bank_raw.json`, `pool_speak.json`, `pool_lis.json`) là **SEED** cho
nhà máy sinh câu Bản 2 (`boss_factory`) — nhà máy bám các mẫu này để nhờ AI viết câu MỚI cùng dạng.

## Provenance
- **Nội dung TỰ SOẠN NGUYÊN GỐC** ở trình độ CEFR B1 / VSTEP B1, **KHÔNG sao chép nguyên văn** bất kỳ
  đề thi hay nguồn có bản quyền nào (VSTEP-ULIS, Cambridge B1 Preliminary/PET, British Council, Aptis…).
- **Cấu trúc/định dạng** đề (bố cục Section 1-4, kiểu câu) là *ý tưởng chung không thuộc phạm vi bản quyền*;
  chỉ *câu chữ nguyên văn* mới được bảo hộ — bộ này không dùng câu chữ nguyên văn của nguồn nào.
- Cảm hứng CHỦ ĐỀ (14 chủ đề B1) tham khảo tài liệu **public-domain** (vd VOA Learning English), nhưng
  mọi câu/đoạn văn đều được **viết mới**.

## Vai trò
- Đây là **seed tạm/khởi tạo** để nhà máy có đa dạng cấu trúc + chủ đề NGAY (không chờ đề thật).
- **Bước 2** (sau): thay/bổ sung bằng **30 đề thật `EB1.2601-2630`** của đối tác khi hết lỗi QC.
- **Bước B** (sau): bổ sung nguyên liệu từ VOA public-domain cho R3/Nghe.

## Kiểm định
- Đáp án R1-R4/W1 đã qua **cổng kiểm đáp án AI đối kháng** (giải độc lập) + parse-gate (loader) —
  xem `SPEC-FACTORY-026`. Giáo viên vẫn là cổng duyệt cuối trước khi câu sinh ra được dùng.
