import logging

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from app.core.config import settings

logger = logging.getLogger(__name__)

# Create database engine
# SQLite does not support connection pooling (pool_size/max_overflow) like PostgreSQL
if settings.DATABASE_URL.startswith("sqlite"):
    # In rõ backend DB lúc khởi động (mask credential) — hành vi sync:false của Render Blueprint
    # khi UPDATE là GIỮ giá trị env cũ (không crash) → sai-thứ-tự-deploy sẽ chạy SQLite ÂM THẦM;
    # dòng log này là bằng chứng verify nhanh trong Render logs (review đối kháng S57 C7).
    logger.warning("DB backend: sqlite (%s) — EPHEMERAL trên Render free, KHÔNG dùng cho LIVE.",
                   settings.DATABASE_URL)
    engine = create_engine(
        settings.DATABASE_URL,
        connect_args={"check_same_thread": False}  # Required for SQLite in multi-threaded FastAPI
    )
else:
    _host = settings.DATABASE_URL.split("@")[-1].split("/")[0] if "@" in settings.DATABASE_URL else "?"
    logger.info("DB backend: %s @ %s (pool %d+%d)", settings.DATABASE_URL.split(":", 1)[0],
                _host, settings.DB_POOL_SIZE, settings.DB_MAX_OVERFLOW)
    engine = create_engine(
        settings.DATABASE_URL,
        # Pool nhỏ mặc định (5+5) — Supabase free Supavisor session-pooler có hạn mức client
        # thấp; nâng qua env DB_POOL_SIZE/DB_MAX_OVERFLOW khi lên paid (SPEC-FACTORY-020).
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        pool_pre_ping=True,     # Verify connection health (pooler/Render hay cắt kết nối idle)
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# Dependency to get DB session in endpoints
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

