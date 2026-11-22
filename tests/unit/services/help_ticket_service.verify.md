# Verification — `app/services/help_ticket_service.py`

> **Current verdict (round 2, 2026-11-04):** PASS — 62 passed · 26 xfailed · 100% branch · mutation 12/12 killed (after excluding 2 equivalent: L48, L119, per spec revision)
> **Round 1 verdict:** NEEDS WORK
> Tests: 61 passed · 26 xfailed (reproduced ✅: 25 strict plus L-16 non-strict, each on its card's line) · coverage 100% branch
> Mutation: 14 mutants · 11 killed · 3 survived → score 79% (after excluding 0 equivalent, 0 dead, 0 bug-path)
> Hand variants (BUG-1863 fix shapes, in memory): 11 run · 8 caught · 2 survive (equivalent at this layer) · 1 reference
> Source commit: e48a092 · Cases revision: 1

## Summary
The tests are faithful: all 87 cards are implemented one to one, with exact messages, `type(...) is`
checks, commit-point snapshots and real re-reads after `db.rollback()`. The only patches are the
Conventions' clocks, spies and failing commit / refresh. The runs match the notes. L-16 (non-strict) xfailed
in all three runs.

The BUG-1863 (OQ-8) cards hold up well. Every hand-written wrong fix that changes the database outcome is
caught:
- a text change allowed when a status rides along (U-22)
- the creator compared with the wrong id (U-01, U-02, U-08, U-32)
- an ownerless ticket left editable (U-24)
- only `title` checked (U-17 … U-21)
- only changed or non-null values counted (U-19, U-23)
- a wrong message (U-16 … U-24) or a wrong exception type (U-16 … U-25)

The work still needed is outside the security rule. One mutant survives because the platform list's default
`limit` has no card. Two survive because spec gap 2 is still open.

## Findings
| # | Kind | Case / line | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing | `list_platform_tickets` R1 (paging), source line 131 | No card calls `list_platform_tickets` without `limit`. Every P card passes `limit=1000` or `100000`, so the default of 100 is never checked. `list_tickets` has one (L-09). | mutant #10 `L131 100 -> 101` survived | case designer: a card like L-09. 101 tickets whose title carries TAG, `search=TAG`, no `limit` → `len(own(result)) == 100` |
| 2 | spec-gap | `create_ticket` R3 / `update_ticket` R7 ("if that re-read finds nothing, the refreshed row is used"), source lines 48, 119 | Cases gap 2 is still open in the APPROVED spec. The fallback can only be reached by patching the DAO's `get_by_id`, which is not an external, so no card exists. On every reachable path `refreshed` is the same identity-mapped instance as `ticket`, so `or` vs `and` cannot be seen. | mutants #13 `L48 Or -> And` and #14 `L119 Or -> And` survived | describer (fill-gaps): either allow a DAO patch for this one rule, or move the fallback to "not unit-testable". In the second case both mutants become `equivalent`. |

No fidelity findings. Checked against every card:
- "nothing written" uses the cards' own definition (row counts of W1 and W2), with `unchanged(T)` for UPDATEs.
- Refusal cards run without a savepoint after a commit point, as the Conventions say.
- U-11 uses the real clock under `SET LOCAL TIME ZONE 'America/New_York'`.
- L-16 asserts the exact order and is not weakened.

## Surviving mutants
| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 10 | 131 | `limit: int = 100` → `101` (`list_platform_tickets`) | case-missing | The rule exists (paging is DAO `list_platform`, default 100), but no card uses the default | case designer |
| 13 | 48 | `refreshed or ticket` → `refreshed and ticket` (`create_ticket`) | spec-gap | Can only be seen when the re-read returns `None`. Cases gap 2 asks the describer whether that may be tested. | describer |
| 14 | 119 | `refreshed or ticket` → `refreshed and ticket` (`update_ticket`) | spec-gap | Same as #13 | describer |

### Hand variants of the BUG-1863 fix (scratch plugin `hts_variants.py`, run on the U cards except the other bugs' U-10, U-11, U-26 … U-31, with `--runxfail`)
| Variant | Caught by |
|---|---|
| reference: refuse before any write when `title`/`description`/`category` is sent and the caller is not `created_by` (or `created_by` is NULL) | — (26 passed) |
| text allowed when `status` is in the same payload | U-22 |
| creator compared with `ticket.id` | U-01, U-02, U-08, U-32 |
| creator compared with `ticket.closed_by` | U-01, U-02, U-08, U-32 |
| ownerless ticket (`created_by` NULL) editable by anyone | U-24 |
| only `title` checked | U-17, U-18, U-19, U-21 |
| only a changed, non-null value counts | U-19, U-23 |
| wrong message | U-16 … U-24 |
| `PermissionError` instead of `HelpTicketForbiddenError` | U-16 … U-25 |
| **refusal placed after the write** (update flushed, then raise) | survives: equivalent at this layer |
| **status written first, text refused after** | survives: equivalent at this layer |

The two "after the write" variants cannot be seen through this service. The service's TC3 rollback
discards the flushed UPDATE before any test can read it, and nothing outside the transaction is touched.
The manager itself does not roll back, so the order matters there. This goes to the help ticket manager
spec (FU-1): its cards for R3a should record statements and assert that no `UPDATE help_tickets` is sent
before the refusal (describer / case designer, when that manager is specified).

"Suspended member": at this layer the role is an argument. Suspended and invited members are refused
earlier, by `get_current_workspace` (`has_access` requires `status == 'active'`). `_workspace_role` in
`app/api/v1/endpoints/help_tickets.py` reads the membership without a status filter and depends on that
dependency running first. This is integration-level, and there is no unit card to add here.

## Traceability
cases 87 · tests 87 · unmatched: none · marker mismatches: none. 25 strict xfails: BUG-1441, BUG-1443,
BUG-1574 ×8, BUG-1575 ×2, BUG-1576, BUG-1577, BUG-1578, BUG-1863 ×10. HTS-L-16 is `strict=False` for
BUG-1442, as its card says. Every reason names its BUG ID, and all of them exist in `bugs.md`.

## Commands run
```
.venv/Scripts/python.exe -m pytest tests/unit/services/test_help_ticket_service.py -q -p no:cacheprovider --cov=app.services.help_ticket_service --cov-branch --cov-report=term-missing
  app\services\help_ticket_service.py  45 stmts  0 miss  0 branch  100%
  61 passed, 26 xfailed, 15 warnings (SQLAlchemy SAWarnings from the coverage re-import, as the notes say)
  repeat runs: 61 passed, 26 xfailed ×2 — stable (L-16 xfailed each time)

.venv/Scripts/python.exe -m pytest tests/unit/services/test_help_ticket_service.py -q -p no:cacheprovider --runxfail -rf --tb=line
  26 failed, 61 passed. Each fails on its card's line: C-05 'HELP-2027-001'; C-06 / U-26 untrimmed; C-07, C-08,
  U-27, U-28, U-30, U-31 DID NOT RAISE ValidationError; C-09 / U-29 '   ' is None; L-12 set() == {..};
  L-16 order [TA, TC, TB]; U-10 closed_by OWN; U-11 timedelta(seconds=18000); U-16 … U-25 Then 1
  DID NOT RAISE HelpTicketForbiddenError; P-05 {T1, T2} == {T1}

.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/services/help_ticket_service.py tests/unit/services/test_help_ticket_service.py --json <scratch>/hts_mut.json
  Mutants: 14 · killed 11 · timeout 0 · survived 3 · score 79%
  SURVIVED #10 L131:21 const 100 -> 101 · #13 L48:44 Or -> And · #14 L119:44 Or -> And

PYTHONPATH=<scratch> HTS_VARIANT=<v> .venv/Scripts/python.exe -m pytest tests/unit/services/test_help_ticket_service.py -q -p no:cacheprovider -p hts_variants --runxfail -k "hts_u_ and not hts_u_10 and not hts_u_11 and not hts_u_26 … hts_u_31"
  (scratch = C:\Users\User\AppData\Local\Temp\makorsh-pipeline\oqv; results in the table above)
```

## Round 2 — 2026-11-04
Cases revision 2 (88 cards: 62 pass, 26 xfail). The spec now marks the "re-read finds nothing" fallback (create R3, update R7) as not unit-testable.

- **Fidelity:** HTS-P-08 matches its card: 101 tickets titled `f"T{k} {TAG}"`, `list_platform_tickets(db, search=TAG)` with no `limit`, then `len(own(result)) == 100`. Traceability: 88 cards, 88 tests, no mismatches.
- **Mutant L131 `100 -> 101`:** KILLED. Command: `mutate.py app/services/help_ticket_service.py tests/unit/services/test_help_ticket_service.py --lines 131-131` → 1 mutant, 1 killed.
- **Mutants L48 and L119 (`or -> and`):** these are now `equivalent`. Per the spec revision, the `None` side cannot be reached without patching the DAO, and on every reachable path the re-read is the same identity-mapped instance.
- **Score:** 12 killed / (14 − 2 equivalent) = 100%.
- **Runs:** 62 passed, 26 xfailed ×3 (stable; L-16 xfailed each time). Branch coverage 100%. `--runxfail`: 26 failed, 62 passed.
- **Findings:** none. Round-1 findings 1 and 2 are closed. The note about refuse-before-write for the future help ticket manager spec stands. **Verdict: PASS.**
