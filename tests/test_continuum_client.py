"""Continuum body pin, protocol fakes, live loopback, and credential isolation."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import unittest
from email.message import EmailMessage
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from rpmail.client import MailClient  # noqa: E402
from rpmail.continuum import (  # noqa: E402
    DISPLAY_NAME,
    EXAMPLE_ORIGIN,
    INSTALL_KEY_UNTIL_SMOKE,
    MAIL_HOOK,
    PROGRAM_ID,
    body_bytes,
    body_document,
    body_text,
    mint_vortice_deploy_key,
    parse_vortice_key,
    pinned_body_sha256,
    verify_vortice_download,
    vortice_bundle_hash,
)
from rpmail.credentials import CredentialVault, assert_credential_isolation  # noqa: E402
from rpmail.live import Endpoint, transport_security  # noqa: E402
from rpmail.models import MailMessage  # noqa: E402
from rpmail.protocols import (  # noqa: E402
    InMemoryImapImporter,
    InMemoryPop3Importer,
    InMemorySmtpSender,
)
from rpmail.roles import Actor, PermissionDenied  # noqa: E402
from rpmail.store import MailboxStore  # noqa: E402
from mail_loopback import LoopbackMail  # noqa: E402

PIN_PATH = ROOT / "continuum" / "vortice.sha256"
IMAP_SECRET = "imap-app-secret-9f3c"
POP_SECRET = "pop3-app-secret-9f3c"
SMTP_SECRET = "smtp-app-secret-9f3c"


def _sample_message() -> MailMessage:
    return MailMessage(
        subject="Hello rpMail",
        from_addr="bob@example.com",
        to_addrs=["ada@example.com"],
        body="A private note.",
        folder="INBOX",
        message_id="m1",
    )


def _rfc822() -> bytes:
    email = EmailMessage()
    email["From"] = "bob@example.com"
    email["To"] = "ada@example.com"
    email["Subject"] = "Hello rpMail"
    email["Message-ID"] = "<m1@example.com>"
    email.set_content("A private note.")
    return email.as_bytes()


class TestProtocolFakesRoundTrip(unittest.TestCase):
    def test_account_round_trip_and_isolation(self) -> None:
        incoming = _sample_message()
        imap = InMemoryImapImporter(mailbox=[incoming])
        pop = InMemoryPop3Importer(mailbox=[incoming])
        smtp = InMemorySmtpSender()
        store = MailboxStore()
        vault = CredentialVault()
        client = MailClient(store, vault, imap=imap, pop3=pop, smtp=smtp)
        user = Actor("u-1", "user")
        staff = Actor("s-1", "staff")
        moderator = Actor("m-1", "moderator")
        shewall = {"seedHex": "ab" * 32, "spendableNanos": 420000000000, "pendingNanos": 0}
        spendable_before = shewall["spendableNanos"]

        with self.assertRaises(PermissionDenied):
            client.configure(
                actor=user,
                address="team@company.example",
                kind="company",
                receive="imap",
                imap=Endpoint("imap.example", 993, True, "team"),
                imap_secret=IMAP_SECRET,
                smtp=Endpoint("smtp.example", 587, True, "team"),
                smtp_secret=SMTP_SECRET,
            )
        with self.assertRaises(PermissionDenied):
            client.configure(
                actor=staff,
                address="team@company.example",
                kind="company",
                receive="imap",
                imap=Endpoint("imap.example", 993, True, "team"),
                imap_secret=IMAP_SECRET,
            )
        self.assertEqual(vault.accounts, {})

        company = client.configure(
            actor=moderator,
            address="team@company.example",
            display_name="Team",
            kind="company",
            receive="imap",
            imap=Endpoint("imap.example", 993, True, "team"),
            imap_secret="company-imap-secret",
            smtp=Endpoint("smtp.example", 587, True, "team"),
            smtp_secret="company-smtp-secret",
            account_id="company-1",
        )
        self.assertEqual(company.kind, "company")

        account = client.configure(
            actor=user,
            address="ada@example.com",
            display_name="Ada",
            kind="personal",
            receive="imap",
            imap=Endpoint("imap.example", 993, True, "ada"),
            imap_secret=IMAP_SECRET,
            pop3=Endpoint("pop.example", 995, True, "ada"),
            pop3_secret=POP_SECRET,
            smtp=Endpoint("smtp.example", 587, True, "ada"),
            smtp_secret=SMTP_SECRET,
            account_id="ada-1",
        )
        self.assertEqual(account.protocol_prefs["receive"], "imap")
        self.assertNotIn("password", json.dumps(account.protocol_prefs))
        self.assertNotIn(IMAP_SECRET, json.dumps(account.to_dict()))

        folders = client.list_folders(account.account_id)
        self.assertIn("INBOX", folders)
        listed = client.list_messages(account.account_id, folder="INBOX")
        self.assertEqual(len(listed), 1)
        read = client.read_message(account.account_id, listed[0].message_id, folder="INBOX")
        self.assertEqual(read.body, "A private note.")

        sent_id = client.send(
            account.account_id,
            MailMessage(
                subject="Out",
                from_addr="",
                to_addrs=["bob@example.com"],
                body="Reply in kind.",
                message_id="out-1",
            ),
        )
        self.assertEqual(sent_id, "out-1")
        self.assertEqual(smtp.sent[0].from_addr, "ada@example.com")
        self.assertEqual(len(client.list_messages(account.account_id, folder="Sent")), 1)

        client.set_receive(account.account_id, "pop3")
        pop_listed = client.list_messages(account.account_id)
        self.assertEqual(pop_listed[0].message_id, "m1")
        self.assertEqual(client.list_folders(account.account_id), ["INBOX"])
        self.assertEqual(client.read_message(account.account_id, "m1").subject, "Hello rpMail")

        again_store = MailboxStore.loads(store.dumps())
        again_vault = CredentialVault.loads(vault.dumps())
        self.assertEqual(len(again_store.accounts), 2)
        restored = next(a for a in again_store.accounts if a.account_id == "ada-1")
        self.assertEqual(restored.protocol_prefs["imap"]["host"], "imap.example")
        self.assertEqual(restored.protocol_prefs["pop3"]["port"], 995)
        self.assertEqual(restored.protocol_prefs["smtp"]["user"], "ada")
        self.assertEqual(again_vault.secret("ada-1", "imap"), IMAP_SECRET)
        self.assertEqual(again_vault.secret("ada-1", "pop3"), POP_SECRET)
        self.assertEqual(again_vault.secret("ada-1", "smtp"), SMTP_SECRET)
        self.assertEqual(shewall["spendableNanos"], spendable_before)

        assert_credential_isolation(
            store=store,
            vault=vault,
            shewall=shewall,
            secrets=[IMAP_SECRET, POP_SECRET, SMTP_SECRET, "company-imap-secret", "company-smtp-secret"],
        )
        self.assertNotIn("seedHex", vault.dumps())
        self.assertNotIn("spendableNanos", store.dumps())


class TestLiveLoopback(unittest.TestCase):
    def test_security_mode(self) -> None:
        self.assertEqual(transport_security("imap", Endpoint("h", 993, True, "u")), "implicit")
        self.assertEqual(transport_security("imap", Endpoint("h", 143, True, "u")), "starttls")
        self.assertEqual(transport_security("imap", Endpoint("h", 143, False, "u")), "plain")
        self.assertEqual(transport_security("pop3", Endpoint("h", 995, True, "u")), "implicit")
        self.assertEqual(transport_security("pop3", Endpoint("h", 110, True, "u")), "starttls")
        self.assertEqual(transport_security("smtp", Endpoint("h", 465, True, "u")), "implicit")
        self.assertEqual(transport_security("smtp", Endpoint("h", 587, True, "u")), "starttls")
        self.assertEqual(transport_security("smtp", Endpoint("h", 25, False, "u")), "plain")

    def test_stdlib_imap_pop3_smtp_round_trip(self) -> None:
        box = LoopbackMail(user="ada", secret="loop-secret", messages=[_rfc822()]).start()
        self.addCleanup(box.close)
        store = MailboxStore()
        vault = CredentialVault()
        client = MailClient(store, vault)
        account = client.configure(
            actor=Actor("u", "user"),
            address="ada@example.com",
            receive="imap",
            imap=Endpoint("127.0.0.1", box.imap_port, False, "ada"),
            imap_secret="loop-secret",
            pop3=Endpoint("127.0.0.1", box.pop3_port, False, "ada"),
            pop3_secret="loop-secret",
            smtp=Endpoint("127.0.0.1", box.smtp_port, False, "ada"),
            smtp_secret="loop-secret",
            account_id="live-1",
        )
        self.assertEqual(client.list_folders(account.account_id), ["INBOX", "Sent"])
        listed = client.list_messages(account.account_id, folder="INBOX")
        self.assertEqual(listed[0].subject, "Hello rpMail")
        self.assertIn("A private note.", client.read_message(account.account_id, "m1@example.com").body)
        client.send(
            account.account_id,
            MailMessage(
                subject="Sent live",
                from_addr="ada@example.com",
                to_addrs=["bob@example.com"],
                body="Via SMTP.",
                message_id="live-out",
            ),
        )
        self.assertTrue(box.sent)
        self.assertIn(b"Sent live", box.sent[0])
        self.assertIn(b"Via SMTP.", box.sent[0])
        client.set_receive(account.account_id, "pop3")
        pop_listed = client.list_messages(account.account_id)
        self.assertEqual(pop_listed[0].message_id, "m1@example.com")
        self.assertEqual(pop_listed[0].folder, "INBOX")
        shewall = {"seedHex": "cd" * 32, "spendableNanos": 7}
        assert_credential_isolation(
            store=store,
            vault=vault,
            shewall=shewall,
            secrets=["loop-secret"],
        )
        self.assertEqual(shewall["spendableNanos"], 7)


class TestContinuumBody(unittest.TestCase):
    def test_body_shape_and_hash_stability(self) -> None:
        raw = body_bytes()
        self.assertTrue(raw.endswith(b"\n"))
        doc = body_document()
        self.assertEqual(doc["v"], 1)
        self.assertEqual(doc["id"], PROGRAM_ID)
        self.assertEqual(doc["name"], DISPLAY_NAME)
        self.assertEqual(doc["hook"], MAIL_HOOK)
        self.assertEqual(doc["pane"], "rpMail")
        self.assertEqual(doc["preinstall"], False)
        self.assertEqual(doc["install"], "vort1-paste-only")
        self.assertEqual(doc["credentials"], "isolated")
        self.assertEqual(doc["companyMailbox"], "moderator")
        self.assertEqual(doc["protocols"], ["imap", "pop3", "smtp"])
        self.assertEqual(doc["isolateFrom"], ["shewall", "spendable"])
        digest = pinned_body_sha256()
        self.assertEqual(digest, hashlib.sha256(raw).hexdigest())
        self.assertEqual(digest, PIN_PATH.read_text(encoding="utf-8").strip())
        self.assertEqual(hashlib.sha256(body_text().encode("utf-8")).hexdigest(), digest)

        source = body_text()
        bundle = vortice_bundle_hash(
            program_id=PROGRAM_ID,
            name=DISPLAY_NAME,
            origin=EXAMPLE_ORIGIN,
            source=source,
        )
        self.assertEqual(
            bundle,
            vortice_bundle_hash(
                program_id=PROGRAM_ID,
                name=DISPLAY_NAME,
                origin=EXAMPLE_ORIGIN,
                source=source,
            ),
        )
        node = subprocess.check_output(
            ["node", "-e", _NODE_HASH],
            input=json.dumps(
                {
                    "programId": PROGRAM_ID,
                    "name": DISPLAY_NAME,
                    "origin": EXAMPLE_ORIGIN,
                    "source": source,
                }
            ).encode(),
        )
        self.assertEqual(bundle, node.decode().strip())
        self.assertNotEqual(
            bundle,
            vortice_bundle_hash(
                program_id=PROGRAM_ID,
                name=DISPLAY_NAME,
                origin=EXAMPLE_ORIGIN,
                source=source + " ",
            ),
        )

    def test_mint_matches_node_and_placeholder_is_not_a_deploy_key(self) -> None:
        self.assertEqual(INSTALL_KEY_UNTIL_SMOKE, "vort1:TODO-rpmail")
        self.assertIsNone(parse_vortice_key(INSTALL_KEY_UNTIL_SMOKE))
        self.assertFalse(INSTALL_KEY_UNTIL_SMOKE.startswith("vort1."))
        source = '{"v":1,"id":"rpmail-v1","pane":"rpMail"}'
        nonce = "ab" * 16
        key = mint_vortice_deploy_key(
            program_id=PROGRAM_ID,
            name=DISPLAY_NAME,
            origin=EXAMPLE_ORIGIN,
            source=source,
            nonce=nonce,
        )
        self.assertIsNotNone(key)
        assert key is not None
        self.assertTrue(key.startswith("vort1."))
        node_key = subprocess.check_output(
            ["node", "-e", _NODE_MINT],
            input=json.dumps(
                {
                    "programId": PROGRAM_ID,
                    "name": DISPLAY_NAME,
                    "origin": EXAMPLE_ORIGIN,
                    "source": source,
                    "nonce": nonce,
                }
            ).encode(),
        ).decode().strip()
        self.assertEqual(key, node_key)
        parsed = parse_vortice_key(key)
        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual(parsed["id"], PROGRAM_ID)
        self.assertEqual(parsed["name"], DISPLAY_NAME)
        self.assertEqual(verify_vortice_download(key, source)["ok"], True)
        self.assertEqual(verify_vortice_download(key, source + "x")["reason"], "bundle_mismatch")
        self.assertIsNone(
            mint_vortice_deploy_key(
                program_id="shear-reserve-v1",
                name="The Reserve",
                origin=EXAMPLE_ORIGIN,
                source=source,
                nonce=nonce,
            )
        )
        self.assertIsNone(
            mint_vortice_deploy_key(
                program_id="pool-unlock-2044",
                name="Pool",
                origin=EXAMPLE_ORIGIN,
                source=source,
                nonce=nonce,
            )
        )


_NODE_HASH = r"""
const { createHash } = require('crypto');
let raw = '';
process.stdin.on('data', (c) => { raw += c; });
process.stdin.on('end', () => {
  const spec = JSON.parse(raw);
  const digest = createHash('sha256')
    .update('chronoflux-Omega-v1')
    .update(String(spec.programId || ''))
    .update('\0')
    .update(String(spec.name || ''))
    .update('\0')
    .update(String(spec.origin || ''))
    .update('\0')
    .update(String(spec.source || ''))
    .digest('hex');
  process.stdout.write(digest);
});
"""

_NODE_MINT = r"""
const { createHash } = require('crypto');
let raw = '';
process.stdin.on('data', (c) => { raw += c; });
process.stdin.on('end', () => {
  const spec = JSON.parse(raw);
  const personal = 'chronoflux-Omega-v1';
  const bundle = createHash('sha256')
    .update(personal)
    .update(String(spec.programId))
    .update('\0')
    .update(String(spec.name))
    .update('\0')
    .update(String(spec.origin))
    .update('\0')
    .update(String(spec.source))
    .digest('hex');
  const body = { v: 1, id: spec.programId, name: spec.name, origin: spec.origin, bundle };
  if (spec.nonce) body.n = spec.nonce;
  const canonical = JSON.stringify(body);
  const mac = createHash('sha256').update(personal).update(canonical).digest('hex').slice(0, 40);
  const payload = { v: 1, id: spec.programId, name: spec.name, origin: spec.origin, bundle, n: spec.nonce, mac };
  process.stdout.write('vort1.' + Buffer.from(JSON.stringify(payload)).toString('base64url'));
});
"""


if __name__ == "__main__":
    unittest.main()
