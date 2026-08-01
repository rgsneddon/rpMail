"""CLI entry for rpMail."""

from __future__ import annotations

import argparse
import json
import sys

from . import PRODUCT_FAMILY, PRODUCT_NAME, __version__
from .models import MailAccount, MailMessage
from .protocols import InMemoryImapImporter, InMemorySmtpSender
from .roles import Actor
from .store import MailboxStore


def smoke() -> dict:
    mod = Actor(user_id="mod-1", role="moderator", display_name="Moderator")
    user = Actor(user_id="u-1", role="user")
    store = MailboxStore()
    store.add_account(
        MailAccount(address="team@company.example", kind="company", display_name="Team"),
        actor=mod,
    )
    try:
        store.add_account(
            MailAccount(address="evil@company.example", kind="company"),
            actor=user,
        )
        user_ok = False
    except PermissionError:
        user_ok = True
    store.add_account(
        MailAccount(address="me@personal.example", kind="personal"),
        actor=user,
    )
    smtp = InMemorySmtpSender()
    msg = MailMessage(
        subject="Hello rpMail",
        from_addr="me@personal.example",
        to_addrs=["team@company.example"],
        body="Privacy-first mail scaffold.",
    )
    smtp.send(msg)
    store.add_message(msg)
    imap = InMemoryImapImporter(mailbox=[msg])
    store.import_batch(imap.import_messages())
    raw = store.dumps()
    roundtrip = MailboxStore.loads(raw)
    return {
        "ok": True,
        "product": PRODUCT_NAME,
        "family": PRODUCT_FAMILY,
        "version": __version__,
        "company_gate_blocks_user": user_ok,
        "accounts": len(roundtrip.accounts),
        "messages": len(roundtrip.messages),
        "smtp_sent": len(smtp.sent),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="rpmail", description="rpMail CLI")
    ap.add_argument("--version", action="store_true")
    ap.add_argument("--smoke", action="store_true", help="Run in-process smoke")
    args = ap.parse_args(argv)
    if args.version:
        print(f"{PRODUCT_NAME} {__version__}")
        return 0
    if args.smoke:
        print(json.dumps(smoke(), indent=2))
        return 0
    ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
