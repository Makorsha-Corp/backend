# Verification — `app/services/base_service.py`

> **Verdict:** PASS
> Tests: 8 passed · 0 xfailed (nothing to reproduce) · coverage 100% branch (10 statements, 0 branches)
> Mutation: 1 mutant · 1 killed · 0 survived → score 100% (after excluding 0 equivalent, 0 dead, 0 bug-path)
> Fidelity: **0 of 8 unfaithful** (8 / 8 right; read by eye against every card)
> Hand variants: 24 (+1 no-op guard) · 22 caught by a pass card · 2 others: 2 equivalent (none is a rule gap)
> Source commit: e48a092 · Cases revision: 1; spec APPROVED

## Summary
- **The tests can be trusted as written.** All 8 match their cards, line for line.
- **`mutate.py` has almost nothing to work on here** (one `raise → pass` mutant; the `try/except` gives coverage.py no branch), so the hand variants carry this verdict. Every one the task asked for is caught: a dropped rollback (BSV-C-02, C-03, C-04), a swallowed exception (C-02, C-03), a re-raised copy, with or without `from e` (C-02, `exc.value is E1`), a wrapped exception (C-02), and a double rollback (C-02, `rb.call_count == 1`).
- Also caught: a narrowed `except`, a hidden rollback error (C-04), flushing instead of committing, rolling back before the commit, committing twice (C-05), a non-`None` return, and for `_rollback_transaction` a no-op, a commit, a double rollback (R-02), a swallowed, wrapped or copied rollback error (R-03), and an `expunge_all` in place of the rollback.
- The only variants that no card sees are equivalent (`raise e` in place of a bare `raise`, and `raise r from None` on the rollback error).

Written by Claude (all 8 under `# [claude]`). Findings in local-written tests / local-written tests: 0 / 0. In others: 0 / 8. No `base_service.local-run.json` exists, so there is no `## Local-coder patterns` section.

## Findings
None.

## Surviving mutants
None. The one mutant (L30 `raise → pass`) is killed by BSV-C-02 (`1 failed, 1 passed` under `-x`).

## Hand variants
`plug\vplug.py` is a pytest plugin that, before each test, swaps in the module built from one edited copy of today's source (methods are set on the real `BaseService` class, so the module-level `svc` picks them up). `variants.py` holds the edits; `runvars.py` checks each applies exactly once and changes the source, then runs the whole test file. The no-op guard `b_nop` gives `8 passed`.

| Group | Variants | Pass card | Cards that fail | Others |
|---|---|---|---|---|
| commit: dropped rollback, `expunge_all` instead, `except SQLAlchemyError` only | 3 | 3 | BSV-C-02, C-03, C-04 | — |
| commit: swallowed exception | 1 | 1 | BSV-C-02, C-03 | — |
| commit: re-raised copy (`type(e)(*e.args)`, also `from e`), wrapped in `RuntimeError` | 3 | 3 | BSV-C-02 | — |
| commit: double rollback | 1 | 1 | BSV-C-02 | — |
| commit: rollback error hidden (commit's re-raised) | 1 | 1 | BSV-C-04 | — |
| commit: `flush` instead of `commit`; rollback before commit | 2 | 2 | BSV-C-01, C-02, C-04, C-05 (+C-03) | — |
| commit: committed twice; returns `True` | 2 | 2 | BSV-C-05; BSV-C-01, C-05 | — |
| commit: `raise e`; `raise r from None` on the rollback error | 2 | 0 | — | 2 × equivalent |
| rollback: no-op, commit, `expunge_all` | 3 | 3 | BSV-R-01, R-02, R-03 | — |
| rollback: double; returns `True`; flush + commit + rollback | 3 | 3 | BSV-R-02; BSV-R-01, R-02 | — |
| rollback: error swallowed, wrapped, copied | 3 | 3 | BSV-R-03 | — |
| **Total** | **24** | **22** | | **2** |

### Considered and not listed
| Variant | Why it is not a finding |
|---|---|
| `b_raise_e` | **Equivalent.** `raise e` re-raises the same object; only one more traceback frame is added. B2 holds. |
| `b_rollback_error_from_none` | **Equivalent under B3.** `raise r from None` keeps `__context__` (= the commit's exception) and only sets `__suppress_context__`, which changes how the traceback prints, not what B3 or any caller checks. |

## Reproduced claims
- **Result line of the notes holds:** `8 passed` in 4 of 4 default runs (the coverage run among them), and `8 passed` with `--runxfail`. No flaky test.
- **Mocks:** only `patch.object(db, "commit" | "rollback", …)` with `side_effect=` or `wraps=`, exactly as the Conventions' failing commit / failing rollback / spies. No `try`, no `if`, no broad `pytest.raises` in a test body. BSV-C-03 leaves out `as rb` (its card counts no rollbacks); the wrap is still there, so the real rollback runs.
- Each `committed:` group starts with one `db.rollback()` (C-01, C-05); `count:` lines run none (C-02, C-03, R-01, R-02), as the Conventions say.

## Traceability
cases 8 · tests 8 · unmatched: none · duplicates: none · marker mismatches: none (all `pass`, no markers). Card order equals file order. Each docstring holds its card's ID, title and Rules; `# Then N` numbers match the card. No BUG IDs used. All sit under `# [claude] <ID>`. `ruff check` passes.

## Limits of this round
- **The variants are mine.** They show what these tests catch around them, not every possible break.
- **TC1–TC6 are not judged here.** The cases file defers them to each subclass's own cases, as the spec says.
- **Runs were not isolated.** Other agents may have been live on `marker_test`. Each kill is a plain `N failed`.

## Commands run
```
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/services/base_service.py tests/unit/services/test_base_service.py --timeout 300 --json <scratch>/res/mut_base.json
  [1/1] L30:12 raise  raise -> pass  KILLED
  Mutants: 1 · killed 1 · timeout 0 · survived 0 · score 100%
.venv/Scripts/python.exe -m pytest tests/unit/services/test_base_service.py -q -p no:cacheprovider --cov=app.services.base_service --cov-branch --cov-report=term-missing
  8 passed · app\services\base_service.py 10 0 0 0 100%
.venv/Scripts/python.exe -m pytest tests/unit/services/test_base_service.py -q -p no:cacheprovider --runxfail -rf
  8 passed
pytest, default, 2 more runs                                    8 passed each
trace.py (cards vs tests: IDs, order, markers, patches)         clean
runvars.py (hand variants through plug\vplug.py)                as above
.venv/Scripts/python.exe -m ruff check tests/unit/services/test_base_service.py   All checks passed!
git diff --stat -- app/services                                 (empty)
```
Scratch: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\svc4v\` (private `COVERAGE_FILE`). Only this report was written in the repo. No commit. Nothing was killed.
