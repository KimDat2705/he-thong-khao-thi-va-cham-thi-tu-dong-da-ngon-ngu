# Quality Document -- Code Standards and Coverage

## 1. Code Style Conventions

### Backend (Python)
- Follow PEP-8 styling conventions.
- Use explicit type annotations for FastAPI router inputs and service signatures.
- Prefer SQLAlchemy 2.0 style queries (e.g. `select(User).where(...)` instead of old `db.query(User)`).
- Pydantic models must use configuration to forbid extra inputs where strictness is required.

### Frontend (TypeScript / Next.js)
- Maintain strict TypeScript type definitions (no implicit `any`).
- Use React functional components with custom hooks for side effects.
- Clean up media stream objects immediately after recording or video verification finishes to prevent memory leaks.

## 2. Test Coverage & Quality
- Core services (Parser, Generator, Grading, Auth) must maintain a minimum of **85% code coverage**.
- All critical business logic boundaries (validation gates) must have corresponding unit test assertions.
- Use mocks for Gemini API grading requests during testing to avoid API cost and flaky network calls.
