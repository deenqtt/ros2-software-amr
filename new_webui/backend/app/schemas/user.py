"""Request and response models for sign-in, accounts and the audit trail."""

from __future__ import annotations

import re
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.security import PASSWORD_MAX, PASSWORD_MIN

Role = Literal["viewer", "operator", "admin", "super_admin"]

USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9._-]{3,32}$")
DISPLAY_NAME_MAX = 64

Password = Annotated[str, Field(min_length=PASSWORD_MIN, max_length=PASSWORD_MAX)]


def _validate_username(value: str) -> str:
    username = value.strip()
    if not USERNAME_PATTERN.match(username):
        raise ValueError("Use 3 to 32 letters, digits, dots, dashes or underscores, with no spaces")
    return username


def _clean_display_name(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


class LoginIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Not validated against the username rules: a sign-in with a malformed name
    # is a failed sign-in, and saying why would tell a guesser which names exist.
    username: Annotated[str, Field(min_length=1, max_length=64)]
    password: Annotated[str, Field(min_length=1, max_length=PASSWORD_MAX)]


class MeOut(BaseModel):
    id: str
    username: str
    display_name: str | None
    role: Role
    #: So the UI can warn before the session runs out rather than after.
    session_idle_minutes: int
    #: Signed in with a password someone else chose: the UI shows only the
    #: "set a new password" screen until it is replaced.
    must_change_password: bool = False


class PasswordChangeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_password: Annotated[str, Field(min_length=1, max_length=PASSWORD_MAX)]
    new_password: Password


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    username: str
    display_name: str | None
    role: Role
    disabled: bool
    #: Still on a password someone else set (new account, or reset).
    must_change_password: bool = False
    created_at: str
    updated_at: str
    last_login_at: str | None


class UserCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str
    display_name: Annotated[str | None, Field(max_length=DISPLAY_NAME_MAX)] = None
    role: Role
    password: Password

    @field_validator("username")
    @classmethod
    def _username(cls, value: str) -> str:
        return _validate_username(value)

    @field_validator("display_name")
    @classmethod
    def _display(cls, value: str | None) -> str | None:
        return _clean_display_name(value)


class UserPatch(BaseModel):
    """Omitted means unchanged. ``password`` set here is an admin reset."""

    model_config = ConfigDict(extra="forbid")

    display_name: Annotated[str | None, Field(max_length=DISPLAY_NAME_MAX)] = None
    role: Role | None = None
    disabled: bool | None = None
    password: Password | None = None

    @field_validator("display_name")
    @classmethod
    def _display(cls, value: str | None) -> str | None:
        return _clean_display_name(value)


class AuditEntryOut(BaseModel):
    id: int
    at: str
    user_id: str | None
    username: str | None
    role: str | None
    action: str
    method: str | None
    path: str | None
    status: int | None
    detail: str | None
    ip: str | None


class AuditPageOut(BaseModel):
    items: list[AuditEntryOut]
    #: Matching records up to ``upto_id``, for "41 to 60 of 1,284".
    total: int
    #: The newest record this reading covers. Send it back with the next page
    #: so pages do not shift as new records arrive.
    upto_id: int
