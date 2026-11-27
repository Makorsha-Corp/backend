# Execution notes — `app/services/account_tag_service.py`

> Cases: `tests/unit/services/account_tag_service.cases.md` (revision 3) · Tests: `tests/unit/services/test_account_tag_service.py` · Source commit: e48a092
> Result: 82 of 82 cases implemented · 41 passed · 41 xfail as designed (39 strict, all xfailed; 2 non-strict, T-07 and Y-04, xfailed in every run) · 0 errors · 0 discrepancies — branch coverage 96% (the 3 missed lines are unreachable)
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/services/test_account_tag_service.py -q -p no:cacheprovider`

## How the tests are built
Same form as `item_tag_service.notes.md`, the twin module. The service has no manager and runs its own transaction (S1–S4).
- **Actors:** `w1`, `w2` and `u1` exist in every test (autouse `actors`).
- **Given rows:** `mk_tag(name, tag_code, **but)`, `mk_system_tag(name, tag_code, **but)`, `DELETED` (`is_active False`), `mk_account()` (A1 = `Account(workspace_id=W1.id, name="Acme")`), `mk_link(account, tag)`, `mk_extra()` (X, built after the commit point). Index cards C-16, C-17 and C-27 insert directly with `AccountTag(**_tag_fields(...))`, as Conventions say (C-16 and C-27 inside `db.begin_nested()`). T-08 builds its 101 tags with `add_all`.
- **Reading helpers:** `reread` (any model, also used for links), `snap_before` / `snap` (all columns at the commit point / after a re-read), `count_tags`, `written`, `new_row(db, w1, given=())`, `ids`, `unloaded`, `usable`, `spies`.
- **Race simulation:** C-18 only, `patch.object(account_tag_dao, "get_by_tag_code_in_workspace", return_value=None)` inside the `raises:` wrap.
- **S3:** C-19, C-30, U-01, U-05, U-17, D-02 and D-06 build X after the commit point and check that it is still there after the refusal. The failing-commit cards (C-37, U-22, D-07) and C-39 check that it is gone.

## Fails-today check
With `--runxfail`, I mapped each failing line to its `# Then N` (scratch plugin `failline.py`). All 41 match their cards:
- T-04: Then 2, `AccountTagResponse` refuses `""`. T-08: Then 1 `100 == 101`. Y-03: Then 1, the deleted system tag is in the list.
- T-07 (non-strict): Then 2, insertion order `[K1, K2, K3, KS]`. Y-04 (non-strict): Then 2 `['Utility', 'client', 'Bank']`. Both did this in every run.
- C-02 … C-05, C-33, U-13, U-14, U-20: Then 1 `DID NOT RAISE ValidationError`.
- C-10, C-11, C-14, C-15: Then 1, the codes are `café`, `""`, `_bolt_` and `কচমল`.
- C-12: the When raises `DataError` (StringDataRightTruncation), just before `# Then 1`, as its card says. C-21 … C-24: the When raises the 409 their cards name (`vendor_x`, `steelbar`, `steelbar`, 50 × `a`).
- C-16, C-27: Then 1 `DID NOT RAISE IntegrityError`.
- C-18, C-25, C-26, C-29, C-30, U-03, U-04, U-15, U-16, U-17, D-04: Then 1 `DID NOT RAISE HTTPException`.
- C-28: Then 3, the code's message comes back instead of the name's.
- C-34: Then 2 `' Bolt '`. U-21: Then 2 `'  Vendor Prime  '`. U-09: Then 3 `'vendor_x'`. U-11: Then 2, the snapshot shows `tag_code 'renamed'`. U-12: Then 2 `'#000000' is None`.

## Reference run
`refplug_at.py` (scratch, written from the spec only) replaces the schemas and the five service methods in memory:
- **Schemas:** `AccountTagCreate` trims `name`, refuses a blank name and checks `tag_code` against `^[a-z0-9_]+$`. `AccountTagUpdate` has no `tag_code`, trims `name`, and refuses null `name` / `is_active`. `AccountTagResponse` takes any stored code.
- **Lists:** live tags only, ordered by `is_system_tag desc, lower(name), id`, with no cap.
- **Create:** the live-name check runs before the code check, and the 409 shows the trimmed name. Only live tags block a code; the check goes through the DAO, so C-18's patch still applies. Derived codes are ASCII, cut to 50, `tag` when nothing is left, then the first free `_2`, `_3`… with the base cut. A unique violation at the flush becomes the 409 after the rollback.
- **Update / delete:** 404 for a deleted tag. Update applies `exclude_unset`, so an explicit null clears.
- **Indexes:** inside each test's transaction, partial unique indexes on live tags for `(workspace_id, tag_code)` and `(workspace_id, lower(btrim(name)))`.

Results:
- With `--runxfail`: **81 passed**. Every check after each failure point also runs and holds.
- Without `--runxfail`: 39 strict cards XPASS, which strict mode reports as failures; the 2 non-strict cards XPASS; 40 pass.
- No test was changed for the reference.

## Stability
3 plain runs, plus 1 run with `enable_seqscan = off` (scratch plugin `noseq.py`, `SET LOCAL` on the test session): 40 passed, 41 xfailed in all 4 runs. No test changed outcome. `ruff check` passes, and so does the `F841,F811` check plus an AST pass for unused test arguments. The file uses LF line endings (no CR bytes).

## Discrepancies
None.

## Coverage gaps
| Lines | Kind | What the code does there |
|---|---|---|
| 46, 64, 80 | unreachable | `except HTTPException: raise` in `create_tag`, `update_tag`, `delete_tag`. Nothing inside those `try` blocks raises an `HTTPException` (spec FU-2; cases "Deferred": no case). |

Coverage is 96% of lines (64 statements, 3 missed), and all 12 branches are covered (0 partial).

## Factories added
None.

## Revision history
- **Revision 3 (2026-11-04):** cases revision 3, from `account_tag_service.verify.md` (R-AT-1, R-AT-2). No other test changed, and no test-weakness was routed to the executor.
  - **Added ATV-U-23 (pass):** the re-read after the commit fails on `update_tag`; the error reaches the caller and the rename stays saved.
  - **Changed ATV-C-37, U-22, D-07:** `boom = RuntimeError("boom")` is built first and given as `side_effect=boom`, and a new Then 5 checks `exc.value is boom`.
  - **Runs:**
    - 3 plain runs (the coverage run is one of them): 41 passed, 41 xfailed in each.
    - Sequential scans off: the same.
    - `--runxfail`: the 41 xfail cards fail on the same lines as before, each as its card says.
    - `refplug_at.py` with `--runxfail`: 82 passed. U-23 needed no change to the reference.
    - Coverage is unchanged at 96%; lines 46, 64 and 80 are still unreachable.
    - `ruff` passes; the file is LF.
  - **Verifier's variants:** I rebuilt them in scratch `r3var.py` and ran them against the pass cards. Each is caught, only by the card meant for it:
    - `wrap_create` fails C-37 at Then 5 (`RuntimeError('boom') is RuntimeError('boom')`); `wrap_update` fails U-22 there, and `wrap_delete` fails D-07 there.
    - `update_swallow_refresh` fails U-23 at Then 1 (`DID NOT RAISE RuntimeError`).
    - `update_undo_on_refresh_fail` fails U-23 at Then 2 (`False is True`).

## Notes for maintainers
- T-07 and Y-04 are non-strict because, with no ORDER BY, the order is whatever Postgres returns. Today that is insertion order every time, so both xfail. Once BUG-1482 is fixed they pass. Remove the markers then.
- T-08 builds 101 rows, and is the slowest card.
- When BUG-1684 / BUG-1689 land as migrations, C-16, C-27 and C-18 XPASS. The fix must turn the race's unique violation into the 409 (C-18 Then 3), not a 500.
- The 3 unreachable `raise` lines go away with the fixes (spec FU-2).
