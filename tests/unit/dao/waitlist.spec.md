# Spec — `app/dao/waitlist.py`

> **Status:** APPROVED (2026-11-03; nothing open)
> **Source commit:** e48a092

> **Review round 2026-11-03.** BUG-1410 and BUG-1411 stand from house rules (the tie-break of BUG-1411 follows BUG-1210). No question needed an answer.

> **Base behaviour** is in `tests/unit/dao/base.spec.md` and is not restated.
>
> **Standing decisions applied here (not asked again):** a missing `ORDER BY` is a bug, and no order recipe counts as deterministic unless it ends in `id`.
>
> **Verified by running** (throwaway scripts `facts.py`, `v_misc.py`, harness `h.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\wsdao\`, each in one transaction rolled back against `marker_test`; nothing committed): the table's columns, defaults and constraints; `create_signup` with untrimmed and empty names, a taken email, the same email in capitals (accepted), a missing keyword, over-long `first_name` and `source`, `wants_product_updates=None`; `get_by_email` with other case and a space; `update_status` with a valid, a free-text and a 21-character status; `list_signups` searching `a_b` (matched `axb` too), `p%q`, `%`, `" big@"`, `"BIG"`, `"   "`, `""`; the `wants_product_updates=False` and status filters; `total` against a short page; `limit=0`, negative `limit`; that rows written in one transaction share one `created_at`; the SQL (`ORDER BY created_at DESC` only); `get` with a positional id; `get_by_workspace` on this model. **Not run:** anything over HTTP; the intended behaviour of the bug rules.

## Review
> All answered; nothing pending.

### Quick list — all answered
| # | What the code does today, in plain words | Answer | Decided by |
|---|---|---|---|
| — | No question of this DAO | — | — |

Decided by house rules: `%` and `_` in the search act as wildcards (BUG-1410, HR-8); signups with one timestamp come back in no fixed order (BUG-1411, HR-6).

### House-rule violations — applied automatically

- **HR-8** `list_signups` R2 — the search text goes into `ILIKE '%…%'` unescaped. Verified: `a_b` also matches `axb@x.com`; `%` alone matches every row.
**Answer:** bug — per HR-8 (house rule)
**Resolution:** BUG-1410 (pattern `unescaped-like-wildcards`). `%`, `_` and `\` in the search are matched literally. Rules: `list_signups` R2.
- **HR-6** `list_signups` R5 — `ORDER BY created_at DESC` only. `created_at` is the database's `now()`, the start of the transaction, so rows written together share it (verified: three rows, one value); on a tie the order is whatever the database produces and paging can repeat or skip a signup. Intended (BUG-1210 precedent): `created_at` descending, then `id` descending, before `skip` / `limit`.
**Answer:** bug — per HR-6 (house rule)
**Resolution:** BUG-1411 (pattern `tied-timestamp-no-tiebreak`). Rules: `list_signups` R5.

Checked and **not** a new line here: **HR-1** — the DAO stores names as given; `WaitlistService.submit_signup` trims them, but `WaitlistSignupRequest` lets `"   "` through (`min_length=1` before the trim), so a blank name is stored `""`. That is the schema's and service's line (FU-1). **HR-2** — the email is unique in the database; case is handled by the service, which lower-cases before every lookup and insert. **HR-4** — no soft delete. **HR-5** — every filter is applied before `count()` and paging. **HR-7** — `GET /waitlist` already requires `1 <= limit <= 500` and `skip >= 0`. **HR-9, HR-10** — no audit columns; `update_status` is a plain overwrite by a platform admin. **HR-16** — the table is not workspace-scoped (platform data).

## Follow-ups for other reviews
> Nothing below is a rule of this DAO and no bug is logged for it here.

| # | Where it must be looked at | What | Came from |
|---|---|---|---|
| FU-1 | **Waitlist service / schema** (`app/services/waitlist_service.py`, `app/schemas/waitlist.py`) | (a) **HR-1:** `first_name` / `last_name` of `"   "` pass `min_length=1`, are trimmed by the service and stored `""`; the schema should strip first. (b) `submit_signup` swallows any exception when the email then exists (meant for the unique-email race); fine, but any other error on an existing email is hidden too. | HR-1 note |

## Overview
`WaitlistDAO` reads and writes `waitlist_signups`, the landing page's list of prospective customers. Platform-wide, not workspace-scoped. Callers: `WaitlistService.submit_signup` (public `POST /waitlist`: look up by email, create), `update_status` (`PATCH /waitlist/{id}/status`, waitlist admins), `list_signups` (`GET /waitlist`, waitlist admins). It never commits.

**Callables:** 4 specified · 1 not specified (+ inherited, base spec)
**Externals to mock:** none (`created_at` is the database's `now()`)
**Integration-only behavior:** none

**Model facts (table `waitlist_signups`):** `email` VARCHAR(320) NOT NULL, **unique (`waitlist_signups_email_key`, also `ix_waitlist_signups_email`), exact and case-sensitive**; `first_name`, `last_name` VARCHAR(100), `company_name` VARCHAR(200), `source` VARCHAR(64), `ip_hash` VARCHAR(64), all nullable; `wants_product_updates` BOOLEAN NOT NULL default `false` (Python and database); `status` VARCHAR(20) NOT NULL default `'PENDING'` (Python and database), indexed, no check; `created_at` **`timestamptz`** NOT NULL, database default `now()`. No soft delete.

**Notes for the test designer:** `from app.dao.waitlist import waitlist_dao`. The table is shared by every concurrently running test and not scoped: give every email a unique suffix, and assert on the rows you made (filter by a unique search term, or compare `total` relative to a count taken at the start). **BUG-1411:** rows made in one test share one `created_at` (one transaction), so a test of the tie-break builds three rows and expects `id` descending; today's order rests on physical order → **non-strict** xfail. **BUG-1410:** today's extra match is deterministic → **strict** xfail.

## Not specified
- `waitlist_dao` — module-level singleton, no logic.
- Inherited `BaseDAO` methods — covered by the base spec. Used: `get` (positional id, `WaitlistService.update_status`). `get_by_workspace` and `get_by_id_and_workspace` raise `AttributeError` (no `workspace_id`).

---

## `WaitlistDAO.get_by_email(db, *, email)`
**Shape:** get
**Persistence:** reads
**Visibility:** public (used by: `WaitlistService.submit_signup`, twice: before inserting, and after a failed insert, with the lower-cased trimmed email)

**Purpose:** The signup of one email, if any.

**Returns:** the `WaitlistSignup`, or `None`.

**Rules:**
- **R1.** Exact match: `zed@x.com` finds the row stored as `zed@x.com`; `Zed@x.com` or ` zed@x.com` gives `None`. The email is unique, so at most one row matches. An unknown email gives `None`.

**Errors:** none of its own.

**Side effects:** none

---

## `WaitlistDAO.list_signups(db, *, skip=0, limit=100, search=None, wants_product_updates=None, status=None)`
**Shape:** search
**Persistence:** reads
**Visibility:** public (used by: `WaitlistService.list_signups` ← `GET /waitlist`, with every argument)

**Purpose:** One page of signups, filtered, with the total.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `search` | `str \| None` | `None` or `""`: no filter; otherwise trimmed, lower-cased, matched as a substring of the email, case-insensitively |
| `wants_product_updates` | `bool \| None` | `None`: no filter; `True` / `False`: exact |
| `status` | `str \| None` | `None`: no filter; otherwise exact, case-sensitive |
| `skip` / `limit` | int, defaults `0` / `100` | not validated |

**Returns:** a tuple `(items, total)`: the page as a `list` of `WaitlistSignup`, and the number of rows matching the filters before paging.

**Rules:**
- **R1.** With no filter, every signup is counted and paged.
- **R2.** [BUG-1410] (HR-8) A search keeps the signups whose email contains the trimmed search text, ignoring case (`" big@"` and `"BIG"` find `BIG@Y.ORG`); `%`, `_` and `\` in the text are matched literally: `a_b` finds `a_b@x.com` and not `axb@x.com`; `%` alone finds only emails containing `%`. *(Today: `_` and `%` are wildcards: `a_b` also finds `axb@x.com`, `%` finds every row.)*
- **R2a.** A search of `""` applies no filter; a search of only spaces (`"   "`) becomes `""` after trimming and matches every row. Only the email is searched, not names or company.
- **R3.** `wants_product_updates=False` keeps only rows with `False` (not "no filter"); `True` only rows with `True`.
- **R4.** `status` keeps rows whose status is exactly that text: `"contacted"` does not find `"CONTACTED"`.
- **R5.** [BUG-1411] (HR-6) Newest first: `created_at` descending, then `id` descending, before `skip` / `limit`. *(Today: `created_at` only; rows with one `created_at` come back in no fixed order.)*
- **R6.** `total` counts every row matching the filters, not only the page: two items and a total of six are possible. `limit=0` gives `([], total)`. A negative `limit` or `skip` raises `DataError` (pgcode `2201W` / `2201X`).
- **R7.** Filters combine with AND.

**Errors:** negative `limit` / `skip` → `sqlalchemy.exc.DataError`.

**Side effects:** none

---

## `WaitlistDAO.create_signup(db, *, email, first_name, last_name, company_name, wants_product_updates, source, ip_hash)`
**Shape:** create
**Persistence:** writes
**Visibility:** public (used by: `WaitlistService.submit_signup`, with the email lower-cased and trimmed, names trimmed, a blank company as `None`, the IP hashed)

**Purpose:** Store a new signup.

**Returns:** the new `WaitlistSignup`, flushed (has `id`, `status = 'PENDING'`, `created_at`), not committed.

**Rules:**
- **R1.** One row is inserted with exactly the given values, nothing trimmed or changed (`" Z "` stays `" Z "`, `""` is stored). `status` is `'PENDING'`; `created_at` is the database's `now()` (an aware datetime).
- **R2.** `wants_product_updates=None` is stored as `False` (the default applies).
- **R3.** A taken email (exact text) raises `IntegrityError` (`UniqueViolation`, pgcode `23505`) at the flush. The same email in other capitals is accepted as a second row (the service lower-cases first).
- **R4.** A value longer than its column (`first_name` / `last_name` > 100, `company_name` > 200, `source` / `ip_hash` > 64, `email` > 320) raises `DataError` (pgcode `22001`).
- **R5.** All seven values are required keywords: leaving one out raises `TypeError`.

**Errors:** as R3–R5.

**Side effects:** one row inserted, flushed, not committed.

---

## `WaitlistDAO.update_status(db, *, signup, status)`
**Shape:** update
**Persistence:** writes
**Visibility:** public (used by: `WaitlistService.update_status` ← `PATCH /waitlist/{id}/status`, whose schema allows only `PENDING`, `CONTACTED`, `ACCEPTED`, `DECLINED`)

**Purpose:** Change a signup's follow-up status.

**Returns:** the same `WaitlistSignup`, flushed, not committed.

**Rules:**
- **R1.** `status` is set to the given text and flushed; nothing else changes. Any text up to 20 characters is accepted at the DAO (`"whatever"`); the same status again is accepted.
- **R2.** More than 20 characters raise `DataError` (pgcode `22001`) at the flush.

**Errors:** as R2.

**Side effects:** one row updated, flushed.

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 11–12 | exact email; `.first()` | `get_by_email` R1 |
| 25–27 | `if search:` truthy → strip, lower, `ILIKE` unescaped (BUG-1410) / `""`, `None` → none | `list_signups` R2, R2a |
| 28–29 | `is not None` → bool filter | `list_signups` R3 |
| 30–31 | `is not None` → exact status | `list_signups` R4 |
| 33 | count before paging | `list_signups` R6 |
| 34–40 | `created_at DESC` only (BUG-1411); offset / limit | `list_signups` R5, R6 |
| 54–65 | row from the arguments; flush: unique, length | `create_signup` R1–R5 |
| 70–73 | set status; flush | `update_status` R1, R2 |
| 76 | module singleton | Not specified |
