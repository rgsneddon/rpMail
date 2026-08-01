"""Unified mailbox + PIM store (Mail · Calendar · Contacts · Tasks)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from .calendar import CalendarStore
from .contacts import ContactBook
from .folders import ensure_default_set, normalize_folder
from .models import MailAccount, MailMessage
from .roles import Actor, require_company_mailbox_creator
from .tasks import TaskList


@dataclass
class MailboxStore:
    accounts: list[MailAccount] = field(default_factory=list)
    messages: list[MailMessage] = field(default_factory=list)
    folders: list[str] = field(default_factory=lambda: ensure_default_set())
    calendar: CalendarStore = field(default_factory=CalendarStore)
    contacts: ContactBook = field(default_factory=ContactBook)
    tasks: TaskList = field(default_factory=TaskList)

    def add_account(self, account: MailAccount, *, actor: Actor) -> MailAccount:
        if account.kind == "company":
            require_company_mailbox_creator(actor)
        self.accounts.append(account)
        return account

    def add_message(self, message: MailMessage) -> MailMessage:
        message.folder = normalize_folder(message.folder)
        if message.folder not in self.folders:
            self.folders.append(message.folder)
        self.messages.append(message)
        return message

    def import_batch(self, msgs: list[MailMessage]) -> int:
        for m in msgs:
            self.add_message(m)
        return len(msgs)

    def messages_in(self, folder: str) -> list[MailMessage]:
        f = normalize_folder(folder)
        return [m for m in self.messages if m.folder == f]

    def draft_reply(self, original: MailMessage, body: str = "") -> MailMessage:
        return MailMessage(
            subject=f"Re: {original.subject}" if not original.subject.lower().startswith("re:") else original.subject,
            from_addr="",
            to_addrs=[original.from_addr] if original.from_addr else [],
            body=body,
            folder="Drafts",
        )

    def draft_forward(self, original: MailMessage, body: str = "") -> MailMessage:
        return MailMessage(
            subject=f"Fwd: {original.subject}",
            from_addr="",
            to_addrs=[],
            body=(body + "\n\n----- Forwarded -----\n" + original.body).strip(),
            folder="Drafts",
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "accounts": [a.to_dict() for a in self.accounts],
            "messages": [m.to_dict() for m in self.messages],
            "folders": list(self.folders),
            "calendar": json.loads(self.calendar.dumps()),
            "contacts": json.loads(self.contacts.dumps()),
            "tasks": json.loads(self.tasks.dumps()),
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
        store.folders = ensure_default_set(list(data.get("folders") or []))
        if data.get("calendar"):
            store.calendar = CalendarStore.loads(json.dumps(data["calendar"]))
        if data.get("contacts"):
            store.contacts = ContactBook.loads(json.dumps(data["contacts"]))
        if data.get("tasks"):
            store.tasks = TaskList.loads(json.dumps(data["tasks"]))
        return store
