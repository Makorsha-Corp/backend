# Fix brief: dao-waitlist

## 1. Unit

| | |
|---|---|
| Slug | `dao-waitlist` |
| Source file | `app/dao/waitlist.py` |
| Worktree | `E:\Projects\Makorsh-Corp\bugfix-worktrees\dao-waitlist` |
| Branch | `bugfix/dao-waitlist` (from `origin/main`) |
| Risk | `normal` (BUG-1411 `tied-timestamp-no-tiebreak` is on the trivial list; BUG-1410 `unescaped-like-wildcards` is not). Not money, stock, order workflow or security: the bugs are about list order and search text in the platform's waitlist. Who may call `GET /waitlist` is decided outside this file and does not change. |

## 2. Bugs

### BUG-1410: `%` and `_` in the waitlist search act as wildcards
- **Pattern:** `unescaped-like-wildcards`
- **Where:** `WaitlistDAO.list_signups`; reached through `GET /waitlist`.
- **Today:** Search text goes into `ILIKE '%…%'` unescaped: `a_b` also finds `axb@x.com`, `%` finds every signup.
- **Intended:** HR-8: `%`, `_` and `\` matched literally.
- **Example:** A waitlist admin searches `a_b`. Today `axb@x.com` is found as well as `a_b@x.com`; after the fix only `a_b@x.com` is. Searching `p%q` finds `p%q@x.com` and not `pzzq@x.com`. Searching `c\d` finds only an email that really contains `c\d` (one backslash), and not `cd@x.com`.
- **Codebase convention:** other DAOs escape `ILIKE` input with a private `_escape_ilike` helper in the same file (for example `app/dao/help_ticket.py`: backslash doubled first, then `%` and `_` prefixed with a backslash, with `\` as the escape character). Follow that convention inside `app/dao/waitlist.py`. A shared helper for all DAOs is a later follow-up, not this unit.

### BUG-1411: Waitlist signups with one timestamp come back in no fixed order
- **Pattern:** `tied-timestamp-no-tiebreak`
- **Where:** `WaitlistDAO.list_signups`; reached through `GET /waitlist`.
- **Today:** `ORDER BY created_at DESC` only; `created_at` is the transaction's `now()`, so ties occur and paging can repeat or skip a signup.
- **Intended:** HR-6 (BUG-1210 precedent): `created_at` descending, then `id` descending, before `skip` / `limit`.
- **Precedent BUG-1210, in words:** a list ordered newest first by a date or time keeps that first key and adds `id` descending as the last key, applied before paging.
- **Why ties happen:** `created_at` is the database's `now()`, the start time of the transaction, so signups written in one transaction share it.

## 3. Intended behaviour (spec rules, copied)

Facts for the whole file: table `waitlist_signups`, the landing page's list of prospective customers; platform-wide, not workspace-scoped. Columns: `email` VARCHAR(320) NOT NULL, unique (`waitlist_signups_email_key`, also index `ix_waitlist_signups_email`), exact and case-sensitive; `first_name`, `last_name` VARCHAR(100), `company_name` VARCHAR(200), `source` VARCHAR(64), `ip_hash` VARCHAR(64), all nullable; `wants_product_updates` BOOLEAN NOT NULL default `false` (Python and database); `status` VARCHAR(20) NOT NULL default `'PENDING'` (Python and database), indexed, no check; `created_at` timestamptz NOT NULL, database default `now()`. No soft delete. Callers: `WaitlistService.submit_signup` (public `POST /waitlist`: look up by email, create), `WaitlistService.update_status` (`PATCH /waitlist/{id}/status`, waitlist admins), `WaitlistService.list_signups` (`GET /waitlist`, waitlist admins). The class never commits. Every parameter after `db` is keyword-only.

### `WaitlistDAO.list_signups(db, *, skip=0, limit=100, search=None, wants_product_updates=None, status=None)`
Used by `WaitlistService.list_signups` ← `GET /waitlist`, with every argument. One page of signups, filtered, with the total.

Inputs: `search` (`str | None`): `None` or `""` means no filter; otherwise trimmed, lower-cased, matched as a substring of the email, case-insensitively. `wants_product_updates` (`bool | None`): `None` no filter; `True` / `False` exact. `status` (`str | None`): `None` no filter; otherwise exact, case-sensitive. `skip` / `limit`: ints, defaults `0` / `100`, not validated here.

Returns: a tuple `(items, total)`: the page as a `list` of `WaitlistSignup`, and the number of rows matching the filters before paging.

- **R1.** With no filter, every signup is counted and paged.
- **R2.** [BUG-1410] (HR-8) A search keeps the signups whose email contains the trimmed search text, ignoring case (`" big@"` and `"BIG"` find `BIG@Y.ORG`); `%`, `_` and `\` in the text are matched literally: `a_b` finds `a_b@x.com` and not `axb@x.com`; `%` alone finds only emails containing `%`. *(Today: `_` and `%` are wildcards: `a_b` also finds `axb@x.com`, `%` finds every row.)*
- **R2a.** A search of `""` applies no filter; a search of only spaces (`"   "`) becomes `""` after trimming and matches every row. Only the email is searched, not names or company.
- **R3.** `wants_product_updates=False` keeps only rows with `False` (not "no filter"); `True` only rows with `True`.
- **R4.** `status` keeps rows whose status is exactly that text: `"contacted"` does not find `"CONTACTED"`.
- **R5.** [BUG-1411] (HR-6) Newest first: `created_at` descending, then `id` descending, before `skip` / `limit`. *(Today: `created_at` only; rows with one `created_at` come back in no fixed order.)*
- **R6.** `total` counts every row matching the filters, not only the page: two items and a total of six are possible. `limit=0` gives `([], total)`. A negative `limit` or `skip` raises `DataError` (pgcode `2201W` / `2201X`).
- **R7.** Filters combine with AND.
- Errors: negative `limit` / `skip` → `sqlalchemy.exc.DataError`. Side effects: none.

### Other methods (not in a bug; must not change)

**`WaitlistDAO.get_by_email(db, *, email)`**, used by `WaitlistService.submit_signup` (before inserting, and after a failed insert, with the lower-cased trimmed email). Returns the `WaitlistSignup` or `None`.
- **R1.** Exact match: `zed@x.com` finds the row stored as `zed@x.com`; `Zed@x.com` or ` zed@x.com` gives `None`. The email is unique, so at most one row matches. An unknown email gives `None`. Errors: none. Side effects: none.

**`WaitlistDAO.create_signup(db, *, email, first_name, last_name, company_name, wants_product_updates, source, ip_hash)`**, used by `WaitlistService.submit_signup`. Returns the new `WaitlistSignup`, flushed (has `id`, `status = 'PENDING'`, `created_at`), not committed.
- **R1.** One row is inserted with exactly the given values, nothing trimmed or changed (`" Z "` stays `" Z "`, `""` is stored). `status` is `'PENDING'`; `created_at` is the database's `now()` (an aware datetime).
- **R2.** `wants_product_updates=None` is stored as `False` (the default applies).
- **R3.** A taken email (exact text) raises `IntegrityError` (`UniqueViolation`, pgcode `23505`) at the flush. The same email in other capitals is accepted as a second row (the service lower-cases first).
- **R4.** A value longer than its column (`first_name` / `last_name` > 100, `company_name` > 200, `source` / `ip_hash` > 64, `email` > 320) raises `DataError` (pgcode `22001`).
- **R5.** All seven values are required keywords: leaving one out raises `TypeError`.
- Side effects: one row inserted, flushed, not committed.

**`WaitlistDAO.update_status(db, *, signup, status)`**, used by `WaitlistService.update_status` ← `PATCH /waitlist/{id}/status` (whose schema allows only `PENDING`, `CONTACTED`, `ACCEPTED`, `DECLINED`). Returns the same `WaitlistSignup`, flushed, not committed.
- **R1.** `status` is set to the given text and flushed; nothing else changes. Any text up to 20 characters is accepted at the DAO (`"whatever"`); the same status again is accepted.
- **R2.** More than 20 characters raise `DataError` (pgcode `22001`) at the flush.

**Inherited `BaseDAO` methods** stay as they are. `get` (positional id) is used by `WaitlistService.update_status`. `get_by_workspace` and `get_by_id_and_workspace` raise `AttributeError` on this model (no `workspace_id`). The module-level singleton `waitlist_dao` stays.

## 4. Rules that apply

- **HR-6. Every paged or top-N result has a stable order.** No order recipe counts as deterministic unless it ends in `id`. Where a list already has a chosen first key (here: `created_at` newest first), keep it and add `id` after it (here descending, to match newest first).
- **HR-8. Search text is literal.** Text placed in `LIKE` / `ILIKE` patterns is escaped: `%` and `_` match literally. For this unit the spec also requires the escape character itself (`\`) to match literally.
- **HR-5 (keep):** every filter is applied before the count and before paging.
- **HR-16:** not applicable; the table is platform data, not workspace-scoped.
- No owner answer (OQ-n) touches these bugs. (OQ-9 is about the waitlist form's bot check, in the service; not this file.)

## 5. Scope

- May change: `app/dao/waitlist.py` only.
- No migration, no schema or API change. Method signatures and return types stay as they are.

## 6. Out of scope (leave alone)

- `app/schemas/waitlist.py`: BUG-1579 (waitlist names of only spaces are accepted and stored empty).
- `app/services/waitlist_service.py`: BUG-1580 (an unreadable answer from the bot check is an internal error).
- `app/core/waitlist_admin.py`: BUG-540 (waitlist admin access granted by an unverified email), BUG-541 (refusal message reveals server configuration).
- A shared `ILIKE` escape helper for all DAOs (follow-up F8): not this unit; keep the helper private to this file.
