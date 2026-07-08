"""Lưu media (audio/ảnh sinh lúc RUNTIME) lên Supabase Storage — SPEC-FACTORY-020.

VÌ SAO: disk Render free là EPHEMERAL — file sinh lúc runtime (audio bài Nghe, ảnh chọn-tranh
của nhà máy) mất khi redeploy/spin-down. Media tĩnh seed lúc BUILD (đề 2601, bank enrich) vẫn
serve từ /static như cũ — KHÔNG đổi. Helper này dành cho slice Nghe (media sinh sau deploy):
upload qua Storage REST (httpx sẵn trong requirements, 0 dep mới) → trả PUBLIC URL tuyệt đối
(serve qua CDN Supabase, không qua backend 512MB) để ghi vào Question.audio_url/image_url.

Cấu hình (env — xem render.yaml): SUPABASE_URL + SUPABASE_SERVICE_KEY + SUPABASE_BUCKET
(bucket PUBLIC, mặc định 'media'). Thiếu cấu hình → is_configured()=False, upload raise
MediaStoreError với thông điệp rõ — caller quyết graceful-skip (KHÔNG crash web process).
"""
import logging
import mimetypes

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_UPLOAD_TIMEOUT = 60.0  # giây — MP3 bài Nghe ~7.6MB trên uplink Render free


class MediaStoreError(RuntimeError):
    """Upload thất bại hoặc chưa cấu hình Supabase Storage."""


def is_configured() -> bool:
    """Đủ SUPABASE_URL + SUPABASE_SERVICE_KEY để upload chưa (bucket có default)."""
    return bool(settings.SUPABASE_URL and settings.SUPABASE_SERVICE_KEY)


def public_url(object_path: str) -> str:
    """URL public (CDN) của một object trong bucket — dạng ghi vào audio_url/image_url."""
    base = str(settings.SUPABASE_URL or "").rstrip("/")
    return f"{base}/storage/v1/object/public/{settings.SUPABASE_BUCKET}/{object_path.lstrip('/')}"


def upload_bytes(object_path: str, data: bytes, content_type: str = None) -> str:
    """Upload bytes lên bucket (upsert — chạy lại không lỗi trùng) → trả PUBLIC URL.

    object_path ví dụ 'listening/LB1.90-2601-1.mp3'. content_type đoán từ đuôi file nếu bỏ trống.
    """
    if not is_configured():
        raise MediaStoreError(
            "Supabase Storage chưa cấu hình (cần env SUPABASE_URL + SUPABASE_SERVICE_KEY) — "
            "media sinh lúc runtime sẽ không sống bền trên Render free."
        )
    ctype = content_type or mimetypes.guess_type(object_path)[0] or "application/octet-stream"
    base = str(settings.SUPABASE_URL).rstrip("/")
    endpoint = f"{base}/storage/v1/object/{settings.SUPABASE_BUCKET}/{object_path.lstrip('/')}"
    headers = {
        "Authorization": f"Bearer {settings.SUPABASE_SERVICE_KEY}",
        "Content-Type": ctype,
        "x-upsert": "true",  # ghi đè nếu trùng path (re-render audio cùng bộ)
    }
    try:
        resp = httpx.post(endpoint, content=data, headers=headers, timeout=_UPLOAD_TIMEOUT)
    except httpx.HTTPError as exc:
        raise MediaStoreError(f"Upload media lỗi mạng: {exc}") from exc
    if resp.status_code not in (200, 201):
        raise MediaStoreError(f"Upload media thất bại HTTP {resp.status_code}: {resp.text[:200]}")
    url = public_url(object_path)
    logger.info("media_store: uploaded %s (%d bytes, %s)", url, len(data), ctype)
    return url


def upload_file(local_path: str, object_path: str, content_type: str = None) -> str:
    """Upload một file trên disk (vd MP3 vừa render) → PUBLIC URL."""
    with open(local_path, "rb") as f:
        return upload_bytes(object_path, f.read(), content_type=content_type)


def download_bytes(object_path: str) -> bytes:
    """Tải nội dung một object từ bucket PUBLIC (vd sidecar bundle Nghe listening/{code}.bundle.json)
    để slice render đọc lại transcript gốc. Bucket public → GET thẳng public URL (không cần Bearer)."""
    if not is_configured():
        raise MediaStoreError(
            "Supabase Storage chưa cấu hình (cần env SUPABASE_URL + SUPABASE_SERVICE_KEY) — "
            "không tải được media runtime."
        )
    url = public_url(object_path)
    try:
        resp = httpx.get(url, timeout=_UPLOAD_TIMEOUT)
    except httpx.HTTPError as exc:
        raise MediaStoreError(f"Tải media lỗi mạng: {exc}") from exc
    if resp.status_code != 200:
        raise MediaStoreError(f"Tải media thất bại HTTP {resp.status_code}: {object_path}")
    return resp.content
