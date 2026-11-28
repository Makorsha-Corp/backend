# Tester pre-check: dao-machine_item (2026-11-27)

Unit `dao-machine_item`, `app/dao/machine_item.py`, bugs BUG-976, BUG-977, BUG-979,
BUG-980, BUG-981, BUG-982. BUG-983 is not in this unit (db-change, multi-file, later).

**Verdict: all 36 target tests are right. No wrong tests; `wrong-tests.md` unchanged.**

How found: bare-number grep over `tests/**/*.py` (only three files hit), plus the
`xf("BUG-…")` helper and `BUG_TITLES` dict in the item summary service file. The manager
(`list_machine_items` → `get_by_machine`) and the service (`_machine_placements` →
`get_by_item`) are the only callers in `app/`.

Run: the 36 targets once with `--runxfail` against `bf_dao_machine_item_test`:
**31 failed, 5 passed** (the 5 are non-strict physical-order cards whose order matches by
accident today: MIM-L-24, MIT-GM-32, MIT-GT-27, MIT-GT-34, MIT-GM-28). Every strict test
fails on the line its card names. Unmodified run of the dao + manager files:
436 passed, 242 xfailed, 10 xpassed (xpasses are all non-strict).

## Per bug

### BUG-976 (`get_by_machine` R6: item name case-insensitive, then row id): right
- Strict: `tests/unit/dao/test_machine_item.py::test_mit_gm_36__the_machine_list_query_asks_for_item_name_case_insensitive_then_row_id`
  (SQL text: `ORDER BY`, `lower(`, `.name` before `machine_items.id`, no `DESC`; exactly one SELECT).
- Non-strict: MIT-GM-31, -32, -33, -34, -35 (dao); MIM-L-02, MIM-L-24
  (`tests/unit/managers/test_machine_item_manager.py`).
- Judgement: checks R6 and R7 (order before paging), nothing more. **SQL-text risk for the
  systems engineer:** MIT-GM-36 needs `lower(` in the ORDER BY, i.e. `func.lower(Item.name)`,
  the codebase convention (factory_section, item_tag, account_tag DAOs; brief names it).
  Ordering by `items.name_normalized`, a `COLLATE`, or a raw `text()` sort would fail it.
  It also needs one single SELECT (R11: item data with no further query).

### BUG-977 (`get_by_item` R6: row id ascending): right
- Strict: MIT-GT-28 (`machine_items.id` in the ORDER BY, no `DESC`, one SELECT);
  `tests/unit/services/test_item_summary_service.py::test_ism_dp_07__placement_read_has_order_by`
  (every SELECT naming `machine_items` during `get_summary` has an ORDER BY; today there is
  exactly one such SELECT).
- Non-strict: MIT-GT-27, MIT-GT-34.
- Judgement: right; a plain `.order_by(MachineItem.id)` passes both strict ones.

### BUG-979 (`get_by_machine` R4a/R4b: deleted machine or deleted factory → `[]`): right
- Strict: MIT-GM-16, -17, -18, -52 (dao); MIM-L-03, MIM-L-04 (manager).
- MIT-GM-17 / -52 use a W2 stock row pointing at a W1 machine (spec R2: only the row's
  `workspace_id` is compared): the parent's state hides it all the same. A join on
  `machines.id` / `factories.id` only (the brief says so) passes them, and keeps the R2
  holding cards green. A fix that adds `Machine.workspace_id == workspace_id` would also
  hide those rows but break the R2 plain-pass cards; the flip check would catch it.
- R4c (no change to rows, inactive-but-live hides nothing, back once live) is covered by
  plain-pass cards that must stay green.

### BUG-980 (`get_by_machine` R5: removed item hidden, takes no place in the page): right
- Strict: MIT-GM-25, -26, -27 (skip=2 of two visible rows → `[]`), -53, -54 (dao);
  MIM-L-05 (manager).
- Non-strict: MIT-GM-28 (Anvil removed, Bolt active, `limit=1` → Bolt; needs R6 too for
  a deterministic answer, hence non-strict; the strict MIT-GM-27 is the proof).
- MIT-GM-53 uses an item of another workspace (removed): hidden by its state. Passes with a
  join on `items.id` + `is_active`, independent of BUG-1086.

### BUG-981 (`get_by_item` R3a/R3b): right
- Strict: MIT-GT-13, -14, -15, -16, -17, -33 (dao);
  `test_ism_dp_04__placement_on_deleted_machine_not_listed`,
  `test_ism_dp_05__placement_on_machine_of_deleted_factory_not_listed` (service: placement
  list and `machine_placement_count`).
- No test asks `get_by_item` to hide a removed item (R4 stays raw; BUG-1339 is the
  service's). The brief tells the fixer not to add the item filter here.

### BUG-982 (`get_by_item` R5: no cap; parameters removed): right
- Strict: MIT-GT-25 (501 rows), MIT-GT-32 (no `LIMIT`, no `OFFSET` in the SQL, one SELECT);
  `test_ism_dp_06__placements_not_capped_at_500` (service, 501 placements and count 501).
- No test anywhere passes `skip` / `limit` to `machine_item_dao.get_by_item` (the
  `get_by_item(... skip=, limit=)` calls in `test_machine_item_ledger.py` are the ledger
  DAO). The only `app/` caller passes neither, so removing the parameters breaks nothing;
  `tests/test_item_summary_empty.py` patches the method with `return_value=[]`, unaffected.

## Outside this unit

- **Spec R2 vs HR-16.** `get_by_machine` R2 / `get_by_item` R2 keep returning a stock row
  whose machine (or item) belongs to another workspace, while HR-16 (owner, 2026-10-30)
  says such links are invalid data and no response may show them. BUG-1086 covers the
  other-workspace *item* (filter "also in `app/dao/machine_item.py`"); nothing logged
  covers an other-workspace *machine* at this DAO. When BUG-1086 is planned, its unit will
  change R2 and the R2 plain-pass cards here (they will flip pass → fail), so that unit
  must carry those card edits. Not a wrong test today.
- BUG-983 unit (later): FU-3 (b) of the spec, `ensure_machine_item` R4 / EMI-07 builds
  two rows for one key and will fail once the index exists.
- Item summary `_machine_placements` fallbacks (`Machine #<id>`, factory `—`) become
  unreachable for deleted machines after BUG-981 (spec FU-2 (a)); service unit to check.
