"""Unit tests for shipped rpMail domain logic."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from rpmail.models import MailAccount, MailMessage  # noqa: E402
from rpmail.protocols import (  # noqa: E402
    InMemoryImapImporter,
    InMemoryPop3Importer,
    InMemorySmtpSender,
    PROTOCOL_CAPABILITIES,
)
from rpmail.roles import Actor, PermissionDenied, can_create_company_mailbox, require_company_mailbox_creator  # noqa: E402
from rpmail.store import MailboxStore  # noqa: E402
from rpmail import __version__, PRODUCT_NAME  # noqa: E402
from rpmail.__main__ import main, smoke  # noqa: E402


class TestRoles(unittest.TestCase):
    def test_company_mailbox_moderator_only(self) -> None:
        self.assertTrue(can_create_company_mailbox(Actor("m", "moderator")))
        self.assertTrue(can_create_company_mailbox(Actor("a", "admin")))
        self.assertFalse(can_create_company_mailbox(Actor("u", "user")))
        self.assertFalse(can_create_company_mailbox(Actor("s", "staff")))
        with self.assertRaises(PermissionDenied):
            require_company_mailbox_creator(Actor("u", "user"))


class TestStoreRoundTrip(unittest.TestCase):
    def test_serialize_roundtrip(self) -> None:
        store = MailboxStore()
        mod = Actor("m", "moderator")
        store.add_account(
            MailAccount(address="c@co.example", kind="company"), actor=mod
        )
        store.add_message(
            MailMessage(subject="S", from_addr="a@b.c", to_addrs=["c@co.example"], body="x")
        )
        raw = store.dumps()
        again = MailboxStore.loads(raw)
        self.assertEqual(len(again.accounts), 1)
        self.assertEqual(again.accounts[0].kind, "company")
        self.assertEqual(again.messages[0].subject, "S")
        # JSON stable
        self.assertEqual(json.loads(raw)["accounts"][0]["address"], "c@co.example")


class TestProtocols(unittest.TestCase):
    def test_smtp_imap_pop3_fakes(self) -> None:
        msg = MailMessage(subject="t", from_addr="a", to_addrs=["b"], body="z")
        smtp = InMemorySmtpSender()
        mid = smtp.send(msg)
        self.assertEqual(mid, msg.message_id)
        self.assertEqual(len(smtp.sent), 1)
        imap = InMemoryImapImporter(mailbox=[msg])
        self.assertEqual(len(imap.import_messages(10)), 1)
        pop = InMemoryPop3Importer(mailbox=[msg, msg])
        self.assertEqual(len(pop.import_messages(1)), 1)
        self.assertIn("smtp", PROTOCOL_CAPABILITIES)
        self.assertIn("imap", PROTOCOL_CAPABILITIES)
        self.assertIn("pop3", PROTOCOL_CAPABILITIES)


class TestEntry(unittest.TestCase):
    def test_smoke_and_cli(self) -> None:
        r = smoke()
        self.assertTrue(r["ok"])
        self.assertEqual(r["product"], PRODUCT_NAME)
        self.assertTrue(r["company_gate_blocks_user"])
        self.assertEqual(main(["--version"]), 0)
        self.assertEqual(main(["--smoke"]), 0)


if __name__ == "__main__":
    unittest.main()
