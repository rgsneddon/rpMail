# rpMail

**Restore Privacy Mail** — IMAP, POP3, and SMTP client for the Shear Continuum wallet.
Installed only by pasting a `vort1.` deploy key. No Solidity. No Continuum preinstall.

Outlook-class pillars (from-scratch variant): Mail · Calendar · Contacts · Tasks — see [docs/OUTLOOK_PARITY_SCOPE.md](docs/OUTLOOK_PARITY_SCOPE.md).

Continuum install, mint, and known gaps: [docs/HANDOFF.md](docs/HANDOFF.md).

## Architecture

```
continuum/vortice.json   # exact bytes a host origin must serve
rpmail/
  models.py              # Account, Message, Folder
  roles.py               # Company-email gate (moderator only)
  protocols.py           # SMTP / IMAP / POP3 interfaces + in-memory fakes
  live.py                # stdlib IMAP / POP3 / SMTP (implicit TLS or STARTTLS)
  client.py              # configure, list, read, send
  credentials.py         # secrets vault, isolated from shewall and Spendable
  continuum.py           # vort1 hash + local key builder (does not mint SHE)
  store.py               # mailbox + PIM store
  __main__.py            # CLI: smoke / version / parity
```

## Company email policy

Creating **company** addresses is **moderator-only**. Staff and users may configure personal mail. Company-domain mailbox creation requires role `moderator` (or `admin`). That role is an rpMail actor. It is not the Shear wallet password.

## Credentials

Mailbox passwords and app passwords live in `CredentialVault`. They are not written into `MailboxStore`, `protocol_prefs`, a SHE balance, or a shewall export. The in-wallet file is `rpmail-secrets.json` beside the session, not inside `shewall.bin`.

## Live config path

`MailClient` uses the in-memory fakes when they are passed in. With no fakes, it opens the endpoint stored on the account:

| Protocol | tls + well-known port | tls + other port | tls false |
|----------|----------------------|------------------|-----------|
| IMAP | 993 implicit TLS | STARTTLS | cleartext |
| POP3 | 995 implicit TLS | STARTTLS | cleartext |
| SMTP | 465 implicit TLS | STARTTLS (587) | cleartext |

Certificate checks stay on for TLS. Cleartext is for a private or loopback host you choose.

## Continuum body

`continuum/vortice.json` is the pinned vortice body (`hook: continuum.mail`, `preinstall: false`). Tip Continuum 0.48 does not render `source` and cannot open IMAP sockets from a page, so the wallet needs the mail host bridge described in the handoff. Until smoke is not-refuted the install string stays `vort1:TODO-rpmail`. Do not mint a gallery key and do not change `vortices.shear.digital`.

## Run

```bash
python3 -m rpmail --smoke
python3 -m rpmail --version
python3 -m unittest discover -s tests -v
```

## Licence

MIT — see [LICENSE](LICENSE).
