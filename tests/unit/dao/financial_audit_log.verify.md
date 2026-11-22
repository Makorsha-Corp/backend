# Verification — `app/dao/financial_audit_log.py`

> **Verdict:** PASS
> Tests: 99 passed · 16 xfail, 9 strict, 7 non-strict (reproduced ✅) · coverage 100% branch (30 statements, 0 branches)
> Mutation: 33 mutants · 33 killed · 0 survived → score 100% (after excluding 0 equivalent, 0 dead, 0 bug-path)
> Fidelity: **0 of 115 unfaithful** (115 / 115 right)
> Hand variants: 16 · 16 caught (14 by a pass card, 2 only by the strict BUG-2370 / BUG-2371 cards, as they should be) · no rule gap
> Source commit: e48a092 · Cases revision: 2; spec APPROVED (revised 2026-11-07)

## Summary
- **The tests can be trusted.** I read all 115 tests against their cards (side by side, every Given, When and numbered Then line). Then-line counts and `# Then N` comments match on every card. Nothing is patched, and there is no `try` / `except` or broad `raises`.
- Every mutant is killed. Every hand variant is caught: wrong sort direction, a dropped workspace filter, half-typed related matches, `AND` in place of `OR`, `ILIKE`, exclusive bounds, a wrong time-zone "fix" (dropping the zone without converting), and accepting `skip=` on `get_recent_logs`.
- **The 7 non-strict tie cards are allowed by their cards.** BE-16, BE-17, RL-17, AT-10, BU-06, DR-13 and RC-09 each say `Expect: xfail BUG-2370 (non-strict)`, and the spec's notes ask for non-strict on the tie cases because "today's order rests on physical row order" (as BUG-1210). Their outcome changed between my runs (0 or 1 XPASS out of 7), which is what the cards expect, so it is not flakiness. The 6 strict SQL-recorder cards (Then 4, `".id" in order_part`) carry the proof.
- **Paging tie-break check.** An `id ASC` tie-break passes every pass card. It is caught only by the strict recorder cards (Then 6, `DESC` count == 2) and by the non-strict tie cards under `--runxfail`. That is right: the direction is BUG-2370's intended behaviour, and the cards checking it are xfail until the fix.

Written by Claude (all 115 under `# [claude]`). Findings in local-written tests / local-written tests: 0 / 0. In others: 0 / 115. There is no `financial_audit_log.local-run.json`, so this report has no `## Local-coder patterns` section.

## Findings
None.

**Notes (no verdict impact):**
| # | Where | What | Fix by |
|---|---|---|---|
| n1 | `financial_audit_log.cases.md`, Reviewer summary | It says "BUG-2370 12". The cards hold 13: 6 tie cards, BE-17, and 6 SQL recorders. The Counts line (16 bug cards) is right. | case designer (wording only) |
| n2 | `financial_audit_log.notes.md` | It says "3 plain runs: all 7 XPASSED". My runs gave 1, 0 and 1 XPASS (and 7 of 7 failing under `--runxfail`). The tie order today depends on the heap, so either result is possible. The sentence should say the outcome varies. | executor (wording only) |

## Surviving mutants
None. All 33 are killed (cmp 33: the workspace, type, id, action, user and related-half equalities, and both date-range bounds).

## Hand variants
`tplv\fadao\plug\fal_variants.py` patches all six readers in-process (app/ is untouched), chosen with `FAL_VARIANT`. Each variant was run with markers on and again with `--runxfail`.

| Variant | Markers on | `--runxfail` | Caught by |
|---|---|---|---|
| `fixed` (performed_at desc, id desc; aware → naive UTC) | 8 failed (strict XPASS) · 99 passed · 7 xpassed | 1 failed (N-02: the model default, which the plugin does not fix) | red run that a fix must produce ✅ |
| `id_asc` tie-break | 99 passed · 16 xfailed | 16 failed | strict recorder cards only (bug path) |
| `id_first` (id desc, then performed_at) | 18 failed | 27 failed | pass cards |
| `asc` (oldest first) | 36 failed | 52 failed | pass cards |
| `id_only` | 18 failed | 27 failed | pass cards |
| `no_order` | 33 failed | 49 failed | pass cards |
| `no_ws` (workspace filter dropped) | 13 failed | 28 failed | isolation cards |
| `rel_no_type` (related half without type) | 3 failed | 19 failed | RL-04, RL-07 |
| `own_no_type` | 2 failed | 14 failed | RL-04 |
| `and_halves` (`AND` in place of `OR`) | 11 failed | 27 failed | RL cards |
| `ilike` on action | 2 failed | 18 failed | AT-02 |
| `tz_strip` (wrong BUG-2371 fix: zone dropped) | 2 failed | 16 failed | DR-08 (pass) + DR-09 XPASS |
| `tz_fix` (right BUG-2371 fix) | 2 failed (DR-09, DR-10 strict XPASS) · 99 passed | 13 failed (only the BUG-2370 ones) | correct fix goes red as designed ✅ |
| `excl_start` | 3 failed | 18 failed | DR-01, DR-03 |
| `excl_end` | 5 failed | 21 failed | DR-01, DR-03, DR-16 |
| `recent_skip_ok` | 1 failed | 17 failed | RC-12 |

Filter boundaries are covered on both sides: entity id 9 and 11 (BE-02), user U1 and U3 (BU-01), workspaces W0 and W2 (every isolation card), and one microsecond outside each date bound (DR-02).

## xfail honesty (`--runxfail`, `--tb=line`, failing line mapped to its `# Then N`)
| Cards | Fails on | Card says |
|---|---|---|
| BE-18, RL-18, AT-11, BU-07, DR-14, RC-10 | Then 4 `".id" in order_part` | Then 4 ✅ |
| BE-16, BE-17, RL-17, AT-10, BU-06, DR-13, RC-09 | Then 2 (id order) | Then 2 ✅ |
| DR-09, DR-10 | Then 1 `ids(result) == [a.id]` | Then 1 ✅ |
| N-02 | Then 2 `before <= performed_at <= after` | Then 2 ✅ |

## Traceability
115 cases · 115 tests · each ID appears exactly once in a docstring · no test lacks an ID · marker mismatches: none. The strictness matches the Expect line on all 16 xfail cards. The reasons name the bug through the constants `R2370`, `R2371` and `R2372`, and each ID exists in `docs/testing/bugs.md`.

## Commands run
```
COVERAGE_FILE=tplv/fadao/.cov .venv/Scripts/python.exe -m pytest tests/unit/dao/test_financial_audit_log.py -q -p no:cacheprovider -o addopts="" --cov=app.dao.financial_audit_log --cov-branch --cov-report=term-missing
  → 99 passed, 16 xfailed · app\dao\financial_audit_log.py 30 0 0 0 100%
.venv/Scripts/python.exe -m pytest … --runxfail -rf            → 16 failed, 99 passed (the 16 xfail cards, each on its card's Then line)
.venv/Scripts/python.exe -m pytest … -rxX   (twice more)       → 99 passed, 15 xfailed, 1 xpassed · 99 passed, 16 xfailed
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/dao/financial_audit_log.py tests/unit/dao/test_financial_audit_log.py --json tplv/fadao/mut.json
  → Mutants: 33 · killed 33 · timeout 0 · survived 0 · score 100%
PYTHONPATH=tplv/fadao/plug FAL_VARIANT=<v> .venv/Scripts/python.exe -m pytest … -p fal_variants [--runxfail]   (16 variants + base, table above)
```
