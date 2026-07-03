from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

try:  # pragma: no cover - optional dependency
    from jose import JWTError, jwt
except ImportError:  # pragma: no cover - fallback for demo environments
    JWTError = ValueError  # type: ignore[assignment]
    jwt = None  # type: ignore[assignment]

try:  # pragma: no cover - optional dependency
    from passlib.context import CryptContext
except ImportError:  # pragma: no cover - fallback for demo environments
    CryptContext = None  # type: ignore[assignment]

from app.core.config import settings


_PWD_CONTEXT = CryptContext(schemes=["bcrypt"], deprecated="auto") if CryptContext else None
_PBKDF2_ITERATIONS = 390000


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def _json_dumps(data: dict[str, Any]) -> bytes:
    return json.dumps(data, separators=(",", ":"), sort_keys=True, default=str).encode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Compare a plain-text password against a stored hash.

    Uses passlib/bcrypt when available, otherwise falls back to a standard
    library PBKDF2 implementation so demo environments keep working.
    """
    if _PWD_CONTEXT is not None:
        return _PWD_CONTEXT.verify(plain_password, hashed_password)

    try:
        scheme, iterations, salt_hex, digest_hex = hashed_password.split("$", 3)
    except ValueError:
        return False

    if scheme != "pbkdf2_sha256":
        return False

    derived = hashlib.pbkdf2_hmac(
        "sha256",
        plain_password.encode("utf-8"),
        bytes.fromhex(salt_hex),
        int(iterations),
    ).hex()
    return hmac.compare_digest(derived, digest_hex)


def get_password_hash(password: str) -> str:
    """Hash a password using bcrypt when available, or PBKDF2 as a fallback."""
    if _PWD_CONTEXT is not None:
        return _PWD_CONTEXT.hash(password)

    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        _PBKDF2_ITERATIONS,
    ).hex()
    return f"pbkdf2_sha256${_PBKDF2_ITERATIONS}${salt.hex()}${digest}"


def create_access_token(
    subject: str,
    expires_delta: timedelta | None = None,
    additional_claims: dict[str, Any] | None = None,
) -> str:
    """Create a signed JWT access token."""
    expire = datetime.now(timezone.utc) + (
        expires_delta
        if expires_delta is not None
        else timedelta(minutes=settings.access_token_expire_minutes)
    )

    payload: dict[str, Any] = {
        "sub": subject,
        "iat": int(datetime.now(timezone.utc).timestamp()),
        "exp": int(expire.timestamp()),
    }
    if additional_claims:
        payload.update(additional_claims)

    if jwt is not None:
        return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)

    header = {"alg": "HS256", "typ": "JWT"}
    header_segment = _b64url_encode(_json_dumps(header))
    payload_segment = _b64url_encode(_json_dumps(payload))
    signing_input = f"{header_segment}.{payload_segment}".encode("ascii")
    signature = hmac.new(
        settings.secret_key.encode("utf-8"),
        signing_input,
        hashlib.sha256,
    ).digest()
    return f"{header_segment}.{payload_segment}.{_b64url_encode(signature)}"


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode a JWT access token and return its payload."""
    if jwt is not None:
        return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])

    try:
        header_segment, payload_segment, signature_segment = token.split(".")
    except ValueError as exc:
        raise JWTError("Invalid token format") from exc

    signing_input = f"{header_segment}.{payload_segment}".encode("ascii")
    expected_signature = hmac.new(
        settings.secret_key.encode("utf-8"),
        signing_input,
        hashlib.sha256,
    ).digest()
    if not hmac.compare_digest(_b64url_encode(expected_signature), signature_segment):
        raise JWTError("Invalid signature")

    payload = json.loads(_b64url_decode(payload_segment).decode("utf-8"))
    exp = payload.get("exp")
    if exp is not None and int(exp) < int(datetime.now(timezone.utc).timestamp()):
        raise JWTError("Token expired")
    return payload


def validate_access_token(token: str) -> dict[str, Any]:
    """Validate a token and raise a clear error for invalid credentials."""
    try:
        payload = decode_access_token(token)
    except JWTError as exc:
        raise ValueError("Invalid authentication token") from exc

    subject = payload.get("sub")
    if not subject:
        raise ValueError("Token payload is missing subject")

    return payload
