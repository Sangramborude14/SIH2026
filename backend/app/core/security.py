import hmac
import hashlib
import secrets
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
import jwt
from fastapi import HTTPException, status
from backend.app.core.config import settings
from backend.app.core.logging import logger

PBKDF2_ITERATIONS = 600000
ALGORITHM = settings.JWT_ALGORITHM


def hash_password(password: str) -> str:
    """
    Hashes a password using PBKDF2-HMAC-SHA256 with 600,000 iterations (OWASP standard)
    and a cryptographically secure 16-byte random salt.
    Format: pbkdf2_sha256$<iterations>$<salt_hex>$<hash_hex>
    """
    if not password:
        raise ValueError("Password cannot be empty.")
    salt = secrets.token_bytes(16)
    key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PBKDF2_ITERATIONS,
    )
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt.hex()}${key.hex()}"


get_password_hash = hash_password


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifies a plain password against a stored PBKDF2-HMAC-SHA256 hash using
    constant-time comparison to prevent timing attacks.
    """
    if not plain_password or not hashed_password:
        return False
    try:
        parts = hashed_password.split("$")
        if len(parts) != 4 or parts[0] != "pbkdf2_sha256":
            return False
        iterations = int(parts[1])
        salt = bytes.fromhex(parts[2])
        expected_key = bytes.fromhex(parts[3])

        computed_key = hashlib.pbkdf2_hmac(
            "sha256",
            plain_password.encode("utf-8"),
            salt,
            iterations,
        )
        return hmac.compare_digest(computed_key, expected_key)
    except Exception as e:
        logger.warning(f"Password verification encountered error: {e}")
        return False


def hash_token(token: str) -> str:
    """Returns SHA-256 hex digest of a token string for safe database lookup."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def generate_refresh_token() -> str:
    """Generates a cryptographically strong, unguessable 256-bit random token string."""
    return secrets.token_urlsafe(48)


def create_access_token(
    user_id: str,
    role: str,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Creates a compact, signed JWT access token.
    Claims strictly limited to: sub, role, iat, exp, jti, type.
    Zero sensitive profile information is included in the payload.
    """
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    
    payload = {
        "sub": str(user_id),
        "role": str(role).upper(),
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "jti": str(uuid.uuid4()),
        "type": "access",
    }

    token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=ALGORITHM)
    return token


def decode_access_token(token: str) -> Dict[str, Any]:
    """
    Decodes and validates a JWT access token.
    Enforces signature verification, expiration, token type, and guards against algorithm confusion.
    """
    try:
        # Check unverified header to reject algorithm substitution / confusion attacks
        header = jwt.get_unverified_header(token)
        if header.get("alg") != ALGORITHM:
            logger.warning(f"Rejected token with unauthorized algorithm: {header.get('alg')}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token algorithm header.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[ALGORITHM],
            options={"require": ["sub", "role", "exp", "iat", "jti"]},
        )

        if payload.get("type") != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return payload

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired. Please refresh your session.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except (jwt.InvalidTokenError, Exception) as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )
