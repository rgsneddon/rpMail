"""Role gates — company mailbox creation is moderator-only."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Role = Literal["user", "staff", "moderator", "admin"]

ROLE_ORDER = ("user", "staff", "moderator", "admin")


@dataclass(frozen=True)
class Actor:
    user_id: str
    role: Role
    display_name: str = ""


class PermissionDenied(PermissionError):
    """Raised when a role gate blocks an action."""


def role_at_least(role: Role, minimum: Role) -> bool:
    return ROLE_ORDER.index(role) >= ROLE_ORDER.index(minimum)


def can_create_company_mailbox(actor: Actor) -> bool:
    """Company emails may be created by moderator (or admin) only."""
    return role_at_least(actor.role, "moderator")


def require_company_mailbox_creator(actor: Actor) -> None:
    if not can_create_company_mailbox(actor):
        raise PermissionDenied(
            f"company mailbox creation requires role moderator+; got {actor.role!r}"
        )
