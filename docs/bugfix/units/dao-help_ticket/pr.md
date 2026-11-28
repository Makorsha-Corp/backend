## Fix: support inbox search treats `%` and `_` as plain text, help ticket lists keep a fixed order, and ticket numbers use the UTC year

**Fixes BUG-1441, BUG-1442 and BUG-1443.** One file (`app/dao/help_ticket.py`). No database change, no API shape change.

Not marked "Good to auto-merge": the search fix (BUG-1443, `unescaped-like-wildcards`) is not yet a pattern on the trivial list, so the owner should look at it.

---

### What was wrong

**1. Searching the support inbox for `%` or `_` found every ticket (BUG-1443). This is the one people notice.**

The platform support inbox search box looks in each ticket's title, ticket number, description and workspace name. The database treats `%` as "anything" and `_` as "any one character", and the search text was passed through unchanged.

*Example:* a support agent searches for `HELP-2026_001`. Instead of that one ticket they also get `HELP-2026-001`, `HELP-2026X001` and so on. Searching `50%` (from a ticket titled "Discount 50% not applied") lists every ticket that contains "50" anywhere. A search for just `_` or `%` listed the whole inbox.

**2. Tickets opened at the same moment came back in a different order each time (BUG-1442)**

Both the workspace's help ticket list and the platform inbox sort newest first, but nothing decided the order between tickets with the same creation time. The database could return them in any order, so moving to the next page could show a ticket twice or skip one.

**3. The year in a ticket number came from the server's local clock (BUG-1441)**

Ticket numbers look like `HELP-2026-014`. The year came from the server's local time, while the ticket's creation time is stored in UTC. Around New Year the two disagree.

*Example:* on a server set to Dhaka time (UTC+6), a ticket opened on 31 Dec 2026 at 20:00 UTC (2:00 on 1 Jan in Dhaka) was numbered `HELP-2027-…` while its creation date said 2026.

---

### What changed

All in `app/dao/help_ticket.py`:

```diff
  # ticket number year
- current_year = datetime.now().year
+ current_year = utcnow().year                          # the UTC year, same clock as created_at

  # both ticket lists
- query.order_by(HelpTicket.created_at.desc())
+ query.order_by(HelpTicket.created_at.desc(), HelpTicket.id.desc())   # tie-break on id

  # platform inbox search
- term = f"%{search.strip()}%"
+ term = f"%{self._escape_ilike(search.strip())}%"     # \ then % and _ escaped
- HelpTicket.title.ilike(term)
+ HelpTicket.title.ilike(term, escape="\\")            # same for ticket number, description, workspace name
```

The rules behind it: house rule HR-6 (every list ends its sort with `id`), house rule HR-8 (search characters `%`, `_` and `\` match literally), and the owner-delegated decision that document-number years come from UTC (as for batch numbers, BUG-1334). The small escape helper is the same one the account invoice search already uses.

### What you'll notice

- Searching the support inbox for text with `%`, `_` or `\` finds only tickets that really contain those characters. Ordinary searches are unchanged, still case-insensitive, and an empty or spaces-only search still lists everything.
- Paging through help tickets no longer repeats or skips tickets; tickets with the same time show the most recently created first.
- Ticket numbers opened around midnight on 31 December get the UTC year. Nothing changes the rest of the year.
- Deliberately unchanged: how the next number is picked (two tickets opened at the same instant can still collide; that is BUG-1440, left for a later round because it needs a locking decision).

### What to look at when reviewing

- **The copied escape helper.** It is a copy of the one in the account invoice DAO, because this fix may only touch one file. About nine other searches still have the same problem; a later shared helper should replace the copies. Object if you'd rather have the shared helper first.
- **The search covers all four fields** (title, ticket number, description, workspace name) with the same escaped text.
- **BUG-1440 is out of scope**, as above.

---

<details>
<summary>Pipeline checks (for the record)</summary>

- **Impact review:** callers are the help ticket manager and service, behind `GET/POST /help-tickets/` and `GET /platform/help/tickets`. None re-sorts or relies on wildcard search. The attachment code uses only the unchanged lookup by id. No new joins; the workspace filter is unchanged.
- **Contract:** same response shape and messages. Only values change (search matches, order on ties, the year on New Year's Eve). The frontend (`PlatformSupportPage.tsx`, `HelpPage.tsx`) needs no change, so there is no frontend PR.
- **Tests:** the 13 tests marked as known failures for these bugs (help ticket DAO and service) now pass, and their markers are removed. Every other test in the full suite had the same result before and after (flip check CLEAN, base `614bbce`).
- **Database:** no migration; one Alembic head.
- **Commits:** `7a24870` (fix; pushed).

</details>

## Code review

**PASS**: 0 blockers, 0 majors, 1 minor, 2 nits. This was an independent strict review; the reviewer didn't see the test results. Details are in `docs/bugfix/units/dao-help_ticket/review-1.md`.

For you to decide (none change behaviour):
- **Minor:** the ticket year comes from the app's UTC clock, but `created_at` comes from the database transaction's start time. A request that starts just before midnight UTC on New Year and takes its number just after could get `HELP-2027-…` with a 2026 `created_at`. That's exactly what the brief asks for, but the code comment that says the two always agree overstates it.
- Nit: the search-escape helper is copied from `app/dao/account_invoice.py`. A shared helper is planned as a later cleanup.
- Nit: the helper could be written as one expression (style only).

🤖 Generated with [Claude Code](https://claude.com/claude-code)
