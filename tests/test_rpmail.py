"""Unit tests for shipped rpMail Outlook-class domain logic."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from rpmail import PRODUCT_NAME, __version__  # noqa: E402
from rpmail.__main__ import main, smoke  # noqa: E402
from rpmail.calendar import CalendarStore  # noqa: E402
from rpmail.contacts import ContactBook  # noqa: E402
from rpmail.models import MailAccount, MailMessage  # noqa: E402
from rpmail.parity_scope import (  # noqa: E402
    OUTLOOK_PILLARS,
    implemented_pillars,
    matrix_as_dict,
    required_pillars_present,
)
from rpmail.protocols import (  # noqa: E402
    InMemoryImapImporter,
    InMemoryPop3Importer,
    InMemorySmtpSender,
    PROTOCOL_CAPABILITIES,
)
from rpmail.roles import (  # noqa: E402
    Actor,
    PermissionDenied,
    can_create_company_mailbox,
    require_company_mailbox_creator,
)
from rpmail.store import MailboxStore  # noqa: E402
from rpmail.tasks import TaskList  # noqa: E402


class TestParityScope(unittest.TestCase):
    def test_outlook_pillars_in_matrix(self) -> None:
        self.assertEqual(OUTLOOK_PILLARS, ("Mail", "Calendar", "Contacts", "Tasks"))
        self.assertTrue(required_pillars_present())
        for p in OUTLOOK_PILLARS:
            self.assertIn(p, implemented_pillars())
        m = matrix_as_dict()
        self.assertEqual(m["product"], "rpMail")
        statuses = {row["status"] for row in m["matrix"]}
        self.assertIn("implemented", statuses)
        self.assertTrue(any(row.get("status") == "planned" for row in m["matrix"]))


class TestRoles(unittest.TestCase):
    def test_company_mailbox_moderator_only(self) -> None:
        self.assertTrue(can_create_company_mailbox(Actor("m", "moderator")))
        self.assertTrue(can_create_company_mailbox(Actor("a", "admin")))
        self.assertFalse(can_create_company_mailbox(Actor("u", "user")))
        with self.assertRaises(PermissionDenied):
            require_company_mailbox_creator(Actor("u", "user"))


class TestPimPillars(unittest.TestCase):
    def test_calendar_persist(self) -> None:
        cal = CalendarStore()
        ev = cal.add_event("Meet", start_unix=100, end_unix=200)
        again = CalendarStore.loads(cal.dumps())
        self.assertEqual(len(again.events), 1)
        self.assertEqual(again.events[0].title, "Meet")
        self.assertEqual(again.events[0].event_id, ev.event_id)

    def test_contacts_lookup(self) -> None:
        book = ContactBook()
        book.add("Ada", "Ada@Example.com")
        hit = book.lookup_by_email("ada@example.com")
        self.assertIsNotNone(hit)
        assert hit is not None
        self.assertEqual(hit.display_name, "Ada")
        self.assertEqual(len(book.lookup_by_name("ad")), 1)

    def test_tasks_complete(self) -> None:
        tl = TaskList()
        t = tl.add("Do", priority=2)
        self.assertFalse(t.completed)
        tl.complete(t.task_id)
        again = TaskList.loads(tl.dumps())
        self.assertTrue(again.tasks[0].completed)
        self.assertEqual(len(again.open_tasks()), 0)


class TestStoreRoundTrip(unittest.TestCase):
    def test_full_pim_roundtrip(self) -> None:
        store = MailboxStore()
        mod = Actor("m", "moderator")
        store.add_account(MailAccount(address="c@co.example", kind="company"), actor=mod)
        store.add_message(
            MailMessage(subject="S", from_addr="a@b.c", to_addrs=["c@co.example"], body="x")
        )
        store.calendar.add_event("E", start_unix=1, end_unix=2)
        store.contacts.add("Bob", "bob@x.com")
        task = store.tasks.add("T")
        store.tasks.complete(task.task_id)
        again = MailboxStore.loads(store.dumps())
        self.assertEqual(len(again.accounts), 1)
        self.assertEqual(len(again.messages), 1)
        self.assertEqual(len(again.calendar.events), 1)
        self.assertEqual(len(again.contacts.contacts), 1)
        self.assertTrue(again.tasks.tasks[0].completed)
        reply = store.draft_reply(store.messages[0])
        self.assertTrue(reply.subject.lower().startswith("re:"))


class TestProtocols(unittest.TestCase):
    def test_smtp_imap_pop3_fakes(self) -> None:
        msg = MailMessage(subject="t", from_addr="a", to_addrs=["b"], body="z")
        smtp = InMemorySmtpSender()
        mid = smtp.send(msg)
        self.assertEqual(mid, msg.message_id)
        imap = InMemoryImapImporter(mailbox=[msg])
        self.assertEqual(len(imap.import_messages(10)), 1)
        pop = InMemoryPop3Importer(mailbox=[msg, msg])
        self.assertEqual(len(pop.import_messages(1)), 1)
        self.assertIn("smtp", PROTOCOL_CAPABILITIES)


class TestEntry(unittest.TestCase):
    def test_smoke_covers_pillars(self) -> None:
        r = smoke()
        self.assertTrue(r["ok"])
        self.assertEqual(r["product"], PRODUCT_NAME)
        self.assertTrue(r["company_gate_blocks_user"])
        self.assertTrue(r["parity_required_ok"])
        pillars = r["pillars"]
        self.assertGreaterEqual(pillars["Mail"]["accounts"], 1)
        self.assertGreaterEqual(pillars["Mail"]["messages"], 1)
        self.assertGreaterEqual(pillars["Calendar"]["events"], 1)
        self.assertTrue(pillars["Calendar"]["event_ids"])
        self.assertGreaterEqual(pillars["Contacts"]["count"], 1)
        self.assertEqual(pillars["Contacts"]["lookup_email"], "ada@example.com")
        self.assertGreaterEqual(pillars["Tasks"]["completed"], 1)
        self.assertEqual(main(["--version"]), 0)
        self.assertEqual(main(["--smoke"]), 0)
        self.assertEqual(main(["--parity"]), 0)


if __name__ == "__main__":
    unittest.main()
