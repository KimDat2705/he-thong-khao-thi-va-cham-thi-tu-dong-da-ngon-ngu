# Kế hoạch đưa Viết / Nói / Nghe của nhà máy lên web (S57)

> Nguồn: nghiên cứu đa-agent 07/07/2026 (6 nhánh: BE factory-web · boss_factory W/S/L · FE+media · TTS · chuẩn B1+ảnh · hosting) + synthesis + 2 phản biện đối kháng (14 finding → sửa hết).
> Trả lời 3 câu Đạt: (a) render-từ-JSON → BỎ, không quan tâm; (b) ảnh → AI-sinh có cổng kiểm (chi tiết §3); (c) TTS → nâng cấp engine hiện tại bằng style-prompt, ĐO A/B trước (chi tiết §4).

## 0. ⚠️ PHÁT HIỆN SỐNG CÒN (báo Đạt ngay)

**DB LIVE là SQLite file trên disk ephemeral của Render free** (`render.yaml`: `sqlite:///./demo_toeic.db`, seed lúc BUILD). Mọi câu nhà máy sinh qua web (kể cả R1-R4 của SPEC-FACTORY-016 đang LIVE) **MẤT sau mỗi lần Render ngủ ~15 phút idle / redeploy / restart**. Bug này tồn tại bất kể phiên này — cho tới khi Slice 4 xong, KHÔNG hứa với GV rằng câu draft sống qua ngày. Cần verify LIVE 1 lần hành vi spin-down để chốt thông điệp.

## 1. Trả lời câu hỏi trung tâm: TỪNG SLICE hay ĐỒNG THỜI?

**TUẦN TỰ cho mọi slice đụng 3 file chung** (`factory_service.py` / `factory_to_bank.py` / `api/factory.py`+FE panel) — tránh conflict, giữ mỗi slice 1 spec + test + verify thật + review đối kháng. **2 ngoại lệ được chạy SONG SONG** vì khác file hoàn toàn:
- Slice 4 (persist DB/media — gần như chỉ đổi env) — làm NGAY khi Đạt tạo account.
- Slice 5 (TTS A/B harness — script đo riêng).

Thứ tự: hỏi D1+D6+D4 đầu phiên → **Slice 1 (W1/W2) ‖ Slice 4 (persist)** → Slice 2 (Nói) → Slice 3 (Nghe text-only) ‖ Slice 5 (TTS A/B) → Slice 6 (Nghe full media).

## 2. Sáu slice

| # | Spec | Phạm vi chính | Effort |
|---|---|---|---|
| 1 | SPEC-FACTORY-017 | **W1+W2 lên web.** `factory_service`: +2 skill; `/factory/skills` trả thêm `parts:[int]`; `factory_to_bank`: `_w1_rows` (part 5, `reference_answer`=câu mẫu, format theo D6) + `_w2_rows` (part 6, không key); converter TỰ chèn note "GV soát tay/chưa qua cổng kiểm" vào explanation (guard `factory_service.py:77` khiến nhánh note trong boss_factory không bao giờ chạy cho skill ngoài R1-R4); **cổng kiểm W1 independent-solve** (D7c — W1 có key đóng, qc_w1 chỉ prefix-match, key sai lan vào điểm thi qua grade_writing); bỏ chốt chặn api; FE bỏ hardcode skill → fetch `/skills`, **tăng poll timeout** + thông điệp "job vẫn chạy nền"; UI phân biệt 3 mức: R1-R4 (cổng AI) / W1 (cổng solve) / W2-Nói-Nghe (GV tay). | 1–1.5 phiên |
| 2 | SPEC-FACTORY-018 | **Nói lên web.** Seed loader theo skill (`pool_speak.json`); chỉ import `part2_topic` (nội dung mới duy nhất) → 1 Question `speaking` part theo D4 (khuyến nghị part 11); part1/part3 là seed lặp → KHÔNG import. | 0.5–1 phiên |
| 3 | SPEC-FACTORY-019 | **Nghe TEXT-ONLY** (kịch bản vào bank, audio pending). 5 Question part 7 + 1 group part 8 (10 con `fill`). **3 chốt an toàn BẰNG CODE:** (a) chống LỘ ĐÁP ÁN — `passage_text` phải là notes-template đục lỗ (TakeView render passage_text thẳng cho thí sinh; transcript đầy chỉ ở explanation admin) + TEST assert không chứa đáp án verbatim = điều kiện nghiệm thu; (b) guard chặn approve câu part 7/8 chưa có audio (bulk-approve hiện flip status không kiểm gì); (c) guard chặn approve khối W1 part 5 <5 câu (review S57 finding 11 — bulk-approve không hiển thị explanation nên cảnh báo trong explanation chưa đủ). Options tranh: chỉ nhãn A/B/C, mô tả cất metadata (không mớm đáp án khi có tranh). | 1 phiên |
| 4 | SPEC-FACTORY-020 | **Persist: Supabase Postgres (DB) + Storage (media)** — sửa bug §0. Gotcha phải xử lý: dùng Supavisor session-pooler URL port 5432 (direct host IPv6-only), đổi scheme `postgres://`→`postgresql://`, đối chiếu pool_size với hạn mức pooler free, test kết nối local TRƯỚC khi đổi env Render. Helper upload Storage bằng httpx (~30 dòng), nén ảnh, URL tuyệt đối vào audio_url/image_url, serve qua CDN. Verify: sinh câu → đợi ngủ 15' → wake → câu còn sống. | 1 phiên |
| 5 | SPEC-FACTORY-021 | **TTS A/B harness ĐO TRƯỚC** (kiểu eval_answer_gate): v1 prompt hiện tại · v2 style-prompt Director's Notes per-speaker + inline tags · v3 `gemini-3.1-flash-tts-preview`. Đạt+GV nghe tai chấm → chốt rồi mới tích hợp. $0, ~10 dòng sửa `_lis_tts`. | 0.5–1 phiên |
| 6 | SPEC-FACTORY-022 | **Nghe FULL media:** nút "render audio" riêng cho bộ đã import → build_listening_audio (style đã chốt) → MP3 → upload Storage → update audio_url CẢ BỘ 15 câu (1 file trọn bài); ảnh L1 chỉ khi D2 duyệt (billing) + cổng kiểm ảnh ngược; **generate đề Nghe cần D5** (exam_generator sample từng part độc lập — không có ràng buộc part 7↔8 cùng bài → phải chọn P1 sửa generator / P2 audio per-question); đo thật RAM/thời-gian 1 bài trên LIVE trước khi mở cho GV. | 2–3 phiên |

## 3. Hướng ẢNH (câu b của Đạt) — HYBRID, chính = AI-sinh

- **Tranh L1 chọn-tranh: AI-sinh (Gemini image)** — hướng DUY NHẤT tự động hoá được ràng buộc "bộ 3 tranh cùng style, khác đúng 1 chi tiết nghe được". Kho nguồn mở (Openclipart/Openverse/Pixabay) license sạch nhưng không có bộ-3-cùng-style khớp transcript sinh mới (chọn tay 5-10'/câu = phá mục tiêu nhà máy); kho đề mở có ảnh KHÔNG tồn tại hợp pháp (sample Cambridge © UCLES). Ép style "black-and-white line drawing, exam illustration" — đúng chuẩn tranh PET Part 1 thật (xác minh từ PDF Cambridge chính thức). KÈM cổng kiểm ảnh ngược (Gemini vision giải độc lập → so đáp án → lệch = SUSPECT) — chờ D2 duyệt.
- **Điều kiện tiền:** image API KHÔNG có free tier — $0.039/ảnh ≈ $0.59/bài 15 ảnh. → D2. Model `gemini-2.5-flash-image` shutdown 02/10/2026 → phải đặt lịch swap.
- **R2 biển báo/notice: KHÔNG dùng AI ảnh** (chữ-trong-ảnh dễ sai) — đề xuất renderer template Pillow/SVG từ text đã QC ($0, khớp 100%, mở khoá ~18/30 seed s2 đang bị loại) — NGOÀI phạm vi phiên, nằm D7a.

## 4. Hướng TTS (câu c của Đạt) — nâng cấp engine hiện tại, KHÔNG đổi provider

Bệnh "đều đều" có nguyên nhân kỹ thuật xác định: `_lis_tts` truyền text THÔ, không style-prompt — trong khi docs chính thức Gemini TTS hỗ trợ điều khiển tone/emotion/pace/accent bằng natural-language (Director's Notes) + inline tags (`[cheerfully]`, `[surprised]`…). Cấu trúc audio hiện tại ĐÃ đúng khung PET chính thức (đọc 2 lần, pause, không nhạc hiệu — đối chiếu tapescript Cambridge). Việc làm = style-preamble per-speaker (nữ British + nam American, natural conversational pace) + cấy inline tags lúc sinh kịch bản + thử `gemini-3.1-flash-tts-preview` (có free tier, context-aware) → **A/B nghe tai (Slice 5) rồi mới tích hợp**. Giới hạn thật: free-tier TTS ~15 req/ngày = 1-2 bài/ngày (đủ giai đoạn GV duyệt); cần sản lượng → trả phí ~$0.26-0.51/bài (D3). Backup $0: edge-tts (unofficial, rủi ro 403). LOẠI: OpenAI/ElevenLabs/Kokoro/Piper (căn cứ trong log nghiên cứu).

## 5. Quyết định chờ Đạt (D1-D7)

- **D1 (KHẨN)**: tạo account Supabase (free, $0) — sửa bug §0. Khuyến nghị: DUYỆT ngay.
- **D2**: billing Gemini cho ảnh L1 — khuyến nghị **tách key/project GCP RIÊNG cho image** (key chấm thi giữ free làm cầu chì; billing chung key = mọi usage vượt free của MỌI model tính tiền âm thầm, budget alert chỉ báo không chặn) + duyệt cổng kiểm ảnh ngược. Chưa bật → part 7 không tranh (graceful skip sẵn).
- **D3**: ngưỡng chi TTS khi cần sản lượng (~$1-8/tháng) — quyết sau A/B Slice 5.
- **D4**: mapping thẻ Nói — khuyến nghị chỉ import `part2_topic` → part 11; part 9/10 bank dùng nguồn enrich cũ.
- **D5**: audio khi generate đề Nghe (TRƯỚC Slice 6, đụng địa hạt sinh đề = việc sếp): P1 sửa generator lấy trọn bộ 15 câu/bài (khuyến nghị về nội dung, cần hồi quy 2601) vs P2 audio per-question (rẻ code, lệch quyết định "cả file không cắt" cũ).
- **D6**: format W1 (TRƯỚC Slice 1): P1 gộp 5 câu/1 Question giữ format đề 2601 (KHUYẾN NGHỊ — đề giống thật, thang điểm giữ nguyên) vs P2 1 câu/Question + nâng blueprint count=5.
- **D7**: (a) renderer biển báo R2? (b) seed thật của sếp cho Nói/Nghe web (fixture hiện RẤT ÍT: W1:3, W2:1, Nói:2, Nghe:2 → sản lượng thấp)? (c) cổng kiểm W1 independent-solve? (d) guard approve đặt ở bank-approve (khuyến nghị) hay exam_generator? (e) FE bỏ hardcode skill list?

## 6. Rủi ro chính (tóm)

Ephemeral (§0) · gotcha Supabase↔Render (IPv6/scheme/pool) · lộ đáp án Nghe (vá Slice 3, test = điều kiện nghiệm thu) · an toàn thi phải là CODE không quy ước · W2/Nói/Nghe không có cổng kiểm đáp án tự động → GV là chốt duy nhất, UI không được hiển thị nhầm PASS · job Nghe full 10-30' trên thread 512MB · quota Gemini free chung key với chấm thi (sinh câu ngoài giờ thi) · seed fixture ít → sản lượng thấp cho tới khi có seed thật · style-prompt TTS là xác suất → bắt buộc A/B tai người.
