# Verification — `app/services/help_ticket_service.py`

## Round 2 (2026-11-26)

> **Verdict:** PASS
> Tests: 119 passed · 39 xfailed (reproduced ✅: the same 39 fail under `--runxfail`, on the same Then lines as round 1) · coverage 100% branch (57 stmts, 2 branches)
> Mutation: 24 mutants · 21 killed · 3 survived → score 100% (21 / 21, after excluding 3 equivalent: L48, L123, L150 `or -> and`, as in round 1). Mutant #24 re-run: killed.
> Hand variants re-run: 5 · 2 caught (the two `except` narrowings) · 3 survive (equivalent, as in round 1)
> Source commit: 41d5ac1 · Cases revision: 4

Narrow round, covering the cases Revision 4 additions made for round-1 findings 1–3.

- **Traceability:** 158 cards, 158 tests, one to one, no mismatches (`trace.py`). The new cards HTS-U-60, U-61, U-62 and V-23 are all `pass` and carry no xfail marker. The counts line reads 158 · 119 pass · 39 xfail.
- **Fidelity of the four new cards:** each test matches its card line by line.
  - **U-60:** `SimpleNamespace(id=CR.id, name="Rahim")` sends `status=OPENED`. The test asserts `HelpTicketStatusChangeForbiddenError` with a `type(...) is` check, then unchanged(T) and nothing written.
  - **U-61:** the same object sends a title. The test checks the returned id, title and `PENDING`, then the committed row after `db.rollback()`.
  - **U-62 and V-23:** both send `HelpTicketUpdate.model_construct(title=None)` and expect `IntegrityError`. Next comes `x not in db`, then `x_gone`, with no test-level rollback before either. Then come nothing written, `SELECT 1`, and unchanged(T).
  - No extra mocks.
- **Round-1 finding 1** (mutant #24, `L118:69 False -> True`): closed. `mutate.py … --lines 118-118` gives 2 mutants, 2 killed.
- **Round-1 finding 2** (`except` narrowed to `(LookupError, PermissionError, ValueError)`): closed. U-62 catches it in `update_ticket` and V-23 in `update_platform_ticket`; each run gave 1 failed, 118 passed, 39 xfailed.
- **Equivalent hand variants:** the three `to_response(refreshed or ticket)` → `to_response(ticket)` variants still survive (119 passed, 39 xfailed). They are equivalent at this layer, as in round 1.
- **Round-1 finding 3** (stale gaps): closed. The cases file's "Spec gaps" rows 3–5 are marked closed by G1–G3. The Reviewer summary now says "Needs a decision: None".
- **Runs:** 119 passed, 39 xfailed in three runs, stable. `--runxfail` gives 39 failed and 119 passed. The set of failing tests is identical to round 1, and only ids and microseconds differ in the messages. None of the new cards is among them.
- **Findings:** none.

Commands:
```
.venv/Scripts/python.exe -m pytest tests/unit/services/test_help_ticket_service.py -q -p no:cacheprovider --cov=app.services.help_ticket_service --cov-branch --cov-report=term-missing
  app\services\help_ticket_service.py  57 stmts  0 miss  2 branch  0 partial  100% · 119 passed, 39 xfailed (×3)
.venv/Scripts/python.exe -m pytest tests/unit/services/test_help_ticket_service.py -q -p no:cacheprovider --runxfail -rf --tb=line
  39 failed, 119 passed
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/services/help_ticket_service.py tests/unit/services/test_help_ticket_service.py --lines 118-118 --json C:\Users\User\AppData\Local\Temp\makorsh-pipeline\help_ticket_service\mutants_r2_l118.json
  Mutants: 2 · killed 2 · survived 0
HTS_VARIANT=<narrow_lookup|noreread>:<method> PYTHONPATH=C:\Users\User\AppData\Local\Temp\makorsh-pipeline\help_ticket_service\plug .venv/Scripts/python.exe -m pytest tests/unit/services/test_help_ticket_service.py -q -p no:cacheprovider -p hts_hand
  narrow_lookup:update → U-62 fails · narrow_lookup:platform → V-23 fails · noreread:* → 119 passed, 39 xfailed (equivalent)
```

---

## Round 1 (2026-11-26)

> **Verdict:** NEEDS WORK
> Tests: 115 passed · 39 xfailed (reproduced ✅: 38 strict plus L-16 non-strict, each on its card's Then line) · coverage 100% branch (57 stmts, 2 branches)
> Mutation: 24 mutants · 20 killed · 4 survived → score 95% (20 / 21, after excluding 3 equivalent, 0 dead, 0 bug-path)
> Hand variants (TC3 / transaction shape, scratch plugin): 16 run (plus the reference) · 11 caught · 5 survive (3 equivalent, 2 case-missing: finding 2)
> Source commit: 41d5ac1 · Cases revision: 3 · Spec revision: 2026-11-26 (Gap log G1–G3)

### Summary
The tests can be trusted for what the cards say. All 154 cards are implemented one to one. I read every
revised and new card against its test and found no fidelity problem: exact messages, `type(...) is` where the
card says type only, commit-point snapshots with `type` in `unchanged(T)`, `committed:` lines after one
`db.rollback()`. The runs reproduce the notes exactly, three times, with no flaky test. Every xfail fails on
the line its card names. The TC3 convention holds where it is written: `X not in db` comes first after the
raise in U-35, U-48, V-05, V-08 and V-12. A rollback spy sits on a non-failing-commit refusal for
`update_ticket` (U-35, U-48) and `update_platform_ticket` (V-05, V-08). `create_ticket` has no refusal, but
C-02's `IntegrityError` leaves the session unusable without the service's rollback, so it is killed too.

Two gaps remain, both for the **case designer**:
- **No card for G2.** Spec G2 closed cases gap 4 ("an object without `is_platform_admin` counts as not an
  admin"), but no card was added. Mutant #24 (`getattr` default `False -> True`) survives.
- **No card with a non-manager error before the commit.** On both update paths, every passing error card
  raises a manager error (`LookupError`, `PermissionError`, `ValueError`; pydantic's `ValidationError` is a
  `ValueError` too). So `except Exception` can be narrowed to those families without any test noticing.

The cases file's "Spec gaps" table and Reviewer summary still list gaps 3–5 as open, but spec G1–G3 has
answered them.

### Findings
| # | Kind | Case / line | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing | `update_ticket` Inputs `user` / spec Gap log G2 (cases gap 4); source line 118 | Spec G2 states the rule: the see-right check and the status flag both use `getattr(user, "is_platform_admin", False)`, and a profile-like object without the attribute counts as not an admin. No card calls `update_ticket` with such an object. Every card passes a real `Profile`, so the `False` default is never read. | Mutant #24 `L118:69 const False -> True` SURVIVED | **case designer**: one card, for example `user=SimpleNamespace(id=CR.id)` (the creator, no `is_platform_admin`), `role=GT_R`, on a pending ticket, `payload=HelpTicketUpdate(status=OPENED)`. Then: raises `HelpTicketStatusChangeForbiddenError` (type only), unchanged(T). A second line could be a text-only change by the same object that passes, which shows the see-right tolerates the missing attribute. |
| 2 | case-missing (TC3, non-manager error) | `update_ticket` R7 / `update_platform_ticket` R6 (TC3 "any exception … anything") | No passing card on either update path raises a non-manager error before the commit. The only flush failure (`{"title": null}` → `IntegrityError`) sits in xfail cards U-30 / U-31 (BUG-1575), which the mutation run excludes. TC4 / TC5 cards don't count: `_commit_transaction` rolls back by itself, and after a commit there is nothing to undo. | Hand variants `except Exception:` → `except (LookupError, PermissionError, ValueError):` in `update_ticket` and in `update_platform_ticket`: 115 passed, 39 xfailed (both survive). The same narrowing in `create_ticket` is killed by C-02. | **case designer**: one card per update method, written like C-02. Creator `title=None` through `HelpTicketUpdate.model_construct(title=None)`, so the schema is skipped and the card still passes after BUG-1575's fix. Expect `IntegrityError`, then x_gone with no test-level rollback, nothing written, `SELECT 1` works. |
| 3 | stale bookkeeping | cases file "Reviewer summary" ("Needs a decision: … Gaps 3–5") and "Spec gaps" rows 3–5 | Spec Gap log G1–G3 (2026-11-26) answers gaps 3, 4 and 5, but the cases file still shows them open. Rows 3 and 5 need no new card: U-43 follows G1, and the R5 cards assert type only, per G3. Row 4 needs finding 1's card. | `help_ticket_service.cases.md` lines 25 and 2622–2629 vs spec lines 385–388 | **case designer**: mark gaps 3–5 closed by G1–G3 in the next revision, together with findings 1 and 2. |

No fidelity findings. These cards were checked line by line against their tests: C-01, C-11, G-01, G-17 …
G-19, L-08, L-17 … L-23, U-01, U-03 … U-06, U-09 … U-11, U-22, U-33 … U-59, V-01 … V-22, P-02, P-09 … P-14,
Q-05, Q-06. U-07, U-12, U-14, U-25 and C-02 were spot-checked. In particular:
- **TC3 `session: X not in db`:** U-35, U-48, V-05 and V-08 assert `x not in db` as the first statement after the `pytest.raises` block. V-12 asserts it as Then 2, in its card's order. None of them has a `db.rollback()` before it.
- **Refusal spy:** U-35, U-48, V-05 and V-08 nest `pytest.raises(<Type>)` around `rollback_spy(db)` around the When, with no savepoint, as the Conventions say.
- **Error checks:** U-59 and V-13 use `pytest.raises(Exception)` only because their cards say so, and Then 2 narrows it with `isinstance(…, (HelpTicketForbiddenError, HelpTicketInvalidTransitionError))`. That is not a swallowed failure.
- **Patches:** no extra mocks. The only patches are the Conventions' clock and close clock, the spies, the refusal spy, the failing commit and the failing refresh.
- **U-11 and V-22:** both run on the real clock after `SET LOCAL TIME ZONE 'America/New_York'`.

### Surviving mutants
| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 18 | 48 | `refreshed or ticket` → `refreshed and ticket` (`create_ticket`) | equivalent | Spec revision 2026-11-04: on every reachable path the re-read returns the same identity-mapped instance, and the `None` side is not unit-testable | — |
| 19 | 123 | same (`update_ticket`) | equivalent | same | — |
| 20 | 150 | same (`update_platform_ticket`) | equivalent | same (spec extends the decision to L150, 2026-11-26) | — |
| 24 | 118 | `getattr(user, "is_platform_admin", False)` → default `True` | case-missing | Spec G2 has the rule, but no card passes a user without the attribute (finding 1) | **case designer** |

#### Hand variants (scratch plugin `hts_hand.py`, re-execs the service module with one method's text changed)
| Variant | `create_ticket` | `update_ticket` | `update_platform_ticket` |
|---|---|---|---|
| reference (no change) | 115 passed, 39 xfailed | — | — |
| `self._rollback_transaction(db)` → `pass` | caught (C-02: `PendingRollbackError`) | caught (U-12 `x_gone`) | caught (V-05 `x not in db` / spy) |
| `except Exception` → `except PermissionError` | caught (C-02) | caught (U-12) | caught (V-05) |
| `except Exception` → `except (LookupError, PermissionError, ValueError)` | caught (C-02) | **survives**: finding 2 | **survives**: finding 2 |
| `is_platform_admin=getattr(…)` → `True` | — | caught (U-35 …, and the BUG-3251 xfails XPASS) | — |
| `db.refresh(ticket)` → `pass` | caught (C-04) | caught (U-34) | caught (V-19) |
| `to_response(refreshed or ticket)` → `to_response(ticket)` | survives: equivalent | survives: equivalent | survives: equivalent |

The last row is equivalent at this layer. `refreshed` is the same identity-mapped instance as `ticket`, and
the creator relationship lazy-loads on either. This is the same reason the spec gives for mutants #18–#20.

### Traceability
cases 154 · tests 154 · unmatched: none · duplicates: none · marker mismatches: none (AST script
`trace.py`). 115 `pass` cards have no xfail marker. 38 strict xfails: BUG-1441 ×1, BUG-1443 ×1, BUG-1574 ×9,
BUG-1575 ×2, BUG-1577 ×2, BUG-1578 ×1, BUG-1863 ×10, BUG-3251 ×8, BUG-3270 ×4. L-16 is `strict=False` for
BUG-1442, as its card says. Every reason string names its card's BUG ID, and every ID exists in
`docs/testing/bugs.md`. No test cites BUG-1576 (resolved).

### Commands run
```
.venv/Scripts/python.exe -m pytest tests/unit/services/test_help_ticket_service.py -q -p no:cacheprovider --cov=app.services.help_ticket_service --cov-branch --cov-report=term-missing
  app\services\help_ticket_service.py   57 stmts  0 miss  2 branch  0 partial  100%
  115 passed, 39 xfailed, 17 warnings
  repeat runs (no coverage): 115 passed, 39 xfailed ×2 — stable (L-16 xfailed each time)

.venv/Scripts/python.exe -m pytest tests/unit/services/test_help_ticket_service.py -q -p no:cacheprovider --runxfail -rf --tb=line
  39 failed, 115 passed. Each on its card's line: C-05 'HELP-2027-001'; C-06 '  Printer  '; C-07, C-08, U-27, U-28,
  U-30, U-31 DID NOT RAISE ValidationError; C-09 / U-29 '   ' is None; L-12 set(); L-16 physical order;
  U-11 / V-22 timedelta(seconds=18000, …); U-16 … U-21, U-23 … U-25, U-58, V-11, V-12, V-14, V-15 DID NOT RAISE
  HelpTicketForbiddenError; U-26 / V-21 '  Toner low  '; U-04, U-05, U-38 … U-43 HelpTicketStatusChangeForbiddenError
  "Only platform admins may change ticket status." from the When call (U-42: escapes pytest.raises(HelpTicketInvalidTransitionError));
  P-05 {T1, T2} == {T1}

.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/services/help_ticket_service.py tests/unit/services/test_help_ticket_service.py --json C:\Users\User\AppData\Local\Temp\makorsh-pipeline\help_ticket_service\mutants.json
  Mutants: 24 · killed 20 · timeout 0 · survived 4 · score 83% (raw)
  SURVIVED #18 L48:44 Or -> And · #19 L123:44 Or -> And · #20 L150:44 Or -> And · #24 L118:69 const False -> True

HTS_VARIANT=<kind:method> PYTHONPATH=C:\Users\User\AppData\Local\Temp\makorsh-pipeline\help_ticket_service\plug .venv/Scripts/python.exe -m pytest tests/unit/services/test_help_ticket_service.py -q -p no:cacheprovider -p hts_hand -x
  (results in the hand-variant table above)
```

---

## Earlier rounds (2026-11-04, source e48a092, cases revisions 1–2)

> **Round 2 verdict (2026-11-04):** PASS — 62 passed · 26 xfailed · 100% branch · mutation 12/12 killed (after excluding 2 equivalent: L48, L119, per spec revision)
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
