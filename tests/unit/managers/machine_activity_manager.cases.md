# Test cases — `app/managers/machine_activity_manager.py`

> **Spec:** `tests/unit/managers/machine_activity_manager.spec.md` (source commit e48a092)
> **Status:** READY
> **Revision:** 1 (2026-10-31) — the spec did not change. Additive, from `machine_activity_manager.verify.md` finding M2 (case-missing): an inactive, live machine works on `log_event` (MAC-LE-33) and `get_latest_status` (MAC-GS-21). No existing card, Convention or ID changed, none retired.
> **Counts:** 170 cases · 156 expected-to-pass · 14 expected-to-fail (bugs) · 10 deferred

## Reviewer summary
- **Per callable:** `format_field_value` 17 (0 bug) · `collect_field_changes` 21 (0 bug) · `log_event` 33 (5 bug) · `list_events` 47 (2 bug) · `get_latest_status` 21 (4 bug) · `get_latest_status_map` 18 (3 bug) · `status_from_activity` 13 (0 bug)
- **Depth:** full for `log_event`, the sole writer of the machine history. Lighter target (skill step 1a) for the rest: plain reads and pure helpers, no stock, money or order state. Each input the spec names still gets a card, because a When holds one call.
- **Expected-to-fail by bug:** BUG-1090 3 · BUG-1091 5 · BUG-1140 4 · BUG-1141 2. 2 of the 14 are non-strict (physical order); all others strict.
- **Answers and the cards that rest on them:** Q1 — MAC-CF-14, CF-15. Q2 — MAC-GS-10 … GS-15. Q4 — MAC-LI-44, LI-45. Q5 — MAC-LI-30.
- **Notable design choices:**
  - **Refusals in `log_event`.** The foreign machine cards use a plain `pytest.raises`, no savepoint, and check `db.new` is empty, because a savepoint's rollback would hide a write. The unknown id cards use the spec's savepoint: today they raise `IntegrityError`. The `Today:` rows of the Errors table have no pass card; a pass card there would test the buggy path, so they sit on the xfail cards.
  - **Filter before paging.** The hidden row is always newer than the skipped row, for `event_type`, `to_date`, another machine and the invalid row of another workspace. `from_date` has no such card: its hidden rows are older, so they sort behind the page.
  - **Substring matches.** `updated` and `status_updated_manual` each have a card on `list_events`, `get_latest_status` and the map; `status` on `list_events`.
  - **Ties both ways** on all three reads: higher id physically last (no update) and physically first (lower id updated). The map's two are non-strict, with a strict `ORDER BY` recorder (MAC-SM-14) and a pass card that one entry comes back (MAC-SM-11).
  - **MAC-SM-16 pins a stated rule:** `get_latest_status_map` R3 shows an invalid row to its own workspace, unlike `get_latest_status` R4. The spec accepts it, since no writer stores one and callers pass their own machines.
  - **Statement checks.** "No event is read" (`list_events` R2) and the read budget (R9) are counts, as the spec's Notes ask. Text is read only for `written`, `locked` and the map's `ORDER BY`.
  - The read budget is checked on both sides: MAC-LI-42 (one entry, 3 reads today) passes, MAC-LI-44 (5 entries) fails.
  - No `Author:` lines: a Claude executor writes the whole file. Race simulations: none.
- **Needs a decision:** None blocking. Spec gaps 1–3 weaken no rule card; see Spec gaps.

## Conventions for this module

**IDs.** `MAC` = `app/managers/machine_activity_manager.py`. `FV` format_field_value · `CF` collect_field_changes · `LE` log_event · `LI` list_events · `GS` get_latest_status · `SM` get_latest_status_map · `SA` status_from_activity.

**Actors and fixed values.**
- `M` = the singleton `machine_activity_manager` (`from app.managers.machine_activity_manager import MachineActivityManager, machine_activity_manager, MACHINE_LOG_FIELDS, MACHINE_ITEM_LOG_FIELDS`). `db` = the test's real session, always the first argument; the rest by keyword, except where a card writes a positional call. `result` = what the When call returns. The session does not autoflush.
- W1, W2 = two `workspaces` rows; U1, U2 = two `profiles` rows, from `make_workspace`, `make_profile` in `tests/unit/factories.py`.
- Classes: `Factory` (`app.models.factory`), `Machine` (`app.models.machine`), `MachineActivityEvent` (`app.models.machine_activity_event`), `MaintenanceTypeEnum` (`app.models.enums`), `HTTPException` (`fastapi`), `Decimal` (`decimal`), `SimpleNamespace` (`types`), `date`, `datetime`, `timedelta`, `timezone` (`datetime`), `text` (`sqlalchemy`).
- `Kind` = a plain enum of the test file: `class Kind(enum.Enum): A = 1; B = 2`.
- MISSING = `999999999`: an id no row of any table has.
- T1 = `datetime(2026, 3, 4, 10, 0, 0)`, T2 = `datetime(2026, 3, 5, 10, 0, 0)`, T3 = `datetime(2026, 3, 6, 10, 0, 0)`.
- FIELDS = `{"a": "Alpha", "b": "Beta", "c": "Gamma"}`, in that order.

**Externals.** None. Nothing is mocked. No code here reads the clock; `created_at` is checked as set, or given in the Given.

**Standing rows.** In every test, in this order, no Given line needed. `is_active True`, `is_deleted False`, `workspace_id W1.id` unless stated.
- Factories (`Factory(workspace_id, name, abbreviation)`): F1 `"Factory One"` / `"F1"`. FD `"Old Plant"` / `"OP"`, `is_deleted True` (`is_active` stays True). F9 `"Factory Nine"` / `"F9"`, `workspace_id W2.id`.
- Machines (`Machine(workspace_id, factory_id, name)`): M1 `"Press 1"`, M2 `"Press 2"` of F1. MD `"Press 4"` of F1, `is_deleted True`, `is_active False`. MF `"Lost Press"` of FD (live, in a soft-deleted factory). MA `"Idle Press"` of F1, `is_active False`, `is_deleted False`. M9 `"Far Press"` of F9, `workspace_id W2.id`.
- No `machine_activity_events` row exists unless the card's Given builds it.

**Given rows.** Built directly with `MachineActivityEvent`, never through `M` unless the line is written as code, flushed one at a time in the order written, so ids rise in that order. A line written as code is a step to run exactly, at that place. `db.add(P)` with no flush leaves P pending.
- **event** = `workspace_id W1.id`, `machine_id M1.id`, `event_type "item_added"`, `description "Logged"`; `metadata_json` and `performed_by` are not passed. The card gives `created_at`; after "but" it lists every other column that differs. `metadata_json None` means the keyword is passed with `None`.
- **status row** = an event, but `event_type "status_updated"`, `metadata_json {"status": "RUNNING"}`.
- **log(n)** = n events by one `add_all` and one flush: `created_at = T1 + timedelta(seconds=i)`, `description f"E{i}"`, for i from 0 to n-1. E(n-1) is the newest.
- A row with `machine_id M9.id` and `workspace_id W1.id` is the invalid row of the spec: built only to prove it is hidden.

**Named checks.**
- **re-read X** = `db.expire_all()`, then SELECT X by id; values are database values. "the returned row" = by `result.id`.
- **unchanged(X)** = after re-read, every column of X equals its value before the call. Snapshot after the last Given line.
- **nothing written** = the row count of `machine_activity_events` (all workspaces) equals its value before the call. A pending row is not stored, so it does not count.
- **ids(x)** = `[pair[0].id for pair in x]`, for a `list_events` result; the order is part of the check.
- **stored_meta(X)** = `tuple(db.execute(text("SELECT metadata::text, metadata IS NULL FROM machine_activity_events WHERE id = :i"), {"i": X.id}).one())`.
- `count:` lines count rows in all workspaces, with the filter stated.
- `raises: HTTPException`: plain `with pytest.raises(HTTPException) as exc:` around the call, no savepoint, unless the line says "in a savepoint".
- `raises: IntegrityError`, `DataError`, `StatementError` (`sqlalchemy.exc`), and any `raises:` line that says "in a savepoint": `with pytest.raises(<Type>) as exc:` then `with db.begin_nested():` then the call. `ForeignKeyViolation`, `NotNullViolation`, `StringDataRightTruncation`, `InvalidRowCountInLimitClause`, `InvalidRowCountInResultOffsetClause` = classes of `psycopg2.errors`.
- `raises: AttributeError`: plain `pytest.raises`.
- Further `raises:` lines are assertions on `exc.value` after the block, one per line.
- `session:` and `pending:` lines run on `db` or the row directly, before any re-read. `statement:` lines are checks on `sql_log`.

**sql_log.** The snapshots of `nothing written` and `unchanged` are taken before it starts. A list filled by a `before_cursor_execute` listener on `db.connection()`, started at that Given line, removed after the call. Each entry is the statement text; `len(sql_log)` counts reads and writes alike. `written(sql_log)` = the entries that start with `INSERT`, `UPDATE` or `DELETE` after stripping and upper-casing. `locked(sql_log)` = the entries holding `FOR UPDATE`, upper-cased.

**Rolled back.** `sp = db.begin_nested()` directly before the call, and a spy wrapping `db.commit` (still callable, records calls). The first checks run inside the savepoint; then `sp.rollback()` and the "after the savepoint rollback" checks.

**xfail cards.** Write the call and checks as shown. Strict unless the Expect line says `(non-strict)`: `pytest.mark.xfail(strict=True, reason="BUG-NNN")`, or `strict=False`. The assertion of a non-strict card is never weakened.

**Race simulations.** None in this module.

## `MachineActivityManager.format_field_value`

### MAC-FV-01 — None gives None
- **Rules:** `format_field_value` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. `value = None`.

**When**
- `result = M.format_field_value(value)`.

**Then**
1. returns: `result is None`.

### MAC-FV-02 — a str enum member gives its value
- **Rules:** `format_field_value` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. `value = MaintenanceTypeEnum.REPAIR`.

**When**
- `result = M.format_field_value(value)`.

**Then**
1. returns: `result == "REPAIR"`.

### MAC-FV-03 — a plain enum member gives the text of its value
- **Rules:** `format_field_value` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. `value = Kind.A`.

**When**
- `result = M.format_field_value(value)`.

**Then**
1. returns: `result == "1"`.

### MAC-FV-04 — any object with a value attribute gives the text of that attribute
- **Rules:** `format_field_value` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. `value = SimpleNamespace(value=7)`.

**When**
- `result = M.format_field_value(value)`.

**Then**
1. returns: `result == "7"`.

### MAC-FV-05 — the value attribute is checked before the date checks
- **Rules:** `format_field_value` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `class Stamp(date): value = 7`.
2. `value = Stamp(2026, 3, 5)`.

**When**
- `result = M.format_field_value(value)`.

**Then**
1. returns: `result == "7"`.

### MAC-FV-06 — a datetime drops its seconds
- **Rules:** `format_field_value` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. `value = datetime(2026, 3, 5, 7, 9, 59)`.

**When**
- `result = M.format_field_value(value)`.

**Then**
1. returns: `result == "2026-03-05 07:09"`.

### MAC-FV-07 — a datetime at midnight keeps its time
- **Rules:** `format_field_value` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `value = datetime(2026, 3, 5, 0, 0, 0)`.

**When**
- `result = M.format_field_value(value)`.

**Then**
1. returns: `result == "2026-03-05 00:00"`.

### MAC-FV-08 — a datetime with a time zone is not converted
- **Rules:** `format_field_value` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `value = datetime(2026, 3, 5, 7, 9, 59, tzinfo=timezone(timedelta(hours=6)))`.

**When**
- `result = M.format_field_value(value)`.

**Then**
1. returns: `result == "2026-03-05 07:09"`.

### MAC-FV-09 — a date gives its ISO form
- **Rules:** `format_field_value` R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. `value = date(2026, 3, 5)`.

**When**
- `result = M.format_field_value(value)`.

**Then**
1. returns: `result == "2026-03-05"`.

### MAC-FV-10 — a Decimal keeps its scale
- **Rules:** `format_field_value` R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. `value = Decimal("1.50")`.

**When**
- `result = M.format_field_value(value)`.

**Then**
1. returns: `result == "1.50"`.

### MAC-FV-11 — a whole Decimal gains no decimals
- **Rules:** `format_field_value` R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. `value = Decimal("100")`.

**When**
- `result = M.format_field_value(value)`.

**Then**
1. returns: `result == "100"`.

### MAC-FV-12 — an int gives its text
- **Rules:** `format_field_value` R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. `value = 5`.

**When**
- `result = M.format_field_value(value)`.

**Then**
1. returns: `result == "5"`.

### MAC-FV-13 — zero gives "0", not None
- **Rules:** `format_field_value` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `value = 0`.

**When**
- `result = M.format_field_value(value)`.

**Then**
1. returns: `result == "0"`.

### MAC-FV-14 — False gives "False", not None
- **Rules:** `format_field_value` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `value = False`.

**When**
- `result = M.format_field_value(value)`.

**Then**
1. returns: `result == "False"`.

### MAC-FV-15 — an empty string stays an empty string
- **Rules:** `format_field_value` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `value = ""`.

**When**
- `result = M.format_field_value(value)`.

**Then**
1. returns: `result == ""`.

### MAC-FV-16 — a padded string is not trimmed
- **Rules:** `format_field_value` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `value = " x "`.

**When**
- `result = M.format_field_value(value)`.

**Then**
1. returns: `result == " x "`.

### MAC-FV-17 — the method can be called on the class
- **Rules:** `format_field_value` R5, Facts (static)
- **Kind:** happy
- **Expect:** pass

**Given**
1. `value = 5`.

**When**
- `result = MachineActivityManager.format_field_value(value)`.

**Then**
1. returns: `result == "5"`.

## `MachineActivityManager.collect_field_changes`

### MAC-CF-01 — a changed tracked field gives one entry with four keys
- **Rules:** `collect_field_changes` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. `record = SimpleNamespace(a=1, b=2, c=3)`.

**When**
- `result = M.collect_field_changes(record, {"a": 5}, FIELDS)`.

**Then**
1. returns: `result == [{"field": "a", "label": "Alpha", "from_value": "1", "to_value": "5"}]`.

### MAC-CF-02 — both sides go through the value text
- **Rules:** `collect_field_changes` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. `record = SimpleNamespace(a=Kind.A, b=2, c=3)`.

**When**
- `result = M.collect_field_changes(record, {"a": date(2026, 3, 6)}, FIELDS)`.

**Then**
1. returns: `result == [{"field": "a", "label": "Alpha", "from_value": "1", "to_value": "2026-03-06"}]`.

### MAC-CF-03 — entries follow the order of fields, not of the update
- **Rules:** `collect_field_changes` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. `record = SimpleNamespace(a=1, b=5, c="x")`.

**When**
- `result = M.collect_field_changes(record, {"c": "y", "a": 2}, FIELDS)`.

**Then**
1. returns: `[entry["field"] for entry in result] == ["a", "c"]`.
2. returns: `result[0] == {"field": "a", "label": "Alpha", "from_value": "1", "to_value": "2"}`.
3. returns: `result[1] == {"field": "c", "label": "Gamma", "from_value": "x", "to_value": "y"}`.

### MAC-CF-04 — a tracked field absent from the update is not read on the record
- **Rules:** `collect_field_changes` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `record = SimpleNamespace(a=1)`: it has no attribute `b` or `c`.

**When**
- `result = M.collect_field_changes(record, {"a": 2}, FIELDS)`.

**Then**
1. returns: `result == [{"field": "a", "label": "Alpha", "from_value": "1", "to_value": "2"}]`.

### MAC-CF-05 — a key that is not tracked is ignored
- **Rules:** `collect_field_changes` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `record = SimpleNamespace(a=1, b=2, c=3)`: it has no attribute `updated_by`.

**When**
- `result = M.collect_field_changes(record, {"updated_by": 9, "a": 2}, FIELDS)`.

**Then**
1. returns: `result == [{"field": "a", "label": "Alpha", "from_value": "1", "to_value": "2"}]`.

### MAC-CF-06 — the same value gives no entry
- **Rules:** `collect_field_changes` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `record = SimpleNamespace(a=1, b=2, c=3)`.

**When**
- `result = M.collect_field_changes(record, {"a": 1}, FIELDS)`.

**Then**
1. returns: `result == []`.

### MAC-CF-07 — Decimals equal in value give no entry, whatever their scale
- **Rules:** `collect_field_changes` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `record = SimpleNamespace(a=Decimal("100.00"), b=2, c=3)`.

**When**
- `result = M.collect_field_changes(record, {"a": Decimal("100")}, FIELDS)`.

**Then**
1. returns: `result == []`.

### MAC-CF-08 — a str enum member and its string give no entry
- **Rules:** `collect_field_changes` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `record = SimpleNamespace(a=MaintenanceTypeEnum.REPAIR, b=2, c=3)`.

**When**
- `result = M.collect_field_changes(record, {"a": "REPAIR"}, FIELDS)`.

**Then**
1. returns: `result == []`.

### MAC-CF-09 — 1 and True are equal, so no entry
- **Rules:** `collect_field_changes` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `record = SimpleNamespace(a=1, b=2, c=3)`.

**When**
- `result = M.collect_field_changes(record, {"a": True}, FIELDS)`.

**Then**
1. returns: `result == []`.

### MAC-CF-10 — None and None give no entry
- **Rules:** `collect_field_changes` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `record = SimpleNamespace(a=None, b=2, c=3)`.

**When**
- `result = M.collect_field_changes(record, {"a": None}, FIELDS)`.

**Then**
1. returns: `result == []`.

### MAC-CF-11 — None to a value is a change
- **Rules:** `collect_field_changes` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `record = SimpleNamespace(a=None, b=2, c=3)`.

**When**
- `result = M.collect_field_changes(record, {"a": 0}, FIELDS)`.

**Then**
1. returns: `result == [{"field": "a", "label": "Alpha", "from_value": None, "to_value": "0"}]`.

### MAC-CF-12 — a value to None is a change
- **Rules:** `collect_field_changes` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `record = SimpleNamespace(a=0, b=2, c=3)`.

**When**
- `result = M.collect_field_changes(record, {"a": None}, FIELDS)`.

**Then**
1. returns: `result == [{"field": "a", "label": "Alpha", "from_value": "0", "to_value": None}]`.

### MAC-CF-13 — None to an empty string is a change
- **Rules:** `collect_field_changes` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `record = SimpleNamespace(a=None, b=2, c=3)`.

**When**
- `result = M.collect_field_changes(record, {"a": ""}, FIELDS)`.

**Then**
1. returns: `result == [{"field": "a", "label": "Alpha", "from_value": None, "to_value": ""}]`.

### MAC-CF-14 — the new value is compared as given, not as the column would store it
- **Rules:** `collect_field_changes` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `record = SimpleNamespace(a=Decimal("12.35"), b=2, c=3)`.

**When**
- `result = M.collect_field_changes(record, {"a": Decimal("12.354")}, FIELDS)`.

**Then**
1. returns: `result == [{"field": "a", "label": "Alpha", "from_value": "12.35", "to_value": "12.354"}]`.

### MAC-CF-15 — the new value is shown as given, its scale included
- **Rules:** `collect_field_changes` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `record = SimpleNamespace(a=Decimal("100.00"), b=2, c=3)`.

**When**
- `result = M.collect_field_changes(record, {"a": Decimal("100.5")}, FIELDS)`.

**Then**
1. returns: `result == [{"field": "a", "label": "Alpha", "from_value": "100.00", "to_value": "100.5"}]`.

### MAC-CF-16 — an empty update gives an empty list
- **Rules:** `collect_field_changes` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `record = SimpleNamespace(a=1, b=2, c=3)`.

**When**
- `result = M.collect_field_changes(record, {}, FIELDS)`.

**Then**
1. returns: `result == []`.

### MAC-CF-17 — empty fields give an empty list
- **Rules:** `collect_field_changes` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `record = SimpleNamespace(a=1, b=2, c=3)`.

**When**
- `result = M.collect_field_changes(record, {"a": 2}, {})`.

**Then**
1. returns: `result == []`.

### MAC-CF-18 — the record is not changed and nothing touches the database
- **Rules:** `collect_field_changes` R9
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. M1 (standing).
2. sql_log started.

**When**
- `result = M.collect_field_changes(M1, {"name": "Changed"}, MACHINE_LOG_FIELDS)`.

**Then**
1. returns: `result == [{"field": "name", "label": "Name", "from_value": "Press 1", "to_value": "Changed"}]`.
2. session: `M1.name == "Press 1"`.
3. session: `M1 not in db.dirty`.
4. statement: `sql_log == []`.

### MAC-CF-19 — a tracked field the record lacks raises AttributeError
- **Rules:** `collect_field_changes` Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. `record = SimpleNamespace(a=1)`: it has no attribute `b`.

**When**
- `M.collect_field_changes(record, {"b": 2}, FIELDS)`.

**Then**
1. raises: `AttributeError`.

### MAC-CF-20 — MACHINE_LOG_FIELDS lists the machine's tracked fields in order
- **Rules:** Facts (`MACHINE_LOG_FIELDS`)
- **Kind:** happy
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = list(MACHINE_LOG_FIELDS.items())`.

**Then**
1. returns: `result == [("name", "Name"), ("factory_id", "Factory"), ("factory_section_id", "Section"), ("model_number", "Model number"), ("manufacturer", "Manufacturer"), ("note", "Note")]`.

### MAC-CF-21 — MACHINE_ITEM_LOG_FIELDS lists the stock row's tracked fields in order
- **Rules:** Facts (`MACHINE_ITEM_LOG_FIELDS`)
- **Kind:** happy
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = list(MACHINE_ITEM_LOG_FIELDS.items())`.

**Then**
1. returns: `result == [("qty", "Quantity"), ("req_qty", "Required quantity"), ("defective_qty", "Defective quantity")]`.

## `MachineActivityManager.log_event`

### MAC-LE-01 — one row is stored with every value given
- **Rules:** `log_event` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. M1 (standing), no events.

**When**
- `result = M.log_event(db, machine_id=M1.id, workspace_id=W1.id, event_type="item_added", description="Added Bolt", performed_by=U2.id, metadata={"quantity": 3})`.

**Then**
1. returns: `isinstance(result, MachineActivityEvent)`.
2. returns: `result.id is not None`.
3. re-read the returned row: `workspace_id == W1.id`, `machine_id == M1.id`, `event_type == "item_added"`, `description == "Added Bolt"`, `performed_by == U2.id`.
4. re-read the returned row: `metadata_json == {"quantity": 3}`.
5. count: `machine_activity_events` with `machine_id == M1.id` has exactly 1 row.

### MAC-LE-02 — positional arguments work, in the order of the signature
- **Rules:** `log_event` R1, Facts (positional-or-keyword)
- **Kind:** happy
- **Expect:** pass

**Given**
1. M1 (standing), no events.

**When**
- `result = M.log_event(db, M1.id, W1.id, "item_added", "Added Bolt", U2.id, {"quantity": 3})`.

**Then**
1. re-read the returned row: `machine_id == M1.id`, `workspace_id == W1.id`, `event_type == "item_added"`, `description == "Added Bolt"`, `performed_by == U2.id`.
2. re-read the returned row: `metadata_json == {"quantity": 3}`.

### MAC-LE-03 — two identical calls give two rows
- **Rules:** `log_event` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `first = M.log_event(db, machine_id=M1.id, workspace_id=W1.id, event_type="updated", description="Same")`.

**When**
- `result = M.log_event(db, machine_id=M1.id, workspace_id=W1.id, event_type="updated", description="Same")`.

**Then**
1. returns: `result.id != first.id`.
2. count: `machine_activity_events` with `machine_id == M1.id` and `description == "Same"` has exactly 2 rows.

### MAC-LE-04 — the call is one INSERT: no other row and not the machine change, no lock
- **Rules:** `log_event` R1, Side effects, Overview
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = event, `created_at T1`.
2. B = event, `created_at T2`, but `machine_id M2.id`.
3. sql_log started.

**When**
- `result = M.log_event(db, machine_id=M1.id, workspace_id=W1.id, event_type="updated", description="Edited")`.

**Then**
1. returns: `result.id not in {A.id, B.id}`.
2. statement: `len(written(sql_log)) == 1`.
3. statement: `written(sql_log)[0].strip().upper().startswith("INSERT INTO MACHINE_ACTIVITY_EVENTS")`.
4. statement: `locked(sql_log) == []`.
5. unchanged: unchanged(A).
6. unchanged: unchanged(B).
7. unchanged: unchanged(M1).

### MAC-LE-05 — left out, metadata is stored as JSON null and performer as NULL
- **Rules:** `log_event` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1 (standing), no events.

**When**
- `result = M.log_event(db, machine_id=M1.id, workspace_id=W1.id, event_type="updated", description="Edited")`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `metadata_json is None`, `performed_by is None`.
3. re-read the returned row: `stored_meta(result) == ("null", False)`.

### MAC-LE-06 — metadata None passed explicitly is stored as JSON null
- **Rules:** `log_event` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1 (standing), no events.

**When**
- `result = M.log_event(db, machine_id=M1.id, workspace_id=W1.id, event_type="updated", description="Edited", metadata=None)`.

**Then**
1. re-read the returned row: `metadata_json is None`.
2. re-read the returned row: `stored_meta(result) == ("null", False)`.

### MAC-LE-07 — empty metadata is stored as an empty object, not as null
- **Rules:** `log_event` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1 (standing), no events.

**When**
- `result = M.log_event(db, machine_id=M1.id, workspace_id=W1.id, event_type="updated", description="Edited", metadata={})`.

**Then**
1. re-read the returned row: `metadata_json == {}`.
2. re-read the returned row: `stored_meta(result) == ("{}", False)`.

### MAC-LE-08 — nested metadata comes back equal, None inside it included
- **Rules:** `log_event` R3
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. M1 (standing), no events.

**When**
- `result = M.log_event(db, machine_id=M1.id, workspace_id=W1.id, event_type="updated", description="Edited", metadata={"a": [1, {"b": None}]})`.

**Then**
1. re-read the returned row: `metadata_json == {"a": [1, {"b": None}]}`.

### MAC-LE-09 — a float in metadata comes back equal
- **Rules:** `log_event` R3
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. M1 (standing), no events.

**When**
- `result = M.log_event(db, machine_id=M1.id, workspace_id=W1.id, event_type="item_added", description="Added", metadata={"quantity": 2.5})`.

**Then**
1. re-read the returned row: `metadata_json == {"quantity": 2.5}`.

### MAC-LE-10 — empty values inside metadata are kept
- **Rules:** `log_event` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1 (standing), no events.

**When**
- `result = M.log_event(db, machine_id=M1.id, workspace_id=W1.id, event_type="updated", description="Edited", metadata={"note": None, "changes": [], "flag": False, "qty": 0, "text": ""})`.

**Then**
1. re-read the returned row: `metadata_json == {"note": None, "changes": [], "flag": False, "qty": 0, "text": ""}`.

### MAC-LE-11 — an empty event type is stored
- **Rules:** `log_event` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1 (standing), no events.

**When**
- `result = M.log_event(db, machine_id=M1.id, workspace_id=W1.id, event_type="", description="Edited")`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `event_type == ""`.

### MAC-LE-12 — a type on no list is stored
- **Rules:** `log_event` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1 (standing), no events.

**When**
- `result = M.log_event(db, machine_id=M1.id, workspace_id=W1.id, event_type="anything_goes", description="Edited")`.

**Then**
1. re-read the returned row: `event_type == "anything_goes"`.

### MAC-LE-13 — an event type of exactly 50 characters is stored
- **Rules:** `log_event` R4, Inputs
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1 (standing), no events.

**When**
- `result = M.log_event(db, machine_id=M1.id, workspace_id=W1.id, event_type="x" * 50, description="Edited")`.

**Then**
1. re-read the returned row: `event_type == "x" * 50`.

### MAC-LE-14 — an event type of 51 characters is refused by the database, no row
- **Rules:** `log_event` Errors row 6, Inputs
- **Kind:** error
- **Expect:** pass

**Given**
1. M1 (standing), no events.

**When**
- `M.log_event(db, machine_id=M1.id, workspace_id=W1.id, event_type="x" * 51, description="Edited")`.

**Then**
1. raises: `DataError`.
2. raises: `isinstance(exc.value.orig, StringDataRightTruncation)`.
3. raises: `exc.value.orig.pgcode == "22001"`.
4. nothing written: nothing written.

### MAC-LE-15 — an empty description is stored
- **Rules:** `log_event` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1 (standing), no events.

**When**
- `result = M.log_event(db, machine_id=M1.id, workspace_id=W1.id, event_type="updated", description="")`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `description == ""`.

### MAC-LE-16 — event type and description are stored as given, not trimmed
- **Rules:** `log_event` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1 (standing), no events.

**When**
- `result = M.log_event(db, machine_id=M1.id, workspace_id=W1.id, event_type=" Item_Added ", description="  Added  ")`.

**Then**
1. re-read the returned row: `event_type == " Item_Added "`, `description == "  Added  "`.

### MAC-LE-17 — created_at is set on the row, with no time zone
- **Rules:** `log_event` R5
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. M1 (standing), no events.

**When**
- `result = M.log_event(db, machine_id=M1.id, workspace_id=W1.id, event_type="updated", description="Edited")`.

**Then**
1. returns: `result.created_at is not None`.
2. re-read the returned row: `created_at is not None`, `created_at.tzinfo is None`.

### MAC-LE-18 — another workspace's machine is refused like an unknown one, nothing written
- **Rules:** `log_event` R6 [BUG-1091], Errors row 1, HR-16
- **Kind:** bug
- **Expect:** xfail BUG-1091
- **Fails today on:** Then 1 (no error is raised: the row is stored under W1 on W2's machine)

**Given**
1. M9 (standing), no events.

**When**
- `M.log_event(db, machine_id=M9.id, workspace_id=W1.id, event_type="attachment_added", description="Attached a.png", performed_by=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Machine with ID {M9.id} not found"`.
4. session: `len(db.new) == 0`.
5. nothing written: nothing written.
6. count: `machine_activity_events` with `machine_id == M9.id` has exactly 0 rows.

### MAC-LE-19 — another workspace's soft-deleted machine is refused too
- **Rules:** `log_event` R6 [BUG-1091], R7, Errors row 1, HR-16
- **Kind:** bug
- **Expect:** xfail BUG-1091
- **Fails today on:** Then 1 (no error is raised: the row is stored under W1 on W2's machine)

**Given**
1. M8 = `machines` row: `workspace_id W2.id`, `factory_id F9.id`, `name "Far Old Press"`, `is_deleted True`, `is_active False`.

**When**
- `M.log_event(db, machine_id=M8.id, workspace_id=W1.id, event_type="deactivated", description="Removed")`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Machine with ID {M8.id} not found"`.
4. session: `len(db.new) == 0`.
5. nothing written: nothing written.

### MAC-LE-20 — an unknown machine gets the same 404
- **Rules:** `log_event` R6 [BUG-1091], Errors rows 1, 2
- **Kind:** bug
- **Expect:** xfail BUG-1091
- **Fails today on:** Then 1 (the call raises IntegrityError: `machine_activity_events_machine_id_fkey`, no machine check runs)

**Given**
1. No machine has id MISSING.

**When**
- `M.log_event(db, machine_id=MISSING, workspace_id=W1.id, event_type="updated", description="Edited")`.

**Then**
1. raises: `HTTPException`, in a savepoint.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Machine with ID 999999999 not found"`.
4. nothing written: nothing written.

### MAC-LE-21 — machine id 0 gets the same 404
- **Rules:** `log_event` R6 [BUG-1091], Errors rows 1, 2
- **Kind:** bug
- **Expect:** xfail BUG-1091
- **Fails today on:** Then 1 (the call raises IntegrityError: `machine_activity_events_machine_id_fkey`, no machine check runs)

**Given**
1. No machine has id 0.

**When**
- `M.log_event(db, machine_id=0, workspace_id=W1.id, event_type="updated", description="Edited")`.

**Then**
1. raises: `HTTPException`, in a savepoint.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Machine with ID 0 not found"`.
4. nothing written: nothing written.

### MAC-LE-22 — an unknown workspace gets the same 404, naming the machine
- **Rules:** `log_event` R6 [BUG-1091], Errors rows 1, 3
- **Kind:** bug
- **Expect:** xfail BUG-1091
- **Fails today on:** Then 1 (the call raises IntegrityError: `machine_activity_events_workspace_id_fkey`, no machine check runs)

**Given**
1. M1 (standing). No workspace has id MISSING.

**When**
- `M.log_event(db, machine_id=M1.id, workspace_id=MISSING, event_type="updated", description="Edited")`.

**Then**
1. raises: `HTTPException`, in a savepoint.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Machine with ID {M1.id} not found"`.
4. nothing written: nothing written.

### MAC-LE-23 — a soft-deleted machine is accepted
- **Rules:** `log_event` R7
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. MD (standing), no events.

**When**
- `result = M.log_event(db, machine_id=MD.id, workspace_id=W1.id, event_type="deactivated", description="Removed", performed_by=U1.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `machine_id == MD.id`, `workspace_id == W1.id`, `event_type == "deactivated"`.
3. count: `machine_activity_events` with `machine_id == MD.id` has exactly 1 row.

### MAC-LE-24 — a machine in a soft-deleted factory is accepted
- **Rules:** `log_event` R7
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. MF (standing), no events.

**When**
- `result = M.log_event(db, machine_id=MF.id, workspace_id=W1.id, event_type="updated", description="Edited")`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `machine_id == MF.id`, `workspace_id == W1.id`.
3. count: `machine_activity_events` with `machine_id == MF.id` has exactly 1 row.

### MAC-LE-25 — an unknown performer is refused by the database, no row
- **Rules:** `log_event` R8, Errors row 4
- **Kind:** error
- **Expect:** pass

**Given**
1. M1 (standing), no events. No profile has id MISSING.

**When**
- `M.log_event(db, machine_id=M1.id, workspace_id=W1.id, event_type="updated", description="Edited", performed_by=MISSING)`.

**Then**
1. raises: `IntegrityError`.
2. raises: `isinstance(exc.value.orig, ForeignKeyViolation)`.
3. raises: `exc.value.orig.pgcode == "23503"`.
4. raises: `"machine_activity_events_performed_by_fkey" in str(exc.value.orig)` (contains).
5. nothing written: nothing written.

### MAC-LE-26 — performer 0 is refused, not read as no performer
- **Rules:** `log_event` R8, Errors row 4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1 (standing), no events. No profile has id 0.

**When**
- `M.log_event(db, machine_id=M1.id, workspace_id=W1.id, event_type="updated", description="Edited", performed_by=0)`.

**Then**
1. raises: `IntegrityError`.
2. raises: `isinstance(exc.value.orig, ForeignKeyViolation)`.
3. raises: `exc.value.orig.pgcode == "23503"`.
4. raises: `"machine_activity_events_performed_by_fkey" in str(exc.value.orig)` (contains).
5. nothing written: nothing written.

### MAC-LE-27 — a performer is not checked against the workspace
- **Rules:** `log_event` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `outsider = make_profile(db)`: a third profile, a member of no workspace.

**When**
- `result = M.log_event(db, machine_id=M1.id, workspace_id=W1.id, event_type="updated", description="Edited", performed_by=outsider.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `performed_by == outsider.id`.

### MAC-LE-28 — a Decimal in metadata fails at the flush, no row
- **Rules:** `log_event` R9, Errors row 7
- **Kind:** error
- **Expect:** pass

**Given**
1. M1 (standing), no events.

**When**
- `M.log_event(db, machine_id=M1.id, workspace_id=W1.id, event_type="updated", description="Edited", metadata={"cost": Decimal("1.50")})`.

**Then**
1. raises: `StatementError`.
2. raises: `isinstance(exc.value.orig, TypeError)`.
3. raises: `getattr(exc.value.orig, "pgcode", None) is None`.
4. nothing written: nothing written.

### MAC-LE-29 — a datetime in metadata fails at the flush, no row
- **Rules:** `log_event` R9, Errors row 7
- **Kind:** error
- **Expect:** pass

**Given**
1. M1 (standing), no events.

**When**
- `M.log_event(db, machine_id=M1.id, workspace_id=W1.id, event_type="updated", description="Edited", metadata={"at": datetime(2026, 3, 5, 10, 0, 0)})`.

**Then**
1. raises: `StatementError`.
2. raises: `isinstance(exc.value.orig, TypeError)`.
3. raises: `getattr(exc.value.orig, "pgcode", None) is None`.
4. nothing written: nothing written.

### MAC-LE-30 — event type None is refused by the database, no row
- **Rules:** `log_event` Errors row 5
- **Kind:** error
- **Expect:** pass

**Given**
1. M1 (standing), no events.

**When**
- `M.log_event(db, machine_id=M1.id, workspace_id=W1.id, event_type=None, description="Edited")`.

**Then**
1. raises: `IntegrityError`.
2. raises: `isinstance(exc.value.orig, NotNullViolation)`.
3. raises: `exc.value.orig.pgcode == "23502"`.
4. nothing written: nothing written.

### MAC-LE-31 — description None is refused by the database, no row
- **Rules:** `log_event` Errors row 5
- **Kind:** error
- **Expect:** pass

**Given**
1. M1 (standing), no events.

**When**
- `M.log_event(db, machine_id=M1.id, workspace_id=W1.id, event_type="updated", description=None)`.

**Then**
1. raises: `IntegrityError`.
2. raises: `isinstance(exc.value.orig, NotNullViolation)`.
3. raises: `exc.value.orig.pgcode == "23502"`.
4. nothing written: nothing written.

### MAC-LE-32 — flushed, not committed: a savepoint's rollback removes the row
- **Rules:** `log_event` R10, Returns, Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. M1 (standing), no events.
2. Rolled back: `sp` opened and the commit spy set, directly before the call.

**When**
- `result = M.log_event(db, machine_id=M1.id, workspace_id=W1.id, event_type="updated", description="Edited")`.

**Then**
1. returns: `result.id is not None`.
2. count: `machine_activity_events` with `machine_id == M1.id` has exactly 1 row, inside the savepoint.
3. mock called: the commit spy was not called.
4. count: after the savepoint rollback, `machine_activity_events` with `machine_id == M1.id` has exactly 0 rows.

### MAC-LE-33 — an inactive, live machine is accepted
- **Rules:** `log_event` R1, R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MA (standing), no events.

**When**
- `result = M.log_event(db, machine_id=MA.id, workspace_id=W1.id, event_type="updated", description="Edited")`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `machine_id == MA.id`, `workspace_id == W1.id`, `event_type == "updated"`.
3. count: `machine_activity_events` with `machine_id == MA.id` has exactly 1 row.

## `MachineActivityManager.list_events`

### MAC-LI-01 — the machine's events come back newest first, as 2-tuples
- **Rules:** `list_events` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = event, `created_at T2`.
2. B = status row, `created_at T3`.
3. C = event, `created_at T1`, but `event_type "created"`.

**When**
- `result = M.list_events(db, machine_id=M1.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `ids(result) == [B.id, A.id, C.id]`.
3. returns: `isinstance(result[0], tuple)`, `len(result[0]) == 2`.
4. returns: `isinstance(result[0][0], MachineActivityEvent)`.

### MAC-LI-02 — on a created_at tie the higher id comes first, physically last
- **Rules:** `list_events` R1 (DAO `get_by_machine` R5)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = event, `created_at T2`.
2. B = event, `created_at T2`.

**When**
- `result = M.list_events(db, machine_id=M1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [B.id, A.id]`.

### MAC-LI-03 — on a created_at tie the higher id comes first, physically first
- **Rules:** `list_events` R1 (DAO `get_by_machine` R5)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = event, `created_at T2`.
2. B = event, `created_at T2`.
3. `A.description = "Edited"`, then `db.flush()`.
4. `db.expire_all()`.

**When**
- `result = M.list_events(db, machine_id=M1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [B.id, A.id]`.

### MAC-LI-04 — every argument reaches the read by position
- **Rules:** `list_events` R1, Facts (positional-or-keyword)
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = event, `created_at T1`.
2. B = event, `created_at T2`.
3. C = event, `created_at T2`, but `event_type "updated"`.
4. D = event, `created_at T3`.
5. E = event, `created_at datetime(2026, 3, 6, 11, 0, 0)`.
6. Z = event, `created_at datetime(2026, 3, 7, 10, 0, 0)`.

**When**
- `result = M.list_events(db, M1.id, W1.id, 1, 2, date(2026, 3, 5), date(2026, 3, 6), "item_added")`.

**Then**
1. returns: `ids(result) == [D.id, B.id]`.

### MAC-LI-05 — skip passes over the newest rows
- **Rules:** `list_events` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = event, `created_at T1`.
2. B = event, `created_at T2`.
3. C = event, `created_at T3`.

**When**
- `result = M.list_events(db, machine_id=M1.id, workspace_id=W1.id, skip=1)`.

**Then**
1. returns: `ids(result) == [B.id, A.id]`.

### MAC-LI-06 — limit 1 returns the newest row alone
- **Rules:** `list_events` R1, R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = event, `created_at T1`.
2. B = event, `created_at T2`.

**When**
- `result = M.list_events(db, machine_id=M1.id, workspace_id=W1.id, limit=1)`.

**Then**
1. returns: `ids(result) == [B.id]`.

### MAC-LI-07 — from_date keeps the first moment of the day
- **Rules:** `list_events` R1 (DAO `get_by_machine` R9)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = event, `created_at datetime(2026, 3, 5, 0, 0, 0)`.

**When**
- `result = M.list_events(db, machine_id=M1.id, workspace_id=W1.id, from_date=date(2026, 3, 5))`.

**Then**
1. returns: `ids(result) == [A.id]`.

### MAC-LI-08 — from_date leaves out the last moment of the day before
- **Rules:** `list_events` R1 (DAO `get_by_machine` R9)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = event, `created_at datetime(2026, 3, 4, 23, 59, 59, 999999)`.

**When**
- `result = M.list_events(db, machine_id=M1.id, workspace_id=W1.id, from_date=date(2026, 3, 5))`.

**Then**
1. returns: `result == []`.

### MAC-LI-09 — to_date keeps the last moment of the day
- **Rules:** `list_events` R1 (DAO `get_by_machine` R10)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = event, `created_at datetime(2026, 3, 5, 23, 59, 59, 999999)`.

**When**
- `result = M.list_events(db, machine_id=M1.id, workspace_id=W1.id, to_date=date(2026, 3, 5))`.

**Then**
1. returns: `ids(result) == [A.id]`.

### MAC-LI-10 — to_date leaves out the first moment of the next day
- **Rules:** `list_events` R1 (DAO `get_by_machine` R10)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = event, `created_at datetime(2026, 3, 6, 0, 0, 0)`.

**When**
- `result = M.list_events(db, machine_id=M1.id, workspace_id=W1.id, to_date=date(2026, 3, 5))`.

**Then**
1. returns: `result == []`.

### MAC-LI-11 — event_type keeps its own type and leaves out another
- **Rules:** `list_events` R1 (DAO `get_by_machine` R13)
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = event, `created_at T1`.
2. B = status row, `created_at T2`.

**When**
- `result = M.list_events(db, machine_id=M1.id, workspace_id=W1.id, event_type="item_added")`.

**Then**
1. returns: `ids(result) == [A.id]`.

### MAC-LI-12 — event_type "updated" does not match status_updated
- **Rules:** `list_events` R1 (DAO `get_by_machine` R13)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = event, `created_at T1`, but `event_type "updated"`.
2. B = status row, `created_at T2`.

**When**
- `result = M.list_events(db, machine_id=M1.id, workspace_id=W1.id, event_type="updated")`.

**Then**
1. returns: `ids(result) == [A.id]`.

### MAC-LI-13 — event_type "status" does not match status_updated
- **Rules:** `list_events` R1 (DAO `get_by_machine` R13)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = status row, `created_at T1`.

**When**
- `result = M.list_events(db, machine_id=M1.id, workspace_id=W1.id, event_type="status")`.

**Then**
1. returns: `result == []`.

### MAC-LI-14 — event_type "status_updated" matches neither a shorter nor a longer type
- **Rules:** `list_events` R1 (DAO `get_by_machine` R13)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = status row, `created_at T1`.
2. B = event, `created_at T2`, but `event_type "updated"`.
3. C = event, `created_at T3`, but `event_type "status_updated_manual"`.

**When**
- `result = M.list_events(db, machine_id=M1.id, workspace_id=W1.id, event_type="status_updated")`.

**Then**
1. returns: `ids(result) == [A.id]`.

### MAC-LI-15 — event_type "" applies no filter
- **Rules:** `list_events` R1 (DAO `get_by_machine` R14)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = event, `created_at T1`.
2. B = status row, `created_at T2`.

**When**
- `result = M.list_events(db, machine_id=M1.id, workspace_id=W1.id, event_type="")`.

**Then**
1. returns: `ids(result) == [B.id, A.id]`.

### MAC-LI-16 — the type filter runs before paging: a hidden row ahead of the skipped row takes no place
- **Rules:** `list_events` R1 (DAO `get_by_machine` R15), HR-5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. R = status row, `created_at T1`.
2. S = status row, `created_at T2`.
3. H = event, `created_at T3`.

**When**
- `result = M.list_events(db, machine_id=M1.id, workspace_id=W1.id, skip=1, limit=1, event_type="status_updated")`.

**Then**
1. returns: `ids(result) == [R.id]`.

### MAC-LI-17 — the date filter runs before paging: a hidden row ahead of the skipped row takes no place
- **Rules:** `list_events` R1 (DAO `get_by_machine` R15), HR-5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. R = event, `created_at T1`.
2. S = event, `created_at T2`.
3. H = event, `created_at T3`.

**When**
- `result = M.list_events(db, machine_id=M1.id, workspace_id=W1.id, skip=1, limit=1, to_date=date(2026, 3, 5))`.

**Then**
1. returns: `ids(result) == [R.id]`.

### MAC-LI-18 — another machine's row ahead of the skipped row takes no place
- **Rules:** `list_events` R1 (DAO `get_by_machine` R1), HR-5
- **Kind:** isolation
- **Expect:** pass

**Given**
1. R = event, `created_at T1`.
2. S = event, `created_at T2`.
3. H = event, `created_at T3`, but `machine_id M2.id`.

**When**
- `result = M.list_events(db, machine_id=M1.id, workspace_id=W1.id, skip=1, limit=1)`.

**Then**
1. returns: `ids(result) == [R.id]`.

### MAC-LI-19 — all filters combine
- **Rules:** `list_events` R1 (DAO `get_by_machine` R15)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = status row, `created_at T1`.
2. B = event, `created_at T2`.
3. C = status row, `created_at T2`.
4. D = status row, `created_at T3`.

**When**
- `result = M.list_events(db, machine_id=M1.id, workspace_id=W1.id, from_date=date(2026, 3, 5), to_date=date(2026, 3, 5), event_type="status_updated")`.

**Then**
1. returns: `ids(result) == [C.id]`.

### MAC-LI-20 — another workspace's machine gets 404, and no event is read
- **Rules:** `list_events` R2, Errors row 1, HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = status row, `created_at T1`, but `workspace_id W2.id`, `machine_id M9.id`.
2. sql_log started.

**When**
- `M.list_events(db, machine_id=M9.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Machine with ID {M9.id} not found"`.
4. statement: `len(sql_log) == 1`.
5. nothing written: nothing written.

### MAC-LI-21 — an unknown machine gets the same 404
- **Rules:** `list_events` R2, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. No machine has id MISSING.

**When**
- `M.list_events(db, machine_id=MISSING, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Machine with ID 999999999 not found"`.
4. nothing written: nothing written.

### MAC-LI-22 — machine id 0 gets the same 404
- **Rules:** `list_events` R2, Errors row 1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No machine has id 0.

**When**
- `M.list_events(db, machine_id=0, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Machine with ID 0 not found"`.
4. nothing written: nothing written.

### MAC-LI-23 — a negative machine id gets the same 404
- **Rules:** `list_events` R2, Errors row 1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No machine has id -1.

**When**
- `M.list_events(db, machine_id=-1, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Machine with ID -1 not found"`.
4. nothing written: nothing written.

### MAC-LI-24 — a W1 row on W2's machine does not reach W1: it gets the 404
- **Rules:** `list_events` R3, HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = event, `created_at T1`, but `machine_id M9.id`.

**When**
- `M.list_events(db, machine_id=M9.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Machine with ID {M9.id} not found"`.
4. unchanged: unchanged(A).

### MAC-LI-25 — W2's list leaves out the W1 row on its machine
- **Rules:** `list_events` R3, HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = event, `created_at T1`, but `workspace_id W2.id`, `machine_id M9.id`.
2. B = event, `created_at T2`, but `machine_id M9.id`.

**When**
- `result = M.list_events(db, machine_id=M9.id, workspace_id=W2.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### MAC-LI-26 — the W1 row ahead of the skipped row takes no place in W2's page
- **Rules:** `list_events` R3, R1, HR-5
- **Kind:** isolation
- **Expect:** pass

**Given**
1. R = event, `created_at T1`, but `workspace_id W2.id`, `machine_id M9.id`.
2. S = event, `created_at T2`, but `workspace_id W2.id`, `machine_id M9.id`.
3. H = event, `created_at T3`, but `machine_id M9.id`.

**When**
- `result = M.list_events(db, machine_id=M9.id, workspace_id=W2.id, skip=1, limit=1)`.

**Then**
1. returns: `ids(result) == [R.id]`.

### MAC-LI-27 — a soft-deleted machine returns every event
- **Rules:** `list_events` R4
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = event, `created_at T1`, but `machine_id MD.id`.
2. B = event, `created_at T2`, but `machine_id MD.id`, `event_type "deactivated"`.

**When**
- `result = M.list_events(db, machine_id=MD.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [B.id, A.id]`.

### MAC-LI-28 — a machine in a soft-deleted factory returns every event
- **Rules:** `list_events` R4
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = event, `created_at T1`, but `machine_id MF.id`.
2. B = event, `created_at T2`, but `machine_id MF.id`.

**When**
- `result = M.list_events(db, machine_id=MF.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [B.id, A.id]`.

### MAC-LI-29 — an inactive machine returns every event
- **Rules:** `list_events` R4
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = event, `created_at T1`, but `machine_id MA.id`.
2. B = event, `created_at T2`, but `machine_id MA.id`.

**When**
- `result = M.list_events(db, machine_id=MA.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [B.id, A.id]`.

### MAC-LI-30 — the first element holds the stored metadata whole
- **Rules:** `list_events` R6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = event, `created_at T1`, but `description "Attached a.png"`, `metadata_json {"note": "belt", "old_quantity": 3, "new_quantity": 5, "attachment_id": 7, "file_name": "a.png", "mime_type": "image/png", "file_size": 120}`.

**When**
- `result = M.list_events(db, machine_id=M1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result[0][0].id == A.id`.
2. returns: `result[0][0].description == "Attached a.png"`.
3. returns: `result[0][0].metadata_json == {"note": "belt", "old_quantity": 3, "new_quantity": 5, "attachment_id": 7, "file_name": "a.png", "mime_type": "image/png", "file_size": 120}`.

### MAC-LI-31 — a row with empty metadata reads back as None
- **Rules:** `list_events` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = event, `created_at T1`, but `metadata_json None`.

**When**
- `result = M.list_events(db, machine_id=M1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. returns: `result[0][0].metadata_json is None`.

### MAC-LI-32 — a machine with no events gives an empty list
- **Rules:** `list_events` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = event, `created_at T1`, but `machine_id M2.id`.

**When**
- `result = M.list_events(db, machine_id=M1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### MAC-LI-33 — each entry holds its own performer, or None
- **Rules:** `list_events` R7
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = event, `created_at T1`, but `performed_by U2.id`.
2. B = event, `created_at T2`.
3. C = event, `created_at T3`, but `performed_by U1.id`.

**When**
- `result = M.list_events(db, machine_id=M1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [C.id, B.id, A.id]`.
2. returns: `result[0][1].id == U1.id`.
3. returns: `result[1][1] is None`.
4. returns: `result[2][1].id == U2.id`.

### MAC-LI-34 — two entries by one person hold the same instance
- **Rules:** `list_events` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = event, `created_at T1`, but `performed_by U1.id`.
2. B = event, `created_at T2`, but `performed_by U1.id`.

**When**
- `result = M.list_events(db, machine_id=M1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result[0][1].id == U1.id`.
2. returns: `result[0][1] is result[1][1]`.

### MAC-LI-35 — with the defaults 100 of 101 entries come back, the newest
- **Rules:** `list_events` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. log(101).

**When**
- `result = M.list_events(db, machine_id=M1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.
2. returns: `result[0][0].description == "E100"`.
3. returns: `result[99][0].description == "E1"`.

### MAC-LI-36 — limit 1000 gives 1000 of 1000
- **Rules:** `list_events` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. log(1000).

**When**
- `result = M.list_events(db, machine_id=M1.id, workspace_id=W1.id, limit=1000)`.

**Then**
1. returns: `len(result) == 1000`.
2. returns: `result[0][0].description == "E999"`.
3. returns: `result[999][0].description == "E0"`.

### MAC-LI-37 — limit 0 gives an empty list
- **Rules:** `list_events` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = event, `created_at T1`.

**When**
- `result = M.list_events(db, machine_id=M1.id, workspace_id=W1.id, limit=0)`.

**Then**
1. returns: `result == []`.

### MAC-LI-38 — skip at the number of rows gives an empty list
- **Rules:** `list_events` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = event, `created_at T1`.
2. B = event, `created_at T2`.

**When**
- `result = M.list_events(db, machine_id=M1.id, workspace_id=W1.id, skip=2)`.

**Then**
1. returns: `result == []`.

### MAC-LI-39 — skip one below the number of rows gives the oldest row
- **Rules:** `list_events` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = event, `created_at T1`.
2. B = event, `created_at T2`.

**When**
- `result = M.list_events(db, machine_id=M1.id, workspace_id=W1.id, skip=1)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### MAC-LI-40 — a negative limit raises DataError
- **Rules:** `list_events` R8, Errors row 2
- **Kind:** error
- **Expect:** pass

**Given**
1. A = event, `created_at T1`.

**When**
- `M.list_events(db, machine_id=M1.id, workspace_id=W1.id, limit=-1)`.

**Then**
1. raises: `DataError`.
2. raises: `isinstance(exc.value.orig, InvalidRowCountInLimitClause)`.
3. raises: `exc.value.orig.pgcode == "2201W"`.
4. nothing written: nothing written.

### MAC-LI-41 — a negative skip raises DataError
- **Rules:** `list_events` R8, Errors row 2
- **Kind:** error
- **Expect:** pass

**Given**
1. A = event, `created_at T1`.

**When**
- `M.list_events(db, machine_id=M1.id, workspace_id=W1.id, skip=-1)`.

**Then**
1. raises: `DataError`.
2. raises: `isinstance(exc.value.orig, InvalidRowCountInResultOffsetClause)`.
3. raises: `exc.value.orig.pgcode == "2201X"`.
4. nothing written: nothing written.

### MAC-LI-42 — one entry with a performer stays within three reads
- **Rules:** `list_events` R9, R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = event, `created_at T1`, but `performed_by U1.id`.
2. sql_log started.

**When**
- `result = M.list_events(db, machine_id=M1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. returns: `result[0][1].id == U1.id`.
3. statement: `len(sql_log) <= 3`.

### MAC-LI-43 — entries with no performer stay within three reads
- **Rules:** `list_events` R9, R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = event, `created_at T1`.
2. B = event, `created_at T2`.
3. C = event, `created_at T3`.
4. sql_log started.

**When**
- `result = M.list_events(db, machine_id=M1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [C.id, B.id, A.id]`.
2. statement: `len(sql_log) <= 3`.

### MAC-LI-44 — five entries by one person make at most three reads
- **Rules:** `list_events` R9 [BUG-1141], R7
- **Kind:** bug
- **Expect:** xfail BUG-1141
- **Fails today on:** Then 3 (one read per entry: 7 reads)

**Given**
1. A = event, `created_at datetime(2026, 3, 1, 10, 0, 0)`, but `performed_by U1.id`.
2. B = event, `created_at datetime(2026, 3, 2, 10, 0, 0)`, but `performed_by U1.id`.
3. C = event, `created_at datetime(2026, 3, 3, 10, 0, 0)`, but `performed_by U1.id`.
4. D = event, `created_at datetime(2026, 3, 4, 10, 0, 0)`, but `performed_by U1.id`.
5. E = event, `created_at datetime(2026, 3, 5, 10, 0, 0)`, but `performed_by U1.id`.
6. sql_log started.

**When**
- `result = M.list_events(db, machine_id=M1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [E.id, D.id, C.id, B.id, A.id]`.
2. returns: `[pair[1].id for pair in result] == [U1.id] * 5`.
3. statement: `len(sql_log) <= 3`.

### MAC-LI-45 — entries by two people and by nobody make at most three reads
- **Rules:** `list_events` R9 [BUG-1141], R7
- **Kind:** bug
- **Expect:** xfail BUG-1141
- **Fails today on:** Then 3 (one read per entry with a performer: 6 reads)

**Given**
1. A = event, `created_at datetime(2026, 3, 1, 10, 0, 0)`, but `performed_by U1.id`.
2. B = event, `created_at datetime(2026, 3, 2, 10, 0, 0)`, but `performed_by U2.id`.
3. C = event, `created_at datetime(2026, 3, 3, 10, 0, 0)`.
4. D = event, `created_at datetime(2026, 3, 4, 10, 0, 0)`, but `performed_by U1.id`.
5. E = event, `created_at datetime(2026, 3, 5, 10, 0, 0)`, but `performed_by U2.id`.
6. sql_log started.

**When**
- `result = M.list_events(db, machine_id=M1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [E.id, D.id, C.id, B.id, A.id]`.
2. returns: `[pair[1].id if pair[1] else None for pair in result] == [U2.id, U1.id, None, U2.id, U1.id]`.
3. statement: `len(sql_log) <= 3`.

### MAC-LI-46 — five entries by two people and by nobody come back with the right performers
- **Rules:** `list_events` R7, R9
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = event, `created_at datetime(2026, 3, 1, 10, 0, 0)`, but `performed_by U1.id`.
2. B = event, `created_at datetime(2026, 3, 2, 10, 0, 0)`, but `performed_by U2.id`.
3. C = event, `created_at datetime(2026, 3, 3, 10, 0, 0)`.
4. D = event, `created_at datetime(2026, 3, 4, 10, 0, 0)`, but `performed_by U1.id`.
5. E = event, `created_at datetime(2026, 3, 5, 10, 0, 0)`, but `performed_by U2.id`.

**When**
- `result = M.list_events(db, machine_id=M1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [E.id, D.id, C.id, B.id, A.id]`.
2. returns: `[pair[1].id if pair[1] else None for pair in result] == [U2.id, U1.id, None, U2.id, U1.id]`.
3. returns: `result[1][1] is result[4][1]`.

### MAC-LI-47 — writes nothing: a newer pending row stays pending and is not returned
- **Rules:** `list_events` R10, Side effects, Overview
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = event, `created_at T1`.
2. `P = MachineActivityEvent(workspace_id=W1.id, machine_id=M1.id, event_type="item_added", description="Pending", created_at=T2)`.
3. `db.add(P)` (not flushed).
4. sql_log started.

**When**
- `result = M.list_events(db, machine_id=M1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. pending: `P in db.new`.
3. pending: `P.id is None`.
4. nothing written: nothing written.
5. unchanged: unchanged(A).
6. statement: `written(sql_log) == []`.
7. statement: `locked(sql_log) == []`.

## `MachineActivityManager.get_latest_status`

### MAC-GS-01 — the newest status row is returned
- **Rules:** `get_latest_status` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = status row, `created_at T2`.
2. B = status row, `created_at T3`, but `metadata_json {"status": "IDLE"}`.
3. C = status row, `created_at T1`.

**When**
- `result = M.get_latest_status(db, machine_id=M1.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, MachineActivityEvent)`.
2. returns: `result.id == B.id`.
3. returns: `result.metadata_json == {"status": "IDLE"}`.

### MAC-GS-02 — positional arguments work, as the callers call it
- **Rules:** `get_latest_status` R1, Visibility
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = status row, `created_at T1`.

**When**
- `result = M.get_latest_status(db, M1.id, W1.id)`.

**Then**
1. returns: `result.id == A.id`.

### MAC-GS-03 — a newer row of another type is ignored, even with a status key
- **Rules:** `get_latest_status` R1 (DAO R3)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = status row, `created_at T1`.
2. B = event, `created_at T2`, but `event_type "maintenance_logged"`, `metadata_json {"status": "MAINTENANCE"}`.

**When**
- `result = M.get_latest_status(db, machine_id=M1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.

### MAC-GS-04 — a newer row of type "updated" is not a status row
- **Rules:** `get_latest_status` R1 (DAO R3)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = status row, `created_at T1`.
2. B = event, `created_at T2`, but `event_type "updated"`, `metadata_json {"status": "IDLE"}`.

**When**
- `result = M.get_latest_status(db, machine_id=M1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.

### MAC-GS-05 — a newer row of type "status_updated_manual" is not a status row
- **Rules:** `get_latest_status` R1 (DAO R3)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = status row, `created_at T1`.
2. B = event, `created_at T2`, but `event_type "status_updated_manual"`, `metadata_json {"status": "IDLE"}`.

**When**
- `result = M.get_latest_status(db, machine_id=M1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.

### MAC-GS-06 — a newer status row of another machine is not returned
- **Rules:** `get_latest_status` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = status row, `created_at T1`.
2. B = status row, `created_at T2`, but `machine_id M2.id`.

**When**
- `result = M.get_latest_status(db, machine_id=M1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.

### MAC-GS-07 — on a created_at tie the highest id is returned, physically last
- **Rules:** `get_latest_status` R1 (DAO R2)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = status row, `created_at T2`.
2. B = status row, `created_at T2`.

**When**
- `result = M.get_latest_status(db, machine_id=M1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == B.id`.

### MAC-GS-08 — on a created_at tie the highest id is returned, physically first
- **Rules:** `get_latest_status` R1 (DAO R2)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = status row, `created_at T2`.
2. B = status row, `created_at T2`.
3. `A.description = "Edited"`, then `db.flush()`.
4. `db.expire_all()`.

**When**
- `result = M.get_latest_status(db, machine_id=M1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == B.id`.

### MAC-GS-09 — a newest status row with no metadata is returned; older rows are not consulted
- **Rules:** `get_latest_status` R1 (DAO R7)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = status row, `created_at T1`.
2. B = status row, `created_at T2`, but `metadata_json None`.

**When**
- `result = M.get_latest_status(db, machine_id=M1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == B.id`.
2. returns: `result.metadata_json is None`.

### MAC-GS-10 — a machine of the workspace with only other rows gives None
- **Rules:** `get_latest_status` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = event, `created_at T1`.

**When**
- `result = M.get_latest_status(db, machine_id=M1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### MAC-GS-11 — a machine of the workspace with no rows gives None
- **Rules:** `get_latest_status` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1 (standing), no events.

**When**
- `result = M.get_latest_status(db, machine_id=M1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### MAC-GS-12 — an unknown machine gets 404
- **Rules:** `get_latest_status` R3 [BUG-1140], Errors row 1
- **Kind:** bug
- **Expect:** xfail BUG-1140
- **Fails today on:** Then 1 (no error is raised: `None` comes back)

**Given**
1. No machine has id MISSING.

**When**
- `M.get_latest_status(db, machine_id=MISSING, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Machine with ID 999999999 not found"`.
4. nothing written: nothing written.

### MAC-GS-13 — machine id 0 gets the same 404
- **Rules:** `get_latest_status` R3 [BUG-1140], Errors row 1
- **Kind:** bug
- **Expect:** xfail BUG-1140
- **Fails today on:** Then 1 (no error is raised: `None` comes back)

**Given**
1. No machine has id 0.

**When**
- `M.get_latest_status(db, machine_id=0, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Machine with ID 0 not found"`.
4. nothing written: nothing written.

### MAC-GS-14 — another workspace's machine gets the same 404
- **Rules:** `get_latest_status` R3 [BUG-1140], Errors row 1, HR-16
- **Kind:** bug
- **Expect:** xfail BUG-1140
- **Fails today on:** Then 1 (no error is raised: `None` comes back)

**Given**
1. A = status row, `created_at T1`, but `workspace_id W2.id`, `machine_id M9.id`.

**When**
- `M.get_latest_status(db, machine_id=M9.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Machine with ID {M9.id} not found"`.
4. nothing written: nothing written.

### MAC-GS-15 — a W1 status row on W2's machine does not reach W1
- **Rules:** `get_latest_status` R4 [BUG-1140], Errors row 1, HR-16
- **Kind:** bug
- **Expect:** xfail BUG-1140
- **Fails today on:** Then 1 (no error is raised: the invalid row comes back)

**Given**
1. A = status row, `created_at T1`, but `machine_id M9.id`.

**When**
- `M.get_latest_status(db, machine_id=M9.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Machine with ID {M9.id} not found"`.
4. unchanged: unchanged(A).

### MAC-GS-16 — W2's answer is its own older row, not the newer W1 row on its machine
- **Rules:** `get_latest_status` R4, HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = status row, `created_at T1`, but `workspace_id W2.id`, `machine_id M9.id`.
2. B = status row, `created_at T2`, but `machine_id M9.id`.

**When**
- `result = M.get_latest_status(db, machine_id=M9.id, workspace_id=W2.id)`.

**Then**
1. returns: `result.id == A.id`.

### MAC-GS-17 — W2 with only the W1 row on its machine gets None
- **Rules:** `get_latest_status` R4, R2, HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = status row, `created_at T1`, but `machine_id M9.id`.

**When**
- `result = M.get_latest_status(db, machine_id=M9.id, workspace_id=W2.id)`.

**Then**
1. returns: `result is None`.

### MAC-GS-18 — the status row of a soft-deleted machine is returned
- **Rules:** `get_latest_status` R5
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = status row, `created_at T1`, but `machine_id MD.id`.

**When**
- `result = M.get_latest_status(db, machine_id=MD.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.

### MAC-GS-19 — the status row of a machine in a soft-deleted factory is returned
- **Rules:** `get_latest_status` R5
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = status row, `created_at T1`, but `machine_id MF.id`.

**When**
- `result = M.get_latest_status(db, machine_id=MF.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.

### MAC-GS-20 — writes nothing: a newer pending row stays pending and is not returned
- **Rules:** `get_latest_status` R6, Side effects, Overview
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = status row, `created_at T1`.
2. `P = MachineActivityEvent(workspace_id=W1.id, machine_id=M1.id, event_type="status_updated", description="Pending", created_at=T2)`.
3. `db.add(P)` (not flushed).
4. sql_log started.

**When**
- `result = M.get_latest_status(db, machine_id=M1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.
2. pending: `P in db.new`.
3. pending: `P.id is None`.
4. nothing written: nothing written.
5. unchanged: unchanged(A).
6. statement: `written(sql_log) == []`.
7. statement: `locked(sql_log) == []`.

### MAC-GS-21 — the status row of an inactive, live machine is returned
- **Rules:** `get_latest_status` R1, R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = status row, `created_at T1`, but `machine_id MA.id`.

**When**
- `result = M.get_latest_status(db, machine_id=MA.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.

## `MachineActivityManager.get_latest_status_map`

### MAC-SM-01 — each machine with a status row gets its newest row; a machine not asked for gets nothing
- **Rules:** `get_latest_status_map` R1 (DAO R2, R3), Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = status row, `created_at T1`.
2. B = status row, `created_at T2`.
3. C = status row, `created_at T1`, but `machine_id M2.id`.
4. D = status row, `created_at T3`, but `machine_id MA.id`.

**When**
- `result = M.get_latest_status_map(db, workspace_id=W1.id, machine_ids=[M1.id, M2.id])`.

**Then**
1. returns: `isinstance(result, dict)`.
2. returns: `set(result) == {M1.id, M2.id}`.
3. returns: `result[M1.id].id == B.id`.
4. returns: `result[M2.id].id == C.id`.

### MAC-SM-02 — an empty list gives an empty dict with no read at all
- **Rules:** `get_latest_status_map` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = status row, `created_at T1`.
2. sql_log started.

**When**
- `result = M.get_latest_status_map(db, workspace_id=W1.id, machine_ids=[])`.

**Then**
1. returns: `result == {}`.
2. statement: `sql_log == []`.

### MAC-SM-03 — None gives an empty dict with no read at all
- **Rules:** `get_latest_status_map` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = status row, `created_at T1`.
2. sql_log started.

**When**
- `result = M.get_latest_status_map(db, workspace_id=W1.id, machine_ids=None)`.

**Then**
1. returns: `result == {}`.
2. statement: `sql_log == []`.

### MAC-SM-04 — three machines make one read
- **Rules:** `get_latest_status_map` R1, Purpose
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = status row, `created_at T1`.
2. B = status row, `created_at T1`, but `machine_id M2.id`.
3. C = status row, `created_at T1`, but `machine_id MA.id`.
4. sql_log started.

**When**
- `result = M.get_latest_status_map(db, workspace_id=W1.id, machine_ids=[M1.id, M2.id, MA.id])`.

**Then**
1. returns: `set(result) == {M1.id, M2.id, MA.id}`.
2. statement: `len(sql_log) == 1`.

### MAC-SM-05 — an unknown id, 0 and a machine with no status row have no entry
- **Rules:** `get_latest_status_map` R1 (DAO R3)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = status row, `created_at T1`.
2. B = event, `created_at T1`, but `machine_id M2.id`.

**When**
- `result = M.get_latest_status_map(db, workspace_id=W1.id, machine_ids=[M1.id, M2.id, MISSING, 0])`.

**Then**
1. returns: `set(result) == {M1.id}`.
2. returns: `result[M1.id].id == A.id`.

### MAC-SM-06 — an id listed twice gives one entry
- **Rules:** `get_latest_status_map` R1 (DAO R3)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = status row, `created_at T1`.

**When**
- `result = M.get_latest_status_map(db, workspace_id=W1.id, machine_ids=[M1.id, M1.id])`.

**Then**
1. returns: `set(result) == {M1.id}`.
2. returns: `result[M1.id].id == A.id`.

### MAC-SM-07 — a newer row of type "updated" is not a status row
- **Rules:** `get_latest_status_map` R1 (DAO R4)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = status row, `created_at T1`.
2. B = event, `created_at T2`, but `event_type "updated"`, `metadata_json {"status": "IDLE"}`.

**When**
- `result = M.get_latest_status_map(db, workspace_id=W1.id, machine_ids=[M1.id])`.

**Then**
1. returns: `set(result) == {M1.id}`.
2. returns: `result[M1.id].id == A.id`.

### MAC-SM-08 — a newer row of type "status_updated_manual" is not a status row
- **Rules:** `get_latest_status_map` R1 (DAO R4)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = status row, `created_at T1`.
2. B = event, `created_at T2`, but `event_type "status_updated_manual"`, `metadata_json {"status": "IDLE"}`.

**When**
- `result = M.get_latest_status_map(db, workspace_id=W1.id, machine_ids=[M1.id])`.

**Then**
1. returns: `set(result) == {M1.id}`.
2. returns: `result[M1.id].id == A.id`.

### MAC-SM-09 — a newer status row of another workspace on the same machine is ignored
- **Rules:** `get_latest_status_map` R1 (DAO R5)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = status row, `created_at T1`.
2. B = status row, `created_at T2`, but `workspace_id W2.id`.

**When**
- `result = M.get_latest_status_map(db, workspace_id=W1.id, machine_ids=[M1.id])`.

**Then**
1. returns: `set(result) == {M1.id}`.
2. returns: `result[M1.id].id == A.id`.

### MAC-SM-10 — the status rows of a soft-deleted machine and of a machine in a soft-deleted factory are the entries; a newest row with no metadata is the value
- **Rules:** `get_latest_status_map` R1 (DAO R7, R8)
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = status row, `created_at T1`, but `machine_id MD.id`.
2. B = status row, `created_at T1`, but `machine_id MF.id`.
3. C = status row, `created_at T1`.
4. D = status row, `created_at T2`, but `metadata_json None`.

**When**
- `result = M.get_latest_status_map(db, workspace_id=W1.id, machine_ids=[MD.id, MF.id, M1.id])`.

**Then**
1. returns: `set(result) == {MD.id, MF.id, M1.id}`.
2. returns: `result[MD.id].id == A.id`.
3. returns: `result[MF.id].id == B.id`.
4. returns: `result[M1.id].id == D.id`.

### MAC-SM-11 — on a tie the machine gets one entry, one of the tied rows
- **Rules:** `get_latest_status_map` R2, R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = status row, `created_at T2`.
2. B = status row, `created_at T2`.
3. C = status row, `created_at T1`.
4. `A.description = "Edited"`, then `db.flush()`.
5. `db.expire_all()`.

**When**
- `result = M.get_latest_status_map(db, workspace_id=W1.id, machine_ids=[M1.id])`.

**Then**
1. returns: `set(result) == {M1.id}`.
2. returns: `result[M1.id].id in {A.id, B.id}`.

### MAC-SM-12 — on a tie the entry is the highest id, physically first, the row of get_latest_status
- **Rules:** `get_latest_status_map` R2 [BUG-1090]
- **Kind:** bug
- **Expect:** xfail BUG-1090 (non-strict)
- **Fails today on:** Then 3 (no order is requested among the tied rows, so the updated lower-id row can win; it rests on physical order, so the card may pass by accident)

**Given**
1. A = status row, `created_at T2`.
2. B = status row, `created_at T2`.
3. `A.description = "Edited"`, then `db.flush()`.
4. `db.expire_all()`.
5. `single = M.get_latest_status(db, machine_id=M1.id, workspace_id=W1.id)`.

**When**
- `result = M.get_latest_status_map(db, workspace_id=W1.id, machine_ids=[M1.id])`.

**Then**
1. returns: `set(result) == {M1.id}`.
2. returns: `single.id == B.id`.
3. returns: `result[M1.id].id == B.id`.
4. returns: `result[M1.id].id == single.id`.

### MAC-SM-13 — on a tie the entry is the highest id, physically last, the row of get_latest_status
- **Rules:** `get_latest_status_map` R2 [BUG-1090]
- **Kind:** bug
- **Expect:** xfail BUG-1090 (non-strict)
- **Fails today on:** Then 3 (no order is requested among the tied rows; it rests on physical order, so the card usually passes today)

**Given**
1. A = status row, `created_at T2`.
2. B = status row, `created_at T2`.
3. `single = M.get_latest_status(db, machine_id=M1.id, workspace_id=W1.id)`.

**When**
- `result = M.get_latest_status_map(db, workspace_id=W1.id, machine_ids=[M1.id])`.

**Then**
1. returns: `set(result) == {M1.id}`.
2. returns: `single.id == B.id`.
3. returns: `result[M1.id].id == B.id`.
4. returns: `result[M1.id].id == single.id`.

### MAC-SM-14 — the map's query asks the database for an order that includes id
- **Rules:** `get_latest_status_map` R2 [BUG-1090]
- **Kind:** bug
- **Expect:** xfail BUG-1090
- **Fails today on:** Then 3 (the query has no `ORDER BY`)

**Given**
1. A = status row, `created_at T1`.
2. sql_log started.

**When**
- `result = M.get_latest_status_map(db, workspace_id=W1.id, machine_ids=[M1.id])`.

**Then**
1. returns: `result[M1.id].id == A.id`.
2. statement: `len(sql_log) == 1`.
3. statement: `"ORDER BY" in sql_log[0]`.
4. statement: `".id" in sql_log[0].split("ORDER BY", 1)[1]`.

### MAC-SM-15 — another workspace's machine simply has no entry, and nothing is refused
- **Rules:** `get_latest_status_map` R3, HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = status row, `created_at T1`.
2. B = status row, `created_at T2`, but `workspace_id W2.id`, `machine_id M9.id`.

**When**
- `result = M.get_latest_status_map(db, workspace_id=W1.id, machine_ids=[M1.id, M9.id])`.

**Then**
1. returns: `set(result) == {M1.id}`.
2. returns: `result[M1.id].id == A.id`.

### MAC-SM-16 — a W1 status row on W2's machine does appear for W1
- **Rules:** `get_latest_status_map` R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = status row, `created_at T1`, but `machine_id M9.id`.

**When**
- `result = M.get_latest_status_map(db, workspace_id=W1.id, machine_ids=[M9.id])`.

**Then**
1. returns: `set(result) == {M9.id}`.
2. returns: `result[M9.id].id == A.id`.

### MAC-SM-17 — writes nothing: a newer pending row stays pending and is not the entry
- **Rules:** `get_latest_status_map` R4, Side effects, Overview
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = status row, `created_at T1`.
2. `P = MachineActivityEvent(workspace_id=W1.id, machine_id=M1.id, event_type="status_updated", description="Pending", created_at=T2)`.
3. `db.add(P)` (not flushed).
4. sql_log started.

**When**
- `result = M.get_latest_status_map(db, workspace_id=W1.id, machine_ids=[M1.id])`.

**Then**
1. returns: `result[M1.id].id == A.id`.
2. pending: `P in db.new`.
3. pending: `P.id is None`.
4. nothing written: nothing written.
5. unchanged: unchanged(A).
6. statement: `written(sql_log) == []`.
7. statement: `locked(sql_log) == []`.

### MAC-SM-18 — positional arguments work, workspace before machine ids
- **Rules:** `get_latest_status_map` R1, Facts (positional-or-keyword)
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = status row, `created_at T1`.

**When**
- `result = M.get_latest_status_map(db, W1.id, [M1.id])`.

**Then**
1. returns: `result[M1.id].id == A.id`.

## `MachineActivityManager.status_from_activity`

### MAC-SA-01 — None gives None
- **Rules:** `status_from_activity` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. `event = None`.

**When**
- `result = M.status_from_activity(event)`.

**Then**
1. returns: `result is None`.

### MAC-SA-02 — metadata None gives None
- **Rules:** `status_from_activity` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `event = MachineActivityEvent(metadata_json=None)`, not saved.

**When**
- `result = M.status_from_activity(event)`.

**Then**
1. returns: `result is None`.

### MAC-SA-03 — empty metadata gives None
- **Rules:** `status_from_activity` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `event = MachineActivityEvent(metadata_json={})`, not saved.

**When**
- `result = M.status_from_activity(event)`.

**Then**
1. returns: `result is None`.

### MAC-SA-04 — metadata with no status key gives None
- **Rules:** `status_from_activity` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `event = MachineActivityEvent(metadata_json={"note": "belt"})`, not saved.

**When**
- `result = M.status_from_activity(event)`.

**Then**
1. returns: `result is None`.

### MAC-SA-05 — a stored status comes back unchanged
- **Rules:** `status_from_activity` R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. `event = MachineActivityEvent(metadata_json={"status": "IDLE"})`, not saved.

**When**
- `result = M.status_from_activity(event)`.

**Then**
1. returns: `result == "IDLE"`.

### MAC-SA-06 — a stored None comes back as None
- **Rules:** `status_from_activity` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `event = MachineActivityEvent(metadata_json={"status": None, "note": "belt"})`, not saved.

**When**
- `result = M.status_from_activity(event)`.

**Then**
1. returns: `result is None`.

### MAC-SA-07 — a stored empty string stays an empty string
- **Rules:** `status_from_activity` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `event = MachineActivityEvent(metadata_json={"status": ""})`, not saved.

**When**
- `result = M.status_from_activity(event)`.

**Then**
1. returns: `result == ""`.

### MAC-SA-08 — a stored number stays a number
- **Rules:** `status_from_activity` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `event = MachineActivityEvent(metadata_json={"status": 5})`, not saved.

**When**
- `result = M.status_from_activity(event)`.

**Then**
1. returns: `result == 5`.
2. returns: `isinstance(result, int)`.

### MAC-SA-09 — the event type is not looked at
- **Rules:** `status_from_activity` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `event = MachineActivityEvent(event_type="maintenance_logged", metadata_json={"status": "MAINTENANCE"})`, not saved.

**When**
- `result = M.status_from_activity(event)`.

**Then**
1. returns: `result == "MAINTENANCE"`.

### MAC-SA-10 — a saved row works like an unsaved one
- **Rules:** `status_from_activity` R4, Inputs
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = status row, `created_at T1`, but `metadata_json {"status": "OFF"}`.

**When**
- `result = M.status_from_activity(A)`.

**Then**
1. returns: `result == "OFF"`.

### MAC-SA-11 — a non-empty list as metadata raises AttributeError
- **Rules:** `status_from_activity` Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. `event = MachineActivityEvent(metadata_json=["status"])`, not saved.

**When**
- `M.status_from_activity(event)`.

**Then**
1. raises: `AttributeError`.

### MAC-SA-12 — a non-empty string as metadata raises AttributeError
- **Rules:** `status_from_activity` Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. `event = MachineActivityEvent(metadata_json="status")`, not saved.

**When**
- `M.status_from_activity(event)`.

**Then**
1. raises: `AttributeError`.

### MAC-SA-13 — the method can be called on the class
- **Rules:** `status_from_activity` R4, Facts (static)
- **Kind:** happy
- **Expect:** pass

**Given**
1. `event = MachineActivityEvent(metadata_json={"status": "IDLE"})`, not saved.

**When**
- `result = MachineActivityManager.status_from_activity(event)`.

**Then**
1. returns: `result == "IDLE"`.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| `list_events` R1, the DAO's detail: R11, R12 (date range, UTC days), the rest of R13 | `tests/unit/dao/machine_activity_event.cases.md` | Covered there. Here each argument has one positive and one negative, per the lighter target. |
| `get_latest_status_map` R2 alarm when the fix has no `ORDER BY` | `tests/unit/dao/machine_activity_event.cases.md` MAE-LM-15, Spec gap 3 | The same alarm, the same blind spot; see Spec gap 2 here. |
| `list_events` R2, `log_event` R6, `get_latest_status` R3 — the HTTP status | integration | the 404 reaches the client |
| `list_events` R8; HR-7 | `GET /machines/{id}/activity/` | `skip >= 0`, `1 <= limit <= 1000`, date parsing |
| Q5, Q6; FU-1 | `MachineService.get_machine_activity`, `app/schemas/machine_activity_event.py` | the response keeps 10 metadata keys; a row of the wrong shape gives 500; `metadata: null`; `performer_name` |
| `log_event` R6; Q3; BUG-1091; FU-2 | `AttachmentManager` (`create_pending_attachment`, `_log_attachment_entity_events`) | sign and confirm refuse a foreign machine; a delete skips the event for such a link and proceeds |
| `collect_field_changes` R7; Q1; FU-3 | `machine_maintenance_log_manager.spec.md` `update_log` R12a, `create_log` R12 | a third decimal in `cost` is refused with 400; the log shows the stored form |
| `log_event` R7 | `MachineManager.delete_machine` | the `deactivated` entry is written after the soft delete |
| Overview: two real concurrent transactions | integration | none here |
| FU-5 | `tests/unit/dao/machine.spec.md` `search_advanced` R12c | a status row with JSON `null` metadata; nothing to change |

## Spec gaps
| # | Where | What is missing | How it blocked the design |
|---|---|---|---|
| 1 | `status_from_activity` Errors, R2 | Errors says "non-empty list or string"; R2 names only `None` and `{}`. What `[]` and `""` give as metadata is implied, not stated. | The empty side of that boundary has no card. MAC-SA-11, SA-12 cover the non-empty side. |
| 2 | `get_latest_status_map` R2 | How the fix must look is not stated (same as DAO cases Spec gap 3). A fix with no `ORDER BY` (a `max(id)` subquery, a Python tie-break) leaves MAC-SM-14 xfailing and no alarm sounds. | MAC-SM-14 asserts `ORDER BY` and `.id`, no direction. That card must be rewritten with such a fix. |
| 3 | `log_event` R6, R8, R9 | After BUG-1091 the order of the machine check against the performer and metadata refusals is not stated: a foreign machine with an unknown performer, say. | No card combines two faults. Each refusal has its own card. |

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `format_field_value` | R1 | MAC-FV-01 |
| `format_field_value` | R2 | MAC-FV-02, FV-03, FV-04, FV-05 |
| `format_field_value` | R3 | MAC-FV-06, FV-07, FV-08 |
| `format_field_value` | R4 | MAC-FV-09 |
| `format_field_value` | R5 | MAC-FV-10, FV-11, FV-12, FV-13, FV-14, FV-15, FV-16, FV-17 |
| `collect_field_changes` | R1 | MAC-CF-01, CF-02 |
| `collect_field_changes` | R2 | MAC-CF-03 |
| `collect_field_changes` | R3 | MAC-CF-04 |
| `collect_field_changes` | R4 | MAC-CF-05 |
| `collect_field_changes` | R5 | MAC-CF-06, CF-07, CF-08, CF-09, CF-10 |
| `collect_field_changes` | R6 | MAC-CF-11, CF-12, CF-13 |
| `collect_field_changes` | R7 | MAC-CF-14, CF-15 |
| `collect_field_changes` | R8 | MAC-CF-16, CF-17 |
| `collect_field_changes` | R9 | MAC-CF-18 |
| `collect_field_changes` | Errors row 1 | MAC-CF-19 |
| Facts | `MACHINE_LOG_FIELDS` | MAC-CF-20 |
| Facts | `MACHINE_ITEM_LOG_FIELDS` | MAC-CF-21 |
| `log_event` | R1 | MAC-LE-01, LE-02, LE-03, LE-04, LE-16, LE-33 |
| `log_event` | R2 | MAC-LE-05, LE-06, LE-07 |
| `log_event` | R3 | MAC-LE-08, LE-09, LE-10 |
| `log_event` | R4 | MAC-LE-11, LE-12, LE-13, LE-15 |
| `log_event` | R5 | MAC-LE-17 |
| `log_event` | R6 [BUG-1091] | MAC-LE-18, LE-19, LE-20, LE-21, LE-22, LE-33 |
| `log_event` | R7 | MAC-LE-19, LE-23, LE-24 |
| `log_event` | R8 | MAC-LE-25, LE-26, LE-27 |
| `log_event` | R9 | MAC-LE-28, LE-29 |
| `log_event` | R10 | MAC-LE-32 |
| `log_event` | Errors row 1 [BUG-1091] | MAC-LE-18, LE-19, LE-20, LE-21, LE-22 |
| `log_event` | Errors row 2 (Today) | MAC-LE-20, LE-21 |
| `log_event` | Errors row 3 (Today) | MAC-LE-22 |
| `log_event` | Errors row 4 | MAC-LE-25, LE-26 |
| `log_event` | Errors row 5 | MAC-LE-30, LE-31 |
| `log_event` | Errors row 6 | MAC-LE-14 |
| `log_event` | Errors row 7 | MAC-LE-28, LE-29 |
| `log_event` | Overview (one INSERT, no lock, no commit) | MAC-LE-04, LE-32 |
| `list_events` | R1 | MAC-LI-01 … LI-19, LI-26 |
| `list_events` | R2 | MAC-LI-20, LI-21, LI-22, LI-23 |
| `list_events` | R3 | MAC-LI-24, LI-25, LI-26 |
| `list_events` | R4 | MAC-LI-27, LI-28, LI-29 |
| `list_events` | R5 | MAC-LI-32 |
| `list_events` | R6 | MAC-LI-30, LI-31 |
| `list_events` | R7 | MAC-LI-33, LI-34, LI-42, LI-43, LI-44, LI-45, LI-46 |
| `list_events` | R8 | MAC-LI-06, LI-35, LI-36, LI-37, LI-38, LI-39, LI-40, LI-41 |
| `list_events` | R9 [BUG-1141] | MAC-LI-42, LI-43, LI-44, LI-45, LI-46 |
| `list_events` | R10 | MAC-LI-47 |
| `list_events` | Errors row 1 | MAC-LI-20, LI-21, LI-22, LI-23 |
| `list_events` | Errors row 2 | MAC-LI-40, LI-41 |
| `get_latest_status` | R1 | MAC-GS-01 … GS-09, GS-21 |
| `get_latest_status` | R2 | MAC-GS-10, GS-11, GS-17 |
| `get_latest_status` | R3 [BUG-1140] | MAC-GS-12, GS-13, GS-14, GS-21 |
| `get_latest_status` | R4 [BUG-1140] | MAC-GS-15, GS-16, GS-17 |
| `get_latest_status` | R5 | MAC-GS-18, GS-19 |
| `get_latest_status` | R6 | MAC-GS-20 |
| `get_latest_status` | Errors row 1 [BUG-1140] | MAC-GS-12, GS-13, GS-14, GS-15 |
| `get_latest_status_map` | R1 | MAC-SM-01 … SM-11, SM-18 |
| `get_latest_status_map` | R2 [BUG-1090] | MAC-SM-11, SM-12, SM-13, SM-14 |
| `get_latest_status_map` | R3 | MAC-SM-15, SM-16 |
| `get_latest_status_map` | R4 | MAC-SM-17 |
| `status_from_activity` | R1 | MAC-SA-01 |
| `status_from_activity` | R2 | MAC-SA-02, SA-03 |
| `status_from_activity` | R3 | MAC-SA-04 |
| `status_from_activity` | R4 | MAC-SA-05, SA-06, SA-07, SA-08, SA-10, SA-13 |
| `status_from_activity` | R5 | MAC-SA-09 |
| `status_from_activity` | Errors row 1 | MAC-SA-11, SA-12 |
