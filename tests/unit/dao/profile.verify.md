# Verification — `app/dao/profile.py`

> **Current verdict (round 2, 2026-11-04):** PASS — 33 passed · 13 xfailed · 100% branch · mutation 8/8 · both round-1 variants now caught
> **Round 1 verdict:** NEEDS WORK
> Tests: 29 passed · 13 xfailed (reproduced ✅, all strict, each on its card's line) · coverage 100% branch
> Mutation: 8 mutants · 8 killed · 0 survived → score 100% (after excluding 0 equivalent, 0 dead, 0 bug-path)
> Hand variants (BUG-1860 fix shapes, in memory): 10 run · 8 caught · 2 survive (see below)
> Source commit: e48a092 · Cases revision: 1

## Summary
The tests are faithful to the cases: all 42 cards are implemented one to one, with exact assertions, real
bcrypt, real re-reads and only the card's `wraps=` spy. The runs match the notes, nothing is flaky, and
every mutant is killed. The tool makes only 8 mutants here, so I also tried hand-written fixes of BUG-1860
(OQ-1). The suite catches substring, prefix, plain `ILIKE`, one-sided lower or trim, and a missing trim on
either side. Two fixes that are too loose still pass every card: `%` left as a wildcard, and inner spaces
stripped. Each needs one more card (case designer). No test or spec change is needed.

## Findings
| # | Kind | Case / line | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing (security, OQ-1) | `get_by_email` R1 / R1a; next to PRF-GE-09 | No card checks that `%` in the argument is a literal character. GE-09 catches only an unescaped `ILIKE`. A fix that escapes `_` but leaves `%` live (`trim(email) ILIKE :key ESCAPE '\'` with only `_` escaped) passes all 42 cards. With such a fix, `%@example.com` would return the first account of a domain. That gives login a password-spraying lever (one attempt tests a password against an arbitrary account), and makes reset, register and invitation lookups match accounts they should not. | Variant `ilike_pct`: 22 passed, only the unrelated AU-04 and AU-09 failed (same as the reference fix) | case designer: add a boundary card, e.g. `get_by_email(email=f"%.{TAG}@example.com")` and `f"Ann.Lee.{TAG}@%"` → `None` with MIXED stored (pass today, stays green after the fix) |
| 2 | case-missing | `get_by_email` R1a ("inner text still has to match") | No card has an inner space. A fix that removes every space (`replace(email,' ','')` on both sides) instead of trimming passes all cards. The spec allows only outer spaces. | Variant `inner_space`: 22 passed (same as the reference fix) | case designer: a card with the stored MIXED and argument `f"Ann.Lee .{TAG}@example.com"` (or `f"Ann. Lee.{TAG}@example.com"`) → `None` |

No fidelity findings. Checked against every card: Then lines in order with `==` / `is` checks. Given rows
use `make_profile` with neighbours at a lower and a higher id. CR-03 uses a savepoint plus a `commit` spy.
GE-12 and AU-11 use a statement recorder. The one mock is AU-04's `wraps=` spy, at the card's target. There
is no `try/except`.

## Surviving mutants
None (8/8 killed).

### Hand variants of the BUG-1860 fix (scratch plugin `prf_variants.py`, run with `--runxfail -k "ge_ or au_"`)
AU-04 (BUG-038) and AU-09 (BUG-500) fail under every variant because those bugs are not part of the
variant. They are left out below.
| Variant | Caught by |
|---|---|
| reference `lower(trim())` on both sides | — (all BUG-1860 cards pass) |
| substring (`contains`) | GE-08, GE-09, GE-11 |
| prefix (`startswith`) | GE-08, GE-09, GE-11 |
| plain `ILIKE` (wildcards live) | GE-09 |
| `ILIKE`, `_` escaped, `%` live | **survives** (finding 1) |
| inner spaces stripped | **survives** (finding 2) |
| argument lowered only, stored side exact | GE-01, GE-03, GE-04, GE-05, GE-12, GE-13, AU-01, AU-02, AU-11 |
| stored side lowered only, argument as typed | GE-01, GE-04, GE-05, GE-06, GE-12, AU-01, AU-02, AU-11 |
| lower without trim | GE-05, GE-13 |
| trim on the argument only | GE-13 |

## Traceability
cases 42 · tests 42 · unmatched: none · marker mismatches: none. 13 strict xfails: BUG-1860 ×6, BUG-1861,
BUG-1862, BUG-1406 ×3, BUG-038, BUG-500. Each reason names its BUG ID, and all of them exist in `bugs.md`.
The 29 pass cards have no marker.

## Commands run
```
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_profile.py -q -p no:cacheprovider --cov=app.dao.profile --cov-branch --cov-report=term-missing
  app\dao\profile.py  22 stmts  0 miss  4 branch  0 brpart  100%
  29 passed, 13 xfailed   (repeat runs: 29 passed, 13 xfailed ×2 — stable)

.venv/Scripts/python.exe -m pytest tests/unit/dao/test_profile.py -q -p no:cacheprovider --runxfail -rf --tb=line
  13 failed, 29 passed. Each fails on its card's "Fails today on" line:
  GE-03/04/05/06/13 and AU-02 Then 1 `assert None is not None`; CR-04 Then 2 `'  Ann ' == 'Ann'`;
  CR-05/06 Then 1 DID NOT RAISE ValidationError; CR-15 Then 2 `'Ann.Lee.<tag>@example.com' == 'ann.lee.<tag>@example.com'`;
  CR-17 Then 1 DID NOT RAISE IntegrityError; AU-04 Then 2 `0 == 1`; AU-09 Then 1 ValueError (72-byte limit)

.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/dao/profile.py tests/unit/dao/test_profile.py --json <scratch>/profile_mut.json
  Mutants: 8 · killed 8 · timeout 0 · survived 0 · score 100%

PYTHONPATH=<scratch> PRF_VARIANT=<v> .venv/Scripts/python.exe -m pytest tests/unit/dao/test_profile.py -q -p no:cacheprovider -p prf_variants --runxfail -k "ge_ or au_"
  (scratch = C:\Users\User\AppData\Local\Temp\makorsh-pipeline\oqv; results in the table above)
```

## Round 2 — 2026-11-04
Cases revision 2 (46 cards: 33 pass, 13 xfail). Narrow re-check of the new cards and the routed variants.

- **Fidelity:** PRF-GE-14 … GE-17 match their cards. Each has the Given rows (neighbours, and for GE-17 the stored `f"Ann. Lee.{TAG}@example.com"`), the exact When argument, and `result is None`. No markers, no mocks. Traceability: 46 cards, 46 tests, no mismatches.
- **Routed variants:** both are now caught.
  - `ILIKE` with `_` escaped and `%` live → GE-14, GE-15. Plain `ILIKE` → GE-09, GE-14, GE-15.
  - Inner spaces stripped → GE-16, GE-17.
  - The reference `lower(trim())` fix still passes every BUG-1860 card. AU-04 and AU-09 belong to other bugs, as in round 1.
- **Runs:** 33 passed, 13 xfailed ×3 (stable). Branch coverage 100%. `--runxfail`: 13 failed, 33 passed.
- **Mutation:** not re-run, because the source is unchanged (round 1: 8/8 killed).
- **Findings:** none. Round-1 findings 1 and 2 are closed. **Verdict: PASS.**
