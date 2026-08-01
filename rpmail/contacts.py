"""Contacts (People) pillar — create + lookup."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Contact:
    display_name: str
    email: str
    phone: str = ""
    company: str = ""
    contact_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Contact":
        return cls(
            display_name=str(data.get("display_name") or ""),
            email=str(data.get("email") or "").lower(),
            phone=str(data.get("phone") or ""),
            company=str(data.get("company") or ""),
            contact_id=str(data.get("contact_id") or uuid.uuid4().hex[:12]),
        )


@dataclass
class ContactBook:
    contacts: list[Contact] = field(default_factory=list)

    def add(self, display_name: str, email: str, **kwargs: Any) -> Contact:
        c = Contact(display_name=display_name, email=email.lower().strip(), **kwargs)
        if not c.email:
            raise ValueError("email required")
        self.contacts.append(c)
        return c

    def lookup_by_email(self, email: str) -> Contact | None:
        key = (email or "").lower().strip()
        for c in self.contacts:
            if c.email == key:
                return c
        return None

    def lookup_by_name(self, name: str) -> list[Contact]:
        q = (name or "").lower().strip()
        if not q:
            return []
        return [c for c in self.contacts if q in c.display_name.lower()]

    def dumps(self) -> str:
        return json.dumps(
            {"contacts": [c.to_dict() for c in self.contacts]},
            indent=2,
            sort_keys=True,
        )

    @classmethod
    def loads(cls, raw: str) -> "ContactBook":
        data = json.loads(raw)
        book = cls()
        for c in data.get("contacts") or []:
            book.contacts.append(Contact.from_dict(c))
        return book
