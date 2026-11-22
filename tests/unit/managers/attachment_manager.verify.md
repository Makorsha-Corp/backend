# Verification — `app/managers/attachment_manager.py`

> **Verdict:** NEEDS WORK
> **Current verdict (Round 2):** PASS — cases Revision 4 closes findings 1–5; 213 passed · 130 xfailed (reproduced ✅, 3/3 runs) · 100% branch · targeted mutation 28/28 (incl. #232) · the 5 round-1 survivor variants and mutant #232 now killed by named cards
> Tests: 208 passed · 117 xfailed (reproduced ✅; 115 strict, 2 non-strict) · coverage 100% branch (269 stmts, 104 branches)
> Mutation: 333 mutants · 332 killed · 1 survived → score 99.7% (after excluding 0 equivalent, 0 dead, 0 bug-path)
> Hand variants (verifier's own reference + one defect each, full file with `--runxfail`): 40 · 32 killed · 8 survived (3 invalid-data only, 5 routed)
> Source commit: e48a092 · Cases revision: 3

## Summary
The tests are faithful. Every case has exactly one test, every marker matches its card, every Then line is asserted in the card's order, and every xfail test fails where its card says it will. Three plain runs gave the same result, so nothing is flaky. Mutation testing of today's code kills everything except one side of the PDF check. My own intended-behaviour reference (PR-1…PR-5 plus every bug fix) passes all 325 tests with `--runxfail`, so the refusal cards will hold once the bugs are fixed. They catch most deliberate defects: role not read, inactive or other-workspace membership counted, case-folded or prefix roles, links read from every workspace, "any link" instead of "all links", missing workspace scoping, missing deleted-parent checks, every too-strict variant, refusal after a write, flush or Cloudinary call, wrong `public_id` or keyword, and size off by one either way. **Missing cards** let four defects through, and one spec question is open. The case designer must add: a platform admin refused a private project; a **ready** attachment of a hidden record refused at confirm; a refusal that comes before the page and `public_id` errors; and a PDF recognised by MIME type alone.

## Findings
| # | Kind | Case / line | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing | PR-2 (C, PG, CF, D) | No card has a platform admin refused a **private project** (spec PR-2: platform admin opens help tickets only). The admin cards are C-58, PG-34, CF-81 and D-54, all on tickets. | Variant `admin_opens_private` (admin passes `can_access_project`): 325 passed | case designer |
| 2 | case-missing | `confirm_attachment` R1a / R2, PR-3, PR-4 | Every CF refusal card uses a `pending` attachment. A version that returns an already-`ready` attachment before the visibility check (R2 short-circuit first) passes them all. The service then maps the hidden attachment with `to_response` (name, `public_id`, signed URLs). This needs a card "ready attachment of a hidden private project / ticket: confirm → `Attachment <id> not found.`, cl_untouched". | Variant `confirm_ready_before_check`: 325 passed | case designer |
| 3 | case-missing | `get_pdf_page_image` R2 / `confirm_attachment` R1a vs R3; PR-3 "exactly as a missing one" | No card combines a hidden attachment with a second error: page 0 on PG, or no `public_id` on CF. A version that raises "Page number must be at least 1." (400) or "Attachment has no public_id." (400) before the visibility check reveals that the attachment exists, and it passes. If the designer reads PR-3 / PR-4 as silent on this order, route it to the describer (fill-gaps). | Variants `pg_page_first`, `confirm_nopid_first`: 325 passed each | case designer |
| 4 | case-missing | `build_pdf_page_image_url` R3 | R3 is an OR ("neither MIME `application/pdf` nor format `pdf`"). No card has MIME `application/pdf` with a format other than `pdf`, so only the format side is tested. | Mutant #232 survived | case designer |
| 5 | spec-gap | PR-2, help tickets | The spec gives tickets only the membership role (`can_access_ticket`). Private projects also open for the workspace owner (`workspaces.owner_user_id`, `_is_workspace_owner`). The spec does not say whether a W1 `owner_user_id` holder with a plain membership role may open another member's ticket, and no card pins it. | Variant `ws_owner_ticket` (owner_user_id opens tickets): 325 passed | describer (fill-gaps), then case designer |

No fidelity findings: no missing, weakened or changed assertions, no wrong setup, no swallowed failures, no extra mocks, no dishonest xfails.

Minor, not a finding: in D-05 the `utcnow` patch also wraps the Given lines. The Given builders do not read that clock, so it changes nothing.

## Surviving mutants
| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 232 | 589 | `'application/pdf'` → `''` in `attachment.mime_type != "application/pdf"` | case-missing | The check becomes `format != "pdf"`. No card has a PDF by MIME type whose format is not `pdf` (finding 4). | case designer |

## Hand variants
Plugin `vref_atcm.py` (in scratch) is my own in-process reference; `ATCM_VARIANT` picks one defect. Reference alone: **325 passed** with `--runxfail`.

| Variant (defect) | Result |
|---|---|
| role_not_read (role passed in / never read) | killed |
| inactive_counts · role_any_ws · role_casefold · role_prefix | killed |
| links_any_ws (link filter not limited to the caller's workspace) · no_link_allowed · any_link | killed |
| **admin_opens_private** | **survived → finding 1** |
| strict_workspace_project · strict_no_creator · strict_no_pmem · strict_no_admin_ticket · strict_creator_only · strict_scratch · strict_member_check (too strict) | killed |
| no_ws_scope (parent read by id only) · no_deleted_check · no_deleted_wo · comp_project_deleted_ok | killed |
| capacity_first · create_check_after_flush · delete_check_after_flush · delete_destroy_first · pg_url_first · confirm_lookup_first (refusal after a write, flush or Cloudinary call) | killed |
| confirm_caller_uploader (ignores `performed_by`) · confirm_rt_hardcoded · destroy_wrong_pid · destroy_wrong_kw | killed |
| size_ge · size_plus1 · size_fail_no_destroy | killed |
| **confirm_ready_before_check** | **survived → finding 2** |
| **pg_page_first · confirm_nopid_first** | **survived → finding 3** |
| **ws_owner_ticket** | **survived → finding 5** |
| pmem_any_ws · comp_project_any_ws · confirm_no_ws | survived — invalid-data only: each needs a row filed across workspaces (project member, component→project, or a W1 link on a W0 attachment), which HR-16 rules out and no writer produces. No finding; defence in depth only. |

## Non-strict xfails
LG-08 and TR-07 (BUG-1433) are `strict=False` by card ("usually comes back first"), so a chance XPASS is allowed. The strict alarm LG-09 (no `ORDER BY` on the links query) still guards the bug. Both xfailed in all three of my runs.

## Traceability
cases 325 · tests 325 (incl. parametrized params) · unmatched: none · duplicate IDs: none · marker mismatches: 0 (aliases `X1870`…`X2102` resolved; every reason names its BUG ID; every BUG ID exists in bugs.md) · Then markers: 325/325 cards match `# Then 1..N` · named checks (cl_untouched, nothing written, session clean, unchanged): 0 gaps.
`--runxfail`: 117/117 fail. 114 fail inside the Then block their card names. CP-03, D-41 and D-47 fail at the When call just above `# Then 1`, which is what their cards' "Fails today" text describes (AttachmentLimitError / IntegrityError).

## Useful for the coming features
- **Permissions:** the gaps above are the edges a permissions layer must decide: platform admin vs private projects (spec: no), workspace `owner_user_id` vs tickets (open, finding 5), and the order of refusal vs validation errors (existence leak). `confirm_attachment` R2 returns a ready attachment before anything else today. Any "who may confirm" rule must come before that short-circuit.
- **Notifications:** "Attached" / "Removed" come from `_log_attachment_entity_events`; after BUG-2093 / BUG-2098 they map one-to-one to ready / removed transitions. The reference shows the clean hook points.
- **Payments / storage quota:** BUG-1434 (failed uploads counted) and BUG-2099 (orphaned files) affect any per-plan storage count. The size guard (BUG-2092) is pinned at exactly 10 485 760 (CF-22 / CF-23; both off-by-one variants killed).
- Reusable: the `--runxfail` + own-reference + `ATCM_VARIANT` plugin pattern tests the strength of xfail refusal cards before the fix exists.

## Commands run
```
COVERAGE_FILE=<scratch>/.coverage.r1 .venv/Scripts/python.exe -m pytest tests/unit/managers/test_attachment_manager.py -q -p no:cacheprovider --cov=app.managers.attachment_manager --cov-branch --cov-report=term-missing
  → app\managers\attachment_manager.py 269 0 104 0 100% · 208 passed, 117 xfailed
COVERAGE_FILE=<scratch>/.coverage.rx .venv/Scripts/python.exe -m pytest tests/unit/managers/test_attachment_manager.py -q -p no:cacheprovider --runxfail -rf
  → 117 failed, 208 passed
(runs 2 and 3, private COVERAGE_FILE each) → 208 passed, 117 xfailed · 208 passed, 117 xfailed
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/managers/attachment_manager.py tests/unit/managers/test_attachment_manager.py --json <scratch>/mut.json
  → Mutants: 333 · killed 332 · timeout 0 · survived 1 · score 100% (SURVIVED #232 L589:35)
PYTHONPATH=<scratch>/plug ATCM_VARIANT=<v> .venv/Scripts/python.exe -m pytest tests/unit/managers/test_attachment_manager.py -q -p no:cacheprovider -p vref_atcm --runxfail -x
  → ref: 325 passed; variants as in the table
```
Scratch: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\attv\atcm3\` (trace.py, failon.py, thens.py, named.py, show.py, plug\vref_atcm.py, runvar.sh, mut.json, var_*.txt).

## Round 2 — 2026-11-04

**Current verdict: PASS.** Cases Revision 4 (343 cards, 18 new) and spec G11 / G12 / BUG-2103 close every round-1 finding. The new tests are faithful, the runs reproduce the notes, nothing is flaky, and every round-1 survivor (5 variants and mutant #232) is now caught by a named card.

### What changed
- New cards: C-71, C-72, PG-44, PG-45, CF-100, CF-101, D-64, D-65 (platform admin refused a private project / component; finding 1). C-73, PG-46, CF-102, D-66 (workspace owner with a plain role opens another member's ticket, BUG-2103; pass today; finding 5). CF-103, CF-104 (hidden ready attachment → 404 before the ready return, no name / public_id / URL in the message; finding 2). PG-47, PG-48, CF-105 (hidden + page 0 / pending / no public_id → 404 before validation; finding 3, G12). PU-15 (PDF by MIME type alone; finding 4).
- Notes say no existing card changed; the card count (325 → 343) and the traceability run agree.

### Fidelity of the 18 new tests
Each was read against its card. Every Then line has its `# Then N` assertion in order with the card's exact value: the message checks use `==`, CF-103/104 Then 3 asserts all three `not in` checks, and `cl_untouched` asserts four checks. The Givens are built as written: `proj(..., private=True)`, `comp`, `set_owner` + `member(UX, "ground-team")`, `att(..., public_id=None)`, and a pending PDF for PG-48. The callers are as written too: UA for the admin cards, UG for the hidden cards, UX for the owner cards. The C cards use the `create()` helper, which is the card's When exactly (NORM(R), "dev/new-1", "Dev/F"). There are no new mocks.
- Markers: C-71/72 `X1870`, PG/CF/D refusals `X2091` (strict, the reason names the BUG). The owner cards and PU-15 have no marker (Expect pass). BUG-2103 exists in bugs.md (open).
- `--runxfail` on the 13 new xfails: 13 failed, each on its card's "Fails today on" line. C-71/72, CF-100/101/103/104 → `DID NOT RAISE AttachmentNotFoundError` at Then 1. PG-44/45/47/48 → `TypeError … unexpected keyword argument 'user_id'` at Then 1. CF-105 → `AttachmentConfirmError: Attachment has no public_id.` at Then 1. D-64/65 → `assert <Attachment> is None` at Then 1.
- Cosmetic, not a finding: the module docstring still says "revision 2" (executor, optional).

### Findings
None.

### Round-1 survivors re-run
Reference plugin `vref_atcm.py` was updated to Revision 4 intent: `owner_user_id` opens every ticket of its workspace (BUG-2103). With `--runxfail` it gives **343 passed**.

| Round-1 survivor | Round 2 | Killed by |
|---|---|---|
| variant `admin_opens_private` | killed (8 failed) | C-71, C-72, PG-44, PG-45, CF-100, CF-101, D-64, D-65 |
| variant `confirm_ready_before_check` | killed (2) | CF-103, CF-104 |
| variant `pg_page_first` | killed (1) | PG-47 |
| variant `confirm_nopid_first` | killed (1) | CF-105 |
| variant `ws_owner_ticket` → now intended; inverted to `ws_owner_ticket_refused` | killed (4) | C-73, PG-46, CF-102, D-66 |
| new variant `pg_ready_first` (pending check before visibility) | killed (1) | PG-48 |
| mutant #232 (L589 `'application/pdf'` → `''`) | killed | PU-15 |

All 35 other round-1 variants were re-run against Revision 4 and give the same outcomes as round 1. All 32 that round 1 killed are still killed. `pmem_any_ws`, `comp_project_any_ws` and `confirm_no_ws` still pass (invalid cross-workspace data only, as classified in round 1, so no finding).

### Mutation (lines 585–595 only, covering #232)
28 mutants · 28 killed · 0 survived → 100%. Together with round 1 (332/333, only #232 surviving), every mutant of the module is now killed.

### Commands run
```
trace.py cases.md test_attachment_manager.py bugs.md ATCM
  → cards 343 · tested ids 343 · missing [] · extra [] · dup {} · marker mismatches 0
COVERAGE_FILE=<scratch>/.cov.main .venv/Scripts/python.exe -m pytest tests/unit/managers/test_attachment_manager.py -q -p no:cacheprovider --cov=app.managers.attachment_manager --cov-branch --cov-report=term-missing
  → app\managers\attachment_manager.py 269 0 104 0 100% · 213 passed, 130 xfailed
(runs 2 and 3, private COVERAGE_FILE each) → 213 passed, 130 xfailed · 213 passed, 130 xfailed
COVERAGE_FILE=<scratch>/.cov.rx .venv/Scripts/python.exe -m pytest … --runxfail -rf --tb=short -k "<13 new xfails>"
  → 13 failed, 330 deselected (each on its card's line)
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/managers/attachment_manager.py tests/unit/managers/test_attachment_manager.py --lines 585-595 --json <scratch>/mut.json
  → Mutants: 28 · killed 28 · timeout 0 · survived 0 · score 100%
runvar.sh ref <variants…>   (PYTHONPATH=<scratch>/plug ATCM_VARIANT=<v> pytest … -p vref_atcm --runxfail)
  → ref 343 passed; variants as in the table
```
Scratch: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\attv\atcm3r2\` (plug\vref_atcm.py, runvar.sh, allvars.txt, var_*.txt, mut.json, mut.log, runxfail_new.txt).

### Useful for the coming features (round 2)
- **Permissions:** the decided edges are now pinned:
  - a platform admin opens tickets only, never private projects or their components;
  - the workspace `owner_user_id` opens every ticket whatever their membership;
  - the visibility refusal comes before every validation error and before confirm's ready short-circuit, so nothing reveals that a hidden attachment exists.

  A shared permission helper must keep that order.
- **Notifications / payments:** nothing new beyond round 1.
