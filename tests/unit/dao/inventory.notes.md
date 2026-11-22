# Execution notes — `app/dao/inventory.py`

> Cases: `tests/unit/dao/inventory.cases.md` (191 cases) · Tests: `tests/unit/dao/test_inventory.py` · Source commit: e48a092
> Result: 158 passed · 32 xfailed · 1 xpassed (INV-ST-03, non-strict by design) · 0 discrepancies · 0 errors — branch coverage 91%
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/dao/test_inventory.py -q -p no:cacheprovider --cov=app.dao.inventory --cov-branch --cov-report=term-missing`

191 tests for 191 cases: 4 exemplars and 9 `Author: claude` cards written by Claude,
178 written by the local model (each under a `# [local-coder] <ID>` comment).
Four consecutive runs gave the same outcome. With `--runxfail -rf`: 32 failed, 159
passed — every strict xfail fails on an `assert` line (no setup error), and INV-ST-03
passes.

## How the tests are built
- **Constants:** `dao` (module-level alias of `inventory_dao`; a fixture named `dao`
  also exists, so a test that lists `dao` as an argument still works), `STORAGE`,
  `DAMAGED`, `WASTE`, `SCRAP`, `MISSING`, `T0`…`T5`.
- **Actor / fixed-row fixtures:** `w1`, `w2`, `u1`, `u2`, `f1`, `f2`, `f9`, `i1`, `i2`,
  `i9`. The autouse fixture `fixed_rows` requests all of them, so the six fixed rows
  exist in every test (Conventions) and are inserted in the order F1, F2, F9, I1, I2, I9
  — whether or not a test lists them as arguments.
- **Builder fixtures** (insert one row, flush, return it): `mk_item(name, **columns)`,
  `mk_factory(name, abbreviation, **columns)`,
  `mk_stock(item, factory, deleted=False, **columns)`,
  `mk_entry(item, factory, *, qty_after, avg_price_after, performed_at, **columns)`.
  They are fixtures because the runner treats calls to fixture names as builders
  (keyword check).
- **Reading helpers** (plain functions): `reread(db, row)` (expire_all, then SELECT by
  id), `snap(db, row)` (all columns, for `unchanged`), `count_rows(db, Model)`,
  `written(db)` (`nothing written`), `ids`, `names`, `by_type`, `high_id(db)`.
- **HIGH_ID** is a function, not a constant or fixture: it must be evaluated at the
  moment the entry is inserted (after E1), which makes it greater than every later
  sequence id by construction.
- **Nothing is mocked** except what Conventions declare for the `Author: claude` cards
  (helpers at the end of the test file):
  - `race_r9()` / `race_r10()` — the two `patch.object(inventory_dao, …)` patches of
    "race R9" / "race R10" (INV-EN-22, EN-23, EN-24). With the row present and both
    pre-insert lookups patched to miss, the real INSERT hits
    `uq_inventory_workspace_item_type_factory` inside the DAO's own savepoint; R9's
    second any-lookup delegates to the real method, R10's keeps returning `None`.
    Coverage confirms lines 278–289 run.
  - `commit_spy(db)` — `patch.object(db, "commit", wraps=db.commit)` for the four
    "rolled back" cards (INV-SY-16, EN-25, EN-26, R-05). Each takes
    `sp = db.begin_nested()` directly before the call, checks inside the savepoint,
    calls `sp.rollback()`, checks again, and asserts `spy.call_count == 0`.
- Database errors: `DataError` cards wrap the call in `db.begin_nested()`;
  `IntegrityError` cards do not (the DAO uses its own savepoint).
- INV-GI-05 builds 26 factories × 4 inventory types = 104 stock rows of I1 in a loop.

## Local-coder run
Model: Qwen3.6-35B-A3B Q4_K_M on llama-server, n_ctx 16,384, thinking off, two repair
attempts per card. Helper sheet 9,208 characters. 6,728 s of model time in total
(≈ 38 s per card), 1.16 M prompt tokens, 41.5 k completion tokens.

| Part | Cards sent | Accepted 1st try | Accepted after retry | Escalated |
|---|---|---|---|---|
| Trial (3 rounds) | 26 | 19 | 7 | 0 |
| Full run | 152 | 134 | 18 | 0 |
| **Total** | **178** | **153** | **25** (23 on the 2nd attempt, 2 on the 3rd) | **0** |

The 9 `Author: claude` cards were skipped by the tool as designed. No escalation, so
there is no escalation root cause to report.

**Cards that needed a retry, and why.** The report keeps the last rejected code
(`last_code`) but not the rejection message for a card that was accepted later; the
reason below was recovered by replaying the tool's `static_check` on `last_code`
(read-only; the tool itself was not run again). All 25 are model slips caught before
acceptance:

| Cause | Count | Cards |
|---|---|---|
| A row the test builds itself (`ia`, `ib`, `fa`) also listed as a fixture argument | 13 | FQ-19, FQ-26, FQ-27, FQ-32, FQ-33, FQ-34, FQ-35 (3 attempts), FQ-37, CNT-10, CNT-12, CNT-13, ST-22, ST-23 |
| `before = written(db)` (or `before_count`) copied from the INV-L-17 exemplar into a card that has no "nothing written" line — unused variable | 6 | EN-12, EN-16, EN-18, EN-19, EN-20, EN-21 |
| `unchanged` snapshot taken after the When call | 3 | SY-09, EN-11, EN-14 (3 attempts) |
| A fixture used but not in the argument list (`f9`, `u2`) | 3 | CNT-02, CNT-03, EN-17 |

**xfail review (Step D).** All 31 local xfail tests were compared with their cards:
`fails_in_then` equals the card's "Fails today on: Then N" in every one, and the
failing assertion is the one the card describes with the value it predicts (e.g.
FQ-26 `[S2] == [S1]`, SY-17 `15 == 10`, L-04 `['bolt', 'Bolt']`, EN-07 `updated_by`
still U1, ST-20 `(STORAGE, 2, 37)`). None was rewritten.

**Mechanical checks on the accepted tests.** `ruff --select F` and an AST pass for
unused arguments and variables; in addition each unused name was looked up in its
card's When / Then lines, and the number of `nothing written` / `unchanged(X)` Then
lines was compared with the number of matching before/after pairs in each test. No
unused `before…` variable, no dropped check.

### Accepted local tests repaired in Step D
**Functional repairs: 0 of 178.** (None — no test was rewritten, strengthened or had
an assertion or a Given value changed.)

**Cosmetic removals: 474** in 158 of the 178 local tests — 245 unused fixture
arguments and 229 unused `sN = …` / `eN = …` builder bindings (the call is kept, the
name dropped). Done by script; no assertion, call or value touched. Before: 229 ×
F841; after: `ruff --select F` clean.

Not repaired, left for the verifier to see as delivered:
- INV-CNT-11's function is named `test_inv_cnt_11__factory_filter_soft_delete_and_scope`
  — the slug is copied from the INV-ST-12 exemplar; docstring, setup and assertion are
  the card's.
- One accepted test (INV-EN-17, as delivered) contains a comment restating a Given line.
- A few docstring first lines lack the final full stop.

Sheet changes: none during the full run (the two changes made during the trial are
the ones described in the trial; the "local row as argument" slip remained the most
frequent retry cause in the full run — 10 of its 18 retries — so the sheet wording
alone does not prevent it).

No tool false negative was found in Step D (0 accepted tests needed a functional
repair by the finishing step; the verifier has not run yet).

## Fix round 1 (after verification round 1)

Verifier verdict: NEEDS WORK — 2 functional and 9 cosmetic findings, all in local-written tests; no mutant survived in specified code. Fixed by hand:

- **INV-ST-13** — "S9" was built in `f2`; now `mk_stock(i9, f9, workspace_id=w2.id)` as Conventions define it (`f9` added to the arguments).
- **INV-EN-13** — Then 6 asserted `count_rows(db, Inventory) == before_count + 1`; now the card's literal `== 2`, and the `before_count` snapshot the card does not ask for is removed.
- **INV-FQ-40, INV-CNT-11** — function-name slug copied from the INV-ST-12 exemplar; renamed from the card title.
- **INV-EN-17** — stray `# Given` / `# When` comments removed.
- **INV-FQ-24, FQ-25, FQ-26, FQ-34, L-06, ST-25** — final full stop added to the docstring's first line.

After the fixes: 158 passed · 32 xfailed · 1 xpassed (INV-ST-03, non-strict by design), three runs; `--runxfail`: 32 failed, 159 passed; `ruff --select F` clean; branch coverage unchanged at 91%.

## Discrepancies
None.

INV-ST-03 (BUG-719, non-strict xfail by design) **XPASSes** in all four runs: with the
four types inserted in the order SCRAP, WASTE, DAMAGED, STORAGE the database still
returns the per-type rows in enum order (sort-based GROUP BY on the native enum). The
card and the spec's designer note both expect this; it is not a discrepancy and the
assertion was not weakened. The bug stays open because no `ORDER BY` guarantees it.

## Coverage gaps
102 statements, 10 missed; 30 branches, 2 partial — 91%.

| Lines | Kind | What the code does there |
|---|---|---|
| 153 | dead | body of the `get_by_workspace` override (review Q3: remove; spec "Not specified", dead-code checklist `app/dao/inventory.py:146`) |
| 305->306, 306 | dead | `get_by_item`'s `inventory_type` filter (review Q5: remove the parameter and its `if inventory_type:` filter; dead-code checklist `:297,305-306`) |
| 311–318 | dead | `soft_delete` (review Q4: remove; dead-code checklist `:309`) |
| 260->262 | unreachable | the `False` side of `if existing.is_deleted:` — a row that the live lookup missed but that is live at the second lookup. Needs a concurrent transaction; the spec's Branch map (row 260–261) says "not reachable in a single session, no rule". |

Every other line and branch of the spec's Branch map is covered, including the race
branch 278–289 (both sides of `if not row:` and of `if row.is_deleted:`). No spec gap.

## Factories added
None.

## Notes for maintainers
- Spec gaps listed in the cases file, checked against `app/models/` and the test
  database: (1) `items` has no unique constraint or index besides the primary key, so
  "Bolt" and "bolt" can coexist in W1 — INV-L-04 / L-05 are implementable as written.
  `factories` has no unique constraint either (INV-GI-05 does not depend on it).
  (2) The item columns are named `description` and `sku` — INV-FQ-23 runs as written.
  (3) `InventoryTypeEnum` values are the upper-case member names; no card depends on
  them.
- INV-L-04 relies on the database collation (`English_United States.1252`) sorting
  "bolt" before "Bolt"; on a `C`-collated database it would XPASS.
- INV-ST-03 is a non-strict xfail that passes today (see Discrepancies). When BUG-719
  is fixed, remove its marker.
- When a bug is fixed its strict xfail tests XPASS (= fail): remove the marker.
  BUG-880: FQ-10, CNT-07, ST-16 · BUG-881: EN-07 · BUG-882: FQ-36, FQ-37, FQ-38, L-19,
  CNT-10, CNT-11, ST-18, ST-19, ST-20 · BUG-883: FQ-31…34, L-21, CNT-12…14, ST-21…24 ·
  BUG-884: GI-09, GI-10 · BUG-701: L-04 · BUG-702: FQ-24, FQ-25, FQ-26 · BUG-664: SY-17.
- When the dead code is removed (`get_by_workspace` override, `soft_delete`,
  `get_by_item`'s `inventory_type`), the only coverage gap left is the
  partial branch 260->262; no test needs to change.
- The race tests patch methods on the `inventory_dao` singleton with `patch.object`
  inside a `with` block, so the patches cannot leak into other tests.
- The runner truncates bug titles to 90 characters in xfail reasons (BUG-883, BUG-882).
- The helper sheet is 9,208 characters, slightly over the skill's 9,000 limit; prompts
  still fit (5,500–5,700 tokens first attempt, ≈ 6,600 on a third).
