"""User management — admin only."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from agent.db import db
from api.auth import hash_password, require_admin
from models.users import UserCreate, UserOut, UserUpdate

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("", response_model=list[UserOut])
async def list_users(
    _: Annotated[dict | None, Depends(require_admin)],
) -> list[UserOut]:
    return await db.list_users()


@router.post("", response_model=UserOut, status_code=201)
async def create_user(
    req: UserCreate,
    _: Annotated[dict | None, Depends(require_admin)],
) -> UserOut:
    if await db.get_user_by_email(req.email):
        raise HTTPException(status_code=400, detail="Email already registered")
    user = await db.create_user(req.email, req.name, hash_password(req.password), req.role)
    if not user:
        raise HTTPException(status_code=500, detail="Failed to create user")
    return user


@router.patch("/{user_id}", response_model=UserOut)
async def update_user(
    user_id: str,
    req: UserUpdate,
    _: Annotated[dict | None, Depends(require_admin)],
) -> UserOut:
    updates: dict = {}
    if req.name is not None:
        updates["name"] = req.name
    if req.role is not None:
        updates["role"] = req.role
    if req.password is not None:
        updates["password_hash"] = hash_password(req.password)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    user = await db.update_user(user_id, **updates)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.delete("/{user_id}", status_code=204)
async def delete_user(
    user_id: str,
    current_user: Annotated[dict | None, Depends(require_admin)],
) -> None:
    if current_user and current_user["id"] == user_id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    await db.delete_user(user_id)
