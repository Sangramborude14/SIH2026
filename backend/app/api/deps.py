from typing import AsyncGenerator, Optional, List, Callable
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db, AsyncSessionLocal
from backend.app.core.security import decode_access_token
from backend.app.models.user import User
from backend.app.core.redis import rate_limiter
from backend.app.core.config import settings
from backend.app.core.logging import logger

security_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    Dependency that extracts, decodes, and validates a JWT Bearer token,
    and returns the active User from the database.
    """
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    payload = decode_access_token(token)
    user_id = payload.get("sub")

    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalars().first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User belonging to this token no longer exists.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive or disabled.",
        )

    return user


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    db: AsyncSession = Depends(get_db)
) -> Optional[User]:
    """
    Optional authentication dependency for endpoints that accept both
    anonymous and authenticated callers (e.g. SOS distress dispatch).
    """
    if not credentials or not credentials.credentials:
        return None
    try:
        payload = decode_access_token(credentials.credentials)
        user_id = payload.get("sub")
        stmt = select(User).where(User.id == user_id)
        result = await db.execute(stmt)
        user = result.scalars().first()
        if user and user.is_active:
            return user
    except Exception:
        return None
    return None


def require_role(allowed_roles: List[str]) -> Callable:
    """
    Role-Based Access Control (RBAC) dependency factory.
    Enforces that the authenticated user possesses one of the allowed roles.
    """
    allowed_roles_upper = [r.upper() for r in allowed_roles]

    async def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role.upper() not in allowed_roles_upper:
            logger.warning(
                f"Access denied: User {current_user.id} ({current_user.role}) "
                f"attempted action requiring {allowed_roles_upper}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Operation not permitted. Required role: {', '.join(allowed_roles_upper)}",
            )
        return current_user

    return role_checker


def check_rate_limit(action: str, max_requests: int = 60, window_seconds: int = 60) -> Callable:
    """
    Rate limiting dependency using Redis/in-memory sliding window counters.
    Identifies clients by IP address or user ID if authenticated.
    """
    async def limiter(request: Request) -> None:
        if not settings.RATE_LIMIT_ENABLED:
            return

        # Client IP extraction respecting reverse proxies
        forwarded_for = request.headers.get("X-Forwarded-For")
        client_ip = forwarded_for.split(",")[0].strip() if forwarded_for else (request.client.host if request.client else "unknown")
        
        identifier = f"{client_ip}"

        allowed, count, retry_after = await rate_limiter.check_rate_limit(
            identifier=identifier,
            action=action,
            max_requests=max_requests,
            window_seconds=window_seconds,
        )

        if not allowed:
            logger.warning(f"Rate limit exceeded for action='{action}' by ip='{client_ip}' (count={count})")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Please retry after {retry_after} seconds.",
                headers={"Retry-After": str(retry_after)},
            )

    return limiter


__all__ = [
    "get_db",
    "AsyncSession",
    "get_current_user",
    "get_current_user_optional",
    "require_role",
    "check_rate_limit",
]
