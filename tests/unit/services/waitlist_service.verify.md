# Verification — `app/services/waitlist_service.py`

> **Current verdict (round 2, 2026-11-04): PASS.** The round-1 finding is fixed; see "Round 2" at the end. The round-1 header below is kept as it was.

> **Verdict:** NEEDS WORK (no unfaithful test; one user-visible text is unguarded. The fix goes to the designer)
> Tests: 30 passed · 5 xfail, 4 strict + 1 non-strict (reproduced ✅) · coverage 100% branch (64 statements, 16 branches)
> Mutation: 38 mutants · 36 killed · 2 survived → score 97% (36 / 37, after excluding 1 equivalent, 0 dead, 0 bug-path)
> Fidelity: **0 of 35 unfaithful** (read by eye, card against test)
> Hand variants: 14 · 13 caught by a pass card · 1 not caught (routed)
> Source commit: e48a092 · Cases revision: 1; spec APPROVED

## Summary
- **The tests are faithful.** All 35 match their cards: the per-test `TAG`, the `signup` / `req` recipes, the Turnstile stub recording `(url, data)`, the settings patches, S-06's first-call-`None` race, and every Then line with exact values (H_PEPPER / H_SEKRIT literals, form data, the 400 / 502 texts).
- **The service's own rules are well guarded.** These variants all fail pass cards: the honeypot, normalising, name trimming, a blank company kept, the IP left unhashed, the salt ignored, `remoteip` always sent, `raise_for_status` dropped, the re-lookup after a failure, the rollback, commit → flush, the status filter and the `skip` echo.
- **What is missing:** every card compares `result.message` with the module's own `SUCCESS_MESSAGE` constant. A change to the public text ("You're on the list — we'll be in touch.", given in the spec's Facts) cannot be seen (designer).

No `waitlist_service.local-run.json`; all 35 tests are under `# [claude]`. Findings in local-written tests / local-written tests: 0 / 0. In others: 0 / 35.

## Findings
| # | Kind | Case / line | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing | WSV-S-01 / S-03 Then 2 (`submit_signup` Returns; spec Facts `SUCCESS_MESSAGE`), source line 22 | The cards assert `result.message == SUCCESS_MESSAGE`, using the constant imported from the module under test, so the check moves with any change to the text. One card should assert the literal from the spec: `"You're on the list — we'll be in touch."` (with the em dash). | mutant #2 (`→ ''`) survived; hand variant `message_changed` (`"OK"`): 30 passed | case designer |

## Surviving mutants
| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 2 | 22 | `SUCCESS_MESSAGE` text → `''` | case-missing | Finding 1 | case designer |
| 20 | 73 | `skip_turnstile` default `False` → `True` | equivalent | The parameter is never read in the body (spec `submit_signup` R5: "has no effect"); S-08 shows that `True` changes nothing. | — |

## Hand variants
Made with `hv.py`. Each is one text edit to today's source, run on the pass cards without `-x`.

| Variants | Caught | Cards that fail |
|---|---|---|
| submit: commit → flush; rollback dropped; no re-lookup; blank company kept; names untrimmed; email not lower-cased; IP unhashed | 7 / 7 | S-01, S-02, S-04, S-06, S-07, S-08, N-01 |
| update: commit → flush | 1 / 1 | U-02, U-03, U-04 |
| Turnstile: `remoteip` always; `raise_for_status` dropped | 2 / 2 | T-03; T-06 |
| list: status dropped; `skip` echo 0 | 2 / 2 | L-02; L-01 |
| hash: salt ignored | 1 / 1 | H-03, S-01 |
| message text changed | 0 / 1 | — (Finding 1) |

## xfail tests: fails-today check
`--runxfail` with `vfailmap.py`: 5 failed, 30 passed. Each card fails on its "Fails today on" line:
- T-08: inside Then 1's wrap, the `ValueError: Expecting value` raised by the stub's `json()` escapes.
- T-09: Then 1 `AttributeError: 'list' object has no attribute 'get'`.
- S-09: Then 1 `DID NOT RAISE ValidationError`.
- L-06: Then 2 `[A, B] == [A]`. L-07 (non-strict): Then 2 `[B, C, A]`, xfailed in every run.

## Reproduced claims
- The notes' Result line holds: `30 passed, 5 xfailed` in the coverage run and in 3 more plain runs. No flaky test.
- Patches are only those that Conventions name (settings, the stub, the failing commit, S-06's race). `ruff check` passes. `git diff -- app/services` is empty.

## Traceability
cases 35 · tests 35 · unmatched: none · duplicates: none · marker mismatches: none (`trace.py`). BUG-1410, BUG-1411, BUG-1579 and BUG-1580 are in `docs/testing/bugs.md`. Card order equals file order.

## Commands run
```
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/services/waitlist_service.py tests/unit/services/test_waitlist_service.py --json <scratch>/mut_waitlist_service.json
  Mutants: 38 · killed 36 · timeout 0 · survived 2 · score 95% (raw)
.venv/Scripts/python.exe -m pytest tests/unit/services/test_waitlist_service.py -q -p no:cacheprovider --cov=app.services.waitlist_service --cov-branch --cov-report=term-missing
  30 passed, 5 xfailed · app\services\waitlist_service.py 64 0 16 0 100%
.venv/Scripts/python.exe -m pytest tests/unit/services/test_waitlist_service.py -q -p no:cacheprovider --runxfail -rf     5 failed, 30 passed
pytest plain × 3                                                                                                       30 passed, 5 xfailed each
vfailmap.py; hv.py waitlist_service (14 variants); trace.py; ruff check                                                as above
```
Scratch: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\svc2v\` (private `COVERAGE_FILE`). Only this report was written in the repo. No commit. No process was killed.

## Round 2 — 2026-11-04
**Verdict: PASS.** Cases revision 2, no spec change. 30 passed · 5 xfail (4 strict + 1 non-strict) · coverage 100% branch.

- **The changed test is faithful to its card.** WSV-S-01 Then 2 asserts the literal `"You're on the list — we'll be in touch."`, and the dash in the file is U+2014 (bytes `e2 80 94`), as the card says. Its other Then lines are unchanged.
- **The routed variant is now caught** (`hv2.py`, pass cards): the message text changed to `"OK"` or to `""` → S-01 fails. In round 1, all 30 passed.
- **Mutation, only on the lines of the round-1 survivors** (`--lines 22-22`, `--lines 73-73`): the message `→ ''` is killed by S-01. `skip_turnstile` `False → True` survives and stays equivalent (R5). Module score: 37 / 37 non-equivalent = **100%**.
- **Runs:** coverage run plus 3 plain runs each give `30 passed, 5 xfailed`; `--runxfail` gives `5 failed, 30 passed`, and every xfail test still fails on its card's line. No flaky test. `trace.py`: 35 cards, 35 tests, no marker mismatch. `ruff check` passes. `app/services` is unchanged.
- **Findings:** none.
