# Test cases — `app/dao/item.py`

> **Spec:** `tests/unit/dao/item.spec.md` (source commit e48a092)
> **Status:** READY
> **Revision:** 4 (2026-10-17, after verification round 2) — ITEM-S-25 and ITEM-S-26 rest on physical row order, so they are now non-strict (bodies unchanged); new strict ITEM-S-28 records the SQL and requires the tie-breakers `lower(items.name)` and `items.id` in the `ORDER BY` (case-designer skill, "Missing sort order").
> Revision 3 — spec fill-gaps G7 (`find_similar_by_name_in_workspace` returns SQLAlchemy `Row` objects, new R10): ITEM-S-01 reworded to assert the tuple-like `Row` properties instead of "2-tuples" (verify finding 4), ITEM-S-05 also asserts the early return is a `list`. Verifier findings addressed: finding 1 / mutant 46 (sku matched only at start) → new ITEM-AF-46, search text in the middle of a sku; finding 2 / mutant 48 (unit) → new ITEM-AF-47, search text in the middle of a unit; finding 3 / mutant 51 (tag name) → new ITEM-AF-48, search text in the middle of a tag name.
> Revision 2 — spec fill-gaps G1–G6 and review Q13/Q14 applied: cross-workspace assignment rows confirmed insertable (G1); exactly-0.35 score now intended-included, BUG-034 (G2/Q13); exact `DataError` class and SQLSTATE for negative limit/offset (G3); backslash in search matched literally, HR-8 under BUG-013 (G4); catalog list ordered by name case-insensitive then id, HR-6, BUG-033 (G5); legacy untrimmed units trimmed+lowercased in unit filter and unit list, BUG-017 (G6/Q14).
> **Counts:** 111 cases · 77 expected-to-pass · 34 expected-to-fail (bugs) · 3 deferred

## Reviewer summary
- **Per callable:** `_apply_item_catalog_filters` 48 cases (19 bug) · `list_active_items_filtered` 15 (4 bug) · `count_active_items_filtered` 8 (1 bug) · `distinct_units_in_workspace` 12 (6 bug) · `find_similar_by_name_in_workspace` 27 (3 bug)
- **Notable design choices:**
  - `_apply_item_catalog_filters` is internal; its cases run it through `list_active_items_filtered` (large `limit`) and compare the returned ids **as a sorted list** (so duplicates still show, but the BUG-033 order change cannot break them). Order is tested only in the `list_active_items_filtered` section. AF R8 ("raw query may duplicate") is covered only indirectly, by the de-duplication cases of the two public callers.
  - BUG-033 (HR-6 order): passing list cases use names whose alphabetical order equals insertion (id) order, so they hold today and after the fix; separate xfail cases (ITEM-L-04, L-13, L-14, L-15) use names whose order differs from id order.
  - ITEM-AF-19 and ITEM-AF-39 insert an `ItemTagAssignment` whose `workspace_id` differs from its item's workspace (confirmed allowed by the spec, G1).
  - Similarity-threshold cases use letter-only strings with hand-computed trigram scores (7/12, 7/19, 7/20, 7/21); each first checks the score with `SELECT similarity(...)`. ITEM-S-11 (score 7/20) is now xfail BUG-034.
  - ITEM-U-04 changed from "pass, `" "` is listed" to "xfail BUG-017, `" "` is not listed" (spec R3a).
  - The tie-order bug cases (ITEM-S-25/26) rely on today's un-tie-broken sort returning rows in storage order; that is likely but not guaranteed, so strict xfail could flake.
  - "Without consulting the database" (similar R1) is checked by counting SQL statements with an engine event listener, not with a mock.
  - Similar-name rows (R10) are checked by their tuple-like properties (`len`, indexing, unpacking) and as `sqlalchemy.engine.Row`. Per the spec, no case asserts `isinstance(row, tuple)` in either direction.
  - The substring cases put the search text in the MIDDLE of sku, unit and tag name (ITEM-AF-46..48), so a "starts with" or "ends with" pattern fails them.
- **Needs a decision:** None.

## Conventions for this module

**IDs:** `ITEM` = `app/dao/item.py`. Method codes: `AF` = `_apply_item_catalog_filters`, `L` = `ItemDAO.list_active_items_filtered`, `CNT` = `ItemDAO.count_active_items_filtered`, `U` = `ItemDAO.distinct_units_in_workspace`, `S` = `ItemDAO.find_similar_by_name_in_workspace`.

**Workspaces:** W1, W2 = two existing workspaces. `W404` = an integer that is no workspace's id (e.g. max workspace id + 1000).

**Item shorthand:** `A "Zeta Rod" (pcs)` means an item in W1 (unless another workspace is named) with `name="Zeta Rod"`, `unit="pcs"`, `sku=NULL`, `description=NULL`, `is_active=True`, and `name_normalized` = the normalized form of the name per the spec's Overview (e.g. `"zeta rod"`). Other fields are named only when they matter: `sku=…`, `desc=…`, `nn=…` (explicit `name_normalized`), `(deleted)` = `is_active=False`. When no unit is shown it is `"pcs"`. Letters (A, B, …) are local to each case. "Inserted in order A, B, C" means the ids ascend in that order (insert and flush one after another). Units are inserted exactly as written, including untrimmed legacy values such as `"kg "` (allowed by the spec's Fixture notes).

**No digits:** unless a case says otherwise, no item or tag text field (name, description, sku, unit, tag name) contains any digit. This keeps the ASCII-digit id match (AF R11) from interfering.

**Backslashes:** in this file `\` in a value is one literal backslash character (Python `"a\\b"`).

**Tags:** `T1 "Galvanized" (W1)` = an `ItemTag` in W1 with that name, a unique `tag_code` (e.g. `"T1"`), and `is_active=True`. `Tdel` = a tag with `is_active=False`. "A tagged T1" = an `ItemTagAssignment(workspace_id=<A's workspace>, item_id=A, tag_id=T1)` unless another assignment workspace is stated. `UNKNOWN_TAG` = an integer that is no tag's id (max tag id + 1000).

**Generated names:** `N(k)` = the k-th three-letter lowercase string in alphabetical order (`N(1)="aaa"`, `N(2)="aab"`, … `N(27)="aba"`, …). Used as item names (and units in ITEM-U-08); they are letter-only with no shared-prefix issues, so their order is collation-independent.

**Actions:**
- `list(...)` = `item_dao.list_active_items_filtered(db, workspace_id=W1, limit=100, ...)`. Only the stated arguments are added or overridden.
  - In the **AF** section results are compared as `sorted(ids)` (duplicates would still show as repeated ids); "returns [A, B]" there means `sorted(ids) == sorted([A.id, B.id])`.
  - In the **L** section results are compared as the **ordered list of ids**, unless the case says "sorted".
- `count(...)` = `item_dao.count_active_items_filtered(db, workspace_id=W1, ...)`.
- `units(ws)` = `item_dao.distinct_units_in_workspace(db, workspace_id=ws)`. Compared as an ordered list.
- `similar(name, ...)` = `item_dao.find_similar_by_name_in_workspace(db, workspace_id=W1, name=name, ...)` (default `limit=5`, `exclude_item_id=None` unless stated). Results are compared as the ordered list of `(item id, score)`. Scores are compared with `pytest.approx(x, abs=1e-4)`.

**Read-only check ("session clean"):** after the call, `db.new`, `db.dirty` and `db.deleted` are all empty.

**Database-error cases:** call inside `db.begin_nested()`. Assert the raised exception is a `sqlalchemy.exc.DataError`, its `.orig` is an instance of the stated `psycopg2.errors` class, `.orig.pgcode` equals the stated SQLSTATE, and `str(exc)` contains the stated Postgres message. After the error, roll back the savepoint, then re-read: the number of items in W1 and each item's `name`/`unit`/`is_active` are unchanged.

**SQL statement counter:** a `before_cursor_execute` listener on the test engine, counting statements issued during the call.

**Trigram preconditions:** the `pg_trgm` extension must exist in the test DB (baseline migration creates it). The similarity cases that depend on a specific score first assert it with `db.execute(text("SELECT similarity(:a, :b)"))`.

**Externals mocked:** none (spec: "Externals to mock: none"). **Time:** not mocked. **Race simulations:** none.

## `_apply_item_catalog_filters` (exercised through `list_active_items_filtered`)

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| ITEM-AF-01 | R3 | happy | W1: A "Zeta Rod" (pcs), B "Plain Bar" (kg), C "Hex Bolt" (box) | `list()` (search, unit, tag_ids all None) | returns [A, B, C]; session clean | pass |
| ITEM-AF-02 | R1 | isolation | W1: A "Zeta Rod" (pcs); W2: X "Zeta Rod" (pcs) | `list()` | returns [A]; X absent | pass |
| ITEM-AF-03 | R1, R11 | isolation | W1: A "Hex Bolt" (pcs); W2: X "Hex Bolt" (pcs) | `list(search=str(X.id))` | returns []; X absent even though the search equals its id | pass |
| ITEM-AF-04 | R1, R7 | isolation | W2: tag T2 "Galvanized" (W2), X "Hex Bolt" in W2 tagged T2 (assignment workspace W2); W1: A "Hex Bolt" untagged | `list(tag_ids=[T2.id])` | returns [] | pass |
| ITEM-AF-05 | R2 | soft-delete | W1: A "Zeta Rod" (pcs), D "Zeta Rod" (pcs) (deleted) | `list()` | returns [A]; D absent | pass |
| ITEM-AF-06 | R2 | soft-delete | W1: A "Zeta Rod", D "Zeta Rod" (deleted) | `list(search="zeta")` | returns [A]; D absent | pass |
| ITEM-AF-07 | R2 | soft-delete | W1: T1 "Galvanized"; D "Hex Bolt" (deleted) tagged T1; A "Plain Bar" untagged | `list(tag_ids=[T1.id])` | returns [] | pass |
| ITEM-AF-08 | R3 | boundary | W1: A "Zeta Rod", B "Plain Bar" | `list(search="")` | returns [A, B] | pass |
| ITEM-AF-09 | R3, R9 | boundary | W1: A "Zeta Rod", B "Plain Bar" | `list(search="   ")` | returns [A, B] (whitespace-only = no search) | pass |
| ITEM-AF-10 | R4 | happy | W1: A "Rod" (kg), B "Bar" (pcs), C "Sack" (kgs) | `list(unit="kg")` | returns [A]; B and C ("kgs") absent | pass |
| ITEM-AF-11 | R4 [BUG-017] | bug | W1: A "Rod" (kg), B "Bar" (Kg), C "Pin" (KG), D "Sack" (kgs), E "Nut" (pcs) | `list(unit="kg")` | returns [A, B, C]; D and E absent | xfail BUG-017 — fails today on: B and C missing (today returns [A]) |
| ITEM-AF-12 | R4 [BUG-017] | bug | W1: A "Rod" (kg), B "Bar" (pcs) | `list(unit="kg ")` | returns [A] | xfail BUG-017 — fails today on: returns [] (no item stored as "kg ") |
| ITEM-AF-13 | R4 [BUG-017] | bug | W1: A "Rod" (kg), B "Bar" (pcs) | `list(unit="   ")` | returns [A, B] (whitespace-only = no unit filter) | xfail BUG-017 — fails today on: returns [] |
| ITEM-AF-14 | R4 | boundary | W1: A "Rod" (kg), B "Bar" (pcs) | `list(unit="")` | returns [A, B] | pass |
| ITEM-AF-15 | R5 | happy | W1: tags T1 "Galvanized", T2 "Painted", T3 "Coated"; A "Rod" tagged T1, B "Bar" tagged T2, C "Pin" tagged T3, D "Nut" untagged | `list(tag_ids=[T1.id, T2.id])` | returns [A, B]; C and D absent | pass |
| ITEM-AF-16 | R5 | boundary | same as ITEM-AF-15 | `list(tag_ids=[])` | returns [A, B, C, D] | pass |
| ITEM-AF-17 | R6 [BUG-014] | bug | W1: Tdel "Obsolete" (is_active False); A "Rod" tagged Tdel; B "Bar" untagged | `list(tag_ids=[Tdel.id])` | returns [] | xfail BUG-014 — fails today on: A returned |
| ITEM-AF-18 | R6 [BUG-014] | bug | W1: Tdel "Obsolete" (deleted), T1 "Galvanized" (active); A "Rod" tagged Tdel only; B "Bar" tagged Tdel and T1 | `list(tag_ids=[Tdel.id, T1.id])` | returns [B] (exactly once); A absent | xfail BUG-014 — fails today on: A returned |
| ITEM-AF-19 | R7 | isolation | W1: T1 "Galvanized" (W1); A "Rod" in W1 with one assignment `(workspace_id=W2, item_id=A, tag_id=T1)` and no W1 assignment | `list(tag_ids=[T1.id])` | returns [] | pass |
| ITEM-AF-20 | R7 | boundary | W1: T1 "Galvanized"; A "Rod" tagged T1 | `list(tag_ids=[UNKNOWN_TAG])` | returns [] | pass |
| ITEM-AF-21 | R7, R5 | boundary | W1: T1 "Galvanized"; A "Rod" tagged T1; B "Bar" untagged | `list(tag_ids=[T1.id, UNKNOWN_TAG])` | returns [A] | pass |
| ITEM-AF-22 | R9, R10, R13 | happy | W1: A "Zeta Rod" (pcs) sku NULL desc NULL; B "Plain Bar" (pcs) desc "made of zeta alloy"; C "Hex Bolt" (pcs) sku "ZETA-AB"; D "Rope" (zetaroll) sku NULL desc NULL; E "Plain Nut" (pcs) sku "PN-AB" desc "steel"; F "Zeta Cap" (pcs) (deleted) | `list(search="ZeTa")` | returns [A, B, C, D] (name / description / sku / unit, case-insensitive, any one field suffices; A and D match despite NULL sku/description); E and F absent | pass |
| ITEM-AF-23 | R9 | boundary | W1: A "Zeta Rod", B "Plain Nut" | `list(search="  zeta  ")` | returns [A] (search is trimmed) | pass |
| ITEM-AF-24 | R9 | boundary | W1: A "Hex Bolt" | `list(search="hex  bolt")` (two inner spaces) | returns [] (inner whitespace kept as typed) | pass |
| ITEM-AF-25 | R9 | boundary | W1: A "Hex Bolt" | `list(search="hex bolt")` (one inner space) | returns [A] | pass |
| ITEM-AF-26 | R9 [BUG-013] | bug | W1: A "Clamp" sku "AB_12"; B "Clip" sku "ABX12" (digits allowed in sku here) | `list(search="AB_12")` | returns [A]; B absent | xfail BUG-013 — fails today on: B returned (`_` acts as wildcard) |
| ITEM-AF-27 | R9 [BUG-013] | bug | W1: A "Cement 50% mix", B "50 kg bag", C "500 ml bottle" (digits allowed here) | `list(search="50%")` | returns [A]; B and C absent | xfail BUG-013 — fails today on: B and C returned |
| ITEM-AF-28 | R9 [BUG-013] | bug | W1: A "snake_case bolt", B "Plain Bar" | `list(search="_")` | returns [A] | xfail BUG-013 — fails today on: B returned |
| ITEM-AF-29 | R9 [BUG-013] | bug | W1: A "100% cotton rag" (digits allowed here), B "Plain Bar" | `list(search="%")` | returns [A] | xfail BUG-013 — fails today on: B returned |
| ITEM-AF-30 | R11, R13 | happy | W1, inserted in order: A "Hex Bolt", B "Plain Bar", then C with name `f"Pack {A.id}"` | `list(search=str(A.id))` | returns [A, C]: A by id, C by name text; B absent | pass |
| ITEM-AF-31 | R11 | boundary | W1: A "Hex Bolt", B "Plain Bar" | `list(search=f" {A.id} ")` | returns [A] (trimmed before the digit check) | pass |
| ITEM-AF-32 | R11 | boundary | W1: A "Hex Bolt", B "Plain Bar" | `list(search=f"{A.id}a")` | returns [] (not all digits: no id match) | pass |
| ITEM-AF-33 | R11 [BUG-012]; L R6 | bug | W1: A "Sheet 2 m²" (digits allowed here), B "Plain Bar" | `list(search="²")` | no exception; returns [A] (text match only) | xfail BUG-012 — fails today on: raises `ValueError` |
| ITEM-AF-34 | R11 [BUG-012] | bug | W1: A "Tile 2² grade" (digits allowed here), B "Plain Bar" | `list(search="2²")` | no exception; returns [A] | xfail BUG-012 — fails today on: raises `ValueError` |
| ITEM-AF-35 | R11 [BUG-012] | bug | W1: A "Hex Bolt", B "Plain Bar" | `list(search=<A.id with each digit replaced by its Arabic-Indic digit U+0660–U+0669>)` (e.g. id 12 → `"١٢"`) | returns [] (non-ASCII digits never match by id) | xfail BUG-012 — fails today on: A returned |
| ITEM-AF-36 | R12 | happy | W1: T1 "Galvanized" (active); A "Hex Bolt" tagged T1; B "Plain Bar" untagged | `list(search="GALV")` | returns [A] | pass |
| ITEM-AF-37 | R12 [BUG-015] | bug | W1: Tdel "Obsolete" (deleted); A "Hex Bolt" tagged Tdel; B "Plain Bar" | `list(search="obsol")` | returns [] | xfail BUG-015 — fails today on: A returned |
| ITEM-AF-38 | R12, R9 [BUG-013] | bug | W1: T1 "A_B grade", T2 "AXB grade" (both active); A "Hex Bolt" tagged T1; B "Plain Nut" tagged T2 | `list(search="a_b")` | returns [A]; B absent | xfail BUG-013 — fails today on: B returned via tag name |
| ITEM-AF-39 | R12 | isolation | W1: T1 "Galvanized" (W1); A "Hex Bolt" in W1 whose only assignment is `(workspace_id=W2, item_id=A, tag_id=T1)` | `list(search="galv")` | returns [] | pass |
| ITEM-AF-40 | R13 | happy | W1: T1 "Galvanized"; A "Zeta Rod" (kg) tagged T1; B "Plain Bar" (kg) tagged T1; C "Zeta Pin" (pcs) tagged T1; D "Zeta Cap" (kg) untagged | `list(search="zeta", unit="kg", tag_ids=[T1.id])` | returns [A] (all three filters AND-ed) | pass |
| ITEM-AF-41 | R9 [BUG-013] (HR-8) | bug | W1: A "Pipe a\b fitting", B "Pipe ab fitting" | `list(search="a\b")` | returns [A]; B absent (backslash literal) | xfail BUG-013 — fails today on: A absent and B returned (today `\` escapes `b`, pattern matches "ab") |
| ITEM-AF-42 | R9 [BUG-013] (HR-8) | bug | W1: A "Pipe a\b fitting", B "Plain Bar", C "Discount rag %" (ends in `%`) | `list(search="\")` | returns [A]; B and C absent | xfail BUG-013 — fails today on: A absent and C returned (today matches only text ending in `%`) |
| ITEM-AF-43 | R9 [BUG-013] (HR-8) | bug | W1: A "Wrench abc\ tool" (the `abc\` is mid-name), B "Plain abc%" (ends in `abc%`), C "Plain Bar" | `list(search="abc\")` | no exception; returns [A]; B and C absent | xfail BUG-013 — fails today on: A absent and B returned (today matches only text ending in "abc%") |
| ITEM-AF-44 | R12, R9 [BUG-013] (HR-8) | bug | W1: T1 "a\b grade", T2 "ab grade" (both active); A "Hex Bolt" tagged T1; B "Plain Nut" tagged T2 | `list(search="a\b")` | returns [A]; B absent (tag-name alternative also literal) | xfail BUG-013 — fails today on: A absent and B returned via tag name |
| ITEM-AF-45 | R4 [BUG-017] (Q14) | bug | W1: A "Rod" unit `"kg "` (trailing space), B "Bar" unit `" KG"` (leading space), C "Pin" (kgs), D "Nut" (pcs) | `list(unit="kg")` | returns [A, B]; C and D absent (stored unit trimmed and compared case-insensitively) | xfail BUG-017 — fails today on: returns [] |
| ITEM-AF-46 | R9 | boundary | W1: A "Hex Bolt" (pcs) sku "XX-ZETA-YY" desc NULL; B "Plain Bar" (pcs) sku "PN-AB" desc NULL | `list(search="zeta")` | returns [A] (the search text is in the middle of A's sku, and no other field of A contains it); B absent | pass |
| ITEM-AF-47 | R9 | boundary | W1: A "Rope" unit "bigzetaroll" sku NULL desc NULL; B "Plain Bar" (pcs) | `list(search="ZETA")` | returns [A] (the search text is in the middle of A's unit, and no other field of A contains it); B absent | pass |
| ITEM-AF-48 | R12 | boundary | W1: T1 "Hot-dip galvanized" (active); A "Hex Bolt" tagged T1; B "Plain Bar" untagged | `list(search="GALV")` | returns [A] (the search text is in the middle of the tag name, and no field of A contains it); B absent | pass |

## `ItemDAO.list_active_items_filtered`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| ITEM-L-01 | R1, R3 | happy | W1 inserted in order: A "Alpha Rod", B "Bravo Bar", C "Charlie Bolt" (name order = id order) | `item_dao.list_active_items_filtered(db, workspace_id=W1)` (all defaults) | returns a `list` of `Item` instances with ids [A, B, C] in that order; session clean | pass |
| ITEM-L-02 | R2 | happy | W1: T1 "Galvanized", T2 "Painted"; A "Rod" tagged T1 and T2; B "Bar" tagged T1 | `list(tag_ids=[T1.id, T2.id])` | length 2; sorted ids = [A, B] (A once) | pass |
| ITEM-L-03 | R2 | happy | W1: T1 "Galvanized Steel", T2 "Galvanized Iron"; A "Galvanized Hex Bolt" tagged T1 and T2; B "Plain Bar" | `list(search="galv")` | returns exactly [A] (length 1) | pass |
| ITEM-L-04 | R3 [BUG-033] | bug | W1 inserted in order: A "Zulu", B "Mike", C "alpha" | `list()` | returns [C, B, A] (names "alpha", "Mike", "Zulu": case-insensitive name order) | xfail BUG-033 — fails today on: returns [A, B, C] (id order) |
| ITEM-L-05 | R3 | boundary | W1 inserted in order: "Zeta alpha", "Plain one", "Zeta bravo", "Zeta charlie", "Plain two", "Zeta delta", "Zeta echo" (zeta names alphabetical = id order) | three calls: `list(search="zeta", skip=0, limit=2)`, `(skip=2, limit=2)`, `(skip=4, limit=2)` | pages are [alpha, bravo], [charlie, delta], [echo]; together they are the 5 zeta items, each exactly once; no "Plain" item appears (filter before paging) | pass |
| ITEM-L-06 | R4 | boundary | W1: 101 active items named N(1)…N(101), inserted in that order | `item_dao.list_active_items_filtered(db, workspace_id=W1)` (defaults) | returns 100 items named N(1)…N(100) in that order; N(101) absent | pass |
| ITEM-L-07 | R4 | boundary | W1: 100 active items named N(1)…N(100), inserted in that order | same call (defaults) | returns all 100, named N(1)…N(100) in that order | pass |
| ITEM-L-08 | R5 | boundary | W1: A "Rod", B "Bar", C "Pin" | `list(limit=0)` | returns [] | pass |
| ITEM-L-09 | R5 | boundary | W1 inserted in order: A "Alpha Rod", B "Bravo Bar", C "Charlie Pin" | `list(limit=1)` | returns [A] | pass |
| ITEM-L-10 | R5, Errors row 1 | error | W1: A "Rod", B "Bar", C "Pin" | `list(limit=-1)` in a savepoint | raises `sqlalchemy.exc.DataError`; `.orig` is `psycopg2.errors.InvalidRowCountInLimitClause`; `.orig.pgcode == "2201W"`; message contains `LIMIT must not be negative`; after savepoint rollback, W1 still has 3 items, unchanged | pass |
| ITEM-L-11 | R5, Errors row 2 | error | W1: A "Rod", B "Bar", C "Pin" | `list(skip=-1)` in a savepoint | raises `sqlalchemy.exc.DataError`; `.orig` is `psycopg2.errors.InvalidRowCountInResultOffsetClause`; `.orig.pgcode == "2201X"`; message contains `OFFSET must not be negative`; after savepoint rollback, W1 still has 3 items, unchanged | pass |
| ITEM-L-12 | R1 | isolation | W1: A "Rod" | `item_dao.list_active_items_filtered(db, workspace_id=W404)` | returns [] | pass |
| ITEM-L-13 | R3 [BUG-033] | bug | W1 inserted in order: A "bolt", B "Axle", C "Bolt" | `list()` | returns [B, A, C] ("Axle" first; "bolt"/"Bolt" tie case-insensitively, lower id A first) | xfail BUG-033 — fails today on: returns [A, B, C] ("bolt" before "Axle") |
| ITEM-L-14 | R3 [BUG-033] | bug | W1 inserted in order: "Zeta echo", "Plain one", "Zeta delta", "Zeta charlie", "Plain two", "Zeta bravo", "Zeta alpha" | three calls: `list(search="zeta", skip=0, limit=2)`, `(skip=2, limit=2)`, `(skip=4, limit=2)` | pages are [alpha, bravo], [charlie, delta], [echo]; each zeta item exactly once across pages | xfail BUG-033 — fails today on: page 1 is [echo, delta] |
| ITEM-L-15 | R4 [BUG-033] | bug | W1: 101 active items named N(101), N(100), …, N(1), inserted in that order (so N(101) has the lowest id) | `item_dao.list_active_items_filtered(db, workspace_id=W1)` (defaults) | returns 100 items named N(1)…N(100) in that order; N(101) (lowest id) absent | xfail BUG-033 — fails today on: N(101) present and N(1) absent (today the 100 lowest ids) |

## `ItemDAO.count_active_items_filtered`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| ITEM-CNT-01 | R1 | happy | W1: A "Zeta Rod", B "Zeta Pin", C "Plain Bar", D "Zeta Cap" (deleted); W2: X "Zeta Rod" | `count(search="zeta")` | returns `2` (type `int`); equals `len(list(search="zeta", limit=100))`; session clean | pass |
| ITEM-CNT-02 | R1 | boundary | W1: 150 active items named N(1)…N(150) | `count()` | returns `150` (not capped at the list's default 100) | pass |
| ITEM-CNT-03 | R2 | happy | W1: T1 "Galvanized", T2 "Painted"; A "Rod" tagged T1 and T2; B "Bar" tagged T1; C "Pin" untagged | `count(tag_ids=[T1.id, T2.id])` | returns `2` | pass |
| ITEM-CNT-04 | R2 | happy | W1: T1 "Galvanized Steel", T2 "Galvanized Iron"; A "Galvanized Hex Bolt" tagged T1 and T2; B "Plain Bar" | `count(search="galv")` | returns `1` | pass |
| ITEM-CNT-05 | R3 | boundary | W1 has no items | `count()` | returns `0`; `isinstance(result, int)` and result is not `None` | pass |
| ITEM-CNT-06 | R3 | isolation | W1: A "Rod" | `item_dao.count_active_items_filtered(db, workspace_id=W404)` | returns `0` (an `int`) | pass |
| ITEM-CNT-07 | R3 | boundary | W1: A "Zeta Rod", B "Plain Bar" | `count(search="nomatch")` | returns `0` (an `int`) | pass |
| ITEM-CNT-08 | R4 [BUG-012] | bug | W1: A "Sheet 2 m²" (digits allowed here), B "Plain Bar" | `count(search="²")` | no exception; returns `1` | xfail BUG-012 — fails today on: raises `ValueError` |

## `ItemDAO.distinct_units_in_workspace`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| ITEM-U-01 | R1, R5 | happy | W1 active items with units "pcs", "kg", "ltr", "kg" | `units(W1)` | returns exactly `["kg", "ltr", "pcs"]`; session clean | pass |
| ITEM-U-02 | R2 | isolation | W1: active item (kg), deleted item (box); W2: active item (drum) | `units(W1)` | returns exactly `["kg"]` | pass |
| ITEM-U-03 | R3 | boundary | W1 active items with units "kg" and "" | `units(W1)` | returns exactly `["kg"]` (`""` never returned) | pass |
| ITEM-U-04 | R3a [BUG-017] | bug | W1 active items with units "kg" and " " (one space) | `units(W1)` | returns exactly `["kg"]` (whitespace-only counts as `""`, not listed) | xfail BUG-017 — fails today on: `" "` returned as its own entry |
| ITEM-U-05 | R4 [BUG-017] | bug | W1 active items with units "kg", "Kg", "KG" | `units(W1)` | returns exactly `["kg"]` | xfail BUG-017 — fails today on: returns three entries |
| ITEM-U-06 | R4 [BUG-017] | bug | W1: one active item with unit "PCS" | `units(W1)` | returns exactly `["pcs"]` | xfail BUG-017 — fails today on: returns `["PCS"]` |
| ITEM-U-07 | R5, R4 [BUG-017] | bug | W1 active items with units "PCS", "kg", "Ltr" | `units(W1)` | returns exactly `["kg", "ltr", "pcs"]` | xfail BUG-017 — fails today on: "PCS"/"Ltr" returned as stored |
| ITEM-U-08 | R6, R5 | boundary | W1: 120 active items, units N(1)…N(120) (each different, lowercase letters) | `units(W1)` | returns all 120 units, equal to `sorted` list N(1)…N(120) | pass |
| ITEM-U-09 | R6 | boundary | W1 has no items | `units(W1)` | returns `[]` | pass |
| ITEM-U-10 | R6 | isolation | W1: active item (kg) | `units(W404)` | returns `[]` | pass |
| ITEM-U-11 | R3a [BUG-017] | bug | W1 active items with units "" and " " only | `units(W1)` | returns `[]` | xfail BUG-017 — fails today on: returns `[" "]` |
| ITEM-U-12 | R4 [BUG-017] (Q14) | bug | W1 active items with units "kg", "Kg", "KG", "kg " (trailing space), plus one with "pcs" | `units(W1)` | returns exactly `["kg", "pcs"]` (legacy untrimmed value merged into "kg") | xfail BUG-017 — fails today on: four separate kg spellings returned |

## `ItemDAO.find_similar_by_name_in_workspace`

In this section `nn` is set explicitly for every item. The trigram scores for single lowercase words sharing the 7-letter prefix `abcdefg` against the proposed `"abcdefg"` are 7/12 ≈ 0.5833 (`abcdefghij`), 7/19 ≈ 0.3684 (`abcdefghijklmnopq`), 7/20 = 0.35 (`abcdefghijklmnopqr`, `real` 0.3499999940395355) and 7/21 ≈ 0.3333 (`abcdefghijklmnopqrs`).

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| ITEM-S-01 | R3, R5 | happy | W1: A name "Steel Rod 22m" nn "steel rod 22m"; B name "Copper Pipe" nn "copper pipe" | `similar("Steel Rod 22 m")` | `type(result) is list`, length 1; the single row `row` is a `sqlalchemy.engine.Row` with `len(row) == 2`; `row[0]` is an `Item` instance with id A; `row[1]` is a `float` equal to 1.0; `item, score = row` unpacks to (A, 1.0); B absent; session clean (do not assert `isinstance(row, tuple)`) | pass |
| ITEM-S-02 | R5 | happy | same as ITEM-S-01 | `similar("  STEEL-Rod   22 m ")` | returns `[(A, 1.0)]` | pass |
| ITEM-S-03 | R1 | boundary | W1: A name "a b" nn "a b" | `similar("a b")` | A is in the result (normalized length 3 proceeds) | pass |
| ITEM-S-04 | R1 | boundary | W1: A name "22m" nn "22m" | `similar("22 m")` | A is in the result (`"22 m"` → `"22m"`, length 3) | pass |
| ITEM-S-05 | R1, R10 | boundary | W1: A name "ab" nn "ab" | `similar("ab")` with the SQL statement counter | returns `[]` and `type(result) is list`; 0 SQL statements issued | pass |
| ITEM-S-06 | R1 | boundary | W1: A name "ab" nn "ab" | `similar("  AB  ")` with the statement counter | returns `[]`; 0 SQL statements issued | pass |
| ITEM-S-07 | R1 | boundary | W1: A name "x" nn "" | `similar("")` with the statement counter | returns `[]`; 0 SQL statements issued | pass |
| ITEM-S-08 | R1 | boundary | W1: A name "x" nn "" | `similar("!!!")` with the statement counter | returns `[]`; 0 SQL statements issued | pass |
| ITEM-S-09 | R2 | happy | W1: A name "Copper Pipe" nn "steel rod 22m"; B name "Steel Rod 22m" nn "copper pipe" | `similar("Steel Rod 22m")` | returns `[(A, 1.0)]`; B absent (judged by `name_normalized`, not `name`) | pass |
| ITEM-S-10 | R3 | boundary | W1: A name "___" nn "___"; precondition: `similarity('___','___') < 0.35` | `similar("___")` | returns exactly one row, item A (exact normalized match returned despite a low score); its score equals the precondition value | pass |
| ITEM-S-11 | R4a [BUG-034] | bug | W1: A nn "abcdefghijklmnopqr" (no item with nn "abcdefg"); precondition: `similarity('abcdefg','abcdefghijklmnopqr') ≈ 0.35` (abs 1e-6) | `similar("abcdefg")` | returns exactly one row, item A, score ≈ 0.35 (`pytest.approx(0.3499999940395355, abs=1e-6)`) | xfail BUG-034 — fails today on: returns `[]` (A excluded) |
| ITEM-S-12 | R4 | boundary | W1: A nn "abcdefghijklmnopqrs"; precondition: `similarity('abcdefg','abcdefghijklmnopqrs') ≈ 0.3333 < 0.35` | `similar("abcdefg")` | returns `[]` | pass |
| ITEM-S-13 | R6 | isolation | W1: A nn "steel rod 22m" (active), D nn "steel rod 22m" (deleted); W2: X nn "steel rod 22m" | `similar("Steel Rod 22m")` | returns `[(A, 1.0)]`; D and X absent | pass |
| ITEM-S-14 | R7 | boundary | W1: 6 active items, all nn "steel rod 22m", names "Rod one" … "Rod six" (letters) | `similar("Steel Rod 22m")` (default limit) | returns exactly 5 rows, each score 1.0, each a distinct item from the 6 | pass |
| ITEM-S-15 | R7 | boundary | W1: 3 items, all nn "steel rod 22m" | `similar("Steel Rod 22m", limit=1)` | returns exactly 1 row, score 1.0 | pass |
| ITEM-S-16 | R7 | boundary | W1: 3 items, all nn "steel rod 22m" | `similar("Steel Rod 22m", limit=0)` | returns `[]` | pass |
| ITEM-S-17 | R7, Errors row 1 | error | W1: 3 items, all nn "steel rod 22m" | `similar("Steel Rod 22m", limit=-1)` in a savepoint | raises `sqlalchemy.exc.DataError`; `.orig` is `psycopg2.errors.InvalidRowCountInLimitClause`; `.orig.pgcode == "2201W"`; message contains `LIMIT must not be negative`; after savepoint rollback, W1 still has 3 items, unchanged | pass |
| ITEM-S-18 | R8 | happy | W1: A name "Steel Rod 22m", B name "Steel Rod 22 m", both nn "steel rod 22m" | `similar("Steel Rod 22m", exclude_item_id=A.id)` | returns `[(B, 1.0)]`; A absent despite exact match | pass |
| ITEM-S-19 | R8 | boundary | same as ITEM-S-18 | `similar("Steel Rod 22m", exclude_item_id=<max item id + 1000>)` | result ids = {A, B} | pass |
| ITEM-S-20 | R8 | boundary | same as ITEM-S-18, plus C name "Copper Pipe" nn "copper pipe" | `similar("Steel Rod 22m", exclude_item_id=C.id)` | result ids = {A, B} | pass |
| ITEM-S-21 | R8 | boundary | same as ITEM-S-18 | `similar("Steel Rod 22m", exclude_item_id=None)` | result ids = {A, B} | pass |
| ITEM-S-22 | R8 | boundary | same as ITEM-S-18 | `similar("Steel Rod 22m", exclude_item_id=0)` | result ids = {A, B} | pass |
| ITEM-S-23 | R9, R4 | happy | W1 inserted in order: P nn "abcdefghijklmnopq", Q nn "abcdefghij", R nn "abcdefg" (distinct names "Pa", "Qa", "Ra") | `similar("abcdefg")` | returns `[(R, 1.0), (Q, ≈0.5833), (P, ≈0.3684)]` in that order (score descending) | pass |
| ITEM-S-24 | R9, R7 | boundary | same as ITEM-S-23 | `similar("abcdefg", limit=1)` | returns `[(R, 1.0)]` (order applied before the limit cut) | pass |
| ITEM-S-25 | R9 [BUG-018] | bug | W1: 7 items, all nn "steel rod 22m", inserted in order with names "delta", "Bravo", "alpha", "Charlie", "echo", "Foxtrot", "bravo" | `similar("Steel Rod 22m", limit=5)` | returned names in order are exactly `["alpha", "Bravo", "bravo", "Charlie", "delta"]` ("Bravo" has the lower id and comes before "bravo"); "echo" and "Foxtrot" absent; all scores 1.0 | xfail BUG-018 (non-strict; Author: claude — rests on physical row order, which is not deterministic on the test database; ITEM-S-28 is the strict alarm) — — fails today on: the name order/selection (today ties come back in storage order, e.g. starting with "delta" and including "echo") |
| ITEM-S-26 | R9 [BUG-018] | bug | same as ITEM-S-25 | `similar("Steel Rod 22m", limit=10)` | returned names in order are exactly `["alpha", "Bravo", "bravo", "Charlie", "delta", "echo", "Foxtrot"]` | xfail BUG-018 (non-strict; Author: claude — rests on physical row order, which is not deterministic on the test database; ITEM-S-28 is the strict alarm) — — fails today on: the order (today storage order, starting with "delta") |
| ITEM-S-27 | R4 | boundary | W1: A nn "abcdefghijklmnopq" (no item with nn "abcdefg"); precondition: `similarity('abcdefg','abcdefghijklmnopq') ≈ 0.3684 > 0.35` | `similar("abcdefg")` | returns `[(A, ≈0.3684)]` (above threshold, no exact match needed) | pass |
| ITEM-S-28 | R9 [BUG-018] | bug | W1: one item, nn "steel rod 22m", name "alpha"; a recorder for the SQL statements the session sends during the When (Author: claude — statement recorder) | `similar("Steel Rod 22m")` | 1. returns one row, the item. 2. the one `SELECT` sent has an `ORDER BY` in which `lower(items.name)` and `items.id` come after the score | xfail BUG-018 (strict) — fails today on: Then 2 (the `ORDER BY` has the score only) |

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| `list_active_items_filtered` R7 [BUG-016] | `GET /items/` endpoint (integration) | `limit=0` and `limit=-1` → 422 before the DAO is reached (HR-7); `limit=1` accepted |
| `find_similar_by_name_in_workspace` R8 [BUG-011] | `GET /items/similar/` endpoint + `ItemService.get_similar_items` (integration) | the endpoint accepts an `exclude_item_id` query parameter and passes it through; the excluded item is absent from the response |
| `_apply_item_catalog_filters` R4 [BUG-017], storage part | `ItemCreate`/`ItemUpdate` schema or `ItemManager` create/update | `unit` is stored trimmed (`"kg "` → `"kg"`); whitespace-only handling per that spec (HR-1/HR-3) |

## Spec gaps
None.

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `_apply_item_catalog_filters` | R1 | ITEM-AF-02, ITEM-AF-03, ITEM-AF-04 |
| `_apply_item_catalog_filters` | R2 | ITEM-AF-05, ITEM-AF-06, ITEM-AF-07, ITEM-AF-22 (F) |
| `_apply_item_catalog_filters` | R3 | ITEM-AF-01, ITEM-AF-08, ITEM-AF-09 |
| `_apply_item_catalog_filters` | R4 [BUG-017] | ITEM-AF-10, ITEM-AF-11, ITEM-AF-12, ITEM-AF-13, ITEM-AF-14, ITEM-AF-45; storage part deferred |
| `_apply_item_catalog_filters` | R5 | ITEM-AF-15, ITEM-AF-16, ITEM-AF-21 |
| `_apply_item_catalog_filters` | R6 [BUG-014] | ITEM-AF-17, ITEM-AF-18 |
| `_apply_item_catalog_filters` | R7 | ITEM-AF-04, ITEM-AF-19, ITEM-AF-20, ITEM-AF-21 |
| `_apply_item_catalog_filters` | R8 | indirect: ITEM-L-02, ITEM-L-03, ITEM-CNT-03, ITEM-CNT-04 |
| `_apply_item_catalog_filters` | R9 [BUG-013] (incl. HR-8 backslash) | ITEM-AF-09, ITEM-AF-22, ITEM-AF-23, ITEM-AF-24, ITEM-AF-25, ITEM-AF-26, ITEM-AF-27, ITEM-AF-28, ITEM-AF-29, ITEM-AF-38, ITEM-AF-41, ITEM-AF-42, ITEM-AF-43, ITEM-AF-44, ITEM-AF-46 (sku mid-string), ITEM-AF-47 (unit mid-string) |
| `_apply_item_catalog_filters` | R10 | ITEM-AF-22, ITEM-AF-46, ITEM-AF-47 |
| `_apply_item_catalog_filters` | R11 [BUG-012] | ITEM-AF-03, ITEM-AF-30, ITEM-AF-31, ITEM-AF-32, ITEM-AF-33, ITEM-AF-34, ITEM-AF-35 |
| `_apply_item_catalog_filters` | R12 [BUG-015] (+ BUG-013 literal) | ITEM-AF-36, ITEM-AF-37, ITEM-AF-38, ITEM-AF-39, ITEM-AF-44, ITEM-AF-48 (tag name mid-string) |
| `_apply_item_catalog_filters` | R13 | ITEM-AF-22, ITEM-AF-30, ITEM-AF-40 |
| `_apply_item_catalog_filters` | Errors: none (Today `ValueError`, BUG-012) | ITEM-AF-33, ITEM-AF-34, ITEM-CNT-08 |
| `list_active_items_filtered` | R1 | ITEM-L-01, ITEM-L-12, all ITEM-AF cases |
| `list_active_items_filtered` | R2 | ITEM-L-02, ITEM-L-03, ITEM-AF-18 |
| `list_active_items_filtered` | R3 [BUG-033] | ITEM-L-01, ITEM-L-05 (pass); ITEM-L-04, ITEM-L-13, ITEM-L-14 (xfail) |
| `list_active_items_filtered` | R4 [BUG-033] | ITEM-L-06, ITEM-L-07 (pass); ITEM-L-15 (xfail) |
| `list_active_items_filtered` | R5 | ITEM-L-08, ITEM-L-09, ITEM-L-10, ITEM-L-11 |
| `list_active_items_filtered` | R6 [BUG-012] | ITEM-AF-33 |
| `list_active_items_filtered` | R7 [BUG-016] | Deferred (`GET /items/`) |
| `list_active_items_filtered` | Errors row 1 (negative limit) | ITEM-L-10 |
| `list_active_items_filtered` | Errors row 2 (negative skip) | ITEM-L-11 |
| `count_active_items_filtered` | R1 | ITEM-CNT-01, ITEM-CNT-02 |
| `count_active_items_filtered` | R2 | ITEM-CNT-03, ITEM-CNT-04 |
| `count_active_items_filtered` | R3 | ITEM-CNT-05, ITEM-CNT-06, ITEM-CNT-07 |
| `count_active_items_filtered` | R4 [BUG-012] | ITEM-CNT-08 |
| `distinct_units_in_workspace` | R1 | ITEM-U-01 |
| `distinct_units_in_workspace` | R2 | ITEM-U-02 |
| `distinct_units_in_workspace` | R3 | ITEM-U-03 |
| `distinct_units_in_workspace` | R3a [BUG-017] | ITEM-U-04, ITEM-U-11 |
| `distinct_units_in_workspace` | R4 [BUG-017] | ITEM-U-05, ITEM-U-06, ITEM-U-07, ITEM-U-12 |
| `distinct_units_in_workspace` | R5 | ITEM-U-01, ITEM-U-07, ITEM-U-08 |
| `distinct_units_in_workspace` | R6 | ITEM-U-08, ITEM-U-09, ITEM-U-10 |
| `find_similar_by_name_in_workspace` | R1 | ITEM-S-03, ITEM-S-04, ITEM-S-05, ITEM-S-06, ITEM-S-07, ITEM-S-08 |
| `find_similar_by_name_in_workspace` | R2 | ITEM-S-09 |
| `find_similar_by_name_in_workspace` | R3 | ITEM-S-01, ITEM-S-10 |
| `find_similar_by_name_in_workspace` | R4 | ITEM-S-12, ITEM-S-23, ITEM-S-27 |
| `find_similar_by_name_in_workspace` | R4a [BUG-034] | ITEM-S-11 |
| `find_similar_by_name_in_workspace` | R5 | ITEM-S-01, ITEM-S-02 |
| `find_similar_by_name_in_workspace` | R6 | ITEM-S-13 |
| `find_similar_by_name_in_workspace` | R7 | ITEM-S-14, ITEM-S-15, ITEM-S-16, ITEM-S-17, ITEM-S-24 |
| `find_similar_by_name_in_workspace` | R8 [BUG-011] | ITEM-S-18, ITEM-S-19, ITEM-S-20, ITEM-S-21, ITEM-S-22; endpoint part deferred (`GET /items/similar/`) |
| `find_similar_by_name_in_workspace` | R9 [BUG-018] | ITEM-S-23, ITEM-S-24, ITEM-S-25, ITEM-S-26 (non-strict), ITEM-S-28 (strict, statement recorder) |
| `find_similar_by_name_in_workspace` | R10 | ITEM-S-01, ITEM-S-05 |
| `find_similar_by_name_in_workspace` | Errors row 1 (negative limit) | ITEM-S-17 |
