import base64
import json
import hmac
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

def base64url_encode(payload: bytes) -> str:
    return base64.urlsafe_b64encode(payload).rstrip(b'=').decode('utf-8')

def base64url_decode(s: str) -> bytes:
    # Add padding back if necessary
    rem = len(s) % 4
    if rem > 0:
        s += '=' * (4 - rem)
    try:
        return base64.urlsafe_b64decode(s.encode('utf-8'))
    except Exception as e:
        raise ValueError(f"Invalid base64url encoding: {e}")

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        from app.core.config import settings
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": int(expire.timestamp())})
    
    header = {"alg": "HS256", "typ": "JWT"}
    
    header_json = json.dumps(header, separators=(',', ':'))
    payload_json = json.dumps(to_encode, separators=(',', ':'))
    
    header_b64 = base64url_encode(header_json.encode('utf-8'))
    payload_b64 = base64url_encode(payload_json.encode('utf-8'))
    
    message = f"{header_b64}.{payload_b64}".encode('utf-8')
    from app.core.config import settings
    signature = hmac.new(settings.SECRET_KEY.encode('utf-8'), message, hashlib.sha256).digest()
    signature_b64 = base64url_encode(signature)
    
    return f"{header_b64}.{payload_b64}.{signature_b64}"

def decode_access_token(token: str) -> dict:
    parts = token.split('.')
    if len(parts) != 3:
        raise ValueError("Invalid token format")
    
    header_b64, payload_b64, signature_b64 = parts
    
    # Re-verify signature
    message = f"{header_b64}.{payload_b64}".encode('utf-8')
    from app.core.config import settings
    expected_sig = hmac.new(settings.SECRET_KEY.encode('utf-8'), message, hashlib.sha256).digest()
    expected_sig_b64 = base64url_encode(expected_sig)
    
    if not secrets.compare_digest(signature_b64, expected_sig_b64):
        raise ValueError("Signature verification failed")
    
    try:
        payload_bytes = base64url_decode(payload_b64)
        payload = json.loads(payload_bytes.decode('utf-8'))
    except Exception as e:
        raise ValueError(f"Invalid payload format: {e}")
    
    exp = payload.get("exp")
    if exp is None:
        raise ValueError("Missing expiration claim")
    
    now = int(datetime.now(timezone.utc).timestamp())
    if now > exp:
        raise ValueError("Token expired")
        
    return payload

def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    iterations = 100000
    dk = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), iterations)
    return f"pbkdf2_sha256${iterations}${salt}${dk.hex()}"

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        parts = hashed_password.split('$')
        if len(parts) != 4 or parts[0] != 'pbkdf2_sha256':
            return False
        iterations = int(parts[1])
        salt = parts[2]
        stored_hash = parts[3]
        
        dk = hashlib.pbkdf2_hmac('sha256', plain_password.encode('utf-8'), salt.encode('utf-8'), iterations)
        return secrets.compare_digest(dk.hex(), stored_hash)
    except Exception:
        return False
