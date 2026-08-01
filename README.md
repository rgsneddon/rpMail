# rpMail

**Restore Privacy Mail** — privacy-focused mail client SDK surface for rpOS /
Restore Privacy Suite commercial deployments.

## Architecture

```
rpmail/
  models.py      # Account, Message, Folder (pure domain)
  roles.py         # User roles; company-email gate (moderator only)
  protocols.py     # SMTP / IMAP / POP3 import interfaces + in-memory fakes
  store.py         # In-process mailbox store (serialize round-trip)
  __main__.py      # CLI entry: smoke / version / demo
```

## Company email policy

Creating **company** addresses is **moderator-only**. Staff/users may import and
compose personal mail; company-domain mailbox creation requires role
`moderator`.

## Run

```bash
python3 -m rpmail --smoke
python3 -m rpmail --version
python3 -m unittest discover -s tests -v
```

## Licence

MIT — see [LICENSE](LICENSE).

Not a Gmail/Outlook clone; structural completeness for commercial per-requirements builds.
