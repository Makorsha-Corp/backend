# Verification — `app/services/financial_audit_log_service.py`

> **Verdict:** PASS (round 2, 2026-11-09; round 1 NEEDS WORK)
> Tests: 24 passed · 0 xfailed (nothing to reproduce; 3 runs identical) · coverage 100% branch (17 statements, 0 branches)
> Mutation: 17 mutants · 17 killed · 0 survived → score 100% (after excluding 0 equivalent, 0 dead, 0 bug-path; source unchanged since round 1)
> Hand variants: 11 (10 round 1 + `entity_limit_cap100` round 2) · 9 killed · 2 survived (1 `equivalent` by design, 1 out of scope by design); the round-1 `case-missing` survivor is now killed by FALS-R-06
> Source commit: e48a092 · Cases revision: 3 (round 1 read revision 2)

## Summary
The tests match the cards. Traceability is clean, every Then line is asserted exactly as written, nothing is mocked except the commit and rollback spies (which wrap the real methods), three plain runs give the same result, and all 17 `mutate.py` mutants are killed. The hand variants for the riskiest faults are caught too: skip and limit swapped, the workspace filter dropped, related rows lost, a DAO error swallowed, a stray commit, a "helpful" swap of reversed date bounds, and a `limit` floor. One wrong change still passes all 22 cards. If the service caps `limit` at its default (50 for `get_recent_logs`, 100 for the others), nothing notices, because no card asks for more rows than the default. Yet spec R1 says `limit` is passed on as given, and the endpoint allows up to 200. The case designer must add one card for this. Nothing else has to change.

## Findings
| # | Kind | Case / line | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing | `get_recent_logs` R1 ("`limit` is passed on as given"); the same for R1 of the other five readers | Every card's `limit` is at or below the default (R-02 `limit=2`, the others `limit=1`, the defaults with 51 / 101 rows). No card asks for more than the default, so a service that caps or clamps `limit` passes. The endpoints allow `limit` up to 200 (`le=200`), so such a regression would silently shorten the page. | Hand variant `recent_limit_cap50` (`get_recent_logs` passes `min(limit, 50)`): **22 passed**. | **case designer**: add a boundary card to `get_recent_logs` (52 rows, `limit=51` → `len == 51`, the newest 51 in order). Optionally add one for a `skip`/`limit` reader too (102 rows, `limit=101` → 101 rows), for example on `get_by_entity`. |

No fidelity findings. Every Then line of every card is asserted in card order with the exact value (`ids(...) ==` with order, `== []`, `pgcode ==`, `call_count == 0`). Each `raises: DataError` is wrapped as the Conventions prescribe (spies → `pytest.raises` → `begin_nested`). `x_gone` is written as `db.rollback()` followed by `db.get(...) is None`. There is no `try`/`except`, and nothing is patched beyond the spies.

## Surviving mutants
None. All 17 were killed: 6 × `return None` and 11 default-constant mutants (`50→51`, `0→1`, `100→101`). Each was a real test failure.

## Hand variants
Run with my own plugin `fasv_variants.py` (`C:\Users\User\AppData\Local\Temp\makorsh-pipeline\tplv\fasvc\plug\`, selected with `FASV=<name>`, loaded with `-p fasv_variants`). It monkeypatches the service class in the test process; `app/` is untouched.

| Variant | Result | Killed by / class |
|---|---|---|
| `get_by_entity` swaps `skip`/`limit` when `skip` is given | KILLED | E-04 (negative skip becomes limit) |
| `get_by_user` without the workspace filter | KILLED | U-01 (Z0 / Z2 appear) |
| `get_related_logs` calls `get_by_entity` (related rows lost) | KILLED | L-01, L-02 |
| `get_recent_logs` floors `limit` at 1 | KILLED | R-04, R-05 |
| `get_by_entity` swallows the DAO error and returns `[]` | KILLED | E-04 |
| `get_by_date_range` swaps reversed bounds | KILLED | D-02 |
| `get_by_user` commits after reading | KILLED | U-03 (spies / x_gone) |
| `get_recent_logs` caps `limit` at 50 | **SURVIVED** | `case-missing`, finding 1 |
| `get_by_action_type` re-sorts ties by `id ASC` | SURVIVED | `equivalent` here. Every card gives each row its own `performed_at` by design, and the tie-break is BUG-2370, carded in the DAO's cases. |
| `get_by_action_type` matches `action_type` case-insensitively (own query) | SURVIVED | Not a finding. Exact matching is a DAO rule, deferred to `financial_audit_log.cases.md` (Deferred row "DAO filters, exact compares"). The service is a one-line pass-through, so `mutate.py` cannot make this change. |

Skip/limit swap with explicit equal values (`skip=1, limit=1` in E-02, L-02, A-02, U-02, D-03) can't be seen in those cards. A full swap is still killed by the default cards (-03 / -04: `skip=100, limit=0` → `[]`), so this is no finding.

## Traceability
Cases 22 · tests 22 · each case ID in exactly one docstring and `# [claude]` comment · unmatched: none · marker mismatches: none (no xfail cards, no xfail markers) · BUG IDs used: none in markers (BUG-2370 / 2371 / 2373 are cited only in comments and Deferred rows, and all exist in `bugs.md`).

## Commands run
```
COVERAGE_FILE=…\tplv\fasvc\.cov1
.venv/Scripts/python.exe -m pytest tests/unit/services/test_financial_audit_log_service.py -q -p no:cacheprovider -o addopts="" --cov=app.services.financial_audit_log_service --cov-branch --cov-report=term-missing
  → app\services\financial_audit_log_service.py  17  0  0  0  100%  ·  22 passed, 15 warnings in 10.61s
.venv/Scripts/python.exe -m pytest … -o addopts="" --runxfail -rf      → 22 passed in 4.71s
.venv/Scripts/python.exe -m pytest … -o addopts=""  (×2 more)          → 22 passed in 4.66s · 22 passed in 4.95s
.venv/Scripts/python.exe -m ruff check tests/unit/services/test_financial_audit_log_service.py → All checks passed!
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/services/financial_audit_log_service.py tests/unit/services/test_financial_audit_log_service.py --json …\tplv\fasvc\mut.json
  → Mutants: 17 · killed 17 · timeout 0 · survived 0 · score 100%
PYTHONPATH=…\tplv\fasvc\plug FASV=<variant> .venv/Scripts/python.exe -m pytest … -o addopts="" -p fasv_variants   (10 variants, table above)
```

## Notes for the future
- **Permissions:** OQ-23 is already recorded in `docs/future/permissions.md`. The service takes no caller argument, so the read gate has to live in the endpoints, or a `user_id` parameter has to be added. If a parameter is added, it should be required, not optional, so that a forgotten argument cannot skip the check.

## Round 2 — 2026-11-09

> **Current verdict:** PASS — cases revision 3; 24 passed · 0 xfailed · coverage 100% branch; mutation unchanged (17/17, 100%, source unchanged, not re-run).

- **New cards read against their tests:** FALS-R-06 and FALS-E-05. Both are faithful: the Given is built with `add_all` and one flush (`many_logs`), the When passes `limit=51` / `limit=101`, and both Then lines are asserted exactly (`len(result) == 51` / `101`, then `ids(result) == newest[:N]`). No other test changed.
- **Round-1 finding 1 closed:** variant `recent_limit_cap50` now fails FALS-R-06 (1 failed, 23 passed). The new variant `entity_limit_cap100` fails FALS-E-05 (1 failed, 23 passed).
- **Runs:** 3 plain runs, 24 passed each, so nothing is flaky. ruff is clean.
- **Findings:** none.

```
COVERAGE_FILE=…\tplv\fasvc2\.cov .venv/Scripts/python.exe -m pytest tests/unit/services/test_financial_audit_log_service.py -q -p no:cacheprovider -o addopts="" --cov=app.services.financial_audit_log_service --cov-branch --cov-report=term-missing
  → 24 passed; financial_audit_log_service.py 17 stmts 0 miss 100%
(2 more plain runs) → 24 passed, 24 passed
PYTHONPATH=…\tplv\fasvc2\plug FASV=recent_limit_cap50  … -p fasv2_variants → 1 failed (FALS-R-06), 23 passed
PYTHONPATH=…\tplv\fasvc2\plug FASV=entity_limit_cap100 … -p fasv2_variants → 1 failed (FALS-E-05), 23 passed
```
