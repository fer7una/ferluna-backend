from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from typing import Any

JWT_ALGORITHM = "HS256"
DEFAULT_JWT_TTL_SECONDS = 30 * 60


class AuthConfigError(RuntimeError):
    pass


class TokenValidationError(RuntimeError):
    pass


def admin_password() -> str | None:
    return os.environ.get("FERLUNA_ADMIN_PASSWORD")


def jwt_secret() -> str | None:
    return os.environ.get("FERLUNA_JWT_SECRET")


def jwt_ttl_seconds() -> int:
    raw_value = os.environ.get("FERLUNA_JWT_TTL_SECONDS")
    if not raw_value:
        return DEFAULT_JWT_TTL_SECONDS

    try:
        ttl = int(raw_value)
    except ValueError as exc:
        raise AuthConfigError("FERLUNA_JWT_TTL_SECONDS must be an integer") from exc

    if ttl < 60 or ttl > 24 * 60 * 60:
        raise AuthConfigError("FERLUNA_JWT_TTL_SECONDS must be between 60 and 86400")

    return ttl


def is_admin_auth_configured() -> bool:
    return bool(admin_password() and jwt_secret())


def verify_admin_password(candidate: str) -> bool:
    expected = admin_password()
    return bool(expected) and hmac.compare_digest(candidate, expected)


def create_admin_jwt() -> dict[str, object]:
    secret = jwt_secret()
    if not secret or not admin_password():
        raise AuthConfigError("FERLUNA_ADMIN_PASSWORD and FERLUNA_JWT_SECRET must be configured")

    now = int(time.time())
    expires_at = now + jwt_ttl_seconds()
    payload = {
        "sub": "ferluna-admin",
        "iat": now,
        "exp": expires_at,
        "scope": "admin",
    }
    token = encode_jwt(payload, secret)

    return {
        "accessToken": token,
        "tokenType": "Bearer",
        "expiresAt": expires_at,
    }


def validate_admin_authorization(authorization: str | None) -> None:
    secret = jwt_secret()
    if not secret or not admin_password():
        raise AuthConfigError("FERLUNA_ADMIN_PASSWORD and FERLUNA_JWT_SECRET must be configured")

    if not authorization or not authorization.startswith("Bearer "):
        raise TokenValidationError("Valid admin bearer token required")

    payload = decode_jwt(authorization.removeprefix("Bearer ").strip(), secret)
    if payload.get("sub") != "ferluna-admin" or payload.get("scope") != "admin":
        raise TokenValidationError("Invalid admin token claims")


def encode_jwt(payload: dict[str, Any], secret: str) -> str:
    header = {"alg": JWT_ALGORITHM, "typ": "JWT"}
    signing_input = ".".join(
        [
            base64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8")),
            base64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8")),
        ]
    )
    signature = sign(signing_input, secret)
    return f"{signing_input}.{signature}"


def decode_jwt(token: str, secret: str) -> dict[str, Any]:
    parts = token.split(".")
    if len(parts) != 3:
        raise TokenValidationError("Invalid token format")

    signing_input = ".".join(parts[:2])
    expected_signature = sign(signing_input, secret)
    if not hmac.compare_digest(parts[2], expected_signature):
        raise TokenValidationError("Invalid token signature")

    try:
        header = json.loads(base64url_decode(parts[0]))
        payload = json.loads(base64url_decode(parts[1]))
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as exc:
        raise TokenValidationError("Invalid token payload") from exc

    if header.get("alg") != JWT_ALGORITHM or header.get("typ") != "JWT":
        raise TokenValidationError("Unsupported token header")

    expires_at = payload.get("exp")
    if not isinstance(expires_at, int) or int(time.time()) >= expires_at:
        raise TokenValidationError("Admin token has expired")

    return payload


def sign(value: str, secret: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), value.encode("utf-8"), hashlib.sha256).digest()
    return base64url_encode(digest)


def base64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def base64url_decode(value: str) -> str:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(f"{value}{padding}".encode("ascii")).decode("utf-8")
