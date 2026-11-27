# Verification — `app/services/item_service.py`

> **Current verdict (round 2, 2026-11-04): PASS.** All three round-1 findings are fixed; see "Round 2" at the end. The round-1 header below is kept as it was.

> **Verdict:** NEEDS WORK (no unfaithful test; three behaviours have no card that can see them. The fixes go to the designer and the describer)
> Tests: 35 passed · 35 xfail, 33 strict + 2 non-strict (reproduced ✅) · coverage 94% branch (71 statements, 8 branches; missed 115, 255, 264–265; partial 254→255), all dead code (confirmed)
> Mutation: 52 mutants · 42 killed · 10 survived → score 93% (42 / 45, after excluding 0 equivalent, 7 dead, 0 bug-path)
> Fidelity: **0 of 70 unfaithful** (read by eye, card against test)
> Hand variants: 23 · 20 caught by a pass card · 3 not caught (all routed)
> Source commit: e48a092 · Cases revision: 1; spec APPROVED

## Summary
- **The tests are faithful.** All 70 match their cards: item / tag / link / stock rows with the Conventions defaults, the "Extra" row after the commit point, the manager patches of the translation cards, the D-02 spy, and every Then line with exact values.
- **The coverage gaps are dead code, as claimed.** Line 115 is `get_items` → `search_items`, which nothing calls (`grep item_service.get_items` finds no caller; spec "Not specified"). Lines 254→255 and 255 are the `if not item` after `ItemManager.update_item`, which always returns its loaded row or raises `ValueError`. Lines 264–265 are `except NotFoundError` in `update_item`: no `NotFoundError` is raised anywhere in `item_manager` or the item DAOs, so line 255 is its only source. All of these are spec D3 / Not specified.
- **What is missing:** the page's `updated_at` / `updated_by` fields are checked only on a row where both are `NULL`, the schema's default (designer). The generic rollback of `delete_item` has no pass card that can see it (designer). The default `limit=5` of `get_similar_items` has no rule (describer).

No `item_service.local-run.json`; all 70 tests are under `# [claude]`. Findings in local-written tests / local-written tests: 0 / 0. In others: 0 / 70.

## Findings
| # | Kind | Case / line | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing | ITS-P-10 (`get_items_page` R3), source lines 170, 172 | P-10's I1 has `updated_at` and `updated_by` `NULL`, the same as the response schema's default. Dropping either field from the row dict, or renaming its key, is invisible. Give I1 `updated_by U2.id` and an explicit `updated_at` stamp in the Given, and assert both values. | mutants #38, #40 survived; hand variants `page_updated_at_dropped`, `page_updated_by_dropped` not caught | case designer |
| 2 | case-missing | `delete_item` R6 / TC3 (generic `except Exception` rollback, line 310) | No pass card shows the rollback on the generic error path of delete. D-09's patched manager writes nothing, and D-10's checks follow a test-level `db.rollback()` (`committed:`). TC3 on delete is carded only through the 404 pre-check (D-02). Suggested: give D-09 or D-10 an uncommitted "Extra" row after the commit point and a `count:` = 0 line before any test rollback, as D-02 does. | hand variant `delete_tc3_norollback`: 35 passed | case designer |
| 3 | spec-gap | `get_similar_items` signature `limit=5` (line 203) | No rule says what the default `limit` is. `GET /items/similar/` always passes `limit` (`Query(5)`), so the default is reached only by direct callers. Mutant `5 → 6` survives. Either write the default as a rule (the designer then adds a card with 6 matches and no `limit`) or list it under Not specified. | mutant #14 survived | describer (fill-gaps) |

## Surviving mutants
| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 3 | 115 | return → `None` | dead | `get_items` is dead (spec Not specified, on the dead-code checklist) | — |
| 10 | 99 | `skip` default 0 → 1 | dead | the `get_items` signature | — |
| 11 | 100 | `limit` default 100 → 101 | dead | the `get_items` signature | — |
| 14 | 203 | `limit` default 5 → 6 | spec-gap | Finding 3 | describer |
| 20 | 255 | raise → pass | dead | `if not item` after `update_item` never fires (D3) | — |
| 21 | 265 | raise → pass | dead | `except NotFoundError` in `update_item`, reachable only from line 255 (D3) | — |
| 38 | 170 | `'updated_at'` → `''` | case-missing | Finding 1 | case designer |
| 40 | 172 | `'updated_by'` → `''` | case-missing | Finding 1 | case designer |
| 43 | 255 | message text → `''` | dead | line 255 (D3) | — |
| 44 | 255 | message text → `''` | dead | line 255 (D3) | — |

## Hand variants
Made with `hv.py`. Each is one text edit to today's source, run on the pass cards without `-x`.

| Group | Variants | Caught | Cards that fail |
|---|---|---|---|
| create TC1 / TC2 / TC3 (flush, refresh dropped / moved, rollback dropped, commit on error) | 5 | 5 | C-01, C-02, C-03, C-04, C-11 |
| update TC1 / TC2 / TC3 | 3 | 3 | U-01; U-02 |
| delete: commit → flush; pre-check rollback dropped | 2 | 2 | D-01; D-02 |
| delete: generic rollback dropped | 1 | 0 | — (Finding 2) |
| page: total from the page, `skip` echo, `has_more` `<=`, count `unit` dropped, tag `icon`, `description` | 6 | 6 | P-01, P-02, P-03, P-05 … P-10 |
| page: `updated_at`, `updated_by` dropped | 2 | 0 | — (Finding 1) |
| similar: query trimmed, `exclude_item_id` dropped | 2 | 2 | S-01; S-03 |
| TC6: get commits, units roll back | 2 | 2 | G-07; N-03 |

## xfail tests: fails-today check
`--runxfail` with `vfailmap.py`: 35 failed, 35 passed. Each card fails on its "Fails today on" line:
- Then 1, a `ValueError` escapes the wrap: C-05, C-06, C-07, U-03, U-04, U-05, D-04, D-05, D-06, D-07.
- Then 1 `DID NOT RAISE`: C-08, C-09, C-10, G-04, U-06, D-08.
- In the When: G-05 (`TypeError`), P-12 (`ValueError` on `²`). G-06: the `TypeError` inside Then 1's wrap.
- C-12 Then 2 (untrimmed); P-11 Then 2 `'physical'`; P-13 Then 1 (both items); P-14, P-15 Then 1 (one item); P-16 Then 2 `['Zulu', 'Mike', 'alpha']`; N-02 Then 1; S-05 Then 1 `0 == 1`; U-08 Then 2; U-09 Then 3 (a new link id); U-10 Then 2; U-11 Then 2; U-12 Then 3; D-11 Then 2 `9 == 8`.
- Non-strict P-17 and S-06: Then 2, xfailed in every run.

## Reproduced claims
- The notes' Result line holds: `35 passed, 35 xfailed` in the coverage run and in 3 more plain runs. No flaky test. Coverage `71 4 8 1 94%`, missing `115, 255, 264-265`, as the notes say.
- Patches are only those that Conventions name. `ruff check` passes. `git diff -- app/services` is empty.

## Traceability
cases 70 · tests 70 · unmatched: none · duplicates: none · marker mismatches: none (`trace.py`). Every BUG ID is in `docs/testing/bugs.md`. Card order equals file order.

## Commands run
```
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/services/item_service.py tests/unit/services/test_item_service.py --json <scratch>/mut_item_service.json
  Mutants: 52 · killed 42 · timeout 0 · survived 10 · score 81% (raw)
.venv/Scripts/python.exe -m pytest tests/unit/services/test_item_service.py -q -p no:cacheprovider --cov=app.services.item_service --cov-branch --cov-report=term-missing
  35 passed, 35 xfailed · app\services\item_service.py 71 4 8 1 94% 115, 255, 264-265
.venv/Scripts/python.exe -m pytest tests/unit/services/test_item_service.py -q -p no:cacheprovider --runxfail -rf     35 failed, 35 passed
pytest plain × 3                                                                                               35 passed, 35 xfailed each
vfailmap.py; hv.py item_service (23 variants); trace.py; ruff check; grep for callers / NotFoundError sources    as above
```
Scratch: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\svc2v\` (private `COVERAGE_FILE`). Only this report was written in the repo. No commit. No process was killed.

## Round 2 — 2026-11-04
**Verdict: PASS.** Cases revision 2, spec R1a. 36 passed · 35 xfail (33 strict + 2 non-strict) · coverage 94% branch; the misses are the same dead lines: 115, 255, 264–265.

- **The changed and new tests are faithful to their cards.**
  - ITS-P-10: I1 now has `updated_by` U2 and `updated_at` `datetime(2026, 2, 3, 4, 5, 6)`; Then 5 and Then 7 assert both, comparing the stamp as wall time, as the card says. The `noqa: DTZ001` is for the card's naive stamp.
  - ITS-D-09: the "Extra" row is added after the commit point, and Then 3 counts it as 0 right after the call, before any test-level rollback; Then 5 checks the session is usable.
  - ITS-S-08 (new): 6 items with `name_normalized "bolt"` and no `limit`; Then 1–3 (5 matches, 5 distinct, all from the six) are as the card says.
- **The routed variants are now caught** (`hv2.py`, pass cards, without `-x`):

| Variant | Round 1 | Round 2 |
|---|---|---|
| `get_similar_items` default `limit` 5 → 6 | 35 passed | S-08 fails |
| page `updated_at` dropped | 35 passed | P-10 fails |
| page `updated_by` dropped | 35 passed | P-10 fails |
| `delete_item` generic-path rollback removed | 35 passed | D-09 fails |

- **Mutation, only on the lines of the round-1 survivors** (99–100, 115, 170–172, 203, 255, 265):
  - Killed: `'updated_at'` / `'updated_by'` → `''` (both on line 170–172, by P-10) and `5 → 6` (by S-08).
  - Still surviving: lines 99, 100, 115, 255 (×3) and 265, all dead as in round 1.
  - Module score: 45 / 45 non-dead = **100%**.
- **Runs:** coverage run plus 3 plain runs each give `36 passed, 35 xfailed`; `--runxfail` gives `35 failed, 36 passed`, and every xfail test still fails on its card's line. No flaky test. `trace.py`: 71 cards, 71 tests, no marker mismatch. `ruff check` passes. `app/services` is unchanged.
- **Findings:** none.
