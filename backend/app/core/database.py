from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from app.core.config import settings

# Create database engine
# PostgreSQL connection pooling settings can be optimized for concurrent load
engine = create_engine(
    settings.DATABASE_URL,
    pool_size=20,          # Standard pool size
    max_overflow=10,       # Allow burst connections
    pool_pre_ping=True,     # Verify connection health
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
