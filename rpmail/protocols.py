"""SMTP / IMAP / POP3 interfaces, in-memory fakes, and protocol capabilities.

Fakes never open the network. Live sockets live in ``rpmail.live``.
"""

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


def _clip(rows: list[MailMessage], limit: int) -> list[MailMessage]:
    return list(rows[: max(0, int(limit))])


@dataclass
class InMemorySmtpSender:
    """Fake SMTP send — records outbound messages."""

    sent: list[MailMessage] = field(default_factory=list)

    def send(self, message: MailMessage) -> str:
        self.sent.append(message)
        return message.message_id


@dataclass
class InMemoryImapImporter:
    """Fake IMAP source with folders, list, and body read."""

    mailbox: list[MailMessage] = field(default_factory=list)

    def import_messages(self, limit: int = 50) -> list[MailMessage]:
        return _clip(self.mailbox, limit)

    def list_folders(self) -> list[str]:
        found: list[str] = []
        for message in self.mailbox:
            if message.folder not in found:
                found.append(message.folder)
        for name in ("INBOX", "Sent", "Drafts", "Archive", "Trash"):
            if name not in found:
                found.append(name)
        return found

    def fetch_messages(self, folder: str = "INBOX", limit: int = 50) -> list[MailMessage]:
        rows = [m for m in self.mailbox if m.folder == folder]
        return _clip(rows, limit)

    def read_message(self, message_id: str, folder: str | None = None) -> MailMessage | None:
        for message in self.mailbox:
            if message.message_id != message_id:
                continue
            if folder is not None and message.folder != folder:
                continue
            return message
        return None


@dataclass
class InMemoryPop3Importer:
    """Fake POP3 source. POP3 exposes INBOX only."""

    mailbox: list[MailMessage] = field(default_factory=list)

    def import_messages(self, limit: int = 50) -> list[MailMessage]:
        return _clip(self._inbox(), limit)

    def list_folders(self) -> list[str]:
        return ["INBOX"]

    def fetch_messages(self, folder: str = "INBOX", limit: int = 50) -> list[MailMessage]:
        if folder != "INBOX":
            return []
        return _clip(self._inbox(), limit)

    def read_message(self, message_id: str, folder: str | None = None) -> MailMessage | None:
        if folder not in (None, "INBOX"):
            return None
        for message in self._inbox():
            if message.message_id == message_id:
                return message
        return None

    def _inbox(self) -> list[MailMessage]:
        return [m for m in self.mailbox if m.folder in ("", "INBOX")]


PROTOCOL_CAPABILITIES = {
    "smtp": {"send": True, "import": False},
    "imap": {"send": False, "import": True, "folders": True},
    "pop3": {"send": False, "import": True, "folders": False},
}
