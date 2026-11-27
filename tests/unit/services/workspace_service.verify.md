# Verification — `app/services/workspace_service.py`

> **Verdict:** PASS (round 2, 2026-11-06; round 1: NEEDS WORK)
> Round 2: 134 passed · 68 xfailed (reproduced ✅, 3 plain runs identical) · coverage 99% branch (same 2 unreachable) · cases revision 5
> Round 1 — Tests: 133 passed · 66 xfailed (reproduced ✅) · coverage 99% branch (83->79, 116 missing; both unreachable, confirmed)
> Mutation: 86 mutants · 80 killed · 6 survived → score 100% (after excluding 2 equivalent, 0 dead, 4 bug-path)
> Source commit: e48a092 · Cases revision: 4

## Summary
The tests are faithful: every card has its test, every Then line is asserted exactly, every strict xfail fails on its card's "Fails today on" line, and three plain runs gave the same 133 / 66. mutate.py leaves only unreachable or BUG-2250 code alive. The hand variants for what the service adds over its manager were caught: owner check too loose, too strict, or after a write; swapped 404/403/400; missing rollbacks; stray commits or rollbacks on reads; audit rows on no change. Two variants survive because of a card gap: `list_invitations` and `get_my_invitations` can pair every invitation with the wrong inviter. No passing card has two different non-null inviters. Fix by: case designer. The executor's claim about the coverage gaps holds.

## Findings
| # | Kind | Case / line | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing | `list_invitations` R3 (L268–276); cards WSS-LI-01…05 | Nothing checks that each invitation is paired with its own inviter. In W1 every passing card's non-null inviter is UO (the `invitation` default); the only card with several inviters is LI-06, a strict xfail BUG-2252. | Hand variant `li_inviter_of_first` (each row gets `invitations[0]`'s inviter): SURVIVED, 133 passed. | case designer: one passing card with two W1 invitations from different inviters (e.g. UO and an owner-role UA) and one with `None`, asserting the `{inv.id: inviter.id}` map. |
| 2 | case-missing | `get_my_invitations` R2 (L347–355); card WSS-MI-01 | Same gap. MI-01 has one non-null inviter (UO) and one `None`, so "the first invitation's inviter for every row" gives the same map. MI-06, which has five inviters, is a strict xfail. | Hand variant `mi_inviter_of_first`: SURVIVED. | case designer: give MI-01's I2 (or a third invitation) a different non-null inviter, e.g. U2 for the W2 invitation, and keep one `None`. |
| 3 | spec note (no test change) | `remove_member` R5, `cancel_invitation`, `update_member_role` R5; TC3 | The `except Exception: rollback` of these three methods cannot be observed without a patch. The commit failure cards (RM-19, XI-15, MR-21, MR-23) are already rolled back inside `_commit_transaction`. Nothing in the `try` before the commit can raise a non-`ValueError` on a patch-free path (the manager writes only plain rows; `member.role = …` cannot raise). | Hand variants `rm_no_rollback_other`, `xi_no_rollback_other`, `mr_no_rollback`: SURVIVED. Classed equivalent below. | describer (fill-gaps): record this TC3 path as unit-untestable without a manager patch. Otherwise allow a manager patch under "Race simulations" so the case designer can add one card per method. |
| 4 | question for the describer | `update_member_role` R4; API | The owner's own `position` can never be changed after creation. R4 refuses any change to an `owner` row, and no other endpoint writes `position` (grep of `app/api/v1/endpoints`). The owner's position is shown on every order's approver list. | Read, not run. | describer: decide whether this is intended, or a bug (e.g. allow a position-only change of the owner's own row). Decide under the delegation; it is not a money or order-workflow question. |

## Surviving mutants
| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 27 | 116 | `raise NotFoundError` → `pass` | equivalent | Unreachable. Line 113 already needs a membership row of this workspace, and `workspace_members.workspace_id` is `ON DELETE CASCADE`, so the workspace exists (spec `get_workspace_with_plan` R3; card G-03). | — |
| 77 | 116 | `'Workspace not found'` → `''` | equivalent | Same unreachable line. | — |
| 29 | 130 | `raise NotFoundError` → `pass` (update_workspace) | bug-path | Today's 404 for a missing workspace is the behaviour BUG-2250 removes. Only U-13 and U-14 (strict xfail) reach it. | — |
| 78 | 130 | message → `''` | bug-path | Same. | — |
| 36 | 175 | `raise NotFoundError` → `pass` (update_member_role) | bug-path | BUG-2250. Only MR-13 (strict xfail) reaches it. | — |
| 80 | 175 | message → `''` | bug-path | Same. | — |

### Coverage gaps (executor's claim checked)
- **83->79** (`list_user_workspaces`, a membership whose workspace is missing): unreachable. `WorkspaceDAO.get` is the plain base `get`, with no soft-delete or status filter. The member FK cascades on workspace delete, and `get_by_user` reads from the database after autoflush, so a member row without its workspace cannot be seen. Only patching the DAO would reach it, which the spec does not allow. Agreed.
- **116**: unreachable, as for mutant #27 above. Agreed.

## Hand variants
Each variant was applied to a private copy of the backend and run with the passing tests only (`-m "not xfail"`). Script: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\wpsvcv\W\hv.py` (and `hv2.py`). Killing tests are in brackets.

| Area | Variant | Result |
|---|---|---|
| owner check too loose | `_require_owner` ignores status: inactive owner passes | KILLED [RO-07] |
| | role `owner` in *any* workspace is enough | KILLED [RO-05, RO-06, SI-04] |
| | `owner_user_id` only, instead of the stored role | KILLED [RO-01…05 + 6 more] |
| | `update_workspace` uses the stored role `owner` instead of `owner_user_id` | KILLED [U-12] |
| | membership check ignores status / ignores workspace | KILLED [AM-06…11 / AM-02…06 + 11] |
| owner check too strict | role `owner` **and** `owner_user_id` | KILLED [RO-01, SI-02] |
| check after a write | `send_invitation` checks the owner after the commit | KILLED [SI-03, SI-04, SI-05] |
| | `update_workspace` checks the owner after the commit | KILLED [U-11, U-12] |
| | `update_member_role` checks the owner after the flush | KILLED [MR-12, MR-30] |
| | `accept_invitation` checks the workspace after the commit | KILLED [AI-04, AI-05 …] |
| "owner" role (BUG-2257) | refuse any spelling (`.lower() == 'owner'`) | KILLED [MR-29] |
| | owner-role refusal before the R2 owner check | KILLED [MR-30] |
| error mapping 404/403/400 | membership 403 → 404 | KILLED [AM-02 … 21 tests] |
| | non-owner 403 → 404 (update, role change) | KILLED [U-11, U-12 / MR-12, MR-30] |
| | "Member not found" 404 → 403; owner target 403 → 400 | KILLED [MR-07…09 / MR-11] |
| | remove `ValueError` → 404 for all; cancel → 400 for all | KILLED [RM-06…09 / XI-04, XI-05] |
| | send / create / accept `ValueError` 400 → 403 or 404 | KILLED [SI-06…08 / C-03…05 / AI-06…10] |
| | wrong-workspace accept 400 → 403 | KILLED [AI-04, AI-05] |
| missing rollback (TC3) | `ValueError` path of remove, cancel, send, create, accept; API-error path of accept; `update_workspace`; other-error path of create | all KILLED |
| | other-error path of remove / cancel; `update_member_role` | SURVIVED: see Finding 3 (equivalent: the path cannot be reached without a patch) |
| stray commit / rollback on reads (TC6) | commit in list_user_workspaces, list_members, get_my_invitations; rollback in get_workspace_with_plan, list_invitations, the membership helper | all KILLED [LW-06, LM-06, MI-05, G-05, LI-05, AM-*] |
| | re-read after remove / cancel (TX3) | KILLED [RM-03 / XI-02] |
| audit on no change | `workspace_updated` / `member_role_changed` written on every call | KILLED [U-23 / MR-19] |
| filters | `include_inactive` ignored; `include_expired` ignored | KILLED [LM-01, LM-03 / LI-02] |
| caller's role | `remover_role` / `canceller_role` forced to `owner` | KILLED [RM-06, RM-07, RM-09 / XI-04, XI-05] |
| position override | accept ignores `position` | KILLED [AI-02, AI-03] |
| pairing | inviter of the first invitation for every row (`get_my_invitations`, `list_invitations`) | **SURVIVED**: Findings 1, 2 |
| filtering after paging | — | not applicable: no list here is paged (spec HR-5, HR-6 checked, D7) |

## Traceability
cards 199 · tests 199 · unmatched: none · marker mismatches: none. Each of the 66 cards marked `xfail BUG-n` has `xfail(strict=True)` with a reason naming that bug. Every BUG ID exists in `bugs.md`. Script: `wpsvcv\W\trace.py`. The RM … MI half was also read by a second reader; no findings.

Fidelity: every card read against its test, AM … MR here and RM … MI by the second reader, together with the shared helpers (`snap`, `counts`, `audit`, `recorder`, `spies`, `failing_commit`, …). No missing, weakened or changed assertion. The setups are as written. Every `committed:` line comes after `db.rollback()`. There is no `try/except` or broad `raises`. The only mocks are the Conventions' `utcnow` patches and the commit / rollback / refresh wraps.

## Commands run
```
COVERAGE_FILE=…\W\.cov1 .venv/Scripts/python.exe -m pytest tests/unit/services/test_workspace_service.py -q -p no:cacheprovider -o addopts= --cov=app.services.workspace_service --cov-branch --cov-report=term-missing
  app\services\workspace_service.py  170  1  34  2  99%  83->79, 116
  133 passed, 66 xfailed, 15 warnings in 38.90s
COVERAGE_FILE=…\W\.cov2 .venv/Scripts/python.exe -m pytest tests/unit/services/test_workspace_service.py -q -p no:cacheprovider -o addopts= --runxfail -rf
  66 failed, 133 passed in 18.06s   (the 66 strict xfails; each on its card's Then line, mapped with W\thenmap.py)
plain runs 2 and 3: 133 passed, 66 xfailed (18.33s, 18.42s); no flaky test
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/services/workspace_service.py tests/unit/services/test_workspace_service.py --json …\wpsvcv\mut_workspace_service.json
  Mutants: 86 · killed 80 · timeout 0 · survived 6 · score 93%
.venv/Scripts/python.exe …\W\hv.py ; …\W\hv2.py   (52 hand variants, table above)
```
Scratch: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\wpsvcv\W\`.

## Round 2 — 2026-11-06
**Current verdict:** PASS. Both round-1 card gaps are closed, the three new cards are faithful, the runs reproduce the notes, and no survivor is left except equivalent / bug-path ones or a path the spec now declares not unit-testable (TX1a).

### What changed
- Cases revision 5 (spec TX1a, R4a / BUG-2258, G7–G9). Notes revision 5. Source unchanged (e48a092).
- Changed tests: WSS-LI-01 … LI-05 (each W1 invitation has its own inviter: UO, UA, UB, `None`; the `{invitation id: inviter id}` map is asserted) and WSS-MI-01 (new I5 in W0 without an inviter, I2 invited by U2; three invitations and the `(workspace, inviter)` map).
- New tests: WSS-MR-31 (strict xfail BUG-2258), MR-32 (pass), MR-33 (strict xfail BUG-2258, `Author: claude`).

### Traceability and fidelity
- Cards 202 · tests 202 · unmatched none · marker mismatches none (`W\trace.py`). 68 xfail cards, all strict, all with the reason their Expect names.
- I read every changed and new test against its card: each Given row (inviter columns included), each Then line with exact `==` maps, `committed:` after `db.rollback()`, and snapshots at the commit point (MR-32). No findings.
- Informational, no action needed: MR-31's Then 3–4 also need BUG-2253, and its Expect names only BUG-2258. That is harmless. The test stays a strict xfail until both bugs are fixed, then XPASSes and fails loudly. If the case designer touches the card again, it could list both bugs on the Expect line.

### Runs
```
plain ×3 (private COVERAGE_FILE, W\r2\): 134 passed, 68 xfailed (12.46s, 18.71s, 18.70s)
--cov branch: app\services\workspace_service.py 170 1 34 2 99% 83->79, 116 — 134 passed, 68 xfailed
--runxfail -rf: 68 failed, 134 passed
  MR-31: Then 1, the call raises PermissionDeniedError "Cannot change workspace owner's role" (as the card says)
  MR-33: Then 1, the call raises IntegrityError NotNullViolation on role (the card's "raises at the commit"; spec G9)
  the other 66 as in round 1
```

### Round-1 survivors re-run (hand variants, passing tests only, refreshed copy of the tests)
| Variant | Round 1 | Round 2 |
|---|---|---|
| `li_inviter_of_first` | SURVIVED | **KILLED**: 3 failed (LI-01/02/03/05 map lines; first failures LI-02, LI-03, LI-05 depending on row order) |
| `mi_inviter_of_first` | SURVIVED | **KILLED**: WSS-MI-01 Then 2 |
| `rm_no_rollback_other`, `xi_no_rollback_other`, `mr_no_rollback` | SURVIVED | still survive. Out of scope by spec TX1a (not unit-testable without patching the manager; G7). Classed equivalent for unit testing; nothing routed. |

No `mutate.py` re-run: the round-1 survivors were equivalent (line 116) or bug-path (BUG-2250, lines 130 / 175), and the source is unchanged.

Routed: nothing.
