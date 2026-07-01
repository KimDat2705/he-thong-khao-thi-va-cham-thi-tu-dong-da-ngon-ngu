from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    PROJECT_NAME: str = "AI-Powered Examination and Grading API"
    API_V1_STR: str = "/api/v1"
    
    # Database Settings
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/grading_db"
    
    # Redis Settings
    REDIS_URL: str = "redis://localhost:6379/0"

    # Celery: when True, tasks run inline (no broker/worker needed). Default off
    # for real async in production; set CELERY_TASK_ALWAYS_EAGER=true in
    # environments without a dedicated Celery worker (local demo, Render free tier)
    # so essay/AI grading still completes synchronously on submit.
    CELERY_TASK_ALWAYS_EAGER: bool = False
    
    # Security Settings
    SECRET_KEY: str = "SUPER_SECRET_TOKEN_CHANGE_ME"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    
    # AI Keys
    GEMINI_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None
    # Gemini model id for grading. Configurable via env (SPEC-SCALE-001) so the
    # model is swappable without code. DEFAULT = gemini-3.5-flash (Đạt-directed:
    # use Google's newest/best flagship). TRADE-OFF: on the FREE tier 3.5-flash can
    # return 503 "high demand" under load (measured 25/06 — Google rations free
    # capacity for brand-new flagships), so LIVE grading may fail intermittently
    # unless on a PAID key. Fallback if free-tier 503s bite: set env
    # GEMINI_MODEL=gemini-2.5-flash (measured 15/15 concurrent OK on free).
    GEMINI_MODEL: str = "gemini-3.5-flash"
    GEMINI_MAX_RETRIES: int = 4
    GEMINI_RETRY_BASE_DELAY: float = 1.5
    
    # Grading Sandbox
    SANDBOX_URL: Optional[str] = None  # E.g., Judge0 API URL if using SaaS

    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
