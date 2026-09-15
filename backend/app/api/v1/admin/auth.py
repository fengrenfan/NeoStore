from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import select

from app.core.deps import SessionDep
from app.core.domain_errors import UnauthorizedError
from app.core.security import AdminDep, create_access_token, verify_password
from app.domain.admin.models import AdminUser

router = APIRouter(prefix="/auth", tags=["admin: auth"])


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class AdminProfile(BaseModel):
    email: str
    role: str


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, session: SessionDep) -> TokenResponse:
    stmt = select(AdminUser).where(AdminUser.email == payload.email)
    user = (await session.execute(stmt)).scalar_one_or_none()
    if (
        user is None
        or not user.is_active
        or not verify_password(payload.password, user.password_hash)
    ):
        raise UnauthorizedError(
            message="invalid credentials", code="INVALID_CREDENTIALS"
        )
    return TokenResponse(access_token=create_access_token(user.email, user.role))


@router.get("/me", response_model=AdminProfile)
async def me(user: AdminDep) -> AdminProfile:
    return AdminProfile(email=user.email, role=user.role)
