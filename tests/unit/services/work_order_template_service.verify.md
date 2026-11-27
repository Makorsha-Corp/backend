# Verification — `app/services/work_order_template_service.py`

> **Verdict:** PASS (round 2, 2026-11-09; round 1 was NEEDS WORK)
> Current (round 2): 41 passed · 9 xfailed · 100% branch · mutation on round-1 survivor line 60: 2/2 killed · Cases revision 3
> Tests: 39 passed · 9 xfailed (reproduced ✅: all 9 strict, each failing on its card's "Fails today on" line) · coverage 100% branch (91 statements, 2 branches)
> Mutation: 21 mutants · 20 killed · 1 survived → score 95% (after excluding 0 equivalent, 0 dead, 0 bug-path)
> Hand variants (in memory, 42 run): 40 caught · 2 survive (both case-missing, below)
> Source commit: e48a092 · Cases revision: 2

## Summary
The tests are faithful. All 48 cards map one to one onto 48 tests. Every Then line has its assertion, in the card's order. Refusal cards check the session (`new`/`dirty`/`deleted`) before any re-read. `committed:` lines re-read after one `db.rollback()`. The only patches are the ones the Conventions name. The three runs match the notes, and nothing is flaky.

The transaction contract holds up well against hand-written breakage:
- a commit removed from any write
- a rollback removed from any write
- a re-read removed, or done before the commit
- reads that commit or roll back
- reads that skip the workspace scope

`generate_drafts` passes its arguments through correctly. Each of these was caught:
- `target_date` ±1 day
- `factory_section_id` or `factory_id` dropped, or the two swapped
- `user_id` dropped

Two gaps remain, both in the case design, not in the tests:
1. `list_templates`' `limit` is never proved to reach the manager, neither the passed value nor the default 100.
2. `generate_drafts` R3 ("any exception") is checked only with an `HTTPException`.

## Findings
| # | Kind | Case / line | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing | WTSV-L-01 (`list_templates` R1, "all five arguments reach the manager"), source lines 58–66 | L-01's Given leaves only two rows that match the filters (B, A). After `skip=1` only A is left, so `limit=1` changes nothing. Dropping `limit` (or passing 100) still returns `[A]`. Also, no card calls the service without `limit` on more than 100 rows, so the signature default `limit=100` (L60) is never seen. The endpoint always passes `limit`, so the default matters only for direct callers. | Mutant #8 `L60:36 100 -> 101` survived. Hand variant `list_drop_limit` (manager called with `limit=100`) survived: 39 passed. | case designer: in L-01, add a third inactive WT1 template A0 (`created_at T0`), so that the expected result `[A.id]` depends on `limit=1`. Add one card with 101 W1 templates and no `limit` → `len(result) == 100` (as in `help_ticket_service` L-09). |
| 2 | case-missing | `generate_drafts` R3 ("**any** exception from the manager rolls back"), source line 141 | GD-03 raises an `HTTPException` only, and TC4 (failing commit) is carded on `create_template` / `delete_template` / `remove_item` only. If `except Exception` in `generate_drafts` is narrowed to `except HTTPException`, a database error inside a Plan-day run (e.g. `IntegrityError` / `DataError` — see BUG-2344, BUG-2350) would leave the session dirty, and no test notices. | Hand variant `gd_except_http_only` survived: 39 passed. | case designer: one more card like GD-03 whose `boom` raises `RuntimeError("boom")` (or a failing commit around `generate_drafts`). Then: same object re-raised, session clean, T's date back to D16, nothing written. |

No fidelity findings. Checked against every card:
- **Snapshots:** "nothing written" counts all four tables over every workspace. It is taken right after the commit point, before X is flushed.
- **unchanged(T/Z/ZL):** compares every column through `select(table)` after `expire_all`.
- **Refusals** run with no savepoint, inside a plain `pytest.raises(HTTPException)`. Messages and status codes are exact (`==`).
- **GD-03** asserts `exc.value is E`. GD-04's `flaky` matches the card: keyword `template_id`, falling back to the second positional argument.
- **G-02** binds only the rollback spy. Its card checks only `rb`, so this is fine.
- **xfail reasons** each name the card's BUG ID, and every ID exists in `bugs.md`.

## Surviving mutants
| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 8 | L60:36 | `limit: int = 100` → `101` | case-missing | Spec signature `limit=100`, R1 "exactly these arguments". No card calls without `limit` on more than 100 rows (finding 1). Not equivalent: a direct caller would get 101 rows. | case designer |

## Hand variants
Applied in memory by the scratch plugin `hv_wots.py` (`C:\Users\User\AppData\Local\Temp\makorsh-pipeline\tplv\wotsvc\plug\`). Each variant was run with `-m "not xfail"`.

| Variant | Result (killing cards) |
|---|---|
| `generate_drafts`: `target_date + 1 day` / `- 1 day` | caught (GD-01, GD-02, GD-05, GD-06 / GD-01, GD-05, GD-06) |
| `generate_drafts`: `factory_section_id` dropped / `factory_id` dropped / the two swapped | caught (GD-06 / GD-07 / GD-06) |
| `generate_drafts`: `user_id=None` / no refresh / no commit | caught (GD-01 / GD-01, GD-05 / GD-01, GD-05, GD-06) |
| `generate_drafts`: `except HTTPException` only | **survived** (finding 2) |
| `list_templates`: `skip` dropped / `is_active` dropped / `is_active=True` forced / type dropped | caught (L-01 / L-01 / L-01, L-02 / L-01) |
| `list_templates`: `limit` dropped | **survived** (finding 1) |
| `create_template`: refresh before the commit | caught (C-01, C-05) |
| no re-read on create / update / restore / add_item / update_item | caught (C-01, C-05 / U-01 / S-01 / A-01 / I-01) |
| no rollback on create / update / delete / restore / add_item / update_item / remove_item | caught (C-02 / U-02 / D-03 / S-02 / A-02 / I-02 / R-02) |
| no commit (flush only) on each of the seven writes | caught (C-01, C-04, C-05 / U-01, U-05 / D-01, D-04 / S-01 / A-01 / I-01 / R-01, R-03) |
| `get_template` / `get_items` / `get_approvers` unscoped (`db.get` / no workspace filter) | caught (G-02, G-03 / N-02 / P-02) |
| reads that commit (`get_template`, `list_templates`, `get_items`, `get_approvers`) / `get_template` rolls back on 404 | caught (G-01 / L-03 / N-01 / P-01 / G-02) |

Not applicable at this layer:
- HR-15 rounding and month-end / leap-year recurrence. The service passes values through; the column rounding is checked by U-01 / I-01, and the date arithmetic is the manager's.
- Refusal order, which is the manager's.

## Traceability
- Cases 48 · tests 48 · every case ID appears in exactly one `# [claude] <ID>` comment and docstring.
- Unmatched: none.
- Marker mismatches: none. There are 9 `xfail BUG-…` cards and 9 `xfail(strict=True)` tests; each reason names the card's BUG ID (C-06 BUG-1228, C-07 / U-03 BUG-2335, C-08 BUG-2334, C-09 / U-06 BUG-2346, U-04 BUG-2340, GD-04 BUG-2344, GD-08 BUG-2345), and all exist in `docs/testing/bugs.md`.
- No `local-run.json`: every test was written by Claude.

## Commands run
All runs used `-o addopts=""` and a private `COVERAGE_FILE` under `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\tplv\wotsvc\`.

```
.venv/Scripts/python.exe -m pytest tests/unit/services/test_work_order_template_service.py -q -p no:cacheprovider -o addopts="" --cov=app.services.work_order_template_service --cov-branch --cov-report=term-missing
  app\services\work_order_template_service.py  91  0  2  0  100%
  39 passed, 9 xfailed, 15 warnings in 14.51s
.venv/Scripts/python.exe -m pytest tests/unit/services/test_work_order_template_service.py -q -p no:cacheprovider -o addopts="" --runxfail -rf
  9 failed, 39 passed in 7.38s
  (with --tb=line: C-06 :374, C-07 :398, C-09 :442, U-03 :533, U-06 :599 DID NOT RAISE HTTPException (Then 1);
   C-08 :426 '  Oil change ' == 'Oil change' (Then 2); U-04 :566 updated_by U1 != U2 (Then 2);
   GD-04 :1267 HTTPException 400 boom escapes the run (Then 1); GD-08 :1368 one draft returned (Then 1))
2 more plain runs: 39 passed, 9 xfailed in 7.21s · 39 passed, 9 xfailed in 7.54s
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/services/work_order_template_service.py tests/unit/services/test_work_order_template_service.py --json <scratch>/mut.json
  Mutants: 21 · killed 20 · timeout 0 · survived 1 · score 95%
  SURVIVED #8 L60:36 const: 100 -> 101
Hand variants: HV=<name> pytest … -p hv_wots -m "not xfail" --tb=no (PYTHONPATH = scratch plug dir)
```

## Future notes
Nothing new. The permission gap (any member may write templates and run "Plan day") and the Plan-day notification for skipped templates are already in the notes and in `docs/future/permissions.md`.

## Round 2 — 2026-11-09

> **Current verdict:** PASS — both round-1 findings are closed by cases revision 3; the tests for the new and changed cards are faithful; the round-1 survivor is now killed.

**New / changed tests read against their cards**
| Case | Change | Fidelity |
|---|---|---|
| WTSV-L-01 | Given 6 adds A0 (inactive, WT1, `T0`) | Built as carded; with `is_active=False, WT1` the matches are B, A, A0 (newest first), so `skip=1, limit=1` now cuts A0. Then 1 `== [A.id]` exact. Faithful. |
| WTSV-L-04 | new: 101 templates, no `limit` → newest 100 | 101 rows via `add_all` + one flush, `created_at = T0 + k min`; `newest` = reversed ids; Then 1 `len == 100`, Then 2 exact list `== newest[:100]`. Rows are built with the model directly rather than the `template` helper; only W1, WT1, name, creator and `created_at` matter to the list, so no finding. Faithful. |
| WTSV-GD-10 | new: as GD-03 with `RuntimeError` | `pytest.raises(RuntimeError)` (specific type), `exc.value is e`, session clean (new/dirty/deleted), X gone, T re-read `== D16`, nothing written. All five Then lines in order. Faithful. |

Traceability: 50 cards · 50 tests, one-to-one; markers unchanged (9 strict xfail, BUG IDs in `bugs.md`).

**Round-1 survivors re-checked**
| Round-1 item | Variant | Now |
|---|---|---|
| Finding 1 / mutant #8 | `list_templates` drops `limit` (passes 100) | KILLED by L-01 |
| Mutant #8 | `limit` default `100 -> 101` (mutate.py, line 60) | KILLED (by L-04) |
| Finding 2 | `generate_drafts` `except` narrowed to `HTTPException` | KILLED by GD-10 |
| (regression) | drop `skip`, drop `is_active`, drop type, force `is_active=True` | all KILLED (L-01; L-02) |

**Runs (3×, plus `--runxfail`)**
```
COVERAGE_FILE=…/tplv/wotsvc2/.cov
pytest tests/unit/services/test_work_order_template_service.py -q -p no:cacheprovider -o addopts="" --cov=app.services.work_order_template_service --cov-branch --cov-report=term-missing
  → 41 passed, 9 xfailed · 91 stmts, 0 miss, 2 branches → 100%
  run 2 → 41 passed, 9 xfailed · run 3 → 41 passed, 9 xfailed   (no flakes)
--runxfail -rf → 9 failed, 41 passed (the 9 strict BUG cards: C-06, C-07, C-08, C-09, U-03, U-04, U-06, GD-04, GD-08)
mutate.py app/services/work_order_template_service.py tests/unit/services/test_work_order_template_service.py --lines 60-60 --json C:/…/tplv/wotsvc2/mut.json
  [1/2] L60 const 0 -> 1 KILLED · [2/2] L60 const 100 -> 101 KILLED → 2/2, 100%
```
Combined with round 1 (20 of 21 killed, only #8 surviving), the module's mutation score is now 21/21 = 100%.

**Routed items:** none.
