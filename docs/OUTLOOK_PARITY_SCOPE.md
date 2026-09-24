# rpMail — full Outlook feature parity scope

From-scratch **Restore Privacy** variant (not a Microsoft Outlook clone).  
Status: **implemented** | **partial** | **planned**

## Pillars (required)

| Pillar | Outlook analogue | Status | Shipped path |
|--------|------------------|--------|--------------|
| **Mail** | Mail | **implemented** | `rpmail.models`, `store`, `protocols` (SMTP/IMAP/POP3 fakes), compose/send/import |
| **Calendar** | Calendar | **implemented** | `rpmail.calendar` events create + JSON persist |
| **Contacts** | People | **implemented** | `rpmail.contacts` create + lookup |
| **Tasks** | To Do / Tasks | **implemented** | `rpmail.tasks` create + complete + persist |

## Extended Outlook matrix (honest full-parity scope)

| Feature area | Status | Notes |
|--------------|--------|-------|
| Multi-account mailboxes | partial | Account model + store; no live Exchange |
| Folders (INBOX/Sent/Drafts/custom) | partial | Folder field on messages; folder list helpers |
| Compose / Reply / Forward models | partial | Compose + send path; reply/forward draft helpers |
| SMTP send | implemented | Interface + in-memory sender + stdlib SMTP |
| IMAP import | implemented | Interface + in-memory importer + stdlib IMAP |
| POP3 import | implemented | Interface + in-memory importer + stdlib POP3 |
| Continuum vort1 client | implemented | `continuum/vortice.json` (`hook: continuum.mail`). Install string `vort1:TODO-rpmail` until smoke. See docs/HANDOFF.md |
| Search / rules / categories | planned | Domain hooks reserved |
| Attachments | planned | Message attachment list scaffold optional |
| Signatures / templates | planned | |
| Shared calendars / free-busy | planned | No Graph/Exchange |
| Recurring events (RRULE) | partial | Basic recurrence string field |
| Contact groups / distribution lists | planned | |
| Task lists / priorities | partial | Priority + complete flag |
| Company mailbox create | implemented | **Moderator-only** (`rpmail.roles`) |
| Encryption / S/MIME | planned | Product privacy path later |
| Desktop GUI parity with Outlook ribbon | planned | Domain+CLI first (this cycle) |
| .pst/.ost / MAPI / Microsoft Graph | planned (non-goal this cycle) | No proprietary MS protocol |

## Product identity

- **Name:** rpMail  
- **Family:** Restore Privacy Suite  
- **Variant:** from-scratch Outlook-class PIM (Mail · Calendar · Contacts · Tasks)
