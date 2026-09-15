"""Admin authentication: password hashing, JWT issuing and the auth dependency."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

import bcrypt
from fastapi import Depends, Request
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.domain_errors import UnauthorizedError
from app.db.session import get_session
from app.domain.admin.models import AdminUser


def hash_password(raw: str) -> str:
    return bcrypt.hashpw(raw.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(raw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(raw.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def create_access_token(subject: str, role: str = "owner") -> str:
    issued = datetime.now(UTC)
    expires = issued + timedelta(minutes=settings.access_token_ttl_minutes)
    payload = {
        "sub": subject,
        "role": role,
        "iat": int(issued.timestamp()),
        "exp": int(expires.timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise UnauthorizedError(message="invalid or expired token") from exc


async def get_admin_user(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AdminUser:
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise UnauthorizedError(message="missing bearer token")

    payload = decode_token(token)
    subject = payload.get("sub")
    if not subject:
        raise UnauthorizedError(message="token has no subject")

    stmt = select(AdminUser).where(AdminUser.email == subject)
    user = (await session.execute(stmt)).scalar_one_or_none()
    if user is None or not user.is_active:
        raise UnauthorizedError(message="account is not active")
    return user


AdminDep = Annotated[AdminUser, Depends(get_admin_user)]
