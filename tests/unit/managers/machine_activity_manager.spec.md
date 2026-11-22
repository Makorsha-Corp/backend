# Spec — `app/managers/machine_activity_manager.py`

> **Status:** APPROVED (2026-10-31; nothing open)
> **Source commit:** e48a092

> **Review round 2026-10-31.** **The owner's own answer (2026-10-31, relayed by the main session):** Q1: bug, but not by rounding: a third decimal in maintenance `cost` is refused with 400 at the input schema, and the log records the stored form ("5.00 → 7.00"); the rule lives in `machine_maintenance_log_manager.spec.md`. **Delegated:** Q2–Q6 accepted as suggested, decided by Claude under the reviewer's delegation (2026-10-31). None of those is the owner's own answer. New bugs: BUG-1140, BUG-1141. BUG-1091 updated (Q3, FU-4).
>
> **Routed here and written as rules or questions:** machine activity event DAO FU-1 (a) Q2; (b) Q4; (c) BUG-1091, `log_event` R6; (d) `log_event` R2. DAO FU-2 (a) Q5; (b) Q6. Machine manager FU-8, the "404 if missing" half: Q2 (the other half is BUG-1090, closed in the DAO spec). Nothing else in those specs was edited.
>
> **Standing decisions applied here (not asked again):**
> 1. A log of activity is history (the owner's ledger ruling, decided for this table; DAO Q1): it stays complete and readable for a deleted machine, and is never hidden by a parent's state.
> 2. A missing `ORDER BY` is a bug; physical row order is not an order.
> 3. HR-16: a row linking to another workspace's row is invalid data, refused on write, and no response shows another workspace's ids or names.
>
> **Verified by running** (throwaway scripts `h.py`, `m1.py` … `m4.py` in `C:\Users\User\AppData\Local\Temp\claude\E--Projects-Makorsh-Corp-backend\5dcda696-13dd-4b73-983c-11d3c05a8ed9\scratchpad\macm\`, each transaction rolled back against `marker_test`; nothing committed): every "Today:" note below; `format_field_value` on 17 values; `collect_field_changes` on every branch and across `Decimal`, enum, `bool`, date; `status_from_activity` on every shape; `log_event` with each default, `{}`, nested metadata, blank and 50 / 51 character types, `None` fields, unknown machine / workspace / performer, `0`, `Decimal` and `datetime` in metadata, a foreign, a deleted and a deleted-factory machine, savepoint roll-back; `list_events` with own / foreign / unknown / `0` / `-1` machine, an invalid row from both sides, a deleted, a deleted-factory and an inactive machine, filters, defaults, negative paging, statement counts for 4 and 1000 events; `get_latest_status` and the map with the same inputs, statement counts; `update_log` of the maintenance manager with six costs; delete of an attachment linked to a foreign machine (Cloudinary patched); a work order on a foreign machine through start, void, `finalize_completion`, line consumption, quantity adjustment and `PUT` (stock postings patched in the last two). **Over HTTP** (`TestClient`, overridden dependencies, rolled back): `GET /machines/{id}/activity/` with every metadata shape of Q5 and Q6. **Not run:** two concurrent transactions; the intended behavior of any bug rule; `complete_as_planned` past its planned-date check (read: same path as start); production data.

## Review
> All answered; applied 2026-10-31.

### Quick list — all answered
| # | What the code does today, in plain words | Answer | Decided by |
|---|---|---|---|
| Q1 | A maintenance cost edit logs a figure that was never stored, and logs a change when the cost did not change | bug — a third decimal is refused with 400 at the input schema, and the log records the stored form; rule in the maintenance manager spec | **owner** |
| Q2 | `get_latest_status` says "404 if missing" and raises nothing | bug — 404 as `list_events` (BUG-1140) | Claude, delegated |
| Q3 | Once BUG-1091 is fixed, an old attachment linked to a foreign machine can no longer be deleted | the delete proceeds, the event is skipped (BUG-1091) | Claude, delegated |
| Q4 | One page of activity makes one extra read per entry | bug — performers read together (BUG-1141) | Claude, delegated |
| Q5 | The API leaves out `note`, `old_quantity`, `new_quantity` and the attachment keys | intended | Claude, delegated |
| Q6 | One stored row of the wrong shape makes the page holding it a 500 | intended; the read-only query stays to be run once | Claude, delegated |

Decided by house rule: an activity row can be written for another workspace's machine (BUG-1091).

### House-rule violations — applied automatically

- **HR-16** `log_event` R6 — the machine is not checked against the workspace, so a row of workspace A can be stored on a machine of workspace B. Intended: 404 `Machine with ID <id> not found`, nothing written.
**Answer:** bug — per HR-16 (house rule)
**Resolution:** 🐞 BUG-1091, logged from DAO FU-1 (c), updated in this round (Q3, FU-4). Rules: `log_event` R6.
- **HR-6** `get_latest_status_map` R2 — reached through this manager; the fix is in the DAO.
**Answer:** bug — per HR-6 (house rule)
**Resolution:** 🐞 BUG-1090, logged at the DAO. Rules: `get_latest_status_map` R2.

**BUG-1091 and the order workflow (checked, so not an OWNER item).** The bug row says stored work order machines reach `log_event`. They do, but nothing they write survives, and the fix changes no reachable outcome. An order with another workspace's machine (BUG-1016) stops at `start_work_order`: 404 `Machine with ID <id> not found`, from `create_machine_event` today, and from `log_event` after the fix when a pending stock line comes first, with the same text. The transaction rolls back either way. `PUT` cannot put such a machine on a started order (400, structural fields locked). With a row built directly as `IN_PROGRESS`, void and completion answer the same 404; only line consumption and quantity adjustment write a row today, and no API path makes that state.

Every other writer is safe: `create_machine`, `update_machine`, `delete_machine`, `create_machine_event`, maintenance logs, machine items, stock postings and `reconcile_machine_item` all read the machine or a row of it inside the workspace first. So `POST /attachments/...` is the one path that stores such a row (Q3).

Checked and **not** violated: **HR-1, HR-2, HR-3** — `event_type` and `description` are composed by the callers; only `get_by_machine`'s filter takes user text, and it only compares. **HR-4** — the table has no soft-delete column, and standing decision 1 settles parents. **HR-5, HR-6** on `list_events` — DAO `get_by_machine` R5, R15. **HR-7** — `GET /machines/{id}/activity/` enforces `skip >= 0`, `1 <= limit <= 1000`. **HR-8** — no `LIKE`. **HR-9** — nothing here stamps a row. **HR-10** — only `log_event` writes, and it checks no state; the check-then-write on status changes is BUG-960. **HR-11 … HR-14** — no external system, no batch. **HR-15** — nothing here rounds; Q1 is about input. **HR-16** on reads — `list_events` answers a foreign machine exactly as an unknown one, and the map and `get_latest_status` return nothing for one unless an invalid row exists (R4, R3 below), which no response shows.

### Questions — answered

### Q1. OWNER — A maintenance cost edit logs a figure that was never stored — bug, in the maintenance manager spec (owner's answer)
**Background:** A maintenance log has a `cost`, stored with 2 decimals (`Numeric(15, 2)`), so the database rounds it half up. `MachineMaintenanceLogUpdate.cost` is a plain `Decimal` with no limit on decimals. An edit compares the stored cost with the value as sent, before the database rounds it, and writes the sent value into the machine's activity log. A log of activity is history, so a wrong entry stays. Nothing else reads that text, and no total is computed from it.
**What happens today:** Verified through `update_log`, stored cost 12.35: sending `12.354` writes an entry "12.35 → 12.354", and the stored cost stays 12.35: an entry with no change behind it. From 20.00, sending `20.005` stores 20.01 and logs "20.00 → 20.005", a figure that exists nowhere else. Sending `20` logs "12.35 → 20" and stores 20.00. Sending `12.350` logs nothing, correctly. The stored cost is always right; only the log differs.
**Example:** A supervisor re-saves a repair costing 12.35 from a form that computed 12.354. The cost does not change, and the machine's history now says the cost was changed to 12.354.
**Rules affected:** `collect_field_changes` R7
**Suggested answer:** `bug — cost is rounded half up to 2 decimals (HR-15) in MachineMaintenanceLogCreate and MachineMaintenanceLogUpdate, before it reaches the compare, so the entry shows the stored figure and an edit that stores the same cost writes no entry.` No rule of this manager changes: R7 stays as it is and the input changes. The fix goes in the maintenance schemas; that manager has no spec yet (FU-3). No input schema limits or rounds decimals today, so this would be the first; rejecting more than 2 decimals with 422 is the alternative. `intended` leaves the entries as they are, since the stored cost is right. Entries already written stay either way: a log of activity is history.
**Answer:** bug, but not by rounding: a third decimal in maintenance `cost` is refused with 400 at the input schema, and the log records the stored form ("5.00 → 7.00"). **The owner's own answer (2026-10-31).**
**Resolution:** the rule lives in `machine_maintenance_log_manager.spec.md`: Q2, `update_log` R12a, `create_log` R12, with the bug. No new ID here, so one fault has one row. The suggested rounding above was not chosen. `collect_field_changes` stays generic: R7 is unchanged, and the maintenance manager hands it the stored form. Rules: `collect_field_changes` R7 ✅.

### Q2. `get_latest_status` says "404 if missing" and raises nothing — 🐞 BUG-1140
**Background:** A machine's current status is the newest `status_updated` row of its log. Before reading it, `get_latest_status` looks the machine up inside the workspace, with the comment "404 if missing", but the result is thrown away. The sibling `list_events` makes the same lookup and does raise. Three callers exist: machine responses (`_to_machine_response`, with a machine it already holds), `create_machine_event` (which has already answered 404) and `_set_machine_status` (work orders, which goes on to `create_machine_event`).
**What happens today:** An unknown id, `0` and another workspace's machine all return `None` (verified). The lookup is one wasted read per call. Through the API nothing differs, because each caller holds the machine or answers 404 next: a start on a foreign machine answers 404 `Machine with ID <id> not found` (verified).
**Example:** A caller asks for the status of machine 999999, which does not exist. The comment promises a 404; it gets `None`, the same as a real machine that has never had a status.
**Rules affected:** `get_latest_status` R2, R3, R4
**Suggested answer:** `bug — raises 404 Machine with ID <id> not found, as list_events, nothing written; a machine in the workspace with no status row still returns None.` It also stops an invalid row reaching workspace A (R4). Not an OWNER item, though `_set_machine_status` belongs to the work order flow: the status and text a user sees there stay the same, and no figure moves. Alternative: `bug — drop the lookup and the comment, keep None`, which saves the read and leaves R4.
**Answer:** bug — raises 404 Machine with ID <id> not found, as list_events, nothing written; a machine in the workspace with no status row still returns None.
**Resolution:** 🐞 BUG-1140 (pattern `not-found-check-discarded`), decided by Claude under the reviewer's delegation (2026-10-31): the suggested answer is accepted. Rules: `get_latest_status` R2 ✅, R3, R4, Errors.

### Q3. Once BUG-1091 is fixed, an old attachment on a foreign machine can no longer be deleted — 🐞 BUG-1091
**Background:** BUG-1091 was found through attachments: signing and confirming with another workspace's machine id stores a link and an `attachment_added` row. Its fix refuses at `POST /attachments/sign` and in `log_event`. But links already stored stay, and deleting an attachment writes `attachment_removed` through `log_event` for each link, inside the delete.
**What happens today:** The delete succeeds and writes a second invalid row (verified). After the fix as worded, that `log_event` answers 404, the delete rolls back and the attachment cannot be removed by the one workspace that sees it.
**Example:** Workspace A has an old drawing linked to B's machine 812. After the fix a user deletes it and gets "Machine with ID 812 not found", for a machine that A's page does not show.
**Rules affected:** `log_event` R6; `app/managers/attachment_manager.py` `_log_attachment_entity_events`
**Suggested answer:** `the delete proceeds and writes no activity row: _log_attachment_entity_events skips a machine link whose machine is not in the workspace, on delete only; log_event still refuses, and confirm still refuses.` HR-16 refuses writes that set a link, and this removes one. Same bug, no new ID (FU-2). Alternative: leave the 404 and clear such links with a script, using `scripts/find_cross_workspace_rows.py` to find them.
**Answer:** the delete proceeds and writes no activity row: _log_attachment_entity_events skips a machine link whose machine is not in the workspace, on delete only; log_event still refuses, and confirm still refuses.
**Resolution:** part of 🐞 BUG-1091, no new ID, decided by Claude under the reviewer's delegation (2026-10-31): the suggested answer is accepted. The rule belongs to the attachment manager, not specified yet (FU-2). Rules here: `log_event` R6, unchanged.

### Q4. One page of activity makes one extra read per entry — 🐞 BUG-1141
**Background:** Each activity entry shows who did it. `list_events` reads the performer's profile entry by entry. The DAO could load them together: the event has a `performer` relationship, and one read by a list of ids would do.
**What happens today:** Verified: 4 events by 2 people take 5 reads (machine, events, 3 profiles). 1000 events by one person take 1002 reads, because a repeated person is read again. The web page asks for 100, so about 102 reads per open; the API allows 1000.
**Example:** Opening a busy machine's activity panel runs 102 database reads to show 100 lines, all by the same 3 people.
**Rules affected:** `list_events` R9
**Suggested answer:** `bug — performers are read together, at most one read for the whole page; the result is unchanged.` No figure and no answer changes, only speed. Alternative: `intended` — bounded by the page size, and nobody has complained.
**Answer:** bug — performers are read together, at most one read for the whole page; the result is unchanged.
**Resolution:** 🐞 BUG-1141 (pattern `n-plus-one-read`), decided by Claude under the reviewer's delegation (2026-10-31): the suggested answer is accepted. Rules: `list_events` R9.

### Q5. The API leaves out stored `note`, `old_quantity`, `new_quantity` and the attachment keys — ✅ intended
**Background:** Each event stores a free-form metadata object. `GET /machines/{id}/activity/` passes it through a fixed list of 10 keys (`MachineActivityEventMetadata`), and anything else is dropped from the response, not from the table. The frontend's type lists the same 10 and it reads only `status`, `changes`, `maintenance_log_id` and `work_order_id`.
**What happens today:** Verified over HTTP. Left out: `note` (status changes); `old_quantity`, `new_quantity` (a work order line's quantity adjustment); `attachment_id`, `file_name`, `mime_type`, `file_size` (attachments, whose `metadata` comes back with every key empty). Nothing is lost for a reader of the panel: `description` already says "Status set to idle (belt)", "Adjusted Bolt from 3 to 5", "Attached a.png". Only `mime_type`, `file_size` and `attachment_id` are in no text. Two listed keys, `transfer_order_id` and `purchase_order_id`, are written by nobody.
**Example:** An API client wants the attachment behind an `attachment_added` entry. It gets the text "Attached a.png" and no id.
**Rules affected:** none here: `list_events` R6 returns the stored metadata whole. The dropping is in the service's response (FU-1).
**Suggested answer:** `intended — the table keeps everything, the text carries what a reader needs, and nothing reads these keys.` Not an OWNER item: a dropped copy of a line's quantity changes no figure, and the stock movement has its own ledger entry. Alternative: `bug — the schema lists the seven keys`, additive and safe, if an API client or the panel will want them; the two unused keys could go at the same time.
**Answer:** intended — the table keeps everything, the text carries what a reader needs, and nothing reads these keys.
**Resolution:** decided by Claude under the reviewer's delegation (2026-10-31): rule unchanged. Rules: `list_events` R6 ✅. FU-1.

### Q6. One stored row of the wrong shape makes the page holding it a 500 — ✅ intended
**Background:** The same response list has types: `quantity: int`, `item_id: int`, `status: str`, and each `changes` entry needs `field` and `label`, with `from_value` a string. The service validates each row and nothing catches a failure. Stock is in whole units: fractional quantities are refused before any posting.
**What happens today:** Verified over HTTP: a row with `quantity: 2.5`, `quantity: "x"`, `status: 5`, `item_id: 1.5`, a `changes` entry with no `label` or a number in `from_value`, or metadata that is a list or a string, gives a 500 for any page that holds it, and only those pages (a smaller `limit`, a `skip` past it or another `event_type` gives 200). `quantity: 2.0` and `"5"` are accepted and returned as integers.
**No writer can store one.** All read: `quantity` comes from `_machine_in` / `_machine_out` (`qty: int`; purchase receipts, reversals, returns and transfers convert through `_delta_to_int` / `_quantity_to_int`, which refuse a fraction with 400; work order consumption refuses one too), and from `machine_item_manager` (integer columns). `log_event` itself would accept `2.5` (R3), and a `Decimal` fails at the flush (R9). `changes` values come from `format_field_value` or `str()`. Older commits were not read one by one.
**Example:** A hand-corrected row with `quantity: 2.5` on Press 4 would break Press 4's activity panel, and nothing else.
**Rules affected:** none here (FU-1).
**Suggested answer:** `intended — no code path writes such a row, and tolerating one would hide a damaged record.` Not an OWNER item: no stock figure is involved, this is a read of a text log. To settle production data, run once (read-only; verified on `marker_test`, it counts `2.5` and `"x"` and not `2`, `2.0` or an absent key): `SELECT count(*) FROM machine_activity_events WHERE metadata->>'quantity' IS NOT NULL AND metadata->>'quantity' !~ '^-?[0-9]+(\.0+)?$';`. Alternative: `bug — a row that does not fit is returned with metadata null and logged, so the page still opens.`
**Answer:** intended — no code path writes such a row, and tolerating one would hide a damaged record.
**Resolution:** decided by Claude under the reviewer's delegation (2026-10-31): no rule here (FU-1). The read-only query above has not been run on production; a non-zero count reopens this.

## Follow-ups for other reviews
> Nothing below is a rule of this manager. Whoever describes the named module must read this list first.

| # | Where it must be looked at | What | Came from |
|---|---|---|---|
| FU-1 | **Machine service, schemas** (`app/services/machine_service.py` `get_machine_activity`, `app/schemas/machine_activity_event.py`) | Q5 and Q6 were answered `intended`, so nothing changes: the facts stay for that spec. `if e.metadata_json` sends `None`, `{}` to `metadata: null`; a filled object comes back with all 10 keys, unset ones `null`. `MachineActivityEventMetadata` has no `extra` setting, so unknown keys are ignored. `performer_name` is `profile.name`, `null` with no performer. No spec of this service exists yet. | Q5, Q6 |
| FU-2 | **Attachment manager** (`app/managers/attachment_manager.py`, not yet specified) | BUG-1091: `create_pending_attachment` / `POST /attachments/sign` checks no entity; `_log_attachment_entity_events` calls `log_event` for each link, on confirm and on delete. Rule, by Q3: the delete proceeds and writes no activity row for a machine link whose machine is not in the workspace, on delete only; confirm still refuses. The other entity types were not checked. | BUG-1091, Q3 |
| FU-3 | **Machine maintenance log manager** (`machine_maintenance_log_manager.spec.md`) | The owner's Q1 answer is applied there: Q2, `update_log` R12a, `create_log` R12. That spec's Q2 must carry it, and its FU-4 is answered here: `collect_field_changes` does not change. `MAINTENANCE_LOG_FIELDS` is the third field list of `collect_field_changes`; it is the only one with an enum, a date and a `Decimal`. | Q1 |
| FU-4 | **`docs/testing/bugs.md`, BUG-1091** | Done: the row's "the same way" now states that such an order stops at start and its row never survives. | checking the fix |
| FU-5 | **Machine DAO** (`tests/unit/dao/machine.spec.md`, `search_advanced` R12c), from DAO FU-1 (d) | `log_event` with `metadata=None` stores JSON `null`, not SQL `NULL` (`log_event` R2). The only writer of `status_updated` always passes metadata, so such a row is not a status row in practice. Nothing to change. | DAO FU-1 (d) |

Answered here: machine activity event DAO FU-1 (a) Q2, (b) Q4, (c) `log_event` R6, (d) `log_event` R2, FU-5; DAO FU-2 (a) Q5, (b) Q6. Machine manager FU-8: Q2.

## Overview
`MachineActivityManager` is the only writer of `machine_activity_events`, the history of a machine: created, edited, deactivated, status changes, stock moved, maintenance, attachments. It also turns an edit into the list of field changes stored with an entry, and reads the log and the machine's current status, which is the newest `status_updated` row. Machine, machine item, maintenance, stock posting, ledger, work order and attachment managers write through it, and `MachineService` reads through it. It is meant to protect workspace isolation and keep the log complete. It never commits, never updates or deletes a row, and takes no lock.

**Callables:** 7 specified · 2 not specified
**Externals to mock:** none. No code here reads the clock. (`created_at` is a Python column default: assert set, not its value.)
**Integration-only behavior:** the HTTP status of the 404; `skip >= 0`, `1 <= limit <= 1000` and date parsing at `GET /machines/{id}/activity/`; the service's response schema (Q5, Q6). Two real concurrent transactions.

**Facts for the test designer**
- Import: `from app.managers.machine_activity_manager import MachineActivityManager, machine_activity_manager, MACHINE_LOG_FIELDS, MACHINE_ITEM_LOG_FIELDS`. `MachineActivityManager()` takes no arguments and holds no per-call state. `format_field_value` and `status_from_activity` are static: callable on the class and on an instance. All parameters are positional-or-keyword.
- `MACHINE_LOG_FIELDS`, in order: `name` "Name", `factory_id` "Factory", `factory_section_id` "Section", `model_number` "Model number", `manufacturer` "Manufacturer", `note` "Note". `MACHINE_ITEM_LOG_FIELDS`, in order: `qty` "Quantity", `req_qty` "Required quantity", `defective_qty` "Defective quantity".
- Table `machine_activity_events`, constraints and metadata storage: DAO spec, **Model facts**. Foreign keys: `machine_activity_events_workspace_id_fkey`, `machine_activity_events_machine_id_fkey`, `machine_activity_events_performed_by_fkey`.
- `HTTPException` is `fastapi.HTTPException`: assert `.status_code` and `.detail`. Database errors are `sqlalchemy.exc.IntegrityError` / `DataError` with `.orig` a `psycopg2` error class.
- `MaintenanceTypeEnum` (`app.models.enums`) is a `str` enum, members such as `REPAIR`; a plain `enum.Enum` member of your own covers the non-`str` case. `Profile` has no workspace column and no soft delete.
- Collaborator rules cited, not repeated: `tests/unit/dao/machine_activity_event.spec.md`, base DAO `get_by_id_and_workspace` (raw: returns soft-deleted rows).

**Notes for the test designer**
- Workspaces and profiles from `tests/unit/factories.py`. Build `Factory(workspace_id, name, abbreviation)`, `Machine(workspace_id, factory_id, name)` and `MachineActivityEvent(...)` directly (add + flush), as the DAO spec's Notes. `autoflush=False`: flush before calling the manager. Give `created_at` explicitly when order matters.
- `format_field_value`, `collect_field_changes` and `status_from_activity` need no database: any object with the attributes serves as the record (`types.SimpleNamespace`), and an unsaved `MachineActivityEvent(metadata_json=...)` as the event.
- **Stored JSON `null` (R2):** read it with `text("SELECT metadata::text, metadata IS NULL ...")`: it gives `('null', False)`, against `('{}', False)` for `{}`.
- **Hidden parents:** soft-deleted machine = `is_deleted=True, is_active=False`; soft-deleted factory = `is_deleted=True` with a live machine in it; inactive-but-live machine = `is_active=False, is_deleted=False`.
- **BUG-1091:** strict xfail: the machine of W2, the call from W, assert the `HTTPException` and that the row count is unchanged. Today it stores the row. For an unknown id today's error is `IntegrityError`, so that case needs `with db.begin_nested():` inside `pytest.raises(...)` until the fix, and is strict xfail too.
- **BUG-1140:** strict xfail, each case of R3 and R4: today `None` or the row comes back. R2 and R5 pass today and must keep passing.
- **BUG-1141:** strict xfail: 1000 is not needed, 5 entries by one person give 7 reads today against at most 3; compare the returned tuples as well.
- **BUG-1090:** one pass-through case, as the DAO spec's Notes describe the tie, non-strict xfail.
- **The invalid row (`list_events` R3, `get_latest_status` R4, `get_latest_status_map` R3):** build the row directly, with W's `workspace_id` on W2's machine.
- **Counting reads (R9):** a `before_cursor_execute` listener on `db.connection()`. Assert the count only, never the SQL text.
- **Database errors** abort the transaction: `with db.begin_nested():` inside `pytest.raises(...)`. **Not committed:** `sp = db.begin_nested()`, call, `sp.rollback()`, re-read. A `TypeError` from a value JSON cannot hold arrives as `sqlalchemy.exc.StatementError`, with `.orig` a `TypeError` and no `pgcode`.

## Not specified
- `MachineActivityManager.__init__` — stores the DAOs, no logic
- `machine_activity_manager` — module-level singleton, no logic

The checklist (`docs/testing/unit-test-checklist-by-layer.md`) marks nothing of this file as possibly unused, and every public method has a caller. The `datetime` branch of `format_field_value` has no caller today: none of the three field lists holds a `datetime` (`maintenance_date` is a `Date`). It is a pure branch, so it stays specified. No legacy test calls this manager.

---

## `MachineActivityManager.format_field_value(value)`
**Shape:** mapper
**Persistence:** pure
**Visibility:** internal (used by: `collect_field_changes`; static)

**Purpose:** The text stored for one value in a field change.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `value` | any | not validated |

**Returns:** a `str`, or `None`.

**Rules:**
- **R1.** `None` → `None`.
- **R2.** Anything with a `value` attribute → `str` of that attribute, checked first: `MaintenanceTypeEnum.REPAIR` → `"REPAIR"`, a plain enum member of value `1` → `"1"`, a non-enum object with `value = 7` → `"7"`.
- **R3.** A `datetime` → `YYYY-MM-DD HH:MM`, seconds dropped, no time zone change: `datetime(2026, 3, 5, 7, 9, 59)` → `"2026-03-05 07:09"`.
- **R4.** A `date` → ISO: `"2026-03-05"`.
- **R5.** Anything else → `str(value)`: `Decimal("1.50")` → `"1.50"` (scale kept), `Decimal("100")` → `"100"`, `5` → `"5"`, `0` → `"0"`, `False` → `"False"`, `""` → `""`, `" x "` → `" x "`.

**Errors:** none.

**Side effects:** none

---

## `MachineActivityManager.collect_field_changes(record, update_dict, fields)`
**Shape:** compute
**Persistence:** pure
**Visibility:** public (used by: `MachineManager.update_machine`, `MachineItemManager.update_machine_item`, `MachineMaintenanceLogManager.update_log`, each before it writes)

**Purpose:** The list of tracked fields an update would change, as stored in an entry's `changes`.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `record` | any | read by attribute; not validated |
| `update_dict` | `dict` | field → new value, as the caller has it |
| `fields` | `dict[str, str]` | field → label; the tracked fields |

**Returns:** a `list` of `{"field", "label", "from_value", "to_value"}`, possibly empty.

**Rules:**
- **R1.** Each field of `fields` present in `update_dict` with a value different from the record's gives one entry: `field`, its `label`, `from_value` the record's value and `to_value` the new one, both through `format_field_value`.
- **R2.** Entries follow the order of `fields`, not of `update_dict`: `{"c": "y", "a": 2}` with fields `a, b, c` gives `a`, then `c`.
- **R3.** A field of `fields` absent from `update_dict` gives no entry, and the record's attribute is not read.
- **R4.** A key of `update_dict` not in `fields` is ignored (`updated_by`).
- **R5.** Equal values give no entry, by Python `==`: same value; `Decimal("100.00")` and `Decimal("100")`; a `str` enum member and its string; `1` and `True`; `None` and `None`.
- **R6.** `None` to a value and a value to `None` give an entry, with `None` on that side. `None` to `""` is a change: `from_value` `None`, `to_value` `""`.
- **R7.** ✅ (Q1) The new value is compared and shown as given, not as the column would store it; for `cost` the refusal of a third decimal and the stored form come from the caller (`machine_maintenance_log_manager.spec.md` `update_log` R12a): a record holding `Decimal("12.35")` with `Decimal("12.354")` gives an entry `"12.35"` → `"12.354"`, and `Decimal("100.00")` with `Decimal("100.5")` gives `"100.00"` → `"100.5"`.
- **R8.** An empty `update_dict` or empty `fields` gives `[]`.
- **R9.** The record is not changed, and nothing touches the database.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| a tracked field in `update_dict` that the record lacks (no caller does this) | `AttributeError` | — |

**Side effects:** none

---

## `MachineActivityManager.log_event(session, machine_id, workspace_id, event_type, description, performed_by=None, metadata=None)`
**Shape:** event-log
**Persistence:** writes
**Visibility:** public (used by: `MachineManager` create / update / delete / status, `MachineItemManager`, `MachineMaintenanceLogManager`, `_machine_in`, `_machine_out`, `LedgerManager.reconcile_machine_item`, `WorkOrderManager`, `AttachmentManager._log_attachment_entity_events`)

**Purpose:** Append one entry to a machine's history.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `session` | `Session` | open session |
| `machine_id` | int | [BUG-1091] must be a machine of the workspace; soft-deleted counts |
| `workspace_id` | int | the row's workspace |
| `event_type` | str | at most 50 characters; no list of values |
| `description` | str | any text, `""` included |
| `performed_by` | int \| `None` | a profile id; `None` = no performer |
| `metadata` | `dict` \| `None` | stored whole; must be JSON-serialisable |

**Returns:** the `MachineActivityEvent`, flushed (`id` set), not committed.

**Rules:**
- **R1.** One row is added on every call, with `workspace_id`, `machine_id`, `event_type`, `description`, `metadata_json`, `performed_by` as given. Two identical calls give two rows. No existing row changes.
- **R2.** `metadata=None` stores JSON `null`, not SQL `NULL`; it reads back as `None`. `{}` is stored as `{}`. `performed_by` left out stores `NULL`.
- **R3.** Metadata is stored as given: nested lists and objects, `None` inside them and floats all come back equal (`{"a": [1, {"b": None}]}`, `{"quantity": 2.5}`).
- **R4.** `event_type` is not checked against any list: `""` and 50 characters are stored. `description` may be `""`.
- **R5.** `created_at` is set on the row, naive (no time zone).
- **R6.** [BUG-1091] (HR-16) A machine that is not in the workspace (another workspace's, an unknown id, `0`, or an unknown `workspace_id`) → 404 `Machine with ID <id> not found`, nothing written, and the answer is the same for each. *(Today: another workspace's machine is stored under the caller's workspace; the others raise `IntegrityError`, see Errors.)*
- **R7.** A soft-deleted machine and a machine in a soft-deleted factory are accepted, also after BUG-1091: `delete_machine` writes its `deactivated` entry after the soft delete, and a log of activity is history.
- **R8.** Unknown `performed_by`, or `0` → `IntegrityError` on `machine_activity_events_performed_by_fkey`, no row. A performer is not checked against the workspace.
- **R9.** A metadata value JSON cannot hold (`Decimal`, `datetime`) fails at the flush, no row. Every caller today passes plain values.
- **R10.** Flushed, not committed: rolling back a savepoint removes the row.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| [BUG-1091] machine not in the workspace | `HTTPException` 404 | `Machine with ID <id> not found` |
| Today: unknown `machine_id` or `0` | `IntegrityError` / `ForeignKeyViolation`, pgcode `23503` | `machine_activity_events_machine_id_fkey` |
| Today: unknown `workspace_id` | `IntegrityError` / `ForeignKeyViolation`, pgcode `23503` | `machine_activity_events_workspace_id_fkey` |
| unknown `performed_by` | `IntegrityError` / `ForeignKeyViolation`, pgcode `23503` | `machine_activity_events_performed_by_fkey` |
| `event_type` or `description` `None` | `IntegrityError` / `NotNullViolation`, pgcode `23502` | — |
| `event_type` over 50 characters | `DataError` / `StringDataRightTruncation`, pgcode `22001` | — |
| metadata not JSON-serialisable | `StatementError`, `.orig` a `TypeError` | — |

**Side effects:** one `machine_activity_events` row, flushed. No commit.

---

## `MachineActivityManager.list_events(session, machine_id, workspace_id, skip=0, limit=100, from_date=None, to_date=None, event_type=None)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `MachineService.get_machine_activity` ← `GET /machines/{id}/activity/`, passing every argument)

**Purpose:** A machine's history, one page at a time, each entry with who did it.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `session` | `Session` | open session |
| `machine_id` | int | must be a machine of the workspace |
| `workspace_id` | int | caller's workspace |
| `skip`, `limit` | int, defaults `0`, `100` | not validated here |
| `from_date`, `to_date` | `date` \| `None` | as DAO `get_by_machine` |
| `event_type` | `str` \| `None` | as DAO `get_by_machine` |

**Returns:** a `list` of 2-tuples `(MachineActivityEvent, Profile | None)`, possibly empty.

**Rules:**
- **R1.** For a machine of the workspace, the result is its events, newest first, with the filters and paging of DAO `get_by_machine` R5–R15; every argument reaches it unchanged.
- **R2.** A machine of another workspace, an unknown id, `0` or a negative id → 404 `Machine with ID <id> not found`, the answers differing only in the id the caller sent. No event is read.
- **R3.** (HR-16) A row of workspace A on a machine of workspace B shows nowhere: A gets R2, and B's list leaves it out (DAO `get_by_machine` R2).
- **R4.** (Standing decision 1; DAO Q1) A soft-deleted machine, a machine in a soft-deleted factory and an inactive machine all return every event.
- **R5.** A machine with no events → `[]`.
- **R6.** ✅ (Q5) The first element is the row as stored: `metadata_json` is whole, keys the API response leaves out included.
- **R7.** The second element is the performer's `Profile`, or `None` when `performed_by` is `None`. Two entries by one person hold the same instance.
- **R8.** With the defaults at most 100 entries come back; `limit=1000` gives 1000 of 1000; `limit=0` and `skip` past the end give `[]`. A negative `limit` or `skip` raises as DAO `get_by_machine` R8.
- **R9.** [BUG-1141] (Q4) All performers of a page are read together: the whole call makes at most three reads, however many entries and people, and R7 still holds. *(Today: two reads plus one per entry with a performer, a repeated person included: 4 entries, 3 with a performer, 5 reads; 1000 entries by one person, 1002 reads.)*
- **R10.** The call writes nothing.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| machine not in the workspace | `HTTPException` 404 | `Machine with ID <id> not found` |
| negative `limit` / `skip` | `DataError` | as DAO `get_by_machine` |

**Side effects:** none

---

## `MachineActivityManager.get_latest_status(session, machine_id, workspace_id)`
**Shape:** get
**Persistence:** reads
**Visibility:** public (used by: `MachineService._to_machine_response`, `MachineManager.create_machine_event`, `WorkOrderManager._set_machine_status`, all positionally)

**Purpose:** The newest status change of one machine, if any.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `session` | `Session` | open session |
| `machine_id` | int | [BUG-1140] must be a machine of the workspace; soft-deleted counts |
| `workspace_id` | int | equality on the row's `workspace_id` |

**Returns:** the `MachineActivityEvent`, or `None`.

**Rules:**
- **R1.** The machine's newest `status_updated` row is returned, as DAO `get_latest_status_by_machine` R1–R3, R7: rows of other types are ignored even when newer.
- **R2.** ✅ (Q2) A machine of the workspace with no status row → `None`.
- **R3.** [BUG-1140] (Q2) An unknown id, `0` or another workspace's machine → 404 `Machine with ID <id> not found`, the answers differing only in the id, as `list_events` R2. *(Today: `None`, nothing raised, despite the comment "404 if missing".)*
- **R4.** [BUG-1140] (Q2, HR-16) A `status_updated` row of workspace A on a machine of B never reaches A: A gets R3, and B's answer is not affected. No writer stores one (`create_machine_event` refuses). *(Today: the row is returned to A.)*
- **R5.** (DAO Q2) The row of a soft-deleted machine, and of a machine in a soft-deleted factory, is returned.
- **R6.** The call writes nothing.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| [BUG-1140] machine not in the workspace | `HTTPException` 404 | `Machine with ID <id> not found` |

**Side effects:** none

---

## `MachineActivityManager.get_latest_status_map(session, workspace_id, machine_ids)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `MachineService._to_machine_responses`, every list of machines)

**Purpose:** The newest status change of each of many machines, in one read.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `session` | `Session` | open session |
| `workspace_id` | int | equality on the row's `workspace_id` |
| `machine_ids` | `list[int]` | not checked against the workspace |

**Returns:** a `dict` from machine id to `MachineActivityEvent`.

**Rules:**
- **R1.** The result is that of DAO `get_latest_status_map` R1–R5, R7, R8: `[]` or `None` → `{}`, with no read at all; each machine with a status row has one entry; unknown ids, `0` and machines with no status row have none.
- **R2.** [BUG-1090] (HR-6) On a `created_at` tie the highest `id` is the value, so an entry equals what `get_latest_status` returns. *(Today: DAO `get_latest_status_map` R6.)*
- **R3.** No machine is looked up, so nothing is refused: another workspace's machine simply has no entry. A row of workspace A on a machine of B does appear for A, unlike `get_latest_status` R4; no writer stores one, and `_to_machine_responses` only passes machines of its own workspace.
- **R4.** The call writes nothing.

**Errors:** none.

**Side effects:** none

---

## `MachineActivityManager.status_from_activity(event)`
**Shape:** mapper
**Persistence:** pure
**Visibility:** public (used by: `MachineService._to_machine_response`, `MachineManager.create_machine_event`, `WorkOrderManager._set_machine_status`; static)

**Purpose:** The status held by a status row.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `event` | `MachineActivityEvent` \| `None` | saved or not; the `event_type` is not looked at |

**Returns:** the stored `status` value, or `None`.

**Rules:**
- **R1.** `None` → `None`.
- **R2.** An event with metadata `None` or `{}` → `None`.
- **R3.** Metadata with no `status` key → `None`.
- **R4.** Otherwise the stored value, unchanged and unchecked: `"IDLE"` → `"IDLE"`, `None` → `None`, `""` → `""`, `5` → `5`.
- **R5.** The event type is not looked at: any event with a `status` key gives its value (a `maintenance_logged` entry stores one).

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| metadata that is a non-empty list or string (no writer stores one) | `AttributeError` | — |

**Side effects:** none

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 15–28 | field lists | Facts for the test designer |
| 34–36 | constructor | Not specified |
| 40–41 | `value is None` | `format_field_value` R1 |
| 42–43 | `hasattr(value, "value")`, before the date checks | `format_field_value` R2 |
| 44–45 | `datetime` (before `date`: a `datetime` is a `date`); no caller today | `format_field_value` R3; Not specified |
| 46–47 | `date` | `format_field_value` R4 |
| 48 | fallback `str` | `format_field_value` R5 |
| 57 | loop over `fields`: empty / one / many, in that order | `collect_field_changes` R2, R8 |
| 58–59 | field absent → `continue` | `collect_field_changes` R3, R4 |
| 60 | attribute read; missing raises | `collect_field_changes` Errors |
| 62–63 | `==` → `continue` | `collect_field_changes` R5, R7 |
| 64–71 | entry built | `collect_field_changes` R1, R6, R7 |
| 84–91 | row built; no machine check (BUG-1091) | `log_event` R1–R7 |
| 92–93 | add, flush; database refusals | `log_event` R8, R9, R10, Errors |
| 107–109 | raw lookup inside the workspace | `list_events` R2, R3, R4 |
| 110–114 | `if not machine` → 404 | `list_events` R2 |
| 115–124 | event read, arguments passed on; defaults | `list_events` R1, R5, R8 |
| 125–128 | comprehension: empty / many; `if e.performed_by` truthy or not (`0` cannot exist); one read per entry (BUG-1141) | `list_events` R5, R6, R7, R9 |
| 136–138 | lookup, result discarded (BUG-1140) | `get_latest_status` R3, R4 |
| 139–141 | status read | `get_latest_status` R1, R2, R5 |
| 149–151 | pass-through; empty list returns early in the DAO | `get_latest_status_map` R1, R2, R3 |
| 155–156 | `not event`, `not event.metadata_json` | `status_from_activity` R1, R2 |
| 157 | `.get("status")` | `status_from_activity` R3, R4, R5, Errors |
| 160 | module singleton | Not specified |
