# Clean State Checklist -- HeThongKhaoThiVaChamThiTuDong

Ensure the following actions are executed before ending any development session to keep the codebase clean and reproducible:

## 1. Test Verification
- [ ] Run `pytest` inside `backend/` directory. Ensure `15 passed` (skipped and expected xfailed are acceptable, but there must be `0 failed`).
- [ ] Run the meta-test to verify spec traceability: `pytest tests/test_specs_traceability.py`.

## 2. Environment & Database Cleanup
- [ ] Verify that any temporary SQLite databases created during testing (`test.db` or similar) are deleted or configured as in-memory databases (`sqlite:///:memory:`).
- [ ] If local database instances are running, ensure they do not contain stale candidate data.

## 3. Worker Processes
- [ ] Stop any active local Celery processes or Redis mock systems: `pkill -f celery` or similar.
- [ ] Clear Redis queue caches if local tasks are stuck.

## 4. Linting and Checks
- [ ] Run linter on backend: `ruff check app/`
- [ ] Run typescript checks on frontend: `cd frontend && npm run build` (or similar next.js static compiler checks).

## 5. Artifacts and Logs
- [ ] Ensure that custom log files or debug logs (e.g. `app.log`) are ignored by `.gitignore` and not committed to GitHub.
- [ ] Update `claude-progress.md` with a summary of changes made during the session.
