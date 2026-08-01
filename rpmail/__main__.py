"""CLI entry for rpMail (Outlook-class from-scratch variant)."""

from __future__ import annotations

import argparse
import json
import time

from . import PRODUCT_FAMILY, PRODUCT_NAME, __version__
from .models import MailAccount, MailMessage
from .parity_scope import matrix_as_dict, required_pillars_present
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
    reply = store.draft_reply(msg, body="Thanks")
    store.add_message(reply)
    imap = InMemoryImapImporter(mailbox=[msg])
    store.import_batch(imap.import_messages())

    # Calendar
    now = int(time.time())
    ev = store.calendar.add_event("Standup", start_unix=now, end_unix=now + 1800, location="Loft")
    # Contacts
    c = store.contacts.add("Ada Lovelace", "ada@example.com", company="Analytical")
    found = store.contacts.lookup_by_email("ada@example.com")
    # Tasks
    t = store.tasks.add("Ship parity", priority=1)
    store.tasks.complete(t.task_id)

    raw = store.dumps()
    roundtrip = MailboxStore.loads(raw)
    return {
        "ok": True,
        "product": PRODUCT_NAME,
        "family": PRODUCT_FAMILY,
        "version": __version__,
        "variant": "from-scratch Outlook-class PIM",
        "pillars": {
            "Mail": {
                "accounts": len(roundtrip.accounts),
                "messages": len(roundtrip.messages),
                "folders": list(roundtrip.folders),
                "smtp_sent": len(smtp.sent),
            },
            "Calendar": {
                "events": len(roundtrip.calendar.events),
                "event_ids": [e.event_id for e in roundtrip.calendar.events],
                "sample_title": ev.title,
            },
            "Contacts": {
                "count": len(roundtrip.contacts.contacts),
                "lookup_email": found.email if found else None,
                "contact_id": c.contact_id,
            },
            "Tasks": {
                "count": len(roundtrip.tasks.tasks),
                "completed": sum(1 for x in roundtrip.tasks.tasks if x.completed),
                "task_id": t.task_id,
            },
        },
        "company_gate_blocks_user": user_ok,
        "parity_required_ok": required_pillars_present(),
        "parity": matrix_as_dict(),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="rpmail", description="rpMail CLI")
    ap.add_argument("--version", action="store_true")
    ap.add_argument("--smoke", action="store_true", help="Run in-process smoke")
    ap.add_argument("--parity", action="store_true", help="Print parity matrix JSON")
    args = ap.parse_args(argv)
    if args.version:
        print(f"{PRODUCT_NAME} {__version__}")
        return 0
    if args.parity:
        print(json.dumps(matrix_as_dict(), indent=2))
        return 0
    if args.smoke:
        print(json.dumps(smoke(), indent=2))
        return 0
    ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
