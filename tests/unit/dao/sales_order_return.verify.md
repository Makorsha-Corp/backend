# Verification — `app/dao/sales_order_return.py`

> **Current verdict: PASS (round 2, 2026-11-10, cases revision 3): finding 1 is closed. See "Round 2" at the end.**
>
> **Verdict:** NEEDS WORK (one card-convention fix for the case designer; the tests themselves are faithful)
> Tests: 74 passed · 12 xfailed (reproduced ✅) · coverage 100% branch (27 statements, 0 branches)
> Mutation: mutate.py 24 mutants · 24 killed · 0 survived → score 100%. Hand variants 60 · 55 killed · 5 survived → score 98% (after excluding 1 equivalent, 0 dead, 3 bug-path)
> Source commit: e48a092 · Cases revision: 2

## Summary
The tests can be trusted. All 86 cards are implemented one-to-one, in card order, with every Then line asserted as written; no extra mocks; every xfail fails on the line its card names. mutate.py kills everything. Hand variants for the brief's targets all die: per-workspace vs global numbering, `<=` / `>=` workspace filters with W0 and W2 rows on both sides, prefix case (`ilike`, lower-case prefix), "contains" instead of "starts with", missing dash, padding, a count that skips voided or completed rows, the year hard-coded or shifted, the void columns (a list or lookup that drops voided rows). One gap: the Conventions' "takes no lock" check, `lock_part == ""`, passes when the query has a plain `FOR UPDATE`, because Postgres puts `FOR UPDATE` at the very end and nothing follows it. Adding `.with_for_update()` to `get_open_by_sales_order` survives. This is a card-wording fix for the case designer.

## Findings
| # | Kind | Case / line | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing (convention) | SRT-GN-16, BS-14, OP-10, IV-09, RI-10 (Conventions "lock_part") | `lock_part` = the text after `FOR UPDATE`. A plain `FOR UPDATE` is the last thing in the statement, so `lock_part == ""` is true whether or not a lock is taken. The "takes no lock" Then lines prove nothing. | Hand variant `sr-op-lock` (`.with_for_update()` on `get_open_by_sales_order`) SURVIVED. Compiled SQL ends `WHERE sales_order_returns.status = %(status_1)s FOR UPDATE`. | **case designer**: change the convention (or these Then lines) to `"FOR UPDATE" not in sql` |

No fidelity findings: no missing, weakened or changed assertion, no wrong setup, no swallowed failure, no extra mock, no dishonest xfail.

## Surviving mutants
mutate.py: none.

Hand variants (run by my own script `hand.py` on a temp copy):
| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 1 | 32 | `datetime.now().year` → `utcnow().year` | bug-path | This is the BUG-2422 fix. Only CW-09 / CW-10 (xfail) tell the two apart. CW-11 (both clocks 2031) passes under both. | — |
| 2 | 38 | drop `status='pending'` from the constructor | equivalent | The model's Python default is `'pending'` too (and the database's), so the row is the same | — |
| 3 | 57 | `order_by(created_at.desc(), id.asc())` | bug-path | Tie direction. Only BS-09 / BS-10 (non-strict) and BS-11 (strict, `DESC` count) see it, and all three are xfail (BUG-2423) | — |
| 4 | 99 | `get_by_return` gets `ORDER BY id DESC` | bug-path | The order of the lines is BUG-2425; only RI-07 / RI-08 (xfail) see it | — |
| 5 | 71 | `get_open_by_sales_order` gets `.with_for_update()` | case-missing | Finding 1 | **case designer** |

`sr-op-order-desc` (open returns ordered `id DESC`, BUG-2424) was "killed" only by GN-14. That run had four hand variants running at once against the global number index. GN-14 is stable when run alone, so I count that kill as interference, and the variant is really bug-path.

## Hand variants — what was tried (all KILLED unless listed above)
Numbering: global count (W filter dropped), `workspace_id <= / >=`, `ilike`, `%prefix%`, no trailing dash, lower-case prefix, pad 4 / 2 / none, `count + 2`, count only pending, count without voided. Year: hard-coded 2026 (CW-11 kills), `+1`. Create: `'Pending'`, `paid=True`, `updated_by` written, no flush, an added commit (CW-18), reason/notes swapped, reason trimmed, return_type coerced. Lists: `created_at ASC`, no order, `id DESC` only, voided dropped from `get_by_sales_order`, `limit(100)` (BS-12). Scoping: `<=` / `>=` / dropped workspace filter on each of the five queries; order id `<=` / `>=` in both order lists; `return_id <=` / `>=`. Status: `ilike('pending')`, `like('%pending%')`, `notin_(completed, voided)`. Invoice: `<=`, `>=`, voided excluded (IV-02), `IS NOT NULL` added, `.one_or_none()` (IV-07).

## Traceability
cases 86 · tests 86 · unmatched: none · duplicates: none · marker mismatches: none. 8 strict and 4 non-strict xfails match the cards' Expect lines. Every reason names its BUG (2420, 2421, 2422, 2423, 2424, 2425), and all six are in `docs/testing/bugs.md`. Every test sits under `# [claude] <ID>`; there is no local-written test (`sales_order_return.local-run.json` does not exist).

`--runxfail` with my own plugin `whereplug.py` (failing test line → preceding `# Then N`): CW-09 and CW-10 fail on Then 2 (local year), CW-12, 13 and 14 on Then 1 (`UniqueViolation`), BS-09 and BS-10 on Then 2, BS-11 on Then 4, OP-07 and OP-08 on Then 2, RI-07 and RI-08 on Then 2. Each is exactly its card's "Fails today on".

## Commands run
```
COVERAGE_FILE=…/omdv/B/.cov.sales_order_return.{1,2,3} .venv/Scripts/python.exe -m pytest tests/unit/dao/test_sales_order_return.py -q -p no:cacheprovider -o addopts="" --cov=app.dao.sales_order_return --cov-branch --cov-report=term-missing
  run 1: 74 passed, 12 xfailed · TOTAL 27 0 0 0 100%
  run 2: 74 passed, 12 xfailed · 100%
  run 3: 74 passed, 12 xfailed · 100%
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_sales_order_return.py -q -p no:cacheprovider -o addopts="" --runxfail -rf
  12 failed, 74 passed
PYTHONPATH=…/omdv/B .venv/Scripts/python.exe -m pytest … --runxfail -p whereplug   (failure lines above)
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/dao/sales_order_return.py tests/unit/dao/test_sales_order_return.py --json …/omdv/sales_order_return.mut.json
  Mutants: 24 · killed 24 · timeout 0 · survived 0 · score 100%
.venv/Scripts/python.exe …/omdv/B/hand.py …/omdv/B/vars.json …/omdv/B/hand.res.txt 4
  sr-*: 60 variants · 55 killed · 5 survived
```
The results match the notes' Result line (74 / 12, 100%). There are no flaky tests across the three runs.

## Round 2 — 2026-11-10
Narrow re-check of cases revision 3 (patched, not regenerated). **Verdict: PASS.**

**Changed cards:** SRT-GN-16, BS-14, OP-10, IV-09, RI-10: the no-lock line is now `"FOR UPDATE" not in sql`.

**Fidelity:** All five match their cards line by line. **0 unfaithful.**

**Runs:** 74 passed, 12 xfailed ×3 · coverage 100% branch · `--runxfail` 12 failed, 74 passed. No flaky outcome. Runs (private `COVERAGE_FILE`, `omdv\R2\.cov`): `pytest <file> -q -p no:cacheprovider -o addopts=""` with `--cov=app.dao.<module> --cov-branch` once, plain twice, then `--runxfail` once.

**Variants:**
- Lock per method (all five reads, OF and plain): all 10 killed, each by its own card (GN-16 via the creates, BS-14, OP-10, IV-09, RI-10).
- Year hard-coded 2026: killed by SRT-CW-11. It also makes the strict SRT-CW-09 XPASS, which a full run reports as a failure. The coordinator's point is confirmed, and no action is needed: CW-11 is the deliberate catch, and CW-09's XPASS is an accident that goes away with BUG-2422.
- Not a finding: a hidden `db.get(SalesOrder | AccountInvoice | SalesOrderReturn, …)` before each read survives, because the parent is in the identity map. No rule of the spec forbids reading the parent, and the result is the same. GN-16, BS-14, OP-10, IV-09 and RI-10 do count SELECTs and read no pending rows, so the new convention "Clear the session before a one-query check" applies to them literally, and `db.expunge_all()` would be harmless there. Apply it if the case designer wants these one-SELECT lines to mean what they say. Not blocking.

Variants: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\omdv\PT\plug\r2var.py` (per-method `FOR UPDATE OF <table>` and plain `FOR UPDATE`; create's year hard-coded 2026, bypassing the tests' clock patch; a hidden `db.get` of the parent), driven by `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\omdv\PT\run_r2.py` on the pass tests (`-m "not xfail"`); results in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\omdv\PT\r2.txt`. `mutate.py` was not re-run: Revision 3 only adds assertions and one card, so no mutant killed in round 1 can survive now.

**Open items:** None.
