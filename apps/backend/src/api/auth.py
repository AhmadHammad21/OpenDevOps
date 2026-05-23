"""JWT helpers and FastAPI auth dependencies."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated

import bcrypt as _bcrypt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from config import settings

_bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return _bcrypt.hashpw(password.encode(), _bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return _bcrypt.checkpw(plain.encode(), hashed.encode())


def create_access_token(user_id: str, role: str) -> str:
    from jose import jwt

    exp = datetime.now(UTC) + timedelta(minutes=settings.jwt_expire_minutes)
    return jwt.encode(
        {"sub": user_id, "role": role, "exp": exp},
        settings.jwt_secret,
        algorithm="HS256",
    )


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> dict | None:
    """Return {id, role} when auth is enabled + token is valid; None in dev mode."""
    if not settings.jwt_secret:
        return None
    token = credentials.credentials if credentials else None
    if token is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        from jose import jwt

        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        user_id: str | None = payload.get("sub")
        role: str = payload.get("role", "user")
        if not user_id:
            raise ValueError("missing sub")
        return {"id": user_id, "role": role}
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")


async def require_admin(
    user: Annotated[dict | None, Depends(get_current_user)],
) -> dict | None:
    if user is not None and user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user
