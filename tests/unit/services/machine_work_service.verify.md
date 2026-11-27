# Verification — `app/services/machine_work_service.py`

> **Verdict:** NEEDS WORK
> Tests: 65 passed · 5 xfailed (reproduced ✅) · coverage 98% branch (line 118 only, unreachable)
> Mutation: 44 mutants · 43 killed · 1 survived → score 100% (after excluding 1 equivalent, 0 dead, 0 bug-path)
> Source commit: e48a092 · Cases revision: 3

## Summary
The assertions are good. Every Then line is asserted exactly, in card order, and the xfails are honest. All 44 `mutate.py` mutants and all 56 of my own variants are caught, apart from one equivalent mutant. That covers the transaction contract, error mapping, row locks, HR-16 for W0 and W2, where the BUG-1571/1572 fixes go, and the horizon maths. The result is NEEDS WORK for one reason, a setup finding: 48 of the 55 database tests never run the **commit point** that the Conventions require after the last Given line. It doesn't change any outcome today, because the service is read-only and every Given row is flushed. But the Givens are not built as the cards describe. The executor adds `commit_point(db)` and re-runs. No new bug.

## Findings
| # | Kind | Case / line | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | Wrong setup | CR-01…CR-23, CR-26, UW-01…UW-15, DM-03…DM-11 (48 tests) | Conventions: "**commit point** = after the last Given line the test runs `db.commit()`". Only CR-24, CR-25, CR-27, UW-16, DM-01, DM-02 and DM-12 call `commit_point(db)`. The other 48 database tests go straight from the last Given builder to the When, so the call runs with the Given objects still unexpired in the identity map instead of after a savepoint release. Sibling suites (`test_machine_service.py` 115 calls / 113 tests, `test_factory_service.py` 41 / 39) run it in every test. | AST scan of the test file (list in Traceability below). The notes' "How the tests are built" defines the commit point but doesn't say it is skipped. | **executor** — add `commit_point(db)` after the last Given in those 48 tests. Where a test then reads a Given object's id for the When or Then, copy the id first, as CR-27 does. Re-run 3× plus `--runxfail`. |
| 2 | Doc drift (minor) | test module docstring | Says "Implements … cases.md (Revision 2)". The cases are at Revision 3. | line 3 of the test file | **executor** (when fixing #1) |
| 3 | Register drift (minor) | `docs/testing/bugs.md` BUG-1572 row | The Location column still names `collect_raw_items` as the place. The Intended column (after D2) says the fix belongs in `upcoming_work`, **not** in `collect_raw_items`. The tests pin D2 correctly (see variants). | bugs.md line 565 | **describer** (register upkeep: change Location to `upcoming_work`) |

## Surviving mutants
| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 14 | 91 | `'machine'` → `''` (initial key of the `defaultdict` bucket) | equivalent | Every bucket is created by `by_machine[mid]` on line 100, and line 101 assigns `bucket["machine"]` right after. Nothing reads the key before that, so a missing initial key, or an extra unused `""` key, cannot be observed. | — |

## Coverage
Line 118 (`continue` when `machine is None`) is the only miss, on one partial branch. It is unreachable. A bucket exists only after the loop on lines 97–112 puts a query row's `machine` into it. The query inner-joins `Machine` and filters `machine_id IS NOT NULL`, so `machine` is never `None`. The spec (D5) names it as dead code, and it is already in `docs/testing/dead-code-removal-checklist.md`. Mutants #7 and #11 (negated `if` / `is` → `is not` on line 117) are killed, because their inverse branch drops every row.

## Variants (my own, on a temp copy; `variants.py` in the scratch folder)
Every variant is caught by a passing test, or behaves as designed under `--runxfail`:

| Area | Variant | Caught by |
|---|---|---|
| TC6, a read that commits | `db.commit()` after the query / at entry of `collect_raw_items`; in `dates_by_machine` | CR-25, UW-16, DM-12 (and CR-27) |
| TC6, rollback | `db.rollback()` at end of `upcoming_work`; in the `dates_by_machine` empty shortcut | UW-16 (+UW-06); DM-01, DM-02 |
| TC6, partial write / state change | `db.flush()`, `db.expire_all()` inside `collect_raw_items` | CR-25, UW-16, DM-12 |
| TC1–TC5 | not applicable: the service is read-only (no commit, rollback or write in source; spec Form) | — |
| Error mapping | `ValueError` → `RuntimeError`; → a `ValueError` subclass; swallowed → `False`; horizon clamped to `date.max` | HH-08 |
| Lock | `.with_for_update()` (Postgres refuses it on the outer-joined eager load) | 48 tests |
| Lock | `.with_for_update(of=WorkOrder)` | CR-24 |
| HR-16 W0/W2 | correct fix `Machine.workspace_id == workspace_id` | 65 pass; under `--runxfail` CR-15, CR-16, UW-14 and DM-09 pass (UW-13 still fails: BUG-1572 is separate) |
| HR-16 W0/W2 | half fix `>=` (W2 still leaks) / `<=` (W0 still leaks) | CR-15, UW-14, DM-09 / CR-16 still fail. The W0 and W2 cards are both needed. |
| HR-16 | filter only in `upcoming_work` | CR-15, CR-16, DM-09 still fail |
| BUG-1572 placement | factory filter in `collect_raw_items` (wrong place) | CR-18, DM-08 (D2 pinned) |
| BUG-1572 placement | filter in `upcoming_work` (right place) | 65 pass; UW-13 passes under `--runxfail` |
| BUG-1572 placement | also hides inactive factories | UW-15 |
| Horizon maths | `+h−1`, `+h+1`, `today < d`, `d < end`, no lower bound, `abs(h)` | HH-01/05; HH-02/06/07; HH-03/05; HH-01/05; HH-02/06/07; HH-07 |
| Helpers | `has_overdue` `<=` / `all`; `earliest` `>` / `max` / first item | HO-02 / HO-01; EU-02 / EU-01, EU-02 / EU-01, EU-02 |
| Sorting | row sort case-sensitive / `-machine_id` / machine id only; item sort `-source_id`; earliest = last item | UW-11; UW-10; UW-10, UW-11 |
| `dates_by_machine` | no sort; deduplicate; no empty shortcut; generator consumed twice; statuses dropped | DM-03; DM-03; DM-01, DM-02; DM-04; DM-06 |
| Filters | factory on `Machine.factory_id`; row factory from the order; `is_active` filter; no eager load; `if statuses` / `if machine_ids`; case-insensitive status; `upcoming_work` adds COMPLETED / drops `factory_id`; `count` by distinct date; `is_deleted` on orders dropped; exclusive end / start | CR-19, UW-03; UW-03, UW-06; CR-13; CR-27; CR-09 / CR-23; CR-06, CR-07; UW-02 / UW-03; UW-05; CR-12; 8 / 13 tests |

Observation, not a finding: DM-03 caught "no sort" in the plain run but not in the `--runxfail` run of the same variant. Its kill depends on the order Postgres happens to return the rows. Mutation score is unaffected (`mutate.py` has no "drop sort" operator).

## Fidelity
I read all 70 tests against their cards. Apart from finding 1, the Givens match each card: rows, order, `but` columns, the gone forms, and W0/W2 rows. Each When is the card's call with the same keywords. Each Then line is asserted with the exact value and operator, in card order. CR-27 reads the ids before the commit point and checks `inspect(mb).unloaded` before touching `mb`. There are no `try` blocks and no broad `pytest.raises`. The only patches are the Conventions' commit/rollback **spies**. `committed:` lines are preceded by one `db.rollback()`. Every xfail is `strict=True` and its reason names the BUG ID: BUG-1571 for CR-15, CR-16, UW-14 and DM-09; BUG-1572 for UW-13.

`--runxfail`: each of the 5 fails on its card's "Fails today on" Then 1 assertion:
- CR-15 :494 `pairs(result) == {(o1.id, m1.id)}` (extra (OS, M9));
- CR-16 :509 (extra (OS, M0));
- UW-13 :917 `[r.machine_id …] == [m1.id]` (Kiln listed);
- UW-14 :932 (Grinder listed);
- DM-09 :1119 `result == {m1.id: [START]}` (M9 is a key).

None failed on setup or import.

## Traceability
- Cases: 70. Tests: 70, one per case ID, in card order.
- Unmatched: none.
- Marker mismatches: none (5 xfail BUG cards = 5 strict xfails; 65 `pass` cards with no marker).
- `# Then N` count equals the card's Then count for every test.
- BUG-1571 and BUG-1572 exist in `bugs.md`.
- Tests missing the commit point (finding 1): CR-01–CR-23, CR-26, UW-01–UW-15, DM-03–DM-11.

## Commands run
```
$env COVERAGE_FILE=<scratch>/.cov_run1
.venv/Scripts/python.exe -m pytest tests/unit/services/test_machine_work_service.py -q -p no:cacheprovider -o addopts="" --cov=app.services.machine_work_service --cov-branch --cov-report=term-missing
  app\services\machine_work_service.py  68 1 16 1  98%  118
  65 passed, 5 xfailed
(run 2) 65 passed, 5 xfailed   (run 3) 65 passed, 5 xfailed   — no flakiness
.venv/Scripts/python.exe -m pytest … --runxfail -rf
  5 failed, 65 passed  (CR-15, CR-16, UW-13, UW-14, DM-09 — each on Then 1)
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/services/machine_work_service.py tests/unit/services/test_machine_work_service.py --lines 1-100 --json <scratch>/mut1.json
  Mutants: 18 · killed 17 · survived 1 (#14 L91 'machine' -> '')
… --lines 101-189 --json <scratch>/mut2.json
  Mutants: 26 · killed 26 · survived 0
.venv/Scripts/python.exe <scratch>/variants.py <scratch>     (56 variants, all caught; log in variants.log / variants.json)
.venv/Scripts/python.exe -m ruff check tests/unit/services/test_machine_work_service.py   → All checks passed!
```
Scratch: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\svc2v2\machine_work_service\`.

## Routed
- **executor**: finding 1 (add the commit point to 48 tests), finding 2 (docstring revision).
- **describer** (register): finding 3 (BUG-1572 Location → `upcoming_work`).
- case designer, spec: none.

## Round 2 — 2026-11-22

> **Verdict:** PASS
> Tests: 65 passed · 5 xfailed (reproduced ✅, 3 runs, no flakiness) · coverage 98% branch (line 118 only, unreachable) · Cases revision: 3a

Round 1 findings:
- **Finding 1 (executor) — fixed.** All 55 database tests now call `commit_point(db)`. No test builds a Given row after it, apart from the documented TC6 "after the commit point" rows in CR-25, UW-16 and DM-12 (scratch `r2_cp.py`, `r2_cp2.py`). The 15 pure-function tests (EU, HO, HH) have no database setup.
- **Finding 2 (executor) — fixed.** The docstring now says Revision 3a.
- **Finding 3 (describer, register) — fixed.** BUG-1572's Location now names `upcoming_work`, per spec D2, and says "not `collect_raw_items`".
- **DM-03 faithful to its card.** O1–O9 are in Given order and machine, with the card's dates, status and factory. Then 1–3 are asserted exactly, including the new sorted-lists line.
- `--runxfail` still fails all 5 xfails (CR-15, CR-16, UW-13, UW-14, DM-09) on Then 1. Ruff is clean.

Targeted variants (scratch `variants.py`, log `r2_variants.log`):
- **Killed:** TC-read-commits, TC-commit-first, TC-rollback (upcoming), TC-flush, TC-expire, TC-commit (dates), TC-rollback (dates-empty), DM-dedupe, ROW-sort-id-desc and ITEM-sort-id-desc. All 10 were caught, by the same tests as in Round 1.
- **DM-no-sort:** killed in only 2 of 5 runs of the full file. The other 3 runs ended "65 passed"; log `r2_nosort.log`.
- **DM-no-sort probe** (scratch `r2_probe*.py`, which prints the rows' order): DM-03's rows often come back neither in id order nor in reverse id order. In one run, M3's ids 846 (MID), 847 (START) and 848 (END) came back as 848, 846, 847, which is in date order (descending). So in the shared test database the order rows are stored in is not the order they were inserted. The test likely reuses space left by other agents' rolled-back rows, and a hash join then reads the rows in that stored order. The premise of the Rev 3a note is wrong, so no insertion order can make every unsorted read fail.

Remaining (non-blocking; the `mutate.py` score is still 100%, and the only survivor is the equivalent L91):
- **Case designer.** DM-03 kills a missing sort only some of the time. Either:
  - make an unsorted read unlikely: more orders per machine with distinct dates (e.g. 6+), and correct the Rev 3a note; or
  - record that a dropped `.sort()` can't be killed reliably because the database gives no row order.

  Do not weaken the case.
