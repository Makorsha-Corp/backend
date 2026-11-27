# Verification: `app/managers/attachment_markup_manager.py`

> **Verdict:** NEEDS WORK
> **Current verdict (Round 2):** PASS (cases Revision 4; see "Round 2 — 2026-11-04" at the end)
> Tests: 94 passed · 99 xfailed (reproduced ✅; 1 non-strict XPASS in 2 of 9 runs, as the card allows) · coverage 100% branch (93 stmts, 26 branches)
> Mutation: 73 mutants · 72 killed · 1 survived → score 98.6% (after excluding 0 equivalent, 0 dead, 0 bug-path)
> Hand variants: 41 · 38 killed · 3 survived
> Source commit: e48a092 · Cases revision: 3

## Summary
The tests can be trusted for what the cards ask. All 193 cards are implemented faithfully: every Then line is asserted with the card's exact value and in the card's order, nothing is mocked beyond the one race simulation, and every strict xfail fails on the line its card names. Mutation testing kills 72 of 73 mutants.

The verifier's hand variants used its own reference of the intended BUG-2115 / 2116 / 2117 fix and then added one defect each. They found three holes in the **cards**, not in the tests:
- A platform admin is let into a private project's attachment.
- A link to another workspace's help ticket is honoured.
- The caller's own-layer lookup in `put_own_layer` / `delete_own_layer` is not limited to the caller's workspace.

None of the three would be caught today or after the fix. Each one goes to the case designer. The one surviving mutant needs one sentence in the spec, so it goes to the describer. No new bug was found in `app/`.

## Findings
| # | Kind | Case / line | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing | `_get_ready_attachment` R5 / PR-2 ("platform admin for tickets only") | No card has a platform admin without a privileged role, or project membership, opening a **private project's** attachment. The reference variant that lets admins into private projects passes every card. GR-38 covers the admin only on a ticket. | Variant R5_admin_private_project: 185 passed, 0 failed (`--runxfail`, reference installed) | case designer: add GR card "admin(UG); P private; link(A2, project, P) → NF(A2)" (strict xfail BUG-2115), and one public-method card |
| 2 | case-missing | `_get_ready_attachment` R5 / PR-1 (other workspace's record), help-ticket type | The cards cover W0/W2 projects (GR-30/31) and machines (GR-48/49) but no **W2 help ticket**. A fix that loads the ticket by id without its workspace, then grants by role, passes every card. | Variant R13_ticket_unscoped: 185 passed, 0 failed | case designer: add GR card "T9 = ticket in W2; link(A2, support_ticket, T9.id); caller U2 (owner role) → NF(A2)" |
| 3 | case-missing | `put_own_layer` R5 / `delete_own_layer` R4, HR-16 (spec Review: "markup rows … written with the caller's workspace") | No card has the caller holding a markup row filed under **another workspace** on the same attachment. A manager that drops `workspace_id` from `get_for_user` / `delete_for_user` passes. LL-02 / LV-02 cover this for the two lists only. | Variant B4_own_layer_unscoped: 94 passed, 0 failed (`-m "not xfail"`) | case designer: add DL card "W2-filed AttachmentMarkup(A1, U1) → delete_own_layer(U1) leaves it, no event" and PL card "same row → put_own_layer(U1, P1) logs `markup_saved` and leaves the W2 row" |
| 4 | spec-gap | line 453 `description.replace("Updated marks", "Saved marks", 1)` | Mutant `1 -> 2` survives. The spec (`put_own_layer` R3) says "Updated marks" is replaced by "Saved marks" but not whether only the leading phrase changes. Page keys are free strings (D9), so a page named "Updated marks" makes the difference visible. | mutant #61 SURVIVED | describer (fill-gaps): state that only the leading phrase is replaced; then the case designer adds one PL card |
| 5 | note (no fix needed) | test file docstring line 3 | It says "revision 2". The cases file is at revision 3. The notes record that revision 3 changed no test code. | header | executor (optional, cosmetic) |

**LL-05 / LV-04 ruling (non-strict xfail, chance XPASS): allowed. Not a finding.**
- Both cards' Expect line says `xfail BUG-1435 (non-strict)` / `xfail BUG-1436 (non-strict)`, and the marker matches (`X1435` / `X1436`, `strict=False`).
- The cases' Reviewer summary gives the reason: the tie order depends on where Postgres places the row on disk. The strict `ORDER BY` alarms already exist in `tests/unit/dao/test_attachment_markup.py:378` and `test_attachment_markup_event.py:349` (both `strict=True`). The notes record the chance XPASS.
- Reproduced: LL-05 XPASSed in 2 of 9 runs. The first was the coverage run, made while the mutation run shared the database. LV-04 never XPASSed.
- The test always fails on its named Then line when it fails, and a non-strict XPASS never turns the suite red. So this is the nondeterminism the card declares, not a hidden flake.
- Until BUG-1435 / 1436 are fixed these two tests can never fail, so they have no alarm value. The DAO tests carry that alarm.

## Surviving mutants
| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 61 | 453 | const `1 -> 2` (replace count) | spec-gap | It differs only when a page key itself contains "Updated marks". That can be reached (any string is a page key), but no spec rule says which occurrence is replaced. | describer |

## Hand variants
Base variants (`B…`) patch today's code with one defect and run against the passing tests (`-m "not xfail"`). Reference variants (`R…`) first install the verifier's own intended BUG-2115 / 2116 / 2117 behaviour, then one defect, and run with `--runxfail`. They exclude the 8 cards of bugs the reference does not implement (LL-05, LL-12, LV-04, LV-06, LV-11, PL-23, PL-24, PL-25). With no defect, the reference (R0) passes all 185 selected tests. Plugin: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\attv\amup3\plug\vamup.py`.

| Variant | Defect | Result | Killed by |
|---|---|---|---|
| R1 | role taken from a parameter (None) instead of read | killed | GR-14, 15, 37, 45 |
| R2 | inactive / suspended membership counted | killed | GR-21, 52, 53, 55, 56, PL-29, DL-13 |
| R3 | privileged role from another workspace counted | killed | GR-19, 20, 54, 57, 58 |
| R4 | links of every workspace counted | killed | GR-59, 61, LL-13 |
| R5 | platform admin allowed on a private project | **survived** | — (finding 1) |
| R6 | workspace owner (`owner_user_id`) not granted (too strict) | killed | GR-14, 16 |
| R7 | platform admin refused a ticket (too strict) | killed | GR-38 |
| R7b | non-member refused workspace-wide types (too strict) | killed | GR-16, 62 |
| R8 | attachment with no own-workspace link allowed | killed | GR-59, 60, LL-13, PL-28 |
| R9 | visibility checked after ready / type | killed | GR-43, 44, PL-21 |
| R10 | any granting link enough (instead of all links) | killed | GR-41, 42 |
| R11 | project looked up without workspace | killed | GR-30, 31, LL-10, PL-18 |
| R12 | component's deleted project ignored | killed | GR-26, 29, DL-10 |
| R13 | help ticket looked up without workspace | **survived** | — (finding 2) |
| R14 / R15 | deleted machine accepted / machine unscoped | killed | GR-47 / GR-48, 49 |
| R16 / R16b / R16c | stamp token 31–33 chars / upper-case hex / prefix match only | killed | SS-19, 20 / SS-21 / SS-20, 23, 24 |
| R17 / R18 | another user's id accepted / environment prefix ignored | killed | SS-15, 16 / SS-25, 26, 32 |
| R19 | stored url kept | killed | SS-12, 13, 14 |
| R20 | Cloudinary URL built from the wrong `public_id` (the stored url) | killed | SS-12, 14 |
| R21 | Cloudinary `delivery_type="upload"` instead of authenticated | killed | SS-12, 13, 14 |
| R22 | `put_own_layer` skips the parent check | killed | PL-13…19, 21, 28, 29 |
| R23 | write first, refuse after the flush (put / delete) | killed | PL-13…19, 28, 29, DL-07…10, 13 |
| B1 | `get_active` without workspace | killed | GR-05, 06, PL-11, 12, DL-06 |
| B2 / B3 | layers / events listed without workspace | killed | LL-02 / LV-02 |
| B4 | own-layer lookup and delete without workspace | **survived** | — (finding 3) |
| B5 / B6 | mime case-folded / `startswith("image")` without slash | killed | IM-04, 06 / IM-06 |
| B7 / B8 / B12 / B13 | `"pdf" in fmt` / `fmt.strip()` / pdf mime case-folded / format case-sensitive | killed | IM-03 / IM-03 / IM-04 / GR-02, IM-02 |
| B9 | only `pending` refused (`failed` passes) | killed | GR-08, DL-07 |
| B10 | write first, refuse after the flush (today's checks) | killed | PL-10…14, DL-05, 07 |
| B11 | layers / events read before the check | killed | LL-06, 07 |
| B14 | non-object stamps returned | killed | SS-04, 05, 06 |
| B15 | `session_id` dropped from events | killed | LE-01, PL-01, 04, 06, DL-01 |

Not applicable here: no file size check and no Cloudinary call in today's code. The only Cloudinary use is the BUG-2117 URL builder, covered by R19–R21. This module moves no files.

## Traceability
Cases 193 · tests 193 · unmatched: none · duplicate IDs: none.
Markers: 94 pass with no marker. 97 strict xfails (`X2115` ×71, `X2116` ×17, `X2117` ×3, `X2118` ×2, `X2119` ×2, `X2120` ×1, `X1437` ×1). 2 non-strict (`X1435` LL-05, `X1436` LV-04). Every reason names the card's BUG ID, and all 9 IDs exist in `docs/testing/bugs.md`.
`# Then N` markers match the number of Then lines on every card.
`--runxfail` check (own plugin `vfail.py`): 83 xfails fail inside the card's named Then line. 16 fail on the When line with the exception the card's "Fails today on" names (15 × `TypeError … user_id` on the GR "returns" cards, 1 × `IntegrityError` 23505 on PL-25). No xfail fails on a setup or import error.
Mocks: only the PL-25 race patch (`AttachmentMarkupDAO.get_for_user`) and the `db.commit` spies of LE-02 / PL-26 / DL-12, as the cases list them. The `try/except` in PL-25 re-raises after `sp.rollback()`, so it swallows nothing.

## Commands run
```
.venv/Scripts/python.exe -m pytest tests/unit/managers/test_attachment_markup_manager.py -q -p no:cacheprovider --cov=app.managers.attachment_markup_manager --cov-branch --cov-report=term-missing
  -> app\managers\attachment_markup_manager.py  93  0  26  0  100%
  -> 94 passed, 98 xfailed, 1 xpassed (LL-05, non-strict)
.venv/Scripts/python.exe -m pytest tests/unit/managers/test_attachment_markup_manager.py -q -p no:cacheprovider --runxfail -rf
  -> 99 failed, 94 passed
6 further plain runs (-rX): 1 x "94 passed, 98 xfailed, 1 xpassed" (LL-05), 5 x "94 passed, 99 xfailed"
.venv/Scripts/python.exe -m pytest ... --runxfail -p vfail        (own fail-location plugin) -> 99 failed, 94 passed
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/managers/attachment_markup_manager.py tests/unit/managers/test_attachment_markup_manager.py --json <scratch>/mut.json
  -> Mutants: 73 · killed 72 · timeout 0 · survived 1 · score 99%  (SURVIVED #61 L453:78 const: 1 -> 2)
AMV=<variant> pytest ... -p vamup  (41 variants; reference baseline R0: 185 passed, 8 deselected)
```
Every pytest run used a private `COVERAGE_FILE` under `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\attv\amup3\`.

## Notes for coming features
- **Permissions:** the visibility rules this module needs are spread across three places: `ProjectManager.can_access_project`, `HelpTicketManager.can_access_ticket`, and PR-1 (exists, live, same workspace) in the attachment manager spec. One shared helper `can_open_parent(session, link, user_id, workspace_id)` would serve all three attachment managers. Its cases need at least the three shapes these cards missed: admin on a private project, a record of another workspace for **every** parent type, and own-workspace scoping of child rows. The verifier's reference in `vamup.py` (`link_ok` / `project_ok`) is one working shape of it.
- **Notifications:** `markup_saved` / `markup_updated` / `markup_cleared` events (with `session_id`) are the natural trigger. BUG-2118 (an unchanged save writes an event) must be fixed first, or no-op autosaves would notify. Recipients must pass the same parent check (BUG-2115), or a notification would leak marks on a private record.
- **Payments:** nothing in this module touches money.

## Round 2 — 2026-11-04

> **Verdict:** PASS
> Tests: 97 passed · 105 xfailed (103 strict, 2 non-strict; reproduced ✅) · coverage 100% branch (93 stmts, 26 branches)
> Mutation (re-run on line 453 only): 3 mutants · 3 killed · 0 survived → 100%
> Hand variants: the 3 round-1 survivors plus a new BUG-2103 variant are all killed now; the 16 round-1 visibility variants re-run against the Revision 4 reference are still killed.
> Source commit: e48a092 · Cases revision: 4

### What changed
- **Spec:** G5 (`put_own_layer` R3: only the leading "Updated marks" becomes "Saved marks"), G6 (a caller's markup row filed under another workspace is invalid data, left untouched, no event), and PR-2 now lets the workspace owner open tickets (BUG-2103).
- **Cards:** 9 added, none changed or removed: GR-64 to GR-68, LL-14, PL-30, PL-31 and DL-14.

### Traceability
- 202 cards and 202 tests, each card matched exactly once.
- Markers: 97 pass with no marker, 103 strict xfail, 2 non-strict xfail (LL-05, LV-04).
- New marker `X2103` is strict, and its reason names BUG-2103 (the only ID on the GR-68 Expect line).
- Every BUG ID used is in `bugs.md`: 1435, 1436, 1437, 2103, 2115 to 2120.
- No mismatches.

### Fidelity of the 9 new tests
None is unfaithful. Each Given is built as the card says (admin, private project or component, W2 or W0 ticket, `set_owner`, the W2-filed `layer`). Each Then line is asserted with the card's exact value, in order.
- PL-30 wraps the When in the savepoint and catches `IntegrityError` as the card prescribes. Nothing is swallowed.
- LL-14 starts `recorder` at Given 4 and asserts `markup_reads == 0`.
- With `--runxfail` (verifier plugin `vfail`), each new xfail fails where its card says:
  - GR-64 to GR-67: in Then 1, `TypeError` (no `user_id`).
  - GR-68: at the When call, `TypeError`. The card says "the call raises TypeError".
  - LL-14: in Then 1, `DID NOT RAISE AttachmentNotFoundError`.
- Overall: 105 failed (Then 1: 83, When: 17, Then 2: 5), the same pattern as Revision 3 plus the new cards.

### Round-1 survivors
| Round-1 item | Round 2 | Killed by |
|---|---|---|
| R5 `admin_private_project` (platform admin opens a private project) | killed | GR-64, GR-65, LL-14 |
| R13 `ticket_unscoped` (ticket read without its workspace) | killed | GR-66, GR-67 |
| B4 `own_layer_unscoped` (manager's own-layer lookup ignores workspace) | killed | DL-14 |
| B4b `own_layer_and_upsert_unscoped` (also the upsert lookup) | killed | PL-30, DL-14 |
| R24 `ws_owner_refused_ticket` (new: workspace owner not granted tickets, BUG-2103) | killed | GR-68 |
| Mutant #61, L453 `1 -> 2` in `replace(..., 1)` | killed | PL-31, the only test with a page key "Updated marks" |

Only DL-14 kills B4 on its own. On the put path, the half-defect finds the W2 row as `previous`, but the scoped upsert still inserts and hits the unique key. The savepoint rollback then leaves exactly today's observable state. Given the unique `(attachment_id, user_id)` key, that put half is equivalent. B4b, which makes the defect reach the write, is killed by PL-30.

Reference: verifier `vamup.py` (Revision 4: workspace owner opens tickets; the platform admin does not get private projects) → `R0` **194 passed** with `--runxfail`. The 8 deselected cards (LL-05, LL-12, LV-04, LV-06, LV-11, PL-23, PL-24, PL-25) are the BUG-1435/1436/1437/2118/2119/2120 cards, which my reference does not implement. The executor's notes report its own reference at 202 passed.

### Runs
- Coverage run: 97 passed, 105 xfailed, 100% branch.
- Plain runs: 97 / 104 / 1 XPASS (LL-05, non-strict BUG-1435, allowed by its card); 97 / 105; 97 / 105.
- That XPASS is the documented non-strict tie-break and not a flaky finding. The ruling from round 1 stands.

### Findings
None that block. Optional, executor: the test-module docstring still says "(revision 2)"; the cases are revision 4. Ruff clean.

### Commands (round 2)
```
python tests/trace.py <cases> <test> docs/testing/bugs.md                                  -> cards 202 tests 202, no problems
pytest <test> -q -p no:cacheprovider --cov=app.managers.attachment_markup_manager --cov-branch --cov-report=term-missing
                                                                                           -> 97 passed, 105 xfailed; 100%
pytest <test> -q -p no:cacheprovider -rX   (x3)                                            -> 97/104/1 xpassed (LL-05); 97/105; 97/105
VFAIL_OUT=… PYTHONPATH=<scratch>\plug pytest <test> -p vfail --runxfail                    -> 105 failed, 97 passed
AMV=<variant> PYTHONPATH=<scratch>\plug pytest <test> -p vamup [--runxfail -k "not …8 bug cards"] -> see table
mutate.py app/managers/attachment_markup_manager.py <test> --lines 453-453 --json <scratch>\mut.json
                                                                                           -> Mutants: 3 · killed 3 · survived 0 · score 100%
```
Scratch: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\attv\amup3r2\` (private `COVERAGE_FILE` per run).
