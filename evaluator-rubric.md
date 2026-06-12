# Evaluator Rubric -- HeThongKhaoThiVaChamThiTuDong

This rubric defines the criteria used to evaluate changes made by AI agents or developers.

## 1. Static Verification Gates (L1 & L2)
- **TypeScript Check**: `cd frontend && npm run build` must compile with zero strict type errors.
- **Python Check**: Code must not contain undefined variables or syntax errors.
- **Unit Tests**: All unit tests in `backend/tests` must pass with zero failures.

## 2. Architecture Boundary Constraints (L4)
- **Strict Decoupling**: Backend code must not import or depend on Next.js/React modules.
- **Database Encapsulation**: Frontend must never make direct SQL queries or import SQLAlchemy models. All DB access must go through the FastAPI REST layer.
- **Spec Integrity**: No implementation code is marked completed unless it has an active `SPEC` reference in `specs/specs.json` and a matching test in `backend/tests/`.

## 3. Performance & Scaling (L3)
- **Exam Generation Latency**: target < 1.5 seconds per TOEIC exam on SQLite/local DB (measured 2026-06-12: ~0.21s on test fixture). Hard gate per SPEC-SCALE-002 is < 10s — re-measure after Part-7 backtracking + validator land (B2/B4), as combinatorial search may add cost.
- **Audio Upload Throughput**: Opus/WebM compressed audio uploads must handle multiple concurrent files without server timeout.
- **Grading Queue Isolation**: AI grading requests must be dispatched asynchronously to Celery workers, never blocking the main web request thread. (Currently NOT met — grading runs synchronously; tracked as SPEC-GRADE-003, planned.)
