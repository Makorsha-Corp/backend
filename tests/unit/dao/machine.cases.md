# Test cases — `app/dao/machine.py`

> **Spec:** `tests/unit/dao/machine.spec.md` (source commit e48a092)
> **Status:** READY — the spec is **APPROVED** (2026-10-11); Q8 and Q9 were accepted as suggested, so nothing is provisional and no card changed.
> **Revision:** 1 — spec revision 2026-10-10 (1). **Added 29 cards:** the new callable `restore` (R1–R9, R7a tagged BUG-890 / BUG-891) → MCH-RS-01 … RS-22; `get_by_factory` R3b → MCH-GF-30, GF-31; `get_by_section` R3b → MCH-GS-30, GS-31; `search_advanced` R3c → MCH-SA-128, SA-129; `search_advanced` R8 (whitespace = `str.strip()`, the spec's own `"\tbolt\n"` example) → MCH-SA-130. **Changed, Rules line only** (R3a was narrowed to "hidden"; what these four cards check moved to R3b): MCH-GF-13, GF-14, GS-13, GS-14 — the docstrings of their four tests must follow. No other existing card was touched, none retired, none renumbered. `soft_delete` R5 (one sentence added) and the tag-only changes need no card change. Conventions: `RS` prefix, **FD made live again**, re-read of FD. Spec gaps 1 and 2 are closed by the spec. Verifier feedback (`machine.verify.md`, PASS): no `case-missing` item; its three "dead" survivors in `restore` (lines 84, 85, 90) are now covered by MCH-RS-01 … RS-22.
> **Counts:** 245 cases · 194 expected-to-pass · 51 expected-to-fail (bugs) · 13 deferred

## Reviewer summary
- **Per callable:** `get_by_factory` 31 (4 bug) · `get_by_section` 31 (5 bug) · `soft_delete` 13 · `restore` 22 (2 bug) · `search_advanced` 130 (40 bug) · inherited `BaseDAO` methods on `Machine` 18.
- **Accepted by the reviewer on 2026-10-11 (were provisional) — the cards that rest on Q8 and Q9:**
  - **Q8** (`restore` R2a — restoring records nobody and writes no activity entry): MCH-RS-04, RS-05, RS-06. One line of the round-trip card MCH-RS-20 (Then 4, `updated_by == U1.id`) also assumes it. If the answer becomes "restore takes the acting user and stamps `updated_by`", these change and every `restore` call gains an argument.
  - **Q9** (`restore` R9 — no name check, two live machines may share a name): MCH-RS-22 only.
- **Confirmed by the reviewer on 2026-10-11 — "hidden, not cascaded"** (was an open point; the alternative, marking each machine deleted, was put to the reviewer and not chosen). The reviewer's sentence about machines of a deleted factory ("these should be soft deleted but stays hidden …") was read by the main session as *hidden by the factory's state alone, machine rows untouched* — not as a cascading soft delete of the machines. If the reviewer meant a cascade, exactly these cards must be redesigned (spec: R3a–R3c of the three lists, `restore` R7 / R7a):
  - hidden while the factory is deleted (R3a, xfail): MCH-GF-12, GS-12, SA-15, SA-16, SA-17, SA-18;
  - the machine row / assignment is left untouched (R3b part 1, pass): MCH-GF-14, GF-31, GS-14, GS-31, SA-21;
  - back by itself once the factory is no longer deleted (R3b part 3 / R3c, pass): MCH-GF-30, GS-30, SA-128, SA-129;
  - `restore` inside a deleted factory (R7, R7a): MCH-RS-16 (pass), RS-17 (xfail BUG-890), RS-18 (xfail BUG-891), RS-19 (pass).
  - Not affected by the reading: the "live but inactive factory" cards (MCH-GF-13, GS-13, SA-19, SA-20) and the raw lookups (MCH-INH-15, INH-17, INH-18).
- **Confirmed answers and their cards:** P1 / BUG-890 — MCH-SA-15 … SA-18, RS-17 (xfail), SA-19 … SA-21, SA-128, SA-129. P2 / BUG-891 — MCH-GF-12, GS-12, RS-18 (xfail), GF-13, GF-14, GF-30, GF-31, GS-13, GS-14, GS-30, GS-31. P3 / BUG-892 — MCH-SA-39 … SA-43, SA-130 (xfail), SA-44, SA-45. Q1 / BUG-886 — MCH-SA-67 … SA-70, SA-72 … SA-89 (22 xfail). Q2 (lenient sort fallback intended) — MCH-SA-92 … SA-96, SA-104 … SA-106. Q3 (whitespace-only counts as a value) — MCH-SA-61 … SA-64. Q5 (keep `restore`) — MCH-RS-01 … RS-22. Q7 (`factory_section_id` trap intended) — MCH-INH-02 … INH-04, INH-10 … INH-13. Q4 / Q6 (`get_active_by_workspace` and the `include_deleted` parameter are dead code, to be removed) — no cards. House-rule lines: BUG-887 — MCH-SA-99, SA-100; BUG-888 — MCH-SA-55, SA-56, SA-58, SA-59, SA-60; BUG-889 — MCH-GS-15, SA-33; BUG-343 — MCH-GF-20, GF-26, GF-27, GS-21, GS-27, GS-28.
- **Notable design choices:**
  - `restore` (new): every card re-reads the row; `restore` does not read the clock, so nothing is mocked. "No UPDATE was issued" (R4) is seen as `updated_at is None` (MCH-RS-09). "Not committed" is one savepoint card (MCH-RS-12). R7a is one strict xfail per bug (MCH-RS-17 against `search_advanced`, RS-18 against the two lookups); what holds today in that scenario — the row becomes live, the factory row is not touched — is the pass card MCH-RS-16. The second sentence of R7a (the machine appears once the factory is no longer deleted) holds today and is the pass card MCH-RS-19, which needs one step between the call and the checks. R8 (undo of `soft_delete`) is two cards whose Given runs `dao.soft_delete` — the only Given in the file that goes through the DAO (MCH-RS-20, RS-21).
  - "Factory no longer deleted" (MCH-GF-30, GS-30, SA-128, SA-129, RS-19): the standing factory FD is changed directly on its row (**FD made live again**, Conventions), never through a factory DAO — nothing in the application restores a factory today (spec follow-up FU-4).
  - `utcnow` is patched to NOW in every test by the helper file (Conventions, Externals), so no `soft_delete` card needs a mock of its own. Every `soft_delete` card re-reads the row from the database; the error card (MCH-SD-10) asserts unchanged / nothing written against a before-snapshot; "not committed" is one savepoint card (MCH-SD-08).
  - The 22 BUG-886 cards all fail today because the call itself raises `AttributeError`; each states the full intended result, so they become real tests the day the filter works. What holds today (`latest_event_type=None`) is in pass cards MCH-SA-25, SA-71.
  - `get_by_factory` / `get_by_section` have no order today (BUG-343): every card except the six non-strict xfails compares ids as a sorted list, and the paging cards assert sizes and membership only. `search_advanced` cards assert exact ordered lists and never use names that differ only in case, except the two BUG-887 cards.
  - `search_advanced` combinations are not a cross-product: each filter has its own cards, then one "every filter at once, each wrong machine fails exactly one filter" card (MCH-SA-123), the factory × section rule (SA-30 … SA-32), two OR-grouping cards for the search (SA-124, SA-125), `has_model_number` × `has_manufacturer` (SA-65, SA-66), one filter × sort × page card (SA-127) and status × factory / search / sort+page (SA-85 … SA-87, xfail).
  - Each bug card that also asserts something that holds today has a pass companion (MCH-GF-14, GS-14, GS-16, SA-21, SA-34, RS-16), and the "inactive but live" side of every soft-delete rule has its own pass card so an over-fix on `is_active` is caught.
  - Cards marked `Author: claude` (21): MCH-GF-15, GF-16, GS-17, SA-116, SA-117 (bulk setup of 101 rows); GF-20, GF-26, GF-27, GS-21, GS-27, GS-28 (non-strict xfail BUG-343); SD-08, RS-12 (savepoint rollback and commit spy); GF-30, GS-30, SA-128, SA-129, RS-16 (change the standing row FD directly); RS-19 (a step between the call and the checks); RS-20, RS-21 (a Given that runs `dao.soft_delete`, and a snapshot taken before it).
- **Needs a decision:** None blocking. Gaps 1 and 2 are closed by the spec. Of the open points under Spec gaps, the ones a reviewer may care about: unknown `"status"` values (gap 4), whether identical names already sort by id today (gap 8), the factory's deletion-stamp columns that MCH-RS-16 relies on (gap 11). Plus the two provisional answers (Q8, Q9) and the "hidden, not cascaded" reading above.


## Conventions for this module

**IDs.** `MCH` = `app/dao/machine.py`. `GF` get_by_factory · `GS` get_by_section · `SD` soft_delete · `RS` restore · `SA` search_advanced · `INH` inherited `BaseDAO` methods on `Machine`.

**Actors and fixed values.**
- `dao` = the singleton `machine_dao` (`from app.dao.machine import machine_dao`). `db` = the test's real database session, always the first argument; every other argument is passed by keyword (only `dao.get(db, <id>)` takes the id positionally). `result` = what the When call returns.
- W1, W2 = two `workspaces` rows. U1, U2 = two `profiles` rows: U1 is `created_by` of every Given machine, U2 is the acting user of the calls.
- `Machine` = `app.models.machine.Machine`. `MachineCreate`, `MachineUpdate` = the schemas of `app.schemas.machine`. IDLE, RUNNING, OFF, MAINTENANCE = the four members of `MachineEventTypeEnum` (`app.models.enums`).
- MISSING = `999999999`: an id that no row of any table has.
- T0 = `datetime(2025, 12, 1, 8, 0, 0)`. T1 = `datetime(2026, 1, 1, 9, 0, 0)`, T2 = `datetime(2026, 1, 1, 10, 0, 0)`, T3 = `datetime(2026, 1, 1, 11, 0, 0)` (all naive).
- NOW = `datetime(2026, 3, 1, 10, 0, 0)` (naive).
- `"a\\b"` is the Python literal for the three characters a\b (one backslash).

**Externals.** In every test `app.dao.machine.utcnow` is patched to return NOW (the helper file does it; a card never patches anything itself). Nothing else is mocked.

**Given rows.** Rows are inserted directly into the tables (never through `dao`) and flushed one at a time in the order written, so ids rise in that order. A card names, by column name, every column that differs from these defaults.
- These eleven rows exist in every test and need no Given line:
  - F1 = `factories` row: `name "Factory One"`, `abbreviation "F1"`, `workspace_id W1.id`, `is_active True`, `is_deleted False`.
  - F2 = the same as F1, but `name "Factory Two"`, `abbreviation "F2"`.
  - F9 = the same as F1, but `name "Factory Nine"`, `abbreviation "F9"`, `workspace_id W2.id`.
  - FD = the same as F1, but `name "Old Plant"`, `abbreviation "OP"`, `is_deleted True` (a soft-deleted factory of W1; `is_active` stays True).
  - FI = the same as F1, but `name "Idle Plant"`, `abbreviation "IP"`, `is_active False` (a live but inactive factory of W1).
  - S1 = `factory_sections` row: `name "Section One"`, `factory_id F1.id`, `workspace_id W1.id`, `is_active True`, `is_deleted False`.
  - S2 = the same as S1, but `name "Section Two"` (a second section of F1).
  - S3 = the same as S1, but `name "Section Three"`, `factory_id F2.id`.
  - SX = the same as S1, but `name "Old Section"`, `is_deleted True` (a soft-deleted section of F1).
  - SI = the same as S1, but `name "Idle Section"`, `is_active False` (a live but inactive section of F1).
  - S9 = the same as S1, but `name "Section Nine"`, `factory_id F9.id`, `workspace_id W2.id`.
- Machines, assignments and events exist only if the card's Given lists them.
- **machine** = `machines` row: `workspace_id W1.id`, `factory_id F1.id`, `is_running False`, `model_number None`, `manufacturer None`, `note None`, `created_by U1.id`, `updated_by None`, `updated_at None`, `is_active True`, `is_deleted False`, `deleted_at None`, `deleted_by None`, `created_at` left to the database (the same instant for every row of a test). The card always gives `name`; after the word "but" it lists every other column that differs.
- **deleted** (said of a machine) = `is_deleted True`, `is_active False`, `deleted_at T0`, `deleted_by U1.id`.
- **assignment of M to S** = `machine_section_assignments` row: `workspace_id` = M's `workspace_id`, `machine_id M.id`, `factory_section_id S.id`; `db.expire_all()` is called right after it is flushed.
- **event of M** = `machine_activity_events` row: `workspace_id` = M's `workspace_id`, `machine_id M.id`, `event_type "status_updated"`, `description "status"`, `performed_by None`. The card always gives `created_at` and `metadata_json`; after the word "but" it lists every other column that differs.

**Named checks.**
- **ids(result)** = `[m.id for m in result]` and **names(result)** = `[m.name for m in result]` — lists in the order returned (the order is part of the check). `sorted(ids(result)) == [M1.id, M2.id]` is used where the order is not part of the check; the right-hand ids are written in Given order, which is ascending id order.
- **by_id(result, X)** = the one element of `result` whose `id == X.id`.
- **re-read X** = `db.expire_all()`, then SELECT X by id; the listed values are database values. (Expiring discards unflushed changes, so a re-read that shows a new value also proves the change was flushed.) "the returned row" = re-read by `result.id`.
- **unchanged(X)** = after re-read, every column of X equals its value before the call (snapshot taken after the last Given row, before the call).
- **nothing written** = the numbers of rows in `machines`, `machine_section_assignments`, `machine_activity_events`, `factories` and `factory_sections` (all workspaces) equal their values before the call.
- `count:` lines count the rows of the named table in all workspaces. Assert `updated_at` only as `is None` / `is not None`.
- `raises: DataError` = `sqlalchemy.exc.DataError`; `raises: IntegrityError` = `sqlalchemy.exc.IntegrityError`. Wrap the call for both: `with pytest.raises(<Type>) as exc:` then `with db.begin_nested():` then the call; keep using `db` afterwards. `InvalidRowCountInLimitClause`, `InvalidRowCountInResultOffsetClause`, `ForeignKeyViolation` = classes of `psycopg2.errors`.
- `raises: AttributeError` = plain `with pytest.raises(AttributeError):` around the call — no `begin_nested`; keep using `db` for the remaining checks.
- Further `raises:` lines of the same card are assertions on `exc.value`, written after the `with` block.

**xfail cards.** Write the call and the checks exactly as shown; the harness adds the marker. A card whose Expect says "(non-strict)" is marked Author: claude and uses `pytest.mark.xfail(strict=False, reason="BUG-343")`.

**Rolled back** (cards marked Author: claude only). `sp = db.begin_nested()` directly before the call and a spy that wraps `db.commit` (still callable, records calls); the first checks run inside the savepoint; then `sp.rollback()` and the "after the savepoint rollback" checks.

**FD made live again** (cards marked Author: claude only). `FD.is_deleted = False`, `FD.deleted_at = None`, `FD.deleted_by = None`, set directly on the standing row FD, then `db.flush()` — never through a factory DAO. "re-read FD" works like re-read of any row: `db.expire_all()`, then SELECT the `factories` row by id.

**Race simulations.** None in this module.


## `DAOMachine.get_by_factory`

### MCH-GF-01 — returns a list of the machines of that factory
- **Rules:** `get_by_factory` R1, R7
- **Kind:** happy
- **Expect:** pass

**Given**
1. M1 = machine, `name "Lathe"`.
2. M2 = machine, `name "Press"`.
3. M3 = machine, `name "Drill"`, but `factory_id F2.id`.

**When**
- `result = dao.get_by_factory(db, factory_id=F1.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `sorted(ids(result)) == [M1.id, M2.id]`.
3. returns: `len(result) == 2`.
4. returns: `isinstance(result[0], Machine)`.

### MCH-GF-02 — a call for the other factory returns only that factory's machine
- **Rules:** `get_by_factory` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. M1 = machine, `name "Lathe"`.
2. M2 = machine, `name "Press"`.
3. M3 = machine, `name "Drill"`, but `factory_id F2.id`.

**When**
- `result = dao.get_by_factory(db, factory_id=F2.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [M3.id]`.

### MCH-GF-03 — another workspace's machine is not returned when its factory id is given
- **Rules:** `get_by_factory` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. M1 = machine, `name "Lathe"`.
2. M9 = machine, `name "Other"`, but `workspace_id W2.id`, `factory_id F9.id`.

**When**
- `result = dao.get_by_factory(db, factory_id=F9.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### MCH-GF-04 — a machine of another workspace carrying this factory's id is not returned
- **Rules:** `get_by_factory` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. M1 = machine, `name "Lathe"`.
2. MX = machine, `name "Stray"`, but `workspace_id W2.id`. (Same factory id F1 as M1, other workspace.)

**When**
- `result = dao.get_by_factory(db, factory_id=F1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [M1.id]`.

### MCH-GF-05 — a call for the other workspace returns only that workspace's machine
- **Rules:** `get_by_factory` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. M1 = machine, `name "Lathe"`.
2. M9 = machine, `name "Other"`, but `workspace_id W2.id`, `factory_id F9.id`.

**When**
- `result = dao.get_by_factory(db, factory_id=F9.id, workspace_id=W2.id)`.

**Then**
1. returns: `ids(result) == [M9.id]`.

### MCH-GF-06 — an unknown workspace id returns an empty list
- **Rules:** `get_by_factory` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1 = machine, `name "Lathe"`.

**When**
- `result = dao.get_by_factory(db, factory_id=F1.id, workspace_id=MISSING)`.

**Then**
1. returns: `result == []`.

### MCH-GF-07 — a soft-deleted machine is not returned
- **Rules:** `get_by_factory` R2
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. M1 = machine, `name "Lathe"`.
2. M2 = machine, `name "Press"`, but deleted.

**When**
- `result = dao.get_by_factory(db, factory_id=F1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [M1.id]`.

### MCH-GF-08 — an inactive live machine and a running machine are returned
- **Rules:** `get_by_factory` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1 = machine, `name "Lathe"`, but `is_active False`. (Still `is_deleted False`.)
2. M2 = machine, `name "Press"`, but `is_running True`.

**When**
- `result = dao.get_by_factory(db, factory_id=F1.id, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [M1.id, M2.id]`.

### MCH-GF-09 — a factory id that does not exist returns an empty list
- **Rules:** `get_by_factory` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1 = machine, `name "Lathe"`.

**When**
- `result = dao.get_by_factory(db, factory_id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### MCH-GF-10 — factory_id 0 returns an empty list
- **Rules:** `get_by_factory` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1 = machine, `name "Lathe"`.
2. M2 = machine, `name "Drill"`, but `factory_id F2.id`.

**When**
- `result = dao.get_by_factory(db, factory_id=0, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### MCH-GF-11 — a factory whose only machine is soft-deleted returns an empty list
- **Rules:** `get_by_factory` R3, R2
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. M1 = machine, `name "Lathe"`.
2. M2 = machine, `name "Drill"`, but `factory_id F2.id`, deleted.

**When**
- `result = dao.get_by_factory(db, factory_id=F2.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### MCH-GF-12 — the live machine of a soft-deleted factory is not returned
- **Rules:** `get_by_factory` R3a [BUG-891]
- **Kind:** bug
- **Expect:** xfail BUG-891
- **Fails today on:** Then 2 (the factory row is never looked at, so MD comes back)

**Given**
1. M1 = machine, `name "Lathe"`.
2. MD = machine, `name "Press"`, but `factory_id FD.id`. (FD is the soft-deleted factory; MD itself is live.)

**When**
- `result = dao.get_by_factory(db, factory_id=FD.id, workspace_id=W1.id)`.

**Then**
1. unchanged: unchanged(MD).
2. returns: `result == []`.

### MCH-GF-13 — the machine of a live but inactive factory is returned
- **Rules:** `get_by_factory` R3b
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1 = machine, `name "Lathe"`.
2. MI = machine, `name "Press"`, but `factory_id FI.id`. (FI is the live but inactive factory.)

**When**
- `result = dao.get_by_factory(db, factory_id=FI.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [MI.id]`.

### MCH-GF-14 — a lookup leaves the machine of a soft-deleted factory untouched
- **Rules:** `get_by_factory` R3b, R1
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. M1 = machine, `name "Lathe"`.
2. MD = machine, `name "Press"`, but `factory_id FD.id`. (FD is the soft-deleted factory; MD itself is live.)

**When**
- `result = dao.get_by_factory(db, factory_id=F1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [M1.id]`.
2. unchanged: unchanged(MD).
3. re-read MD: `is_deleted is False`, `is_active is True`.
4. nothing written: nothing written.
5. count: `machines` has exactly 2 rows.

### MCH-GF-15 — default limit returns exactly 100 of 101 machines
- **Rules:** `get_by_factory` R4
- **Kind:** boundary
- **Expect:** pass
- **Author:** claude — bulk setup (a loop over 101 machines) outside the Conventions vocabulary

**Given**
1. 101 machines N1 … N101, inserted in that order; machine Nk (k = 1 … 101) has `name` = `f"M{k:03d}"` (so "M001" … "M101") and is otherwise the default machine.

**When**
- `result = dao.get_by_factory(db, factory_id=F1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.
2. returns: `len(set(ids(result))) == 100`.
3. returns: `set(ids(result)) <= {N1.id, …, N101.id}` (the set of all 101 ids).

### MCH-GF-16 — an explicit limit of 101 returns all 101 machines
- **Rules:** `get_by_factory` R4
- **Kind:** boundary
- **Expect:** pass
- **Author:** claude — bulk setup (a loop over 101 machines) outside the Conventions vocabulary

**Given**
1. 101 machines N1 … N101, inserted in that order; machine Nk (k = 1 … 101) has `name` = `f"M{k:03d}"` (so "M001" … "M101") and is otherwise the default machine.

**When**
- `result = dao.get_by_factory(db, factory_id=F1.id, workspace_id=W1.id, limit=101)`.

**Then**
1. returns: `len(result) == 101`.
2. returns: `sorted(ids(result)) == [N1.id, …, N101.id]` (all 101 ids, ascending).

### MCH-GF-17 — a soft-deleted machine does not use up a place in the page
- **Rules:** `get_by_factory` R4, R2
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. M1 = machine, `name "Lathe"`.
2. M2 = machine, `name "Mill"`, but deleted.
3. M3 = machine, `name "Press"`.

**When**
- `result = dao.get_by_factory(db, factory_id=F1.id, workspace_id=W1.id, limit=2)`.

**Then**
1. returns: `sorted(ids(result)) == [M1.id, M3.id]`.

### MCH-GF-18 — limit 2 of three machines returns two different machines
- **Rules:** `get_by_factory` R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. M1 = machine, `name "Lathe"`.
2. M2 = machine, `name "Mill"`.
3. M3 = machine, `name "Press"`.

**When**
- `result = dao.get_by_factory(db, factory_id=F1.id, workspace_id=W1.id, skip=0, limit=2)`.

**Then**
1. returns: `len(result) == 2`.
2. returns: `len(set(ids(result))) == 2`.
3. returns: `set(ids(result)) <= {M1.id, M2.id, M3.id}`.

### MCH-GF-19 — the last window is short
- **Rules:** `get_by_factory` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1 = machine, `name "Lathe"`.
2. M2 = machine, `name "Mill"`.
3. M3 = machine, `name "Press"`.

**When**
- `result = dao.get_by_factory(db, factory_id=F1.id, workspace_id=W1.id, skip=2, limit=2)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `result[0].id in [M1.id, M2.id, M3.id]`.

### MCH-GF-20 — a middle window holds the machine that is second by name
- **Rules:** `get_by_factory` R4, R6 [BUG-343]
- **Kind:** bug
- **Expect:** xfail BUG-343 (non-strict)
- **Fails today on:** Then 1 (no ordering is requested; the database usually answers in insertion order, giving ["apple"], but may happen to give this order — non-strict xfail, the assertion is never weakened)
- **Author:** claude — non-strict xfail (`pytest.mark.xfail(strict=False, reason="BUG-343")`)

**Given**
1. M1 = machine, `name "Zulu"`.
2. M2 = machine, `name "apple"`.
3. M3 = machine, `name "Mango"`.

**When**
- `result = dao.get_by_factory(db, factory_id=F1.id, workspace_id=W1.id, skip=1, limit=1)`.

**Then**
1. returns: `names(result) == ["Mango"]`.

### MCH-GF-21 — limit 0 returns an empty list
- **Rules:** `get_by_factory` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1 = machine, `name "Lathe"`.

**When**
- `result = dao.get_by_factory(db, factory_id=F1.id, workspace_id=W1.id, limit=0)`.

**Then**
1. returns: `result == []`.

### MCH-GF-22 — skip equal to the number of matching machines returns an empty list
- **Rules:** `get_by_factory` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1 = machine, `name "Lathe"`.
2. M2 = machine, `name "Press"`.

**When**
- `result = dao.get_by_factory(db, factory_id=F1.id, workspace_id=W1.id, skip=2)`.

**Then**
1. returns: `result == []`.

### MCH-GF-23 — skip one below the number of matching machines returns one machine
- **Rules:** `get_by_factory` R5, R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1 = machine, `name "Lathe"`.
2. M2 = machine, `name "Press"`.

**When**
- `result = dao.get_by_factory(db, factory_id=F1.id, workspace_id=W1.id, skip=1)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `result[0].id in [M1.id, M2.id]`.

### MCH-GF-24 — negative limit is rejected by the database and nothing changes
- **Rules:** `get_by_factory` R5, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. M1 = machine, `name "Lathe"`.

**When**
- `dao.get_by_factory(db, factory_id=F1.id, workspace_id=W1.id, limit=-1)`.

**Then**
1. raises: `DataError`.
2. raises: `isinstance(exc.value.orig, InvalidRowCountInLimitClause)`.
3. raises: `exc.value.orig.pgcode == "2201W"`.
4. raises: `"LIMIT must not be negative" in str(exc.value.orig)`.
5. nothing written: nothing written.
6. unchanged: unchanged(M1).

### MCH-GF-25 — negative skip is rejected by the database and nothing changes
- **Rules:** `get_by_factory` R5, Errors row 2
- **Kind:** error
- **Expect:** pass

**Given**
1. M1 = machine, `name "Lathe"`.

**When**
- `dao.get_by_factory(db, factory_id=F1.id, workspace_id=W1.id, skip=-1)`.

**Then**
1. raises: `DataError`.
2. raises: `isinstance(exc.value.orig, InvalidRowCountInResultOffsetClause)`.
3. raises: `exc.value.orig.pgcode == "2201X"`.
4. raises: `"OFFSET must not be negative" in str(exc.value.orig)`.
5. nothing written: nothing written.
6. unchanged: unchanged(M1).

### MCH-GF-26 — machines come back by name, case-insensitive ascending
- **Rules:** `get_by_factory` R6 [BUG-343]
- **Kind:** bug
- **Expect:** xfail BUG-343 (non-strict)
- **Fails today on:** Then 1 (no ordering is requested; the database usually answers in insertion order ["Zulu", "apple", "Banana"], but may happen to give this order — non-strict xfail, the assertion is never weakened)
- **Author:** claude — non-strict xfail (`pytest.mark.xfail(strict=False, reason="BUG-343")`)

**Given**
1. M1 = machine, `name "Zulu"`.
2. M2 = machine, `name "apple"`.
3. M3 = machine, `name "Banana"`.

**When**
- `result = dao.get_by_factory(db, factory_id=F1.id, workspace_id=W1.id)`.

**Then**
1. returns: `names(result) == ["apple", "Banana", "Zulu"]`.

### MCH-GF-27 — names that differ only in case come back in id order
- **Rules:** `get_by_factory` R6 [BUG-343]
- **Kind:** bug
- **Expect:** xfail BUG-343 (non-strict)
- **Fails today on:** Then 1 (no ordering is requested; the database usually answers in insertion order [M1, M2, M3, M4] — non-strict xfail, the assertion is never weakened)
- **Author:** claude — non-strict xfail (`pytest.mark.xfail(strict=False, reason="BUG-343")`)

**Given**
1. M1 = machine, `name "bolt"`.
2. M2 = machine, `name "Zulu"`.
3. M3 = machine, `name "Bolt"`.
4. M4 = machine, `name "apple"`.

**When**
- `result = dao.get_by_factory(db, factory_id=F1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [M4.id, M1.id, M3.id, M2.id]`.

### MCH-GF-28 — a machine with an assignment and one without are each returned once
- **Rules:** `get_by_factory` R7
- **Kind:** happy
- **Expect:** pass

**Given**
1. M1 = machine, `name "Lathe"`.
2. assignment of M1 to S1.
3. M2 = machine, `name "Press"`.

**When**
- `result = dao.get_by_factory(db, factory_id=F1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 2`.
2. returns: `sorted(ids(result)) == [M1.id, M2.id]`.

### MCH-GF-29 — section id and name are readable on an assigned machine and None on an unassigned one
- **Rules:** `get_by_factory` R8
- **Kind:** happy
- **Expect:** pass

**Given**
1. M1 = machine, `name "Lathe"`.
2. assignment of M1 to S2.
3. M2 = machine, `name "Press"`.

**When**
- `result = dao.get_by_factory(db, factory_id=F1.id, workspace_id=W1.id)`.

**Then**
1. returns: `by_id(result, M1).factory_section_id == S2.id`.
2. returns: `by_id(result, M1).factory_section_name == "Section Two"`.
3. returns: `by_id(result, M2).factory_section_id is None`.
4. returns: `by_id(result, M2).factory_section_name is None`.

### MCH-GF-30 — once the factory is no longer deleted its machine is returned again, unchanged
- **Rules:** `get_by_factory` R3b
- **Kind:** soft-delete
- **Expect:** pass
- **Author:** claude — changes the standing row FD directly

**Given**
1. M1 = machine, `name "Lathe"`.
2. MD = machine, `name "Press"`, but `factory_id FD.id`, `is_running True`, `model_number "P-4"`. (FD is the soft-deleted factory; MD itself is live.)
3. AD = assignment of MD to S1.
4. FD made live again (Conventions). Nothing is done to MD or AD.

**When**
- `result = dao.get_by_factory(db, factory_id=FD.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [MD.id]`.
2. returns: `result[0].is_running is True`.
3. returns: `result[0].model_number == "P-4"`.
4. returns: `result[0].factory_section_id == S1.id`.
5. unchanged: unchanged(MD).
6. re-read MD: `is_deleted is False`, `is_active is True`.
7. re-read MD: `deleted_at is None`, `deleted_by is None`.
8. re-read MD: `updated_at is None`.
9. re-read AD: `machine_id == MD.id`, `factory_section_id == S1.id`.
10. nothing written: nothing written.

### MCH-GF-31 — a lookup leaves the section assignment of a soft-deleted factory's machine untouched
- **Rules:** `get_by_factory` R3b
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. M1 = machine, `name "Lathe"`.
2. MD = machine, `name "Press"`, but `factory_id FD.id`. (FD is the soft-deleted factory; MD itself is live.)
3. AD = assignment of MD to S1.

**When**
- `result = dao.get_by_factory(db, factory_id=F1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [M1.id]`.
2. unchanged: unchanged(AD).
3. re-read AD: `machine_id == MD.id`, `factory_section_id == S1.id`.
4. count: `machine_section_assignments` has exactly 1 row.


## `DAOMachine.get_by_section`

### MCH-GS-01 — returns a list of the machines assigned to that section, each once
- **Rules:** `get_by_section` R1, R6
- **Kind:** happy
- **Expect:** pass

**Given**
1. M1 = machine, `name "Lathe"`.
2. assignment of M1 to S1.
3. M2 = machine, `name "Press"`.
4. assignment of M2 to S1.
5. M3 = machine, `name "Drill"`.
6. assignment of M3 to S2.
7. M4 = machine, `name "Saw"`. (No assignment.)

**When**
- `result = dao.get_by_section(db, factory_section_id=S1.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `sorted(ids(result)) == [M1.id, M2.id]`.
3. returns: `len(result) == 2`.
4. returns: `isinstance(result[0], Machine)`.

### MCH-GS-02 — a call for the other section returns only that section's machine
- **Rules:** `get_by_section` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. M1 = machine, `name "Lathe"`.
2. assignment of M1 to S1.
3. M2 = machine, `name "Drill"`.
4. assignment of M2 to S2.
5. M3 = machine, `name "Saw"`. (No assignment.)

**When**
- `result = dao.get_by_section(db, factory_section_id=S2.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [M2.id]`.

### MCH-GS-03 — a section with no assigned machine returns an empty list
- **Rules:** `get_by_section` R3, R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1 = machine, `name "Saw"`. (No assignment.)
2. M2 = machine, `name "Drill"`.
3. assignment of M2 to S2.

**When**
- `result = dao.get_by_section(db, factory_section_id=S1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### MCH-GS-04 — a machine of another workspace assigned to this section is not returned
- **Rules:** `get_by_section` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. M1 = machine, `name "Lathe"`.
2. assignment of M1 to S1.
3. M9 = machine, `name "Other"`, but `workspace_id W2.id`, `factory_id F9.id`.
4. assignment of M9 to S1. (The other workspace's machine points at this workspace's section.)

**When**
- `result = dao.get_by_section(db, factory_section_id=S1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [M1.id]`.

### MCH-GS-05 — the workspace filter follows the machine, not the section
- **Rules:** `get_by_section` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. M1 = machine, `name "Lathe"`.
2. assignment of M1 to S1.
3. M9 = machine, `name "Other"`, but `workspace_id W2.id`, `factory_id F9.id`.
4. assignment of M9 to S1. (The other workspace's machine points at this workspace's section.)

**When**
- `result = dao.get_by_section(db, factory_section_id=S1.id, workspace_id=W2.id)`.

**Then**
1. returns: `ids(result) == [M9.id]`.

### MCH-GS-06 — an unknown workspace id returns an empty list
- **Rules:** `get_by_section` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1 = machine, `name "Lathe"`.
2. assignment of M1 to S1.

**When**
- `result = dao.get_by_section(db, factory_section_id=S1.id, workspace_id=MISSING)`.

**Then**
1. returns: `result == []`.

### MCH-GS-07 — a soft-deleted machine is not returned although its assignment still exists
- **Rules:** `get_by_section` R2
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. M1 = machine, `name "Lathe"`.
2. assignment of M1 to S1.
3. M2 = machine, `name "Press"`, but deleted.
4. assignment of M2 to S1.

**When**
- `result = dao.get_by_section(db, factory_section_id=S1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [M1.id]`.
2. count: `machine_section_assignments` has exactly 2 rows.

### MCH-GS-08 — an inactive live machine and a running machine are returned
- **Rules:** `get_by_section` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1 = machine, `name "Lathe"`, but `is_active False`. (Still `is_deleted False`.)
2. assignment of M1 to S1.
3. M2 = machine, `name "Press"`, but `is_running True`.
4. assignment of M2 to S1.

**When**
- `result = dao.get_by_section(db, factory_section_id=S1.id, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [M1.id, M2.id]`.

### MCH-GS-09 — a section id that does not exist returns an empty list
- **Rules:** `get_by_section` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1 = machine, `name "Lathe"`.
2. assignment of M1 to S1.

**When**
- `result = dao.get_by_section(db, factory_section_id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### MCH-GS-10 — factory_section_id 0 returns an empty list
- **Rules:** `get_by_section` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1 = machine, `name "Lathe"`.
2. assignment of M1 to S1.
3. M2 = machine, `name "Saw"`. (No assignment.)

**When**
- `result = dao.get_by_section(db, factory_section_id=0, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### MCH-GS-11 — a section whose only assigned machine is soft-deleted returns an empty list
- **Rules:** `get_by_section` R3, R2
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. M1 = machine, `name "Lathe"`, but deleted.
2. assignment of M1 to S1.
3. M2 = machine, `name "Drill"`.
4. assignment of M2 to S2.

**When**
- `result = dao.get_by_section(db, factory_section_id=S1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### MCH-GS-12 — a machine whose factory is soft-deleted is not returned
- **Rules:** `get_by_section` R3a [BUG-891]
- **Kind:** bug
- **Expect:** xfail BUG-891
- **Fails today on:** Then 3 (the factory row is never looked at, so MD comes back with M1)

**Given**
1. M1 = machine, `name "Lathe"`.
2. assignment of M1 to S1.
3. MD = machine, `name "Press"`, but `factory_id FD.id`. (FD is the soft-deleted factory; MD itself is live.)
4. assignment of MD to S1.

**When**
- `result = dao.get_by_section(db, factory_section_id=S1.id, workspace_id=W1.id)`.

**Then**
1. unchanged: unchanged(MD).
2. count: `machine_section_assignments` has exactly 2 rows.
3. returns: `ids(result) == [M1.id]`.

### MCH-GS-13 — a machine whose factory is live but inactive is returned
- **Rules:** `get_by_section` R3b
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1 = machine, `name "Lathe"`.
2. assignment of M1 to S1.
3. MI = machine, `name "Press"`, but `factory_id FI.id`. (FI is the live but inactive factory.)
4. assignment of MI to S1.

**When**
- `result = dao.get_by_section(db, factory_section_id=S1.id, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [M1.id, MI.id]`.

### MCH-GS-14 — a lookup leaves the machine of a soft-deleted factory and its assignment untouched
- **Rules:** `get_by_section` R3b, R1
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. M1 = machine, `name "Lathe"`.
2. assignment of M1 to S2.
3. MD = machine, `name "Press"`, but `factory_id FD.id`. (FD is the soft-deleted factory; MD itself is live.)
4. assignment of MD to S1.

**When**
- `result = dao.get_by_section(db, factory_section_id=S2.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [M1.id]`.
2. unchanged: unchanged(MD).
3. re-read MD: `is_deleted is False`, `is_active is True`.
4. nothing written: nothing written.
5. count: `machine_section_assignments` has exactly 2 rows.

### MCH-GS-15 — a soft-deleted section returns an empty list although an assignment still points at it
- **Rules:** `get_by_section` R4 [BUG-889]
- **Kind:** bug
- **Expect:** xfail BUG-889
- **Fails today on:** Then 2 (the section row is never looked at, so M1 comes back)

**Given**
1. M1 = machine, `name "Lathe"`.
2. assignment of M1 to SX. (SX is the soft-deleted section; a left-over assignment.)
3. M2 = machine, `name "Press"`.
4. assignment of M2 to S1.

**When**
- `result = dao.get_by_section(db, factory_section_id=SX.id, workspace_id=W1.id)`.

**Then**
1. count: `machine_section_assignments` has exactly 2 rows.
2. returns: `result == []`.

### MCH-GS-16 — a live but inactive section returns its machines and the assignment is not changed
- **Rules:** `get_by_section` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1 = machine, `name "Lathe"`.
2. assignment of M1 to SI. (SI is the live but inactive section.)
3. M2 = machine, `name "Press"`.
4. assignment of M2 to S1.

**When**
- `result = dao.get_by_section(db, factory_section_id=SI.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [M1.id]`.
2. count: `machine_section_assignments` has exactly 2 rows.
3. nothing written: nothing written.

### MCH-GS-17 — default limit returns exactly 100 of 101 assigned machines
- **Rules:** `get_by_section` R5
- **Kind:** boundary
- **Expect:** pass
- **Author:** claude — bulk setup (a loop over 101 machines and 101 assignments) outside the Conventions vocabulary

**Given**
1. 101 machines N1 … N101, inserted in that order; machine Nk (k = 1 … 101) has `name` = `f"M{k:03d}"` (so "M001" … "M101") and is otherwise the default machine.
2. For every Nk: assignment of Nk to S1.

**When**
- `result = dao.get_by_section(db, factory_section_id=S1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.
2. returns: `len(set(ids(result))) == 100`.
3. returns: `set(ids(result)) <= {N1.id, …, N101.id}` (the set of all 101 ids).

### MCH-GS-18 — a soft-deleted machine does not use up a place in the page
- **Rules:** `get_by_section` R5, R2
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. M1 = machine, `name "Lathe"`.
2. assignment of M1 to S1.
3. M2 = machine, `name "Mill"`, but deleted.
4. assignment of M2 to S1.
5. M3 = machine, `name "Press"`.
6. assignment of M3 to S1.

**When**
- `result = dao.get_by_section(db, factory_section_id=S1.id, workspace_id=W1.id, limit=2)`.

**Then**
1. returns: `sorted(ids(result)) == [M1.id, M3.id]`.

### MCH-GS-19 — limit 2 of three assigned machines returns two different machines
- **Rules:** `get_by_section` R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. M1 = machine, `name "Lathe"`.
2. assignment of M1 to S1.
3. M2 = machine, `name "Mill"`.
4. assignment of M2 to S1.
5. M3 = machine, `name "Press"`.
6. assignment of M3 to S1.

**When**
- `result = dao.get_by_section(db, factory_section_id=S1.id, workspace_id=W1.id, skip=0, limit=2)`.

**Then**
1. returns: `len(result) == 2`.
2. returns: `len(set(ids(result))) == 2`.
3. returns: `set(ids(result)) <= {M1.id, M2.id, M3.id}`.

### MCH-GS-20 — the last window is short
- **Rules:** `get_by_section` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1 = machine, `name "Lathe"`.
2. assignment of M1 to S1.
3. M2 = machine, `name "Mill"`.
4. assignment of M2 to S1.
5. M3 = machine, `name "Press"`.
6. assignment of M3 to S1.

**When**
- `result = dao.get_by_section(db, factory_section_id=S1.id, workspace_id=W1.id, skip=2, limit=2)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `result[0].id in [M1.id, M2.id, M3.id]`.

### MCH-GS-21 — a middle window holds the machine that is second by name
- **Rules:** `get_by_section` R5, R7 [BUG-343]
- **Kind:** bug
- **Expect:** xfail BUG-343 (non-strict)
- **Fails today on:** Then 1 (no ordering is requested; the database usually answers in insertion order, giving ["apple"], but may happen to give this order — non-strict xfail, the assertion is never weakened)
- **Author:** claude — non-strict xfail (`pytest.mark.xfail(strict=False, reason="BUG-343")`)

**Given**
1. M1 = machine, `name "Zulu"`.
2. assignment of M1 to S1.
3. M2 = machine, `name "apple"`.
4. assignment of M2 to S1.
5. M3 = machine, `name "Mango"`.
6. assignment of M3 to S1.

**When**
- `result = dao.get_by_section(db, factory_section_id=S1.id, workspace_id=W1.id, skip=1, limit=1)`.

**Then**
1. returns: `names(result) == ["Mango"]`.

### MCH-GS-22 — limit 0 returns an empty list
- **Rules:** `get_by_section` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1 = machine, `name "Lathe"`.
2. assignment of M1 to S1.

**When**
- `result = dao.get_by_section(db, factory_section_id=S1.id, workspace_id=W1.id, limit=0)`.

**Then**
1. returns: `result == []`.

### MCH-GS-23 — skip equal to the number of assigned machines returns an empty list
- **Rules:** `get_by_section` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1 = machine, `name "Lathe"`.
2. assignment of M1 to S1.
3. M2 = machine, `name "Press"`.
4. assignment of M2 to S1.

**When**
- `result = dao.get_by_section(db, factory_section_id=S1.id, workspace_id=W1.id, skip=2)`.

**Then**
1. returns: `result == []`.

### MCH-GS-24 — skip one below the number of assigned machines returns one machine
- **Rules:** `get_by_section` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1 = machine, `name "Lathe"`.
2. assignment of M1 to S1.
3. M2 = machine, `name "Press"`.
4. assignment of M2 to S1.

**When**
- `result = dao.get_by_section(db, factory_section_id=S1.id, workspace_id=W1.id, skip=1)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `result[0].id in [M1.id, M2.id]`.

### MCH-GS-25 — negative limit is rejected by the database and nothing changes
- **Rules:** `get_by_section` R5, Errors (negative `limit`, as `get_by_factory`)
- **Kind:** error
- **Expect:** pass

**Given**
1. M1 = machine, `name "Lathe"`.
2. assignment of M1 to S1.

**When**
- `dao.get_by_section(db, factory_section_id=S1.id, workspace_id=W1.id, limit=-1)`.

**Then**
1. raises: `DataError`.
2. raises: `isinstance(exc.value.orig, InvalidRowCountInLimitClause)`.
3. raises: `exc.value.orig.pgcode == "2201W"`.
4. raises: `"LIMIT must not be negative" in str(exc.value.orig)`.
5. nothing written: nothing written.
6. unchanged: unchanged(M1).

### MCH-GS-26 — negative skip is rejected by the database and nothing changes
- **Rules:** `get_by_section` R5, Errors (negative `skip`, as `get_by_factory`)
- **Kind:** error
- **Expect:** pass

**Given**
1. M1 = machine, `name "Lathe"`.
2. assignment of M1 to S1.

**When**
- `dao.get_by_section(db, factory_section_id=S1.id, workspace_id=W1.id, skip=-1)`.

**Then**
1. raises: `DataError`.
2. raises: `isinstance(exc.value.orig, InvalidRowCountInResultOffsetClause)`.
3. raises: `exc.value.orig.pgcode == "2201X"`.
4. raises: `"OFFSET must not be negative" in str(exc.value.orig)`.
5. nothing written: nothing written.
6. unchanged: unchanged(M1).

### MCH-GS-27 — machines come back by name, case-insensitive ascending
- **Rules:** `get_by_section` R7 [BUG-343]
- **Kind:** bug
- **Expect:** xfail BUG-343 (non-strict)
- **Fails today on:** Then 1 (no ordering is requested; the database usually answers in insertion order ["Zulu", "apple", "Banana"], but may happen to give this order — non-strict xfail, the assertion is never weakened)
- **Author:** claude — non-strict xfail (`pytest.mark.xfail(strict=False, reason="BUG-343")`)

**Given**
1. M1 = machine, `name "Zulu"`.
2. assignment of M1 to S1.
3. M2 = machine, `name "apple"`.
4. assignment of M2 to S1.
5. M3 = machine, `name "Banana"`.
6. assignment of M3 to S1.

**When**
- `result = dao.get_by_section(db, factory_section_id=S1.id, workspace_id=W1.id)`.

**Then**
1. returns: `names(result) == ["apple", "Banana", "Zulu"]`.

### MCH-GS-28 — names that differ only in case come back in id order
- **Rules:** `get_by_section` R7 [BUG-343]
- **Kind:** bug
- **Expect:** xfail BUG-343 (non-strict)
- **Fails today on:** Then 1 (no ordering is requested; the database usually answers in insertion order [M1, M2, M3, M4] — non-strict xfail, the assertion is never weakened)
- **Author:** claude — non-strict xfail (`pytest.mark.xfail(strict=False, reason="BUG-343")`)

**Given**
1. M1 = machine, `name "bolt"`.
2. assignment of M1 to S1.
3. M2 = machine, `name "Zulu"`.
4. assignment of M2 to S1.
5. M3 = machine, `name "Bolt"`.
6. assignment of M3 to S1.
7. M4 = machine, `name "apple"`.
8. assignment of M4 to S1.

**When**
- `result = dao.get_by_section(db, factory_section_id=S1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [M4.id, M1.id, M3.id, M2.id]`.

### MCH-GS-29 — every returned machine reports the section it was found through
- **Rules:** `get_by_section` R8
- **Kind:** happy
- **Expect:** pass

**Given**
1. M1 = machine, `name "Lathe"`.
2. assignment of M1 to S2.
3. M2 = machine, `name "Press"`.
4. assignment of M2 to S2.
5. M3 = machine, `name "Drill"`.
6. assignment of M3 to S1.

**When**
- `result = dao.get_by_section(db, factory_section_id=S2.id, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [M1.id, M2.id]`.
2. returns: `by_id(result, M1).factory_section_id == S2.id`.
3. returns: `by_id(result, M1).factory_section_name == "Section Two"`.
4. returns: `by_id(result, M2).factory_section_id == S2.id`.
5. returns: `by_id(result, M2).factory_section_name == "Section Two"`.

### MCH-GS-30 — once the factory is no longer deleted its machine is returned again, still assigned to the same section
- **Rules:** `get_by_section` R3b
- **Kind:** soft-delete
- **Expect:** pass
- **Author:** claude — changes the standing row FD directly

**Given**
1. M1 = machine, `name "Lathe"`.
2. assignment of M1 to S1.
3. MD = machine, `name "Press"`, but `factory_id FD.id`, `is_running True`, `model_number "P-4"`. (FD is the soft-deleted factory; MD itself is live.)
4. AD = assignment of MD to S1.
5. FD made live again (Conventions). Nothing is done to MD or AD.

**When**
- `result = dao.get_by_section(db, factory_section_id=S1.id, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [M1.id, MD.id]`.
2. returns: `by_id(result, MD).factory_section_id == S1.id`.
3. returns: `by_id(result, MD).factory_section_name == "Section One"`.
4. returns: `by_id(result, MD).is_running is True`.
5. unchanged: unchanged(MD).
6. re-read MD: `is_deleted is False`, `is_active is True`.
7. re-read MD: `model_number == "P-4"`, `updated_at is None`.
8. unchanged: unchanged(AD).
9. re-read AD: `machine_id == MD.id`, `factory_section_id == S1.id`.
10. count: `machine_section_assignments` has exactly 2 rows.

### MCH-GS-31 — a lookup leaves the assignment row of a soft-deleted factory's machine as it was
- **Rules:** `get_by_section` R3b
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. M1 = machine, `name "Lathe"`.
2. assignment of M1 to S2.
3. MD = machine, `name "Press"`, but `factory_id FD.id`. (FD is the soft-deleted factory; MD itself is live.)
4. AD = assignment of MD to S1.

**When**
- `result = dao.get_by_section(db, factory_section_id=S2.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [M1.id]`.
2. unchanged: unchanged(AD).
3. re-read AD: `machine_id == MD.id`, `factory_section_id == S1.id`.
4. count: `machine_section_assignments` has exactly 2 rows.


## `DAOMachine.soft_delete`

### MCH-SD-01 — a live machine is marked deleted with the clock value and the acting user
- **Rules:** `soft_delete` R1, R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. M1 = machine, `name "Press 4"`.

**When**
- `result = dao.soft_delete(db, db_obj=M1, deleted_by=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was passed in).
2. re-read M1: `is_deleted is True`, `is_active is False`.
3. re-read M1: `deleted_at == NOW`.
4. re-read M1: `deleted_by == U2.id`.
5. count: `machines` has exactly 1 row.

### MCH-SD-02 — no other column of the machine is changed and a running machine stays running
- **Rules:** `soft_delete` R2
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. M1 = machine, `name "Press 4"`, but `factory_id F2.id`, `model_number "MX-1"`, `manufacturer "Siemens"`, `note "n1"`, `is_running True`, `updated_by U1.id`, `created_at T1`.

**When**
- `result = dao.soft_delete(db, db_obj=M1, deleted_by=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was passed in).
2. re-read M1: `name == "Press 4"`, `factory_id == F2.id`, `workspace_id == W1.id`.
3. re-read M1: `model_number == "MX-1"`, `manufacturer == "Siemens"`, `note == "n1"`.
4. re-read M1: `created_by == U1.id`, `updated_by == U1.id`.
5. re-read M1: `created_at == T1`.
6. re-read M1: `is_running is True`.
7. re-read M1: `updated_at is not None`.
8. re-read M1: `is_deleted is True`.

### MCH-SD-03 — updated_by is not stamped and a stopped machine stays stopped
- **Rules:** `soft_delete` R2
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. M1 = machine, `name "Press 4"`. (`updated_by None`, `is_running False`, all optional texts None.)

**When**
- `result = dao.soft_delete(db, db_obj=M1, deleted_by=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was passed in).
2. re-read M1: `updated_by is None`.
3. re-read M1: `is_running is False`.
4. re-read M1: `model_number is None`, `manufacturer is None`, `note is None`.
5. re-read M1: `created_by == U1.id`.
6. re-read M1: `is_deleted is True`.

### MCH-SD-04 — the section assignment row is kept
- **Rules:** `soft_delete` R3
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. M1 = machine, `name "Press 4"`.
2. A1 = assignment of M1 to S1.

**When**
- `result = dao.soft_delete(db, db_obj=M1, deleted_by=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was passed in).
2. returns: `result.factory_section_id == S1.id`.
3. count: `machine_section_assignments` has exactly 1 row.
4. re-read A1: `machine_id == M1.id`, `factory_section_id == S1.id`.
5. re-read M1: `is_deleted is True`.
6. re-read M1: `factory_section_id == S1.id`.

### MCH-SD-05 — an already deleted machine gets a new deletion stamp without an error
- **Rules:** `soft_delete` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1 = machine, `name "Press 4"`, but deleted. (`deleted_at T0`, `deleted_by U1.id`.)

**When**
- `result = dao.soft_delete(db, db_obj=M1, deleted_by=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was passed in).
2. re-read M1: `deleted_at == NOW`.
3. re-read M1: `deleted_by == U2.id`.
4. re-read M1: `is_deleted is True`, `is_active is False`.

### MCH-SD-06 — after the delete the machine is gone from the three lists in the same session
- **Rules:** `soft_delete` R5
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. M1 = machine, `name "Lathe"`.
2. assignment of M1 to S1.
3. M2 = machine, `name "Press"`.
4. assignment of M2 to S1.

**When**
- `result = dao.soft_delete(db, db_obj=M1, deleted_by=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was passed in).
2. returns: after the call, `ids(dao.get_by_factory(db, factory_id=F1.id, workspace_id=W1.id)) == [M2.id]`.
3. returns: after the call, `ids(dao.get_by_section(db, factory_section_id=S1.id, workspace_id=W1.id)) == [M2.id]`.
4. returns: after the call, `ids(dao.search_advanced(db, workspace_id=W1.id)) == [M2.id]`.

### MCH-SD-07 — after the delete the machine is still found by the raw id lookup
- **Rules:** `soft_delete` R5
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. M1 = machine, `name "Lathe"`.

**When**
- `result = dao.soft_delete(db, db_obj=M1, deleted_by=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was passed in).
2. returns: after the call, `dao.get_by_id_and_workspace(db, id=M1.id, workspace_id=W1.id).id == M1.id`.
3. returns: after the call, `dao.get_by_id_and_workspace(db, id=M1.id, workspace_id=W1.id).is_deleted is True`.

### MCH-SD-08 — the delete is flushed but not committed: a rollback makes the machine live again
- **Rules:** `soft_delete` R5
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude — savepoint rollback and a commit spy

**Given**
1. M1 = machine, `name "Lathe"`.
2. Savepoint and commit spy per **rolled back** (Conventions).

**When**
- `result = dao.soft_delete(db, db_obj=M1, deleted_by=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was passed in).
2. re-read M1: `is_deleted is True`.
3. re-read M1 after the savepoint rollback: `is_deleted is False`, `is_active is True`.
4. re-read M1 after the savepoint rollback: `deleted_at is None`, `deleted_by is None`.
5. mock called: the `db.commit` spy was never called.

### MCH-SD-09 — a machine of another workspace is deleted all the same
- **Rules:** `soft_delete` R6
- **Kind:** isolation
- **Expect:** pass

**Given**
1. M9 = machine, `name "Other"`, but `workspace_id W2.id`, `factory_id F9.id`.

**When**
- `result = dao.soft_delete(db, db_obj=M9, deleted_by=U2.id)`.

**Then**
1. returns: `result is M9` (the very object that was passed in).
2. re-read M9: `is_deleted is True`, `is_active is False`.
3. re-read M9: `deleted_at == NOW`, `deleted_by == U2.id`.
4. re-read M9: `workspace_id == W2.id`.

### MCH-SD-10 — a deleted_by that is no profile id fails on flush and nothing is saved
- **Rules:** `soft_delete` R7, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. M1 = machine, `name "Press 4"`.

**When**
- `dao.soft_delete(db, db_obj=M1, deleted_by=MISSING)`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `isinstance(exc.value.orig, ForeignKeyViolation)`.
3. unchanged: unchanged(M1).
4. re-read M1: `is_deleted is False`, `is_active is True`.
5. re-read M1: `deleted_at is None`, `deleted_by is None`.
6. re-read M1: `updated_at is None`.
7. nothing written: nothing written.

### MCH-SD-11 — deleted_by None is stored as NULL
- **Rules:** `soft_delete` R1 (Inputs: `deleted_by`)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1 = machine, `name "Press 4"`.

**When**
- `result = dao.soft_delete(db, db_obj=M1, deleted_by=None)`.

**Then**
1. returns: `result is M1` (the very object that was passed in).
2. re-read M1: `deleted_by is None`.
3. re-read M1: `is_deleted is True`, `is_active is False`.
4. re-read M1: `deleted_at == NOW`.

### MCH-SD-12 — only that machine row is touched and no activity event is written
- **Rules:** `soft_delete` Side effects, R2
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. M1 = machine, `name "Lathe"`.
2. M2 = machine, `name "Press"`.

**When**
- `result = dao.soft_delete(db, db_obj=M1, deleted_by=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was passed in).
2. re-read M1: `is_deleted is True`.
3. unchanged: unchanged(M2).
4. re-read M2: `is_deleted is False`, `updated_at is None`.
5. nothing written: nothing written.
6. count: `machines` has exactly 2 rows.
7. count: `machine_activity_events` has exactly 0 rows.

### MCH-SD-13 — an inactive live machine is deleted like any other
- **Rules:** `soft_delete` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1 = machine, `name "Press 4"`, but `is_active False`. (Still `is_deleted False`.)

**When**
- `result = dao.soft_delete(db, db_obj=M1, deleted_by=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was passed in).
2. re-read M1: `is_deleted is True`, `is_active is False`.
3. re-read M1: `deleted_at == NOW`, `deleted_by == U2.id`.


## `DAOMachine.restore`

### MCH-RS-01 — a deleted machine is made live again and its deletion stamp is cleared
- **Rules:** `restore` R1, R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. M1 = machine, `name "Press 4"`, but deleted. (`deleted_at T0`, `deleted_by U1.id`.)

**When**
- `result = dao.restore(db, db_obj=M1)`.

**Then**
1. returns: `result is M1` (the very object that was passed in).
2. re-read M1: `is_deleted is False`, `is_active is True`.
3. re-read M1: `deleted_at is None`.
4. re-read M1: `deleted_by is None`.
5. count: `machines` has exactly 1 row.

### MCH-RS-02 — no other column of the machine is changed and a running machine comes back running
- **Rules:** `restore` R2
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. M1 = machine, `name "Press 4"`, but `factory_id F2.id`, `model_number "MX-1"`, `manufacturer "Siemens"`, `note "n1"`, `is_running True`, `created_at T1`, deleted.

**When**
- `result = dao.restore(db, db_obj=M1)`.

**Then**
1. returns: `result is M1` (the very object that was passed in).
2. re-read M1: `name == "Press 4"`, `factory_id == F2.id`, `workspace_id == W1.id`.
3. re-read M1: `model_number == "MX-1"`, `manufacturer == "Siemens"`, `note == "n1"`.
4. re-read M1: `created_by == U1.id`.
5. re-read M1: `created_at == T1`.
6. re-read M1: `is_running is True`.
7. re-read M1: `updated_at is not None`.
8. re-read M1: `is_deleted is False`.

### MCH-RS-03 — a stopped machine comes back stopped and its empty texts stay empty
- **Rules:** `restore` R2
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. M1 = machine, `name "Press 4"`, but deleted. (`is_running False`, all optional texts None.)

**When**
- `result = dao.restore(db, db_obj=M1)`.

**Then**
1. returns: `result is M1` (the very object that was passed in).
2. re-read M1: `is_running is False`.
3. re-read M1: `model_number is None`, `manufacturer is None`, `note is None`.
4. re-read M1: `name == "Press 4"`, `factory_id == F1.id`, `workspace_id == W1.id`.
5. re-read M1: `created_by == U1.id`.
6. re-read M1: `is_deleted is False`.

### MCH-RS-04 — updated_by keeps the value it had
- **Rules:** `restore` R2a (Q8)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. M1 = machine, `name "Press 4"`, but `updated_by U2.id`, deleted. (`deleted_by U1.id`.)

**When**
- `result = dao.restore(db, db_obj=M1)`.

**Then**
1. returns: `result is M1` (the very object that was passed in).
2. re-read M1: `updated_by == U2.id`.
3. re-read M1: `is_deleted is False`.

### MCH-RS-05 — an empty updated_by stays empty: nobody is recorded as having restored
- **Rules:** `restore` R2a (Q8)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. M1 = machine, `name "Press 4"`, but deleted. (`updated_by None`, `deleted_by U1.id`.)

**When**
- `result = dao.restore(db, db_obj=M1)`.

**Then**
1. returns: `result is M1` (the very object that was passed in).
2. re-read M1: `updated_by is None`.
3. re-read M1: `is_deleted is False`.

### MCH-RS-06 — no activity entry is written and no other table is touched
- **Rules:** `restore` R2a (Q8), Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. M1 = machine, `name "Press 4"`, but deleted.
2. event of M1, `created_at T0`, `metadata_json None`, but `event_type "deactivated"`.

**When**
- `result = dao.restore(db, db_obj=M1)`.

**Then**
1. returns: `result is M1` (the very object that was passed in).
2. re-read M1: `is_deleted is False`.
3. count: `machine_activity_events` has exactly 1 row.
4. nothing written: nothing written.
5. count: `machines` has exactly 1 row.

### MCH-RS-07 — the section assignment of the restored machine is the same row as before
- **Rules:** `restore` R3
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. M1 = machine, `name "Press 4"`, but deleted.
2. A1 = assignment of M1 to S1.

**When**
- `result = dao.restore(db, db_obj=M1)`.

**Then**
1. returns: `result is M1` (the very object that was passed in).
2. returns: `result.factory_section_id == S1.id`.
3. unchanged: unchanged(A1).
4. re-read A1: `machine_id == M1.id`, `factory_section_id == S1.id`.
5. count: `machine_section_assignments` has exactly 1 row.
6. re-read M1: `is_deleted is False`.
7. re-read M1: `factory_section_id == S1.id`.

### MCH-RS-08 — a machine without an assignment still has none after the restore
- **Rules:** `restore` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1 = machine, `name "Press 4"`, but deleted. (No assignment.)
2. M2 = machine, `name "Lathe"`.
3. assignment of M2 to S1.

**When**
- `result = dao.restore(db, db_obj=M1)`.

**Then**
1. returns: `result is M1` (the very object that was passed in).
2. returns: `result.factory_section_id is None`.
3. count: `machine_section_assignments` has exactly 1 row.
4. re-read M1: `is_deleted is False`.
5. re-read M1: `factory_section_id is None`.

### MCH-RS-09 — a machine that is already live and active is left exactly as it is, with no UPDATE
- **Rules:** `restore` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1 = machine, `name "Press 4"`. (Live and active; `updated_at None`.)

**When**
- `result = dao.restore(db, db_obj=M1)`.

**Then**
1. returns: `result is M1` (the very object that was passed in).
2. unchanged: unchanged(M1).
3. re-read M1: `updated_at is None`.
4. re-read M1: `is_deleted is False`, `is_active is True`.
5. re-read M1: `deleted_at is None`, `deleted_by is None`.
6. count: `machines` has exactly 1 row.

### MCH-RS-10 — a live but inactive machine is made active and stays not deleted
- **Rules:** `restore` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1 = machine, `name "Press 4"`, but `is_active False`. (Still `is_deleted False`, no deletion stamp.)

**When**
- `result = dao.restore(db, db_obj=M1)`.

**Then**
1. returns: `result is M1` (the very object that was passed in).
2. re-read M1: `is_active is True`.
3. re-read M1: `is_deleted is False`.
4. re-read M1: `deleted_at is None`, `deleted_by is None`.
5. re-read M1: `updated_at is not None`.

### MCH-RS-11 — after the restore the machine is back in the three lists in the same session
- **Rules:** `restore` R5
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. M1 = machine, `name "Lathe"`, but deleted.
2. assignment of M1 to S1.
3. M2 = machine, `name "Press"`.
4. assignment of M2 to S1.

**When**
- `result = dao.restore(db, db_obj=M1)`.

**Then**
1. returns: `result is M1` (the very object that was passed in).
2. returns: after the call, `sorted(ids(dao.get_by_factory(db, factory_id=F1.id, workspace_id=W1.id))) == [M1.id, M2.id]`.
3. returns: after the call, `sorted(ids(dao.get_by_section(db, factory_section_id=S1.id, workspace_id=W1.id))) == [M1.id, M2.id]`.
4. returns: after the call, `ids(dao.search_advanced(db, workspace_id=W1.id)) == [M1.id, M2.id]`.

### MCH-RS-12 — the restore is flushed but not committed: a rollback makes the machine deleted again
- **Rules:** `restore` R5
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude — savepoint rollback and a commit spy

**Given**
1. M1 = machine, `name "Lathe"`, but deleted. (`deleted_at T0`, `deleted_by U1.id`.)
2. Savepoint and commit spy per **rolled back** (Conventions).

**When**
- `result = dao.restore(db, db_obj=M1)`.

**Then**
1. returns: `result is M1` (the very object that was passed in).
2. re-read M1: `is_deleted is False`, `is_active is True`.
3. re-read M1 after the savepoint rollback: `is_deleted is True`, `is_active is False`.
4. re-read M1 after the savepoint rollback: `deleted_at == T0`.
5. re-read M1 after the savepoint rollback: `deleted_by == U1.id`.
6. mock called: the `db.commit` spy was never called.

### MCH-RS-13 — a machine of another workspace is restored all the same
- **Rules:** `restore` R6
- **Kind:** isolation
- **Expect:** pass

**Given**
1. M9 = machine, `name "Other"`, but `workspace_id W2.id`, `factory_id F9.id`, deleted.

**When**
- `result = dao.restore(db, db_obj=M9)`.

**Then**
1. returns: `result is M9` (the very object that was passed in).
2. re-read M9: `is_deleted is False`, `is_active is True`.
3. re-read M9: `deleted_at is None`, `deleted_by is None`.
4. re-read M9: `workspace_id == W2.id`, `factory_id == F9.id`.

### MCH-RS-14 — a second deleted machine of the same factory stays deleted
- **Rules:** `restore` R6
- **Kind:** isolation
- **Expect:** pass

**Given**
1. M1 = machine, `name "Lathe"`, but deleted.
2. M2 = machine, `name "Press"`, but deleted. (Same factory F1; `deleted_at T0`, `deleted_by U1.id`.)

**When**
- `result = dao.restore(db, db_obj=M1)`.

**Then**
1. returns: `result is M1` (the very object that was passed in).
2. re-read M1: `is_deleted is False`.
3. unchanged: unchanged(M2).
4. re-read M2: `is_deleted is True`, `is_active is False`.
5. re-read M2: `deleted_at == T0`, `deleted_by == U1.id`.
6. re-read M2: `updated_at is None`.
7. count: `machines` has exactly 2 rows.

### MCH-RS-15 — a deleted machine of another factory and a live machine are not touched
- **Rules:** `restore` R6
- **Kind:** isolation
- **Expect:** pass

**Given**
1. M1 = machine, `name "Lathe"`, but deleted.
2. M3 = machine, `name "Drill"`, but `factory_id F2.id`, deleted.
3. M4 = machine, `name "Saw"`. (Live, same factory F1.)

**When**
- `result = dao.restore(db, db_obj=M1)`.

**Then**
1. returns: `result is M1` (the very object that was passed in).
2. re-read M1: `is_deleted is False`.
3. unchanged: unchanged(M3).
4. re-read M3: `is_deleted is True`, `is_active is False`.
5. unchanged: unchanged(M4).
6. re-read M4: `is_deleted is False`, `updated_at is None`.
7. count: `machines` has exactly 3 rows.

### MCH-RS-16 — a deleted machine of a soft-deleted factory is restored and the factory row is not touched
- **Rules:** `restore` R7
- **Kind:** soft-delete
- **Expect:** pass
- **Author:** claude — changes the standing row FD directly (gives it a deletion stamp) and re-reads it

**Given**
1. FD is given a deletion stamp directly on its row: `FD.deleted_at = T0`, `FD.deleted_by = U1.id`, then `db.flush()`. (`is_deleted` stays True.)
2. MD = machine, `name "Press"`, but `factory_id FD.id`, deleted.

**When**
- `result = dao.restore(db, db_obj=MD)`.

**Then**
1. returns: `result is MD` (the very object that was passed in).
2. re-read MD: `is_deleted is False`, `is_active is True`.
3. re-read MD: `deleted_at is None`, `deleted_by is None`.
4. re-read MD: `factory_id == FD.id`.
5. unchanged: unchanged(FD).
6. re-read FD: `is_deleted is True`.
7. re-read FD: `deleted_at == T0`, `deleted_by == U1.id`.
8. count: `factories` has exactly 5 rows.

### MCH-RS-17 — a machine restored inside a soft-deleted factory stays hidden from the machine search
- **Rules:** `restore` R7a [BUG-890]
- **Kind:** bug
- **Expect:** xfail BUG-890
- **Fails today on:** Then 3 (the factory row is never looked at, so "Press" is listed right after the restore)

**Given**
1. M1 = machine, `name "Lathe"`.
2. MD = machine, `name "Press"`, but `factory_id FD.id`, deleted. (FD is the soft-deleted factory.)

**When**
- `result = dao.restore(db, db_obj=MD)`.

**Then**
1. returns: `result is MD` (the very object that was passed in).
2. re-read MD: `is_deleted is False`.
3. returns: after the call, `names(dao.search_advanced(db, workspace_id=W1.id)) == ["Lathe"]`.
4. returns: after the call, `dao.search_advanced(db, workspace_id=W1.id, factory_id=FD.id) == []`.

### MCH-RS-18 — a machine restored inside a soft-deleted factory stays hidden from the factory and section lookups
- **Rules:** `restore` R7a [BUG-891]
- **Kind:** bug
- **Expect:** xfail BUG-891
- **Fails today on:** Then 3 (the factory row is never looked at, so MD comes back right after the restore)

**Given**
1. M1 = machine, `name "Lathe"`.
2. assignment of M1 to S1.
3. MD = machine, `name "Press"`, but `factory_id FD.id`, deleted. (FD is the soft-deleted factory.)
4. assignment of MD to S1.

**When**
- `result = dao.restore(db, db_obj=MD)`.

**Then**
1. returns: `result is MD` (the very object that was passed in).
2. re-read MD: `is_deleted is False`.
3. returns: after the call, `dao.get_by_factory(db, factory_id=FD.id, workspace_id=W1.id) == []`.
4. returns: after the call, `ids(dao.get_by_section(db, factory_section_id=S1.id, workspace_id=W1.id)) == [M1.id]`.

### MCH-RS-19 — the restored machine appears in the three lists once its factory is no longer deleted
- **Rules:** `restore` R7a (second sentence — holds today), R7
- **Kind:** soft-delete
- **Expect:** pass
- **Author:** claude — a step between the call and the checks (FD made live again), and a snapshot taken after the call

**Given**
1. M1 = machine, `name "Lathe"`.
2. assignment of M1 to S1.
3. MD = machine, `name "Press"`, but `factory_id FD.id`, deleted. (FD is the soft-deleted factory.)
4. assignment of MD to S1.

**When**
- `result = dao.restore(db, db_obj=MD)`.

**Then**
1. returns: `result is MD` (the very object that was passed in).
2. re-read MD: `is_deleted is False`, `is_active is True`. Directly after this line take AFTER = every column of MD, then do the step **FD made live again** (Conventions).
3. re-read FD: `is_deleted is False`.
4. returns: after that step, `ids(dao.search_advanced(db, workspace_id=W1.id)) == [M1.id, MD.id]`.
5. returns: after that step, `ids(dao.get_by_factory(db, factory_id=FD.id, workspace_id=W1.id)) == [MD.id]`.
6. returns: after that step, `sorted(ids(dao.get_by_section(db, factory_section_id=S1.id, workspace_id=W1.id))) == [M1.id, MD.id]`.
7. unchanged: after the three list calls, every column of MD (re-read) equals AFTER — nothing further was done to the machine.

### MCH-RS-20 — delete then restore gives back the same value in every column except updated_at
- **Rules:** `restore` R8, `soft_delete` R5
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude — a Given step that runs `dao.soft_delete`, and a snapshot taken before it

**Given**
1. M1 = machine, `name "Press 4"`, but `factory_id F2.id`, `model_number "MX-1"`, `manufacturer "Siemens"`, `note "n1"`, `is_running True`, `updated_by U1.id`, `created_at T1`. (Live and active.)
2. BEFORE = every column of M1, taken now.
3. M1 is soft-deleted through the DAO: `dao.soft_delete(db, db_obj=M1, deleted_by=U2.id)`. (The one Given step in this file that uses `dao`.)

**When**
- `result = dao.restore(db, db_obj=M1)`.

**Then**
1. returns: `result is M1` (the very object that was passed in).
2. unchanged: after re-read, every column of M1 except `updated_at` equals its value in BEFORE.
3. re-read M1: `name == "Press 4"`, `factory_id == F2.id`, `workspace_id == W1.id`.
4. re-read M1: `created_by == U1.id`, `updated_by == U1.id`.
5. re-read M1: `model_number == "MX-1"`, `manufacturer == "Siemens"`, `note == "n1"`.
6. re-read M1: `is_running is True`, `created_at == T1`.
7. re-read M1: `is_deleted is False`, `is_active is True`.
8. re-read M1: `deleted_at is None`, `deleted_by is None`.
9. re-read M1: `updated_at is not None`.

### MCH-RS-21 — delete then restore keeps the same assignment row and the machine is listed again where it was
- **Rules:** `restore` R8, `soft_delete` R5
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude — a Given step that runs `dao.soft_delete`, and a snapshot taken before it

**Given**
1. M1 = machine, `name "Lathe"`.
2. A1 = assignment of M1 to S1.
3. M2 = machine, `name "Press"`.
4. assignment of M2 to S1.
5. BEFORE_A1 = every column of A1, taken now.
6. M1 is soft-deleted through the DAO: `dao.soft_delete(db, db_obj=M1, deleted_by=U2.id)`.

**When**
- `result = dao.restore(db, db_obj=M1)`.

**Then**
1. returns: `result is M1` (the very object that was passed in).
2. returns: `result.factory_section_id == S1.id`.
3. unchanged: after re-read, every column of A1 equals its value in BEFORE_A1.
4. re-read A1: `machine_id == M1.id`, `factory_section_id == S1.id`.
5. count: `machine_section_assignments` has exactly 2 rows.
6. returns: after the call, `sorted(ids(dao.get_by_factory(db, factory_id=F1.id, workspace_id=W1.id))) == [M1.id, M2.id]`.
7. returns: after the call, `sorted(ids(dao.get_by_section(db, factory_section_id=S1.id, workspace_id=W1.id))) == [M1.id, M2.id]`.
8. returns: after the call, `ids(dao.search_advanced(db, workspace_id=W1.id)) == [M1.id, M2.id]`.

### MCH-RS-22 — a machine is restored although another live machine of the factory now has its name
- **Rules:** `restore` R9 (Q9)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1 = machine, `name "Press 4"`, but deleted.
2. M2 = machine, `name "Press 4"`. (Live, same factory F1, the same name.)

**When**
- `result = dao.restore(db, db_obj=M1)`.

**Then**
1. returns: `result is M1` (the very object that was passed in).
2. re-read M1: `is_deleted is False`, `is_active is True`.
3. re-read M1: `name == "Press 4"`.
4. unchanged: unchanged(M2).
5. re-read M2: `name == "Press 4"`, `is_deleted is False`.
6. re-read M2: `updated_at is None`.
7. returns: after the call, `sorted(ids(dao.get_by_factory(db, factory_id=F1.id, workspace_id=W1.id))) == [M1.id, M2.id]`.
8. count: `machines` has exactly 2 rows.


## `DAOMachine.search_advanced`

### MCH-SA-01 — with no filter, returns a list of the workspace's live machines by name ascending
- **Rules:** `search_advanced` R3, R13, R15
- **Kind:** happy
- **Expect:** pass

**Given**
1. M1 = machine, `name "Press"`.
2. M2 = machine, `name "Drill"`.
3. M3 = machine, `name "Lathe"`.

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `ids(result) == [M2.id, M3.id, M1.id]`.
3. returns: `isinstance(result[0], Machine)`.

### MCH-SA-02 — a machine of another workspace is not returned
- **Rules:** `search_advanced` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. M1 = machine, `name "Lathe"`.
2. M9 = machine, `name "Lathe Two"`, but `workspace_id W2.id`, `factory_id F9.id`.

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [M1.id]`.

### MCH-SA-03 — a call for the other workspace returns only that workspace's machine
- **Rules:** `search_advanced` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. M1 = machine, `name "Lathe"`.
2. M9 = machine, `name "Lathe Two"`, but `workspace_id W2.id`, `factory_id F9.id`.

**When**
- `result = dao.search_advanced(db, workspace_id=W2.id)`.

**Then**
1. returns: `ids(result) == [M9.id]`.

### MCH-SA-04 — another workspace's machine is not returned when its factory id is the filter
- **Rules:** `search_advanced` R1, R4
- **Kind:** isolation
- **Expect:** pass

**Given**
1. M1 = machine, `name "Lathe"`.
2. M9 = machine, `name "Lathe Two"`, but `workspace_id W2.id`, `factory_id F9.id`.

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id, factory_id=F9.id)`.

**Then**
1. returns: `result == []`.

### MCH-SA-05 — a machine of another workspace carrying this workspace's factory id is not returned
- **Rules:** `search_advanced` R1, R4
- **Kind:** isolation
- **Expect:** pass

**Given**
1. M1 = machine, `name "Lathe"`.
2. MX = machine, `name "Stray"`, but `workspace_id W2.id`. (Same factory id F1 as M1, other workspace.)

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id, factory_id=F1.id)`.

**Then**
1. returns: `ids(result) == [M1.id]`.

### MCH-SA-06 — a machine of another workspace assigned to this workspace's section is not returned
- **Rules:** `search_advanced` R1, R5
- **Kind:** isolation
- **Expect:** pass

**Given**
1. M1 = machine, `name "Lathe"`.
2. assignment of M1 to S1.
3. M9 = machine, `name "Other"`, but `workspace_id W2.id`, `factory_id F9.id`.
4. assignment of M9 to S1. (The other workspace's machine points at this workspace's section.)

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id, factory_section_id=S1.id)`.

**Then**
1. returns: `ids(result) == [M1.id]`.

### MCH-SA-07 — a machine of another workspace is not returned when the search text matches it
- **Rules:** `search_advanced` R1, R9
- **Kind:** isolation
- **Expect:** pass

**Given**
1. M1 = machine, `name "Lathe"`.
2. M9 = machine, `name "Lathe Two"`, but `workspace_id W2.id`, `factory_id F9.id`, `model_number "LT-2"`, `manufacturer "Lathex"`.

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id, search="lathe")`.

**Then**
1. returns: `ids(result) == [M1.id]`.

### MCH-SA-08 — an unknown workspace id returns an empty list
- **Rules:** `search_advanced` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1 = machine, `name "Lathe"`.

**When**
- `result = dao.search_advanced(db, workspace_id=MISSING)`.

**Then**
1. returns: `result == []`.

### MCH-SA-09 — a soft-deleted machine is not returned
- **Rules:** `search_advanced` R2
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. M1 = machine, `name "Lathe"`.
2. M2 = machine, `name "Press"`, but deleted.

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [M1.id]`.

### MCH-SA-10 — a soft-deleted machine does not use up a place in the page
- **Rules:** `search_advanced` R2, R17
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. M1 = machine, `name "Alpha"`, but deleted.
2. M2 = machine, `name "Bravo"`.
3. M3 = machine, `name "Charlie"`.

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id, limit=1)`.

**Then**
1. returns: `ids(result) == [M2.id]`.

### MCH-SA-11 — a soft-deleted machine is not returned when every filter matches it
- **Rules:** `search_advanced` R2
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. M1 = machine, `name "Press"`, but `is_running True`, `model_number "MX-1"`, deleted.
2. M2 = machine, `name "Lathe"`.

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id, factory_id=F1.id, is_running=True, search="press", has_model_number=True)`.

**Then**
1. returns: `result == []`.

### MCH-SA-12 — an inactive live machine is returned
- **Rules:** `search_advanced` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1 = machine, `name "Lathe"`, but `is_active False`. (Still `is_deleted False`.)
2. M2 = machine, `name "Press"`.

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [M1.id, M2.id]`.

### MCH-SA-13 — assigned and unassigned machines of every factory are each returned once
- **Rules:** `search_advanced` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. M1 = machine, `name "Alpha"`.
2. assignment of M1 to S1.
3. M2 = machine, `name "Bravo"`. (No assignment.)
4. M3 = machine, `name "Charlie"`, but `factory_id F2.id`, `is_running True`.
5. assignment of M3 to S3.

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 3`.
2. returns: `ids(result) == [M1.id, M2.id, M3.id]`.

### MCH-SA-14 — section id and name are readable on an assigned machine and None on an unassigned one
- **Rules:** `search_advanced` Returns, R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. M1 = machine, `name "Alpha"`.
2. assignment of M1 to S2.
3. M2 = machine, `name "Bravo"`. (No assignment.)

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [M1.id, M2.id]`.
2. returns: `result[0].factory_section_id == S2.id`.
3. returns: `result[0].factory_section_name == "Section Two"`.
4. returns: `result[1].factory_section_id is None`.
5. returns: `result[1].factory_section_name is None`.

### MCH-SA-15 — the machine of a soft-deleted factory is not listed
- **Rules:** `search_advanced` R3a [BUG-890]
- **Kind:** bug
- **Expect:** xfail BUG-890
- **Fails today on:** Then 1 (the factory row is never looked at, so "Press" is listed too)

**Given**
1. M1 = machine, `name "Lathe"`.
2. MD = machine, `name "Press"`, but `factory_id FD.id`. (FD is the soft-deleted factory; MD itself is live.)

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id)`.

**Then**
1. returns: `names(result) == ["Lathe"]`.

### MCH-SA-16 — the id of a soft-deleted factory as the filter returns an empty list
- **Rules:** `search_advanced` R3a [BUG-890]
- **Kind:** bug
- **Expect:** xfail BUG-890
- **Fails today on:** Then 1 (the factory row is never looked at, so "Press" comes back)

**Given**
1. M1 = machine, `name "Lathe"`.
2. MD = machine, `name "Press"`, but `factory_id FD.id`. (FD is the soft-deleted factory; MD itself is live.)

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id, factory_id=FD.id)`.

**Then**
1. returns: `result == []`.

### MCH-SA-17 — the machine of a soft-deleted factory does not use up a place in the page
- **Rules:** `search_advanced` R3a [BUG-890]
- **Kind:** bug
- **Expect:** xfail BUG-890
- **Fails today on:** Then 1 (the single row is "Press", the machine of the soft-deleted factory)

**Given**
1. M1 = machine, `name "Lathe"`.
2. MD = machine, `name "Press"`, but `factory_id FD.id`. (FD is the soft-deleted factory; MD itself is live.)

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id, sort_dir="desc", limit=1)`.

**Then**
1. returns: `names(result) == ["Lathe"]`.

### MCH-SA-18 — the machine of a soft-deleted factory is not returned when the other filters match it
- **Rules:** `search_advanced` R3a [BUG-890]
- **Kind:** bug
- **Expect:** xfail BUG-890
- **Fails today on:** Then 1 (the factory row is never looked at, so MD comes back with M1)

**Given**
1. M1 = machine, `name "Press One"`, but `is_running True`.
2. assignment of M1 to S1.
3. MD = machine, `name "Press Two"`, but `factory_id FD.id`, `is_running True`. (FD is the soft-deleted factory; MD itself is live.)
4. assignment of MD to S1.

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id, factory_section_id=S1.id, is_running=True, search="press")`.

**Then**
1. returns: `ids(result) == [M1.id]`.

### MCH-SA-19 — the machine of a live but inactive factory is listed like any other
- **Rules:** `search_advanced` R3b
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1 = machine, `name "Lathe"`.
2. MI = machine, `name "Press"`, but `factory_id FI.id`. (FI is the live but inactive factory.)

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [M1.id, MI.id]`.

### MCH-SA-20 — the id of a live but inactive factory works as the factory filter
- **Rules:** `search_advanced` R3b, R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1 = machine, `name "Lathe"`.
2. MI = machine, `name "Press"`, but `factory_id FI.id`. (FI is the live but inactive factory.)

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id, factory_id=FI.id)`.

**Then**
1. returns: `ids(result) == [MI.id]`.

### MCH-SA-21 — searching changes nothing: the machine of a soft-deleted factory stays as it was
- **Rules:** `search_advanced` R3b
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. M1 = machine, `name "Lathe"`.
2. MD = machine, `name "Press"`, but `factory_id FD.id`. (FD is the soft-deleted factory; MD itself is live.)

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id, factory_id=F1.id)`.

**Then**
1. returns: `ids(result) == [M1.id]`.
2. unchanged: unchanged(MD).
3. re-read MD: `is_deleted is False`, `is_active is True`.
4. unchanged: unchanged(M1).
5. nothing written: nothing written.
6. count: `machines` has exactly 2 rows.

### MCH-SA-22 — factory_id filter keeps only that factory
- **Rules:** `search_advanced` R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. M1 = machine, `name "Press"`, but `factory_id F2.id`.
2. M2 = machine, `name "Lathe"`.
3. M3 = machine, `name "Drill"`, but `factory_id F2.id`.

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id, factory_id=F2.id)`.

**Then**
1. returns: `ids(result) == [M3.id, M1.id]`.

### MCH-SA-23 — a factory id that does not exist returns an empty list
- **Rules:** `search_advanced` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1 = machine, `name "Lathe"`.

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id, factory_id=MISSING)`.

**Then**
1. returns: `result == []`.

### MCH-SA-24 — factory_id 0 filters and returns an empty list
- **Rules:** `search_advanced` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1 = machine, `name "Lathe"`.
2. M2 = machine, `name "Drill"`, but `factory_id F2.id`.

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id, factory_id=0)`.

**Then**
1. returns: `result == []`.

### MCH-SA-25 — explicit None for every optional filter applies no filter
- **Rules:** `search_advanced` R4, R5, R7, R8, R10, R11, R12
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1 = machine, `name "Alpha"`.
2. assignment of M1 to S1.
3. M2 = machine, `name "Bravo"`, but `factory_id F2.id`, `is_running True`, `model_number "MX-1"`, `manufacturer "Acme"`. (No assignment.)

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id, factory_id=None, factory_section_id=None, is_running=None, search=None, has_model_number=None, has_manufacturer=None, latest_event_type=None)`.

**Then**
1. returns: `ids(result) == [M1.id, M2.id]`.

### MCH-SA-26 — factory_section_id filter keeps only the machines assigned to that section
- **Rules:** `search_advanced` R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. M1 = machine, `name "Press"`.
2. assignment of M1 to S1.
3. M2 = machine, `name "Drill"`.
4. assignment of M2 to S2.
5. M3 = machine, `name "Saw"`. (No assignment.)
6. M4 = machine, `name "Lathe"`.
7. assignment of M4 to S1.

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id, factory_section_id=S1.id)`.

**Then**
1. returns: `len(result) == 2`.
2. returns: `ids(result) == [M4.id, M1.id]`.
3. returns: `result[0].factory_section_id == S1.id`.

### MCH-SA-27 — a section id that does not exist returns an empty list
- **Rules:** `search_advanced` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1 = machine, `name "Lathe"`.
2. assignment of M1 to S1.
3. M2 = machine, `name "Saw"`. (No assignment.)

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id, factory_section_id=MISSING)`.

**Then**
1. returns: `result == []`.

### MCH-SA-28 — factory_section_id 0 filters and returns an empty list
- **Rules:** `search_advanced` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1 = machine, `name "Lathe"`.
2. assignment of M1 to S1.
3. M2 = machine, `name "Saw"`. (No assignment.)

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id, factory_section_id=0)`.

**Then**
1. returns: `result == []`.

### MCH-SA-29 — the id of a live but inactive section works as the section filter
- **Rules:** `search_advanced` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1 = machine, `name "Lathe"`.
2. assignment of M1 to SI. (SI is the live but inactive section.)
3. M2 = machine, `name "Press"`.
4. assignment of M2 to S1.

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id, factory_section_id=SI.id)`.

**Then**
1. returns: `ids(result) == [M1.id]`.

### MCH-SA-30 — factory and section filters must both match the machine
- **Rules:** `search_advanced` R6, R13a
- **Kind:** happy
- **Expect:** pass

**Given**
1. M1 = machine, `name "Lathe"`.
2. assignment of M1 to S1.
3. M2 = machine, `name "Press"`, but `factory_id F2.id`.
4. assignment of M2 to S1. (A machine of F2 pointing at a section of F1.)
5. M3 = machine, `name "Saw"`. (No assignment.)

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id, factory_id=F1.id, factory_section_id=S1.id)`.

**Then**
1. returns: `ids(result) == [M1.id]`.

### MCH-SA-31 — a section of another factory than factory_id returns an empty list
- **Rules:** `search_advanced` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1 = machine, `name "Lathe"`.
2. assignment of M1 to S1.
3. M2 = machine, `name "Press"`, but `factory_id F2.id`.
4. assignment of M2 to S3. (S3 is the section of F2.)

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id, factory_id=F1.id, factory_section_id=S3.id)`.

**Then**
1. returns: `result == []`.

### MCH-SA-32 — the matching factory and section pair of the other factory returns its machine
- **Rules:** `search_advanced` R6
- **Kind:** happy
- **Expect:** pass

**Given**
1. M1 = machine, `name "Lathe"`.
2. assignment of M1 to S1.
3. M2 = machine, `name "Press"`, but `factory_id F2.id`.
4. assignment of M2 to S3. (S3 is the section of F2.)

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id, factory_id=F2.id, factory_section_id=S3.id)`.

**Then**
1. returns: `ids(result) == [M2.id]`.

### MCH-SA-33 — the id of a soft-deleted section as the filter returns an empty list
- **Rules:** `search_advanced` R6a [BUG-889]
- **Kind:** bug
- **Expect:** xfail BUG-889
- **Fails today on:** Then 2 (the section row is never looked at, so M1 comes back)

**Given**
1. M1 = machine, `name "Lathe"`.
2. assignment of M1 to SX. (SX is the soft-deleted section; a left-over assignment.)
3. M2 = machine, `name "Press"`.
4. assignment of M2 to S1.

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id, factory_section_id=SX.id)`.

**Then**
1. count: `machine_section_assignments` has exactly 2 rows.
2. returns: `result == []`.

### MCH-SA-34 — without a section filter a machine with a left-over assignment to a deleted section is listed
- **Rules:** `search_advanced` R6a
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. M1 = machine, `name "Lathe"`.
2. assignment of M1 to SX. (SX is the soft-deleted section; a left-over assignment.)
3. M2 = machine, `name "Press"`.
4. assignment of M2 to S1.

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [M1.id, M2.id]`.
2. count: `machine_section_assignments` has exactly 2 rows.

### MCH-SA-35 — is_running True keeps only running machines
- **Rules:** `search_advanced` R7
- **Kind:** happy
- **Expect:** pass

**Given**
1. M1 = machine, `name "Press"`, but `is_running True`.
2. M2 = machine, `name "Lathe"`.
3. M3 = machine, `name "Drill"`, but `is_running True`.

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id, is_running=True)`.

**Then**
1. returns: `ids(result) == [M3.id, M1.id]`.

### MCH-SA-36 — is_running False keeps only machines that are not running
- **Rules:** `search_advanced` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1 = machine, `name "Press"`, but `is_running True`.
2. M2 = machine, `name "Lathe"`.
3. M3 = machine, `name "Drill"`.

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id, is_running=False)`.

**Then**
1. returns: `ids(result) == [M3.id, M2.id]`.

### MCH-SA-37 — search None applies no search filter
- **Rules:** `search_advanced` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1 = machine, `name "Bolt cutter"`.
2. M2 = machine, `name "Lathe"`.

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id, search=None)`.

**Then**
1. returns: `ids(result) == [M1.id, M2.id]`.

### MCH-SA-38 — an empty search text applies no search filter
- **Rules:** `search_advanced` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1 = machine, `name "Bolt cutter"`.
2. M2 = machine, `name "Lathe"`.

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id, search="")`.

**Then**
1. returns: `ids(result) == [M1.id, M2.id]`.

### MCH-SA-39 — a search of three spaces applies no search filter
- **Rules:** `search_advanced` R8 [BUG-892]
- **Kind:** bug
- **Expect:** xfail BUG-892
- **Fails today on:** Then 1 (the three spaces are searched as text and no machine contains them, so the list is empty)

**Given**
1. M1 = machine, `name "Bolt cutter"`.
2. M2 = machine, `name "Lathe"`.

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id, search="   ")`. The text is three spaces.

**Then**
1. returns: `ids(result) == [M1.id, M2.id]`.

### MCH-SA-40 — a search of a space, a tab and a newline applies no search filter
- **Rules:** `search_advanced` R8 [BUG-892]
- **Kind:** bug
- **Expect:** xfail BUG-892
- **Fails today on:** Then 1 (the whitespace is searched as text and no machine contains it, so the list is empty)

**Given**
1. M1 = machine, `name "Bolt cutter"`.
2. M2 = machine, `name "Lathe"`.

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id, search=" \t\n")`.

**Then**
1. returns: `ids(result) == [M1.id, M2.id]`.

### MCH-SA-41 — spaces around the search text are removed before matching
- **Rules:** `search_advanced` R8 [BUG-892]
- **Kind:** bug
- **Expect:** xfail BUG-892
- **Fails today on:** Then 1 (the text is used with both spaces, which no machine contains, so the list is empty)

**Given**
1. M1 = machine, `name "Bolt cutter"`.
2. M2 = machine, `name "Lathe"`.

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id, search=" bolt ")`.

**Then**
1. returns: `ids(result) == [M1.id]`.

### MCH-SA-42 — leading spaces of the search text are removed before matching
- **Rules:** `search_advanced` R8 [BUG-892]
- **Kind:** bug
- **Expect:** xfail BUG-892
- **Fails today on:** Then 1 (the text is used with its leading spaces, which no machine contains, so the list is empty)

**Given**
1. M1 = machine, `name "Bolt cutter"`.
2. M2 = machine, `name "Lathe"`.

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id, search="  bolt")`. The text starts with two spaces.

**Then**
1. returns: `ids(result) == [M1.id]`.

### MCH-SA-43 — a trailing space of the search text is removed before matching
- **Rules:** `search_advanced` R8 [BUG-892]
- **Kind:** bug
- **Expect:** xfail BUG-892
- **Fails today on:** Then 1 (the text is used with its trailing space; "Bolt cutter" does not end in a space, so the list is empty)

**Given**
1. M1 = machine, `name "Bolt cutter"`.
2. M2 = machine, `name "Lathe"`.

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id, search="cutter ")`. The text ends with one space.

**Then**
1. returns: `ids(result) == [M1.id]`.

### MCH-SA-44 — inner whitespace of the search text is kept and matches as typed
- **Rules:** `search_advanced` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1 = machine, `name "Bolt cutter"`.
2. M2 = machine, `name "Boltcutter"`.

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id, search="bolt cutter")`.

**Then**
1. returns: `ids(result) == [M1.id]`.

### MCH-SA-45 — two inner spaces do not match a name with one space
- **Rules:** `search_advanced` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1 = machine, `name "Bolt cutter"`.
2. M2 = machine, `name "Lathe"`.

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id, search="bolt  cutter")`. The text has two spaces between the words.

**Then**
1. returns: `result == []`.

### MCH-SA-46 — the search is case-insensitive and matches anywhere in the name
- **Rules:** `search_advanced` R9
- **Kind:** happy
- **Expect:** pass

**Given**
1. M1 = machine, `name "Steel bolt"`.
2. M2 = machine, `name "Bolt cutter"`.
3. M3 = machine, `name "Lathe"`.

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id, search="BOLT")`.

**Then**
1. returns: `ids(result) == [M2.id, M1.id]`.

### MCH-SA-47 — a text from the middle of the name matches
- **Rules:** `search_advanced` R9
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1 = machine, `name "Bolt cutter"`.
2. M2 = machine, `name "Lathe"`.

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id, search="olt cut")`.

**Then**
1. returns: `ids(result) == [M1.id]`.

### MCH-SA-48 — the search matches the model number
- **Rules:** `search_advanced` R9
- **Kind:** happy
- **Expect:** pass

**Given**
1. M1 = machine, `name "Lathe"`, but `model_number "MX-500"`.
2. M2 = machine, `name "Press"`, but `model_number "QR-7"`.
3. M3 = machine, `name "Drill"`.

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id, search="x-5")`.

**Then**
1. returns: `ids(result) == [M1.id]`.

### MCH-SA-49 — the search matches the manufacturer
- **Rules:** `search_advanced` R9
- **Kind:** happy
- **Expect:** pass

**Given**
1. M1 = machine, `name "Lathe"`, but `manufacturer "Siemens"`.
2. M2 = machine, `name "Press"`, but `manufacturer "Bosch"`.
3. M3 = machine, `name "Drill"`.

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id, search="sie")`.

**Then**
1. returns: `ids(result) == [M1.id]`.

### MCH-SA-50 — a match in any one of name, model number or manufacturer is enough
- **Rules:** `search_advanced` R9, R13a
- **Kind:** happy
- **Expect:** pass

**Given**
1. M1 = machine, `name "Bolt cutter"`.
2. M2 = machine, `name "Lathe"`, but `model_number "BOLT-9"`.
3. M3 = machine, `name "Press"`, but `manufacturer "Boltco"`.
4. M4 = machine, `name "Drill"`, but `model_number "QR-7"`, `manufacturer "Bosch"`.

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id, search="bolt")`.

**Then**
1. returns: `ids(result) == [M1.id, M2.id, M3.id]`.

### MCH-SA-51 — a text that no machine contains returns an empty list, NULL fields included
- **Rules:** `search_advanced` R9
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1 = machine, `name "Lathe"`. (`model_number None`, `manufacturer None`.)
2. M2 = machine, `name "Press"`, but `model_number "QR-7"`.

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id, search="sie")`.

**Then**
1. returns: `result == []`.

### MCH-SA-52 — the note is not searched
- **Rules:** `search_advanced` R9
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1 = machine, `name "Lathe"`, but `note "bolt spare"`.
2. M2 = machine, `name "Press"`.

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id, search="bolt")`.

**Then**
1. returns: `result == []`.

### MCH-SA-53 — the factory name is not searched
- **Rules:** `search_advanced` R9
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1 = machine, `name "Lathe"`. (Its factory F1 is named "Factory One".)

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id, search="Factory")`.

**Then**
1. returns: `result == []`.

### MCH-SA-54 — the section name is not searched
- **Rules:** `search_advanced` R9
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1 = machine, `name "Lathe"`.
2. assignment of M1 to S1. (S1 is named "Section One".)

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id, search="Section")`.

**Then**
1. returns: `result == []`.

### MCH-SA-55 — a percent sign alone finds only machines that contain a percent sign
- **Rules:** `search_advanced` R9 [BUG-888]
- **Kind:** bug
- **Expect:** xfail BUG-888
- **Fails today on:** Then 1 (the percent sign acts as a wildcard, so both machines come back)

**Given**
1. M1 = machine, `name "Lathe"`, but `model_number "50%"`.
2. M2 = machine, `name "Press"`, but `model_number "QR-7"`.

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id, search="%")`.

**Then**
1. returns: `ids(result) == [M1.id]`.

### MCH-SA-56 — a percent sign inside the text is not a wildcard
- **Rules:** `search_advanced` R9 [BUG-888]
- **Kind:** bug
- **Expect:** xfail BUG-888
- **Fails today on:** Then 1 (the percent sign acts as a wildcard, so model number "500" matches too)

**Given**
1. M1 = machine, `name "Lathe"`, but `model_number "50%"`.
2. M2 = machine, `name "Press"`, but `model_number "500"`.

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id, search="50%")`.

**Then**
1. returns: `ids(result) == [M1.id]`.

### MCH-SA-57 — a text with a percent sign finds the machine that contains it
- **Rules:** `search_advanced` R9
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1 = machine, `name "Lathe"`, but `model_number "50%"`.
2. M2 = machine, `name "Press"`, but `model_number "QR-7"`.

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id, search="50%")`.

**Then**
1. returns: `ids(result) == [M1.id]`.

### MCH-SA-58 — an underscore alone finds only machines that contain an underscore
- **Rules:** `search_advanced` R9 [BUG-888]
- **Kind:** bug
- **Expect:** xfail BUG-888
- **Fails today on:** Then 1 (the underscore acts as a one-character wildcard, so both machines come back)

**Given**
1. M1 = machine, `name "Lathe_2"`.
2. M2 = machine, `name "Press"`.

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id, search="_")`.

**Then**
1. returns: `ids(result) == [M1.id]`.

### MCH-SA-59 — an underscore inside the text is not a wildcard
- **Rules:** `search_advanced` R9 [BUG-888]
- **Kind:** bug
- **Expect:** xfail BUG-888
- **Fails today on:** Then 1 (the underscore matches any one character, so manufacturer "ACME-1" matches too)

**Given**
1. M1 = machine, `name "Lathe"`, but `manufacturer "ACME_1"`.
2. M2 = machine, `name "Press"`, but `manufacturer "ACME-1"`.

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id, search="acme_1")`.

**Then**
1. returns: `ids(result) == [M1.id]`.

### MCH-SA-60 — a backslash in the text is matched literally
- **Rules:** `search_advanced` R9 [BUG-888]
- **Kind:** bug
- **Expect:** xfail BUG-888
- **Fails today on:** Then 1 (the backslash acts as the escape character, so "ab" comes back instead of the name with the backslash)

**Given**
1. M1 = machine, `name "a\\b"`. (The three characters a, backslash, b.)
2. M2 = machine, `name "ab"`.

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id, search="a\\b")`.

**Then**
1. returns: `ids(result) == [M1.id]`.

### MCH-SA-61 — has_model_number True keeps machines with a non-empty model number, spaces included
- **Rules:** `search_advanced` R10
- **Kind:** happy
- **Expect:** pass

**Given**
1. M1 = machine, `name "Alpha"`, but `model_number "MX-1"`.
2. M2 = machine, `name "Bravo"`. (`model_number None`.)
3. M3 = machine, `name "Charlie"`, but `model_number ""`.
4. M4 = machine, `name "Delta"`, but `model_number "   "`. (Three spaces.)

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id, has_model_number=True)`.

**Then**
1. returns: `ids(result) == [M1.id, M4.id]`.

### MCH-SA-62 — has_model_number False keeps machines whose model number is NULL or empty
- **Rules:** `search_advanced` R10
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1 = machine, `name "Alpha"`, but `model_number "MX-1"`.
2. M2 = machine, `name "Bravo"`. (`model_number None`.)
3. M3 = machine, `name "Charlie"`, but `model_number ""`.
4. M4 = machine, `name "Delta"`, but `model_number "   "`. (Three spaces.)

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id, has_model_number=False)`.

**Then**
1. returns: `ids(result) == [M2.id, M3.id]`.

### MCH-SA-63 — has_manufacturer True keeps machines with a non-empty manufacturer, spaces included
- **Rules:** `search_advanced` R11
- **Kind:** happy
- **Expect:** pass

**Given**
1. M1 = machine, `name "Alpha"`, but `manufacturer "Acme"`.
2. M2 = machine, `name "Bravo"`. (`manufacturer None`.)
3. M3 = machine, `name "Charlie"`, but `manufacturer ""`.
4. M4 = machine, `name "Delta"`, but `manufacturer "   "`. (Three spaces.)

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id, has_manufacturer=True)`.

**Then**
1. returns: `ids(result) == [M1.id, M4.id]`.

### MCH-SA-64 — has_manufacturer False keeps machines whose manufacturer is NULL or empty
- **Rules:** `search_advanced` R11
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1 = machine, `name "Alpha"`, but `manufacturer "Acme"`.
2. M2 = machine, `name "Bravo"`. (`manufacturer None`.)
3. M3 = machine, `name "Charlie"`, but `manufacturer ""`.
4. M4 = machine, `name "Delta"`, but `manufacturer "   "`. (Three spaces.)

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id, has_manufacturer=False)`.

**Then**
1. returns: `ids(result) == [M2.id, M3.id]`.

### MCH-SA-65 — has_model_number True with has_manufacturer False looks at each column on its own
- **Rules:** `search_advanced` R11, R10, R13a
- **Kind:** happy
- **Expect:** pass

**Given**
1. M1 = machine, `name "Alpha"`, but `model_number "MX-1"`, `manufacturer "Acme"`.
2. M2 = machine, `name "Bravo"`, but `model_number "MX-2"`.
3. M3 = machine, `name "Charlie"`, but `manufacturer "Bosch"`.
4. M4 = machine, `name "Delta"`.

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id, has_model_number=True, has_manufacturer=False)`.

**Then**
1. returns: `ids(result) == [M2.id]`.

### MCH-SA-66 — has_model_number False with has_manufacturer True looks at each column on its own
- **Rules:** `search_advanced` R11, R10, R13a
- **Kind:** happy
- **Expect:** pass

**Given**
1. M1 = machine, `name "Alpha"`, but `model_number "MX-1"`, `manufacturer "Acme"`.
2. M2 = machine, `name "Bravo"`, but `model_number "MX-2"`.
3. M3 = machine, `name "Charlie"`, but `manufacturer "Bosch"`.
4. M4 = machine, `name "Delta"`.

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id, has_model_number=False, has_manufacturer=True)`.

**Then**
1. returns: `ids(result) == [M3.id]`.

### MCH-SA-67 — latest_event_type RUNNING returns the machine whose latest status is RUNNING
- **Rules:** `search_advanced` R12 [BUG-886], Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-886
- **Fails today on:** Then 1 (the call raises AttributeError: the status filter cannot be built)

**Given**
1. M1 = machine, `name "Alpha"`.
2. event of M1, `created_at T1`, `metadata_json {"status": "RUNNING"}`.
3. M2 = machine, `name "Bravo"`.
4. event of M2, `created_at T1`, `metadata_json {"status": "IDLE"}`.
5. M3 = machine, `name "Charlie"`.
6. event of M3, `created_at T1`, `metadata_json {"status": "OFF"}`.
7. M4 = machine, `name "Delta"`.
8. event of M4, `created_at T1`, `metadata_json {"status": "MAINTENANCE"}`.
9. M5 = machine, `name "Echo"`. (No events.)

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id, latest_event_type=RUNNING)`.

**Then**
1. returns: `ids(result) == [M1.id]`.

### MCH-SA-68 — latest_event_type IDLE returns the machine whose latest status is IDLE
- **Rules:** `search_advanced` R12 [BUG-886]
- **Kind:** bug
- **Expect:** xfail BUG-886
- **Fails today on:** Then 1 (the call raises AttributeError: the status filter cannot be built)

**Given**
1. M1 = machine, `name "Alpha"`.
2. event of M1, `created_at T1`, `metadata_json {"status": "RUNNING"}`.
3. M2 = machine, `name "Bravo"`.
4. event of M2, `created_at T1`, `metadata_json {"status": "IDLE"}`.
5. M3 = machine, `name "Charlie"`.
6. event of M3, `created_at T1`, `metadata_json {"status": "OFF"}`.
7. M4 = machine, `name "Delta"`.
8. event of M4, `created_at T1`, `metadata_json {"status": "MAINTENANCE"}`.
9. M5 = machine, `name "Echo"`. (No events.)

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id, latest_event_type=IDLE)`.

**Then**
1. returns: `ids(result) == [M2.id]`.

### MCH-SA-69 — latest_event_type OFF returns the machine whose latest status is OFF
- **Rules:** `search_advanced` R12 [BUG-886]
- **Kind:** bug
- **Expect:** xfail BUG-886
- **Fails today on:** Then 1 (the call raises AttributeError: the status filter cannot be built)

**Given**
1. M1 = machine, `name "Alpha"`.
2. event of M1, `created_at T1`, `metadata_json {"status": "RUNNING"}`.
3. M2 = machine, `name "Bravo"`.
4. event of M2, `created_at T1`, `metadata_json {"status": "IDLE"}`.
5. M3 = machine, `name "Charlie"`.
6. event of M3, `created_at T1`, `metadata_json {"status": "OFF"}`.
7. M4 = machine, `name "Delta"`.
8. event of M4, `created_at T1`, `metadata_json {"status": "MAINTENANCE"}`.
9. M5 = machine, `name "Echo"`. (No events.)

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id, latest_event_type=OFF)`.

**Then**
1. returns: `ids(result) == [M3.id]`.

### MCH-SA-70 — latest_event_type MAINTENANCE returns the machine whose latest status is MAINTENANCE
- **Rules:** `search_advanced` R12 [BUG-886]
- **Kind:** bug
- **Expect:** xfail BUG-886
- **Fails today on:** Then 1 (the call raises AttributeError: the status filter cannot be built)

**Given**
1. M1 = machine, `name "Alpha"`.
2. event of M1, `created_at T1`, `metadata_json {"status": "RUNNING"}`.
3. M2 = machine, `name "Bravo"`.
4. event of M2, `created_at T1`, `metadata_json {"status": "IDLE"}`.
5. M3 = machine, `name "Charlie"`.
6. event of M3, `created_at T1`, `metadata_json {"status": "OFF"}`.
7. M4 = machine, `name "Delta"`.
8. event of M4, `created_at T1`, `metadata_json {"status": "MAINTENANCE"}`.
9. M5 = machine, `name "Echo"`. (No events.)

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id, latest_event_type=MAINTENANCE)`.

**Then**
1. returns: `ids(result) == [M4.id]`.

### MCH-SA-71 — without a status filter, machines with several status events are each listed once
- **Rules:** `search_advanced` R12, R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1 = machine, `name "Alpha"`.
2. event of M1, `created_at T1`, `metadata_json {"status": "RUNNING"}`.
3. event of M1, `created_at T2`, `metadata_json {"status": "IDLE"}`.
4. M2 = machine, `name "Bravo"`. (No events.)

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 2`.
2. returns: `ids(result) == [M1.id, M2.id]`.

### MCH-SA-72 — the newest status change decides: the machine matches its newest status
- **Rules:** `search_advanced` R12a [BUG-886]
- **Kind:** bug
- **Expect:** xfail BUG-886
- **Fails today on:** Then 1 (the call raises AttributeError: the status filter cannot be built)

**Given**
1. M1 = machine, `name "Alpha"`.
2. event of M1, `created_at T1`, `metadata_json {"status": "RUNNING"}`.
3. event of M1, `created_at T2`, `metadata_json {"status": "IDLE"}`.
4. M2 = machine, `name "Bravo"`.
5. event of M2, `created_at T1`, `metadata_json {"status": "RUNNING"}`.

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id, latest_event_type=IDLE)`.

**Then**
1. returns: `ids(result) == [M1.id]`.

### MCH-SA-73 — the newest status change decides: the machine does not match an older status
- **Rules:** `search_advanced` R12a [BUG-886]
- **Kind:** bug
- **Expect:** xfail BUG-886
- **Fails today on:** Then 1 (the call raises AttributeError: the status filter cannot be built)

**Given**
1. M1 = machine, `name "Alpha"`.
2. event of M1, `created_at T1`, `metadata_json {"status": "RUNNING"}`.
3. event of M1, `created_at T2`, `metadata_json {"status": "IDLE"}`.
4. M2 = machine, `name "Bravo"`.
5. event of M2, `created_at T1`, `metadata_json {"status": "RUNNING"}`.

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id, latest_event_type=RUNNING)`.

**Then**
1. returns: `ids(result) == [M2.id]`.

### MCH-SA-74 — "latest" goes by created_at, not by the order of insertion
- **Rules:** `search_advanced` R12a [BUG-886]
- **Kind:** bug
- **Expect:** xfail BUG-886
- **Fails today on:** Then 1 (the call raises AttributeError: the status filter cannot be built)

**Given**
1. M1 = machine, `name "Alpha"`.
2. event of M1, `created_at T2`, `metadata_json {"status": "IDLE"}`. (The newer status, inserted first.)
3. event of M1, `created_at T1`, `metadata_json {"status": "RUNNING"}`. (The older status, inserted second.)
4. M2 = machine, `name "Bravo"`.
5. event of M2, `created_at T3`, `metadata_json {"status": "RUNNING"}`.

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id, latest_event_type=IDLE)`.

**Then**
1. returns: `ids(result) == [M1.id]`.

### MCH-SA-75 — on a created_at tie the status change with the greater id decides
- **Rules:** `search_advanced` R12a [BUG-886]
- **Kind:** bug
- **Expect:** xfail BUG-886
- **Fails today on:** Then 1 (the call raises AttributeError: the status filter cannot be built)

**Given**
1. M1 = machine, `name "Alpha"`.
2. event of M1, `created_at T2`, `metadata_json {"status": "RUNNING"}`. (Inserted first: lower id.)
3. event of M1, `created_at T2`, `metadata_json {"status": "OFF"}`. (Inserted second: greater id.)
4. M2 = machine, `name "Bravo"`.
5. event of M2, `created_at T1`, `metadata_json {"status": "RUNNING"}`.

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id, latest_event_type=OFF)`.

**Then**
1. returns: `ids(result) == [M1.id]`.

### MCH-SA-76 — on a created_at tie the status change with the lower id does not match
- **Rules:** `search_advanced` R12a [BUG-886]
- **Kind:** bug
- **Expect:** xfail BUG-886
- **Fails today on:** Then 1 (the call raises AttributeError: the status filter cannot be built)

**Given**
1. M1 = machine, `name "Alpha"`.
2. event of M1, `created_at T2`, `metadata_json {"status": "RUNNING"}`. (Inserted first: lower id.)
3. event of M1, `created_at T2`, `metadata_json {"status": "OFF"}`. (Inserted second: greater id.)
4. M2 = machine, `name "Bravo"`.
5. event of M2, `created_at T1`, `metadata_json {"status": "RUNNING"}`.

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id, latest_event_type=RUNNING)`.

**Then**
1. returns: `ids(result) == [M2.id]`.

### MCH-SA-77 — a machine with only events of other types never matches
- **Rules:** `search_advanced` R12b [BUG-886]
- **Kind:** bug
- **Expect:** xfail BUG-886
- **Fails today on:** Then 1 (the call raises AttributeError: the status filter cannot be built)

**Given**
1. M1 = machine, `name "Alpha"`.
2. event of M1, `created_at T2`, `metadata_json {"status": "RUNNING"}`, but `event_type "created"`.
3. M2 = machine, `name "Bravo"`.
4. event of M2, `created_at T1`, `metadata_json {"status": "RUNNING"}`.
5. M3 = machine, `name "Charlie"`. (No events.)

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id, latest_event_type=RUNNING)`.

**Then**
1. returns: `ids(result) == [M2.id]`.

### MCH-SA-78 — a newer event of another type does not replace the latest status
- **Rules:** `search_advanced` R12b [BUG-886]
- **Kind:** bug
- **Expect:** xfail BUG-886
- **Fails today on:** Then 1 (the call raises AttributeError: the status filter cannot be built)

**Given**
1. M1 = machine, `name "Alpha"`.
2. event of M1, `created_at T1`, `metadata_json {"status": "RUNNING"}`.
3. event of M1, `created_at T2`, `metadata_json {"status": "OFF"}`, but `event_type "updated"`.

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id, latest_event_type=RUNNING)`.

**Then**
1. returns: `ids(result) == [M1.id]`.

### MCH-SA-79 — the status in a newer event of another type is not matched
- **Rules:** `search_advanced` R12b [BUG-886]
- **Kind:** bug
- **Expect:** xfail BUG-886
- **Fails today on:** Then 1 (the call raises AttributeError: the status filter cannot be built)

**Given**
1. M1 = machine, `name "Alpha"`.
2. event of M1, `created_at T1`, `metadata_json {"status": "RUNNING"}`.
3. event of M1, `created_at T2`, `metadata_json {"status": "OFF"}`, but `event_type "updated"`.

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id, latest_event_type=OFF)`.

**Then**
1. returns: `result == []`.

### MCH-SA-80 — a latest status change without metadata matches nothing and the older one is not used
- **Rules:** `search_advanced` R12c [BUG-886]
- **Kind:** bug
- **Expect:** xfail BUG-886
- **Fails today on:** Then 1 (the call raises AttributeError: the status filter cannot be built)

**Given**
1. M1 = machine, `name "Alpha"`.
2. event of M1, `created_at T1`, `metadata_json {"status": "RUNNING"}`.
3. event of M1, `created_at T2`, `metadata_json None`.
4. M2 = machine, `name "Bravo"`.
5. event of M2, `created_at T1`, `metadata_json {"status": "RUNNING"}`.

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id, latest_event_type=RUNNING)`.

**Then**
1. returns: `ids(result) == [M2.id]`.

### MCH-SA-81 — a latest status change without a "status" key matches nothing and the older one is not used
- **Rules:** `search_advanced` R12c [BUG-886]
- **Kind:** bug
- **Expect:** xfail BUG-886
- **Fails today on:** Then 1 (the call raises AttributeError: the status filter cannot be built)

**Given**
1. M1 = machine, `name "Alpha"`.
2. event of M1, `created_at T1`, `metadata_json {"status": "RUNNING"}`.
3. event of M1, `created_at T2`, `metadata_json {"note": "x"}`.
4. M2 = machine, `name "Bravo"`.
5. event of M2, `created_at T1`, `metadata_json {"status": "RUNNING"}`.

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id, latest_event_type=RUNNING)`.

**Then**
1. returns: `ids(result) == [M2.id]`.

### MCH-SA-82 — a status change recorded in another workspace is not counted
- **Rules:** `search_advanced` R12d [BUG-886]
- **Kind:** bug
- **Expect:** xfail BUG-886
- **Fails today on:** Then 1 (the call raises AttributeError: the status filter cannot be built)

**Given**
1. M1 = machine, `name "Alpha"`.
2. event of M1, `created_at T1`, `metadata_json {"status": "IDLE"}`.
3. event of M1, `created_at T2`, `metadata_json {"status": "RUNNING"}`, but `workspace_id W2.id`. (Newer, but recorded in the other workspace.)

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id, latest_event_type=IDLE)`.

**Then**
1. returns: `ids(result) == [M1.id]`.

### MCH-SA-83 — the status of a change recorded in another workspace is not matched
- **Rules:** `search_advanced` R12d [BUG-886]
- **Kind:** bug
- **Expect:** xfail BUG-886
- **Fails today on:** Then 1 (the call raises AttributeError: the status filter cannot be built)

**Given**
1. M1 = machine, `name "Alpha"`.
2. event of M1, `created_at T1`, `metadata_json {"status": "IDLE"}`.
3. event of M1, `created_at T2`, `metadata_json {"status": "RUNNING"}`, but `workspace_id W2.id`. (Newer, but recorded in the other workspace.)

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id, latest_event_type=RUNNING)`.

**Then**
1. returns: `result == []`.

### MCH-SA-84 — two newest status changes with the same status list the machine once
- **Rules:** `search_advanced` R12e [BUG-886]
- **Kind:** bug
- **Expect:** xfail BUG-886
- **Fails today on:** Then 1 (the call raises AttributeError: the status filter cannot be built)

**Given**
1. M1 = machine, `name "Alpha"`.
2. event of M1, `created_at T2`, `metadata_json {"status": "RUNNING"}`.
3. event of M1, `created_at T2`, `metadata_json {"status": "RUNNING"}`.
4. event of M1, `created_at T1`, `metadata_json {"status": "RUNNING"}`.

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id, latest_event_type=RUNNING)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `ids(result) == [M1.id]`.

### MCH-SA-85 — the status filter combines with the factory filter
- **Rules:** `search_advanced` R12e [BUG-886], R13a
- **Kind:** bug
- **Expect:** xfail BUG-886
- **Fails today on:** Then 1 (the call raises AttributeError: the status filter cannot be built)

**Given**
1. M1 = machine, `name "Alpha"`.
2. event of M1, `created_at T1`, `metadata_json {"status": "RUNNING"}`.
3. M2 = machine, `name "Bravo"`, but `factory_id F2.id`.
4. event of M2, `created_at T1`, `metadata_json {"status": "RUNNING"}`.
5. M3 = machine, `name "Charlie"`.
6. event of M3, `created_at T1`, `metadata_json {"status": "IDLE"}`.

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id, factory_id=F1.id, latest_event_type=RUNNING)`.

**Then**
1. returns: `ids(result) == [M1.id]`.

### MCH-SA-86 — the status filter combines with the search text
- **Rules:** `search_advanced` R12e [BUG-886], R13a
- **Kind:** bug
- **Expect:** xfail BUG-886
- **Fails today on:** Then 1 (the call raises AttributeError: the status filter cannot be built)

**Given**
1. M1 = machine, `name "Bolt cutter"`.
2. event of M1, `created_at T1`, `metadata_json {"status": "RUNNING"}`.
3. M2 = machine, `name "Lathe"`.
4. event of M2, `created_at T1`, `metadata_json {"status": "RUNNING"}`.
5. M3 = machine, `name "Bolt press"`.
6. event of M3, `created_at T1`, `metadata_json {"status": "IDLE"}`.

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id, search="bolt", latest_event_type=RUNNING)`.

**Then**
1. returns: `ids(result) == [M1.id]`.

### MCH-SA-87 — the status filter is sorted and paged like any other result
- **Rules:** `search_advanced` R12e [BUG-886], R17
- **Kind:** bug
- **Expect:** xfail BUG-886
- **Fails today on:** Then 1 (the call raises AttributeError: the status filter cannot be built)

**Given**
1. M1 = machine, `name "Alpha"`.
2. event of M1, `created_at T1`, `metadata_json {"status": "RUNNING"}`.
3. M2 = machine, `name "Bravo"`.
4. event of M2, `created_at T1`, `metadata_json {"status": "RUNNING"}`.
5. M3 = machine, `name "Charlie"`.
6. event of M3, `created_at T1`, `metadata_json {"status": "RUNNING"}`.
7. M4 = machine, `name "Delta"`.
8. event of M4, `created_at T1`, `metadata_json {"status": "IDLE"}`.

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id, latest_event_type=RUNNING, sort_dir="desc", skip=1, limit=1)`.

**Then**
1. returns: `ids(result) == [M2.id]`.

### MCH-SA-88 — with the status filter a machine of another workspace is not returned
- **Rules:** `search_advanced` R1, R12 [BUG-886]
- **Kind:** bug
- **Expect:** xfail BUG-886
- **Fails today on:** Then 1 (the call raises AttributeError: the status filter cannot be built)

**Given**
1. M1 = machine, `name "Alpha"`.
2. event of M1, `created_at T1`, `metadata_json {"status": "RUNNING"}`.
3. M9 = machine, `name "Other"`, but `workspace_id W2.id`, `factory_id F9.id`.
4. event of M9, `created_at T1`, `metadata_json {"status": "RUNNING"}`.

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id, latest_event_type=RUNNING)`.

**Then**
1. returns: `ids(result) == [M1.id]`.

### MCH-SA-89 — with the status filter a soft-deleted machine is not returned
- **Rules:** `search_advanced` R2, R12 [BUG-886]
- **Kind:** bug
- **Expect:** xfail BUG-886
- **Fails today on:** Then 1 (the call raises AttributeError: the status filter cannot be built)

**Given**
1. M1 = machine, `name "Alpha"`.
2. event of M1, `created_at T1`, `metadata_json {"status": "RUNNING"}`.
3. M2 = machine, `name "Bravo"`, but deleted.
4. event of M2, `created_at T1`, `metadata_json {"status": "RUNNING"}`.

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id, latest_event_type=RUNNING)`.

**Then**
1. returns: `ids(result) == [M1.id]`.

### MCH-SA-90 — sort_by "name" with sort_dir "asc" sorts by name ascending
- **Rules:** `search_advanced` R13, R15
- **Kind:** happy
- **Expect:** pass

**Given**
1. M1 = machine, `name "Press"`, but `created_at T2`.
2. M2 = machine, `name "Drill"`, but `created_at T3`.
3. M3 = machine, `name "Lathe"`, but `created_at T1`.

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id, sort_by="name", sort_dir="asc")`.

**Then**
1. returns: `ids(result) == [M2.id, M3.id, M1.id]`.

### MCH-SA-91 — sort_by "created_at" puts the earliest created machine first
- **Rules:** `search_advanced` R13, R16
- **Kind:** happy
- **Expect:** pass

**Given**
1. M1 = machine, `name "Press"`, but `created_at T2`.
2. M2 = machine, `name "Drill"`, but `created_at T3`.
3. M3 = machine, `name "Lathe"`, but `created_at T1`.

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id, sort_by="created_at")`.

**Then**
1. returns: `ids(result) == [M3.id, M1.id, M2.id]`.

### MCH-SA-92 — sort_by "maintenance_date" sorts by name without an error
- **Rules:** `search_advanced` R13
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1 = machine, `name "Press"`, but `created_at T2`.
2. M2 = machine, `name "Drill"`, but `created_at T3`.
3. M3 = machine, `name "Lathe"`, but `created_at T1`.

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id, sort_by="maintenance_date")`.

**Then**
1. returns: `ids(result) == [M2.id, M3.id, M1.id]`.

### MCH-SA-93 — sort_by "createdAt" sorts by name without an error
- **Rules:** `search_advanced` R13
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1 = machine, `name "Press"`, but `created_at T2`.
2. M2 = machine, `name "Drill"`, but `created_at T3`.
3. M3 = machine, `name "Lathe"`, but `created_at T1`.

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id, sort_by="createdAt")`.

**Then**
1. returns: `ids(result) == [M2.id, M3.id, M1.id]`.

### MCH-SA-94 — an empty sort_by sorts by name without an error
- **Rules:** `search_advanced` R13
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1 = machine, `name "Press"`, but `created_at T2`.
2. M2 = machine, `name "Drill"`, but `created_at T3`.
3. M3 = machine, `name "Lathe"`, but `created_at T1`.

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id, sort_by="")`.

**Then**
1. returns: `ids(result) == [M2.id, M3.id, M1.id]`.

### MCH-SA-95 — sort_by "CREATED_AT" in upper case sorts by name
- **Rules:** `search_advanced` R13
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1 = machine, `name "Press"`, but `created_at T2`.
2. M2 = machine, `name "Drill"`, but `created_at T3`.
3. M3 = machine, `name "Lathe"`, but `created_at T1`.

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id, sort_by="CREATED_AT")`.

**Then**
1. returns: `ids(result) == [M2.id, M3.id, M1.id]`.

### MCH-SA-96 — an unknown sort_by with sort_dir "desc" sorts by name descending
- **Rules:** `search_advanced` R13, R15
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1 = machine, `name "Press"`, but `created_at T2`.
2. M2 = machine, `name "Drill"`, but `created_at T3`.
3. M3 = machine, `name "Lathe"`, but `created_at T1`.

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id, sort_by="createdAt", sort_dir="desc")`.

**Then**
1. returns: `ids(result) == [M1.id, M3.id, M2.id]`.

### MCH-SA-97 — names of mixed case sort case-insensitively, ascending
- **Rules:** `search_advanced` R14
- **Kind:** happy
- **Expect:** pass

**Given**
1. M1 = machine, `name "Zulu"`.
2. M2 = machine, `name "apple"`.
3. M3 = machine, `name "Banana"`.

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id)`.

**Then**
1. returns: `names(result) == ["apple", "Banana", "Zulu"]`.

### MCH-SA-98 — names of mixed case sort case-insensitively, descending
- **Rules:** `search_advanced` R14, R15
- **Kind:** happy
- **Expect:** pass

**Given**
1. M1 = machine, `name "Zulu"`.
2. M2 = machine, `name "apple"`.
3. M3 = machine, `name "Banana"`.

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id, sort_dir="desc")`.

**Then**
1. returns: `names(result) == ["Zulu", "Banana", "apple"]`.

### MCH-SA-99 — ascending, names that differ only in case come back in id order
- **Rules:** `search_advanced` R14 [BUG-887]
- **Kind:** bug
- **Expect:** xfail BUG-887
- **Fails today on:** Then 1 (the database collation puts "bolt" before "Bolt", so the order is [M2, M1])

**Given**
1. M1 = machine, `name "Bolt"`.
2. M2 = machine, `name "bolt"`.

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [M1.id, M2.id]`.

### MCH-SA-100 — descending, names that differ only in case come back in id order
- **Rules:** `search_advanced` R14 [BUG-887]
- **Kind:** bug
- **Expect:** xfail BUG-887
- **Fails today on:** Then 1 (the database collation puts "Bolt" before "bolt" when descending, so the order is [M2, M1])

**Given**
1. M1 = machine, `name "bolt"`.
2. M2 = machine, `name "Bolt"`.

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id, sort_dir="desc")`.

**Then**
1. returns: `ids(result) == [M1.id, M2.id]`.

### MCH-SA-101 — ascending, identical names come back in id order
- **Rules:** `search_advanced` R14
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1 = machine, `name "Bolt"`.
2. M2 = machine, `name "Bolt"`.
3. M3 = machine, `name "Apex"`.

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [M3.id, M1.id, M2.id]`.

### MCH-SA-102 — descending, identical names still come back in ascending id order
- **Rules:** `search_advanced` R14, R15
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1 = machine, `name "Bolt"`.
2. M2 = machine, `name "Bolt"`.
3. M3 = machine, `name "Apex"`.

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id, sort_dir="desc")`.

**Then**
1. returns: `ids(result) == [M1.id, M2.id, M3.id]`.

### MCH-SA-103 — sort_dir "desc" sorts by name descending
- **Rules:** `search_advanced` R15
- **Kind:** happy
- **Expect:** pass

**Given**
1. M1 = machine, `name "Press"`.
2. M2 = machine, `name "Drill"`.
3. M3 = machine, `name "Lathe"`.

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id, sort_dir="desc")`.

**Then**
1. returns: `ids(result) == [M1.id, M3.id, M2.id]`.

### MCH-SA-104 — sort_dir "DESC" in upper case sorts ascending
- **Rules:** `search_advanced` R15
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1 = machine, `name "Press"`.
2. M2 = machine, `name "Drill"`.
3. M3 = machine, `name "Lathe"`.

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id, sort_dir="DESC")`.

**Then**
1. returns: `ids(result) == [M2.id, M3.id, M1.id]`.

### MCH-SA-105 — sort_dir "descending" sorts ascending
- **Rules:** `search_advanced` R15
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1 = machine, `name "Press"`.
2. M2 = machine, `name "Drill"`.
3. M3 = machine, `name "Lathe"`.

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id, sort_dir="descending")`.

**Then**
1. returns: `ids(result) == [M2.id, M3.id, M1.id]`.

### MCH-SA-106 — an empty sort_dir sorts ascending
- **Rules:** `search_advanced` R15
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1 = machine, `name "Press"`.
2. M2 = machine, `name "Drill"`.
3. M3 = machine, `name "Lathe"`.

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id, sort_dir="")`.

**Then**
1. returns: `ids(result) == [M2.id, M3.id, M1.id]`.

### MCH-SA-107 — sort_by "created_at" descending puts the earliest created machine last
- **Rules:** `search_advanced` R16, R15
- **Kind:** happy
- **Expect:** pass

**Given**
1. M1 = machine, `name "Press"`, but `created_at T2`.
2. M2 = machine, `name "Drill"`, but `created_at T3`.
3. M3 = machine, `name "Lathe"`, but `created_at T1`.

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id, sort_by="created_at", sort_dir="desc")`.

**Then**
1. returns: `ids(result) == [M2.id, M1.id, M3.id]`.

### MCH-SA-108 — ascending by created_at, machines created at the same time come back in id order
- **Rules:** `search_advanced` R16
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1 = machine, `name "Zulu"`, but `created_at T2`.
2. M2 = machine, `name "Mango"`, but `created_at T1`.
3. M3 = machine, `name "Apex"`, but `created_at T1`.

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id, sort_by="created_at")`.

**Then**
1. returns: `ids(result) == [M2.id, M3.id, M1.id]`.

### MCH-SA-109 — descending by created_at, machines created at the same time still come back in ascending id order
- **Rules:** `search_advanced` R16
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1 = machine, `name "Zulu"`, but `created_at T2`.
2. M2 = machine, `name "Mango"`, but `created_at T1`.
3. M3 = machine, `name "Apex"`, but `created_at T1`.

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id, sort_by="created_at", sort_dir="desc")`.

**Then**
1. returns: `ids(result) == [M1.id, M2.id, M3.id]`.

### MCH-SA-110 — machines inserted in one transaction share created_at and come back in id order
- **Rules:** `search_advanced` R16
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1 = machine, `name "Zulu"`.
2. M2 = machine, `name "Mango"`.
3. M3 = machine, `name "Apex"`.

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id, sort_by="created_at", sort_dir="desc")`.

**Then**
1. returns: `ids(result) == [M1.id, M2.id, M3.id]`.

### MCH-SA-111 — first window of two
- **Rules:** `search_advanced` R17
- **Kind:** happy
- **Expect:** pass

**Given**
1. M1 = machine, `name "Echo"`.
2. M2 = machine, `name "Alpha"`.
3. M3 = machine, `name "Delta"`.
4. M4 = machine, `name "Bravo"`.
5. M5 = machine, `name "Charlie"`.

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id, skip=0, limit=2)`.

**Then**
1. returns: `ids(result) == [M2.id, M4.id]`.

### MCH-SA-112 — second window of two continues without repeat or gap
- **Rules:** `search_advanced` R17
- **Kind:** happy
- **Expect:** pass

**Given**
1. M1 = machine, `name "Echo"`.
2. M2 = machine, `name "Alpha"`.
3. M3 = machine, `name "Delta"`.
4. M4 = machine, `name "Bravo"`.
5. M5 = machine, `name "Charlie"`.

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id, skip=2, limit=2)`.

**Then**
1. returns: `ids(result) == [M5.id, M3.id]`.

### MCH-SA-113 — last window is short
- **Rules:** `search_advanced` R17
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1 = machine, `name "Echo"`.
2. M2 = machine, `name "Alpha"`.
3. M3 = machine, `name "Delta"`.
4. M4 = machine, `name "Bravo"`.
5. M5 = machine, `name "Charlie"`.

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id, skip=4, limit=2)`.

**Then**
1. returns: `ids(result) == [M1.id]`.

### MCH-SA-114 — skip and limit are applied after filtering
- **Rules:** `search_advanced` R17, R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. M1 = machine, `name "Alpha"`.
2. M2 = machine, `name "Bravo"`, but `factory_id F2.id`.
3. M3 = machine, `name "Charlie"`.
4. M4 = machine, `name "Delta"`, but `factory_id F2.id`.
5. M5 = machine, `name "Echo"`.

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id, factory_id=F1.id, skip=1, limit=1)`.

**Then**
1. returns: `ids(result) == [M3.id]`.

### MCH-SA-115 — skip and limit are applied after ordering
- **Rules:** `search_advanced` R17, R15
- **Kind:** happy
- **Expect:** pass

**Given**
1. M1 = machine, `name "Echo"`.
2. M2 = machine, `name "Alpha"`.
3. M3 = machine, `name "Delta"`.
4. M4 = machine, `name "Bravo"`.
5. M5 = machine, `name "Charlie"`.

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id, sort_dir="desc", skip=1, limit=2)`.

**Then**
1. returns: `ids(result) == [M3.id, M5.id]`.

### MCH-SA-116 — default limit returns the first 100 of 101 machines by name
- **Rules:** `search_advanced` R17
- **Kind:** boundary
- **Expect:** pass
- **Author:** claude — bulk setup (a loop over 101 machines) outside the Conventions vocabulary

**Given**
1. 101 machines N1 … N101, inserted in the order N101, N100, … N1 (descending k); machine Nk (k = 1 … 101) has `name` = `f"M{k:03d}"` (so "M001" … "M101") and is otherwise the default machine.

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.
2. returns: `result[0].name == "M001"`.
3. returns: `result[99].name == "M100"`.
4. returns: `"M101" not in names(result)`.

### MCH-SA-117 — an explicit limit of 101 returns all 101 machines
- **Rules:** `search_advanced` R17
- **Kind:** boundary
- **Expect:** pass
- **Author:** claude — bulk setup (a loop over 101 machines) outside the Conventions vocabulary

**Given**
1. 101 machines N1 … N101, inserted in the order N101, N100, … N1 (descending k); machine Nk (k = 1 … 101) has `name` = `f"M{k:03d}"` (so "M001" … "M101") and is otherwise the default machine.

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id, limit=101)`.

**Then**
1. returns: `len(result) == 101`.
2. returns: `result[0].name == "M001"`.
3. returns: `result[100].name == "M101"`.

### MCH-SA-118 — limit 0 returns an empty list
- **Rules:** `search_advanced` R18
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1 = machine, `name "Lathe"`.

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id, limit=0)`.

**Then**
1. returns: `result == []`.

### MCH-SA-119 — skip equal to the number of matching machines returns an empty list
- **Rules:** `search_advanced` R18
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1 = machine, `name "Lathe"`.
2. M2 = machine, `name "Press"`.

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id, skip=2)`.

**Then**
1. returns: `result == []`.

### MCH-SA-120 — skip one below the number of matching machines returns the last machine
- **Rules:** `search_advanced` R18, R17
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1 = machine, `name "Lathe"`.
2. M2 = machine, `name "Press"`.

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id, skip=1)`.

**Then**
1. returns: `ids(result) == [M2.id]`.

### MCH-SA-121 — negative limit is rejected by the database and nothing changes
- **Rules:** `search_advanced` R18, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. M1 = machine, `name "Lathe"`.

**When**
- `dao.search_advanced(db, workspace_id=W1.id, limit=-1)`.

**Then**
1. raises: `DataError`.
2. raises: `exc.value.orig.pgcode == "2201W"`.
3. raises: `"LIMIT must not be negative" in str(exc.value.orig)`.
4. nothing written: nothing written.
5. unchanged: unchanged(M1).

### MCH-SA-122 — negative skip is rejected by the database and nothing changes
- **Rules:** `search_advanced` R18, Errors row 2
- **Kind:** error
- **Expect:** pass

**Given**
1. M1 = machine, `name "Lathe"`.

**When**
- `dao.search_advanced(db, workspace_id=W1.id, skip=-1)`.

**Then**
1. raises: `DataError`.
2. raises: `exc.value.orig.pgcode == "2201X"`.
3. raises: `"OFFSET must not be negative" in str(exc.value.orig)`.
4. nothing written: nothing written.
5. unchanged: unchanged(M1).

### MCH-SA-123 — all filters combine with AND: a machine failing any one filter is left out
- **Rules:** `search_advanced` R13a, R4, R5, R7, R9, R10, R11
- **Kind:** happy
- **Expect:** pass

**Given**
1. M1 = machine, `name "Bolt A"`, but `is_running True`, `model_number "MX-1"`, `manufacturer "Acme"`.
2. assignment of M1 to S1.
3. M2 = machine, `name "Bolt B"`, but `factory_id F2.id`, `is_running True`, `model_number "MX-1"`, `manufacturer "Acme"`.
4. assignment of M2 to S1.
5. M3 = machine, `name "Bolt C"`, but `is_running True`, `model_number "MX-1"`, `manufacturer "Acme"`.
6. assignment of M3 to S2.
7. M4 = machine, `name "Bolt D"`, but `model_number "MX-1"`, `manufacturer "Acme"`. (`is_running False`.)
8. assignment of M4 to S1.
9. M5 = machine, `name "Nut E"`, but `is_running True`, `model_number "MX-1"`, `manufacturer "Acme"`.
10. assignment of M5 to S1.
11. M6 = machine, `name "Bolt F"`, but `is_running True`, `manufacturer "Acme"`. (`model_number None`.)
12. assignment of M6 to S1.
13. M7 = machine, `name "Bolt G"`, but `is_running True`, `model_number "MX-1"`. (`manufacturer None`.)
14. assignment of M7 to S1.

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id, factory_id=F1.id, factory_section_id=S1.id, is_running=True, search="bolt", has_model_number=True, has_manufacturer=True)`.

**Then**
1. returns: `ids(result) == [M1.id]`.

### MCH-SA-124 — the three search alternatives are one group: a match in another factory is not returned
- **Rules:** `search_advanced` R13a, R9, R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1 = machine, `name "Bolt cutter"`.
2. M2 = machine, `name "Lathe"`, but `factory_id F2.id`, `model_number "BOLT-9"`.
3. M3 = machine, `name "Press"`, but `factory_id F2.id`, `manufacturer "Boltco"`.
4. M4 = machine, `name "Drill"`.

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id, factory_id=F1.id, search="bolt")`.

**Then**
1. returns: `ids(result) == [M1.id]`.

### MCH-SA-125 — the search alternatives stay one group next to the soft-delete filter and is_running
- **Rules:** `search_advanced` R13a, R9, R2, R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1 = machine, `name "Bolt cutter"`, but `is_running True`.
2. M2 = machine, `name "Lathe"`, but `manufacturer "Boltco"`. (`is_running False`.)
3. M3 = machine, `name "Press"`, but `is_running True`, `manufacturer "Boltco"`, deleted.
4. M4 = machine, `name "Drill"`, but `is_running True`.

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id, is_running=True, search="bolt")`.

**Then**
1. returns: `ids(result) == [M1.id]`.

### MCH-SA-126 — section and is_running filters combine with AND
- **Rules:** `search_advanced` R13a, R5, R7
- **Kind:** happy
- **Expect:** pass

**Given**
1. M1 = machine, `name "Alpha"`, but `is_running True`.
2. assignment of M1 to S1.
3. M2 = machine, `name "Bravo"`.
4. assignment of M2 to S1.
5. M3 = machine, `name "Charlie"`, but `is_running True`.
6. assignment of M3 to S2.
7. M4 = machine, `name "Delta"`, but `is_running True`. (No assignment.)

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id, factory_section_id=S1.id, is_running=True)`.

**Then**
1. returns: `ids(result) == [M1.id]`.

### MCH-SA-127 — a filter, a created_at descending sort and paging work together
- **Rules:** `search_advanced` R13a, R16, R17
- **Kind:** happy
- **Expect:** pass

**Given**
1. M1 = machine, `name "Alpha"`, but `is_running True`, `created_at T1`.
2. M2 = machine, `name "Bravo"`, but `created_at T3`.
3. M3 = machine, `name "Charlie"`, but `is_running True`, `created_at T3`.
4. M4 = machine, `name "Delta"`, but `is_running True`, `created_at T2`.

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id, is_running=True, sort_by="created_at", sort_dir="desc", skip=1, limit=2)`.

**Then**
1. returns: `ids(result) == [M4.id, M1.id]`.

### MCH-SA-128 — once the factory is no longer deleted its machine is listed again, exactly as it was
- **Rules:** `search_advanced` R3c
- **Kind:** soft-delete
- **Expect:** pass
- **Author:** claude — changes the standing row FD directly

**Given**
1. M1 = machine, `name "Lathe"`.
2. MD = machine, `name "Press"`, but `factory_id FD.id`, `is_running True`, `model_number "P-4"`. (FD is the soft-deleted factory; MD itself is live.)
3. AD = assignment of MD to S1.
4. FD made live again (Conventions). Nothing is done to MD or AD.

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id)`.

**Then**
1. returns: `names(result) == ["Lathe", "Press"]`.
2. returns: `by_id(result, MD).is_running is True`.
3. returns: `by_id(result, MD).model_number == "P-4"`.
4. returns: `by_id(result, MD).factory_section_id == S1.id`.
5. returns: `by_id(result, MD).factory_section_name == "Section One"`.
6. unchanged: unchanged(MD).
7. re-read MD: `is_deleted is False`, `is_active is True`.
8. re-read MD: `deleted_at is None`, `deleted_by is None`.
9. re-read MD: `updated_at is None`.
10. re-read AD: `machine_id == MD.id`, `factory_section_id == S1.id`.
11. nothing written: nothing written.

### MCH-SA-129 — once the factory is no longer deleted its id works as the factory filter again
- **Rules:** `search_advanced` R3c, R4
- **Kind:** soft-delete
- **Expect:** pass
- **Author:** claude — changes the standing row FD directly

**Given**
1. M1 = machine, `name "Lathe"`.
2. MD = machine, `name "Press"`, but `factory_id FD.id`, `is_running True`, `model_number "P-4"`. (FD is the soft-deleted factory; MD itself is live.)
3. AD = assignment of MD to S1.
4. FD made live again (Conventions). Nothing is done to MD or AD.

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id, factory_id=FD.id)`.

**Then**
1. returns: `ids(result) == [MD.id]`.
2. returns: `result[0].is_running is True`.
3. returns: `result[0].model_number == "P-4"`.
4. returns: `result[0].factory_section_name == "Section One"`.
5. unchanged: unchanged(MD).
6. re-read MD: `factory_id == FD.id`, `is_deleted is False`.

### MCH-SA-130 — a tab before and a newline after the search text are removed before matching
- **Rules:** `search_advanced` R8 [BUG-892]
- **Kind:** bug
- **Expect:** xfail BUG-892
- **Fails today on:** Then 1 (the text is used with its tab and newline, which no machine contains, so the list is empty)

**Given**
1. M1 = machine, `name "Bolt cutter"`.
2. M2 = machine, `name "Lathe"`.

**When**
- `result = dao.search_advanced(db, workspace_id=W1.id, search="\tbolt\n")`.

**Then**
1. returns: `ids(result) == [M1.id]`.


## Inherited `BaseDAO` methods on `Machine`

### MCH-INH-01 — create with a dict of the three required values stores a machine with the model defaults
- **Rules:** inherited R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. No machines exist.

**When**
- `result = dao.create(db, obj_in={"workspace_id": W1.id, "name": "Press", "factory_id": F1.id})`.

**Then**
1. returns: `result.id is not None`.
2. returns: `result.factory_section_id is None`.
3. re-read the returned row: `name == "Press"`, `workspace_id == W1.id`, `factory_id == F1.id`.
4. re-read the returned row: `is_running is False`, `is_active is True`, `is_deleted is False`.
5. re-read the returned row: `created_at is not None`, `updated_at is None`.
6. re-read the returned row: `model_number is None`, `manufacturer is None`, `note is None`.
7. re-read the returned row: `deleted_at is None`, `deleted_by is None`.
8. count: `machines` has exactly 1 row.
9. count: `machine_section_assignments` has exactly 0 rows.

### MCH-INH-02 — create with a MachineCreate schema raises and adds no machine
- **Rules:** inherited R2, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. No machines exist.

**When**
- `dao.create(db, obj_in=MachineCreate(name="Press", factory_id=F1.id))`.

**Then**
1. raises: `AttributeError`.
2. nothing written: nothing written.
3. count: `machines` has exactly 0 rows.

### MCH-INH-03 — create with a dict holding factory_section_id None raises and adds no machine
- **Rules:** inherited R2, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. No machines exist.

**When**
- `dao.create(db, obj_in={"workspace_id": W1.id, "name": "Press", "factory_id": F1.id, "factory_section_id": None})`.

**Then**
1. raises: `AttributeError`.
2. nothing written: nothing written.
3. count: `machines` has exactly 0 rows.

### MCH-INH-04 — create with a dict holding a real section id raises and adds no machine or assignment
- **Rules:** inherited R2, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. No machines exist.

**When**
- `dao.create(db, obj_in={"workspace_id": W1.id, "name": "Press", "factory_id": F1.id, "factory_section_id": S1.id})`.

**Then**
1. raises: `AttributeError`.
2. nothing written: nothing written.
3. count: `machines` has exactly 0 rows.
4. count: `machine_section_assignments` has exactly 0 rows.

### MCH-INH-05 — update with a dict of real columns sets them
- **Rules:** inherited R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. M1 = machine, `name "Press"`.

**When**
- `result = dao.update(db, db_obj=M1, obj_in={"name": "B", "updated_by": U2.id})`.

**Then**
1. returns: `result.id == M1.id`.
2. re-read M1: `name == "B"`, `updated_by == U2.id`.
3. re-read M1: `updated_at is not None`.
4. re-read M1: `factory_id == F1.id`, `is_running is False`.

### MCH-INH-06 — update with a dict sets is_running
- **Rules:** inherited R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. M1 = machine, `name "Press"`.

**When**
- `result = dao.update(db, db_obj=M1, obj_in={"is_running": True})`.

**Then**
1. returns: `result.id == M1.id`.
2. re-read M1: `is_running is True`.
3. re-read M1: `name == "Press"`, `updated_by is None`.

### MCH-INH-07 — update with the current value issues no UPDATE and leaves updated_at empty
- **Rules:** inherited R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1 = machine, `name "Press"`.

**When**
- `result = dao.update(db, db_obj=M1, obj_in={"name": "Press"})`.

**Then**
1. returns: `result.id == M1.id`.
2. re-read M1: `name == "Press"`.
3. re-read M1: `updated_at is None`.

### MCH-INH-08 — update with a MachineUpdate that does not set factory_section_id applies the other field
- **Rules:** inherited R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. M1 = machine, `name "Press"`.
2. A1 = assignment of M1 to S1.

**When**
- `result = dao.update(db, db_obj=M1, obj_in=MachineUpdate(name="B"))`. `factory_section_id` is not sent.

**Then**
1. returns: `result.id == M1.id`.
2. re-read M1: `name == "B"`.
3. re-read A1: `factory_section_id == S1.id`.
4. count: `machine_section_assignments` has exactly 1 row.

### MCH-INH-09 — update with a MachineUpdate whose factory_section_id is None applies the other field
- **Rules:** inherited R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1 = machine, `name "Press"`.
2. A1 = assignment of M1 to S1.

**When**
- `result = dao.update(db, db_obj=M1, obj_in=MachineUpdate(name="B", factory_section_id=None))`.

**Then**
1. returns: `result.id == M1.id`.
2. re-read M1: `name == "B"`.
3. re-read A1: `factory_section_id == S1.id`.
4. count: `machine_section_assignments` has exactly 1 row.

### MCH-INH-10 — update with a dict holding a section id raises and saves nothing
- **Rules:** inherited R4, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. M1 = machine, `name "Press"`.

**When**
- `dao.update(db, db_obj=M1, obj_in={"name": "B", "factory_section_id": S1.id})`.

**Then**
1. raises: `AttributeError`.
2. unchanged: unchanged(M1).
3. re-read M1: `name == "Press"`.
4. re-read M1: `updated_at is None`.
5. nothing written: nothing written.
6. count: `machine_section_assignments` has exactly 0 rows.

### MCH-INH-11 — update with a dict holding factory_section_id None raises and saves nothing
- **Rules:** inherited R4, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. M1 = machine, `name "Press"`.

**When**
- `dao.update(db, db_obj=M1, obj_in={"name": "B", "factory_section_id": None})`.

**Then**
1. raises: `AttributeError`.
2. unchanged: unchanged(M1).
3. re-read M1: `name == "Press"`.
4. re-read M1: `updated_at is None`.
5. nothing written: nothing written.

### MCH-INH-12 — update with a MachineUpdate whose factory_section_id is a number raises and saves nothing
- **Rules:** inherited R4, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. M1 = machine, `name "Press"`.

**When**
- `dao.update(db, db_obj=M1, obj_in=MachineUpdate(name="B", factory_section_id=S1.id))`.

**Then**
1. raises: `AttributeError`.
2. unchanged: unchanged(M1).
3. re-read M1: `name == "Press"`.
4. re-read M1: `updated_at is None`.
5. nothing written: nothing written.
6. count: `machine_section_assignments` has exactly 0 rows.

### MCH-INH-13 — a refused update leaves an existing assignment pointing at its old section
- **Rules:** inherited R4
- **Kind:** error
- **Expect:** pass

**Given**
1. M1 = machine, `name "Press"`.
2. A1 = assignment of M1 to S1.

**When**
- `dao.update(db, db_obj=M1, obj_in={"factory_section_id": S2.id})`.

**Then**
1. raises: `AttributeError`.
2. unchanged: unchanged(A1).
3. re-read A1: `machine_id == M1.id`, `factory_section_id == S1.id`.
4. unchanged: unchanged(M1).
5. count: `machine_section_assignments` has exactly 1 row.

### MCH-INH-14 — get returns a soft-deleted machine
- **Rules:** inherited R5
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. M1 = machine, `name "Press"`, but deleted.

**When**
- `result = dao.get(db, M1.id)`.

**Then**
1. returns: `result.id == M1.id`.
2. returns: `result.is_deleted is True`.

### MCH-INH-15 — get returns the machine of a soft-deleted factory
- **Rules:** inherited R5
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. MD = machine, `name "Press"`, but `factory_id FD.id`. (FD is the soft-deleted factory; MD itself is live.)

**When**
- `result = dao.get(db, MD.id)`.

**Then**
1. returns: `result.id == MD.id`.
2. returns: `result.factory_id == FD.id`.

### MCH-INH-16 — get_by_id_and_workspace returns a soft-deleted machine
- **Rules:** inherited R5
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. M1 = machine, `name "Press"`, but deleted.

**When**
- `result = dao.get_by_id_and_workspace(db, id=M1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == M1.id`.
2. returns: `result.is_deleted is True`.

### MCH-INH-17 — get_by_id_and_workspace returns the machine of a soft-deleted factory
- **Rules:** inherited R5
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. MD = machine, `name "Press"`, but `factory_id FD.id`. (FD is the soft-deleted factory; MD itself is live.)

**When**
- `result = dao.get_by_id_and_workspace(db, id=MD.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == MD.id`.
2. returns: `result.factory_id == FD.id`.

### MCH-INH-18 — get_by_workspace returns soft-deleted machines and machines of a soft-deleted factory
- **Rules:** inherited R5
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. M1 = machine, `name "Lathe"`.
2. M2 = machine, `name "Press"`, but deleted.
3. MD = machine, `name "Drill"`, but `factory_id FD.id`. (FD is the soft-deleted factory; MD itself is live.)
4. M9 = machine, `name "Other"`, but `workspace_id W2.id`, `factory_id F9.id`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [M1.id, M2.id, MD.id]`.


## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| Overview "Integration-only behavior": `skip >= 0`, `1 <= limit <= 1000` | `GET /machines/` (endpoint) | 422 for `skip=-1`, `limit=0`, `limit=1001`. Here the DAO lets Postgres reject negatives (MCH-SA-121, SA-122) and `limit=0` returns `[]` by rule (MCH-SA-118). |
| Q2 — unknown `sort_by` / `sort_dir` rejected with 422 | `MachineManager.search_machines` / `GET /machines/` | Validation of the two values. Here the lenient fallback is intended (MCH-SA-92 … SA-96, SA-104 … SA-106). |
| `sort_by="maintenance_date"` and the maintenance-window filter (`skip=0, limit=10_000`, paging in Python) | `MachineManager.search_machines` spec | The real maintenance-date order. Here the value just falls back to name (MCH-SA-92). |
| Q3 — trimming `model_number` / `manufacturer` when saved | machine form schema / `MachineManager` spec | A whitespace-only value is not stored. Here the filter compares what is stored (MCH-SA-61 … SA-64). |
| `soft_delete` Visibility: 404 for a missing / other-workspace machine, 400 "Machine is already deleted", the "deactivated" activity event | `MachineManager.delete_machine` spec | The checks before the DAO call and the event. Here the DAO deletes whatever it is given (MCH-SD-05, SD-09) and writes no event (MCH-SD-12). |
| Cross-spec note: duplicate-name check uses `get_by_factory` with the default limit of 100 and exact `==` | `MachineManager._check_name_exists_in_factory` spec | A duplicate beyond the first 100 machines; case / whitespace compare (HR-2). |
| Cross-spec note: work-order generation calls with `limit=1000` (BUG-342) | `app/utils/work_order_generation.py` spec | No cap on machines per factory / section. |
| Cross-spec note: `search_machines(include_deleted=True)` is unreachable from the API | `MachineManager.search_machines` spec | Whether the flag is exposed or removed. |
| Cross-spec note: displayed status picks "latest" by timestamp only (tie may disagree with R12a after the BUG-886 fix) | `MachineActivityEventDAO.get_latest_status_map` spec | Tie-break by highest `id`, the same as MCH-SA-75, SA-76. |
| Inherited `get`, `get_multi`, `create`, `update`, `remove`, `get_by_workspace`, `get_by_id_and_workspace` — generic behaviour (including "flushed, not committed" of `create` / `update`, base `update` R8) | `tests/unit/dao/base.spec.md` / `base.cases.md` | Not repeated here; only what the `Machine` model changes has cards (MCH-INH-01 … INH-18). |
| `get_by_factory` R6, `get_by_section` R7 — strict proof of the `ORDER BY` | a test with a statement recorder (emitted SQL has `ORDER BY lower(name), id`), e.g. in the work-order-generation tests | The six BUG-343 cards here are non-strict xfails and may pass by accident today; they only become real protection after the fix. |
| Spec follow-up FU-3 — the "restore machine" feature (nothing calls `restore` today) | machine manager / service / endpoint spec (feature to build) | 404 for a missing / other-workspace machine and the answer for a machine that is not deleted; who restored and a "restored" activity entry (Q8); refusing a name now used by another live machine of the factory with 409 (Q9); the answer for a machine whose factory is soft-deleted. Here the DAO restores whatever it is given (MCH-RS-09, RS-10, RS-13, RS-16), records nobody (MCH-RS-04 … RS-06) and checks no name (MCH-RS-22). |
| Spec follow-up FU-4 — undoing a factory's soft delete (`DAOFactory.restore` has no caller) | factory DAO / manager spec | The undo itself. Here only its effect on machines is tested, with the factory row changed directly (MCH-GF-30, GS-30, SA-128, SA-129, RS-19). |

## Spec gaps
| # | Where | What is missing | How it blocked the design |
|---|---|---|---|
| 1 | `get_by_section` R3a | **CLOSED by spec revision 2026-10-10 (1):** `get_by_section` R3b (2) now states it. | MCH-GS-13 stands as designed; its Rules line now cites R3b. |
| 2 | `search_advanced` R8 | **CLOSED by spec revision 2026-10-10 (1):** whitespace = what Python's `str.strip()` removes (spaces, tabs, newlines). | MCH-SA-40 stands as designed; MCH-SA-130 added for the trim with a tab and a newline. |
| 3 | `search_advanced` R9 | A search text that is only a backslash, or ends in a backslash (`"a\"`), is not specified (today it may make Postgres reject the pattern). | No card. |
| 4 | `search_advanced` R12 / R12c | Not specified: a `"status"` value that is not one of the four names (`"running"` in lower case, `"BROKEN"`, JSON `null`, a number). | No card; R12c cards cover only "no metadata" and "no `status` key". |
| 5 | `search_advanced` Errors rows 1–2 | The `.orig` exception classes are given for `get_by_factory` but not for `search_advanced` (only `pgcode`). | Not blocking: MCH-SA-121, SA-122 assert `pgcode` and the message only. |
| 6 | `get_by_factory`, `get_by_section` | "Side effects: none" but no numbered "changes nothing in the database" rule for the general case. Partly closed by the spec revision: the new R3b (1) states it for the machines of a soft-deleted factory. | Not blocking: MCH-GF-14, GF-31, GS-14, GS-31 cite R3b; GS-16 and the four error cards assert nothing written / unchanged. |
| 7 | `soft_delete` Inputs (`deleted_by`: "`None` is stored as `NULL`") | Stated in the Inputs table only, not as a rule. | Not blocking: MCH-SD-11 cites R1 + Inputs. |
| 8 | `search_advanced` R14 | "Identical names come back in `id` ascending order — in both directions": the `Today` note covers only case-only differences, so whether identical names already hold today is inferred, not stated. | MCH-SA-101, SA-102 are designed as **pass** cards. If they fail today they belong to BUG-887 (xfail). |
| 9 | `search_advanced` R3a × R12 | R3a says "whatever the other filters"; a card combining the soft-deleted factory with `latest_event_type` would be an xfail of two bugs at once. | No such card; R3a is combined with the section, `is_running` and search filters (MCH-SA-18). |
| 10 | Inherited R3 (`update` "behaves as base spec `update` R1, R7, R8") | The return value of `update` (same instance or not) is not restated here. | MCH-INH-05 … INH-09 assert `result.id == M1.id` only. |
| 11 | Overview, Model facts (`Factory`) × `restore` R7 | R7 says the factory's `deleted_at` / `deleted_by` stay unchanged and the designer note sets them, but the `Factory` model facts list only `is_active` / `is_deleted`: the two columns' types and whether `deleted_by` is a foreign key to `profiles` are not stated. | Not blocking: MCH-RS-16 assumes a naive datetime and a profile id (`T0`, `U1.id`), the same as on machines and sections. Without a stamp on the factory the card could not see a restore that clears it. |
| 12 | `restore` R1 / R4 | Not specified: a machine in a mixed state — `is_deleted = True` with `is_active = True`, or deleted with an empty stamp (`deleted_at` / `deleted_by` `None`). R1 covers the fully deleted machine, R4 the two live ones. | No card. (The spec says no application path produces other states.) |
| 13 | `restore` R7a × `search_advanced` R3a "whatever the other filters" | A restored machine of a soft-deleted factory combined with further filters (section, search, `is_running`) is not asked for by R7a. | No such card; MCH-RS-17 checks the unfiltered list and the factory's own id, MCH-SA-18 already combines R3a with the other filters. |
| 14 | Review P1 "Reading note" | The rules R3a–R3c of the three lists and `restore` R7 / R7a rest on the main session's reading of the reviewer's sentence ("hidden, not a cascading soft delete"), which the reviewer has not confirmed in those words. | Not blocking: the cards are designed to the rules as written; the Reviewer summary lists exactly which cards change if the reading is wrong. |

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `get_by_factory` | R1 | MCH-GF-01, GF-02, GF-03, GF-04, GF-05, GF-14 |
| `get_by_factory` | R2 | MCH-GF-07, GF-08, GF-11, GF-17 |
| `get_by_factory` | R3 | MCH-GF-06, GF-09, GF-10, GF-11 |
| `get_by_factory` | R3a [BUG-891] | MCH-GF-12 (xfail) |
| `get_by_factory` | R3b | (1) nothing altered: MCH-GF-14, GF-31 · (2) inactive factory: GF-13 · (3) factory no longer deleted: GF-30 |
| `get_by_factory` | R4 | MCH-GF-15, GF-16, GF-17, GF-18, GF-19, GF-20, GF-23 |
| `get_by_factory` | R5 | MCH-GF-21, GF-22, GF-23, GF-24, GF-25 |
| `get_by_factory` | R6 [BUG-343] | MCH-GF-20, GF-26, GF-27 (non-strict xfail) |
| `get_by_factory` | R7 | MCH-GF-01, GF-28 |
| `get_by_factory` | R8 | MCH-GF-29 |
| `get_by_factory` | Errors row 1 (negative `limit`) | MCH-GF-24 |
| `get_by_factory` | Errors row 2 (negative `skip`) | MCH-GF-25 |
| `get_by_section` | R1 | MCH-GS-01, GS-02, GS-03, GS-14 |
| `get_by_section` | R2 | MCH-GS-04, GS-05, GS-06, GS-07, GS-08, GS-11, GS-18 |
| `get_by_section` | R3 | MCH-GS-03, GS-09, GS-10, GS-11 |
| `get_by_section` | R3a [BUG-891] | MCH-GS-12 (xfail) |
| `get_by_section` | R3b | (1) nothing altered: MCH-GS-14, GS-31 · (2) inactive factory: GS-13 · (3) factory no longer deleted: GS-30 |
| `get_by_section` | R4 [BUG-889] | MCH-GS-15 (xfail), GS-16 |
| `get_by_section` | R5 | MCH-GS-17, GS-18, GS-19, GS-20, GS-21, GS-22, GS-23, GS-24, GS-25, GS-26 |
| `get_by_section` | R6 | MCH-GS-01 |
| `get_by_section` | R7 [BUG-343] | MCH-GS-21, GS-27, GS-28 (non-strict xfail) |
| `get_by_section` | R8 | MCH-GS-29 |
| `get_by_section` | Errors (negative `limit`, as `get_by_factory`) | MCH-GS-25 |
| `get_by_section` | Errors (negative `skip`, as `get_by_factory`) | MCH-GS-26 |
| `soft_delete` | R1 | MCH-SD-01, SD-11, SD-13 |
| `soft_delete` | R2 | MCH-SD-02, SD-03, SD-12 |
| `soft_delete` | R3 | MCH-SD-04 |
| `soft_delete` | R4 | MCH-SD-05 |
| `soft_delete` | R5 | MCH-SD-01, SD-06, SD-07, SD-08; "`restore` undoes the delete": MCH-RS-20, RS-21 |
| `soft_delete` | R6 | MCH-SD-09 |
| `soft_delete` | R7 | MCH-SD-10 |
| `soft_delete` | Errors row 1 (`deleted_by` references no profile) | MCH-SD-10 |
| `soft_delete` | Side effects (one row, no activity event) | MCH-SD-12 |
| `restore` | R1 | MCH-RS-01 |
| `restore` | R2 | MCH-RS-02, RS-03 |
| `restore` | R2a (Q8) | MCH-RS-04, RS-05, RS-06 |
| `restore` | R3 | MCH-RS-07, RS-08 |
| `restore` | R4 | MCH-RS-09, RS-10 |
| `restore` | R5 | MCH-RS-01, RS-11, RS-12 |
| `restore` | R6 | MCH-RS-13, RS-14, RS-15 |
| `restore` | R7 | MCH-RS-16, RS-19 |
| `restore` | R7a [BUG-890] [BUG-891] | MCH-RS-17 (xfail BUG-890), RS-18 (xfail BUG-891); second sentence (holds today): RS-19 |
| `restore` | R8 | MCH-RS-20, RS-21 |
| `restore` | R9 (Q9) | MCH-RS-22 |
| `restore` | Errors (none) | no error row to test; MCH-RS-09, RS-10, RS-16, RS-22 are the "no error is raised" paths |
| `restore` | Side effects (at most one row, no activity event, no other table) | MCH-RS-06, RS-09, RS-14, RS-15 |
| `search_advanced` | Returns (section data loaded) | MCH-SA-14, SA-26 |
| `search_advanced` | R1 | MCH-SA-02, SA-03, SA-04, SA-05, SA-06, SA-07, SA-08, SA-88 (xfail BUG-886) |
| `search_advanced` | R2 | MCH-SA-09, SA-10, SA-11, SA-12, SA-125, SA-89 (xfail BUG-886) |
| `search_advanced` | R3 | MCH-SA-01, SA-13, SA-14, SA-71 |
| `search_advanced` | R3a [BUG-890] | MCH-SA-15, SA-16, SA-17, SA-18 (all xfail) |
| `search_advanced` | R3b | MCH-SA-19, SA-20, SA-21 |
| `search_advanced` | R3c | MCH-SA-128 (no filter), SA-129 (that factory's id) |
| `search_advanced` | R4 | MCH-SA-04, SA-05, SA-20, SA-22, SA-23, SA-24, SA-25, SA-114, SA-123, SA-124, SA-129 |
| `search_advanced` | R5 | MCH-SA-06, SA-25, SA-26, SA-27, SA-28, SA-29, SA-123, SA-126 |
| `search_advanced` | R6 | MCH-SA-30, SA-31, SA-32 |
| `search_advanced` | R6a [BUG-889] | MCH-SA-33 (xfail), SA-34 |
| `search_advanced` | R7 | MCH-SA-25, SA-35, SA-36, SA-123, SA-125, SA-126 |
| `search_advanced` | R8 [BUG-892] | MCH-SA-37, SA-38, SA-44, SA-45 (pass); SA-39, SA-40, SA-41, SA-42, SA-43, SA-130 (xfail) |
| `search_advanced` | R9 [BUG-888] | MCH-SA-07, SA-46, SA-47, SA-48, SA-49, SA-50, SA-51, SA-52, SA-53, SA-54, SA-57, SA-123, SA-124, SA-125 (pass); SA-55, SA-56, SA-58, SA-59, SA-60 (xfail) |
| `search_advanced` | R10 | MCH-SA-25, SA-61, SA-62, SA-65, SA-66, SA-123 |
| `search_advanced` | R11 | MCH-SA-25, SA-63, SA-64, SA-65, SA-66, SA-123 |
| `search_advanced` | R12 [BUG-886] | MCH-SA-67, SA-68, SA-69, SA-70, SA-88, SA-89 (xfail); SA-25, SA-71 (`None` = no filter, pass) |
| `search_advanced` | R12a [BUG-886] | MCH-SA-72, SA-73, SA-74, SA-75, SA-76 |
| `search_advanced` | R12b [BUG-886] | MCH-SA-77, SA-78, SA-79 |
| `search_advanced` | R12c [BUG-886] | MCH-SA-80, SA-81 |
| `search_advanced` | R12d [BUG-886] | MCH-SA-82, SA-83 |
| `search_advanced` | R12e [BUG-886] | MCH-SA-84, SA-85, SA-86, SA-87 |
| `search_advanced` | R13 | MCH-SA-01, SA-90, SA-91, SA-92, SA-93, SA-94, SA-95, SA-96 |
| `search_advanced` | R13a | MCH-SA-30, SA-50, SA-65, SA-66, SA-123, SA-124, SA-125, SA-126, SA-127; SA-85, SA-86 (xfail BUG-886) |
| `search_advanced` | R14 [BUG-887] | MCH-SA-97, SA-98, SA-101, SA-102 (pass); SA-99, SA-100 (xfail) |
| `search_advanced` | R15 | MCH-SA-01, SA-90, SA-96, SA-98, SA-102, SA-103, SA-104, SA-105, SA-106, SA-107, SA-115 |
| `search_advanced` | R16 | MCH-SA-91, SA-107, SA-108, SA-109, SA-110, SA-127 |
| `search_advanced` | R17 | MCH-SA-10, SA-111, SA-112, SA-113, SA-114, SA-115, SA-116, SA-117, SA-120, SA-127; SA-87 (xfail BUG-886) |
| `search_advanced` | R18 | MCH-SA-118, SA-119, SA-120, SA-121, SA-122 |
| `search_advanced` | Errors row 1 (negative `limit`) | MCH-SA-121 |
| `search_advanced` | Errors row 2 (negative `skip`) | MCH-SA-122 |
| `search_advanced` | Errors row 3 (today only — BUG-886 `AttributeError`) | MCH-SA-67 … SA-70, SA-72 … SA-89 (each is xfail because the call raises today) |
| inherited | R1 | MCH-INH-01 |
| inherited | R2 | MCH-INH-02, INH-03, INH-04 |
| inherited | R3 | MCH-INH-05, INH-06, INH-07, INH-08, INH-09 |
| inherited | R4 | MCH-INH-10, INH-11, INH-12, INH-13 |
| inherited | R5 | MCH-INH-14, INH-15, INH-16, INH-17, INH-18 |
| inherited | Errors row 1 (`factory_section_id` passed to `create` / `update`) | MCH-INH-02, INH-03, INH-04, INH-10, INH-11, INH-12, INH-13 |
| BUG-343 | `get_by_factory` R6, `get_by_section` R7 | MCH-GF-20, GF-26, GF-27, GS-21, GS-27, GS-28 |
| BUG-886 | `search_advanced` R12, R12a–R12e | MCH-SA-67 … SA-70, SA-72 … SA-89 |
| BUG-887 | `search_advanced` R14 | MCH-SA-99, SA-100 |
| BUG-888 | `search_advanced` R9 | MCH-SA-55, SA-56, SA-58, SA-59, SA-60 |
| BUG-889 | `get_by_section` R4, `search_advanced` R6a | MCH-GS-15, SA-33 |
| BUG-890 | `search_advanced` R3a, `restore` R7a | MCH-SA-15, SA-16, SA-17, SA-18, RS-17 |
| BUG-891 | `get_by_factory` R3a, `get_by_section` R3a, `restore` R7a | MCH-GF-12, GS-12, RS-18 |
| BUG-892 | `search_advanced` R8 | MCH-SA-39, SA-40, SA-41, SA-42, SA-43, SA-130 |
