"""SMTP / IMAP / POP3 import interfaces with in-memory fakes (no live network)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from .models import MailMessage


class MailImporter(Protocol):
    def import_messages(self, limit: int = 50) -> list[MailMessage]:
        ...


class MailSender(Protocol):
    def send(self, message: MailMessage) -> str:
        """Return provider message-id or local id."""
        ...


@dataclass
class InMemorySmtpSender:
    """Fake SMTP send — records outbound messages."""

    sent: list[MailMessage] = field(default_factory=list)

    def send(self, message: MailMessage) -> str:
        self.sent.append(message)
        return message.message_id


@dataclass
class InMemoryImapImporter:
    """Fake IMAP import source."""

    mailbox: list[MailMessage] = field(default_factory=list)

    def import_messages(self, limit: int = 50) -> list[MailMessage]:
        return list(self.mailbox[: max(0, int(limit))])


@dataclass
class InMemoryPop3Importer:
    """Fake POP3 import source."""

    mailbox: list[MailMessage] = field(default_factory=list)

    def import_messages(self, limit: int = 50) -> list[MailMessage]:
        return list(self.mailbox[: max(0, int(limit))])


PROTOCOL_CAPABILITIES = {
    "smtp": {"send": True, "import": False},
    "imap": {"send": False, "import": True},
    "pop3": {"send": False, "import": True},
}
