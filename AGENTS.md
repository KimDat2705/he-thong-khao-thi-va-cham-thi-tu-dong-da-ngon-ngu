# AGENTS.md -- Guidelines for AI Assistants

This repository relies on structured Harness Engineering to verify development work. As an AI Agent working here, you must follow these rules:

## Development Loop

1.  **Read the Harness**: Always read `CLAUDE.md` and check `feature_list.json` before starting work.
2.  **No Hallucinations**: Do not report a feature as done unless:
    - You have written automated pytest assertions covering the feature's acceptance criteria.
    - All tests pass locally.
    - The architectural boundary validation script passes.
3.  **Handoff Duty**: Before ending your turn or when the session limit is approaching, update `claude-progress.md` with your status and write a detailed handoff description in `session-handoff.md`.
4.  **Alembic Migrations**: Never modify database models without generating a corresponding Alembic migration script.

## Spec Traceability

Every business rule implemented must map to a spec in `specs/specs.json`. If a new requirement is added:
1.  Add a spec item with a unique `SPEC-<DOMAIN>-<NNN>` ID.
2.  Implement corresponding pytest test cases matching the spec ID.
3.  Link the test case in `specs.json`.
