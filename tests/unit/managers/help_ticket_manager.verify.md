# Verification — `app/managers/help_ticket_manager.py`

## Round 2 (2026-11-26)

> **Verdict:** PASS
> Tests: 165 passed · 29 xfailed (reproduced ✅, all strict) · coverage 100% branch (85 statements, 24 branches)
> Mutation: unchanged source, so the previous round's run stands: 79 mutants · 78 killed · 1 survived (bug-path #64) → score 100% after exclusions. Hand variant H14 re-run: **killed** (by U-64).
> Source commit: 41d5ac1 · Cases revision: 2 (with gap fill R-07 / R-08 and the verifier-round card U-64)

### Summary
A narrow round for the one finding of the previous round. The case designer added HTM-U-64 (an opened ticket that still carries stamps is closed by a platform admin), and the executor implemented it. The test reproduces the card exactly, and it now catches H14 (`ticket.closed_by or user_id`), which survived before. Nothing else changed: same source, the other 193 tests as verified in the previous round. No open findings.

### Findings
None. Previous Finding 1 (case-missing, `update_ticket` R5b) is **resolved** by HTM-U-64.

### Surviving mutants
| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 64 | 174 | `"Only platform admins may change ticket status."` → `""` | bug-path | As in the previous round: only U-51 (strict xfail, BUG-3251) checks the message. | — |

Hand variant H14 (`update_data["closed_by"] = ticket.closed_by or user_id`), re-run from `…\help_ticket_manager\variants_h14.py` on a temp copy: **1 failed, 164 passed**. The failure is `u_64`, on its Then 3 `closed_by == ADM.id`. H15 stays equivalent.

### Traceability
cases 194 · tests 194 (`# [claude] HTM-U-64` at line 3844, in card order after U-63) · unmatched: none · marker mismatches: none. Counts 165 pass / 29 xfail match the cases header and the notes' Result line. The xfail set is unchanged. U-64 is `Expect: pass` and has no marker.

**Fidelity of U-64:**
- **Given:** `mk_opened("HELP-2026-001", closed_at=PAST, closed_by=mgr.id)`, an opened ticket with both stale stamps, as the card says.
- **When:** the exact call (`status=CLOSED`, `user_id=adm.id`, `is_platform_admin=True`), inside the close clock.
- **Then 1:** `result is t`.
- **Then 2–4:** each is a separate re-read, asserting `status == "closed"`, `closed_by == adm.id` and `closed_at == CLOSE_AT` with exact `==`, in the card's order.
- Nothing extra is mocked and no failure is swallowed.

### Commands run
```
.venv/Scripts/python.exe …\help_ticket_manager\trace.py <cases> <tests> docs/testing/bugs.md
  cards 194 · tests 194 · pass 165 / xfail 29 · no mismatch lines
COVERAGE_FILE=…\.cov2 .venv/Scripts/python.exe -m pytest tests/unit/managers/test_help_ticket_manager.py -q -p no:cacheprovider --cov=app.managers.help_ticket_manager --cov-branch --cov-report=term-missing
  app\managers\help_ticket_manager.py  85  0  24  0  100%
  165 passed, 29 xfailed, 21 warnings in 20.86s
.venv/Scripts/python.exe -m pytest tests/unit/managers/test_help_ticket_manager.py -q -p no:cacheprovider --runxfail -rf --tb=no
  29 failed, 165 passed — the failures are exactly AC-20/21/22, G-22, L-14/15/27/28/30, U-17, U-18…22, U-25…28, U-51…60
2 more plain runs: 165 passed, 29 xfailed each (no flaky test)
.venv/Scripts/python.exe -I …\help_ticket_manager\variants_h14.py
  V14 stamp on close keeps old closed_by if set: 1 failed, 164 passed, 29 deselected | failed: ['u_64']
```

---

## Round (2026-11-26)

> **Verdict:** NEEDS WORK
> Tests: 164 passed · 29 xfailed (reproduced ✅, all strict, each fails on its card's "Fails today on" line) · coverage 100% branch (85 statements, 24 branches)
> Mutation: 79 mutants · 78 killed · 1 survived → score 100% (after excluding 0 equivalent, 0 dead, 1 bug-path). Hand variants: 21, of which 1 is a `case-missing` survivor (H14) and 1 is equivalent (H15)
> Source commit: 41d5ac1 · Cases revision: 2 (with gap fill R-07 / R-08)

### Summary
These tests can be trusted, with one small gap. All 193 cards are implemented once each, with the right markers, and every Then line I read is asserted as written. `--runxfail` fails exactly the 29 xfail cards, each on the line its card names. `mutate.py` killed 78 of 79 mutants. The survivor is today's BUG-3251 refusal message, which only the xfail card U-51 checks (bug-path). I also wrote 21 hand variants aimed at the transition table, the stamps and the BUG-3251 fix. The passing tests caught every widened table entry, every misplaced stamp, a refusal moved after the check or the write, and a status read from the database instead of the session. Under `--runxfail`, the BUG-3251 cards accepted a correct fix (only U-53 still fails, because it also needs BUG-1863). They caught four wrong fixes: no workspace-owner grant, any role grants, owning any workspace grants, and the old message kept. Making `role` required would break 61 of today's passing cards, so the gap-3 default is pinned too.
One gap: no card closes an opened ticket that still has `closed_at` / `closed_by` set. R5d makes that state reachable, because `pending → opened` keeps stamps that were set directly (U-34). So a close that keeps an earlier `closed_by` (H14) passes every test. One new card from the case designer fixes this. Nothing else has to change.

### Findings
| # | Kind | Case / line | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing | `update_ticket` R5b (with R5d); source lines 193–195 | R5b says `opened → closed` sets `closed_by = user_id` and `closed_at = utcnow()`. Every close card (U-06, U-13, U-32, U-43, U-54) starts from an opened ticket with empty stamps. None checks that stale stamps are overwritten. R5d (U-34) makes such a ticket reachable: a pending row with stamps, then opened. | Hand variant H14 `update_data["closed_by"] = ticket.closed_by or user_id`: 164 passed, 0 failed. | **case designer**: add a card. T = opened ticket, but `closed_at PAST`, `closed_by MGR.id`. A platform admin closes it. Re-read: `closed_by == ADM.id`, `closed_at == CLOSE_AT`. |

### Surviving mutants
| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 64 | 174 | `"Only platform admins may change ticket status."` → `""` | bug-path | Today's text is the BUG-3251 message (R5h). By the spec's Notes, R5 cards assert the type only. Only U-51 (strict xfail, excluded from the run) checks the message, and it checks the intended text. Resolves when BUG-3251 is fixed. | — |

#### Hand variants (verifier's own; `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\help_ticket_manager\variants.py`, run on a temp copy)
| # | Variant | Run | Result | Caught by |
|---|---|---|---|---|
| H01 | table: `pending → closed` allowed | pass tests | killed | U-35, U-39, U-63 |
| H02 | table: `closed → pending` allowed | pass | killed | U-37, U-63 |
| H03 | table: `opened → opened` allowed | pass | killed | U-15, U-63 |
| H04 | table: `closed → closed` allowed (HR-9) | pass | killed | U-16, U-63 |
| H05 | table: `opened → pending` allowed | pass | killed | U-36, U-63 |
| H06 | stamps cleared on every move to `opened` (pending too) | pass | killed | U-34 |
| H07 | `closed_by` = the creator | pass | killed | U-06, U-13, U-43 |
| H08 | no `closed_at` on close | pass | killed | U-06, U-13, U-32, U-43 |
| H09 | reopen clears `closed_at` only | pass | killed | U-08, U-14 |
| H10 | current status read from the database, not the session | pass | killed | U-43 |
| H11 | bad requested value raised as `HelpTicketInvalidTransitionError` | pass | killed | U-11, U-12, U-44 |
| H12 | transition checked before the status right | pass | killed | U-42, U-45, U-47 |
| H13 | text written (`setattr`) before the status refusal | pass | killed | U-23, U-24, U-39, U-49 |
| H14 | close keeps an existing `closed_by` (`ticket.closed_by or user_id`) | pass | **survived** | none → Finding 1 |
| H15 | `.get(current, set())` default → every status | pass | survived, equivalent | The default is unreachable: every enum value is a key, and a stored value outside the enum raises before line 187 (R5e). |
| F1 | BUG-3251 correct fix (`role: str \| None = None`; admin, role owner / ground-team-manager, or `ticket.workspace.owner_user_id == user_id`; new message) | `--runxfail` all | 3251 cards: only U-53 fails (needs BUG-1863 too). The other 20 failures are the other bugs' xfails, as before. 0 passing card broken | — (the fix is accepted) |
| F2 | fix without the workspace-owner grant | `--runxfail` | killed | U-56 |
| F3 | fix: any non-null role grants | `--runxfail` | killed | U-58, U-59, U-60 |
| F4 | fix: owning any workspace grants | `--runxfail` | killed | U-59, U-60 |
| F5 | fix with `role` required (no default) | `--runxfail` | killed | 61 passing cards fail with `TypeError` (gap 3 pinned) |
| F6 | fix, old message kept | `--runxfail` | killed | U-51 |

### Traceability
cases 193 · tests 193 (one `def` per card, `# [claude] <ID>` on each, card order kept) · unmatched: none · marker mismatches: none. 29 Expect-xfail cards → `xfail(strict=True)` with every listed bug in the reason. That is BUG-2103 4, BUG-1578 2, BUG-3250 3, BUG-1577 1, BUG-1863 10 and BUG-3251 9. U-53's reason names BUG-3251 and BUG-1863, as its Expect line does. 164 pass cards have no marker. All six bug IDs are rows in `docs/testing/bugs.md`. Checked with my AST script (`…\help_ticket_manager\trace.py`).

**Fidelity:** I read every new and revised card against its test: AC-18, AC-20 … 25, G-22, L-07 … 09, L-20 … 30, P-02, P-04, P-12 … 14, C-01, C-02, C-07, U-01, U-06 … U-17, U-23, U-24, U-26, U-31 … U-63, R-01, R-04 … R-08 and I-01. I also sampled unchanged cards: AC-16, AC-17, G-18 … G-21, L-01, L-02, L-06, L-14 … L-19, P-03, Q-05, C-03 … C-06, U-02 … U-05, U-18 … U-22, U-25, U-27 … U-30 and I-02 … I-05. I found:
- no missing, weakened or changed assertion;
- no wrong setup (the `set_owner` order follows each card, e.g. L-29, U-59 and U-60 set the owner before T);
- no write checked only in memory, and no swallowed failure.
`session:` and `pending:` lines run before any re-read, and `snap` reads with a Core `select`, so nothing is expired early. Only the Conventions' patches are used: the clock, the close clock, and the `wraps=` commit / rollback spies. Nothing else is mocked.

The BUG-3251 TypeError rule is honest:
- U-53 and U-57 … U-60 raise `TypeError` inside the Then 1 `pytest.raises`.
- U-54 … U-56 raise `TypeError` at the call, before Then 1. Under the notes' rule that is a failure of Then 1, which matches the cards' "Fails today on: Then 1 (the call raises TypeError …)".
- F1 shows the same cards pass once the parameter exists.

### Commands run
```
COVERAGE_FILE=…\help_ticket_manager\.cov .venv/Scripts/python.exe -m pytest tests/unit/managers/test_help_ticket_manager.py -q -p no:cacheprovider --cov=app.managers.help_ticket_manager --cov-branch --cov-report=term-missing
  app\managers\help_ticket_manager.py  85  0  24  0  100%
  164 passed, 29 xfailed, 21 warnings in 19.82s
.venv/Scripts/python.exe -m pytest tests/unit/managers/test_help_ticket_manager.py -q -p no:cacheprovider --runxfail -rf --tb=line
  29 failed, 164 passed — exactly the 29 xfail cards. AC-20/21/22 `assert False is True`; G-22 HelpTicketForbiddenError at the call;
  L-14/15/27/28/30 idset mismatch; U-17 time-zone delta; U-18…22, 25…28, 52 "DID NOT RAISE HelpTicketForbiddenError";
  U-51 'Only platfor…' == 'You may not …'; U-53…60 TypeError: unexpected keyword argument 'role'
2 more plain runs: 164 passed, 29 xfailed each (no flaky test)
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/managers/help_ticket_manager.py tests/unit/managers/test_help_ticket_manager.py --json C:/Users/User/AppData/Local/Temp/makorsh-pipeline/help_ticket_manager/mutants.json
  Mutants: 79 · killed 78 · timeout 0 · survived 1 · score 99% (raw)
  SURVIVED #64 L174:20 const: 'Only platform admins' -> ''
.venv/Scripts/python.exe -I …\help_ticket_manager\variants.py   (table above)
```

### For the coming features
- **Permissions:** BUG-3251's fix must add `role: str | None = None` as a keyword-only parameter (F5 shows that a required `role` breaks 61 cards). The workspace-owner grant must read the ticket's own workspace (F4). Keep the order: status right, then the transition, then the write (H12, H13).
- **Notifications:** every allowed move is a real transition, because same-status requests are refused (H03, H04). A hook after the status branch never fires on a no-op.

---

## Round 1 (e48a092)

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
