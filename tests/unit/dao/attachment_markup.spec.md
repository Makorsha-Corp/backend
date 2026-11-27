# Spec — `app/dao/attachment_markup.py`

> **Status:** APPROVED (2026-11-03; nothing open)
> **Source commit:** e48a092

> **Review round 2026-11-03.** No owner answer in this round. **Delegated:** P1 accepted as suggested, decided by Claude under the reviewer's delegation (2026-11-03). It is not the owner's own answer. The house-rule line stands.

> **Base behaviour** is in `tests/unit/dao/base.spec.md` and is not restated.
>
> **Standing decisions applied here (not asked again):** a missing `ORDER BY` is a bug, and no order recipe counts as deterministic unless it ends in `id`. Soft-deleted parents hide their children. Raw lookups stay raw (HR-4 scope). HR-16: a row linking to another workspace's row is invalid data.
>
> **Verified by running** (throwaway scripts `cat1.py`, `v_markup.py`, `v_markup2.py` with the harness `h.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\attdao\`, each transaction rolled back against `marker_test`; nothing committed): the table's columns, constraints and indexes; `get_for_user` none / found / other workspace / other user / other attachment; insert and update through `upsert_for_user`, the statements of an update with an equal payload, `updated_at` against the transaction's `now()`; an upsert under another workspace for an existing attachment + user; `payload` `{}` and `None` on insert and update; unknown attachment and user; a row of workspace B on an attachment of A; order of three layers with one `updated_at` under a forced sequential scan before and after an update, and with one older; a deleted attachment; `delete_for_user` other workspace / found / again; positional calls; no `ORDER BY` and no `FOR UPDATE` on the single lookup. **Read, not run:** the callers in `app/managers/attachment_markup_manager.py`. **Not run:** anything over HTTP; two concurrent first saves (needs commits).

## Review
> All answered; applied 2026-11-03.

### Quick list — all answered
| # | What the code does today, in plain words | Answer | Decided by |
|---|---|---|---|
| P1 | The layers of a deleted attachment are still read and written here | intended at the DAO — the only caller refuses a deleted attachment first | Claude, delegated |

Decided by a house rule: layers saved at the same moment come back in no fixed order (BUG-1435).

### House-rule violations — applied automatically

- **HR-6** `get_for_attachment` R4 — ordered by `updated_at` alone. `updated_at` is the database's `now()`, the transaction's start, so layers saved in one transaction share it. Verified under a forced sequential scan: three layers with one `updated_at` came back `1, 2, 3`, then `2, 3, 1` after an update of the first. Intended: `updated_at` oldest first, then `id` ascending.
**Answer:** bug — per HR-6 (house rule)
**Resolution:** BUG-1435 (pattern `tied-timestamp-no-tiebreak`). Rules: `get_for_attachment` R4.

Checked and **not** a new line here: **HR-6** on `get_for_user` — no `ORDER BY`, but the unique constraint on `(attachment_id, user_id)` leaves at most one row. **HR-9** — the table has no "changed by" field; `updated_at` moves only when the payload changes (`upsert_for_user` R4). **HR-10** — two first saves of one user's layer at once would both insert and the second would fail with `IntegrityError` 23505 (not run: needs commits); nothing harmful is duplicated (the loser writes nothing), so no lock is required; the manager may turn it into a retry (FU-1 (a)). **HR-16** — reads and writes take the workspace from the caller; the unique constraint lacks `workspace_id`, so the same attachment + user under another workspace is refused (R6 of `upsert_for_user`); a row of workspace B on an attachment of A is accepted (invalid data no caller produces: the manager checks the attachment in the caller's workspace first). **HR-4** — P1. **HR-1, HR-2, HR-3, HR-5, HR-7, HR-8, HR-15** — no names, paging, `LIKE` or money.

### Precedent matches — all accepted (decided by Claude under the reviewer's delegation, 2026-11-03)

### P1. The layers of a deleted attachment are still read here — ✅ intended at the DAO
**Background:** A markup layer is one user's drawing over one attachment. Attachments are soft-deleted. Every caller of this DAO is in `AttachmentMarkupManager`, and each first calls `_get_ready_attachment`, which answers 404 `Attachment <id> not found.` for a deleted attachment (`attachment_dao.get_active`) before touching layers. The machine stock DAO kept single-row lookups raw where the manager decides (machine item DAO P5).
**What happens today:** All four methods ignore the attachment's state: the layers of a deleted attachment are listed, found, updated and deleted. (Verified.) Through the API the 404 comes first.
**Example:** Drawing 12 is deleted. `GET /attachments/12/markup` answers 404 before this DAO is reached; called directly, `get_for_attachment` still returns its 3 layers.
**Rules affected:** `get_for_attachment` R5, `get_for_user` R4
**Answer:** intended at the DAO — per machine item DAO P5 / HR-4 scope: raw reads; the manager's 404 hides them
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-03): rules unchanged. Rules: `get_for_attachment` R5 ✅, `get_for_user` R4 ✅.

## Follow-ups for other reviews
> Nothing below is a rule of this DAO and no bug is logged for it here. Whoever describes the named module must read this list first.

| # | Where it must be looked at | What | Came from |
|---|---|---|---|
| FU-1 | **Attachment markup manager** (`app/managers/attachment_markup_manager.py`, not yet specified) | (a) Two first saves of one user's layer at once: the second fails with `IntegrityError` 23505 on `uq_attachment_markup_user` → 500 (not run). (b) `put_own_layer` logs `markup_updated` even when the payload is equal to the stored one; the row is not written then (`upsert_for_user` R4). Whether an unchanged save should leave no event is the manager's question. | HR-10, HR-9 notes |

## Overview
`AttachmentMarkupDAO` stores `attachment_markups`: one drawing layer per user per attachment (JSON overlay, not file bytes). Callers: `AttachmentMarkupManager.list_layers`, `put_own_layer`, `delete_own_layer` (the markup endpoints under `/attachments/{id}/markup`). It is meant to protect workspace isolation through the row's `workspace_id`. It flushes, never commits, and takes no lock.

**Callables:** 4 specified · 1 not specified
**Externals to mock:** none. `updated_at` comes from the database.
**Integration-only behavior:** none.

**Model facts (table `attachment_markups`, class `app.models.attachment_markup.AttachmentMarkup`):**
| Column | Type / constraint | Default |
|---|---|---|
| `id` | Integer PK | sequence |
| `workspace_id` | Integer NOT NULL, FK `workspaces.id` ON DELETE CASCADE | — |
| `attachment_id` | Integer NOT NULL, FK `attachments.id` ON DELETE CASCADE | — |
| `user_id` | Integer NOT NULL, FK `profiles.id` ON DELETE CASCADE | — |
| `payload` | `json` NOT NULL | — |
| `updated_at` | `timestamptz` NOT NULL | database `now()`; `onupdate` database `now()` |

- Unique constraint `uq_attachment_markup_user` on `(attachment_id, user_id)` — **without** `workspace_id`. Indexes on `workspace_id`, `attachment_id`, `user_id`. No check constraint, no trigger.
- `payload` is SQLAlchemy `JSON` with its default `none_as_null=False`: Python `None` is stored as the JSON value `null`, not SQL `NULL`, so it passes NOT NULL.
- `now()` is the transaction's start time, so all writes of one test share one `updated_at`.

**Notes for the test designer:**
- Use the singleton `attachment_markup_dao`. Every parameter after `db` is keyword-only (a positional call raises `TypeError`).
- Attachments as in `tests/unit/dao/attachment.spec.md`; three profiles from `make_profile`.
- **BUG-1435:** three layers in one transaction share `updated_at`. Force a sequential scan (base spec note) and update the lowest-`id` row's `payload` with SQL (`UPDATE attachment_markups SET payload = CAST(:p AS json) WHERE id = :i`); verified to put it last. Write to the intended order; **non-strict** xfail. To give one layer an older time: `UPDATE … SET updated_at = now() - interval '1 hour'`.
- `updated_at` after an update cannot be "later" inside one transaction: assert the UPDATE statement was or was not issued (statement listener), or that `updated_at` equals `SELECT now()`.

## Not specified
- `attachment_markup_dao` — module-level singleton, no logic.
- Inherited `BaseDAO` methods — no caller on this DAO; base spec.

---

## `AttachmentMarkupDAO.get_for_attachment(db, *, workspace_id, attachment_id)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `AttachmentMarkupManager.list_layers`)

**Purpose:** Every user's layer on one attachment.

**Returns:** a `list` of `AttachmentMarkup` (possibly empty); no paging, no cap.

**Rules:**
- **R1.** Returns the layers of that attachment with that `workspace_id`, one per user who has one.
- **R2.** A layer with another `workspace_id` is not returned (only the row's `workspace_id` is compared: a row of workspace B on an attachment of A is returned for B, not for A).
- **R3.** An unknown attachment id, `0`, or an attachment without layers returns `[]`.
- **R4.** [BUG-1435] (HR-6) Ordered by `updated_at` oldest first, then `id` ascending: an hour-older layer comes first, then layers sharing one `updated_at` in `id` order, also after one of them was updated in place. *(Today: `updated_at` only; verified `1, 2, 3` → `2, 3, 1` after an update of the first.)*
- **R5.** ✅ (P1) The attachment's state is not looked at: the layers of a soft-deleted attachment are returned.

**Errors:** none.

**Side effects:** none

---

## `AttachmentMarkupDAO.get_for_user(db, *, workspace_id, attachment_id, user_id)`
**Shape:** get
**Persistence:** reads
**Visibility:** public (used by: `upsert_for_user`, `delete_for_user`; `AttachmentMarkupManager.put_own_layer` to tell `markup_saved` from `markup_updated`)

**Purpose:** One user's layer on one attachment, if any.

**Returns:** the `AttachmentMarkup` the session holds, or `None`.

**Rules:**
- **R1.** Given a row with that workspace, attachment and user, it is returned.
- **R2.** All three must match: another user, another attachment, or another workspace → `None`.
- **R3.** No match, including ids of `0`, returns `None`, with no error.
- **R4.** ✅ (P1) The attachment's state is not looked at, as `get_for_attachment` R5.

**Errors:** none.

**Side effects:** none

---

## `AttachmentMarkupDAO.upsert_for_user(db, *, workspace_id, attachment_id, user_id, payload)`
**Shape:** create / update
**Persistence:** writes
**Visibility:** public (used by: `AttachmentMarkupManager.put_own_layer`, with `MarkupPayload.model_dump()`, when the payload is not empty)

**Purpose:** Save one user's layer: create it the first time, replace its payload afterwards.

**Returns:** the row, flushed, not committed.

**Rules:**
- **R1.** When the user has no layer on that attachment in that workspace (`get_for_user` R1–R3), a row is created with the four given values; `id` is set and `updated_at` is the transaction's `now()`.
- **R2.** When the user has one, the same row is returned with `payload` replaced by the given value; no second row is created.
- **R3.** The payload is stored as given: `{}` is stored as `{}`, and `None` is stored as the JSON value `null` (not SQL `NULL`), with no error, on insert and on update.
- **R4.** When the given payload is equal to the stored one, no UPDATE is issued and `updated_at` stays as it was; when it differs, `updated_at` becomes the transaction's `now()`.
- **R5.** An unknown `attachment_id` or `user_id` raises `IntegrityError` (pgcode `23503`) at the flush.
- **R6.** When a layer for the same attachment and user exists under **another** `workspace_id`, the lookup misses it and the insert raises `IntegrityError` (`UniqueViolation`, pgcode `23505`, `uq_attachment_markup_user`); nothing changes.
- **R7.** The attachment's workspace is not compared with `workspace_id`: a row of workspace B on an attachment of A is created (HR-16: invalid data; the caller checks the attachment first).
- **R8.** Flushed, not committed: rolling back a savepoint removes the insert or restores the old payload.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| unknown attachment / user | `sqlalchemy.exc.IntegrityError`, pgcode `23503` | — |
| same attachment + user under another workspace | `sqlalchemy.exc.IntegrityError`, pgcode `23505` | — |

**Side effects:** one row inserted or updated, flushed; no event (the manager writes it).

---

## `AttachmentMarkupDAO.delete_for_user(db, *, workspace_id, attachment_id, user_id)`
**Shape:** delete
**Persistence:** writes
**Visibility:** public (used by: `AttachmentMarkupManager.put_own_layer` (empty payload), `delete_own_layer`)

**Purpose:** Remove one user's layer, saying whether there was one.

**Returns:** `True` when a row was deleted, `False` otherwise.

**Rules:**
- **R1.** When the user's layer exists (`get_for_user` R1), it is hard-deleted and flushed, and `True` is returned; the other users' layers stay.
- **R2.** When there is none (another workspace, another user, unknown ids), `False` is returned and nothing is deleted; a second call after R1 returns `False`.
- **R3.** Flushed, not committed: rolling back a savepoint brings the row back.

**Errors:** none.

**Side effects:** at most one row deleted; no event (the manager writes it).

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 12–18, 29–35, 47–54, 75–81 | keyword-only parameters | Notes for the test designer |
| 20–24 | workspace AND attachment; attachment state not read | `get_for_attachment` R1, R2, R3, R5 |
| 25 | `updated_at ASC` only (BUG-1435) | `get_for_attachment` R4 |
| 37–44 | workspace AND attachment AND user; `.first()` row / `None` | `get_for_user` R1–R4 |
| 56–61 | lookup through `get_for_user` | `upsert_for_user` R1, R2, R6 |
| 62–69 | `row is None` → new row added | `upsert_for_user` R1, R3, R5, R6, R7 |
| 70–71 | else → payload replaced | `upsert_for_user` R2, R3, R4 |
| 72 | flush, no commit | `upsert_for_user` R8 |
| 83–88 | lookup through `get_for_user` | `delete_for_user` R1, R2 |
| 89–90 | `row is None` → `False` | `delete_for_user` R2 |
| 91–93 | delete + flush → `True` | `delete_for_user` R1, R3 |
| 96 | singleton | Not specified |
| `models/attachment_markup.py` 27–29 | `updated_at` server default and `onupdate` `now()` | `upsert_for_user` R1, R4 |
