# Verification — `app/managers/help_ticket_manager.py`

> **Verdict:** PASS
> Tests: 120 passed · 15 xfailed (reproduced ✅, all strict, each fails on its card's Then line) · coverage 100% branch (72 statements, 20 branches)
> Mutation: 62 mutants · 62 killed · 0 survived → score 100% (after excluding 0 equivalent, 0 dead, 0 bug-path)
> Source commit: e48a092 · Cases revision: 1

## Summary
These tests can be trusted. Every card is implemented once, with the marker its Expect line asks for, and every Then line is asserted as written. `mutate.py` killed all 62 mutants. I also wrote 20 variants of my own aimed at the access rules (OQ-5, OQ-8, BUG-1863, BUG-1578). The passing tests caught every loosened or tightened visibility rule and every unscoped read. The BUG-1863 xfail cards (run with `--runxfail`) caught every wrong fix I tried: a refusal after the flush, a refusal after the attributes were set, text allowed together with a status change, `category: null` or a ticket with no creator let through, and a check on changed values only. A correct fix passes all of them. Nothing has to change.

## Findings
None.

## Surviving mutants
None (`mutate.py`: 62/62 killed).

### Hand variants (verifier's own, `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\mgr6v\variants.py`, run on a temp copy)
| # | Variant | Run | Result | Caught by |
|---|---|---|---|---|
| H01 | platform-admin grant dropped | pass tests | killed (3) | AC-01, AC-02, G-04 |
| H02 | creator check against `closed_by` (wrong id) | pass | killed (6) | AC-07, AC-08, AC-14, G-01 … |
| H03 | creator check `created_by is not None` (anyone) | pass | killed (12) | AC-09 … AC-17, G-06 … G-21 |
| H04 | ticket with no creator open to anyone | pass | killed (2) | AC-12, G-09 |
| H05 | any non-null role sees all | pass | killed (22) | VA-05 … VA-13, AC-*, … |
| H06 | `finance` added to view-all | pass | killed (8) | VA-05, VA-14, AC-10, L-04 … |
| H07 | too strict: ground-team-manager dropped | pass | killed (7) | VA-02, VA-04, AC-04, G-03, L-02 … |
| H08 | get by id without workspace | pass | killed (6) | G-13 … G-18 |
| H09 | list without the creator filter | pass | killed (4) | L-03 … L-06 |
| H10 | list always filtered by creator (too strict) | pass | killed (10) | L-01, L-02, L-07 … |
| H11 | creator filter applied in Python after paging (BUG-1958 shape) | pass | killed (1) | L-06 |
| H12 | list with `workspace_id=None` | pass | killed (15) | L-01 … L-12 |
| H20 | BUG-1863 correct fix (refuse before any write) | `--runxfail` U-0x, U-18 … U-28 | 20 passed | — (the fix is accepted) |
| H21 | BUG-1863 refusal after the DAO flush | `--runxfail` | killed (11/11) | U-18 … U-28 |
| H22 | BUG-1863 refusal after `setattr`, no flush | `--runxfail` | killed (10/11) | all but U-22 (there the value set equals the current one, so nothing is modified: equivalent) |
| H23 | text change allowed together with a status change | `--runxfail` | killed | U-23, U-24 |
| H24 | `category: null` / no-creator ticket not counted as text edit | `--runxfail` | killed | U-21, U-25 |
| H25 | over-strict: non-creator refused for close / reopen | pass | killed (8) | U-06, U-08, U-09, U-11 … U-15 |
| H26 | refuse only when the text value changes | `--runxfail` | killed | U-22 |
| H27 | BUG-1578 correct fix (admin gets no creator filter) | `--runxfail` L-1x | 10 passed | — (L-14, L-15 pass; L-16 holds) |

## Traceability
cases 135 · tests 135 (one `def` per card, `# [claude] <ID>` on each) · unmatched: none · marker mismatches: none. 15 xfail cards → `xfail(strict=True)` with the bug in the reason (BUG-1576 1, BUG-1577 1, BUG-1578 2, BUG-1863 11). Every BUG ID exists in `docs/testing/bugs.md`. Checked with my own AST script (`mgr6v\trace.py`).

Fidelity: I read all 135 cards against their tests. No missing, weakened or changed assertion. No wrong setup: the caller id and role are the ones each card names, and the W0 / W2 rows are where the cards put them. No in-memory-only write check, no swallowed failure. Only the four clocks the Conventions name and the `wraps=` commit / rollback spies are patched. In the BUG-1863 cards, `session:` / `pending:` checks run before any re-read, under a plain `pytest.raises` with no savepoint. Helpers (`snap`, `unchanged` with all 8 columns, `counts` over W0/W1/W2, `record_sql`, standing-row order) match the Conventions.

## Commands run
```
COVERAGE_FILE=…\mgr6v\.cov_h
.venv/Scripts/python.exe -m pytest tests/unit/managers/test_help_ticket_manager.py -q -p no:cacheprovider --cov=app.managers.help_ticket_manager --cov-branch --cov-report=term-missing
  app\managers\help_ticket_manager.py  72  0  20  0  100%
  120 passed, 15 xfailed, 19 warnings in 9.11s
.venv/Scripts/python.exe -m pytest tests/unit/managers/test_help_ticket_manager.py -q -p no:cacheprovider --runxfail -rf
  15 failed, 120 passed — the 15 are exactly the xfail cards
.venv/Scripts/python.exe -m pytest … --runxfail --tb=line -m xfail
  L-14 :1186 set() == {TM, TC} · L-15 :1202 · U-16 :2034 closed_by rewritten · U-17 :2058 5 h > 60 s · U-18 … U-28 "DID NOT RAISE HelpTicketForbiddenError" on the Then 1 raises line
2 more plain runs: 120 passed, 15 xfailed each (no flaky test)
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/managers/help_ticket_manager.py tests/unit/managers/test_help_ticket_manager.py --json …\mgr6v\mut_help.json
  Mutants: 62 · killed 62 · timeout 0 · survived 0 · score 100%
.venv/Scripts/python.exe …\mgr6v\variants.py help   (table above)
```

## For the coming features
- **Permissions.** These points hold today, and the U and L cards pin each one, so a refactor will not drift silently:
  - The see-right is `can_access_ticket`: platform admin, then role, then creator.
  - The edit-right does not exist yet (BUG-1863). Its fix must refuse the **whole** payload before any `setattr` or flush, including a text change together with a status change, `category: null`, an unchanged value, and a ticket with no creator.
  - Close / reopen stays open to everyone who passed the see-right.
  - `list_tickets` does not reuse `can_access_ticket` (BUG-1578). A shared predicate would keep the list and the get in step.
  - Attachments call neither helper (BUG-1950).
  - `role` is trusted as passed, so a suspended membership's role still counts (BUG-1885, in the endpoint).
- **Notifications.** The manager sends nothing. The hooks are `create_ticket` and the status branch of `update_ticket`. Notify only on a real transition: after BUG-1576 a repeat close is a no-op. Send after the service's commit.
