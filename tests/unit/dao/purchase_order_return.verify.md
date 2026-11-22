# Verification — `app/dao/purchase_order_return.py`

> **Current verdict: PASS (round 2, 2026-11-10, cases revision 3): findings 1 and 2 are closed. See "Round 2" at the end.**
>
> **Verdict:** NEEDS WORK (two missing cards for the case designer; the tests themselves are faithful)
> Tests: 74 passed · 15 xfailed (reproduced ✅) · coverage 100% branch (27 statements, 0 branches)
> Mutation: mutate.py 24 mutants · 24 killed · 0 survived → score 100%. Hand variants 60 · 53 killed · 7 survived → score 96% (after excluding 1 equivalent, 0 dead, 4 bug-path)
> Source commit: e48a092 · Cases revision: 2

## Summary
The 89 tests are faithful to their cards: every Then line is asserted as written, no extra mocks, and each xfail fails on its card's line. mutate.py kills all 24 mutants. Hand variants on numbering scope, prefix case, "contains", padding, voided rows, every workspace filter (`<=` / `>=` / dropped, with W0 and W2 rows on both sides) and the invoice lookup are all killed.

Two real gaps survive. Both are cards the case designer must add, and the sales twin already has one of them:
- Hard-coding the year to 2026 survives. No pass card runs the clock in a year other than 2026 (the twin's SRT-CW-11).
- Adding a row lock to `get_open_by_purchase_order` survives. No PRT card checks "takes no lock". If one is added, it must not use the Conventions' `lock_part == ""`, which is vacuous for a plain `FOR UPDATE` (see the sales twin's verify, finding 1).

## Findings
| # | Kind | Case / line | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing | `create_with_user` R2 / R2a (pass half of BUG-2428), line 35 | Every passing `CW` card runs under clock(JUNE 2026, JUNE 2026) or the real 2026 clock (CW-02 does not check the number). So no pass card proves that the current year goes into the number. CW-08 / CW-09 do, but they are xfail and excluded. | Hand variant `pr-year-hard2026` (`year=2026`) SURVIVED. The twin SRT-CW-11 (both clocks 2031 → `SR-2031-001`) kills the same variant in the sales DAO. | **case designer**: add the twin of SRT-CW-11 (both clocks `datetime(2031, 1, 1, 5, 0)` → `PR-2031-001`) |
| 2 | case-missing | Overview "takes no lock" (all four list/lookup queries), line 74 | No PRT card checks that a read takes no lock (`lock_part` is defined but never asserted). | Hand variant `pr-op-lock` (`.with_for_update()` on `get_open_by_purchase_order`) SURVIVED | **case designer**: add a no-lock Then (`"FOR UPDATE" not in sql`) to OP-13 / PO-15 / IN-10 / RI-11, as the twin has. Do not use `lock_part == ""`. |

No fidelity findings.

## Surviving mutants
mutate.py: none.

Hand variants:
| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 1 | 35 | `datetime.now().year` → `utcnow().year` | bug-path | BUG-2428 fix; only CW-08 / CW-09 (xfail) separate it | — |
| 2 | 35 | `year=2026` | case-missing | Finding 1 | **case designer** |
| 3 | 41 | drop `status='pending'` | equivalent | The Python and database defaults are both `'pending'` | — |
| 4 | 60 | `order_by(created_at.desc(), id.asc())` | bug-path | Tie direction, BUG-2429 (PO-10, 11, 12 non-strict; PO-13 strict, all xfail) | — |
| 5 | 74 | open returns ordered `id DESC` | bug-path | BUG-2430 (OP-10, 11, 12 xfail) | — |
| 6 | 74 | open returns `.with_for_update()` | case-missing | Finding 2 | **case designer** |
| 7 | 102 | lines ordered `id DESC` | bug-path | BUG-2431 (RI-08, 09, 10 xfail) | — |

## Hand variants — what was tried (all KILLED unless listed above)
The same 60-variant set as the sales twin, with `PR` and `purchase_order_id`. Killed: global numbering (GN-01, 03, 04, 05, CW-07); workspace `<=` / `>=`; `ilike` (GN-17); `%prefix%` (GN-11); no dash; lower-case prefix; padding 4 / 2 / none; `+2`; pending-only and no-voided counts (GN-06); year `+1`; `'Pending'`; `paid=True`; `updated_by`; no flush; commit (CW-16); reason/notes swap; trim; return_type coercion; `ASC`, no order, `id DESC` only; voided dropped (PO-01); `limit(100)` (PO-16); scoping on all five queries; order id and `return_id` `<=` / `>=`; status `ilike` / `like` / `notin_` (OP-03, 04); invoice `<=` / `>=`, voided excluded (IN-03), `IS NOT NULL`, `.one_or_none()` (IN-09).

## Traceability
cases 89 · tests 89 · unmatched: none · duplicates: none · marker mismatches: none. 8 strict and 7 non-strict xfails match the Expect lines. The reasons name BUG-2426 … 2431, and all are in `bugs.md`. Every test sits under `# [claude] <ID>`; there is no local-written test.

`--runxfail` (own `whereplug.py`): CW-08 and CW-09 fail on Then 2, CW-10, 11 and 12 on Then 1 (`UniqueViolation`), PO-10, 11 and 12 on Then 2, PO-13 on Then 3, OP-10, 11 and 12 on Then 2, RI-08, 09 and 10 on Then 2. All match "Fails today on".

## Commands run
```
COVERAGE_FILE=…/omdv/B/.cov.purchase_order_return.{1,2,3} .venv/Scripts/python.exe -m pytest tests/unit/dao/test_purchase_order_return.py -q -p no:cacheprovider -o addopts="" --cov=app.dao.purchase_order_return --cov-branch --cov-report=term-missing
  runs 1–3: 74 passed, 15 xfailed · TOTAL 27 0 0 0 100%
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_purchase_order_return.py -q -p no:cacheprovider -o addopts="" --runxfail -rf
  15 failed, 74 passed
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/dao/purchase_order_return.py tests/unit/dao/test_purchase_order_return.py --json …/omdv/purchase_order_return.mut.json
  Mutants: 24 · killed 24 · timeout 0 · survived 0 · score 100%
.venv/Scripts/python.exe …/omdv/B/hand.py …/omdv/B/vars.json …/omdv/B/hand.res.txt 4
  pr-*: 60 variants · 53 killed · 7 survived
```
The results match the notes (74 / 15, 100%). There are no flaky tests across the three runs.

## Round 2 — 2026-11-10
Narrow re-check of cases revision 3 (patched, not regenerated). **Verdict: PASS.**

**Changed cards:** new PRT-CW-19 (both clocks 2031 → `PR-2031-001`); PRT-OP-13, PO-15 (Then 9), IN-10 (Then 8), RI-11 (Then 10) add `"FOR UPDATE" not in sql`.

**Fidelity:** All five match their cards line by line. RI-11 reads `r.id` and `W1.id` into locals before the recorder, after the carded `db.expire_all()`. That keeps the expire's refresh out of the recorded SQL and changes no check. **0 unfaithful.**

**Runs:** 75 passed, 15 xfailed ×3 · coverage 100% branch · `--runxfail` 15 failed, 75 passed. No flaky outcome. Runs (private `COVERAGE_FILE`, `omdv\R2\.cov`): `pytest <file> -q -p no:cacheprovider -o addopts=""` with `--cov=app.dao.<module> --cov-branch` once, plain twice, then `--runxfail` once.

**Variants:**
- Year hard-coded 2026: **killed by PRT-CW-19** (the round-1 survivor). It also makes the strict PRT-CW-08 XPASS (see the sales twin; no action).
- Lock per method (all five reads, OF and plain): all 10 killed (PO-15, OP-13, IN-10, RI-11, and the creates via `generate_return_number`). `get_open_by_purchase_order` used to survive.
- Clear-the-session not applied to OP-13, PO-15, IN-10, RI-11: **agreed, correct.** Their Thens check pending rows (`P in db.new`, `A in db.dirty`), which `expunge_all` would remove. They do not count SELECTs, so the convention does not apply. A hidden `db.get` of the parent order or return survives there, but no spec rule forbids it (same note as the sales twin).

Variants: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\omdv\PT\plug\r2var.py` (per-method `FOR UPDATE OF <table>` and plain `FOR UPDATE`; create's year hard-coded 2026, bypassing the tests' clock patch; a hidden `db.get` of the parent), driven by `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\omdv\PT\run_r2.py` on the pass tests (`-m "not xfail"`); results in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\omdv\PT\r2.txt`. `mutate.py` was not re-run: Revision 3 only adds assertions and one card, so no mutant killed in round 1 can survive now.

**Open items:** None.
