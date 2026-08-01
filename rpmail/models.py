"""Domain models for accounts and messages (pure, serializable)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any
import time
import uuid


@dataclass
class MailAccount:
    """One mailbox account (personal or company)."""

    address: str
    display_name: str = ""
    kind: str = "personal"  # personal | company
    protocol_prefs: dict[str, Any] = field(default_factory=dict)
    account_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MailAccount":
        return cls(
            address=str(data["address"]),
            display_name=str(data.get("display_name") or ""),
            kind=str(data.get("kind") or "personal"),
            protocol_prefs=dict(data.get("protocol_prefs") or {}),
            account_id=str(data.get("account_id") or uuid.uuid4().hex[:12]),
        )


@dataclass
class MailMessage:
    """One message (import or compose)."""

    subject: str
    from_addr: str
    to_addrs: list[str]
    body: str = ""
    folder: str = "INBOX"
    message_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    created_unix: int = field(default_factory=lambda: int(time.time()))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MailMessage":
        return cls(
            subject=str(data.get("subject") or ""),
            from_addr=str(data.get("from_addr") or ""),
            to_addrs=list(data.get("to_addrs") or []),
            body=str(data.get("body") or ""),
            folder=str(data.get("folder") or "INBOX"),
            message_id=str(data.get("message_id") or uuid.uuid4().hex),
            created_unix=int(data.get("created_unix") or 0),
        )
