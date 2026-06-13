# AI-Powered Examination & Grading System - Backend

This is the backend server for the automated grading and examination system. It is built using **FastAPI (Python)**.

## Architecture

- **`app/main.py`**: API Entrypoint.
- **`app/api/`**: Endpoint routes (authentication, courses, exams, submissions).
- **`app/core/`**: Security, database configurations, environment settings.
- **`app/models/`**: SQLAlchemy models.
- **`app/schemas/`**: Pydantic models for request/response validation.
- **`app/services/`**: Grading engines, Docker runtime environment wrappers, LLM evaluators.

## Getting Started

1. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: .\venv\Scripts\activate
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the development server:
   ```bash
   uvicorn app.main:app --reload
   ```
4. Access the auto-generated API docs at `http://127.0.0.1:8000/docs`.

## Database & Migrations

This project uses **Alembic** to manage database schema migrations.

- **SQLite (Dev & Automated Tests)**: SQLite database files and in-memory test databases are initialized and updated automatically using SQLAlchemy's `create_all()`.
- **PostgreSQL (Production & Staging)**: Real PostgreSQL database instances must be upgraded to the latest schema using Alembic:
  ```bash
  alembic upgrade head
  ```

