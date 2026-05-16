"""Auth endpoints: /auth/status, /auth/register, /auth/login, /auth/me."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr

from agent.db import db
from api.auth import create_access_token, get_current_user, hash_password, verify_password
from config import settings

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    email: EmailStr
    name: str
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.get("/status")
async def auth_status() -> dict:
    return {"required": bool(settings.jwt_secret)}


@router.post("/register", response_model=TokenResponse)
async def register(req: RegisterRequest) -> TokenResponse:
    if await db.get_user_by_email(req.email):
        raise HTTPException(status_code=400, detail="Email already registered")
    is_first = (await db.count_users()) == 0
    role = "admin" if is_first else "user"
    org = await db.get_first_org()
    org_id = org["id"] if org else None
    user = await db.create_user(req.email, req.name, hash_password(req.password), role, org_id)
    if not user:
        raise HTTPException(
            status_code=501,
            detail="User management requires CHECKPOINT_BACKEND=postgres",
        )
    return TokenResponse(access_token=create_access_token(str(user["id"]), role))


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest) -> TokenResponse:
    user = await db.get_user_by_email(req.email)
    if not user or not verify_password(req.password, user.get("password_hash") or ""):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return TokenResponse(
        access_token=create_access_token(str(user["id"]), user["role"])
    )


@router.get("/me")
async def me(
    current_user: Annotated[dict | None, Depends(get_current_user)],
) -> dict:
    if current_user is None:
        return {"id": None, "role": "admin", "name": "You", "auth_enabled": False}
    row = await db.get_user_by_id(current_user["id"])
    name = row["name"] if row else ""
    return {**current_user, "name": name, "auth_enabled": True}
