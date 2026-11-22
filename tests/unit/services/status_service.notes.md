# Execution notes — `app/services/status_service.py`

> Cases: `tests/unit/services/status_service.cases.md` (revision 5) · Tests: `tests/unit/services/test_status_service.py` · Source commit: e48a092
> Result: 76 of 76 cases implemented · 37 passed · 39 xfailed (38 strict, 1 non-strict: L-09) · 0 open discrepancies (DISCREPANCY-1 closed 2026-11-04, see Revision history) · 0 errors — branch coverage 93% (3 missed lines: blocked today by BUG-035, see below)
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/services/test_status_service.py -q -p no:cacheprovider`

## How the tests are built
Same form as `item_tag_service.notes.md`. This service has no manager and does its own commits (S1–S4, S2a).
- **Actors:** `w1`, `w2`, `u1` (autouse `actors`). No workspace is seeded.
- **Given rows:** `mk_status(**but)` (default `Feat` / `A note` in W1), `mk_transfer(s, **but)`, `mk_purchase(s, **but)`, `mk_sales(s, **but)` (builds AC and FA right before the order), `mk_workflow(ids, **but)` (default `Flow`, type `PFM`). Each flushes.
- **Reading helpers:** `commit_point`, `n_all_of` (taken right after the commit point), `reread`, `snap_before` / `snap` (unchanged), `count_statuses(**filters)`, `ids`, `idset`, `unloaded`, `usable`, `spies`, `record_sql` / `the_select` / `order_part_of` (statement recorder, L-10).
- **BUG-035 cards** call with `workspace_id=` as written. Today they fail with `TypeError` in the When, just before `# Then 1`.
- The schema-only cards (C-03, C-07, C-08, U-15) take no fixtures except the autouse actors.

## Fails-today check
`--runxfail`, with the failing line mapped to its `# Then N`:
- L-02, G-05, C-01, C-05, C-11 … C-13, U-07, D-05: `TypeError` (no `workspace_id`) in the When, just before Then 1. C-09 and C-10 raise the same `TypeError` inside their Then 1 `raises:` wrap.
- L-09 (non-strict): Then 2 `['zeta', 'Alpha', 'beta']`. L-10: Then 2 `'lower(' in ''`.
- C-06, U-14: Then 1 `DID NOT RAISE ValidationError`. C-07, U-15: Then 1 `' Feat '` / `' Done '`.
- U-16: Then 1 `DID NOT RAISE IntegrityError`.
- U-08, U-09, U-19, U-21 … U-23, D-06, D-07, D-14: Then 1 `DID NOT RAISE HTTPException`.
- D-08 … D-11, D-15, D-17, D-18: Then 1, `IntegrityError` 23502 (`NotNullViolation` on `current_status_id`), which is what the cards name.
- **U-20: fails in its Given**, not at Then 1. See DISCREPANCY-1.

## Reference run
I wrote `refplug.py` (scratch `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\svc3e\status\`). It patches the five service methods in-process with the spec's intended behaviour:
- `workspace_id` scoping (left optional, so the cards that call without it still run);
- a `lower(name), id` order;
- BUG-1220: protection and the R4a detail, with a rollback before the 400;
- BUG-1218: the blocker list (`AppValidationError`), with a rollback first.

It also swaps `StatusCreate` / `StatusUpdate` in `app.schemas.status` for subclasses that trim and refuse blank names (BUG-1680). An autouse fixture creates a unique index on `(workspace_id, lower(btrim(name)))` inside each test's transaction (BUG-1221).
- With `--runxfail`: 70 passed, 1 failed (U-20, in its Given).
- With `REF_DROP_WF_UQ=1`, the plugin drops `uq_order_workflows_workspace_type` inside the test transaction. U-20 then passes under `--runxfail`, so its Then lines hold once its Given can be built.
- Without `--runxfail`: the 33 buildable strict cards XPASS (strict, so they fail), L-09 XPASSes, and U-20 still xfails.

## Stability
3 plain runs plus 1 run with `PGOPTIONS="-c enable_seqscan=off"` each gave 36 passed and 35 xfailed. No test moved. L-09 xfailed in every run. Ruff passes, an AST pass found no unused test arguments, and the file is LF.

## Discrepancies
| ID | Case | Designed | Actual | Evidence | Likely cause |
|---|---|---|---|---|---|
| DISCREPANCY-1 | SSV-U-20 | xfail BUG-1220, fails today on Then 1 | xfails, but at Given 3, today and after the fix | `UniqueViolation: duplicate key value violates unique constraint "uq_order_workflows_workspace_type"`. `order_workflows` is unique on `(workspace_id, type)`. Given F and G are both W1 workflows of type `PFM` (the convention's default; the "but" changes only `name`). | Card defect: the two workflows can't both exist. Fix: give G another type (e.g. `but name "Alt Flow", type "SFM"`). With the constraint dropped, the reference passes U-20. Marked `xfail(strict=True)` with the reason `BUG-1220; DISCREPANCY-1`. Goes back to the case designer. |

## Coverage gaps
| Lines | Kind | What the code does there |
|---|---|---|
| 23–25 | unreachable (today, BUG-035) | `create_status` success path: commit, refresh, return. `StatusCreate` has no `workspace_id`, so every create fails at the DAO's flush (23502) before line 23. The create cards that would reach it (C-01, C-05, C-11 … C-13) are BUG-035 xfails that stop at the `TypeError`. These lines become reachable when BUG-035 is fixed. |

93% (41 statements, 3 missed); all 4 branches covered, 0 partial.

## Factories added
None.

## Revision history
- **2026-11-04 — U-20 fix in, DISCREPANCY-1 closed.** The cases now give SSV-U-20's second workflow G `type "STM"`. The test now builds G with `type="STM"`, and the DISCREPANCY-1 text is gone from its xfail reason (strict, BUG-1220).
  - `--runxfail`: U-20 fails at Then 1, `DID NOT RAISE HTTPException`, which is the line its card names.
  - Reference plugin with `--runxfail`, constraint not dropped: all 71 tests pass.
  - 3 plain runs: 36 passed, 35 xfailed each time. Ruff passes; the file is LF.
  - The Discrepancies table above keeps the original record. The Result line now shows 0 open discrepancies.

- **2026-11-04 — Revision 3** (from `status_service.verify.md`).
  - R-ST-0: SSV-L-01 has joined the BUG-035 retire list. Notes only; no test changed (the Notes for maintainers already listed it).
  - R-ST-1: C-12, U-17 and D-13 now build `boom = RuntimeError("boom")` before the failing-commit wrap, pass it as `side_effect=boom`, and check `exc.value is boom` as Then 5. C-12 is still a strict BUG-035 xfail that stops at the `TypeError`.
  - R-ST-2: new SSV-L-12 (pass), the default `skip=0` with 2 rows.
  - No other test changed.
  - 3 plain runs: 37 passed, 35 xfailed each time. Coverage is unchanged: 93%, lines 23–25.
  - `--runxfail`: the same 35 tests fail on the Then lines their cards name; U-20 fails at Then 1.
  - Reference plugin with `--runxfail`: all 72 pass.
  - Scratch `varplug.py` rebuilds the verifier's variants: update and delete re-raise `RuntimeError(str(e))`, and the list defaults to `skip=1`. Under it U-17, D-13 and L-12 fail.
  - Ruff passes; the file is LF.

- **2026-11-04 — Revision 4** (owner answer OQ-13: stage names match ignoring capitals and outer spaces, BUG-1880).
  - Changed: SSV-U-24 (`"receiving"`) and SSV-D-16 (`" Complete"`) are now strict xfail BUG-1880 refusals that check the exact detail text.
  - New: U-25 (`" Receiving "`) and D-19 (`"COMPLETE"`), both strict xfail BUG-1880; U-26 (`"Re ceiving"`, renamed), pass.
  - `--runxfail`: U-24, U-25, D-16 and D-19 fail at Then 1, `DID NOT RAISE HTTPException`. The other 35 are unchanged.
  - Reference plugin: `refplug.py` now matches stage names with `strip().lower()`. With `--runxfail` all 75 pass; without it the 38 strict cards XPASS and L-09 XPASSes. BUG-1867, 1868 and 1879 are discussion-only, so they need no patch here.
  - 3 plain runs: 36 passed, 39 xfailed each time. Coverage is unchanged: 93%, lines 23–25. Ruff passes; the file is LF.

- **2026-11-04 — Revision 5** (verify round 3, R-ST-3).
  - New: SSV-D-20 (`"Com plete"`, a space inside, deleted), pass.
  - U-24, U-25, D-16 and D-19 are now marked strict xfail on both BUG-1220 and BUG-1880. Only the reason changed.
  - `--runxfail`: the same 39 fail on their named Then lines (U-24, U-25, D-16, D-19 at Then 1).
  - Reference plugin with `--runxfail`: all 76 pass.
  - With BUG-1220 fixed but stage names still matched exactly (scratch `no1880/refplug1220.py`), exactly those four fail. Both fixes are needed, as the Expect lines say.
  - 3 plain runs: 37 passed, 39 xfailed each time. Ruff passes; the file is LF.

## Notes for maintainers
- When BUG-035 lands, every card that is not about BUG-035 gains `workspace_id=w1.id` (cases Reviewer summary). L-01, G-04, C-02, U-06 and D-04 retire.
- `TO-1`, `SO-1` and `PO-1` are the cards' literal numbers. `transfer_number` and `sales_order_number` are unique across all workspaces, so two runs side by side that both build them wait on each other's transaction (no failure, just a wait).
- L-09 rests on physical order and stays non-strict until BUG-1681 is fixed.
