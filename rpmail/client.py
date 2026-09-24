"""Account configure, folder list, read, and SMTP send.

In-memory fakes are used when they are passed in. Otherwise the client opens
the live IMAP, POP3, or SMTP endpoint stored on the account. Secrets come
from ``CredentialVault`` only.
"""

from __future__ import annotations

import uuid
from dataclasses import replace

from .credentials import CredentialVault
from .live import (
    Endpoint,
    fetch_imap,
    fetch_pop3,
    list_imap_folders,
    send_smtp,
)
from .models import MailAccount
from .models import MailMessage
from .protocols import InMemoryImapImporter, InMemoryPop3Importer, InMemorySmtpSender
from .roles import Actor
from .store import MailboxStore


class MailClient:
    def __init__(
        self,
        store: MailboxStore,
        vault: CredentialVault,
        *,
        imap: InMemoryImapImporter | None = None,
        pop3: InMemoryPop3Importer | None = None,
        smtp: InMemorySmtpSender | None = None,
    ) -> None:
        self.store = store
        self.vault = vault
        self.imap = imap
        self.pop3 = pop3
        self.smtp = smtp

    def configure(
        self,
        *,
        actor: Actor,
        address: str,
        display_name: str = "",
        kind: str = "personal",
        receive: str = "imap",
        imap: Endpoint | None = None,
        imap_secret: str = "",
        pop3: Endpoint | None = None,
        pop3_secret: str = "",
        smtp: Endpoint | None = None,
        smtp_secret: str = "",
        account_id: str = "",
    ) -> MailAccount:
        if receive not in ("imap", "pop3"):
            raise ValueError("receive must be imap or pop3")
        if receive == "imap" and imap is None:
            raise ValueError("imap endpoint required")
        if receive == "pop3" and pop3 is None:
            raise ValueError("pop3 endpoint required")
        prefs: dict = {"receive": receive}
        if imap is not None:
            prefs["imap"] = _public_endpoint(imap)
        if pop3 is not None:
            prefs["pop3"] = _public_endpoint(pop3)
        if smtp is not None:
            prefs["smtp"] = _public_endpoint(smtp)
        account = MailAccount(
            address=address,
            display_name=display_name,
            kind=kind if kind in ("personal", "company") else "personal",
            protocol_prefs=prefs,
            account_id=account_id or uuid.uuid4().hex[:12],
        )
        # Role gate runs before any secret is written.
        self.store.add_account(account, actor=actor)
        self.vault.put(
            account.account_id,
            imap_secret=imap_secret,
            pop3_secret=pop3_secret,
            smtp_secret=smtp_secret,
        )
        return account

    def set_receive(self, account_id: str, protocol: str) -> MailAccount:
        if protocol not in ("imap", "pop3"):
            raise ValueError("receive must be imap or pop3")
        account = self._account(account_id)
        if protocol not in account.protocol_prefs:
            raise ValueError(f"{protocol} is not configured")
        account.protocol_prefs["receive"] = protocol
        return account

    def list_folders(self, account_id: str) -> list[str]:
        account = self._account(account_id)
        receive = str(account.protocol_prefs.get("receive") or "imap")
        if receive == "pop3":
            if self.pop3 is not None:
                return self.pop3.list_folders()
            return ["INBOX"]
        if self.imap is not None:
            return self.imap.list_folders()
        endpoint, secret = self._endpoint(account, "imap")
        return list_imap_folders(endpoint, secret)

    def list_messages(self, account_id: str, folder: str = "INBOX", limit: int = 50) -> list[MailMessage]:
        account = self._account(account_id)
        receive = str(account.protocol_prefs.get("receive") or "imap")
        if receive == "pop3":
            if self.pop3 is not None:
                return self.pop3.fetch_messages("INBOX", limit)
            endpoint, secret = self._endpoint(account, "pop3")
            return fetch_pop3(endpoint, secret, limit=limit)
        if self.imap is not None:
            return self.imap.fetch_messages(folder, limit)
        endpoint, secret = self._endpoint(account, "imap")
        return fetch_imap(endpoint, secret, folder=folder, limit=limit)

    def read_message(
        self,
        account_id: str,
        message_id: str,
        folder: str | None = None,
    ) -> MailMessage:
        account = self._account(account_id)
        receive = str(account.protocol_prefs.get("receive") or "imap")
        if receive == "pop3":
            if self.pop3 is not None:
                found = self.pop3.read_message(message_id, "INBOX")
            else:
                found = _find(self.list_messages(account_id, "INBOX", limit=200), message_id)
            if found is None:
                raise KeyError(message_id)
            return found
        target = folder
        if self.imap is not None:
            found = self.imap.read_message(message_id, target)
            if found is None:
                raise KeyError(message_id)
            return found
        messages = self.list_messages(account_id, folder or "INBOX", limit=200)
        found = _find(messages, message_id)
        if found is None:
            raise KeyError(message_id)
        return found

    def send(self, account_id: str, message: MailMessage) -> str:
        account = self._account(account_id)
        outgoing = message if message.from_addr else replace(message, from_addr=account.address)
        if self.smtp is not None:
            message_id = self.smtp.send(outgoing)
        else:
            if "smtp" not in account.protocol_prefs:
                raise ValueError("smtp is not configured")
            endpoint, secret = self._endpoint(account, "smtp")
            message_id = send_smtp(endpoint, secret, outgoing)
        stored = replace(outgoing, folder="Sent", message_id=message_id or outgoing.message_id)
        if self.imap is not None:
            self.imap.mailbox.append(stored)
        self.store.add_message(stored)
        return stored.message_id

    def _account(self, account_id: str) -> MailAccount:
        for account in self.store.accounts:
            if account.account_id == account_id:
                return account
        raise KeyError(account_id)

    def _endpoint(self, account: MailAccount, protocol: str) -> tuple[Endpoint, str]:
        raw = account.protocol_prefs.get(protocol)
        if not isinstance(raw, dict) or not raw.get("host"):
            raise ValueError(f"{protocol} is not configured")
        endpoint = Endpoint(
            host=str(raw["host"]),
            port=int(raw["port"]),
            tls=bool(raw["tls"]),
            user=str(raw.get("user") or ""),
        )
        return endpoint, self.vault.secret(account.account_id, protocol)


def _public_endpoint(endpoint: Endpoint) -> dict:
    return {
        "host": endpoint.host,
        "port": int(endpoint.port),
        "tls": bool(endpoint.tls),
        "user": endpoint.user,
    }


def _find(messages: list[MailMessage], message_id: str) -> MailMessage | None:
    for message in messages:
        if message.message_id == message_id:
            return message
    return None
