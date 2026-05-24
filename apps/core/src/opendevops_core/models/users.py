from datetime import datetime

from pydantic import BaseModel, EmailStr, field_validator


class UserOut(BaseModel):
    id: str
    email: str
    name: str
    role: str
    created_at: datetime


class UserCreate(BaseModel):
    email: EmailStr
    name: str
    password: str
    role: str = "user"

    @field_validator("role")
    @classmethod
    def _valid_role(cls, v: str) -> str:
        if v not in ("admin", "user"):
            raise ValueError("role must be 'admin' or 'user'")
        return v


class UserUpdate(BaseModel):
    name: str | None = None
    role: str | None = None
    password: str | None = None

    @field_validator("role")
    @classmethod
    def _valid_role(cls, v: str | None) -> str | None:
        if v is not None and v not in ("admin", "user"):
            raise ValueError("role must be 'admin' or 'user'")
        return v
