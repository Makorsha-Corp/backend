# Spec — `app/dao/machine_activity_event.py`

> **Status:** APPROVED (2026-10-31; nothing open)
> **Source commit:** e48a092

> **Review round 2026-10-31.** **Delegated:** Q1, Q2, Q3 accepted as suggested, decided by Claude under the reviewer's delegation (2026-10-31). None of these is the owner's own answer. BUG-1090 stands from the house rule. FU-1 (c) is logged as BUG-1091; its rule belongs to the machine activity manager's spec, so no rule here carries that tag.

> **Standing reviewer decisions applied here (not asked again):**
> 1. Physical row order and collation order are **not** an order: a missing `ORDER BY` is a bug, and no order recipe in this spec is called deterministic unless it ends in `id`.
> 2. Things of a soft-deleted parent are hidden by the parent's state, their own rows untouched ("hidden, not cascaded", 2026-10-11). **This does not reach ledgers and history logs** (owner, 2026-10-30: a ledger is history, not a count, and stays complete). Whether this log counts as history is Q1, with a suggestion.
> 3. Raw lookups stay raw (HR-4 scope; base DAO spec).
> 4. HR-16: a row linking to another workspace's row is invalid data, and no response shows another workspace's ids or names.
>
> **Verified by running** (throwaway scripts `mae_1.py` … `mae_4.py` with the harness `mae_h.py` in `C:\Users\User\AppData\Local\Temp\claude\E--Projects-Makorsh-Corp-backend\5dcda696-13dd-4b73-983c-11d3c05a8ed9\scratchpad\mae\`, each transaction rolled back against `marker_test`; nothing committed): the table's columns, nullability, defaults (only `id` has a database default), constraints, indexes, no trigger, no table references it; the order of `get_by_machine` including a timestamp tie; defaults and caps (101 rows → 100; `limit=1000` → 101); `limit=0`; `skip` past the end; negative paging errors; keyword-only parameters; both date bounds to the microsecond; a same-day range; a range with `from_date` after `to_date`; a `datetime` passed as a date; the same result under session time zones `America/New_York` and `Asia/Dhaka`; `event_type` as `""`, `None`, another case, a space, padded, unknown, with `%`; filtering before paging; all three methods for a soft-deleted machine and for a live machine in a soft-deleted factory; a row of workspace A on a machine of workspace B, through all three methods and through `list_events` (404); latest status with none, with newer rows of another type, on a tie, with empty metadata; the map with `[]`, `None`, an id listed twice, unknown ids, `0`, a machine without status rows, a same-stamp row of another type, a newer and a same-stamp row of another workspace; **the map and `get_latest_status_by_machine` disagreeing on a tie** (ids 106076 / 106077: the map returned 106076 after that row was updated, the single lookup 106077); that the map's row query has no `ORDER BY` and neither query has `FOR UPDATE`; one statement per call and no join; metadata `None` set explicitly stores JSON `null`, left unset stores SQL `NULL`, both read back as `None`; the default `created_at` is naive; **BUG-1091:** `log_event` stored a row of workspace A on a machine of workspace B, and `create_pending_attachment` + `confirm_attachment` did the same from A with B's machine id (Cloudinary calls patched), after which B saw 0 such rows and A got 404. `GET /machines/{id}/activity/` was run through `MachineService.get_machine_activity`, not over HTTP. **Not run:** anything over HTTP; two concurrent transactions; the intended behavior of BUG-1090.

## Review
> All answered; applied 2026-10-31.

### Quick list — all answered
| # | What the code does today, in plain words | Answer | Decided by |
|---|---|---|---|
| Q1 | The activity log of a deleted machine, or of a machine in a deleted factory, stays readable and complete | intended — this log is history (the owner's ledger ruling) | Claude, delegated |
| Q2 | A deleted machine still reports its last status | intended — raw reads | Claude, delegated |
| Q3 | The date filter uses UTC days, not the day the user sees | intended for now; a change would be a product-wide rule | Claude, delegated |

Decided by house rules: on a timestamp tie the machines page can show a different status from the machine's own page (BUG-1090, HR-6); an activity row can be written for another workspace's machine (BUG-1091, HR-16; FU-1 (c)).

### House-rule violations — applied automatically

- **HR-6** `get_latest_status_map` R6 — a per-machine top-1 picked by timestamp alone, with no `ORDER BY` in the row query: on a tie the row kept is the last one the database happens to return. `get_latest_status_by_machine` breaks the same tie by highest `id`, and the BUG-886 fix does too (machine DAO `search_advanced` R12a). Verified: two rows with one timestamp, the map returned the lower `id` once that row had been updated, the single lookup kept the higher `id`, so `GET /machines/` and `GET /machines/{id}/` showed different statuses for one machine. Intended: newest `created_at`, ties to the highest `id`.
**Answer:** bug — per HR-6 (house rule)
**Resolution:** BUG-1090 (pattern `ambiguous-latest-row-tiebreak`, same root cause as BUG-664). Rules: `get_latest_status_map` R6. Closes the second half of FU-8 in `tests/unit/managers/machine_manager.spec.md` and the cross-spec note in `tests/unit/dao/machine.spec.md`.

Checked and **not** a new line here: **HR-6** on `get_by_machine` and `get_latest_status_by_machine` — both order by `created_at` descending, then `id` descending, before paging. **HR-5** — every filter is in the query. **HR-7** — `GET /machines/{id}/activity/` requires `skip >= 0` and `1 <= limit <= 1000`. **HR-8** — no `LIKE`; `event_type` is an exact match. **HR-4** — the table has no soft-delete column; parents are Q1 and Q2. **HR-9** — the DAO writes nothing. **HR-10** — the DAO only reads; the check-then-write on status changes is `create_machine_event`, already logged as BUG-960. **HR-15** — no money. **HR-16** — no response of this DAO is affected, see `get_by_machine` R2; the write side is BUG-1091 (FU-1 (c)). **HR-1, HR-2, HR-3** — `event_type` is never user input on the write side (the filter value is only compared). **`event_type=""`** (R14) is reachable only by a hand-written URL, because the frontend leaves the parameter out for "All", and it means "no filter", so it is a rule, not a question. A range with `from_date` after `to_date` returns an empty list (R11), which is no surprise to a user.

### New questions

### Q1. The activity log of a deleted machine stays readable — ✅ intended
**Background:** The machine activity log is the panel of a machine's history: created, edited, deactivated, status changes, stock added or removed, maintenance. Its model calls it an "append-only audit log", and the log is what records who did what. The owner ruled that a ledger is history, not a count, and stays complete even when its parent is soft-deleted: hiding entries leaves gaps in the audit trail. Lists of things that are counted do hide rows of soft-deleted parents. This log has no soft-delete column and nothing reads it as a total. After BUG-955 and BUG-966, `GET /machines/{id}/` answers 404 for a deleted machine; `GET /machines/{id}/activity/` looks the machine up raw, so it keeps answering.
**What happens today:** `get_by_machine` returns every event of a soft-deleted machine and of a live machine in a soft-deleted factory. (Verified, also through `MachineService.get_machine_activity`.)
**Example:** "Press 4" is deleted on Monday. On Tuesday someone asks who moved stock off it last month: `GET /machines/<Press 4>/activity/` still lists every entry, the "deactivated" entry included. Press 4 itself is gone from the machines page.
**Rules affected:** `get_by_machine` R4
**Suggested answer:** `intended — this log is history, by the owner's ledger ruling: it stays complete for a deleted machine and is never hidden by its parent's state`. Not an OWNER item: it changes no figure, and it applies a ruling the owner already made. Alternative: `bug — the log of a deleted machine is hidden unless include_deleted is given`, which would have to go in `MachineActivityManager.list_events`, not here.
**Answer:** intended — this log is history, by the owner's ledger ruling: it stays complete for a deleted machine and is never hidden by its parent's state
**Resolution:** decided by Claude under the reviewer's delegation (2026-10-31): rule unchanged. Rules: `get_by_machine` R4 ✅.

### Q2. A deleted machine still reports its last status — ✅ intended
**Background:** A machine's current status (RUNNING, IDLE, OFF, MAINTENANCE) is not a column: it is the `status` in the metadata of its newest `status_updated` event. Deleting a machine writes a `deactivated` event, which is not a status change, so the status stays what it was. These two reads are used for the status shown in machine responses and to check a new status change. `create_machine_event` refuses a deleted machine before it reads the status. A status is a current state rather than an entry of history, so Q1's answer does not settle it, but both reads are for machines the caller names.
**What happens today:** Both methods return the status row of a soft-deleted machine and of a live machine in a soft-deleted factory. (Verified.)
**Example:** "Press 4" is running when it is deleted. Any response that still shows it says `latest_status_type: RUNNING`, though `is_active` is false.
**Rules affected:** `get_latest_status_by_machine` R6, `get_latest_status_map` R7
**Suggested answer:** `intended — raw reads (HR-4 scope, standing decision 3): the caller names the machines and decides what to show`. Which machines appear at all is decided by `get_machine` and `search_machines`. Alternative: `bug — a deleted machine reports no status`.
**Answer:** intended — raw reads (HR-4 scope, standing decision 3): the caller names the machines and decides what to show
**Resolution:** decided by Claude under the reviewer's delegation (2026-10-31): rules unchanged. Rules: `get_latest_status_by_machine` R6 ✅, `get_latest_status_map` R7 ✅.

### Q3. The date filter uses UTC days, not the day the user sees — ✅ intended
**Background:** Events are stored in UTC with no time zone. The activity panel has two plain date boxes and sends the date the user picked, for example `2026-03-05`, and the API has no time zone parameter. Each profile can have a time zone, used for display. The purchase order and transfer order date filters work in UTC days too, and BUG-991 (ledger end date) kept that.
**What happens today:** `from_date` and `to_date` are days from 00:00:00 to 23:59:59.999999 **UTC**. (Verified; the session's time zone makes no difference.)
**Example:** A user in Dhaka (UTC+6) logs an event at 01:00 on 5 March, which is 19:00 on 4 March UTC. Filtering on 5 March leaves that event out, and shows one logged at 01:00 on 6 March Dhaka time.
**Rules affected:** `get_by_machine` R12
**Suggested answer:** `intended for now — date filters use UTC days; changing one alone would make the pages disagree`. If the owner wants the user's own day, that is a new house rule for every date filter, with the time zone passed in by the API. Not an OWNER item on this log, but such a rule would also reach ledgers and order filters, so it would become one.
**Answer:** intended for now — date filters use UTC days; changing one alone would make the pages disagree
**Resolution:** decided by Claude under the reviewer's delegation (2026-10-31): rule unchanged. Rules: `get_by_machine` R12 ✅.

## Follow-ups for other reviews
> Nothing below is a rule of this DAO. Whoever describes the named module must read this list first.

| # | Where it must be looked at | What | Came from |
|---|---|---|---|
| FU-1 | **Machine activity manager** (`app/managers/machine_activity_manager.py`, not yet specified) | (a) `get_latest_status` has the comment "404 if missing" and raises nothing (machine manager FU-8). (b) `list_events` calls `profile_dao.get` once per event with a performer, so up to 1000 extra reads for one page. (c) **BUG-1091 (HR-16), logged:** `log_event` does not check that the machine belongs to the workspace, so a row of workspace A can be stored on a machine of workspace B. Such a row shows nowhere today (`get_by_machine` R2). Reachable today through attachments: `POST /attachments/sign` with `entity_type = machine` and another workspace's machine id, then confirm (verified at manager level). Machine manager, maintenance log, machine item manager and stock postings check the machine first; the work order calls depend on `wo.machine_id`, which is BUG-1016. The manager's spec must carry the rule and the tag: 404 `Machine with ID <id> not found`, nothing written. (d) `log_event` with `metadata=None` stores JSON `null`, not SQL `NULL` (Model facts): machine DAO `search_advanced` R12c must be read with that in mind. | Q1, machine manager FU-8 |
| FU-2 | **Machine service** (`app/services/machine_service.py`, `get_machine_activity`) | (a) `MachineActivityEventMetadata` has no `note`, `old_quantity` or `new_quantity`: these stored keys are dropped from the response (verified). (b) `quantity: int`: one stored non-integer value makes `model_validate` raise `ValidationError`, so that machine's whole activity page is a 500 (verified with `{"quantity": 2.5}`). The stock postings pass `qty: int`, so check whether any writer can store a fraction. | reading the schema |

## Overview
`MachineActivityEventDAO` reads `machine_activity_events`, the activity log of a machine: one row per thing that happened to it. It has three reads: one machine's log with date and type filters, the newest status change of one machine, and the newest status change of many machines. A machine's current status has no column; it is the newest `status_updated` row of this table. All writes go through `MachineActivityManager.log_event`, not this DAO. Callers: `MachineActivityManager` only (`list_events`, `get_latest_status`, `get_latest_status_map`), reached by `GET /machines/{id}/activity/`, by every machine response of `MachineService`, by `create_machine_event` and by `WorkOrderManager._set_machine_status`. It is meant to protect workspace isolation. It never writes, never commits and takes no lock.

**Callables:** 3 specified · 2 not specified
**Externals to mock:** none. No method reads the clock.
**Integration-only behavior:** none. (`skip >= 0`, `1 <= limit <= 1000` and date parsing are enforced by `GET /machines/{id}/activity/`, not here.)

**Model facts (table `machine_activity_events`, class `app.models.machine_activity_event.MachineActivityEvent`):**
| Column | Type / constraint | Default |
|---|---|---|
| `id` | Integer PK | sequence |
| `workspace_id` | Integer NOT NULL, FK `workspaces.id` ON DELETE CASCADE (`machine_activity_events_workspace_id_fkey`) | — |
| `machine_id` | Integer NOT NULL, FK `machines.id` ON DELETE CASCADE (`machine_activity_events_machine_id_fkey`) | — |
| `event_type` | String(50) NOT NULL, no check constraint | — |
| `description` | Text NOT NULL | — |
| `metadata` (attribute `metadata_json`) | generic `JSON` (Postgres `json`, not `jsonb`), nullable | `NULL` |
| `performed_by` | Integer nullable, FK `profiles.id` ON DELETE SET NULL (`machine_activity_events_performed_by_fkey`) | `NULL` |
| `created_at` | `timestamp without time zone` NOT NULL, naive UTC by convention | Python default `utcnow`, no database default |

- No soft-delete column, no `is_active`, no `updated_at`. Indexes: primary key, `ix_machine_activity_events_workspace_id`, `ix_machine_activity_events_machine_id`. (The test database has no `ix_machine_activity_events_id`, though migration 113 and `index=True` mention one.) No unique constraint, no check constraint, no trigger; no table references this one.
- "Append-only" is a convention: nothing in the database enforces it, and no code updates or deletes these rows.
- `machine_id` and `workspace_id` of a row are independent: the database does not require the machine to belong to the row's workspace.
- Metadata set to Python `None` explicitly (what `log_event` does) is stored as JSON `null`; left unset it is SQL `NULL`. Both read back as `None`.
- Relationship: `performer` (lazy, `Profile`).
- Status values and the metadata shape are written by `MachineManager.create_machine_event`: `event_type = "status_updated"`, `metadata_json = {"status": "<STATUS>", "note": …, "changes": […]}`. Other event types (`created`, `updated`, `deactivated`, `item_added`, `maintenance_logged`, …) may carry a `status` key too and do not count as status changes.
- Parents, as used by Q1 and Q2: `Machine` soft delete = `is_deleted = True` with `is_active = False`. `Factory` soft delete = `is_deleted = True`, `is_active` unchanged.

**Notes for the test designer:**
- Use the module singleton `machine_activity_event_dao` (`from app.dao.machine_activity_event import machine_activity_event_dao`). Every parameter after `db` is keyword-only (a positional call raises `TypeError`).
- Workspaces and profiles from `tests/unit/factories.py`. Build `Factory(workspace_id, name, abbreviation)`, `Machine(workspace_id, factory_id, name)` and `MachineActivityEvent(workspace_id, machine_id, event_type, description, created_at, metadata_json)` directly (add + flush). The session runs with `autoflush=False`: flush before calling the DAO.
- Always give `created_at` explicitly, with distinct values unless the case is about a tie. Bounds to the microsecond: `datetime(2026, 3, 5, 23, 59, 59, 999999)`.
- **The tie (BUG-1090):** two `status_updated` rows of one machine with one `created_at`, then an `UPDATE` of the **lower**-`id` row's `description`, flushed, then `db.expire_all()`. Today the map then returned the lower `id` (verified), but that rests on physical row order, which is not an order. Write the case to the intended result and mark it **non-strict** xfail (`strict=False`); never weaken the assertion. Compare with `get_latest_status_by_machine` in the same case: that method needs no xfail.
- **Database errors:** wrap calls expected to raise `DataError` in `with db.begin_nested():` inside `pytest.raises(...)` so the session stays usable.

## Not specified
- `machine_activity_event_dao` — module-level singleton, no logic.
- Inherited `BaseDAO` methods (`get`, `get_multi`, `get_by_workspace`, `get_by_id_and_workspace`, `create`, `update`, `remove`) — not overridden and with **no caller on this DAO**: `log_event` adds the row itself. The base spec (`tests/unit/dao/base.spec.md`) covers them. The file's header says every query must filter by `workspace_id`; `get` and `get_multi` do not, and nothing calls them here.

The checklist (`docs/testing/unit-test-checklist-by-layer.md`) marks none of the three methods as possibly unused. `app/dao/machine.py` has its own copy of the latest-status query in `search_advanced` (BUG-886), specified in the machine DAO spec.

---

## `MachineActivityEventDAO.get_by_machine(db, *, machine_id, workspace_id, skip=0, limit=100, from_date=None, to_date=None, event_type=None)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `MachineActivityManager.list_events` ← `GET /machines/{id}/activity/`, passing every argument)

**Purpose:** One machine's activity log, newest first, one page at a time.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `db` | `Session` | open session |
| `machine_id` | int | equality on the row's `machine_id`; not validated |
| `workspace_id` | int | equality on the row's `workspace_id` |
| `skip` | int, default `0` | rows to skip; not validated |
| `limit` | int, default `100` | max rows; not validated |
| `from_date` | `date` \| `None` | `None` = no lower bound. A `datetime` is accepted and only its date is used (the API sends a `date`) |
| `to_date` | `date` \| `None` | `None` = no upper bound. Same as `from_date` |
| `event_type` | `str` \| `None` | `None` or `""` = no filter; otherwise compared exactly |

**Returns:** a `list` of `MachineActivityEvent` instances (possibly empty).

**Rules:**
- **R1.** Returns the rows with that `machine_id` and that `workspace_id`, of every event type. Rows of another machine are never returned.
- **R2.** Workspace isolation follows the row: a call with the right machine id and another workspace returns `[]`. Only the row's own `workspace_id` is compared, not the machine's. A row with `workspace_id` = A on a machine of workspace B is returned for A and not for B, so B never sees it. (HR-16: that row is invalid data, and it cannot reach a response, because `list_events` answers 404 for a machine of another workspace before this method runs. The write side is BUG-1091.)
- **R3.** An unknown machine id, `machine_id=0`, an unknown workspace, or a machine with no events returns `[]`.
- **R4.** ✅ (Q1) The state of the machine and of its factory is not looked at: the events of a soft-deleted machine, and of a live machine in a soft-deleted factory, are all returned.
- **R5.** Rows are ordered by `created_at` descending, then `id` descending, before `skip` / `limit`. Given 4 Mar, 5 Mar and two rows on 6 Mar, the result is the higher `id` of 6 Mar, the lower `id` of 6 Mar, 5 Mar, 4 Mar.
- **R6.** At most `limit` rows are returned after skipping `skip`; with the defaults at most 100: given 101 rows, exactly 100; with `limit=1000`, 101. Consecutive windows partition the rows with no repeats or gaps.
- **R7.** `limit=0` returns `[]`; `skip` at or past the number of matching rows returns `[]`.
- **R8.** A negative `limit` or `skip` makes Postgres reject the query (see Errors).
- **R9.** `from_date` keeps rows with `created_at` at or after 00:00:00.000000 of that day: a row at exactly that moment is kept, a row at 23:59:59.999999 of the day before is not.
- **R10.** `to_date` keeps rows with `created_at` at or before 23:59:59.999999 of that day: a row at exactly that moment is kept, a row at 00:00:00.000000 of the next day is not.
- **R11.** Both together keep the rows in the inclusive range: `from_date` = `to_date` covers that whole day. `from_date` after `to_date` returns `[]`, with no error.
- **R12.** ✅ (Q3) The bounds are compared directly with stored `created_at`, which is UTC, so a day means a UTC day, whatever the session's time zone: for `2026-03-05`, a row at `2026-03-04 19:00` is left out and a row at `2026-03-05 19:00` is kept.
- **R13.** A non-empty `event_type` keeps only rows whose `event_type` equals it exactly: case-sensitive, no trimming, no wildcards. `"ITEM_ADDED"`, `"item_added "`, `" "`, `"item%"` and an unknown type all return `[]` when the stored type is `item_added`.
- **R14.** `event_type=None` and `event_type=""` both apply no filter.
- **R15.** All filters combine (AND) and apply before `skip` / `limit`: given a newer `item_added` row and an older `status_updated` row, `event_type="status_updated", limit=1` returns the `status_updated` row.
- **R16.** Rows come back as stored: `metadata_json` is the stored value, `None` for both SQL `NULL` and JSON `null`, and `performer` gives the profile, or `None` when `performed_by` is `None`. The call changes nothing.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| negative `limit` | `sqlalchemy.exc.DataError`; `.orig` is `psycopg2.errors.InvalidRowCountInLimitClause`, `.orig.pgcode == "2201W"` | `LIMIT must not be negative` |
| negative `skip` | `sqlalchemy.exc.DataError`; `.orig` is `psycopg2.errors.InvalidRowCountInResultOffsetClause`, `.orig.pgcode == "2201X"` | `OFFSET must not be negative` |

**Side effects:** none

---

## `MachineActivityEventDAO.get_latest_status_by_machine(db, *, machine_id, workspace_id)`
**Shape:** get
**Persistence:** reads
**Visibility:** public (used by: `MachineActivityManager.get_latest_status` ← `MachineService._to_machine_response` for one machine, `MachineManager.create_machine_event`, `WorkOrderManager._set_machine_status`)

**Purpose:** The newest status change of one machine, if any.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `db` | `Session` | open session |
| `machine_id` | int | equality on the row's `machine_id`; not validated |
| `workspace_id` | int | equality on the row's `workspace_id` |

**Returns:** the `MachineActivityEvent` instance, or `None`.

**Rules:**
- **R1.** Returns the machine's `status_updated` row with the newest `created_at`.
- **R2.** On a `created_at` tie, the row with the highest `id` is returned.
- **R3.** Only `event_type == "status_updated"` counts, exactly: rows of other types are ignored even when newer and even when their metadata has a `"status"` key.
- **R4.** No matching row, an unknown machine id or `machine_id=0` returns `None`, with no error. Nothing is created.
- **R5.** Workspace isolation follows the row, as `get_by_machine` R2: a status row of another workspace is never returned, and a call with another workspace returns `None`.
- **R6.** ✅ (Q2) The state of the machine and of its factory is not looked at: the status row of a soft-deleted machine, and of a live machine in a soft-deleted factory, is returned.
- **R7.** The metadata is not looked at: when the newest status row has no metadata, or no `"status"` key, that row is returned, and older rows are not consulted.

**Errors:** none.

**Side effects:** none

---

## `MachineActivityEventDAO.get_latest_status_map(db, *, workspace_id, machine_ids)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `MachineActivityManager.get_latest_status_map` ← `MachineService._to_machine_responses`, i.e. every list of machines)

**Purpose:** The newest status change of each of many machines, in one read.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `db` | `Session` | open session |
| `workspace_id` | int | equality on the row's `workspace_id` |
| `machine_ids` | `list[int]` | machines asked for; duplicates, unknown ids and `0` are harmless |

**Returns:** a `dict` from machine id to `MachineActivityEvent`. Key order is not part of the contract.

**Rules:**
- **R1.** An empty `machine_ids` (`[]`, or `None`) returns `{}`.
- **R2.** Each machine asked for that has a status row gets one entry: its key is the machine id, its value the machine's `status_updated` row with the newest `created_at`.
- **R3.** A machine with no status row, an unknown id and `0` have no entry. A machine not asked for has no entry, even when it has status rows. An id listed twice gives one entry.
- **R4.** Only `event_type == "status_updated"` counts, exactly: rows of other types are ignored when newer, when their metadata has a `"status"` key, and when they carry the same `created_at` as the newest status row.
- **R5.** Workspace isolation follows the row, as `get_by_machine` R2: a status row of another workspace on the same machine id is ignored when newer, and when it carries the same `created_at`.
- **R6.** [BUG-1090] (HR-6) On a `created_at` tie the row with the highest `id` is the value, so for every machine the entry is the row `get_latest_status_by_machine` returns. *(Today: no ordering is requested among the tied rows, and the last one the database produces is kept. Verified: after the lower-`id` row was updated the map held it, while `get_latest_status_by_machine` returned the higher `id`.)*
- **R7.** ✅ (Q2) The state of the machine and of its factory is not looked at, as `get_latest_status_by_machine` R6.
- **R8.** The metadata is not looked at, as `get_latest_status_by_machine` R7: a newest status row with no metadata is the value.

**Errors:** none.

**Side effects:** none

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 18–25 | keyword-only parameters; defaults `skip=0`, `limit=100`, filters `None` | Notes for the test designer; `get_by_machine` R6, R14 |
| 27–30 | `machine_id` AND `workspace_id`; no join to machines or factories | `get_by_machine` R1, R2, R3, R4, R16 |
| 31–32 | `from_date is not None`: bound / none; `>=` start of day; date of a `datetime` | `get_by_machine` R9, R11, R12; Inputs |
| 33–34 | `to_date is not None`: bound / none; `<=` end of day | `get_by_machine` R10, R11, R12 |
| 35–36 | `if event_type:` `None` / `""` skip; exact match | `get_by_machine` R13, R14, R15 |
| 38 | `created_at` desc, `id` desc | `get_by_machine` R5 |
| 39–41 | offset / limit; `limit=0`; negative values; empty / many | `get_by_machine` R6, R7, R8, Errors |
| 52–57 | machine AND workspace AND `status_updated`; no parent, no metadata | `get_latest_status_by_machine` R3, R5, R6, R7 |
| 58 | `created_at` desc, `id` desc | `get_latest_status_by_machine` R1, R2 |
| 59 | `.first()`: row / `None` | `get_latest_status_by_machine` R1, R4 |
| 69–70 | `if not machine_ids`: empty → `{}` | `get_latest_status_map` R1 |
| 72–84 | newest `created_at` per machine among status rows of the workspace, for the ids asked | `get_latest_status_map` R2, R3, R4, R5, R7, R8 |
| 86–94 | join on machine and timestamp: more than one row on a tie | `get_latest_status_map` R2, R6 |
| 95–98 | workspace AND `status_updated` on the outer row | `get_latest_status_map` R4, R5 |
| 99 | no `ORDER BY` (BUG-1090) | `get_latest_status_map` R6 |
| 101 | dict by machine id: last row wins; empty / one / many | `get_latest_status_map` R2, R3, R6 |
| 104 | module singleton | Not specified |
