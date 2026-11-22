# Spec — `app/dao/attachment_ledger.py`

> **Status:** APPROVED (2026-11-02; nothing open)
> **Source commit:** e48a092

> **Review round 2026-11-02.** **Delegated:** Q1 accepted as pre-filled, decided by Claude under the reviewer's delegation (2026-11-02). It is not the owner's own answer. BUG-640 stands from the house rule.

> **Base behaviour** is in `tests/unit/dao/base.spec.md` and is not restated. This DAO overrides `get_by_workspace` with its own signature. The manager's view is `LedgerManager.get_attachment_ledger` in `tests/unit/managers/ledger_manager.spec.md`.
>
> **Standing decisions applied here (not asked again):** a missing `ORDER BY` is a bug, and no order recipe counts as deterministic unless it ends in `id`. Ledgers are history and stay complete whatever happens to the parent. HR-16: a row linking to another workspace's row is invalid data.
>
> **Verified by running** (throwaway scripts `cat1.py`, `v4.py`, harness `h.py`, `w.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\childdao\`, each transaction rolled back against `marker_test`; nothing committed): the table's columns, constraints, indexes; order; a tie after the lower `id` was updated; `attachment_id` `0`; `entity_type` and `transaction_type` as `""`, another case, unknown; both date bounds at the exact moment; a reversed range; a bound with no time zone under `America/New_York`, `UTC`, `Asia/Dhaka`; 105 rows; `limit=0`; `skip` past the end; negative values; another workspace; a soft-deleted attachment. **Not run:** anything over HTTP; the intended behaviour of the bugs named here.

## Review
> All answered; applied 2026-11-02.

### Quick list — all answered
| # | What the code does today, in plain words | Answer | Decided by |
|---|---|---|---|
| Q1 | A date with no time zone is read in the database's time zone | bug — it means UTC (BUG-1281) | Claude, delegated |

Decided by a house rule: rows with one stamp come back in no fixed order (BUG-640, HR-6).

### House-rule violations — applied automatically

- **HR-6** `get_by_workspace` R8 — ordered by `performed_at` alone. Verified: two rows with one stamp came back higher `id` first once the lower `id` was updated. Intended: `performed_at` descending, then `id` descending.
**Answer:** bug — per HR-6 (house rule)
**Resolution:** BUG-640 already holds this (logged at `get_attachment_ledger`). No new ID; the line to fix is in this DAO.

Checked and **not** a new line here: **HR-7** — `GET /ledgers/attachments/` has no lower bound on `limit`: BUG-642. **HR-5** — every filter is in the query. **HR-8** — no `LIKE`. **HR-4** — no soft-delete column; the attachment is a parent and this is a ledger, so its rows stay (R13). **HR-9, HR-10** — the DAO only reads. **HR-15** — no money. **HR-16** — the workspace filter applies to the row; `attachment_id` alone reaches no other workspace (R2). **`end_date` as a plain date** becoming midnight is BUG-991, at the endpoint.

### Precedent matches — confirmed

### Q1. A date with no time zone is read in the database's time zone — 🐞 BUG-1281
**Background:** `performed_at` is a real point in time (`timestamptz`), unlike most stamps here, which are naive UTC. `GET /ledgers/attachments/` takes `start_date` and `end_date` as date-times, and a value with no zone arrives naive. Postgres reads a naive value in the session's `TimeZone` setting, which is whatever the server is set to. The test database is on `America/New_York`. BUG-992 and BUG-1102 settled, under the reviewer's delegation, that a result must not depend on that setting. Other ledgers use UTC days (machine activity Q3).
**What happens today:** The same request gives different rows on servers set to different zones. (Verified.)
**Example:** An entry at 12:00 UTC and `end_date=2026-03-05T12:00:00`: under `UTC` the entry is found, under `Asia/Dhaka` it is left out, and under `America/New_York` an entry at 13:00 UTC is found as well.
**Rules affected:** `get_by_workspace` R7a
**Suggested answer:** the answer below. On a server set to UTC, nothing changes. Not an OWNER item: no money.
**Answer:** bug — per BUG-992 precedent: a bound with no time zone means UTC, whatever the database's `TimeZone`; a bound with a zone stays exact
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-02): BUG-1281 (pattern `aware-datetime-against-naive-column`, as BUG-992; here the mismatch runs the other way). Rules: `get_by_workspace` R7a.

## Overview
`AttachmentLedgerDAO` reads `attachment_ledger`, the append-only history of attachments: pending, ready, failed, deleted. Rows are written by `AttachmentManager._append_attachment_ledger` through inherited `create`. The one reader is `LedgerManager.get_attachment_ledger`, reached through `GET /ledgers/attachments/`, which passes every argument.

**Callables:** 1 specified · 2 not specified
**Externals to mock:** none
**Integration-only behavior:** none

**Model facts (table `attachment_ledger`):** `workspace_id` FK CASCADE, `attachment_id` FK RESTRICT, `transaction_type` String(16), `file_name`, `mime_type`, `file_size` BigInteger are NOT NULL; `entity_type` String(64), `entity_id` nullable; `performed_at` `timestamp with time zone` NOT NULL, database default `now()`. Append-only is a convention: nothing in the database enforces it.

**Notes for the test designer:**
- `from app.dao.attachment_ledger import attachment_ledger_dao`. `Attachment(workspace_id, file_name, mime_type, file_size, uploaded_by)`.
- **Always give `performed_at` and the bounds as aware UTC values**, except for the R7a cases. The test database's `TimeZone` is `America/New_York`.
- R7a: `db.execute(text("SET LOCAL TIME ZONE 'Asia/Dhaka'"))` inside the test; the rollback resets it. Under `Asia/Dhaka` and `America/New_York` the case is a strict xfail. Under `UTC` it passes today and needs no xfail.
- BUG-640: two rows with one `performed_at`, update the lower `id`, flush, `db.expire_all()`. **Non-strict** xfail, assertion not weakened.
- Wrap negative paging in `db.begin_nested()`.

## Not specified
- `attachment_ledger_dao` — module-level singleton, no logic.
- Inherited `BaseDAO` methods — covered by the base spec. Inherited `update` and `remove` have no caller.

---

## `AttachmentLedgerDAO.get_by_workspace(db, *, workspace_id, attachment_id=None, entity_type=None, start_date=None, end_date=None, transaction_type=None, skip=0, limit=100)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `LedgerManager.get_attachment_ledger`)

**Purpose:** A workspace's attachment history, newest first, with filters.

**Returns:** a `list` of `AttachmentLedger` (possibly empty).

**Rules:**
- **R1.** Returns only rows of that workspace. Another or unknown workspace returns `[]`.
- **R2.** `attachment_id` keeps that attachment's rows, inside the workspace. `0` is a real filter and returns `[]`. `None` applies no filter.
- **R3.** `entity_type` keeps exact matches, case-sensitive. `None` and `""` apply no filter. An unknown value or another case returns `[]`. A row with `entity_type` `NULL` is kept only with no filter.
- **R4.** `transaction_type` works the same way: exact; `None` and `""` no filter.
- **R5.** `start_date` keeps rows at or after that moment; a row at exactly that moment is kept.
- **R6.** `end_date` keeps rows at or before that moment; a row at exactly that moment is kept. `start_date` after `end_date` returns `[]`, with no error. `start_date` = `end_date` keeps rows at that moment.
- **R7.** A bound with a zone is an exact moment, whatever the session's `TimeZone`.
- **R7a.** [BUG-1281] A bound with no zone means UTC, whatever the session's `TimeZone`. With an entry at 12:00 UTC and 13:00 UTC, and naive `end_date` 12:00, only the 12:00 entry is kept, under `UTC`, `Asia/Dhaka` and `America/New_York` alike. *(Today: read in the session's `TimeZone`: `UTC` keeps the first, `Asia/Dhaka` neither, `America/New_York` both.)*
- **R8.** [BUG-640] (HR-6) Ordered by `performed_at` descending, then `id` descending, before `skip` / `limit`. *(Today: `performed_at` alone.)*
- **R9.** With the defaults at most 100 rows: 105 give 100; `limit=1000` gives 105.
- **R10.** `limit=0` and `skip` past the end return `[]`.
- **R11.** Negative paging is refused by Postgres (see Errors).
- **R12.** All filters combine (AND) and apply before `skip` / `limit`.
- **R13.** The attachment's state is not looked at: rows of a soft-deleted attachment are all returned. This is history.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| negative `limit` | `sqlalchemy.exc.DataError`, `.orig.pgcode == "2201W"` | `LIMIT must not be negative` |
| negative `skip` | `sqlalchemy.exc.DataError`, `.orig.pgcode == "2201X"` | `OFFSET must not be negative` |

**Side effects:** none

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 18–26 | keyword-only parameters; defaults | R2–R6, R9 |
| 28 | workspace filter | R1 |
| 29–30 | `attachment_id is not None` | R2 |
| 31–32 | `if entity_type:` `None` / `""` skip | R3 |
| 33–34 | `if transaction_type:` `None` / `""` skip | R4 |
| 35–36 | `start_date is not None`, `>=` | R5, R7, R7a |
| 37–38 | `end_date is not None`, `<=` | R6, R7, R7a |
| 40 | `performed_at` descending only (BUG-640) | R8 |
| 41–42 | offset / limit; `0`; negative | R9, R10, R11, R12 |
| 28–43 | no join to attachments | R13 |
| 47 | module singleton | Not specified |
