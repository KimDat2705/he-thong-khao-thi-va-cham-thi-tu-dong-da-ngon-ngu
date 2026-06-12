# Sprint Contract -- Sprint 1: English Exam Generation Pipeline

## Objective

Build the complete pipeline to ingest English exam files (.docx / .xlsx), import them to the question bank, generate exams based on blueprints (VSTEP/TOEIC), and validate correctness through automated gates.

## Deliverables

1.  **Parser/Ingestion Engine**:
    - Convert legacy `.doc` files to `.docx`.
    - Parse paragraph structures and questions using python-docx.
    - Extract reference answers and difficulty weights using openpyxl.
    - Map MP3 files to question IDs and output complete JSON payloads.
2.  **Validator Service**:
    - Implement `app/services/exam_validator.py` verifying generated exam constraints.
    - Limit overlap between any two exams to less than 40%.
3.  **Harness Verification**:
    - Fully verify all 16 related specs in `specs/specs.json` (move from `gap` or `planned` to `active`).
    - Run unit tests and monorepo architectural boundary validations.
