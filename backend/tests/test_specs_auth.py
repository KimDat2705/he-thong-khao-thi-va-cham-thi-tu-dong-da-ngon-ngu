import pytest
import base64
import json
from datetime import timedelta
from fastapi import Depends
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app as fastapi_app
from app.core.database import get_db
from app.models.user import User
from app.core.security import hash_password, create_access_token, decode_access_token
from app.core.deps import require_role
from app.core.config import settings

# Setup dummy routes for role testing
@fastapi_app.get("/api/v1/test-auth-admin")
def dummy_auth_admin(current_user: User = Depends(require_role("admin"))):
    return {"status": "ok", "user": current_user.username}

@fastapi_app.get("/api/v1/test-auth-teacher")
def dummy_auth_teacher(current_user: User = Depends(require_role("teacher"))):
    return {"status": "ok", "user": current_user.username}


@pytest.fixture
def client(db_session: Session):
    fastapi_app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(fastapi_app) as c:
        yield c
    fastapi_app.dependency_overrides.clear()


def test_SPEC_AUTH_001_register_and_login(client: TestClient, db_session: Session):
    """
    SPEC-AUTH-001: Register & Login.
    - Password hashed (not stored as plain text).
    - Public /register enforces role='candidate'.
    - Correct credentials return a valid JWT token.
    - Incorrect credentials return 401.
    """
    # 1. Register a user
    reg_payload = {
        "username": "newcandidate",
        "password": "securepassword123",
        "full_name": "John Candidate"
    }
    
    response = client.post("/api/v1/auth/register", json=reg_payload)
    assert response.status_code == 201
    data = response.json()
    assert data["username"] == "newcandidate"
    assert data["role"] == "candidate"
    
    # Verify in Database
    db_user = db_session.query(User).filter(User.username == "newcandidate").first()
    assert db_user is not None
    assert db_user.hashed_password.startswith("pbkdf2_sha256$")
    assert "securepassword123" not in db_user.hashed_password

    # 2. Login successfully
    login_payload = {
        "username": "newcandidate",
        "password": "securepassword123"
    }
    login_response = client.post("/api/v1/auth/login", json=login_payload)
    assert login_response.status_code == 200
    token_data = login_response.json()
    assert "access_token" in token_data
    assert token_data["token_type"] == "bearer"

    # Decode and verify token structure
    token = token_data["access_token"]
    payload = decode_access_token(token)
    assert payload["sub"] == "newcandidate"
    assert payload["role"] == "candidate"

    # 3. Login fails with incorrect password
    bad_login_payload = {
        "username": "newcandidate",
        "password": "wrongpassword"
    }
    bad_response = client.post("/api/v1/auth/login", json=bad_login_payload)
    assert bad_response.status_code == 401

    # 4. Login fails for non-existent user
    non_existent_payload = {
        "username": "doesnotexist",
        "password": "password"
    }
    bad_response2 = client.post("/api/v1/auth/login", json=non_existent_payload)
    assert bad_response2.status_code == 401

    # 5. Register same username again returns 409
    dup_response = client.post("/api/v1/auth/register", json=reg_payload)
    assert dup_response.status_code == 409


def test_SPEC_AUTH_002_token_authentication(client: TestClient, db_session: Session):
    """
    SPEC-AUTH-002: Token authentication & verification.
    - get_current_user accepts valid tokens.
    - Rejects missing, malformed, forged, or expired tokens with 401.
    """
    # Create test user directly in DB
    db_user = User(
        username="verifieduser",
        hashed_password=hash_password("password"),
        full_name="Verified User",
        role="candidate",
        is_active=True
    )
    db_session.add(db_user)
    db_session.commit()

    # Generate a valid token
    valid_token = create_access_token(data={"sub": "verifieduser", "role": "candidate"})

    # 1. Valid token -> 200 OK
    headers = {"Authorization": f"Bearer {valid_token}"}
    response = client.get("/api/v1/auth/me", headers=headers)
    assert response.status_code == 200
    assert response.json()["username"] == "verifieduser"

    # 2. Missing token -> 401
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401

    # 3. Malformed token -> 401
    response = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer not-three-parts"})
    assert response.status_code == 401

    # 4. Forged payload with original signature -> 401
    parts = valid_token.split(".")
    header_b64, payload_b64, signature_b64 = parts
    
    # Decode and modify payload
    rem = len(payload_b64) % 4
    pad = payload_b64 + "=" * (4 - rem) if rem > 0 else payload_b64
    payload = json.loads(base64.urlsafe_b64decode(pad.encode('utf-8')).decode('utf-8'))
    payload["sub"] = "adminuser"  # Attempt to forge admin access
    
    # Re-encode modified payload
    forged_payload_json = json.dumps(payload, separators=(',', ':'))
    forged_payload_b64 = base64.urlsafe_b64encode(forged_payload_json.encode('utf-8')).rstrip(b'=').decode('utf-8')
    
    # Assemble forged token
    forged_token = f"{header_b64}.{forged_payload_b64}.{signature_b64}"
    
    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {forged_token}"})
    assert response.status_code == 401

    # 5. Token signed with a different key -> 401
    original_key = settings.SECRET_KEY
    try:
        settings.SECRET_KEY = "DIFFERENT_SECRET_KEY_FOR_FORGERY_TEST"
        token_wrong_key = create_access_token(data={"sub": "verifieduser", "role": "candidate"})
    finally:
        settings.SECRET_KEY = original_key

    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token_wrong_key}"})
    assert response.status_code == 401

    # 6. Expired token -> 401
    expired_token = create_access_token(
        data={"sub": "verifieduser", "role": "candidate"},
        expires_delta=timedelta(seconds=-10)
    )
    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {expired_token}"})
    assert response.status_code == 401


def test_SPEC_AUTH_003_role_authorization(client: TestClient, db_session: Session):
    """
    SPEC-AUTH-003: Role-based authorization.
    - Proper role -> 200.
    - Improper role -> 403.
    - Unauthenticated -> 401.
    """
    # Create test users with different roles
    admin_user = User(
        username="adminuser",
        hashed_password=hash_password("pw"),
        full_name="Admin",
        role="admin",
        is_active=True
    )
    teacher_user = User(
        username="teacheruser",
        hashed_password=hash_password("pw"),
        full_name="Teacher",
        role="teacher",
        is_active=True
    )
    candidate_user = User(
        username="candidateuser",
        hashed_password=hash_password("pw"),
        full_name="Candidate",
        role="candidate",
        is_active=True
    )
    db_session.add_all([admin_user, teacher_user, candidate_user])
    db_session.commit()

    # Generate tokens
    admin_token = create_access_token(data={"sub": "adminuser", "role": "admin"})
    teacher_token = create_access_token(data={"sub": "teacheruser", "role": "teacher"})
    candidate_token = create_access_token(data={"sub": "candidateuser", "role": "candidate"})

    # --- Test /api/v1/test-auth-admin (Requires "admin") ---
    # 1. Admin access -> 200 OK
    res = client.get("/api/v1/test-auth-admin", headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 200
    assert res.json()["user"] == "adminuser"

    # 2. Teacher access -> 403 Forbidden
    res = client.get("/api/v1/test-auth-admin", headers={"Authorization": f"Bearer {teacher_token}"})
    assert res.status_code == 403

    # 3. Candidate access -> 403 Forbidden
    res = client.get("/api/v1/test-auth-admin", headers={"Authorization": f"Bearer {candidate_token}"})
    assert res.status_code == 403

    # 4. Unauthenticated -> 401 Unauthorized
    res = client.get("/api/v1/test-auth-admin")
    assert res.status_code == 401

    # --- Test /api/v1/test-auth-teacher (Requires "teacher") ---
    # 1. Teacher access -> 200 OK
    res = client.get("/api/v1/test-auth-teacher", headers={"Authorization": f"Bearer {teacher_token}"})
    assert res.status_code == 200
    assert res.json()["user"] == "teacheruser"

    # 2. Admin access -> 403 Forbidden
    res = client.get("/api/v1/test-auth-teacher", headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 403
