# Verification — `app/dao/invoice_event.py`

> **Verdict:** PASS
> Tests: 27 passed · 2 xfail, 1 strict, 1 non-strict (reproduced ✅) · coverage 100% branch (14 statements, 0 branches)
> Mutation: 15 mutants · 14 killed · 1 survived → score 100% (after excluding 1 equivalent, 0 dead, 0 bug-path)
> Fidelity: **0 of 29 unfaithful** (29 / 29 right)
> Hand variants: 32 · 28 caught by a pass card · 4 others, none a rule gap
> Source commit: e48a092 · Cases revision: none; spec APPROVED

## Summary
- **The tests can be trusted.** Every test was read against its card, and my script agrees: 29 of 29 match. Every rule that holds today is caught by a pass card, including both sides of each id filter (GI-02 / GI-06, GI-03 / GI-04) and the order with an older row holding the higher id (GI-08).
- **Money:** amounts travel only as strings inside `metadata`; nothing is computed here.
- No finding for any stage.

Written by Claude (all 29 under `# [claude]`). Findings in local-written tests / local-written tests: 0 / 0. In others: 0 / 29. No `invoice_event.local-run.json` exists, so there is no `## Local-coder patterns` section.

## Findings
None.

## Surviving mutants
| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 15 | 37 | `label("performed_by_name")` → `label("")` | equivalent | The rows are unpacked by position (`for ev, name in rows`); the label is never read. | — |

**Guard.** My own driver re-ran each of the 15 mutants with no `-x`: every run reached all 27 pass tests, with no collection or setup error, and each status matched `mutate.py`. All 14 kills end in a plain `N failed`.

## Hand variants
`variants.py`, on my reference with `--runxfail`, on three plans (default; sequential scans off; index and bitmap scans off): the same variants caught by the same pass cards. Every edit was asserted to apply once, and every run reached all 29 tests.

| Group | Variants | Pass card | Cards that fail | Others |
|---|---|---|---|---|
| ce_r1 | 5 | 5 | IEV-CE-01 … CE-06 | — |
| ce_r2 | 2 | 2 | IEV-CE-03 | — |
| ce_r3 | 3 | 3 | IEV-CE-06, CE-07, CE-08, CE-12 | — |
| ce_r4 | 1 | 1 | IEV-CE-08 … CE-13 | — |
| ce_r5 | 1 | 1 | IEV-CE-14 | — |
| gi_r1 | 5 | 5 | IEV-GI-02 … GI-07 | — |
| gi_r2 | 2 | 1 | IEV-GI-11 | `gi_r2_cap_1000` |
| gi_r3 | 5 | 2 | IEV-GI-08, GI-11, GI-13 | `gi_r3_tail_asc`, `gi_r3_no_tail`, `gi_r3_desc_text` |
| gi_r4 | 2 | 2 | IEV-GI-01, GI-12, GI-13 … | — |
| gi_r5 | 1 | 1 | IEV-GI-14 | — |
| gi_r6 | 3 | 3 | IEV-GI-01 | — |
| gi_w | 2 | 2 | IEV-GI-15 | — |
| **Total** | **32** | **28** |  | **4** |

### Considered and not listed
| Variants | Why it is not a finding |
|---|---|
| `gi_r3_tail_asc`, `gi_r3_no_tail`, `gi_r3_desc_text` | **Bug path.** Wrong tie orders of BUG-638; each fails IEV-GI-09 (non-strict) and GI-10 (strict) on the reference, which is what those cards are for. |
| `gi_r2_cap_1000` | A cap above the card's own 201; `gi_r2_cap_200` is caught. |

## xfail tests against the reference
Reference: `ORDER BY created_at DESC, id DESC`, in memory. Nothing is written to `app/`.

With `--runxfail` on the reference: 29 passed, on all three plans. **The alarm works:** with the markers on, `1 failed, 27 passed, 1 xpassed`, GI-10 `XPASS(strict)`.

| Cards | Marker | Fails today on |
|---|---|---|
| IEV-GI-09 | non-strict | Then 2, in all 3 plans |
| IEV-GI-10 | strict | Then 3, in all 3 plans, as the card says |

## Reproduced claims
- **Result line of the notes holds:** `27 passed, 2 xfailed` in 4 of 4 default runs, the coverage run among them. No flaky test. IEV-CE-02 compares two real-clock stamps within 5 seconds; it passed in every run here.
- `--runxfail` on today's code: `2 failed, 27 passed` on all three plans.
- Coverage: 100%.
- **Mocks:** the `db.commit` spy of IEV-CE-14 only. No `try`, no broad `pytest.raises`.

## Traceability
cases 29 · tests 29 · unmatched: none · duplicates: none · marker mismatches: none. Card order equals file order. Each docstring equals its card's ID, title and Rules. `# Then N` numbers match the card. BUG-638 is in `docs/testing/bugs.md`. All sit under `# [claude] <ID>`. `ruff check` passes. `rebuild.py`: 0 reports here; selftest 1141 of 1141.

## Commands run
```
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/dao/invoice_event.py tests/unit/dao/test_invoice_event.py --timeout 300 --json <scratch>/res/mut_invoice_event.json
  15 mutants · 14 killed · 1 survived
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_invoice_event.py -q -p no:cacheprovider --cov=app.dao.invoice_event --cov-branch --cov-report=term-missing
  27 passed, 2 xfailed · TOTAL 14 0 0 0 100%
pytest (same file), 3 more default runs                       27 passed, 2 xfailed each
drive.py bases / muts / vars (3 plans); rx.py; rebuild.py
```
Scratch: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\acctv\`. Private `COVERAGE_FILE`. Only this report was written in the repo. No commit. Nothing was killed.
