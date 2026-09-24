# rpMail Continuum handoff

Client-only mail. No Solidity, no on-chain mailbox, no SHE mint, no Continuum preinstall.

## What tip Continuum does today

Shear Continuum (wallet pin **0.48**, `wallet/lib/main.dart` `_vortex`) installs a third-party vortice like this:

1. Vortex → Add new vortice → paste `vort1.`
2. `downloadVorticeFromOrigin` fetches the origin named in the key.
3. `verifyVorticeDownload` checks `vorticeBundleHash` (`crypto/vortex.js`, `wallet/lib/shear_vortex.dart`).
4. The roster stores `id`, `name`, `origin`, `bundle`, and `source`.

The pane for that chip shows the display name, program id, origin, the line that third-party vortice cannot mint SHE, and Remove. `parseVorticeSource` exists and is unused. There is no WebView. The example body in wallet tests is JSON (`{"id":"…","pane":"ok"}`). A browser page could not open IMAP, POP3, or SMTP sockets even if it were shown.

rpMail therefore publishes a JSON body with `hook: "continuum.mail"`. Opening it as in-wallet mail needs a host bridge in shear-testnet. That bridge is not a preinstall: the mail pane appears only after a pasted key whose downloaded body declares the hook.

## Origin path

Serve the exact bytes of [`continuum/vortice.json`](../continuum/vortice.json).

| Field | Value |
| --- | --- |
| programId | `rpmail-v1` |
| display name | `rpMail` |
| repo path | `continuum/vortice.json` |
| body sha256 | see `continuum/vortice.sha256` (sha256 of those bytes) |
| hook | `continuum.mail` |
| install | `vort1-paste-only` (`preinstall: false`) |
| example origin | `https://rpmail.example/continuum/vortice.json` (documentation only) |

Do not point the key at `vortices.shear.digital`. Do not edit the live gallery. A changed body needs a new key; the sha256 pin test fails if the file and `continuum/vortice.sha256` diverge.

## Install string until smoke is not-refuted

```
vort1:TODO-rpmail
```

That string is not a deploy key (`parseVorticeKey` rejects it). Do not paste it. Do not replace it with a minted key in this repo before smoke has failed to refute the bridge.

## Mint (operator, after the origin is serving the pinned bytes)

On a Shear node, with `source` equal to the file bytes (not a copy you re-encoded):

```
store.mintVorticeDeployKey({
  programId: 'rpmail-v1',
  name: 'rpMail',
  origin: 'https://<host-you-control>/continuum/vortice.json',
  source: exactBytesOfContinuumVorticeJson,
})
```

The same fields are accepted by `POST /api/vortex/mint`. If the origin is already live, `store.mintVorticeFromOrigin({ programId, name, origin })` fetches and pins those bytes.

You receive `vort1.` + base64url JSON. The node stores origin and bundle hash. It does not keep the dapp body. It does not mint SHE. `rpmail-v1` is not a reserved program id.

`rpmail.continuum.mint_vortice_deploy_key` builds the same key locally so tests can match `crypto/vortex.js`. It does not call a node.

Holders: Vortex → Add new vortice → paste the key. They never type the URL.

## What the client does

- Configure IMAP and/or POP3 (host, port, TLS, user, mailbox secret) plus SMTP.
- List folders (IMAP `LIST`; POP3 is INBOX only), list messages, read the body.
- Send via SMTP. A Sent copy is kept in the local mailbox store. Live IMAP APPEND is not done.
- Company mailbox creation stays moderator-only (`rpmail.roles`). Users and staff are refused before a secret is stored.

TLS: IMAP 993, POP3 995, and SMTP 465 are implicit TLS. Other ports with TLS use STARTTLS. `tls: false` is cleartext for a host you mean to use that way (the loopback test).

## Credential isolation

| Stays here | Never receives mail secrets |
| --- | --- |
| `CredentialVault` (SDK) | `MailboxStore` / `protocol_prefs` |
| `rpmail-secrets.json` next to the Continuum session (bridge) | `shewall.bin`, session vortices, Spendable nanos |

The vault document has no `seedHex` and no `spendableNanos`. Saving a mailbox does not change a SHE balance. Logs and transport errors redact the secret. rpMail does not ask for a Shear password or a shewall dump.

## Host bridge

Tip Continuum cannot run network mail from the vortice body alone. The bridge patch is [`continuum/shear-testnet-mail-bridge.patch`](../continuum/shear-testnet-mail-bridge.patch). It applies on shear-testnet `main` (`git apply` from the repo root) and touches only these surfaces:

- `wallet/lib/shear_mail_bridge.dart` — IMAP/POP3/SMTP on `dart:io`, secret file, company-role gate
- `wallet/lib/shear_mail_pane.dart` — in-wallet mail UI
- `wallet/lib/main.dart` — if `hook` is `continuum.mail`, show that pane under the existing chip (name, origin, cannot-mint, Remove stay)
- `wallet/test/mail_bridge_test.dart`

No invent, pool, or reconstruct edits. No default chip. Reserved program ids stay rejected. The Vortex subtree in `main.dart` does not contain the word Password (wallet tests forbid it). The mailbox field is labeled as a mailbox secret, not the Shear wallet secret.

This agent could not open the shear-testnet pull request. `cursor[bot]` is denied push on `rgsneddon/shear-testnet` (HTTP 403, `permissions.push` false). Apply the patch locally and open that PR from an account that can push. `flutter test test/mail_bridge_test.dart` passed here (loopback IMAP/POP3/SMTP, secret isolation, and the pasted-pane widget). The older “Vortex deploys a third-party dapp” widget test also leaves an Argon2 fake timer pending on unmodified `main` in this environment; that failure is not from the patch.

## Known gaps

- Gallery key remains `vort1:TODO-rpmail` until smoke is not-refuted.
- No WebView and no HTML dapp. The body is the JSON hook the bridge understands.
- No IMAP IDLE, no server-side Sent APPEND, no attachments, no S/MIME.
- POP3 has no folders besides INBOX.
- Large mailboxes are capped (default 50 messages per list).
- Mail secrets are device-local. Importing `shewall.bin` does not restore them, on purpose.
- Moderator is an rpMail role inside the pane, not a Shear identity.
