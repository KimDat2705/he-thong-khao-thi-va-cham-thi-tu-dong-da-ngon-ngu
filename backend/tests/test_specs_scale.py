"""
SPEC-SCALE-* — Bảo chứng Cấu hình & Chịu tải (chiến lược MVP -> Production).

Nguyên tắc: MVP (50-100 CCU) và Production (500-1000 CCU) dùng CÙNG codebase —
mọi khác biệt hạ tầng nằm trong biến môi trường (.env). SPEC-SCALE-003 (chịu tải
500-1000 CCU) verify bằng k6/Locust trên staging, không nằm trong pytest.
"""
import time

from sqlalchemy.orm import Session

from app.services.toeic_generator import generate_toeic_exam


def test_SPEC_SCALE_001_config_from_environment(monkeypatch):
    """SPEC-SCALE-001: Mọi cấu hình hạ tầng (DATABASE_URL, REDIS_URL,
    GEMINI_API_KEY...) phải đọc từ biến môi trường; chuyển MVP -> Production
    chỉ thay .env, không sửa code.
    """
    from app.core.config import Settings

    monkeypatch.setenv("DATABASE_URL", "postgresql://prod_user:secret@cloudsql.internal:5432/exam_prod")
    monkeypatch.setenv("REDIS_URL", "redis://memorystore.internal:6379/1")
    monkeypatch.setenv("GEMINI_API_KEY", "khoa-tu-bien-moi-truong")

    # _env_file=None: bỏ qua file .env cục bộ, chỉ đọc từ env — đúng hành vi container
    fresh_settings = Settings(_env_file=None)

    assert fresh_settings.DATABASE_URL == "postgresql://prod_user:secret@cloudsql.internal:5432/exam_prod"
    assert fresh_settings.REDIS_URL == "redis://memorystore.internal:6379/1"
    assert fresh_settings.GEMINI_API_KEY == "khoa-tu-bien-moi-truong"


def test_SPEC_SCALE_002_generation_latency_smoke(db_session: Session):
    """SPEC-SCALE-002: Sinh một đề TOEIC hoàn chỉnh từ ngân hàng chuẩn phải hoàn
    tất trong dưới 10 giây (đảm bảo sinh lô 100 đề khả thi trong một phiên).

    Smoke test trên SQLite in-memory; số liệu PostgreSQL thực tế đo lại ở giai
    đoạn load test (SPEC-SCALE-003, k6/Locust trên staging).
    """
    started = time.perf_counter()
    exam = generate_toeic_exam(db_session, title="Đề kiểm tra SPEC-SCALE-002")
    elapsed = time.perf_counter() - started

    assert exam.id is not None
    assert elapsed < 10.0, f"Sinh đề mất {elapsed:.2f}s — vượt ngưỡng 10s"
