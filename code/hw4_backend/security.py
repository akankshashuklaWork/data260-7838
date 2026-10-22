import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from typing import Any

JWT_ALGORITHM = "HS256"
JWT_TTL_SECONDS = 30 * 60


class TokenError(ValueError):
    """Raised when a bearer token cannot be authenticated."""


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 240_000)
    return f"pbkdf2_sha256$240000${salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, rounds, salt_hex, digest_hex = encoded.split("$")
        if algorithm != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode(),
            bytes.fromhex(salt_hex),
            int(rounds),
        )
        return hmac.compare_digest(digest.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


def _b64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _b64url_decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _jwt_secret() -> bytes:
    # A local development fallback keeps the repository runnable.  Deployments
    # must supply JWT_SECRET_KEY rather than committing a real secret.
    return os.getenv("JWT_SECRET_KEY", "local-hw7-development-secret").encode("utf-8")


def create_access_token(
    user_id: int, username: str, role: str, *, ttl_seconds: int = JWT_TTL_SECONDS
) -> str:
    """Create a minimal signed HS256 access token without storing a session."""
    now = int(time.time())
    header = _b64url_encode(
        json.dumps({"alg": JWT_ALGORITHM, "typ": "JWT"}, separators=(",", ":")).encode()
    )
    payload = _b64url_encode(
        json.dumps(
            {
                "sub": str(user_id),
                "username": username,
                "role": role,
                "iat": now,
                "exp": now + ttl_seconds,
            },
            separators=(",", ":"),
        ).encode()
    )
    signature = _b64url_encode(
        hmac.new(_jwt_secret(), f"{header}.{payload}".encode(), hashlib.sha256).digest()
    )
    return f"{header}.{payload}.{signature}"


def decode_access_token(token: str) -> dict[str, Any]:
    """Verify a JWT signature, required claims, and expiration time."""
    try:
        header_part, payload_part, signature_part = token.split(".")
        header = json.loads(_b64url_decode(header_part))
        claims = json.loads(_b64url_decode(payload_part))
        expected = hmac.new(
            _jwt_secret(), f"{header_part}.{payload_part}".encode(), hashlib.sha256
        ).digest()
        actual = _b64url_decode(signature_part)
        if header.get("alg") != JWT_ALGORITHM or not hmac.compare_digest(expected, actual):
            raise TokenError("invalid token signature")
        if not isinstance(claims.get("sub"), str) or claims.get("role") not in {
            "reader",
            "writer",
            "moderator",
        }:
            raise TokenError("missing required token claims")
        if not isinstance(claims.get("exp"), int) or claims["exp"] <= int(time.time()):
            raise TokenError("token has expired")
        return claims
    except (ValueError, KeyError, TypeError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        if isinstance(exc, TokenError):
            raise
        raise TokenError("malformed bearer token") from exc
