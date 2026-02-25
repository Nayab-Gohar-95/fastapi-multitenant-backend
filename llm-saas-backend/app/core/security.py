"""
core/security.py
----------------
Password hashing and JWT token utilities.

Design decisions:
  - bcrypt work factor 12 (good balance of security vs latency)
  - JWT payload contains sub (user_id), tenant_id, and role for
    zero-DB-round-trip auth checks in most endpoints.
  - Tokens are signed with HS256; swap to RS256 for multi-service setups.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

# bcrypt context — rounds=12 is OWASP recommended minimum
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)


# ── Password Utilities ────────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    """Return a bcrypt hash of the plain-text password."""
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Constant-time comparison of plain password against stored hash."""
    return pwd_context.verify(plain, hashed)


# ── JWT Utilities ─────────────────────────────────────────────────────────────

def create_access_token(
    subject: str,
    tenant_id: str,
    role: str,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Mint a JWT access token.

    Args:
        subject: User UUID (stored in 'sub' claim).
        tenant_id: Tenant UUID — embedded so middleware can filter without DB.
        role: 'admin' | 'user'
        expires_delta: Optional custom expiry; defaults to settings value.

    Returns:
        Signed JWT string.
    """
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload: Dict[str, Any] = {
        "sub": subject,
        "tenant_id": tenant_id,
        "role": role,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> Dict[str, Any]:
    """
    Decode and validate a JWT access token.

    Raises:
        JWTError: If the token is invalid, expired, or tampered with.

    Returns:
        Raw payload dict.
    """
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
