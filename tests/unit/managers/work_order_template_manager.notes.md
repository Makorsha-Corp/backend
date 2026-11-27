# Execution notes — `app/managers/work_order_template_manager.py`

> Cases: `tests/unit/managers/work_order_template_manager.cases.md` (revision 5) · Tests: `tests/unit/managers/test_work_order_template_manager.py` · Source commit: e48a092
> Result: 213 passed · 136 xfailed (all strict) · 0 open discrepancies (DISCREPANCY-1 closed in revision 3) · 0 errors — branch coverage 99% (156 statements, 56 branches; 1 line / 1 branch part missed, unreachable)
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/managers/test_work_order_template_manager.py -q -p no:cacheprovider -o addopts="" --cov=app.managers.work_order_template_manager --cov-branch --cov-report=term-missing` (with `COVERAGE_FILE` set to a private file)

## How the tests are built
- **One test per card, in card order.** Cards that share the Given and the Then and differ in one input are parametrized with one `pytest.param(id="WTMG-…")` per card. Examples: the schema refusals CT-36…39/47, UT-24…31, UT-72/73/76, AI-18…23/26, UI-14/15, UI-19/21/23; the cadence tables AR-02…09 and GD-10…19; the order shapes AR-14…19 and GD-27/28/29/31/32. All 349 IDs were checked against the collected node IDs: none missing, none extra, none twice.
- **Standing rows** (Conventions 1–9) come from the fixture `R`. It is built in every test, in the stated order, one flush per row: `R.W0 < R.W1 < R.W2`, `R.U1…U5`, the five memberships, `R.WT0/1/2/9`, `R.F0/1/2/9`, `R.S0/1/2/3/9`, `R.M0/1/2/3/9` with their section assignments, `R.I0/1/2/3/9`, `R.A0/1/9`.
- **Given rows:**
  - `tpl(db, R, **over)` is the Conventions "template". `tpl_w0` and `tpl_w2` are the W0 and W2 variants.
  - `WEEKLY`, `DAILY` and `monthly(d)` are the cadence shorthands.
  - `line`, `approver` and `order` are line(T, I), approver(T, U) and order N(m, d).
  - `gone(R)` is "gone" for a type or section. `gone_off(R)` adds `is_active False` for a machine or account.
  - `many_templates(db, R, n)` builds E1…En with `add_all` (LT-05/06, GD-40/41).
  - Every builder flushes.
- **Named checks:**
  - `reread` = `expire_all` + `db.get`.
  - `snap(db, x)` reads every column with a Core `SELECT` by primary key, so it never sees the identity map. `unchanged(X)` is a `snap` taken after the last Given line, compared with `unchanged_snap` (`expire_all`, then `snap`) after the When.
  - `counts(db)` is "nothing written": the row counts of the four tables across all workspaces.
  - `approvers`, `lines`, `drafts` and `pairs` follow the Conventions literally.
  - `record_sql(db)` is the statement recorder: a `before_cursor_execute` listener on `db.connection()`, removed after the block. `locks_of(log)` keeps the `SELECT … work_order_templates … FOR UPDATE` statements.
- **"Rolled back" cards** (RA-13, CT-46, UT-75, DT-06, RT-08, AI-25, UI-22, RI-06, AR-24, GD-48) work like this:
  - `sp = db.begin_nested()`, and the call runs inside `patch.object(db, "commit", wraps=db.commit)`.
  - The inside counts are taken, then `sp.rollback()`, then the after counts.
- **Refusal cards** use a plain `pytest.raises(HTTPException)` with no savepoint. `session:` checks run before any re-read.
  - The five xfail cards whose call raises `IntegrityError` today (CT-13, CT-20, UT-38, AI-15, UI-17) fail inside the `pytest.raises` block. That is Then 1, as their cards state.
- **`Author: claude` cards:**
  - **RI-07** builds a `WorkOrderItem` with the card's columns plus `workspace_id=W1.id`. That is the only other NOT NULL column of `work_order_items` without a default. `uses_inventory`, `created_at` and `is_deleted` have defaults.
  - **AR-25** patches `wom.create_work_order_from_template` (spec Notes, G6). The patch calls the real method on the first call and raises `HTTPException(400, "boom")` on the second.
  - **GD-43** uses the same patch target. It raises `RuntimeError("boom")` for T1's `template_id` and calls the real method for every other template. It checks `caplog` at WARNING.
    - The When sits under `# Then 1`: today the call itself raises, so Then 1 (`pairs(result)`) is never reached. This matches the card's "Fails today on: Then 1 (the call raises RuntimeError)".
- **Nothing else is mocked** (Externals: none).
- **Explicit ids** 770001 and 770002 (UI-05, RI-05) are inserted inside the test's transaction. A parallel run that uses the same ids waits for this rollback and does not fail.

## Verification done
- **3 plain runs (revision 4):** 213 passed and 136 xfailed each time. A junit check compared every outcome, by card ID, with the card's `Expect` line and the bug number in the xfail reason: no mismatch.
- **`--runxfail`** with the executor's own `failson_wotm.py` plugin (failing line → `# Then N`), revision 4: all 136 xfail cards fail, each in the Then line its card names in "Fails today on". The failing assertion is the one the card describes, for example:
  - `DID NOT RAISE` for the refusals;
  - `'  Oil change  ' == 'Oil change'` (CT-10);
  - `None == 31` (CT-42, UT-59);
  - `0 >= 1` on `locks` (AR-22, GD-42);
  - the extra drafts on M1 and M2 (Q19-01…04, Q19-07);
  - N cut off (GD-41).
- **Reference plugin** `ref_wotm.py` (scratch, in-process, never in `app/`) puts in the intended fix of all 19 bugs as the spec states them:
  - schema bounds, trimming and nulls;
  - link, line and approver checks in R10 order;
  - merged-state 422s;
  - a stamp only on a real change;
  - section templates selected in SQL, non-recurring only;
  - `FOR UPDATE` with `populate_existing`;
  - a savepoint and a WARNING per template.

  Under `--runxfail -p ref_wotm`, all 349 pass (revision 4). The plugin needed no change for the revision-4 cards: its section run already takes non-recurring templates only (Q19-07), and it checks the links before the lines and each line's item before its replaced item and its own rule (CT-56…60). In revision 2, CT-26 and CT-27 failed there (DISCREPANCY-1).
- **Coverage (revision 4):** 99% branch, unchanged (line 261, unreachable).
- **Lint and files:** `ruff check` is clean. The file is LF only.
- **Unused arguments:** an AST pass found none. `db` was dropped from CT-07/08, which only build a schema.

## Discrepancies
| ID | Case | Designed | Actual | Evidence | Likely cause |
|---|---|---|---|---|---|
| DISCREPANCY-1 (**closed** 2026-11-09, cases revision 3) | WTMG-CT-26, WTMG-CT-27 | pass | pass today; **fail once BUG-2350 is fixed** | Both send line quantities with three decimals (`0.125`, `2.345`, `0.124`, `-1.005`) through `WorkOrderTemplateItemCreate` and expect them stored, rounded half up. AI-20 (strict xfail BUG-2350) expects the same `IC(quantity=Decimal("0.125"))` to raise `ValidationError`, and spec `create_template` R9 refuses three-decimal line quantities. Under the reference plugin both fail with `decimal_max_places`. The cases' revision note says "no pass card sends a three-decimal value", but these two were missed in the G7 sweep. | Case-design contradiction (cases revision 2, G7). Not a code bug. Route to the case designer: turn CT-26/27 into strict xfail BUG-2350 schema refusals (as CT-36…39), or drop them. The markers are left as designed, because the outcome today is as designed. |

## Coverage gaps
| Lines | Kind | What the code does there |
|---|---|---|
| 261 (`continue` in the de-dupe loop of `generate_drafts`) | unreachable | `section_templates` already leaves out every id in `recurring`, and neither list can hold the same row twice, so a repeated `tpl.id` never occurs. The de-dupe is defensive. |

## Factories added
None. Every model here is used only by this module's tests. Builders are local.

## Notes for maintainers
- **When a bug is fixed**, its strict xfails XPASS (red): remove the marker. Which cards change with each fix:

  | Bug | Cards |
  |---|---|
  | BUG-2350 | CT-26, CT-27, CT-36…39, CT-47, UT-72/73/76, AI-18…21, AI-23, AI-26, UI-19/21/23 |
  | BUG-1015 | 32 cards (27 + CT-56…60) |
  | BUG-2339 | 20 cards |
  | BUG-2335 | RA-06…12, CT-34, UT-65, UT-78, Q21-08 |
  | BUG-2346 | Q21-01, Q21-02, Q21-04, Q21-05, Q21-12 |
  | BUG-2345 | Q19-01…04, Q19-07 |
  | BUG-2343 | AR-22, GD-42 |
  | BUG-2344 | GD-43 |
  | BUG-2342 | GD-41 |

- **The reference plugin** is a usable sketch of the fix. See `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\tple\wotm\ref_wotm.py`.
  - BUG-2344's savepoint per template needs `session.begin_nested()` inside the loop. `sp.rollback()` expunges the failed template's drafts from the session.
  - BUG-2343's lock is `with_for_update().populate_existing()`. It refreshes the caller's template object, which is safe because callers flush first.
- **Fragile spots:**
  - `created_at` has a server default of `now()`, which is constant inside one transaction. Every list and order card therefore sets `created_at` explicitly, as the cards say.
  - GD-40 and GD-41 build 999 and 1000 templates (about 1 s each).
  - Work order numbers for drafts come from `WorkOrderDAO.get_next_number`. The given orders use `WO-<name>`, so they never collide.
- **Run time** is about 35 s, or 70 s with coverage.

## Useful for the coming permissions / notifications / payment features
- **Permissions:**
  - No role check anywhere. Any active member can create, edit, deactivate and restore templates, pick default approvers, and run `generate_drafts` (spec "Permission checks"; already in `docs/future/permissions.md`).
  - After BUG-2335, the approver rule is "active member of this workspace", the same as the work order's own approver check. It does not mean any particular role.
- **Notifications:**
  - `generate_drafts` and the anchored range create draft work orders through `WorkOrderManager.create_work_order_from_template`. That call logs a `created_from_template` event, which is the natural hook for a "drafts planned" notification.
  - After BUG-2344, a skipped template produces a WARNING log with the template id. That is a candidate for an "a template could not be planned" alert.
- **Payments / plans:** none directly. `cost` and `account_id` are copied onto the draft (GD-49). BUG-2350 bounds `cost` to `Numeric(15, 2)`.

## Revision history
- **2026-11-09 — Revision 2 (first execution):** 338 cases → 210 passed · 128 xfailed (strict). DISCREPANCY-1 recorded (CT-26 and CT-27 against BUG-2350). No new bug.
- **2026-11-09 — Revision 3:** cases revision 3 closes DISCREPANCY-1. 339 cases → 209 passed · 130 xfailed (strict).
  - CT-26 and CT-27 were rewritten to match their new cards: strict xfail BUG-2350 schema refusals of `IC(quantity=0.124)` and `IC(quantity=-1.005)`, with Then 1 `ValidationError` and Then 2 nothing written. Under `--runxfail` both fail on Then 1 (`DID NOT RAISE ValidationError`).
  - New pass card CT-55: 0 and -1.01 are stored exactly.
  - No other test changed.
  - Under the reference plugin all 339 pass. Coverage is unchanged at 99% (line 261, unreachable). ruff is clean, the file is LF only, and 3 plain runs gave the same result each time.
- **2026-11-09 — Revision 4:** cases revision 4 (verifier findings 1–5). 349 cases → 213 passed · 136 xfailed (strict).
  - New: CT-56…CT-60 (strict xfail BUG-1015, check-order pairs), Q19-07 (strict xfail BUG-2345, due tomorrow), UT-79/80 and UI-25/26 (pass, `cost` and `quantity` at the Numeric(15, 2) bounds through `TU` and `IU`; parametrized in pairs).
  - Changed: GD-44 gains Z9, a non-recurring W2 template on S9, with Then 4–5. It was split out of the GD-44/45 parametrization, and GD-45 is now its own test, with the same checks as before.
  - Finding 5 (executor): "Verification done" now shows the current numbers.
  - No other test changed and no ID was retired. `ref_wotm.py` needed no extension.
  - Checks: `--runxfail` makes all 136 xfail cards fail on their named Then line; all 349 pass under the reference plugin; 3 plain runs gave the same result each time; coverage is still 99%; ruff is clean and the file is LF only.
- **2026-11-09 — Revision 5:** cases revision 5 (verifier round 2). In GD-44, the W2 template Z9 now has `default_machine_id=R.M9.id`; that is the only test change. Counts are unchanged at 349 cases (213 pass, 136 xfail).
  - GD-44 passes today.
  - Checked against `mut_unscoped.py`, an executor scratch plugin: `WorkOrderTemplateDAO.get_by_workspace` drops its workspace filter, so the section run of `generate_drafts` also sees Z9. Under it GD-44 fails: drafting Z9 on M9 raises `HTTPException 404: Work order template with ID … not found` from `create_work_order_from_template`. The test now catches a section run that is not scoped by workspace.
  - Checks: 3 plain runs, all with the same result; ruff is clean and the file is LF only.
