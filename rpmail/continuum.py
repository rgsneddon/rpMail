"""Continuum vort1 body for rpMail.

The hosted file is ``continuum/vortice.json``. Continuum downloads those exact
bytes, checks ``vorticeBundleHash``, and (with the mail host bridge) opens
``hook: continuum.mail``. This module can build a ``vort1.`` key locally. It
does not contact a node and it does not mint SHE.

Until a smoke run is not-refuted, the install string stays
``vort1:TODO-rpmail``. Do not publish a live gallery key.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
import secrets
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

VORTEX_PERSONAL = "chronoflux-Omega-v1"
VORTICE_KEY_PREFIX = "vort1."
PROGRAM_ID = "rpmail-v1"
DISPLAY_NAME = "rpMail"
MAIL_HOOK = "continuum.mail"
# Not a deploy key. Paste-install stays blocked until smoke is not-refuted.
INSTALL_KEY_UNTIL_SMOKE = "vort1:TODO-rpmail"
BODY_RELATIVE = "continuum/vortice.json"
# Documented example only. Not vortices.shear.digital and not a live pin.
EXAMPLE_ORIGIN = "https://rpmail.example/continuum/vortice.json"

RESERVED_PROGRAMS = frozenset(
    {
        "shear-reserve-v1",
        "shear-join-v1",
        "shear-join-watch-v1",
        "pool-unlock-2044",
    }
)


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def body_path() -> Path:
    return repo_root() / BODY_RELATIVE


def body_bytes() -> bytes:
    return body_path().read_bytes()


def body_text() -> str:
    return body_bytes().decode("utf-8")


def body_document() -> dict[str, Any]:
    data = json.loads(body_text())
    if not isinstance(data, dict):
        raise ValueError("vortice body must be a JSON object")
    return data


def pinned_body_sha256() -> str:
    return hashlib.sha256(body_bytes()).hexdigest()


def valid_program_id(program_id: str) -> str | None:
    pid = str(program_id or "").strip().lower()
    if not re.fullmatch(r"[a-z0-9._-]{3,64}", pid):
        return None
    if pid in RESERVED_PROGRAMS:
        return None
    return pid


def valid_origin(origin: str) -> str | None:
    raw = str(origin or "").strip()
    try:
        parsed = urlparse(raw)
    except ValueError:
        return None
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return None
    return raw


def vortice_bundle_hash(*, program_id: str, name: str, origin: str, source: str) -> str:
    """Match shear-testnet ``crypto/vortex.js`` ``vorticeBundleHash``."""

    digest = hashlib.sha256()
    digest.update(VORTEX_PERSONAL.encode("utf-8"))
    digest.update(str(program_id or "").encode("utf-8"))
    digest.update(b"\0")
    digest.update(str(name or "").encode("utf-8"))
    digest.update(b"\0")
    digest.update(str(origin or "").encode("utf-8"))
    digest.update(b"\0")
    digest.update(str(source or "").encode("utf-8"))
    return digest.hexdigest()


def _canonical_body(*, id: str, name: str, origin: str, bundle: str, n: str | None) -> str:
    body: dict[str, Any] = {
        "v": 1,
        "id": id,
        "name": name,
        "origin": origin,
        "bundle": bundle,
    }
    if n:
        body["n"] = n
    return json.dumps(body, separators=(",", ":"), ensure_ascii=False)


def _mac_of(body: str) -> str:
    return hashlib.sha256((VORTEX_PERSONAL + body).encode("utf-8")).hexdigest()[:40]


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def mint_vortice_deploy_key(
    *,
    program_id: str,
    name: str,
    origin: str,
    source: str,
    nonce: str | None = None,
) -> str | None:
    """Build a ``vort1.`` deploy key for ``source`` bytes. Does not mint SHE."""

    pid = valid_program_id(program_id)
    url = valid_origin(origin)
    if not pid or not url or source is None:
        return None
    label = str(name or pid).strip() or pid
    if not 1 <= len(label) <= 64:
        return None
    n = nonce if nonce is not None else secrets.token_hex(16)
    if not re.fullmatch(r"[0-9a-f]{32}", n):
        return None
    bundle = vortice_bundle_hash(program_id=pid, name=label, origin=url, source=source)
    body = _canonical_body(id=pid, name=label, origin=url, bundle=bundle, n=n)
    payload = {
        "v": 1,
        "id": pid,
        "name": label,
        "origin": url,
        "bundle": bundle,
        "n": n,
        "mac": _mac_of(body),
    }
    raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return f"{VORTICE_KEY_PREFIX}{_b64url(raw)}"


def parse_vortice_key(key: str) -> dict[str, Any] | None:
    raw = str(key or "").strip()
    if not raw.startswith(VORTICE_KEY_PREFIX):
        return None
    token = raw[len(VORTICE_KEY_PREFIX) :]
    pad = "=" * ((4 - len(token) % 4) % 4)
    try:
        payload = json.loads(base64.urlsafe_b64decode(token + pad))
    except (ValueError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    pid = valid_program_id(str(payload.get("id") or ""))
    origin = valid_origin(str(payload.get("origin") or ""))
    name = str(payload.get("name") or "")
    bundle = str(payload.get("bundle") or "")
    mac = str(payload.get("mac") or "").lower()
    n = str(payload.get("n") or "")
    if n and not re.fullmatch(r"[0-9a-f]{32}", n, flags=re.IGNORECASE):
        return None
    if not pid or not origin or not bundle or not 1 <= len(name) <= 64:
        return None
    body = _canonical_body(id=pid, name=name, origin=origin, bundle=bundle, n=n or None)
    if _mac_of(body) != mac:
        return None
    return {
        "id": pid,
        "name": name,
        "origin": origin,
        "bundle": bundle,
        "n": n,
        "key": raw,
    }


def verify_vortice_download(key: str, source: str) -> dict[str, Any]:
    parsed = parse_vortice_key(key)
    if not parsed:
        return {"ok": False, "reason": "bad_key"}
    bundle = vortice_bundle_hash(
        program_id=str(parsed["id"]),
        name=str(parsed["name"]),
        origin=str(parsed["origin"]),
        source=source,
    )
    if bundle != parsed["bundle"]:
        return {"ok": False, "reason": "bundle_mismatch"}
    return {"ok": True, "source": source, **parsed}
