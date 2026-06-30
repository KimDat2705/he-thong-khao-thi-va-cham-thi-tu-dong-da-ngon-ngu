# CLAUDE.md -- Quick Reference for Claude Code / Antigravity

## Project Overview

Multi-language automated exam generation and grading system (VSTEP for English, HSK for Chinese).
Features split frontend (Next.js 16, TypeScript, Tailwind v4) and backend (FastAPI, SQLAlchemy 2, Celery, Redis).

## Build & Run Commands

### Backend (FastAPI)

```bash
cd backend
python -m venv venv              # Create virtual environment
source venv/Scripts/activate     # Activate on Windows (Git Bash)
pip install -r requirements.txt  # Install python dependencies
uvicorn app.main:app --reload    # Run FastAPI local server (port 8000)
pytest                           # Run test suite
```

### Frontend (Next.js)

```bash
cd frontend
npm install                      # Install node modules
npm run dev                      # Run dev server (port 3000)
npm run build                    # Compile Next.js build
npm run test                     # Run frontend tests (if any)
```

## Architecture Rules

- **Strict Decoupling**: Backend code must never import React or frontend files. Frontend code must never import python scripts or SQLAlchemy DB models directly. All communication happens via HTTP/JSON REST API.
- **Blueprint-as-Data**: Exam configurations (blueprints) are treated as database records, not hardcoded logic. Adding a new exam format (e.g., VSTEP B2) only requires inserting a new blueprint record.
- **Bank Immutability**: Questions inside a generated exam are cloned copies of the question bank records. Modifying or retiring a question in the bank does not affect past/released exams.
- **Spec Traceability**: Every business rule in `specs/specs.json` must link to a test in `backend/tests/test_specs_<domain>.py` named `test_SPEC_<DOMAIN>_<NNN>_<description>`.

## Development Workflows

1. **Modify Database Models**: Update files in `backend/app/models/` and run `alembic revision --autogenerate -m "description"` inside the backend folder to generate migration scripts.
2. **Implement API Endpoint**: Define schemas in `backend/app/schemas/`, implement services in `backend/app/services/`, and register router in `backend/app/api/`.
3. **Write Tests**: Write pytest assertions under `backend/tests/`. Run `pytest tests/` to verify traceability and logic.

## Verification

```bash
pytest                               # Run backend specs and meta-tests
bash scripts/check-architecture.sh   # Run layer boundary checks
```

## Session Continuity & Harness Map (tiến độ giữa các phiên chat)

**Phân vai dự án:** Đạt + Claude = giao việc, quản lý tiến độ, review/nghiệm thu. Anti (Antigravity) = thực thi code theo brief `docs/workflow_giao_viec_anti_agent.md` (giao thức plan-trước-code, mỗi PR một track).

**Bản đồ file harness — đọc/ghi đúng lúc:**

| File | Vai trò | Khi nào dùng |
|---|---|---|
| `claude-progress.md` | Nhật ký session (việc đã làm, pytest, next steps) | ĐỌC đầu phiên mới · GHI cuối khối việc lớn hoặc khi user nói "cập nhật tiến độ" |
| `session-handoff.md` | Handoff chi tiết: trạng thái, gaps, mục tiêu phiên sau | GHI trước khi kết thúc phiên làm việc lớn |
| `feature_list.json` | Sổ trạng thái feature (status/evidence/testedAt) | CẬP NHẬT trung thực khi feature đổi trạng thái — chỉ "active" khi có test pass (luật No-Hallucination trong `AGENTS.md`) |
| `specs/specs.json` | Nguồn sự thật 23 spec | Trạng thái spec KHÔNG suy đoán từ trí nhớ — đọc file + chạy `cd backend && python -m pytest tests -q` |
| `evaluator-rubric.md` | Rubric nghiệm thu (gates L1-L4, hiệu năng) | Dùng làm checklist mỗi khi review/nghiệm thu PR của Anti |
| `quality-document.md` | Chuẩn code (PEP-8, SQLAlchemy 2.0 style, strict TS, coverage 85%) | Đối chiếu khi review code mới |
| `clean-state-checklist.md` | Checklist trước khi kết thúc phiên dev | Chạy trước khi đóng phiên có sửa code |
| `sprint-contract.md` | Cam kết sprint hiện tại (Sprint 1 = pipeline Ra đề EN) | Đối chiếu phạm vi khi nhận yêu cầu mới |
| `AGENTS.md` | Luật chung cho mọi AI agent làm việc trong repo | Mặc định tuân thủ (Development Loop, Handoff Duty, Spec Traceability) |

**Bí mật:** API key chỉ nằm trong `backend/.env` (đã gitignore) — tuyệt đối không đưa vào tài liệu, code, hay commit.
