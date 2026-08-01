"""In-process mailbox store with JSON serialize round-trip."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from .models import MailAccount, MailMessage
from .roles import Actor, require_company_mailbox_creator


@dataclass
class MailboxStore:
    accounts: list[MailAccount] = field(default_factory=list)
    messages: list[MailMessage] = field(default_factory=list)

    def add_account(self, account: MailAccount, *, actor: Actor) -> MailAccount:
        if account.kind == "company":
            require_company_mailbox_creator(actor)
        self.accounts.append(account)
        return account

    def add_message(self, message: MailMessage) -> MailMessage:
        self.messages.append(message)
        return message

    def import_batch(self, msgs: list[MailMessage]) -> int:
        self.messages.extend(msgs)
        return len(msgs)

    def to_dict(self) -> dict[str, Any]:
        return {
            "accounts": [a.to_dict() for a in self.accounts],
            "messages": [m.to_dict() for m in self.messages],
        }

    def dumps(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)

    @classmethod
    def loads(cls, raw: str) -> "MailboxStore":
        data = json.loads(raw)
        store = cls()
        for a in data.get("accounts") or []:
            store.accounts.append(MailAccount.from_dict(a))
        for m in data.get("messages") or []:
            store.messages.append(MailMessage.from_dict(m))
        return store
