# Verification — `app/services/discussion_service.py`

> **Current verdict: PASS** (round 4, 2026-11-04, cases revision 5). See "Round 4" at the end. Round 3 was NEEDS WORK; its findings are closed. The rest of this block is round 1.
>
> **Verdict:** NEEDS WORK — 1 test-weakness (executor), 4 case gaps (case designer)
> Tests: 27 passed · 23 xfailed (21 strict, 2 non-strict: L-12, L-13) (reproduced ✅) · coverage 100% branch (34 statements, 10 branches)
> Mutation: 23 mutants · 20 killed · 3 survived → score 100% (after excluding 0 equivalent, 0 dead, 3 bug-path)
> Fidelity: **1 of 50 unfaithful** (DSS-C-01); all 50 read by eye against their cards
> Hand variants: 42 · 34 caught by a pass card · 8 others: 6 gaps (in Findings), 1 the correct BUG-1694 fix (must pass, and does), 1 with no observable effect
> Source commit: e48a092 · Cases revision: 2; spec APPROVED (OQ-5 parked)

## Summary
- **Mostly trustworthy.** 49 of 50 tests match their cards exactly, and D2, D3 and D4 are guarded. A rollback added on a refusal or on a database error, a commit in `list`, a swallowed commit error and a second commit each fail a pass card.
- **The three checked points:**
  - **OQ-5 isolation holds.** `invited_only`, `HelpTicket` / `mk_ticket` and `support_ticket` appear only in DSS-L-15, L-16, C-28 and C-29. Every other card posts on or lists P1 (visibility `workspace`), a purchase order or an item, as UA or UB, both active members. An owner answer of "bug" changes only those four.
  - **DSS-C-16 … C-18 catch both today's code and the fixed class.** Six variants that write the message before the refusal, commit before it, or roll back on it each fail all three cards, both with today's `TypeError` and with `NotFoundError` / `ValidationError`. So does a refusal that writes a notification (C-16), or one raised as `HTTPException`. The correct BUG-1694 fix passes all three, as it must.
  - **But the split covers only 3 of the 5 refusal shapes.** A parent of **another workspace** (C-11) and a parent on **another record type** (C-14) have only their xfail card. A variant that finds the parent in any workspace stores a reply under W1 that points at W2's message, and passes every pass card. That is the cross-workspace link HR-16 forbids.
- **One test does not check what its card asks.** DSS-C-01 reads `mid = result.id` before its `loaded:` line. Reading the id reloads the expired object, so Then 1 cannot fail: a `create` without `db.refresh` passes.
- Two smaller rule gaps: the `limit` pass-through is checked only for a negative value and for the default, and the mention fan-out only ever with one distinct active recipient.

Written by Claude (all 50 under `# [claude]`). Findings in local-written tests / local-written tests: 0 / 0. In others: 1 / 50. No `discussion_service.local-run.json`, so there is no `## Local-coder patterns` section.

## Findings
| # | Kind | Case / line | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | test-weakness | DSS-C-01 Then 1 (test lines 700–705) | `mid = result.id` comes before the `loaded:` asserts. On the expired object (`expire_on_commit` is on) that read reloads every column, so `"id" / "created_at" / "message" not in unloaded` holds even when nothing was re-read. Conventions: `loaded:` lines "run on the returned object first". Run them before reading `mid`. | variant `d1_no_refresh` (drop `db.refresh(discussion)`) passes all 27 pass tests. My R-DS-1 (the same asserts, before `result.id`) fails on it: `'id' not in unloaded`. | **executor** |
| 2 | case-missing | `create` R5, R12; D2; HR-16 (pass split of DSS-C-11) | The pass cards C-16 … C-18 cover parent `0`, a reply to a reply and another record id. A parent of another workspace is checked only by the strict xfail C-11, which still xfails when the reply is *stored*. | variants `r_parent_any_workspace` and `r_parent_any_workspace_fixed` (parent looked up by id alone) pass all 27 pass tests; R-DS-2 fails on both (`DID NOT RAISE`). | **case designer** |
| 3 | case-missing | `create` R7, R12; D2 (pass split of DSS-C-14) | The same for a parent on another `entity_type` with the same id: only the xfail C-14 checks it. | variant `r_same_entity_id_only` (the type comparison dropped) passes all 27; R-DS-3 fails on it. | **case designer** |
| 4 | case-missing | `list` R1 ("`skip`, `limit` … unchanged") | DSS-L-03 has 2 roots with `skip=1`, so its `limit=1000` cannot show anything. The limit is checked only at `-1` (L-04) and at the default (L-02). | variant `l_cap_50` (`min(limit, 50)`) passes all 27; R-DS-4 fails on it (`50 == 51`). Over the API a client asking `limit=200` would get 50. | **case designer** |
| 5 | case-missing | `create` R9 (the ids passed; each distinct active member once) | No pass card mentions two distinct active members other than the author (C-05 repeats UB, and C-07, with UA and UB, is xfail BUG-1535). | variant `c_only_first_mention` (`mentioned_ids[:1]`) passes all 27; R-DS-5 fails on it (`[] == [UB, UC]`). | **case designer** |

### Scratch cards that close the gaps
In `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\svc3v\discussion\test_prop_ds.py`, not in the repo. All 5 pass today and on the correct BUG-1694 fix (`d2_fixed_classes_correct`). Each fails on its variants as listed above.

| Recipe | Where | Given and When | Then | Expect |
|---|---|---|---|---|
| R-DS-1 | DSS-C-01 as written (executor) | — | Then 1 asserted on `result` before `mid = result.id` is read | pass |
| R-DS-2 | new card, `create` R5, R12; D2 | RZ = msg, but `workspace_id W2.id`. XM. When `svc.create(db, workspace_id=W1.id, user_id=UB.id, data=DiscussionCreate(entity_type=ET("project"), entity_id=P1.id, message="Reply", parent_id=RZ.id))`, with **spies**, inside `raises: (TypeError, NotFoundError)` | 1. raises: `isinstance(exc.value, (TypeError, NotFoundError))`. 2. `cm.call_count == 0`. 3. `rb.call_count == 0`. 4. count: `message == "Extra"`: exactly 1. 5. count: `message == "Reply"`: exactly 0. | pass |
| R-DS-3 | new card, `create` R7, R12; D2 | R = msg, but `entity_type "machine"`. XM. When the same call as DSS-C-14 (`message="Wrong type"`, `parent_id=R.id`), with **spies**, inside `raises: (TypeError, AppValidationError)` | 1. raises: `isinstance(exc.value, (TypeError, AppValidationError))`. 2. `cm.call_count == 0`. 3. `rb.call_count == 0`. 4. count: `message == "Extra"`: exactly 1. 5. count: `message == "Wrong type"`: exactly 0. | pass |
| R-DS-4 | new card (or replace L-03's Given), `list` R1 | 52 messages by `add_all` (as DSS-L-02). When `svc.list(db, W1.id, ET("project"), P1.id, limit=51)` | 1. `len(items) == 51`. 2. `total == 52`. | pass |
| R-DS-5 | new card, `create` R9 | UC = `make_profile(db, name="Cid")`, active member of W1 (a Given row; the standing rows have no third active member). When UA posts `f"@[{US.id}] @[{UB.id}] @[{UC.id}]"` on P1 | 1. committed: `recipients(mid) == sorted([UB.id, UC.id])`. | pass (also after BUG-1535: the author is not mentioned) |

## Surviving mutants
| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 21 | L51:27 | `"Parent discussion not found"` → `""` | bug-path | BUG-1694: today the `APIException(...)` call raises `TypeError` before the detail reaches anyone. Only the xfail C-09 … C-11 check the text. | — (resolves with BUG-1694) |
| 22 | L56:27 | `"Replies can only be one level deep"` → `""` | bug-path | The same; C-12, C-15. | — |
| 23 | L62:27 | `"Reply must be on the same entity as the parent"` → `""` | bug-path | The same; C-13, C-14. | — |

All 20 kills end in a plain failure of a pass card. The 27 pass tests ran on every mutant.

## Hand variants
Source edited in memory by my plugin `vplug.py`, run against the 27 pass tests. Every variant was applied, and every run reached all 27.

| Group | Variants | Pass card | Cards that fail | Others |
|---|---|---|---|---|
| d2 (write / commit / roll back on a refusal, each on today's `TypeError` and on the fixed classes; wrong class; notify on refusal; correct fix) | 9 | 8 | DSS-C-16, C-17, C-18 | `d2_fixed_classes_correct` (must pass, and does) |
| refusal rules (any-workspace parent ×2, type or id only, no depth check, truthy `parent_id`) | 6 | 3 | DSS-C-16, C-17, C-18 | `r_parent_any_workspace`, `r_parent_any_workspace_fixed`, `r_same_entity_id_only` |
| d1 (flush only, no re-read, commit before the fan-out, two commits) | 4 | 3 | DSS-C-01 … C-05, C-25, C-27 … C-29 | `d1_no_refresh` |
| d3 (rollback on error, on commit error; swallowed commit error) | 3 | 3 | DSS-C-26, C-27 | — |
| d4 (list commits, rolls back, flushes) | 3 | 3 | DSS-L-05 | — |
| list rules (skip, limit, defaults, total, return type, caps) | 7 | 5 | DSS-L-01 … L-04 | `l_cap_50`, `l_cap_200` |
| create rules (message stripped, actor, preview, source, entity, first mention only) | 8 | 7 | DSS-X-01, DSS-C-02, C-04, C-05 | `c_only_first_mention` |
| `_extract_mentions` (signed / spaced, no brackets) | 2 | 2 | DSS-X-03 | — |
| **Total** | **42** | **34** | | **8** |

### Considered and not listed
| Variant | Why it is not a finding |
|---|---|
| `d2_fixed_classes_correct` | The intended BUG-1694 fix. C-16 … C-18 must accept it, and they do. |
| `l_cap_200` (`min(limit, 200)`) | No observable effect: the endpoint already bounds `limit` to ≤ 200 (spec HR-7, cases "Deferred"). |

## xfail tests
`--runxfail` with my plugin `vfail.py`: **23 failed, 27 passed**. Each fails where its card's "Fails today on" says:
- On Then 1: X-05 (`[12, 12] == []`); L-08 … L-11, C-19 … C-22, C-24 (`DID NOT RAISE NotFoundError`); C-09 … C-15, C-23 (`TypeError: APIException.__init__() missing 2 required positional arguments`).
- On a later Then: L-12 on Then 2 (`[R3, R2, R1]`: the updated R1 comes last); L-13 on Then 2 (`[B, C, A]`); L-14 on Then 2 (no `parent_id IN` select); C-07 on Then 2 (`[UA, UB]`); C-08 on Then 3 (`'@Bob @Otto'`).
None fails on a setup or import error.

## Reproduced claims
- **The notes' Result line holds:** `27 passed, 23 xfailed` in 3 of 3 default runs (the coverage run is one of them). No flaky test.
- `--runxfail -rf`: `23 failed, 27 passed`.
- **Mocks:** only the spies, C-27's failing commit and L-14's listen-only statement recorder. No race simulation. `ruff check` passes.

## Traceability
cases 50 · tests 50 · unmatched: none · marker mismatches: none (27 pass with no marker; 21 `strict=True`; L-12, L-13 `strict=False`, as their Expect says). Every reason names its BUG ID, and every BUG ID is in `bugs.md`. Card order, docstrings, `# Then N` and `# [claude] <ID>` all match.

## Limits of this round
I did not build a reference for the intended behaviour. The executor's `refplug.py` passes all 50 with `--runxfail` (notes). I used it as evidence only. The runs were not isolated from the parallel mutation run.

## Commands run
```
mutate.py app/services/discussion_service.py tests/unit/services/test_discussion_service.py --json <scratch>/discussion/mut.json
  Mutants: 23 · killed 20 · timeout 0 · survived 3 · score 87%
  SURVIVED #21 L51:27, #22 L56:27, #23 L62:27 const: '<detail>' -> ''
pytest tests/unit/services/test_discussion_service.py -q -p no:cacheprovider --cov=app.services.discussion_service --cov-branch --cov-report=term-missing
  27 passed, 23 xfailed · 34 0 10 0 100%
pytest … --runxfail -rf (with -p vfail)                         23 failed, 27 passed
pytest … (x2)                                                   27 passed, 23 xfailed (both)
drive.py app.services.discussion_service … variants.py          42 variants (above)
pytest test_prop_ds.py (base + 8 variants)                      5 passed on base and on the correct fix; each gap variant fails its proposal
trace.py; grep for invited_only / ticket / support_ticket (OQ-5 isolation); ruff check (passes)
```
Scratch: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\svc3v\` (own `COVERAGE_FILE` per run). I wrote only this report in the repo. No commit. No process was killed.

## Fix list
1. **Executor:** DSS-C-01: assert Then 1 (`loaded:`) before `mid = result.id` is read.
2. **Case designer:** add R-DS-2 … R-DS-5 (wording above). Optional: say in Conventions that `mid` is read after any `loaded:` line, so that the two rules cannot be read as conflicting.
3. **Executor,** after 2: implement them, then send the module back for a narrow re-verification.

## Round 2 — 2026-11-04 (cases revision 3, narrow)

> **Verdict:** PASS
> Tests: 31 passed · 23 xfailed (reproduced ✅, 3 of 3 runs) · coverage 100% branch
> Mutation: not re-run (no source change); round 1 stands at 20 / 20 → 100% (23 mutants, 3 bug-path)
> Fidelity: **0 of 54 unfaithful** (the 5 changed or new cards read by eye; all 54 traced by script)
> Source commit: e48a092 · Cases revision: 3; spec APPROVED, unchanged

Findings 1–5 are closed. There is no new finding. I edited no test and made no commit.

| Card | Recipe | Read against card | Variants that now fail it |
|---|---|---|---|
| DSS-C-01 (fixed) | R-DS-1 | matches: the three `loaded:` asserts now run before `mid = result.id` | `d1_no_refresh` |
| DSS-C-30 (new) | R-DS-2 | matches (pass; `(TypeError, NotFoundError)`, spies, XM stays, no "Reply") | `r_parent_any_workspace`, `r_parent_any_workspace_fixed` |
| DSS-C-31 (new) | R-DS-3 | matches (pass; `(TypeError, AppValidationError)`) | `r_same_entity_id_only` |
| DSS-C-32 (new) | R-DS-5 | matches (UC built as a Given row; `recipients == sorted([UB, UC])`) | `c_only_first_mention` |
| DSS-L-17 (new) | R-DS-4 | matches (52 roots, `limit=51` → 51, total 52) | `l_cap_50` |

- **The correct BUG-1694 fix (`d2_fixed_classes_correct`) still passes all 31 pass tests.**
- **OQ-5 isolation:** unchanged. None of the new cards uses a private project or a help ticket.
- **Reproduced:** `31 passed, 23 xfailed` in 3 of 3 runs. `--runxfail`: `23 failed, 31 passed`.
- **Traceability:** cases 54 · tests 54 · unmatched: none · marker mismatches: none. `ruff check` passes.

```
pytest tests/unit/services/test_discussion_service.py -q -p no:cacheprovider   (x3)   31 passed, 23 xfailed
pytest … --runxfail                                                                     23 failed, 31 passed
drive.py … d1_no_refresh r_parent_any_workspace r_parent_any_workspace_fixed r_same_entity_id_only l_cap_50 c_only_first_mention   all 6 KILLED; d2_fixed_classes_correct passes
trace.py; ruff check
```

## Round 3 — 2026-11-04 (cases revision 4, OQ-5 answered; narrow)

> **Verdict:** NEEDS WORK — 1 case gap (case designer), 1 spec gap (describer). No test is wrong.
> Tests: 40 passed · 52 xfailed (reproduced ✅, 3 of 3 runs) · coverage 100% branch (source unchanged)
> Mutation: touched lines only (34–36 `list`; 65–91 write and mention fan-out): 2 mutants · 2 killed. The rest of the file is unchanged since round 1 (20 / 20 → 100%).
> Fidelity: **0 of 42 unfaithful** (the changed and new cards read by eye: L-15, L-16, L-18 … L-31, C-28, C-29, C-33 … C-56; all 92 traced by script)
> Reference fix (mine, written from the spec): **all 29 BUG-1867 / BUG-1868 / BUG-1879 xfail cards pass**. Under `--runxfail`: 69 passed, 23 failed, and the 23 are exactly the cards of other bugs (BUG-1536, 1686, 1687, 1438, 1439, 1490, 1534, 1535, 1694).
> Fix variants: 28 · 26 caught by a card · 2 others (in Findings)
> Source commit: e48a092 · Cases revision: 4; spec APPROVED (OQ-5 answered by the owner)

### Fidelity and fails-today
- **Builders match the Conventions:** `mk_person`, `mk_admin` (no membership, `is_platform_admin` set and flushed), `set_owner`, `mk_private_project` (`invited_only`, `created_by` UA), `mk_component`, `invite`, `mk_ticket(**but)`, and `notes(db, mid, recipient=…)`.
- **Each test matches its card:** Given order, commit point, XM after the commit point, the spies inside the `raises:` wrap, and every Then line in order.
- **`--runxfail`:** each card fails where it says.
  - Of the 16 `list` cards that pass `user_id`, L-15, L-16 and L-28 fail on Then 1 (the call inside the `raises:`). The other 13 fail on the stored call just before Then 1. All 16 fail with `TypeError: … unexpected keyword argument 'user_id'` (accepted, as agreed).
  - C-28, C-29, C-42, C-46 … C-49, C-51 fail on Then 1 (`DID NOT RAISE NotFoundError`).
  - C-50 fails on Then 1 (`TypeError` of BUG-1694, as its card says).
  - C-52 … C-54 fail on Then 4, and C-55 on Then 3 (`1 == 0`: UB notified).
- **Pass cards** C-33 … C-41, C-43 … C-45 and C-56 pass today and under the reference fix.

### Reference fix and variants
My reference fix is in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\svc3v\discussion\variants_r3.py` (`ref`), applied in memory by `vplug.py`.
- **What it adds:**
  - a `may_open(record, user)` check following the spec Facts:
    - private project: workspace owner, active `owner` / `ground-team-manager` member of *this* workspace, creator, `project_members` row for this project;
    - component: its project;
    - ticket: platform admin, `owner` / `ground-team-manager` role, creator.
  - The check runs before the parent check, refuses with `NotFoundError("Record not found")` and makes no rollback.
  - `list` gets a keyword-only `user_id`.
  - Mentioned ids are filtered through the same check.
- **Each variant runs on top of that fix, with `--runxfail`.** "Caught" means a card fails that passes on the fix:

| Variant | Cards that catch it |
|---|---|
| too loose: any active member opens a private project (allows UB) | C-28, C-42, C-46 … C-48, C-50, C-52, C-53, C-55, L-15, L-28 |
| too loose: any member opens any ticket | C-29, C-49, C-54, L-16 |
| too loose: component not checked | C-42, C-53, L-28 |
| too loose: privileged role in any workspace / owner of any workspace / invited to any project / suspended privileged / creator of any ticket | C-47 / C-48 / C-46 / C-51 / C-49 |
| too strict: invited member refused | C-37, C-43, C-52, C-53, L-22, L-29 |
| too strict: platform admin refused (ticket) | C-41, L-27 |
| too strict: workspace owner / project creator / ticket creator / ground-team-manager refused | C-34, L-19 / C-33, C-52, C-53, C-55, L-18 / C-38, C-54, L-24 / C-36, L-21 |
| too strict: `workspace` projects checked too; every type checked | 16 cards (C-01 … C-06, C-17, C-18, C-26, C-27, C-31, C-32, C-44, C-56, L-23, L-30) / C-25, C-45, L-31 |
| check placed after the parent check | C-50 |
| refusal after the write; refusal with a rollback | C-28, C-29, C-42, C-46 … C-51 / C-28, C-29, C-42, C-46 … C-49, C-51 |
| mentions not filtered; filtered by the author's access; all dropped when one is refused; only privileged kept everywhere | C-52 … C-55; C-52 … C-55; C-52 … C-54; C-04, C-05, C-32, C-52, C-53, C-56 |
| **survives:** a platform admin opens private projects | — (Finding R3-1) |
| **survives:** a suspended `owner` / `ground-team-manager` is refused on tickets | — (Finding R3-2) |

### Findings (round 3)
| # | Kind | Rule | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| R3-1 | case-missing | `create` R11 / `list` R5 (Facts: "Anyone else may not"; a platform admin is not among the four kinds for a private project) | No card refuses a platform admin on a private project. The admin is allowed only on tickets (C-41, L-27). | variant `loose_admin_on_project` passes every card on the reference. My R-DS-6 (`…\svc3v\discussion\test_prop_ds3.py`) fails on it, passes on the reference, and fails today (`DID NOT RAISE`). | **case designer** |
| R3-2 | spec-gap | `list` R5a / `create` R11a (Facts, "Who may open a help ticket", (2)) | The ticket rule says "membership role `owner` or `ground-team-manager`" and is silent on `status`. The private-project rule says "an **active** member". `HelpTicketManager.can_access_ticket` takes the role from the request, not from a membership row. So nothing says whether a suspended manager may open a ticket's thread. | variant `strict_ticket_active_only` and the reference disagree on that caller, and no card exists. A card cannot be written until the rule says which. | **describer** (fill-gaps) |

**Recipe R-DS-6** (strict xfail BUG-1867; fails today on Then 1, `DID NOT RAISE NotFoundError`):
- **Given:** admin PA. PP = private project, `name "Secret Project"`. XM.
- **When:** `svc.create(db, workspace_id=W1.id, user_id=PA.id, data=DiscussionCreate(entity_type=ET("project"), entity_id=PP.id, message="Hidden"))`.
- **Then:**
  1. raises: `NotFoundError`.
  2. raises: `exc.value.detail == "Record not found"`.
  3. count: `message == "Hidden"`: exactly 0.
  4. count: `message == "Extra"`: exactly 1.

A `list` twin (`user_id=PA.id`) is optional.

### For the coming notifications and permissions features
- **One `may_open(record, user)` helper.** These rules need the same check in three places in this service: `list`, `create`, and the mention filter. OQ-5 extends it to attachments and calendar entries. Put the project rule (`ProjectManager.can_access_project`) and the ticket rule (`HelpTicketManager.can_access_ticket`) behind one function.
- **Pass explicit inputs.** Today the ticket rule reads the role from the request, while the project rule reads membership from the database. Mentions need the check for *another* person, so the helper must take `user_id` and `workspace_id`, not the request.
- **Decide the platform admin's reach.** Today an admin opens every ticket but no private project (R3-1). Confirm this with the owner before the permissions feature generalises it.
- **Suspended members (R3-2).** Projects require `active`; tickets are unspecified. Pick one rule for every record type.
- **R9a filter location.** The filter may sit in `discussion_service` or in `notification_service.fan_out_mentions` (the spec leaves it open). If it moves to `fan_out_mentions`, give that function the record's type and id plus the access check, so that other notification sources (attachments, calendar) get the same filter.
- **Previews are built before filtering.** `humanize_mention_preview` runs on the whole message. A refused person gets no row, so nothing leaks today. But a feature that sends previews by another channel (email, push) must filter first.
- **Access changes after the fact are unspecified.** No rule says what happens to notifications already written when a project becomes private or an invitation is removed. Their previews stay in the old recipients' lists. This is a question for the notifications feature.
- **`list` gains a required `user_id`.** The endpoint must pass `current_user.id`. The older `list` cards gain `user_id=UA.id` (Conventions).
- **The refusal is the same 404 `Record not found` as a missing record.** Deep links from notifications to a thread the reader can no longer open will 404 without telling them why. That is intended (no existence leak), but the UI should expect it.

### Commands run
```
pytest tests/unit/services/test_discussion_service.py -q -p no:cacheprovider   (x3)   40 passed, 52 xfailed
pytest … -p vfail --runxfail                                                           52 failed, 40 passed; fail lines as above
pytest … -p vplug (VARIANT=ref) --runxfail                                             69 passed, 23 failed (other bugs only)
drive.py (DRIVE_ALL=1) app.services.discussion_service … variants_r3.py                28 fix variants, diffed against ref (diffvars.py)
pytest test_prop_ds3.py: base FAIL (today stored) · ref PASS · loose_admin_on_project FAIL
mutate.py app/services/discussion_service.py … --lines 34-36    1 mutant · 1 killed
mutate.py app/services/discussion_service.py … --lines 65-91    1 mutant · 1 killed
trace.py (cards 92 · tests 92 · mismatches 0); ruff check (passes)
```
Scratch: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\svc3v\`. I wrote only this report in the repo. No commit. No process was killed.

## Round 4 — 2026-11-04 (cases revision 5, narrow)

> **Verdict:** PASS
> Tests: 41 passed · 56 xfailed (reproduced ✅, 3 of 3 runs) · coverage unchanged (source unchanged)
> Mutation: not re-run (no source change); rounds 1–3 stand
> Fidelity: **0 unfaithful** among the changed or new cards (DSS-L-32, C-57, L-33, C-58, C-59); all 97 traced by script
> Source commit: e48a092 · Cases revision: 5

No new finding. I edited no test and made no commit.

| Variant (on my corrected reference `ref5`: the ticket's owner / ground-team-manager role counts only for an active member, per the spec's dated note) | Cards that catch it |
|---|---|
| platform admin allowed on private projects (round-3 R3-1) | C-57, L-32 |
| suspended `owner` allowed on a ticket (round-3 R3-2; my round-3 reference) | C-58, L-33 |
| creator must be active to post on their own ticket (too strict) | C-59 |

- **Reading the tests:** L-32, C-57, L-33, C-58 and C-59 each match their card (Givens, commit point, XM after it, spies inside the `raises:` wrap, every Then line in order).
- **`--runxfail`:** L-32 and L-33 fail on Then 1 with the `user_id` `TypeError` (the call is inside the `raises:`), and C-57 and C-58 on Then 1 (`DID NOT RAISE NotFoundError`), as their cards say. C-59 passes today.
- **Under `ref5`:** 74 passed and 23 failed, and the 23 are only the other bugs' cards. All 33 BUG-1867 / BUG-1868 / BUG-1879 cards pass.
- **Runs:** `41 passed, 56 xfailed` in 3 of 3 runs. Traceability: cards 97 · tests 97 · mismatches 0. `ruff check` passes.
- R3-1 and R3-2 are closed. The spec note's BUG-1885 (the help ticket code reads the role without the status) is a manager bug, not a rule of this service.

```
pytest <test file> -q -p no:cacheprovider (x3); pytest … -p vfail --runxfail; drive.py (DRIVE_ALL=1) on the variants above; trace.py; ruff check
```
