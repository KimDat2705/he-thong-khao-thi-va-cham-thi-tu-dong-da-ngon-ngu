import json
import urllib.request
import urllib.error
import sys
import os

# GitHub Repository Information
REPO = "KimDat2705/he-thong-khao-thi-va-cham-thi-tu-dong-da-ngon-ngu"
API_URL = f"https://api.github.com/repos/{REPO}"

def make_request(url, data=None, token=None, method="GET"):
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "Antigravity-Repo-Setup-Script"
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    
    req_data = None
    if data:
        req_data = json.dumps(data).encode("utf-8")
        headers["Content-Type"] = "application/json"
    
    req = urllib.request.Request(url, data=req_data, headers=headers, method=method)
    
    try:
        with urllib.request.urlopen(req) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8")
        try:
            err_json = json.loads(err_msg)
            return e.code, err_json
        except Exception:
            return e.code, {"message": err_msg}
    except Exception as e:
        return 500, {"message": str(e)}

def main():
    token = os.environ.get("GITHUB_TOKEN")
    if not token and len(sys.argv) > 1:
        token = sys.argv[1]
        
    if not token:
        print("[-] Error: GITHUB_TOKEN is not set.")
        print("Please run the script as: python scripts/setup_repo_github.py <YOUR_GITHUB_PERSONAL_ACCESS_TOKEN>")
        print("Or set the environment variable GITHUB_TOKEN first.")
        sys.exit(1)
        
    print(f"[*] Authenticating and setting up repo: {REPO}...")
    
    # 1. Create labels
    labels = [
        {"name": "parser", "color": "1d76db", "description": "Parser & Ingestion issues"},
        {"name": "generator", "color": "b60205", "description": "Exam Generation & Shuffling algorithms"},
        {"name": "bank", "color": "0e8a16", "description": "Question Bank administration & lifecycle"},
        {"name": "infra", "color": "bfd4f2", "description": "Database migrations, CI/CD, and settings"},
        {"name": "spec", "color": "fef2c0", "description": "Harness engineering & spec traceability"},
        {"name": "frontend", "color": "f9d0c4", "description": "Next.js UI & Web client development"}
    ]
    
    for l in labels:
        status, resp = make_request(f"{API_URL}/labels", data=l, token=token, method="POST")
        if status == 201:
            print(f"[+] Label '{l['name']}' created successfully.")
        elif status == 422: # Already exists
            print(f"[~] Label '{l['name']}' already exists.")
        else:
            print(f"[-] Failed to create label '{l['name']}': {resp.get('message')}")
            
    # 2. Create milestone
    milestone_data = {
        "title": "M2 — Ra đề tiếng Anh (17/06)",
        "description": "Milestone M2: Hoàn thành toàn bộ phân hệ Ra đề tiếng Anh (TOEIC & B1 VSTEP) bao gồm Parser, Bank, Generator & Validator.",
        "due_on": "2026-06-17T23:59:59Z"
    }
    
    milestone_number = None
    # Check if milestone already exists
    status, milestones = make_request(f"{API_URL}/milestones?state=all", token=token)
    if status == 200:
        for m in milestones:
            if m["title"] == milestone_data["title"]:
                milestone_number = m["number"]
                print(f"[~] Milestone '{milestone_data['title']}' already exists with number {milestone_number}.")
                break
                
    if not milestone_number:
        status, resp = make_request(f"{API_URL}/milestones", data=milestone_data, token=token, method="POST")
        if status == 201:
            milestone_number = resp["number"]
            print(f"[+] Milestone '{milestone_data['title']}' created with number {milestone_number}.")
        else:
            print(f"[-] Failed to create milestone: {resp.get('message')}")
            sys.exit(1)

    # 3. Create issues
    issues = [
        # Setup
        {
            "title": "chore: CI pytest - 0b",
            "body": "### chore: CI pytest - 0b\n\n**Mô tả:** Thiết lập quy trình CI bằng GitHub Actions chạy test tự động trên mỗi commit/PR.\n\n**Chi tiết:**\n- Cấu hình linter Python `ruff` (thêm vào requirements.txt, cấu hình CI chạy `ruff check app/`).\n- Cập nhật file `clean-state-checklist.md` thay thế references của flake8 thành ruff.\n- Cài đặt `pytest-cov`, cấu hình CI chạy `pytest --cov=app` để báo cáo coverage.\n- Tạo file `.github/workflows/ci.yml` chạy trên Python 3.11.\n\n**DoD:** CI chạy xanh trên PR đầu tiên, hiển thị đầy đủ kết quả test và coverage.",
            "labels": ["infra", "spec"]
        },
        {
            "title": "feat: alembic init + migration nền - 0c",
            "body": "### feat: alembic init + migration nền - 0c\n\n**Mô tả:** Thiết lập hạ tầng quản lý database migrations (Alembic) và chạy đợt di dân dữ liệu nền đầu tiên.\n\n**Chi tiết:**\n- Cài đặt `alembic` và cấu hình kết nối DB động.\n- Tạo migration 1: baseline cho các models hiện tại.\n- Tạo migration 2: thêm bảng `blueprints`, `import_batches`; thêm cột `source_question_id`, `content_hash` cho questions/question_groups.\n- Tạo models và đăng ký tương ứng.\n\n**DoD:** Chạy `alembic upgrade head` thành công trên DB PostgreSQL trống; pytest xanh hoàn toàn.",
            "labels": ["infra"]
        },
        # Track A
        {
            "title": "feat/parser-core - A1",
            "body": "### feat/parser-core - A1\n\n**Spec:** SPEC-PARSE-001, 003, 004 (planned -> active)\n\n**Mô tả:** Tạo khung xử lý Parser Engine nạp liệu lõi đúng thiết kế nguyên tử.\n\n**Chi tiết:**\n- Viết hàm `import_file(db, path, profile)` làm điểm nạp duy nhất, chạy nguyên khối trong 1 transaction.\n- Viết validators kiểm tra toàn vẹn (options, đáp án đúng) và quét ký tự lạ UTF-8 sạch.\n- Triển khai content-hash để đảm bảo tính idempotent.\n\n**DoD:** Gỡ skip và pass hoàn toàn 4 tests trong `tests/test_specs_parser.py`.",
            "labels": ["parser", "bank", "spec"]
        },
        {
            "title": "feat/parser-toeic-listening - A2",
            "body": "### feat/parser-toeic-listening - A2\n\n**Spec:** SPEC-PARSE-002 (planned -> active)\n\n**Mô tả:** Triển khai profile đọc đề nghe TOEIC.\n\n**Chi tiết:**\n- Cấu hình file profile nhận dạng tệp Word nghe và Excel đáp án.\n- Viết `audio_linker.py` liên kết MP3 theo quy ước tên file, copy vào storage local.\n\n**DoD:** Chạy nạp thành công bộ nghe TOEIC có file MP3 tương ứng.",
            "labels": ["parser", "bank", "spec"]
        },
        {
            "title": "feat/parser-toeic-reading - A3",
            "body": "### feat/parser-toeic-reading - A3\n\n**Mô tả:** Triển khai profile đọc đề đọc TOEIC.\n\n**Chi tiết:**\n- Viết `converter.py` chuyển đổi tệp nhị phân `.doc` sang `.docx` qua LibreOffice headless.\n- Cấu hình profile nhận dạng đọc hiểu TOEIC (P5, P6, P7), trích xuất hình ảnh minh họa.",
            "labels": ["parser", "bank"]
        },
        {
            "title": "feat/parser-b1 - A4",
            "body": "### feat/parser-b1 - A4\n\n**Mô tả:** Triển khai profile đọc và nạp đề VSTEP B1.\n\n**Chi tiết:**\n- Viết profile đọc đề nghe LB1 và đọc/viết EB1.\n- Parse Speaking cards thành câu hỏi tự luận dạng ghi âm.\n- Trích xuất tiêu chí thang điểm thành tệp JSON prompt trong `prompts/en/`.",
            "labels": ["parser", "bank"]
        },
        {
            "title": "feat/bank-admin-api - A5",
            "body": "### feat/bank-admin-api - A5\n\n**Mô tả:** Viết các endpoints API quản trị và duyệt ngân hàng câu hỏi.\n\n**Chi tiết:**\n- Viết endpoints: `/bank/import` (multipart upload), `/bank/questions` (lọc, phân trang), `/bank/approve` (duyệt draft -> approved).\n- Viết `/bank/stats` so khớp tồn kho approved với blueprint để cảnh báo phần thiếu.\n\n**DoD:** API tests trong `tests/test_bank_api.py` pass 100%.",
            "labels": ["bank", "frontend"]
        },
        {
            "title": "feat/bank-admin-ui - A6",
            "body": "### feat/bank-admin-ui - A6\n\n**Mô tả:** Xây dựng màn hình quản trị ngân hàng đề thi phía Frontend.\n\n**Chi tiết:**\n- Tạo trang Next.js `/admin/bank` lọc danh sách questions, nút duyệt bulk và bảng stats cảnh báo.",
            "labels": ["frontend", "bank"]
        },
        # Track B
        {
            "title": "feat/generator-hardening - B1",
            "body": "### feat/generator-hardening - B1\n\n**Spec:** SPEC-BANK-001, SPEC-GEN-006 (gap -> active), SPEC-GEN-005 (planned -> active)\n\n**Mô tả:** Nâng cấp và thắt chặt bảo mật thuật toán sinh đề.\n\n**Chi tiết:**\n- Lọc chỉ lấy câu hỏi trạng thái `approved`.\n- Thực hiện kiểm tồn kho fail-fast trước khi ghi Exam vào DB, ném `InsufficientBankError` nếu thiếu câu.\n- Tích hợp tham số `seed` và `random.Random` để đảm bảo tính tái lập.\n- Lưu source_question_id cho câu hỏi clone.\n\n**DoD:** Pytest 0 failed, 3 specs GEN-005, GEN-006, BANK-001 chuyển sang active.",
            "labels": ["generator", "spec"]
        },
        {
            "title": "feat/generator-part7-backtracking - B2",
            "body": "### feat/generator-part7-backtracking - B2\n\n**Spec:** SPEC-GEN-001, SPEC-MATRIX-002 (gap -> active)\n\n**Mô tả:** Viết thuật toán subset-sum chọn tổ hợp nhóm Part 7 TOEIC đạt đúng 54 câu và phân bổ độ khó tốt.\n\n**Chi tiết:**\n- Thay thế greedy Part 7 bằng backtracking tìm tổ hợp tối ưu.\n- Đồng bộ với fixture mở rộng có nhiều kích cỡ nhóm (2,3,5 câu) để test chạy được.\n\n**DoD:** Gỡ xfail và pass hoàn toàn 2 specs GEN-001 và MATRIX-002.",
            "labels": ["generator", "spec"]
        },
        {
            "title": "feat/generator-balance-topic - B3",
            "body": "### feat/generator-balance-topic - B3\n\n**Spec:** SPEC-GEN-002, SPEC-GEN-003 (gap -> active)\n\n**Mô tả:** Cân bằng tỷ lệ đáp án A/B/C/D và giới hạn trùng lặp chủ đề trong đề thi.\n\n**Chi tiết:**\n- Cân bằng đáp án bằng cách hoán vị các options và đáp án đúng trên bản clone (đạt 20%-28%).\n- Khống chế tỷ lệ trùng topic không quá 20% số câu trong 1 part.\n\n**DoD:** Gỡ xfail và pass hoàn toàn 2 specs GEN-002 và GEN-003.",
            "labels": ["generator", "spec"]
        },
        {
            "title": "feat/exam-validator - B4",
            "body": "### feat/exam-validator - B4\n\n**Mô tả:** Tách module kiểm định chất lượng đề thi độc lập dùng chung.\n\n**Chi tiết:**\n- Tạo file `app/services/exam_validator.py` làm post-check xác thực đề thi sau sinh.\n- Tự động rollback và sinh lại tối đa 10 lần nếu phát hiện vi phạm.\n\n**DoD:** Test `tests/test_exam_validator.py` pass 100%.",
            "labels": ["generator", "spec"]
        },
        {
            "title": "feat/blueprint-as-data - B5",
            "body": "### feat/blueprint-as-data - B5\n\n**Mô tả:** Triển khai cơ chế blueprint-as-data lưu trong DB và tổng quát hóa generator.\n\n**Chi tiết:**\n- Seed 2 bản ghi blueprint TOEIC và B1 vào DB.\n- Viết `exam_generator.py` tổng quát hóa cách đọc và sinh theo blueprints DB.\n- Giữ `generate_toeic_exam()` làm wrapper để giữ tương thích ngược.",
            "labels": ["generator", "infra"]
        },
        {
            "title": "feat/generate-batch - B6",
            "body": "### feat/generate-batch - B6\n\n**Spec:** SPEC-GEN-004 (planned -> active)\n\n**Mô tả:** Triển khai sinh hàng loạt đề thi chạy ngầm qua Celery và API kiểm tra độ trùng lặp.\n\n**Chi tiết:**\n- Tạo endpoint `/exams/generate-batch` đẩy task Celery.\n- Đo lường và sinh báo cáo trùng lặp chéo giữa các đề (overlap_report <= 40%).\n\n**DoD:** Đạt spec GEN-004 chuyển active.",
            "labels": ["generator", "infra", "spec"]
        }
    ]
    
    for i, issue in enumerate(issues):
        data = {
            "title": issue["title"],
            "body": issue["body"],
            "milestone": milestone_number,
            "labels": issue["labels"]
        }
        status, resp = make_request(f"{API_URL}/issues", data=data, token=token, method="POST")
        if status == 201:
            print(f"[+] Issue #{i+1} '{issue['title']}' created successfully.")
        else:
            print(f"[-] Failed to create issue '{issue['title']}': {resp.get('message')}")

if __name__ == "__main__":
    main()
