"""Outlook full-parity scope matrix (from-scratch rpMail variant)."""

from __future__ import annotations

from typing import Any

# Required pillars for acceptance
OUTLOOK_PILLARS: tuple[str, ...] = ("Mail", "Calendar", "Contacts", "Tasks")

# status: implemented | partial | planned
OUTLOOK_PARITY_MATRIX: list[dict[str, str]] = [
    {"pillar": "Mail", "feature": "Accounts, folders, compose, send, SMTP/IMAP/POP3 import", "status": "implemented"},
    {"pillar": "Calendar", "feature": "Events create + serialize/persist", "status": "implemented"},
    {"pillar": "Contacts", "feature": "Create + lookup by email/name", "status": "implemented"},
    {"pillar": "Tasks", "feature": "Create + complete + persist", "status": "implemented"},
    {"pillar": "Mail", "feature": "Multi-account mailboxes", "status": "partial"},
    {"pillar": "Mail", "feature": "Reply/forward draft helpers", "status": "partial"},
    {"pillar": "Calendar", "feature": "Recurrence string field", "status": "partial"},
    {"pillar": "Tasks", "feature": "Priority field", "status": "partial"},
    {"pillar": "Mail", "feature": "Search / rules / categories", "status": "planned"},
    {"pillar": "Mail", "feature": "Attachments binary pipeline", "status": "planned"},
    {"pillar": "Calendar", "feature": "Shared free-busy / Graph", "status": "planned"},
    {"pillar": "Contacts", "feature": "Distribution lists", "status": "planned"},
    {"pillar": "Mail", "feature": "MAPI / .pst / Exchange live", "status": "planned"},
    {"pillar": "Mail", "feature": "Continuum vort1 mail client (IMAP/POP3/SMTP, isolated credentials)", "status": "implemented"},
]


def required_pillars_present() -> bool:
    found = {row["pillar"] for row in OUTLOOK_PARITY_MATRIX}
    return all(p in found for p in OUTLOOK_PILLARS)


def implemented_pillars() -> list[str]:
    return sorted(
        {
            row["pillar"]
            for row in OUTLOOK_PARITY_MATRIX
            if row["status"] == "implemented" and row["pillar"] in OUTLOOK_PILLARS
        }
    )


def matrix_as_dict() -> dict[str, Any]:
    return {
        "product": "rpMail",
        "variant": "from-scratch Outlook-class PIM",
        "required_pillars": list(OUTLOOK_PILLARS),
        "matrix": list(OUTLOOK_PARITY_MATRIX),
        "implemented_pillars": implemented_pillars(),
    }
