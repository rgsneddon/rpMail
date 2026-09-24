"""Stdlib IMAP, POP3, and SMTP. TLS mode follows the usual ports.

- IMAP 993 / POP3 995 / SMTP 465: implicit TLS
- other ports with tls=True: STARTTLS
- tls=False: cleartext (loopback and private nets)

Secrets are used only as protocol credentials. They are stripped from errors.
"""

from __future__ import annotations

import imaplib
import poplib
import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage
from email.parser import BytesParser
from email.policy import default as default_policy
from typing import Any

from .models import MailMessage

IMPLICIT_PORTS = {"imap": 993, "pop3": 995, "smtp": 465}


class MailTransportError(RuntimeError):
    """Network or protocol failure. The message never includes a mailbox secret."""


@dataclass(frozen=True)
class Endpoint:
    host: str
    port: int
    tls: bool
    user: str


def transport_security(protocol: str, endpoint: Endpoint) -> str:
    if protocol not in IMPLICIT_PORTS:
        raise ValueError(f"unknown protocol {protocol}")
    if not endpoint.tls:
        return "plain"
    if int(endpoint.port) == IMPLICIT_PORTS[protocol]:
        return "implicit"
    return "starttls"


def _redact(text: str, secret: str) -> str:
    if secret and secret in text:
        return text.replace(secret, "[redacted]")
    return text


def _fail(code: str, exc: BaseException, secret: str) -> MailTransportError:
    detail = _redact(str(exc), secret).strip()
    if detail:
        return MailTransportError(f"{code}: {detail}")
    return MailTransportError(code)


def _open_imap(endpoint: Endpoint, secret: str) -> imaplib.IMAP4:
    mode = transport_security("imap", endpoint)
    try:
        if mode == "implicit":
            conn: imaplib.IMAP4 = imaplib.IMAP4_SSL(endpoint.host, int(endpoint.port))
        else:
            conn = imaplib.IMAP4(endpoint.host, int(endpoint.port))
            if mode == "starttls":
                conn.starttls(ssl.create_default_context())
        conn.login(endpoint.user, secret)
        return conn
    except Exception as exc:
        raise _fail("imap_login_failed", exc, secret) from None


def _open_pop3(endpoint: Endpoint, secret: str) -> poplib.POP3:
    mode = transport_security("pop3", endpoint)
    try:
        if mode == "implicit":
            conn: poplib.POP3 = poplib.POP3_SSL(endpoint.host, int(endpoint.port))
        else:
            conn = poplib.POP3(endpoint.host, int(endpoint.port))
            if mode == "starttls":
                conn.stls(ssl.create_default_context())
        conn.user(endpoint.user)
        conn.pass_(secret)
        return conn
    except Exception as exc:
        raise _fail("pop3_login_failed", exc, secret) from None


def _logout_imap(conn: imaplib.IMAP4) -> None:
    try:
        conn.logout()
    except Exception:
        try:
            conn.shutdown()
        except Exception:
            pass


def list_imap_folders(endpoint: Endpoint, secret: str) -> list[str]:
    conn = _open_imap(endpoint, secret)
    try:
        typ, data = conn.list()
        if typ != "OK":
            raise MailTransportError("imap_list_failed")
        folders: list[str] = []
        for row in data or []:
            name = _folder_name(row)
            if name and name not in folders:
                folders.append(name)
        return folders or ["INBOX"]
    except MailTransportError:
        raise
    except Exception as exc:
        raise _fail("imap_list_failed", exc, secret) from None
    finally:
        _logout_imap(conn)


def fetch_imap(
    endpoint: Endpoint,
    secret: str,
    *,
    folder: str = "INBOX",
    limit: int = 50,
) -> list[MailMessage]:
    conn = _open_imap(endpoint, secret)
    try:
        typ, _ = conn.select(folder)
        if typ != "OK":
            raise MailTransportError("imap_select_failed")
        typ, data = conn.search(None, "ALL")
        if typ != "OK":
            raise MailTransportError("imap_search_failed")
        raw_ids = (data[0] or b"").split() if data else []
        chosen = raw_ids[-max(0, int(limit)) :]
        out: list[MailMessage] = []
        for mid in chosen:
            typ, fetched = conn.fetch(mid, "(RFC822)")
            if typ != "OK":
                continue
            blob = _extract_rfc822(fetched)
            if blob is None:
                continue
            out.append(parse_rfc822(blob, folder=folder))
        return out
    except MailTransportError:
        raise
    except Exception as exc:
        raise _fail("imap_fetch_failed", exc, secret) from None
    finally:
        _logout_imap(conn)


def fetch_pop3(endpoint: Endpoint, secret: str, *, limit: int = 50) -> list[MailMessage]:
    conn = _open_pop3(endpoint, secret)
    try:
        count, _size = conn.stat()
        start = max(1, int(count) - max(0, int(limit)) + 1) if count else 1
        out: list[MailMessage] = []
        for index in range(start, int(count) + 1):
            _resp, lines, _octets = conn.retr(index)
            blob = b"\r\n".join(lines)
            out.append(parse_rfc822(blob, folder="INBOX"))
        return out
    except MailTransportError:
        raise
    except Exception as exc:
        raise _fail("pop3_fetch_failed", exc, secret) from None
    finally:
        try:
            conn.quit()
        except Exception:
            pass


def send_smtp(endpoint: Endpoint, secret: str, message: MailMessage) -> str:
    mode = transport_security("smtp", endpoint)
    msg = _email_from_message(message)
    try:
        if mode == "implicit":
            smtp: smtplib.SMTP = smtplib.SMTP_SSL(endpoint.host, int(endpoint.port), timeout=20)
        else:
            smtp = smtplib.SMTP(endpoint.host, int(endpoint.port), timeout=20)
        try:
            smtp.ehlo()
            if mode == "starttls":
                smtp.starttls(context=ssl.create_default_context())
                smtp.ehlo()
            if endpoint.user:
                smtp.login(endpoint.user, secret)
            smtp.send_message(msg)
        finally:
            try:
                smtp.quit()
            except Exception:
                pass
    except MailTransportError:
        raise
    except Exception as exc:
        raise _fail("smtp_send_failed", exc, secret) from None
    return message.message_id


def parse_rfc822(raw: bytes, *, folder: str) -> MailMessage:
    parsed = BytesParser(policy=default_policy).parsebytes(raw)
    body = _body_text(parsed)
    message_id = str(parsed.get("Message-ID") or "").strip().strip("<>")
    if not message_id:
        message_id = MailMessage(subject="", from_addr="", to_addrs=[]).message_id
    to_addrs: list[str] = []
    for item in parsed.get_all("To", []) or []:
        for part in str(item).split(","):
            part = part.strip()
            if part:
                to_addrs.append(part)
    created = 0
    return MailMessage(
        subject=str(parsed.get("Subject") or ""),
        from_addr=str(parsed.get("From") or ""),
        to_addrs=to_addrs,
        body=body,
        folder=folder or "INBOX",
        message_id=message_id,
        created_unix=created,
    )


def _body_text(parsed: Any) -> str:
    if parsed.is_multipart():
        for part in parsed.walk():
            if part.get_content_type() != "text/plain" or part.get_content_disposition() == "attachment":
                continue
            content = part.get_content()
            return content if isinstance(content, str) else str(content)
        return ""
    if parsed.get_content_type() == "text/plain":
        content = parsed.get_content()
        return content if isinstance(content, str) else str(content)
    payload = parsed.get_payload(decode=True)
    if isinstance(payload, bytes):
        return payload.decode("utf-8", errors="replace")
    return str(payload or "")


def _email_from_message(message: MailMessage) -> EmailMessage:
    email = EmailMessage()
    email["From"] = message.from_addr
    email["To"] = ", ".join(message.to_addrs)
    email["Subject"] = message.subject
    email["Message-ID"] = f"<{message.message_id}>"
    email.set_content(message.body or "")
    return email


def _folder_name(row: Any) -> str:
    if not isinstance(row, (bytes, bytearray)):
        return ""
    text = bytes(row).decode("utf-8", errors="replace")
    if '"' in text:
        return text.rsplit('"', 2)[-2]
    parts = text.split(" ")
    return parts[-1] if parts else ""


def _extract_rfc822(fetched: Any) -> bytes | None:
    if not fetched:
        return None
    for item in fetched:
        if isinstance(item, tuple) and len(item) >= 2 and isinstance(item[1], (bytes, bytearray)):
            return bytes(item[1])
        if isinstance(item, (bytes, bytearray)) and b"\n" in item and b"FETCH" not in item[:40]:
            return bytes(item)
    return None

