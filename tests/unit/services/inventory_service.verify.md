# Verification — `app/services/inventory_service.py`

> **Verdict:** PASS
> Tests: 63 passed · 23 xfailed + 1 non-strict XPASS (INVS-S-09) (reproduced ✅, 3 identical runs) · coverage 98% branch (49 stmts, 1 missed: line 60, dead)
> Mutation: 17 mutants · 14 killed · 3 survived → score 100% (after excluding 0 equivalent, 3 dead, 0 bug-path)
> Hand variants: 83 service mutants (transaction contract, error mapping, pass-through, HR-16, BUG-3082) · 83 killed · lock-clause variants 5/5 behave as spec R1a says
> Source commit: e48a092 · Cases revision: 2

## Summary
You can trust these tests. All 87 cards are implemented one-to-one, and the markers match each card's Expect line. Every strict xfail fails today on the Then line its card names. Every tool mutant in live code was killed. So were all 83 hand-written variants: the transaction contract TC1–TC6, error mapping, every pass-through argument, a W0 workspace swap and a user-id swap. The lock check in U-12 / D-09 holds for `FOR UPDATE OF inventory` and only for that. A plain `FOR UPDATE`, `NOWAIT`, `SKIP LOCKED` or `FOR SHARE` each fail it. Only one thing is advisory, for the case designer: the BUG-3082 cards cannot tell a real fix from one that drops the parameter until BUG-700 is fixed (see Notes).

All 87 tests are written by claude; there is no `.local-run.json`, so there are no local-coder findings.

## Findings
None.

## Surviving mutants
| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 2 | 60 | `return` → `return None` | dead | `list_inventory` is listed as dead under the spec's Not specified, and on `docs/testing/dead-code-removal-checklist.md` | — |
| 8 | 58 | default `skip` 0 → 1 | dead | same callable (`list_inventory` signature) | — |
| 9 | 58 | default `limit` 100 → 101 | dead | same callable | — |

## Variants tried (hand mutants on a temp copy; own script `hand_mutants.py` in the scratch folder)
| Area | Variants | Result |
|---|---|---|
| TC1 no commit | commit removed / replaced by `flush()` in create, update, delete | killed (5–7 tests each: C-01/C-07/C-13/C-15/C-16, U-01/U-07/U-15/U-16, D-01/D-02/D-11 …) |
| TC3 missing rollback | `_rollback_transaction` removed in each write path | killed (create 5, update 4, delete 3 failures). The TC3 cards check `x_gone` and `inv_count` with no test rollback before them, so a pending X left in the session is seen |
| TC3 commit before the error / partial write | `db.commit()` before the manager call; `commit` instead of rollback in `except`; `commit` + `rollback` in `except` | killed (X committed → `x_gone` fails) |
| TC2 re-read | `refresh` removed / replaced by `expire` | killed (`loaded(result)` in C-01, U-01, D-01) |
| TC4 / TC5 | covered by C-10/C-11, U-09/U-10, D-06/D-07; tool mutants `raise → pass` (L36, L49, L127) killed | killed |
| TC6 read that commits / rolls back / flushes | before the manager call in get, page, stats, incoming; commit after the get; rollback on the 404 path of get and incoming | killed (spies plus `B in db.dirty` / `x_there`) |
| Error mapping | all errors → 500 HTTPException; non-HTTP errors wrapped in RuntimeError; HTTPException re-raised with an altered detail; swallowed with `return None` | killed in each write path |
| Pass-through | each of `inventory_type`, `factory_id`, `item_id`, `search`, `include_zero_qty` dropped or forced, for page and stats; factory/item swapped; `skip`/`limit` dropped or swapped; default limit 49 / 100; default `include_zero_qty=True`; incoming `factory_id` dropped or `or None` (the `factory_id=0` boundary) | killed |
| HR-16 (W0 / W2) | `workspace_id` replaced by 0 in create, get, page, stats, incoming | killed; the W2 foreign rows (C-03, U-02, G-02, G-08, D-03, IS-04, P-01, S-01) hold their 404 or exclusion |
| Audit user | `user_id=None` in create, update, delete | killed |
| Lock (BUG-704/705, own plugin `lock_variants.py`, `--runxfail`) | `with_for_update(of=Inventory)` → U-12, D-09 pass; plain `FOR UPDATE` → Postgres `FeatureNotSupported` (outer join), U-01/D-01 fail too; `nowait`, `skip_locked`, `read` → U-12, D-09 fail on Then 2 | pinned exactly as R1a says |
| BUG-3082 (own plugin `dropped_param.py`, `--runxfail -k invs_g_`) | `include_deleted` accepted but not passed on | G-05, G-06, G-07 **pass**; only G-04 (BUG-700) fails — see Notes |

## Notes for future work
- **Case designer (advisory, not blocking):** BUG-3082 depends on BUG-700. While the manager still returns soft-deleted rows (BUG-700 open), a service that accepts `include_deleted` and ignores it passes G-05, G-06 and G-07. Those strict xfails would XPASS, and their markers would be removed even though nothing reaches the manager. G-05 only catches a dropped parameter once BUG-700 is fixed. Suggest a "Fix after BUG-700" line on G-05 … G-07 (or on the BUG-3082 row in `bugs.md`). Another option is a card that sets `include_deleted=False` on a soft-deleted row and expects 404, which also only bites after BUG-700. Today the class is bug-path, so it does not change the verdict.
- **Executor (none):** S-09 XPASSes every run, as its non-strict card allows. IS-09 xfails every run.
- **Integration (already deferred in cases):** real two-connection lock races (BUG-704/705), the `include_deleted` query parameter, and the global handlers' 409/500/422.
- **Lock clause:** the probe confirmed that a plain `FOR UPDATE` errors on this load (`FOR UPDATE cannot be applied to the nullable side of an outer join`). The fix must use `with_for_update(of=Inventory)`. `inventory_manager.spec.md` R10 / R8 still say plain `FOR UPDATE` (spec G2): **describer**, outside this file.

## Traceability
cases 87 · tests 87 · every ID in exactly one docstring and one `# [claude]` tag · unmatched: none · marker mismatches: none (63 `pass` without marker; 22 strict `xfail` whose reasons name the card's BUG IDs; S-09 BUG-719 and IS-09 BUG-706 non-strict as their cards say). All 18 BUG IDs used (700–707, 710, 712–719, 3082) exist in `docs/testing/bugs.md`. `ruff check`: all checks passed.

**Fidelity:** every card was read against its test. Given rows are built in card order with the Conventions defaults. Then lines are asserted in order with the card's exact values, and `committed:` lines start with one `db.rollback()`. No patch is used beyond the Conventions' spies, failing commit / refresh and the C-09 race simulation. No `try/except` and no broad `pytest.raises`. **`--runxfail`:** 23 failed, 64 passed (S-09). Each failure is on its card's "Fails today on" line: C-05, C-06, U-05, G-04, IS-05 → Then 1 DID NOT RAISE. G-05, G-06, G-07 → Then 1 TypeError. C-14 → Then 1 IntegrityError at the call. C-12, U-13, D-10 → Then 3 `total_cost` None. U-06 → Then 2 `'n1' is None`. U-11 → Then 2. U-12, D-09 → Then 2 (no `FOR UPDATE`). U-14 → Then 2 (0 ledger rows). P-11 → Then 2 (collation order). P-12, S-08 → Then 1 (2 rows). IS-07 → Then 2 (15.00 ≠ 7). IS-09 → Then 2. D-08 → Then 2 (qty -4).

## Commands run
```
COVERAGE_FILE=<scratch>/.cov-run .venv/Scripts/python.exe -m pytest tests/unit/services/test_inventory_service.py -q -p no:cacheprovider -o addopts="" --cov=app.services.inventory_service --cov-branch --cov-report=term-missing -rX   (x3)
  app\services\inventory_service.py  49  1  0  0  98%  60
  63 passed, 23 xfailed, 1 xpassed  (runs 1–3 identical; XPASS = INVS-S-09)
COVERAGE_FILE=<scratch>/.cov-rx .venv/Scripts/python.exe -m pytest tests/unit/services/test_inventory_service.py -q -p no:cacheprovider -o addopts="" --runxfail -rf --tb=short
  23 failed, 64 passed
COVERAGE_FILE=<scratch>/.cov-mut .venv/Scripts/python.exe tests/unit/_tools/mutate.py app/services/inventory_service.py tests/unit/services/test_inventory_service.py --timeout 300 --json <scratch>/mut.json
  Mutants: 17 · killed 14 · timeout 0 · survived 3 · score 82%   (survivors L58 ×2, L60: dead list_inventory)
.venv/Scripts/python.exe <scratch>/hand_mutants.py          → 83 variants, 83 killed, 0 survived
LOCKMODE={of,plain,nowait,skip,read} pytest … -p lock_variants --runxfail -k "u_12 or d_09 or u_01 or d_01"
  of: 4 passed · plain: 4 failed (FeatureNotSupported) · nowait/skip/read: U-12, D-09 failed on Then 2
pytest … -p dropped_param --runxfail -k invs_g_   → 9 passed, 1 failed (G-04 only)
.venv/Scripts/python.exe -m ruff check tests/unit/services/test_inventory_service.py   → All checks passed!
```
`<scratch>` = `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\svc2v\inventory\`
