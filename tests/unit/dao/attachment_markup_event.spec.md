# Spec — `app/dao/attachment_markup_event.py`

> **Status:** APPROVED (2026-11-03; nothing open)
> **Source commit:** e48a092

> **Review round 2026-11-03.** No owner answer in this round. **Delegated:** P1 and P2 accepted as suggested, decided by Claude under the reviewer's delegation (2026-11-03). None of them is the owner's own answer. The house-rule line stands.

> **Base behaviour** is in `tests/unit/dao/base.spec.md` and is not restated.
>
> **Standing decisions applied here (not asked again):** a missing `ORDER BY` is a bug, and no order recipe counts as deterministic unless it ends in `id`. Event logs are history (the owner's ledger ruling, 2026-10-30): the state of a soft-deleted parent never hides or trims them. Raw lookups stay raw (HR-4 scope). HR-16: a row linking to another workspace's row is invalid data.
>
> **Verified by running** (throwaway scripts `cat1.py`, `v_markup.py`, `v_markup2.py` with the harness `h.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\attdao\`, each transaction rolled back against `marker_test`; nothing committed): the table's columns, constraints and indexes; `create_event` with and without `session_id` / `metadata_json`, the stored value of `metadata_json=None`, the Python default of `created_at` against the database's UTC clock, a 37-character `session_id`, a 33-character `event_type`, unknown attachment and user, `description=None`, empty strings; order with three events of one `created_at` (set by SQL) and one later, under a forced sequential scan, before and after an update; how many of 30 events written one after another share a `created_at` (4 distinct values); `limit` 2, 0, −1; another workspace; 201 events with no `limit`; a deleted attachment; the SQL; a positional call. **Not run:** anything over HTTP.

## Review
> All answered; applied 2026-11-03.

### Quick list — all answered
| # | What the code does today, in plain words | Answer | Decided by |
|---|---|---|---|
| P1 | The markup history of an attachment silently stops at the 200 newest entries | bug — the whole log is returned (BUG-1437) | Claude, delegated |
| P2 | The history of a deleted attachment is still read here | intended — logs are history | Claude, delegated |

Decided by a house rule: entries with the same time come back in no fixed order (BUG-1436).

### House-rule violations — applied automatically

- **HR-6** `list_for_attachment` R3 — ordered by `created_at` newest first, nothing after it. `created_at` comes from the server's clock, which is coarse on Windows: of 30 entries written one after another, only 4 distinct times were stored. Verified under a forced sequential scan: three entries of one time came back `213, 214, 215`, then `214, 215, 213` after an update. With the 200-entry cap (P1) a tie at the edge also decides which entry is cut off. Intended: `created_at` newest first, then `id` descending (BUG-1321 precedent).
**Answer:** bug — per HR-6 (house rule)
**Resolution:** BUG-1436 (pattern `tied-timestamp-no-tiebreak`). Rules: `list_for_attachment` R3.

Checked and **not** a new line here: **HR-4** — no soft-delete column; the attachment's state is P2. **HR-5, HR-8** — equality filters only. **HR-7** — `limit` is never passed by the caller (P1). **HR-9, HR-10** — append-only, no lock needed. **HR-16** — reads filter on the row's `workspace_id`; `create_event` stores what the caller gives, and the manager passes an attachment it checked in the caller's workspace. **HR-1, HR-2, HR-3, HR-15** — `event_type` and `description` are written by code.

### Precedent matches — all accepted (decided by Claude under the reviewer's delegation, 2026-11-03)

### P1. The markup history silently stops at 200 entries — 🐞 BUG-1437
**Background:** `list_for_attachment` has `limit=200`, and its only caller (`AttachmentMarkupManager.list_events`, the markup history panel) passes none and has no paging. Logs are history and are never trimmed (standing decision). Hidden caps were ruled bugs before (BUG-342, BUG-982).
**What happens today:** Given 201 entries, the 200 newest come back and the oldest is left out, with nothing telling the user the list is cut. (Verified.)
**Example:** A drawing reviewed for months has 260 markup saves. The history shows the latest 200; the first 60, including who first marked the drawing, are not there.
**Rules affected:** `list_for_attachment` R4
**Answer:** bug — per BUG-982 precedent: every entry is returned, no cap; the `limit` parameter, never passed, goes with the fix
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-03): 🐞 BUG-1437 (pattern `silent-result-cap`). If a long history ever needs paging, it is added at the endpoint with HR-7 limits. The dead `limit` parameter is listed in `docs/testing/dead-code-removal-checklist.md` "remove together with the fix of BUG-1437". Rules: `list_for_attachment` R4 (tagged).

### P2. The history of a deleted attachment is still read — ✅ intended
**Background:** Attachments are soft-deleted. The only caller first answers 404 for a deleted attachment (`_get_ready_attachment`).
**What happens today:** `list_for_attachment` returns the entries of a soft-deleted attachment like any other. (Verified.)
**Example:** Drawing 12 is deleted; its 4 markup entries stay in the table and are returned when read directly. The API answers 404 first.
**Rules affected:** `list_for_attachment` R5
**Answer:** intended — event logs are history (owner's ledger ruling); the manager's 404 hides them through the API
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-03): rule unchanged. Rules: `list_for_attachment` R5 ✅.

## Overview
`AttachmentMarkupEventDAO` writes and reads `attachment_markup_events`, the append-only history of markup saves, updates and clears on an attachment. Callers: `AttachmentMarkupManager._log_markup_event` (`create_event`, after `put_own_layer` / `delete_own_layer`) and `AttachmentMarkupManager.list_events` (`list_for_attachment`). It is meant to protect workspace isolation through the row's `workspace_id`. It flushes, never commits, never updates or deletes a row, and takes no lock.

**Callables:** 2 specified · 1 not specified
**Externals to mock:** none needed. `created_at` defaults to `app.utils.time.utcnow` captured at import by the model; patching a module name does not reach it. To control times, pass none and set them by SQL afterwards, or construct rows with `created_at` given.
**Integration-only behavior:** none.

**Model facts (table `attachment_markup_events`, class `app.models.attachment_markup_event.AttachmentMarkupEvent`):**
| Column | Type / constraint | Default |
|---|---|---|
| `id` | Integer PK | sequence |
| `workspace_id` | Integer NOT NULL, FK `workspaces.id` ON DELETE CASCADE | — |
| `attachment_id` | Integer NOT NULL, FK `attachments.id` ON DELETE CASCADE | — |
| `user_id` | Integer NOT NULL, FK `profiles.id` ON DELETE CASCADE | — |
| `session_id` | String(36) nullable, indexed | `NULL` |
| `event_type` | String(32) NOT NULL | — (written: `markup_saved`, `markup_updated`, `markup_cleared`) |
| `description` | Text NOT NULL | — |
| `metadata_json` | `json` nullable | `NULL`; Python `None` is stored as JSON `null` |
| `created_at` | `timestamp` (no zone) NOT NULL | Python `utcnow()` (naive UTC); the database also has `now()`, which the model never leaves to it |

- Indexes: primary key, `workspace_id`, `attachment_id`, `session_id`, and `(attachment_id, created_at)`. No check constraint, no trigger. Hard-deleting the attachment, the user or the workspace deletes the entries.

**Notes for the test designer:**
- Use the singleton `attachment_markup_event_dao`. Every parameter after `db` is keyword-only.
- **BUG-1436:** create three entries, then `UPDATE attachment_markup_events SET created_at = :t WHERE id = ANY(:ids)`; force a sequential scan (base spec note) and update the lowest-`id` one's `description`; verified to put it last of the three. Intended: highest `id` first among equals; **non-strict** xfail.
- **BUG-1437:** 201 entries (`add_all`), no `limit` → intended 201, today 200 → **strict** xfail.

## Not specified
- `attachment_markup_event_dao` — module-level singleton, no logic.
- (`list_for_attachment`'s `limit` parameter — never passed; to be removed with BUG-1437 (P1). Its effect today is R4.)
- Inherited `BaseDAO` methods — no caller on this DAO; base spec.

---

## `AttachmentMarkupEventDAO.list_for_attachment(db, *, workspace_id, attachment_id, limit=200)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `AttachmentMarkupManager.list_events`, with no `limit`)

**Purpose:** The markup history of one attachment, newest first.

**Returns:** a `list` of `AttachmentMarkupEvent` (possibly empty).

**Rules:**
- **R1.** Returns the entries of that attachment with that `workspace_id`; entries of another attachment never.
- **R2.** Entries with another `workspace_id` are not returned; an unknown attachment id or `0` returns `[]`.
- **R3.** [BUG-1436] (HR-6) Ordered by `created_at` newest first, then `id` descending: a later entry comes first, then entries of one time highest `id` first, also after one of them was updated. *(Today: `created_at` only; verified `213, 214, 215` → `214, 215, 213` after an update.)*
- **R4.** [BUG-1437] (P1) Every matching entry is returned: given 201, 201. *(Today: at most 200, the newest by R3.)*
- **R5.** ✅ (P2) The attachment's state is not looked at: the entries of a soft-deleted attachment are returned.

**Errors:** none reachable from the caller. (A negative `limit` passed directly raises `DataError` 2201W; `limit=0` returns `[]` — the parameter goes with BUG-1437.)

**Side effects:** none

---

## `AttachmentMarkupEventDAO.create_event(db, *, workspace_id, attachment_id, user_id, event_type, description, session_id=None, metadata_json=None)`
**Shape:** event-log
**Persistence:** writes
**Visibility:** public (used by: `AttachmentMarkupManager._log_markup_event`)

**Purpose:** Append one entry to an attachment's markup history.

**Returns:** the new row, flushed, not committed.

**Rules:**
- **R1.** A row is created with the given values; `id` is set; `created_at` is `utcnow()` at the flush (naive UTC, equal to the database's `now() AT TIME ZONE 'UTC'` within a second).
- **R2.** `session_id` and `metadata_json` default to `None`. A `metadata_json` of `None` is stored as the JSON value `null` (`metadata_json IS NULL` is false) and reads back as `None`; a dict is stored and read back as given.
- **R3.** Nothing is validated: empty `event_type` and `description` are stored. A `session_id` over 36 or an `event_type` over 32 characters raises `DataError` (pgcode `22001`); `description=None` raises `IntegrityError` (pgcode `23502`); an unknown `attachment_id` or `user_id` raises `IntegrityError` (pgcode `23503`).
- **R4.** Flushed, not committed: rolling back a savepoint removes the row.

**Errors:** as in R3.

**Side effects:** one row inserted and flushed.

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 12–19, 31–42 | keyword-only parameters; defaults `limit=200`, `session_id=None`, `metadata_json=None` | Notes; `list_for_attachment` R4; `create_event` R2 |
| 22–25 | workspace AND attachment; attachment state not read | `list_for_attachment` R1, R2, R5 |
| 26 | `created_at DESC` only (BUG-1436) | `list_for_attachment` R3 |
| 27 | `limit` 200, never passed (BUG-1437) | `list_for_attachment` R4 |
| 43–51 | row built from the arguments, unvalidated | `create_event` R1, R2, R3 |
| 52–54 | add + flush, no commit | `create_event` R1, R4 |
| 57 | singleton | Not specified |
| `models/attachment_markup_event.py` 30 | `created_at` Python default `utcnow` | `create_event` R1 |
