"""Mail folder helpers (Outlook Mail partial)."""

from __future__ import annotations

DEFAULT_FOLDERS: tuple[str, ...] = ("INBOX", "Sent", "Drafts", "Archive", "Trash")


def normalize_folder(name: str) -> str:
    n = (name or "INBOX").strip() or "INBOX"
    return n


def ensure_default_set(existing: list[str] | None = None) -> list[str]:
    out = list(DEFAULT_FOLDERS)
    for f in existing or []:
        if f not in out:
            out.append(f)
    return out
