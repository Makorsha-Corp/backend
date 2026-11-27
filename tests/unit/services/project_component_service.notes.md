# Execution notes — `app/services/project_component_service.py`

> Cases: `tests/unit/services/project_component_service.cases.md` (revision 4) · Tests: `tests/unit/services/test_project_component_service.py` · Source commit: e48a092
> Result: 129 of 129 cases implemented · 80 passed · 49 xfailed (48 strict bug cards incl. D-06 BUG-2262, and 1 non-strict, L-27; all xfailed) · 0 errors · 0 open discrepancies (DISCREPANCY-1 settled by cases revision 3) — branch coverage 94% (2 dead lines)
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/services/test_project_component_service.py -q -p no:cacheprovider`

## How the tests are built
Same form as `test_project_service.py`: one test per card, in card order, `# [claude] <ID>` above each, `# Then N` before the checks of Then line N.
- **Standing rows:** autouse fixture `S`: W0, W1, W2, U1 / U2 / UG with W1 memberships, F0, F1, F9, then P0, PA, PB (private, creator U1), P9, each flushed, in the Conventions' order.
- **Given rows:** `comp(db, P, name, k, **but)` (explicit id `XID(k)`), section builders `cr_upd` (CR of the update section: "Roof", "Top", budget 100, PLANNING, XID(12)) and `cr_del` (CR of the delete section), `um`, `member(..., ws=)`, `pmem`, `set_owner`, `proj(..., private=, deleted=, **but)`, `bulk(db, n, P)`, `wt1`, `wo(..., deleted=)`, `i1`, `line`, `task(..., note=, **but)`, `act`, `ledger`, `misc`, `at0`, `att`, `pev`. Every card commits at `commit_point(db)`; `extra_x`, `pending_q` and `edit_e` run after it.
- **Checks:** `snap` / `unchanged`, `counts` (project_components, project_events), `x_count`, `evs(db, P.id, type)`, `reread`. Ids copied to locals before the When.
- **Spies:** `spies` (commit, rollback), `failing_commit`, `failing_refresh` (both with the rollback spy), `recorder` set after the commit point.
- L-40 runs the call inside `db.begin_nested()` within `pytest.raises(DataError)`.
- D-06 (BUG-2262) fails today in the When call itself; its `# Then 1` comment sits above the call, so the failure maps to Then 1 as the card names.

## Fails-today check
`--runxfail` with the scratch plugin `then_check.py` and `then_report.py` (shared with `project_service`). Revision 3: all 47 xfail cards (D-06 included: Then 1, `IntegrityError` NotNullViolation on `project_component_attachments`) fail on their named Then line, 0 mismatches. Revision 2: all 46 bug cards fail on the Then line their card names, 0 mismatches, with the value the card describes:
- L-19, L-22: Then 1, the deleted project's component is listed. L-20: Then 1, `set()`. L-21: Then 1, V1 and V2. L-23: Then 2, `12 <= 3`. L-25: Then 1, `['Zulu', 'apple', 'Banana']`. L-26: Then 1, `['Zulu']`. L-27 (non-strict): Then 1, `[XID(12), XID(11)]`. L-28: Then 2, no `ORDER BY`. L-39: Then 1, `['Beta', 'alpha', 'Gamma']`.
- L-35, L-36, G-08, C-10, U-09, D-11: Then 1, `DID NOT RAISE HTTPException`.
- C-12, C-13, C-18, C-19, C-20, U-13, U-14, U-19, U-21, U-22: Then 1, `DID NOT RAISE ValidationError` (pydantic).
- C-11: Then 2, `'  Roof  '`. U-18: Then 2, `'  Roof deck  '`. U-10: Then 2, `'Top'`. U-11: Then 2, `Decimal('100.00')`. U-12: Then 2, the deadline. U-16, U-17: Then 2, one `component_updated` event.
- D-13, D-14, D-19, D-20, D-26: Then 1, `DID NOT RAISE ValidationError` (the delete succeeds). D-15 … D-18, D-21 … D-24: Then 1, `IntegrityError` (NotNullViolation at the flush).

## Reference run
`ref_pcs.py` (scratch, `-p ref_pcs`, `PYTHONPATH` = scratch folder) patches in memory: fixed `ProjectComponentCreate` / `ProjectComponentUpdate` (stripped non-blank name; `budget` a decimal `ge=0, max_digits=15, decimal_places=2`; null `name` / `status` refused: BUG-2272, 2273, 2274, 2275), `require_project_access` refusing a deleted project with 404 (BUG-1278), DAO `get_by_project` ordered `lower(name), id` (BUG-1275), `get_components` (only `None` means no project, BUG-2278; one query joining the project, deleted projects and inaccessible private projects filtered in SQL, `lower(name), id`, then paging: BUG-2277, 2279, 1278), `update_component` (`exclude_unset` only, event only when a value changes: BUG-2275, 2276), `delete_component` (blocker list in the spec's type order, other workspaces as one last `other_workspace`, `ValidationError("Component has history")`: BUG-1196; link rows of `project_component_attachments` deleted first: BUG-2262).
- With `--runxfail`: **126 passed** (D-06 included, through the BUG-2262 fix).

## Discrepancies
| ID | Case | Designed | Actual | Evidence | Likely cause |
|---|---|---|---|---|---|
| DISCREPANCY-1 (settled, cases revision 3: D-06 is now strict xfail BUG-2262, R5a) | PCS-D-06 | pass: a component with a `project_component_attachments` row is deleted, the link row goes by CASCADE | `IntegrityError` (NotNullViolation) at the flush: `UPDATE project_component_attachments SET project_component_id=NULL` | The model's backref `ProjectComponent.attachments` (no `passive_deletes`) makes the ORM null the children before the delete; the column is NOT NULL, so the database CASCADE never runs. The model is registered app-wide (`app/models/__init__.py`, `app/db/base.py`), so production behaves the same. | Code bug against spec R5 → logged as **BUG-2262** (`orm-nulls-cascade-child`). No app code writes this table any more (dead DAO), so only older rows are affected. Marked `xfail(strict=True, reason="DISCREPANCY-1 (BUG-2262) ...")`; the describer should tag R5 for these rows with BUG-2262 and the designer change D-06's Expect. |

## Coverage gaps
| Lines | Kind | What the code does there |
|---|---|---|
| 101 | dead | `update_component`: `if not component: return None` after the guard already 404s (spec D1, dead-code checklist) |
| 135 | dead | `delete_component`: `if not component: return False`, same (spec D1) |

## Factories added
None.

## Notes for maintainers
- When a bug is fixed its cards XPASS: remove the marker. Schemas: BUG-2272 … 2275 (`app/schemas/project_component.py`); service: BUG-2275, 2276, 2277, 2278, 2279, 1196; manager: BUG-1278; DAO: BUG-1275; model: BUG-2262.
- L-27 is non-strict: it rests on physical order (two equal-but-case names).
- L-20 relies on today's physical (insertion) order for its strict failure, as the spec's Notes ask.
- The blocker cards D-15 … D-18, D-21 … D-24 fail today because the ORM nulls each child's NOT NULL FK (the same mechanism as BUG-2262), not because of the ledger's RESTRICT.
- Components use explicit ids `XID(k)` (pid-based), so parallel runs do not collide.

## Scratch
`C:\Users\User\AppData\Local\Temp\makorsh-pipeline\wpsvce\B\` — `ref_pcs.py`, `then_check.py`, `then_report.py`, `.coverage.PCS`.

## Revision history
- **Revision 3 (2026-11-05)** — cases revision 3 (from DISCREPANCY-1). D-06 rewritten to its new card (renamed `test_pcs_d_06__attachment_links_go_with_component`): `xfail(strict=True, reason="BUG-2262")` replaces the DISCREPANCY marker (definition removed); Given now adds C2 and its own link LK2; Then 4–8 check the `Attachment` row and LK2 stay, C2 stays, one `component_deleted` event with its description and metadata. D-15's comments renumbered to Then 5, 6 as the card. Header points at revision 3. No other test changed; no ID retired. Re-verified: 79 passed / 47 xfailed in each of 3 plain runs; `--runxfail`: 47 of 47 xfail cards fail on their named Then line (0 mismatches); `ref_pcs.py` with `--runxfail`: 126 passed (D-06 through its BUG-2262 fix, no plugin change); branch coverage 94% (lines 101, 135, dead); ruff check and format clean; LF.
- **Revision 4 (2026-11-06)** — cases revision 4 (verifier findings 1, 2). Added `test_pcs_l_43__project_list_keeps_pending_changes` (PCS-L-43, CT6 on the `project_id` path; pass; after L-42), `test_pcs_d_27__trailing_space_attachment_added_blocks` (PCS-D-27, `"attachment_added "`) and `test_pcs_d_28__attachment_add_blocks` (PCS-D-28, `"attachment_add"`), both strict xfail BUG-1196, appended after D-26. No existing test changed; no ID retired; `ref_pcs.py` needed no change (its activity exclusion is already an exact `NOT IN`). Re-verified: 80 passed / 49 xfailed in each of 3 plain runs; `--runxfail`: 49 of 49 xfail cards fail on their named Then line (D-27, D-28: Then 1, `DID NOT RAISE ValidationError`), 0 mismatches; `ref_pcs.py` with `--runxfail`: 129 passed; branch coverage 94% (lines 101, 135, dead); ruff check and format clean; LF.
