"""Mailbox secrets kept off the mail store and off any SHE / shewall blob.

The vault is a separate document. It is not a balance, it does not hold a
seed, and callers must not merge it into ``MailboxStore`` or a shewall export.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from .store import MailboxStore

WALLET_MATERIAL_KEYS = frozenset(
    {
        "seed",
        "seedHex",
        "seed32",
        "spendable",
        "spendableNanos",
        "pendingNanos",
        "shewall",
    }
)

SECRET_FIELD_KEYS = frozenset(
    {
        "password",
        "secret",
        "app_password",
        "appPassword",
        "imap_secret",
        "pop3_secret",
        "smtp_secret",
    }
)


@dataclass
class CredentialVault:
    """Per-account IMAP / POP3 / SMTP secrets. Not a SHE balance."""

    accounts: dict[str, dict[str, str]] = field(default_factory=dict)

    def put(
        self,
        account_id: str,
        *,
        imap_secret: str = "",
        pop3_secret: str = "",
        smtp_secret: str = "",
    ) -> None:
        self.accounts[str(account_id)] = {
            "imap": str(imap_secret or ""),
            "pop3": str(pop3_secret or ""),
            "smtp": str(smtp_secret or ""),
        }

    def secret(self, account_id: str, protocol: str) -> str:
        row = self.accounts.get(str(account_id)) or {}
        return str(row.get(protocol) or "")

    def to_dict(self) -> dict[str, Any]:
        return {
            "accounts": {key: dict(row) for key, row in sorted(self.accounts.items())},
        }

    def dumps(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)

    @classmethod
    def loads(cls, raw: str) -> "CredentialVault":
        data = json.loads(raw)
        vault = cls()
        for account_id, row in (data.get("accounts") or {}).items():
            if not isinstance(row, dict):
                continue
            vault.put(
                str(account_id),
                imap_secret=str(row.get("imap") or ""),
                pop3_secret=str(row.get("pop3") or ""),
                smtp_secret=str(row.get("smtp") or ""),
            )
        return vault


def _has_key(obj: Any, forbidden: frozenset[str]) -> bool:
    if isinstance(obj, dict):
        if any(str(key) in forbidden for key in obj):
            return True
        return any(_has_key(value, forbidden) for value in obj.values())
    if isinstance(obj, list):
        return any(_has_key(value, forbidden) for value in obj)
    return False


def prefs_have_secret_fields(store: MailboxStore) -> bool:
    for account in store.accounts:
        if _has_key(account.protocol_prefs, SECRET_FIELD_KEYS | WALLET_MATERIAL_KEYS):
            return True
    return False


def isolation_report(
    *,
    store: MailboxStore,
    vault: CredentialVault,
    shewall: dict[str, Any],
    secrets: list[str],
) -> dict[str, bool]:
    """True flags mean a leak. ``secrets_in_vault`` is True when every secret is present."""

    store_raw = store.dumps()
    wall_raw = json.dumps(shewall, sort_keys=True)
    vault_raw = vault.dumps()
    wanted = [s for s in secrets if s]
    return {
        "secrets_in_store": any(secret in store_raw for secret in wanted),
        "secrets_in_shewall": any(secret in wall_raw for secret in wanted),
        "secrets_in_vault": all(secret in vault_raw for secret in wanted) if wanted else False,
        "store_has_wallet_keys": _has_key(json.loads(store_raw), WALLET_MATERIAL_KEYS),
        "vault_has_wallet_keys": _has_key(vault.to_dict(), WALLET_MATERIAL_KEYS),
        "prefs_have_secret_keys": prefs_have_secret_fields(store),
    }


def assert_credential_isolation(
    *,
    store: MailboxStore,
    vault: CredentialVault,
    shewall: dict[str, Any],
    secrets: list[str],
) -> dict[str, bool]:
    """Raise AssertionError if mail secrets touch the store, shewall, or a balance field."""

    report = isolation_report(store=store, vault=vault, shewall=shewall, secrets=secrets)
    leaks = [
        report["secrets_in_store"],
        report["secrets_in_shewall"],
        report["store_has_wallet_keys"],
        report["vault_has_wallet_keys"],
        report["prefs_have_secret_keys"],
        not report["secrets_in_vault"],
    ]
    if any(leaks):
        raise AssertionError(f"mail credentials are not isolated: {report}")
    return report
