# Verification — `app/managers/project_manager.py`

> **Current verdict (round 2, 2026-11-04, cases revision 2):** PASS. Findings 1–5 are closed. 234 passed · 46 xfailed · 100% branch, stable over 3 runs. See "Round 2" at the end.
>
> **Round 1 verdict:** NEEDS WORK (case designer only; tests and executor clean)
> Tests: 233 passed · 46 xfailed (reproduced ✅; 43 strict, 3 non-strict LM-03 / L-09 / L-10) · coverage 100% branch (207 statements, 64 branches)
> Mutation: 200 mutants · 196 killed · 4 survived → score 100% (196 / 196, after excluding 3 equivalent, 0 dead, 1 bug-path)
> Source commit: e48a092 · Cases revision: 1

## Summary
The tests do what the cards say. All 279 cards are traced, and fidelity is clean (EV-08 included, see below). The runs reproduce the notes, `mutate.py` leaves nothing but equivalent or bug-path survivors, and my access-rule variants are caught. Visibility that is too loose, visibility that is too strict, unscoped reads, a refusal after a flush, and a wrong BUG-1958 fix all fail tests.

One gap remains, and it is in the **cards**. Most refusal cards of the write methods prove "nothing written" only through `unchanged` (after `expire_all`) and row counts. Those two checks cannot see a change that was set on the session but **not flushed**, and the test session does not autoflush. I wrote variants that leave a dirty attribute, a pending add or a pending delete, then raise. They survive in `set_visibility`, `delete_project`, `add_member` (409) and `remove_member` (creator 400). The same pattern is caught only where the card has a `session:` line (AM-04, U-14). The service commits after the manager, so such a leftover would be written.

## Findings
| # | Kind | Case / line | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing | SV-04 (SV-05) · `set_visibility` R2 | A deleted-project refusal that sets `project.visibility` without flushing passes. The card has no `session:` line (`P not in db.dirty`). `unchanged(P)` expires the change first. | variant P37 (`project.visibility = visibility.value` before the raise, no flush): 233 passed | **case designer** — add `session: P not in db.dirty and not db.new` before the re-read, as U-14 does |
| 2 | case-missing | D-05 · `delete_project` R2 | Same for "already deleted": `project.deleted_by = user_id` set without a flush, then the raise, survives. | variant P39c: 233 passed | **case designer** — add `session: P not in db.dirty` |
| 3 | case-missing | AM-12, AM-13 · `add_member` R3 | A 409 that leaves a pending `ProjectEvent` / `ProjectMember` in the session survives. AM-04 (the 400) has `session: not db.new` and kills the same shape (P39). | variant P39b: 233 passed | **case designer** — add `session: not db.new` to AM-12 (and AM-13) |
| 4 | case-missing | RM-05 (RM-06) · `remove_member` R2 | A creator refusal that has already called `session.delete(row)` without a flush survives. `unchanged(M1)` expires, and the pending delete is never sent. | variant P39d: 233 passed | **case designer** — add `session: not db.deleted` |
| 5 | case-missing (minor) | `can_access_project` R2 / R3 | The member grant's `workspace_id` comes from the argument, not from `project.workspace_id`. No card has a private project of another workspace whose member row sits in the project's own workspace. CA-30 pins R3 for the privileged grant only. | variant P03 (`workspace_id=project.workspace_id` in the member lookup): 233 passed | **case designer** — one CA card: W2 private project, member row under W2, asked with W1 → `False` |

The other refusal cards without a `session:` line are AM-05 … AM-11, AM-14 … AM-16, RM-08 … RM-11, SV-06, SV-07, C-07, C-08, D-06, D-07, U-15 and U-16. They refuse before the method touches the session (404 / 403 at the access check, or the 400 before the add). Adding the same line to them is cheap, but it is not required for the variants above.

No fidelity finding for the executor. **EV-08**: the call's ids are read before `expire_all`. This is faithful: reading `S.W1.id` / `S.UG.id` after the expiry would add two refresh statements the card does not count. The card's own "fails today" figure, 6 besides the project read, is the executor's count (`6 <= 3` reproduced). A literal reading would give 8, and would also fail a correct fix.

## Surviving mutants
| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 145 | 296 | `'User #'` → `''` (`add_member` name fallback) | equivalent | Unreachable. The person must have an active `workspace_members` row, and that row's `user_id` references `profiles`, so `profile_dao.get` cannot return `None` (spec `add_member` R4: "unreachable while the membership exists"). | — |
| 148 | 335 | `'User #'` → `''` (`remove_member` name fallback) | equivalent | Unreachable. `project_members.user_id` is `ForeignKey("profiles.id", ondelete="CASCADE")`, so a member row cannot outlive its profile. | — |
| 155 | 501 | `exclude_unset=True` → `False` | equivalent | Every `ProjectUpdate` field defaults to `None`, and `exclude_none=True` drops them. The dict is the same either way. | — |
| 156 | 501 | `exclude_none=True` → `False` | bug-path | Lets explicit `null` through, which is the BUG-1953 behaviour. Only the xfail cards U-17 … U-24 send `null`. | — |

### Hand variants (verifier's own, `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\mgr6v\variants.py`, temp copy)
| # | Variant | Result | Caught by |
|---|---|---|---|
| P01 | workspace-visible project treated as private | killed (14) | CA-01, CA-02, RA-01, L-02 … |
| P02 | membership of **any** project of the workspace grants access | killed (2) | CA-16, L-02 |
| P03 | member lookup with `project.workspace_id` | **survived** | Finding 5 |
| P03b | member row of the project in any workspace | killed | CA-18 |
| P04 | owner of **any** workspace (W0 / W2) privileged | killed (6) | WO-05 … WO-07, CA-13, CA-14, L-04 |
| P05 | active owner / GTM in **any** workspace privileged | killed (4) | PV-16, PV-17, CA-15, L-05 |
| P06 | creator check against `updated_by` (wrong id) | killed (6) | CA-07, CA-29, CA-31, EV-06, G-02, L-02 |
| P07 | private project with no creator open to all | killed | CA-23 |
| P08 | inactive / suspended privileged member allowed | killed (8) | PV-05 … PV-09, CA-11, CA-12, L-06 |
| P09 | any active role privileged | killed (38) | PV-04, PV-10 … PV-14, CA-03 … |
| P10–P13 | too strict: no creator / no member / no privileged grant / GTM not privileged | all killed | CA-07, CA-08 … CA-10, CA-04 … CA-06, PV-03, PV-18 … |
| P14–P18 | unscoped project / component (require, log) / factory / active-member reads | all killed | GN-05/06, RA-05/06, RC-06/07, LC-07/08, C-09/10, AM-06/07 … |
| P19 | list without access filter | killed (5) | L-02, L-04 … L-06, L-30 |
| P20, P21 | list: privileged bypass rewritten / removed | survived, **equivalent** | Without the bypass, privileged callers still pass `can_access_project` one by one. Same rows, more queries. |
| P30–P36 | refusal after a **flush** (400 / 409 / creator / deleted / deleted factory / already deleted / access check skipped) | all killed | AM-04 … AM-14, RM-05, U-14, SV-04, C-06, D-05, AM-15 |
| P37, P39b, P39c, P39d | refusal leaving an **unflushed** change | **survived** | Findings 1–4 |
| P38, P39 | same, in `update_project` / `add_member` 400 | killed | U-14, AM-04 (their `session:` lines) |
| P40 | BUG-1958 correct fix (filter before paging) | L-07, L-08 pass with `--runxfail` | — |
| P41 / P42 | BUG-1958 wrong fix (filter before paging, but drops the privileged and member grants) | passes L-07 / L-08, killed by passing L-01, L-02, L-03, L-11 | — |

## Traceability
cases 279 · tests 279 (246 `def`s, 43 of them as `pytest.param(id=…)` rows) · unmatched: none · marker mismatches: none. 46 xfail cards: 43 `strict=True` and 3 `strict=False` (LM-03 BUG-1274, L-09 / L-10 BUG-1958), as their Expect lines say. Every reason names the card's bug, and every BUG ID exists in `bugs.md`. Each of the 46 fails under `--runxfail` on its card's Then line.

Fidelity: all 279 cards read against their tests. No findings:
- Access setups are as each card says: the caller in another project; owner or privileged in W0 / W2; suspended or inactive privileged; `created_by None`; ids above and below.
- The BUG-1958 rows really show the bug: three private projects first, then `limit=2` gives `[]`.
- `session:` lines come before any re-read.
- Only the clock and the `wraps=` commit spies are patched.
- `bulk` also sets four columns to their model defaults. Harmless.

## Commands run
```
COVERAGE_FILE=…\mgr6v\.cov_p
.venv/Scripts/python.exe -m pytest tests/unit/managers/test_project_manager.py -q -p no:cacheprovider --cov=app.managers.project_manager --cov-branch --cov-report=term-missing
  app\managers\project_manager.py  207  0  64  0  100%
  233 passed, 46 xfailed, 15 warnings in 18.67s
.venv/Scripts/python.exe -m pytest tests/unit/managers/test_project_manager.py -q -p no:cacheprovider --runxfail --tb=line -m xfail
  46 failed, 233 deselected — e.g. EV-08 "6 <= 3", L-07 set() == {V1, V2}, L-24 ['Zulu','apple','Banana'], G-07 TypeError include_deleted, U-32 '1000.5'
2 more plain runs (-rxX): 233 passed, 46 xfailed each; no XPASS, no flaky test
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/managers/project_manager.py tests/unit/managers/test_project_manager.py --timeout 300 --json …\mgr6v\mut_project.json
  Mutants: 200 · killed 196 · timeout 0 · survived 4 · score 98% (raw)
.venv/Scripts/python.exe …\mgr6v\variants.py project   (table above)
```

## For the coming features
- **Permissions.**
  - The rule is `can_access_project`: workspace-visible → anyone; otherwise the workspace owner, an **active** owner / GTM (exact strings), the creator, or a `project_members` row. That row is raw: someone who left the workspace still counts.
  - The rule trusts the `workspace_id` argument (Finding 5). Platform admins are not in it.
  - Anyone who may open a project may edit it, delete it, change its visibility, and add or remove members (spec FU-2). A role check there is the main gap.
  - `list_projects` filters in Python after paging (BUG-1958). The fix should put `can_access_project` into SQL. P41 shows that a fix which drops the privileged / member grants is caught.
  - 403 vs 404 for private projects is settled (OQ-18: 403 on project pages, 404 on discussions, files and calendar under OQ-5).
  - New refusal paths should come with cards that have `session:` lines (Findings 1–4).
- **Notifications.**
  - Nothing is sent. `log_event` already records `member_added`, `member_removed`, `visibility_updated`, `status_updated`, `updated`, `created` and `deleted`. These are the natural triggers (spec FU-3: adding or removing a member, or making a project private, notifies nobody).
  - `set_visibility` and `update_project` already skip no-op changes for the event. `update_project` still stamps them (BUG-1952). Notify after the service's commit.

## Round 2 — 2026-11-04
Scope: a narrow re-check of cases revision 2. It added `session:` lines to SV-04, SV-05, D-05, AM-12, AM-13, RM-05 and RM-06, and a new card PRJM-CA-33. `app/` is unchanged at e48a092.

- **Fidelity (8 tests read against their cards):**
  - All 8 are faithful.
  - Each new `session:` assertion is the card's exact expression and runs right after the `raises` block, before `unchanged` / `counts` (which expire). SV-04 / SV-05 / D-05 use `P not in db.dirty and not db.new`. AM-12 / AM-13 use `not db.new and not db.dirty`. RM-05 / RM-06 use `not db.deleted and not db.new`.
  - Later Then lines were renumbered as the cards say.
  - CA-33 builds a private W2 project and puts UG's member row under W2: `pmem` takes `p.workspace_id`. It calls with `workspace_id=W1.id` and asserts `result is False`.
- **Traceability:** cases 280 · tests 280 · unmatched none · marker mismatches none (46 xfail, unchanged).
- **Variants from round 1:** all now killed:
  - P03 (Finding 5) by CA-33; P03b now by CA-18 and CA-33.
  - P37 (Finding 1) by SV-04 and SV-05.
  - P39c (Finding 2) by D-05.
  - P39b (Finding 3) by AM-12 and AM-13.
  - P39d (Finding 4) by RM-05.
- **Runs:** 3 runs, each 234 passed, 46 xfailed, no XPASS. Branch coverage 100% (207 / 64).
- **Mutation:** not re-run. The source is unchanged and revision 2 only added assertions and one test, so no round-1 kill can be lost. The 4 round-1 survivors stay classified as 3 equivalent and 1 bug-path.

```
.venv/Scripts/python.exe …\mgr6v\trace.py …project_manager.cases.md …test_project_manager.py docs/testing/bugs.md PRJM
  cards 280 tests 280 xfail cards 46
.venv/Scripts/python.exe -m pytest tests/unit/managers/test_project_manager.py -q -p no:cacheprovider --cov=app.managers.project_manager --cov-branch --cov-report=term-missing
  app\managers\project_manager.py  207  0  64  0  100%  ·  234 passed, 46 xfailed in 23.11s
(-rxX) 234 passed, 46 xfailed in 11.61s · 234 passed, 46 xfailed in 10.15s
.venv/Scripts/python.exe …\mgr6v\variants.py project P03 P37 P39b P39c P39d   (log: mgr6v\var_project_r2.log)
  P03 1 failed (CA-33) · P03b 2 failed (CA-18, CA-33) · P37 2 failed (SV-04, SV-05) · P39b 2 failed (AM-12, AM-13) · P39c 1 failed (D-05) · P39d 1 failed (RM-05)
```
