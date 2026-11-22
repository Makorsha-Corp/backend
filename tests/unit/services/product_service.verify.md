# Verification — `app/services/product_service.py`

> **Verdict:** PASS
> Tests: 58 passed · 34 xfailed (reproduced ✅; 33 strict, 1 non-strict LG-15) · coverage 100% branch (47 statements, 0 missed)
> Mutation: 13 mutants · 13 killed · 0 survived → score 100% (after excluding 0 equivalent, 0 dead, 0 bug-path). Hand mutants: 47 · 47 killed. Reference probes (BUG-2793, BUG-2772): 17 · 17 as expected.
> Source commit: e48a092 (working tree clean for `app/services/product_service.py`, `app/managers/product_manager.py`, `app/dao/product_ledger.py`) · Cases revision: 2

## Summary
These tests can be trusted. All 92 cards map one-to-one to 92 tests. Every marker matches its card's Expect line, and every Then line is asserted in card order with the card's exact values. The runs reproduce the notes, with no flakiness over 3 runs. Under `--runxfail` all 34 xfail tests fail on the line their card names. `mutate.py` produced only 13 mutants on this thin pass-through file, so I added 47 hand mutants for the transaction contract, error mapping, argument pass-through and HR-16. All 47 were killed.

The two bug wrappers that do not exist yet were probed against a stand-in implementation of my own. For `make_sellable` (BUG-2793), the MS cards pass against a correct version, and each broken lock clause, extra commit, missing rollback and wrong return is caught. For `include_deleted` (BUG-2772), each wrong variant is caught by exactly one of G-04 / G-05 / G-06. Nothing needs to change.

## Findings
None.

Checked and not a finding:
- **PRDS-D-05** patches `product_service.manager.delete_product`. The spec's Notes for BUG-2774 and the card both prescribe this patch (`Author: claude`), so it is not an extra mock.
- **G-05, MS-01, MS-02 and MS-10** fail at the When line, not inside a Then block. Their cards say exactly that: "Then 1 (the call raises TypeError / AttributeError)", where Then 1 is a `returns:` or `loaded:` line. The notes record the same; it is not a dishonest xfail.
- **C-05, C-07 and U-07** accept `(IntegrityError, HTTPException)`. That is the card's `raises: IntegrityError or HTTPException`, not a swallowed failure.
- **LG-15** is non-strict, as its card says (`Author: claude`). It xfailed in all 3 runs. LG-16 is the strict SQL check for BUG-640.

## Surviving mutants
None (`mutate.py`: 13 / 13 killed).

### Hand mutants (scratch `hand_mut.py`, temp copy of the backend, `-m "not xfail"`)
All 47 were killed. Tests that killed each group:

| Variant | Mutants | Killed by |
|---|---|---|
| TC1 no commit | H01 create, H05 update, H09 delete | C-01/02/10/12/14/17/18 · U-01/02/06/10/13/15/17 · D-01/06 |
| TC2 no refresh | H02, H06, H10 | C-01/C-18 · U-01 · D-01 (`loaded`) |
| TC3 missing rollback | H03, H07, H11 | C-03/04/05/07 · U-03/04/07 · D-02/03/05 |
| TC3 commit before the error (commit in `except`) | H04, H08, H12 | same as above (`cm == 0`, `x_gone`) |
| Partial write (commit before the manager call; second commit) | H13, H15, H14 | C-01…C-12 · D-01/02/03/05 · U-01/U-10 |
| TC6 read that commits / rolls back | H16–H20, H43 (rollback on a raising read) | G-10/G-11 · L-08 · LG-20/LG-21 · G-11 |
| Error mapping (500 wrap; a copy, not the same object; translated to HTTPException) | H39–H42 | C-03/04/17/18 · U-03/04/17 · D-02/03/05/06 (D-05 `is E`) |
| Pass-through arguments (factory, flag, dates, type, paging dropped, hardcoded or swapped; `user_id` dropped) | H21–H29, H36–H38, H44, H45 | L-02…L-07 · LG-02…LG-21 · C-01 · U-01/02/13 · D-01 |
| HR-16 W0 / W2 (workspace −1 / +1; get without a workspace check) | H30–H35, H46, H47 | L-01…L-08 · LG-01…LG-13 (LG-03 W2, LG-04 W0) · G-01/02/03 |

### Reference probes (`--runxfail`, stand-in methods appended to a temp copy)
- **`make_sellable` (BUG-2793).** The reference takes `with_for_update(of=Product)` on both bucket reads, commits once, refreshes, and rolls back on error. All 11 MS cards pass against it. Each broken variant fails at least one card:
  - **R01** bare `FOR UPDATE`: MS-01/02/09/10/11 (Postgres refuses it on the joined `items` outer join).
  - **R02** target read unlocked, **R03** `SKIP LOCKED`, **R04** `NOWAIT`: MS-10.
  - **R05** commit in the middle of the move: MS-01/10.
  - **R06** no commit: MS-01/02/09/10/11.
  - **R07** missing rollback, **R08** commit on error: MS-03…08.
  - **R09** no refresh: MS-01/11.
  - **R10** returns the source: MS-01/02/10.
  - **R11** source not reduced: MS-01/02/11.
- **`include_deleted` (BUG-2772).** The reference passes G-01…06 and G-09…11. Each wrong variant fails exactly one card:
  - **G01** flag ignored: G-05.
  - **G02** flag always on: G-04.
  - **G03** default `True`: G-04.
  - **G04** workspace filter dropped when the flag is set: G-06.

## Traceability
- 92 cases, 92 tests; every case ID appears exactly once. Unmatched: none. Marker mismatches: none.
- 58 `pass` with no marker. 33 `xfail(strict=True)` and 1 `strict=False` (LG-15), each reason naming its BUG ID.
- Every BUG ID used is in `docs/testing/bugs.md`: 640, 992, 1011, 1336, 2771–2781, 2793.
- Fails on the card's Then line: 30 of 34 inside the named Then block, plus 4 at the When as their cards state (G-05, MS-01, MS-02, MS-10). Failure types:
  - 11 × AttributeError (`make_sellable`)
  - 5 × DID NOT RAISE HTTPException
  - 4 × DID NOT RAISE ValidationError
  - 2 × TypeError (`include_deleted`)
  - 3 × IntegrityError (23505 ×2, FK ×1)
  - 9 assertion failures on the named Then line

## Commands run
Scratch: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\svc2v\product\`, with a private `COVERAGE_FILE` there for every run.
```
.venv/Scripts/python.exe -m pytest tests/unit/services/test_product_service.py -q -p no:cacheprovider -o addopts="" --cov=app.services.product_service --cov-branch --cov-report=term-missing
  → 58 passed, 34 xfailed · app\services\product_service.py 47 stmts 0 miss 100%
.venv/Scripts/python.exe -m pytest tests/unit/services/test_product_service.py -q -p no:cacheprovider -o addopts=""   (×2 more)
  → 58 passed, 34 xfailed · 58 passed, 34 xfailed
.venv/Scripts/python.exe -m pytest tests/unit/services/test_product_service.py -q -p no:cacheprovider -o addopts="" --runxfail -rf --tb=short
  → 34 failed, 58 passed
.venv/Scripts/python.exe -m ruff check tests/unit/services/test_product_service.py → All checks passed!
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/services/product_service.py tests/unit/services/test_product_service.py --json <scratch>/mut.json
  → Mutants: 13 · killed 13 · timeout 0 · survived 0 · score 100%
<scratch>/hand/hand_mut.py hand   → 47 / 47 killed
<scratch>/hand/hand_mut.py probe  → 17 / 17 as expected (R00, G00 pass; 15 broken variants fail)
<scratch>/trace.py                → traceability clean; Then-line map as above
```
