from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.deps import get_db, get_current_user, check_rate_limit
from backend.app.core.config import settings
from backend.app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    generate_refresh_token,
    hash_token,
)
from backend.app.models.user import User, RefreshToken
from backend.app.schemas.auth import (
    UserCreate,
    UserLogin,
    UserResponse,
    TokenResponse,
    TokenRefreshResponse,
)
from backend.app.core.logging import logger

router = APIRouter()


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(check_rate_limit("auth:register", max_requests=10, window_seconds=60))]
)
async def register_user(
    user_in: UserCreate,
    response: Response,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Registers a new user account.
    Default role is CITIZEN. Elevated roles (FIELD_RESPONDER, EXPERT, ADMIN)
    require presenting the configured ADMIN_BOOTSTRAP_TOKEN.
    Issues a short-lived access token and sets an httpOnly secure refresh cookie.
    """
    # 1. Check if email already registered
    existing_stmt = select(User).where(User.email == user_in.email.lower().strip())
    existing = (await db.execute(existing_stmt)).scalars().first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists."
        )

    # 2. Validate role privileges
    requested_role = (user_in.role or "CITIZEN").upper()
    valid_roles = ["CITIZEN", "FIELD_RESPONDER", "EXPERT", "ADMIN"]
    if requested_role not in valid_roles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role. Allowed roles: {', '.join(valid_roles)}"
        )

    if requested_role in ["EXPERT", "ADMIN", "FIELD_RESPONDER"]:
        if not user_in.admin_bootstrap_token or user_in.admin_bootstrap_token != settings.ADMIN_BOOTSTRAP_TOKEN:
            logger.warning(f"Unauthorized attempt to register elevated role '{requested_role}' for {user_in.email}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Administrative bootstrap token required to register elevated roles."
            )

    # 3. Create User
    new_user = User(
        email=user_in.email.lower().strip(),
        hashed_password=hash_password(user_in.password),
        full_name=user_in.full_name.strip(),
        phone_number=user_in.phone_number.strip() if user_in.phone_number else None,
        role=requested_role,
        is_active=True,
    )
    db.add(new_user)
    await db.flush()

    # 4. Generate Tokens
    access_token = create_access_token(user_id=new_user.id, role=new_user.role)
    raw_refresh = generate_refresh_token()
    now = datetime.now(timezone.utc)
    refresh_expires = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    refresh_record = RefreshToken(
        user_id=new_user.id,
        token_hash=hash_token(raw_refresh),
        expires_at=refresh_expires,
        user_agent=request.headers.get("User-Agent", "")[:255],
        ip_address=request.client.host if request.client else None,
    )
    db.add(refresh_record)
    await db.commit()

    # 5. Set httpOnly refresh cookie
    response.set_cookie(
        key=settings.REFRESH_COOKIE_NAME,
        value=raw_refresh,
        httponly=True,
        secure=settings.REFRESH_COOKIE_SECURE,
        samesite=settings.REFRESH_COOKIE_SAMESITE,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        path="/api/v1/auth",
    )

    logger.info(f"User registered successfully: {new_user.id} ({new_user.role})")
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserResponse.model_validate(new_user),
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    dependencies=[Depends(check_rate_limit("auth:login", max_requests=10, window_seconds=60))]
)
async def login_user(
    login_in: UserLogin,
    response: Response,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Authenticates user credentials.
    Rate limited against brute-force attacks.
    Issues JWT access token and sets an httpOnly refresh token cookie.
    """
    stmt = select(User).where(User.email == login_in.email.lower().strip())
    user = (await db.execute(stmt)).scalars().first()

    if not user or not verify_password(login_in.password, user.hashed_password):
        client_ip = request.client.host if request.client else "unknown"
        logger.warning(f"Failed login attempt for email '{login_in.email}' from IP {client_ip}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is suspended or inactive."
        )

    # Issue tokens
    access_token = create_access_token(user_id=user.id, role=user.role)
    raw_refresh = generate_refresh_token()
    now = datetime.now(timezone.utc)
    refresh_expires = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    refresh_record = RefreshToken(
        user_id=user.id,
        token_hash=hash_token(raw_refresh),
        expires_at=refresh_expires,
        user_agent=request.headers.get("User-Agent", "")[:255],
        ip_address=request.client.host if request.client else None,
    )
    db.add(refresh_record)
    await db.commit()

    # Set httpOnly cookie
    response.set_cookie(
        key=settings.REFRESH_COOKIE_NAME,
        value=raw_refresh,
        httponly=True,
        secure=settings.REFRESH_COOKIE_SECURE,
        samesite=settings.REFRESH_COOKIE_SAMESITE,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        path="/api/v1/auth",
    )

    logger.info(f"User logged in: {user.id} ({user.role})")
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserResponse.model_validate(user),
    )


@router.post("/refresh", response_model=TokenRefreshResponse)
async def refresh_access_token(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db)
):
    """
    Validates the httpOnly refresh token cookie, rotates the refresh token
    (single-use token rotation), and returns a fresh short-lived access token.
    """
    raw_token = request.cookies.get(settings.REFRESH_COOKIE_NAME)
    if not raw_token:
        # Fallback to custom header for non-browser clients / mobile apps
        raw_token = request.headers.get("X-Refresh-Token")

    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token not found. Please log in again.",
        )

    t_hash = hash_token(raw_token)
    stmt = select(RefreshToken).where(RefreshToken.token_hash == t_hash)
    token_record = (await db.execute(stmt)).scalars().first()

    now = datetime.now(timezone.utc)

    if not token_record:
        logger.warning(f"Refresh attempt with unknown token hash: {t_hash[:12]}...")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token.",
        )

    # Check revocation / reuse
    if token_record.revoked_at is not None:
        logger.error(
            f"SECURITY ALERT: Revoked refresh token reuse detected for user {token_record.user_id}! "
            "Possible token theft. Invalidating all user refresh sessions."
        )
        # Security precaution: Revoke all refresh tokens for this user on token reuse detection
        await db.execute(
            RefreshToken.__table__.update()
            .where(RefreshToken.user_id == token_record.user_id)
            .values(revoked_at=now)
        )
        await db.commit()
        response.delete_cookie(settings.REFRESH_COOKIE_NAME, path="/api/v1/auth")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Compromised session detected. Please log in again.",
        )

    # Check expiration
    expires_at = token_record.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if expires_at < now:
        token_record.revoked_at = now
        await db.commit()
        response.delete_cookie(settings.REFRESH_COOKIE_NAME, path="/api/v1/auth")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token expired. Please log in again.",
        )

    # Token rotation: Invalidate old token
    token_record.revoked_at = now

    # Retrieve user
    user_stmt = select(User).where(User.id == token_record.user_id)
    user = (await db.execute(user_stmt)).scalars().first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is no longer active.",
        )

    # Issue new refresh token
    new_raw_refresh = generate_refresh_token()
    new_refresh_record = RefreshToken(
        user_id=user.id,
        token_hash=hash_token(new_raw_refresh),
        expires_at=now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        user_agent=request.headers.get("User-Agent", "")[:255],
        ip_address=request.client.host if request.client else None,
    )
    db.add(new_refresh_record)

    # Issue new access token
    new_access_token = create_access_token(user_id=user.id, role=user.role)
    await db.commit()

    # Set rotated cookie
    response.set_cookie(
        key=settings.REFRESH_COOKIE_NAME,
        value=new_raw_refresh,
        httponly=True,
        secure=settings.REFRESH_COOKIE_SECURE,
        samesite=settings.REFRESH_COOKIE_SAMESITE,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        path="/api/v1/auth",
    )

    return TokenRefreshResponse(
        access_token=new_access_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/logout")
async def logout_user(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db)
):
    """
    Logs out the current session by revoking the refresh token and clearing cookies.
    """
    raw_token = request.cookies.get(settings.REFRESH_COOKIE_NAME)
    if not raw_token:
        raw_token = request.headers.get("X-Refresh-Token")

    if raw_token:
        t_hash = hash_token(raw_token)
        stmt = select(RefreshToken).where(RefreshToken.token_hash == t_hash)
        record = (await db.execute(stmt)).scalars().first()
        if record and record.revoked_at is None:
            record.revoked_at = datetime.now(timezone.utc)
            await db.commit()

    response.delete_cookie(key=settings.REFRESH_COOKIE_NAME, path="/api/v1/auth")
    return {"status": "success", "message": "Successfully logged out."}


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
    current_user: User = Depends(get_current_user)
):
    """
    Returns authenticated user profile and active permissions role.
    """
    return UserResponse.model_validate(current_user)
