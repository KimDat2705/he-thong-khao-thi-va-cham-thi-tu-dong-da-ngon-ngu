# KẾ HOẠCH: MỞ RỘNG NGÂN HÀNG ĐỀ B1 — BÀN GIAO CHO PIPELINE CỦA SẾP

> Lập 2026-07-02 (S52, Claude). Nguồn: nghiên cứu trực tiếp dữ liệu sếp gửi trên Google Drive
> (`BAN_GIAO_TONG_HOP.md`, `BAN_GIAO_NGHE_NOI.md`, `KIEN_TRUC_PIPELINE_SINH_DE.md`,
> `bank_raw.json`, `pool_lis.json`, `pool_speak.json`, `sua_nguon*.json`, `extract_bank.py`,
> `chay_tat_ca.py`) + đối chiếu demo hiện tại của mình.
>
> **Phạm vi phiên: CHỈ nghiên cứu + lập kế hoạch.** Chưa code. Chốt các quyết định ở mục 8 trước khi làm.

---

## 0. PHÂN VAI (điều chỉnh định hướng — QUAN TRỌNG)

- **Sếp (`1980anhtuan@gmail.com`)** sở hữu **pipeline "ghép đề từ ngân hàng"** (đã xong): trích → build → trộn → render → QC → web app Cloud Run. Phần **"tạo đề" coi như xong**.
- **Mình (Đạt + Claude)** = **MỞ RỘNG NGÂN HÀNG ĐỀ** — sinh thêm câu hỏi B1 tiếng Anh chất lượng, **đúng định dạng của sếp**, để sếp **ghép thẳng** vào pipeline.
- **Yêu cầu sếp nhắn:** "bám sát ngân hàng đề đã có · hạn chế tối đa việc ảo giác · tốt nhất có người chuyên môn tiếng Anh kiểm tra."
- **Gác lại:** chịu tải (SCALE-003), CN/HSK. **Chỉ B1 tiếng Anh.**

⚠️ **Hệ quả:** phần **generate đề + web + chấm** của hệ demo mình đang có **TRÙNG** với hệ của sếp → nhiều khả năng KHÔNG bàn giao. Giá trị mình mang lại = **cỗ máy sinh câu (Gemini) + kiểm chất lượng + xuất đúng format sếp**. Xem quyết định D1 (mục 8).

---

## 1. HỆ CỦA SẾP — TÓM TẮT (nguồn sự thật)

Hệ RIÊNG, **không dùng DB/SQLAlchemy như mình** — ngân hàng là **file JSON**, pipeline Python + web Flask/Cloud Run (`tdu-de-thi-b1-1091801778800.asia-east1.run.app`, project `tdu-grading-system-auto`).

**Triết lý nền (nguyên văn):** *"Sinh đề = **TRỘN ĐỀ, KHÔNG bịa câu**. Pipeline chỉ chọn và sắp xếp các câu/khối **đã được con người duyệt**... **AI KHÔNG tự sinh nội dung câu hỏi**."* Ngân hàng làm giàu bằng **trích xuất từ 30 đề THẬT (2601–2630)**.

**Đề B1 = 3 bài / 100đ:** Bài 1 **Đọc+Viết (60đ)** · Bài 2 **Nghe (20đ)** · Bài 3 **Nói (20đ)**.

**Luồng 3 lớp mỗi kỹ năng** (chìa khoá — sửa đúng chỗ):
1. `bank_*.json` — trích THÔ từ nguồn (đừng sửa tay, bị ghi đè).
2. `sua_nguon*.json` — **LỚP SỬA** (đáp án + loại section + ghi chú GV). *Sửa đáp án ở đây.*
3. → `pool_*.json` / DB = **ngân hàng CHUẨN** (đã áp mọi sửa) — generator đọc từ đây.

**Pipeline 5 giai đoạn:**
| GĐ | Script | Vai trò |
|---|---|---|
| 0 | `extract_bank.py`/`extract_lis.py`/`extract_speak.py` | Trích câu/đáp án/đoạn đọc/ảnh từ docx nguồn → `bank_*.json` |
| 1 | `build_db.py` (+`phan_loai_do_kho.py`) | Áp `sua_nguon`, **gắn độ khó**, LOẠI khối lỗi → pool (sqlite/xlsx) |
| 2 | `tron_de.py`/`tron.py` | **Trộn theo `seed`**, quota **3 Dễ/5 TB/2 Khó**, overlap ≤40%, exposure cap, khử near-dup → `plan.json` |
| 3 | `render_de.py`/`render_lis.py`/`render_speak.py` | **CLONE khối gốc từ .docx** (giữ ảnh/định dạng), reletter, bake numbering → đề+Key .docx |
| 4 | `qc_check.py`/`qc.py` | Cổng nội dung BLOCKING/CẢNH BÁO trên bản render |

**Tái lập:** 1 `random.Random(seed)` → cùng seed ⇒ cùng đề (MD5 khớp). Test ≥15–20 seed.

**Giới hạn máy (PHẢI có người):** không cổng nào kiểm được **đúng/sai NGỮ NGHĨA đáp án đọc-hiểu** → **bắt buộc GV duyệt + soát độc lập (đa-agent)** trước khi **người ký**. "Có thể **đóng băng pipeline** rồi **bồi đắp ngân hàng dần**."

---

## 2. SCHEMA BÀN GIAO (bám sát 100%)

### 2A. ĐỌC + VIẾT — `bank_raw.json` (60đ)
List phẳng 30 record (`ma_de` = "EB1.2601"…"2630"). 6 section/đề: Đọc S1–S4 (câu 1–30), Viết W1–W2. **Khóa dùng `s1..s4` (S1=R1…S4=R4).**

| Phần | Dạng bài | Lưu | Đáp án |
|---|---|---|---|
| **S1 (R1)** — 10 câu | MCQ ngữ pháp/từ vựng điền chỗ trống, **4 lựa chọn** | `s1` = dict `{"1".."10": {stem, options{A,B,C,D}, answer}}` — **cấu trúc SẠCH, dễ tái dùng nhất** | trong `answer` mỗi câu |
| **S2 (R2)** — 5 câu (11–15) | Đọc thông báo/biển báo → chọn diễn giải, **3 lựa chọn A/B/C** | `s2_raw` = list `{kind:"p"|"tbl", text}` | `s2_answers`/`key_reading` |
| **S3 (R3)** — 5 câu (16–20) | Đoạn văn + câu hỏi hiểu, **4 lựa chọn A–D** | `s3_raw` = list block | `s3_answers` |
| **S4 (R4)** — 10 chỗ (21–30) | Điền từ từ **hộp từ** (mỗi từ 1 lần) | `s4_raw` (hộp từ = block `kind:"tbl"`) | `s4_answers`/`key_cloze` (từ phải ∈ hộp) |
| **W1** — 5 câu | Viết lại câu giữ nguyên nghĩa (cho sẵn phần đầu) | `w1_raw` block | `w1_answers`/`key_w1` (câu mẫu) |
| **W2** — 1 bài | Viết thư ~100 từ theo gợi ý (2–3 ý) | `w2_raw` block | **không có key** (tự luận) |

Cờ mỗi record: `sX_complete`, `sX_has_image` (chỉ cờ, KHÔNG lưu bytes ảnh), `issues`. **KHÔNG có field độ khó/CLO/chủ đề/GUID per-item** — độ khó gắn sau ở `phan_loai_do_kho.py`.

`sua_nguon.json` (lớp sửa): `reading_fixes/cloze_fixes/w1_fixes/s1_stem_fixes/exclude_sections/render_fixes` + ghi chú GV (`typo_GV_xac_nhan`, `ghi_chu_GV`) + mỗi sửa có `_..._ly_do`.

### 2B. NGHE — `pool_lis.json` (20đ)
Dict 29 bài (LB1.2601–2629; **2630 bị loại** vì sai audio). Mỗi bài **gắn 1 file mp3 THẬT**:
`{code, audio_path, audio_name, audio_duration_s, answers{1-15}, l1_stems[5], l1_count:5, l2_gaps[6-15], l2_count:10, n_media, media_ext, flags, needs_audio_verify, has_render_fix}`.
5 câu chọn-tranh (MCQ) + 10 điền. **Đơn vị = CẢ BÀI gắn audio** — không tách câu tái dùng được.

### 2C. NÓI — `pool_speak.json` (20đ)
Dict 30 thẻ. Mỗi thẻ: `{code:"SB1.26xx", src_code, set_file, part2_topic, domain_guess, part1(cố định), part3(cố định)}`. **Chỉ `part2_topic` thay đổi**; `domain_guess` = 1 trong 14 chủ đề B1.

---

## 3. NGUYÊN TẮC (khớp yêu cầu sếp)

1. **Grounded, không sinh từ 0** → dùng **paraphrase từ chính đề thật của sếp làm seed** (đúng tinh thần BANK-007 mình đã làm) → giảm ảo giác tối đa.
2. **Bám sát định dạng** → xuất đúng shape `s1/s2_raw/.../pool_speak` — round-trip qua extract/build của sếp không vỡ.
3. **Người duyệt** → mọi item AI sinh phải qua **cổng QC tự động + GV tiếng Anh ký** (đặc biệt ngữ nghĩa đáp án đọc-hiểu — máy không tự kiểm được).
4. **Gắn nhãn độ khó Dễ/TB/Khó** cho mỗi item (để lọt quota 3/5/2 của sếp) — đây chính là "gán nhãn độ khó cho mỗi câu" mà Đạt nhắc; nó THỰC SỰ cần cho bàn giao.

---

## 4. CHIẾN LƯỢC TỔNG THỂ: "NHÀ MÁY SINH CÂU" (question factory)

Tái dùng **engine Gemini + paraphrase/enrichment** mình đã có (`b1_question_gen.py`, `paraphrase_from_seed`), NHƯNG:
- **Đầu vào (seed)** = đọc bank thật của sếp (`bank_raw.json`/`pool_speak.json`).
- **Đầu ra** = **JSON đúng schema của sếp** (không phải Question model của mình).
- **Kèm** nhãn độ khó + explanation + (Nghe) audio nếu làm.
- **Qua** cổng QC (format + hộp-từ + nhãn A/B/C/D + no-dup) + bản GV duyệt.

**KHÔNG dùng** phần web/DB/generate-đề/chấm của hệ mình cho bàn giao (trùng sếp) — xem D1.

---

## 5. KẾ HOẠCH THEO KỸ NĂNG (ưu tiên)

### 🥇 P1 — ĐỌC (S1–S4, ~45đ) — giá trị cao nhất, dễ paraphrase
- **S1/R1** (dễ nhất, cấu trúc sạch): paraphrase 300 câu R1 thật (30 đề × 10) → biến thể MCQ mới `{stem, options{A,B,C,D}, answer}` giữ điểm ngữ pháp, đảo distractor. **Bắt đầu ở đây.**
- **S2/R2**: paraphrase thông báo/biển báo (3 lựa chọn) → block `{kind,text}` + `s2_answers`. Lưu ý ảnh (18/30 có ảnh) — flag `s2_has_image`.
- **S3/R3**: khó hơn (đoạn văn + 5 câu hiểu). Paraphrase đoạn + viết lại câu hỏi, giữ đáp án. Cần GV soát ngữ nghĩa kỹ.
- **S4/R4**: cloze hộp từ — sinh đoạn mới + hộp từ, **ràng buộc đáp án ∈ hộp** (cổng QC `kiem_hop_tu` của sếp bắt lỗi này).

### 🥈 P2 — VIẾT (W1–W2, ~15đ)
- **W1**: paraphrase 150 câu biến đổi (30×5) → cặp câu gốc + phần đầu + câu mẫu. Grounded, dễ.
- **W2**: sinh **đề thư mới** theo 14 chủ đề B1 (role + thư nhận + 2–3 ý + ~100 từ). Không cần đáp án.

### 🥉 P3 — NÓI (20đ) — dễ nhất về kỹ thuật
- Sinh thêm **thẻ part2_topic** per `domain` (14 chủ đề) theo mẫu 30 thẻ thật → `pool_speak.json` shape. Rất ít rủi ro ảo giác (chỉ là chủ đề nói).

### 🚧 P4 — NGHE (20đ) — KHÓ, cân nhắc HOÃN
- Đơn vị gắn **audio thật**. Sinh mới cần **TTS** (mình có Gemini TTS) + câu khớp + ảnh chọn-tranh. Sếp ghi rõ **audio là việc trung tâm/người**. → **HOÃN** hoặc chỉ làm PoC TTS, cần chốt D3.

---

## 6. CÁC THÀNH PHẦN CẦN XÂY (backlog kỹ thuật — sau khi chốt mục 8)

1. **`seed_loader`**: đọc `bank_raw.json`/`pool_speak.json` của sếp → trích item thật làm seed (per part).
2. **`boss_exporter`**: chuyển item mình sinh → đúng shape `s1`/`s2_raw`/…/`pool_speak` + key dict. Có validate schema.
3. **`paraphrase→boss`**: nối `paraphrase_from_seed` (đã có) với exporter, per part R1/R2/R3/R4/W1/W2/Speaking.
4. **`difficulty_labeler`**: gắn Dễ/TB/Khó mỗi item (đối chiếu Ma trận B1 + độ dài/từ vựng CEFR) — để lọt quota 3/5/2. *(Chính là "gán nhãn độ khó" Đạt nhắc.)*
5. **`qc_gate`** (bám cổng của sếp): nhãn A/B/C(/D) đủ, stem không rỗng, cloze ∈ hộp từ, no near-dup (jaccard), 4-option cho R1/R3, 3-option R2.
6. **`review_export`**: xuất bản GV duyệt (bảng: câu gốc | biến thể | đáp án | độ khó | ô ký) + gộp ghi chú kiểu `sua_nguon`.
7. **`roundtrip_test`**: item sinh ra chạy thử qua bản mô phỏng extract/build/tron của sếp (hoặc bộ mini) → không vỡ, đủ pool cho N đề.

**Bàn giao** = 1 file JSON đúng format + báo cáo QC + bản GV đã ký → sếp merge vào `bank_raw.json`/`pool_*` (qua lớp `sua_nguon` nếu là sửa) rồi build lại.

---

## 7. ĐỐI CHIẾU DEMO HIỆN TẠI ↔ NHU CẦU SẾP

| Hạng mục hệ mình | Dùng cho bàn giao? |
|---|---|
| Engine Gemini sinh câu (`b1_question_gen`, R1–L2, TTS, image) | ✅ **Lõi giá trị** — tái dùng, đổi đầu ra |
| BANK-007 paraphrase-from-seed | ✅ **Đúng bài toán** — đổi seed=bank sếp, output=format sếp |
| BANK-006 async, BANK-005 enrich API | ⚠️ Có thể tái dùng cơ chế, nhưng output phải đổi |
| Web app generate đề + chọn-tranh + chấm AI + proctoring | ❌ **Trùng hệ sếp** — không bàn giao (giữ làm sandbox nội bộ nếu muốn) |
| DB SQLAlchemy + Question model + blueprint | ❌ Không khớp (sếp dùng JSON) |
| Cổng QC/validate (`validate_b1_bank`) | ⚠️ Ý tưởng tái dùng, viết lại theo cổng của sếp |

---

## 8. ⚠️ QUYẾT ĐỊNH CẦN CHỐT (trước khi code) — cần Đạt (+ hỏi sếp)

- **D1 — Phạm vi hệ mình:** Có **dừng phát triển phần web/generate/chấm** (trùng sếp), chỉ giữ **engine sinh câu** làm "nhà máy" xuất JSON cho sếp không? (Khuyến nghị: **CÓ** — tập trung giá trị, tránh trùng.)
- **D2 — Điểm nhận của sếp (KỸ THUẬT LỚN):** Render của sếp **CLONE từ .docx gốc**. Câu AI mới **không có .docx gốc**. Vậy sếp nhận item mới theo đường nào? (a) mình xuất **JSON vào `bank_raw`** + sếp mở rộng render đọc-từ-JSON (đổi pipeline sếp); (b) mình xuất luôn **.docx block chuẩn** để extract/render nuốt được; (c) mình giao JSON, **sếp tự quyết render**.
  - **✅ D2 ĐÃ CHỐT = OPTION (a)** *(02/07 S53 — Claude tự quyết theo uỷ quyền Đạt, DỰA TRÊN tài liệu sếp gửi, KHÔNG chờ sếp trả lời vì sếp chưa xong phần của sếp).* Thẩm định độc lập 3 lăng kính (biện hộ (a) · steelman (b) · phản biện cố bác (a)) đều **hội tụ về (a)**, confidence CAO. Chốt cứng:
    - **Cô lập rủi ro vào đúng 1 khâu:** 4/5 giai đoạn của sếp (extract/build_db/tron_de/qc) ĐÃ đọc `bank_raw` JSON → item mình thêm TỰ chảy vào pool + gắn độ khó + trộn quota 3/5/2 + qua QC mà sếp KHÔNG sửa gì; chỉ **render** cần THÊM 1 nhánh (không sửa logic cũ). Đây là mức phụ thuộc **nhỏ nhất** vào phần code sếp còn biến động — đúng ràng buộc "giảm tối đa phụ thuộc code sếp chưa xong".
    - **Output mình ĐÃ CÓ chính là payload (a) cần** (SPEC-FACTORY-001/002 xuất đúng shape s1/pool_speak + do_kho + truy vết) → 0 chi phí đổi hướng. Chọn (b) = vứt bỏ export JSON đã nghiệm thu để dựng lại tầng .docx.
    - **Loại (b):** tự nguyện bước vào "lớp lỗi #1" (trích xuất/CLONE .docx) do CHÍNH sếp cảnh báo; reverse-engineer parser mình không sở hữu; coupling ngược & giòn theo thời gian (sếp chỉnh `extract_bank.py` → .docx mình vỡ âm thầm); phá "JSON là nguồn sự thật duy nhất".
    - **DE-RISK (để KHÔNG bị chặn dù sếp chưa xong):** (1) **giao pure-JSON TRƯỚC** — item vào pool + được trộn ngay cả khi nhánh render-từ-JSON của sếp chưa có → tiến độ mình KHÔNG treo vào code sếp; (2) kèm **helper render-từ-JSON tham chiếu** (mình viết `build_docx_block_from_json` mẫu → chứng minh item dùng được + GV ký được TRƯỚC khi sếp làm, đồng thời là spec mẫu sếp copy); (3) **chốt schema JSON một lần** (đóng băng interface s1_item/speak_card làm hợp đồng) trước khi nhân rộng; (4) **tách part CÓ ẢNH** (R2/R3/L1) ra slice riêng — (a) sạch cho part TEXT (R1/R4/W1/W2/Nói), part ảnh cần chốt cơ chế giao asset; (5) **phương án lùi**: nếu sếp DỨT KHOÁT không đổi render → dùng (b) CHỈ cho part text (helper docx là bước đệm sẵn) → không có tình huống kẹt hoàn toàn.
    - **Giả định cần xác nhận khi sếp rảnh** (không chặn): build_db/tron nhận item mới miễn đủ cờ tối thiểu (`sX_complete` + độ khó); `qc_check` đối xử item JSON-origin (không .docx gốc) NGANG item clone. → nên xin **1 record mẫu `bank_raw` hoàn chỉnh** để đối chiếu đủ cờ.
  - **✅ KHUYẾN NGHỊ (Đạt yêu cầu chọn, trừ (c)) = OPTION (a)** — mình xuất JSON vào `bank_raw`, sếp thêm nhánh "render item từ JSON". Lý do:
    - `build_db.py`/`tron_de.py` của sếp **đã đọc `bank_raw` (JSON)** → item JSON mình thêm **tự chảy vào pool + được trộn** mà KHÔNG cần sếp sửa gì ở khâu chọn/QC. Chỉ **khâu render** cần nhánh mới.
    - Với item **text (R1/R4/W1/W2)** — phần lớn giá trị — render-từ-JSON của sếp **RẤT ĐƠN GIẢN** (đổ stem+options vào Word), nhẹ hơn nhiều so với (b).
    - (b) buộc **mình** phải dựng .docx **khớp CHÍNH XÁC** cách `extract_bank.py` parse (numbering/nhãn/bảng hộp-từ/nhúng ảnh) — đúng **lớp lỗi #1** mà chính sếp cảnh báo ("lỗi do TRÍCH XUẤT docx & CLONE"). Rủi ro cao, giòn.
    - (a) giữ **bank JSON là nguồn sự thật duy nhất** (đúng triết lý sếp) + mình tái dùng ngay output JSON đã có (SPEC-FACTORY-001 đang xuất shape `s1`).
    - **Đánh đổi:** (a) cần sếp buy-in (thêm ~1 hàm render-từ-JSON, phần ảnh R2/L1 phức tạp hơn — mình sinh ảnh Imagen + tham chiếu, sếp nhúng). Nếu sếp KHÔNG muốn đổi render → lùi về (b) chỉ cho các part text.
  - → **Cần Đạt xác nhận (a) với sếp**; đây là chốt cách ghép nối cuối.
- **D3 — Nghe:** Hoãn hẳn, hay làm PoC **TTS** (chấp nhận audio máy) chờ trung tâm thay audio thật?
- **D4 — GV duyệt:** Ai là người tiếng Anh ký? Cần bản duyệt dạng nào (Excel/Docs)? Có làm **soát chéo đa-agent** (AI review AI) trước khi tới GV để giảm tải?
- **D5 — Sản lượng mục tiêu:** mở rộng bao nhiêu/part? (vd gấp đôi kho: +10/đề R1, +…); ưu tiên P1 Đọc trước.

---

## 9. BƯỚC TIẾP (sau khi chốt D1–D5)
1. ✅ **D1 CHỐT** (Đạt 02/07): tập trung "nhà máy sinh câu", bỏ phần web/generate/chấm trùng sếp.
2. ✅ **SLICE P1-R1 XONG** (02/07, SPEC-FACTORY-001): `boss_factory.py` (load_r1_seeds → build_r1_variants shape `s1` + độ khó + truy vết → qc_r1 → export_bundle → review_sheet) + CLI `make_r1_variants.py` + test. Verify DỮ LIỆU THẬT (30 đề thật + Gemini) → biến thể chất lượng, xuất JSON `s1` + bảng GV. pytest 63/0.
3. ✅ **D2 CHỐT (a)** (02/07 S53) — xem mục 8. Bàn giao = pure-JSON đúng schema đối tác + (sẽ có) helper render-từ-JSON tham chiếu. KHÔNG chặn tiến độ mình.
4. ✅ **SLICE P3-NÓI XONG** (02/07 S53, SPEC-FACTORY-002): `boss_factory.py` mở rộng (load_speak_seeds đọc `pool_speak.json` DICT → build_speak_variants sinh `part2_topic` MỚI cùng domain, giữ part1/part3, shape pool_speak 7 field + metadata + code `SB1.90-<seed>-<n>` ổn định/truy vết + qc_speak khớp domain khoan dung định dạng + phát hiện/gắn nhãn near-dup jaccard → export_speak_bundle → speak_review_sheet) + CLI `make_speak_variants.py` + test. **Chứng minh factory tổng quát sang FORMAT THỨ 2** (pool_speak DICT ≠ bank_raw LIST). pytest 64/0, ruff/arch/traceability sạch. Verify Gemini THẬT: 3 thẻ Nói chất lượng cùng domain, QC OK, card 7 field thuần + metadata sibling. Review đối kháng 4-lăng-kính (14 agent) → vá 6 defect trước khi chốt.
5. ✅ **SLICE R4 (cloze hộp-từ) XONG** (02/07 S53, SPEC-FACTORY-003): **FORMAT THỨ 3**, GROUND trên `bank_raw.json` THẬT (đọc qua Google Drive connector — xác nhận `s4_raw` list block, hộp từ = block `kind:"tbl"`, `s4_answers`==`key_cloze` 21-30, đáp án có thể viết hoa vs hộp thường). `load_r4_seeds`/`build_r4_variants` (passage mới 10 chỗ + hộp từ, MỌI đáp án ∈ hộp — cổng `kiem_hop_tu` không phân biệt hoa/thường + blank multiset chính xác)/`qc_r4`/`export_r4_bundle`/`r4_review_sheet` + CLI + test. pytest 64→**65/0**, verify Gemini THẬT (gorilla 2601 → cloze "Benefits of Cycling"). Review đối kháng 4-lăng-kính (12 agent) → vá 4 defect.
6. ✅ **SLICE R2 (thông báo/biển báo) XONG** (02/07 S53, SPEC-FACTORY-004): **FORMAT THỨ 4** (3 đáp án A/B/C). GROUND trên s2 THẬT (`s2_raw` = block `tbl` GỘP 5 thông báo "NN. <notice> A. .. B. .. C. .."; `s2_answers` 11-15). `load_r2_seeds` **parser ROBUST** (mốc câu tăng dần trái→phải — số embedded ở câu sau không nhầm; tách options bằng " A. " hợp lệ CUỐI — chịu " A. " nội dung) + `build_r2_variants` (`s2_item` clean + `s2_raw_fragment`) + `qc_r2` + CLI + test. pytest 65→**66/0**; verify Gemini THẬT (3 thông báo 2601). Review đối kháng 12 agent **verify trên 30 đề THẬT** → parser cũ vỡ EB1.2605 (số "12." trong thân câu 15) → thiết kế lại; **verify FIX EB1.2605 THẬT đúng 5 seed**.
7. ✅ **SLICE R3 (đọc-hiểu đoạn văn) XONG** (02/07 S53, SPEC-FACTORY-005): **FORMAT THỨ 5** (4 đáp án A-D, đơn vị = CẢ NHÓM passage + câu hỏi). GROUND trên s3 THẬT (`s3_raw` = block `p` riêng: passage + từng câu "16.<stem>" + 4 option; `s3_answers` 16-20). `load_r3_seeds`/`build_r3_variants` (đoạn văn mới + câu hỏi hiểu; `s3_item` {passage,questions} + `s3_raw` + `s3_answers`)/`qc_r3` + CLI + test. **NGỮ-NGHĨA-NẶNG → GV bắt buộc soát.** pytest 66→**67/0**; verify Gemini THẬT (dentist → "Science of Sleep" 5 câu song song). Review 9 agent → vá 4 defect (regex số thập phân; crash lô shape méo; near-copy; CLI UTF-8).
8. ✅ **SLICE W1 (viết lại câu) XONG** (02/07 S53, SPEC-FACTORY-006): **FORMAT THỨ 6**. GROUND trên w1 THẬT (cặp câu gốc + câu viết-lại có chỗ trống; `key_w1` câu mẫu; dạng bị động/tường thuật/điều kiện/nominalization). `load_w1_seeds` (ghép cặp nghiêm ngặt, bỏ record lệch)/`build_w1_variants` (`w1_item` {original,prompt,answer}, câu mẫu bắt đầu bằng phần đầu)/`qc_w1` (`_w1_prefix_ok` token-based) + CLI + test. pytest 67→**68/0**; verify Gemini THẬT (5 câu đúng kiểu biến đổi). Review 16 agent → vá 10 defect (prefix false-reject/pass; [HIGH] ghép cặp lệch key; qc thiếu kiểm blank/lead).
9. **THỨ TỰ TIẾP** (đúng logic + tối ưu):
   - **W2** (đề thư ~100 từ theo 14 chủ đề, KHÔNG key — tự luận, chấm AI/GV). → sau W2 xong 6/6 dạng Đọc-Viết + Nói.
   - **Nghe (P4): hoãn** tới khi chốt D3 (cần audio; sếp bảo audio là việc trung tâm). Ảnh R2/R3 (s2/s3_has_image) tách sau (D2 de-risk).
   - **Helper render-từ-JSON tham chiếu** (de-risk D2 điểm 2) — làm khi có nhịp, không chặn.
10. Mỗi slice: spec `SPEC-FACTORY-00N` + test (mock tất định) + verify dữ liệu thật + review đối kháng + cập nhật harness (như quy trình BANK-005/6/7).

---

*Dữ liệu thô đã tải/đọc: schema 3 kỹ năng + pipeline nằm trong doc này. File JSON gốc của sếp trên Drive (owner 1980anhtuan@gmail.com); folder "Auto ra đề tiếng Anh" — gdown KHÔNG tải được (404, cần auth), đọc qua Google Drive connector.*
