# Bug-fix pipeline: improvement log

Every friction point, workaround, guard gap or unclear instruction the agents hit,
and what we changed because of it. Reviewed after each batch; fixes go into the
skills (`.claude/skills/bug-*`), the fixer agent (`.claude/agents/bug-fixer.md`),
the guard (`.claude/hooks/fixer_guard.py`) or the tools (`scripts/bugfix/`,
`tests/unit/_tools/flipcheck.py`).

| # | Date | Stage | What happened | Change made | Status |
|---|---|---|---|---|---|
| 1 | 2026-11-27 | guard | Live test: Glob `**/test_*.py` from the repo root listed test file names. | Guard blocks glob-form test names, any Grep/Glob whose folder contains or is inside `tests/` or `docs/bugfix/`, and recursive shell search. Re-test 10/10. | done (8d0150c) |

## Batch 1 (2026-11-27)

_Notes collected while the batch runs._

### Planner (batch 1)

| # | Finding | Proposed change | Status |
|---|---|---|---|
| P1 | The pre-check timing is in pipeline.md, but the planner skill doesn't say who triggers it or whether planning waits for it. | Orchestrator runs the tester pre-check right after planning; units are "ready" only after it. Write this into both skills. | done 2026-11-27 (bug-planner rewritten) |
| P2 | How to find a bug's spec is unclear: Spec links are relative (`../../tests/...`) and sometimes name two specs. | Tell the planner to resolve links relative to `docs/testing/`, and to copy from every spec named. | done 2026-11-27 (bug-planner rewritten) |
| P3 | Copying only the bug rules hides sibling rules the fixer must not break. | Copy **all rules of each affected method**. | done 2026-11-27 (bug-planner rewritten) |
| P4 | Rows naming two files without "(fix in X)" (BUG-2440) have no rule. | Skip such bugs, or make it a two-file unit with both files in scope. Decide. | done 2026-11-27 (bug-planner rewritten) |
| P5 | What to strip from spec text is given only by example. | List it: "Verified by running" script paths, other spec paths under `tests/`, base-spec references (paraphrase them). | done 2026-11-27 (bug-planner rewritten) |
| P6 | Status matching is fuzzy ("open (deferred)", "open — revisit after launch", "superseded by…"). | Exact rule: Status starts with `open` and contains none of: defer, revisit, future, superseded, note. | done 2026-11-27 (bug-planner rewritten) |
| P7 | The planner's `trivial` misses §7's no-money/stock/workflow/security condition, and doesn't say whether every bug must be trivial or most. | Use the §7 definition verbatim: every bug trivial, plus the area exclusions. | done 2026-11-27 (bug-planner rewritten) |
| P8 | No `state.md` header or status values, no "none" form for `questions.md`, and `wrong-tests.md` is never created. | Define the status values: planned → prechecked → fixing → review → testing → pr-open / parked. Give file templates. | done 2026-11-27 (bug-planner rewritten) |
| P9 | "Prefer many trivial bugs" pulls toward big files. | Prefer moderate units (about 3–8 bugs), especially early. | done 2026-11-27 (bug-planner rewritten) |
| P10 | Preconditions aren't stated: origin/main must match, and the brief lives in the main checkout. | Add a preconditions section. | done 2026-11-27 (bug-planner rewritten) |
| P11 | The slug keeps underscores (`dao-order_template`). | Fine; state it. | done 2026-11-27 (bug-planner rewritten) |

### Tools (batch 1)

| # | Finding | Change made | Status |
|---|---|---|---|
| T1 | The baseline flip check showed 2 failures in `tests/test_attachments.py`: it didn't set the dummy Cloudinary env that CI's legacy job sets. | `flipcheck.py run` sets `CLOUDINARY_*=ci` when they're unset. Baseline re-recorded. | done |

### Tester pre-check (batch 1)

| # | Finding | Proposed change | Status |
|---|---|---|---|
| A1 | It's unclear whether to create `wrong-tests.md` when a unit has none, and parallel testers could race to create it. | The planner creates `wrong-tests.md` once, with a header. | done 2026-11-27 (bug-tester §A) |
| A2 | The `state.md` status after a pre-check isn't named, and neither is the status for a unit with every bug removed. | Use `prechecked`, and `dropped (all bugs wrong-tested)`. | done 2026-11-27 (bug-tester §A) |
| A3 | `grep "BUG-<n>"` also hits specs, cases and verify files, and the bare number hits `.local-run.json`. | Search `tests/**/*.py` for markers first, then open the matching cards. | done 2026-11-27 (bug-tester §A) |
| A4 | No rule for a non-strict xfail that already passes before the fix (physical-order tie). | The strict card is the proof; a non-strict pass is fine if the card allows it. | done 2026-11-27 (bug-tester §A) |
| A5 | Running the target tests at pre-check is not mentioned; it takes seconds and confirms each failing line. | Add as a step. | done 2026-11-27 (bug-tester §A) |
| A6 | Findings outside the unit (the same pattern in a caller in another file) have no home. | Add an "Outside this unit" section to `tester-precheck.md`. The systems engineer reads it, and the planner reads it for later batches. | done 2026-11-27 (bug-tester §A) |
| A7 | Markers often use reason constants (`R2330 = "BUG-2330: …"`), so grepping for `BUG-<n>` near `xfail` misses them. | Pre-check: grep the bare number in `tests/**/*.py`, then map constants to their `xfail(... reason=CONST)` uses. (flipcheck is fine: it reads the runtime reason text.) | done 2026-11-27 (bug-tester §A) |
| A8 | The "no wrong tests" path isn't described (create the file? re-run the firewall?), and `state.md` isn't given as a full path. | Add: "No wrong tests: leave wrong-tests.md alone, set `docs/bugfix/state.md` to `prechecked`." | done 2026-11-27 (bug-tester §A) |
| A9 | A bug's tests can sit in callers' test files (manager or service). | Pre-check: also search the test files of every module that calls the unit's file. | done 2026-11-27 (bug-tester §A) |
| A10 | Several testers edit `state.md` at once. | Re-read it right before a single one-row Edit. | done 2026-11-27 (bug-tester §A) |
| A11 | Strict SQL-text checks (`".id" in order_part`) depend on how the fix is written: an ORM sort passes, a raw `text("id")` fails. | Accept them when a normal fix passes. The systems engineer warns about raw-SQL ordering. | done 2026-11-27 (bug-tester §A) |

### Fixer (batch 1)

| # | Finding | Proposed change | Status |
|---|---|---|---|
| F1 | A script in `.scratch/` can't import `app` without `PYTHONPATH=.`. | Fixer instructions: run checks with `PYTHONPATH=.` from the worktree root, or `python -m`. | done 2026-11-27 (bug-fixer rule 5/6; rowkit.py, compile_query.py) |
| F2 | `ruff` leaves `.ruff_cache/` in the worktree (git-ignored). | Mention it as expected. | done 2026-11-27 (bug-fixer rule 5/6; rowkit.py, compile_query.py) |
| F3 | dao-order_template's fixer checked the generated SQL only, not tied rows against the DB. That's acceptable for a sort fix, but the instructions don't say when a DB repro is expected. | Say: reproduce against the test DB when the bug is about data or rows; SQL inspection is enough for pure ordering or query-shape bugs. | done 2026-11-27 (bug-fixer rule 5/6; rowkit.py, compile_query.py) |
| F4 | The guard blocks every git command, including `git diff --stat` on the fixer's own worktree. | Keep the block (the diff shows history and other refs). Say plainly that all git is off-limits, and that the fixer lists its changes in fix-notes. | done 2026-11-27 (bug-fixer rule 5/6; rowkit.py, compile_query.py) |
| F5 | `.scratch/` in the worktree vs the session scratchpad is ambiguous. | Say: the worktree's `.scratch/` only. | done 2026-11-27 (bug-fixer rule 5/6; rowkit.py, compile_query.py) |
| F6 | Building rows for a DB check means a long chain of required parents (plan, workspace, factory, section, type, profiles), so the fixer skipped checking BUG-2331 rows. | Give the fixer a small row-builder helper outside `tests/` (e.g. `scripts/bugfix/rowkit.py`), or let it import `tests/unit/factories.py` through a copied, test-free module. | done 2026-11-27 (bug-fixer rule 5/6; rowkit.py, compile_query.py) |

### Systems engineer (batch 1)

| # | Finding | Proposed change | Status |
|---|---|---|---|
| S1 | No status vocabulary for `state.md`. | Shared vocabulary (see P8). | done 2026-11-27 (bug-systems-engineer checklist) |
| S2 | Unclear whether `contract.md` is written when there's no change. | Always write it; "No contract change" means the frontend is skipped. | done 2026-11-27 (bug-systems-engineer checklist) |
| S3 | `grep "<name>("` matches same-named methods on other DAOs. | Also grep the DAO instance name (e.g. `order_template_item_dao`). | done 2026-11-27 (bug-systems-engineer checklist) |
| S4 | Callers that re-sort or re-filter a DAO result decide whether an order fix matters (stable `sorted`). | Add "callers that re-sort or re-filter" to the upstream checklist. | done 2026-11-27 (bug-systems-engineer checklist) |
| S5 | Unclear whether to run `blind` on approval. | No: blind only before a fixer round; the tester unblinds. | done 2026-11-27 (bug-systems-engineer checklist) |
| T2 | Testers running full-suite flip checks in parallel would share the `marker_gw*_test` databases. | Each unit runs with its own `TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/bf_<slug>_test`. conftest derives the worker databases from it. Put this in the tester skill. | applied by orchestrator in batch 1; skill update open |
| S6 | A caller's sibling fallback can hide a DAO fix end to end (work_order_template manager section fallback). | Upstream checklist: "when a caller merges the fixed result with another unfiltered path, check the intended behaviour still holds at the endpoint". | done 2026-11-27 (bug-systems-engineer checklist) |
| S7 | No way to record a newly found bug. | The systems engineer reports it; the orchestrator logs it in `bugs.md` from the owner range (done: BUG-3300). | done 2026-11-27 (bug-systems-engineer checklist) |
| S8 | Compiling the changed query with the Postgres dialect is a cheap check of joins and AND/OR precedence. | Add `scripts/bugfix/compile_query.py`, plus a skill step. | done 2026-11-27 (bug-systems-engineer checklist) |
| S9 | HR-16: new subqueries and joins need a workspace bound. | Checklist item: "is every new subquery bounded by workspace, directly or through the outer filter?" | done 2026-11-27 (bug-systems-engineer checklist) |
| S10 | A value-only change (same field, different value, e.g. `slot_count`) isn't covered by "contract change". | Define it: shape, status, message, **or meaning/value** changes are contract changes; the frontend agent decides if UI work is needed. | done 2026-11-27 (bug-systems-engineer checklist) |
| S11 | The reviewer didn't know to check `../frontend` for how a changed value is shown. | Step: grep `../frontend/src` for each changed response field. | done 2026-11-27 (bug-systems-engineer checklist) |
| S12 | Paths that bypass a guard (re-confirming a failed upload skips the capacity check). | Checklist: "for a guard change, find every path that reaches the guarded state without the guard". | done 2026-11-27 (bug-systems-engineer checklist) |
| S13 | A spec claimed a note existed in `docs/future/subscription-payments.md`, and the systems engineer said it didn't. It did (line 254). | Tell the systems engineer to grep before claiming a note is missing. It may append to `docs/future/*` itself. | done 2026-11-27 (bug-systems-engineer checklist) |
| S14 | `state.md` updates are named only for PARK. | Update the row on every verdict. | done 2026-11-27 (bug-systems-engineer checklist) |

### Tester run (batch 1)

| # | Finding | Proposed change | Status |
|---|---|---|---|
| T3 | Worktrees are cut from main, which lacks the uncommitted Cloudinary-dummy change to flipcheck. The tester had to export the env vars itself. | Commit the flipcheck change to main (batch-1 bookkeeping PR). | done 2026-11-27 (flipcheck change merged to main) |
| T4 | A relative `compare --json docs/bugfix/units/...` resolves against the worktree and fails. | Skill gives absolute main-checkout paths for the unit folder. | done 2026-11-27 (bug-tester env section) |
| T5 | Worktrees have no `.venv`. | Skill: use the main checkout's interpreter. `app` imports from the worktree because pytest runs there. | done 2026-11-27 (bug-tester env section) |
| T6 | `.scratch-flip/` isn't git-ignored, so it risks an accidental commit. | Add `.scratch-flip/` and `.scratch/` to `.gitignore`. | done 2026-11-27 (.gitignore) |
| T7 | Where `pr.md` lives isn't specified, and there's no status for "branch pushed, PR not opened". | `pr.md` lives in the main-checkout unit folder; status is `branch-pushed`, then `pr-open` once a PR exists. | done 2026-11-27 (status vocabulary + D.4) |
| T8 | Worktrees have no `.env`, so the 2 Cloudinary legacy tests fail there. This caused a false REJECT on the first attachment_link run, and the flip check caught it as a non-target change. | Same fix as T3: flipcheck sets `CLOUDINARY_*=ci`. Once committed to main, worktrees get it. Never copy `.env`. | done 2026-11-27 |
| T9 | Quick spot-check pytest runs used the default `marker_test`. | Skill: every pytest call in C uses the unit's own `TEST_DATABASE_URL`. | done 2026-11-27 (bug-tester env section) |
| T10 | Helper marker constants used only by this unit (`X1434 = pytest.mark.xfail(...)`) should go with their decorators. | Add to C3. | done 2026-11-27 (bug-tester C.3) |
| T11 | The raw xpassed total moves between runs (77 vs 97) because of non-strict ties. | Skill: never compare raw totals; only the compare verdict counts. | done 2026-11-27 (bug-tester C.4) |
| T12 | All 3 testers hit the Cloudinary false rejection. The real cause: `tests/test_attachments.py` patches `attachment_manager.settings`, but `cloudinary_client._ensure_configured` reads the core settings. | Short term: flipcheck dummies (T3). Long term: fix those 2 legacy tests through the test pipeline (added to the wrong-tests backlog). | open |
| T13 | The baseline `_meta` doesn't record the test environment (`TEST_DATABASE_URL`, `CLOUDINARY_*`). | flipcheck records the env names it depends on and warns about a mismatch before REJECT. | done 2026-11-27 (flipcheck records env, compare warns) |
| T14 | "Direct callers' test files" is vague. | Grep `tests/unit/managers` and `tests/unit/services` for the DAO instance names. | done 2026-11-27 (bug-tester A.1) |

### Batch 1 result

| Unit | Bugs | Flipped | Other changes | Commit | Branch |
|---|---|---|---|---|---|
| dao-order_template | BUG-1210, 1211 | 7 | 0 | 4fcd227 | bugfix/dao-order_template (trivial: "Good to auto-merge") |
| dao-attachment_link | BUG-1432, 1433, 1434 | 12 | 0 | 11db000 | bugfix/dao-attachment_link |
| dao-work_order_template | BUG-2330, 2331, 2332 | 9 | 0 | 23cb9e5 | bugfix/dao-work_order_template |

There were no feedback rounds and no wrong tests. The guard never blocked legitimate fixer work except git (F4). A new bug was found: BUG-3300.

### First CI run on GitHub (2026-11-27)

| # | Finding | Change made | Status |
|---|---|---|---|
| C1 | 5 tests expect Postgres 18's error code 23001 (`ON DELETE RESTRICT`); CI ran Postgres 16, which reports 23503. Production (Railway) is 18.6. | CI uses `postgres:18`, matching production and local. | done |
| C2 | `is_valid_iana_timezone("localtime")` is True on Linux (OS timezone files) and False on Windows (`tzdata` package). It's a real production bug hidden by Windows-only test runs. | BUG-3301 logged. The 2 tests are strict xfail wherever the OS timezone files include those names. | done |
| C3 | Every baseline and tester run was on Windows, so platform differences only show up in CI. | Treat CI (Linux, PG 18) as the reference. A tester's PR isn't "green" until GitHub CI passes. Consider running the baseline in CI too. | done 2026-11-27 (bug-tester: CI is the reference platform) |

### Owner feedback (2026-11-27)

| # | Finding | Change made | Status |
|---|---|---|---|
| O1 | PR descriptions were written for the pipeline, not for a human reviewer. | `bug-tester` D.4 now gives a reviewer-first template: human title, what was wrong with a concrete example, a small commented diff, what you'll notice, what to look at, and pipeline checks collapsed. The batch-1 `pr.md` files are rewritten to match. | done |
| C4 | WOM-GI-01 asserted id order on a list with no ORDER BY (BUG-1272) but was a plain "pass" card. It passed by chance on Windows and failed on Linux CI. | Made it non-strict `xf(1272)`; card revised. **Lesson for the test designer and verifier:** any pass card that checks the order of a list whose sort is a known bug must be non-strict xfail for that bug. A sweep of other such cards is worth doing (verifier task). | done (sweep open) |


### Applied after batch 1 (2026-11-27)

The skills, the fixer agent and the tools are updated with the findings above. New tools:
`scripts/bugfix/rowkit.py` builds rows with every required parent, in a transaction
that is always rolled back. `scripts/bugfix/compile_query.py` prints a DAO method's SQL
without a database. Still open: T12 (fix the 2 Cloudinary legacy tests through the
test pipeline), T13 (record the test environment in the baseline metadata), C4 sweep (running).

## Batch 2 (2026-11-27)

### Planner (batch 2)

| # | Finding | Proposed change | Status |
|---|---|---|---|
| P12 | The local checkout was behind `origin/main`, so `bugs.md` statuses were stale. | §0: `git merge origin/main` into the working branch before planning, or read `git show origin/main:docs/testing/bugs.md`. | open |
| P13 | The planner had to write its own `bugs.md` parser. "Names two files" is tricky because "reached through … via `app/services/...`" mentions aren't fix locations. | Add `scripts/bugfix/open_bugs.py --layer dao`, counting only fix locations. | open |
| P14 | Bugs tied to another unit's bug ("goes away with BUG-908") aren't covered. | Skip them, or plan them with the bug they depend on. | open |
| P15 | There's no status for "briefed, worktree deferred". | Add `briefed`. The orchestrator flips it to `planned` when it creates the worktree. | open |
| P16 | Unclear whether a brief may carry an implementation hint from the spec ("import utcnow the way `machine.py` does"). | Yes, if the spec or the row already says it; never invent one. | open |

### Tester pre-check (batch 2)

| # | Finding | Proposed change | Status |
|---|---|---|---|
| A12 | A **wrong label** (the test checks the right thing, but its marker leaves out a second bug it needs) is different from a wrong check. Skipping the whole bug would be overkill. | §A.4: record a marker-only diff, apply it before the baseline (the flip check reads bug ids from the baseline's reasons), and keep the bug in the unit. Done this batch: MMLM-G-21/22 now name BUG-1101 and BUG-1150. | open (skill) |
| A13 | Read the cards' "Fails today on" lines early: a TypeError, a missing parameter or another bug's new API means the marker must name that bug too. | Add to §A.1 and §A.3. | open |
| A14 | Clock bugs: check that the expected value is a patched constant (so the test is time-zone independent) and the patch target is a module-level name. Warn the systems engineer when the code uses function-local imports. | Add to §A.3. | open |

### Order sweep (2026-11-27)

| # | Finding | Change made | Status |
|---|---|---|---|
| C5 | The suite was run with every query's row order forced, ascending and descending. 3 pass tests relied on luck: PRJM-L-11 (BUG-100) and POS-AR-02/08 (BUG-2431). 8 strict xfails passed under one forced order, so they could go red on CI. | All 11 are now non-strict with their bug, and the cards are revised (`docs/bugfix/order-sweep-2026-11-27.md`). The tool is reusable: `makorsh-pipeline/order_sweep/plug/order_perturb.py`. Consider adding it to the tools as a periodic check. | done |
| C6 | BUG-2293, 2298, 2308 and 2611 (project areas) now have only a statement-count strict card, with no strict paging card. | Add a deterministic skip-case card for each. Revisit after launch (projects deferred). | open (after launch) |
| A15 | **A simulated fix at pre-check** (a scratch plugin that swaps the DAO method in memory, then runs the callers' files with and without it) showed a correct DAO-only fix breaks 2 passing manager tests (factory_section include_deleted). It cost no fixer round. | Make it a §A step for soft-delete, join-filter and other behaviour-narrowing fixes. | open |
| A16 | Planner: a DAO-only soft-delete or join-filter fix breaks callers that rely on the raw list (manager `include_deleted` paths). | §1 check: grep the callers for `include_deleted` or similar. If any rely on the raw list, put the caller in scope (two-file unit) or hold the bug back. Applied to dao-factory_section (now DAO + manager pass-through). | open |
| A17 | With `-rA`, a strict xfail that now passes shows as FAILED. | Say so in §C so testers don't count those as regressions. | open |
| A18 | Statement-count tests ("exactly one SELECT") constrain how a fix may be written, like SQL-text tests do. | Extend the A.3 note; pass it to the systems engineer as plain behaviour ("read in one query"). | open |
| A19 | Concurrency bugs: single-session stale-object tests can't tell a real relative UPDATE from a re-read-then-write shortcut (item_tag BUG-931). | Pre-check: for atomic-update bugs, require a SQL check on the UPDATE. Applied: ITG-INC-11 and DEC-13 got a Then 4 (cards revised). Same gap expected in account_tag BUG-1484. | open (skill) |
| A20 | "Would a correct fix pass?" is best answered by running candidate fixes (one correct, one plausible-but-wrong, one shortcut) through a scratch plugin, not by reasoning. | Make it the standard §A method, together with A15. | open |
| A21 | The "conditional keep" route (BUG-1101, BUG-931): when a test correction only adds checks and doesn't change today's outcome, the bug stays in the unit if the correction lands before the baseline. | Write it into §A.4. | open |

### Batch 2 fix round (2026-11-27)

| Id | Seen | Fix |
|---|---|---|
| A22 | machine_maintenance_log fixer fixed without reproducing the bugs first (the SE had to confirm the old code really had them). | Fixer rule: reproduce before changing, or say "not reproduced" and why. |
| A23 | Fixers' "Seen, not fixed" lists real candidates: `app/dao/machine.py` pages with no ORDER BY; account_tag BUG-1484 has the same counter pattern as BUG-931. | Planner: read fix-notes "Seen, not fixed" when planning the next batch. |
| T15 | `flipcheck.py run --out .scratch-flip/after.json` does not create the folder; the run (~7 min) is lost with FileNotFoundError at session finish. | flipcheck: `out.parent.mkdir(parents=True, exist_ok=True)`.  **Done 2026-11-27.** |
| T16 | `compare --bugs` takes a comma list; space-separated ids are rejected. | Skill C.4: show the comma form.  **Done 2026-11-27.** |
| T17 | Removing a unit's markers was done by an ad-hoc script each time (one-line and multi-line decorators, shared reasons). | Tool `scripts/bugfix/remove_markers.py`: drop a decorator only when every BUG id in it belongs to the unit. |
| O2 | PowerShell `Set-Content -Encoding utf8` adds a BOM to state.md; `ConvertFrom-Json` can't read the baseline (case-only duplicate test ids). | Orchestrator: edit docs with the Edit tool or Python; read JSON with Python. |
| T18 | `compare` stays silent about non-strict tests it let move (xfailed <-> xpassed); confirming the pre-check's predicted XPASSes needed a hand diff. | flipcheck: list "ignored non-strict changes" in the output and JSON.  **Done 2026-11-27.** |
| O3 | Orchestrator prompt used `bf_factory_section_test`; the skill's naming rule gives `bf_dao_factory_section_test`. Harmless. | Orchestrator: take the db name from the skill rule (`bf_<unit>_test`). |
| T19 | Hand-written marker regexes missed two single-line markers (caught by re-grepping). | Skill C.3: always re-grep `xfail(.*BUG-<ids>` after removal (covered by T17's tool). |
| P17 | Pre-check guessed caller test file paths wrong (`test_item_tag_assignment.py` is under dao/). | Pre-check lists caller test files by full path, found with Grep, not guessed. |

### Batch 2 result

All 3 units CLEAN on the first round, no fixer feedback rounds, no contract changes: dao-machine_maintenance_log (46 flipped, `5966805`), dao-factory_section (16 flipped, `cab794a`), dao-item_tag (11 flipped, `10ac8de`). All three testers lost one full run to T15.
| R1 | Fixers write bug ids into code comments/docstrings (both reviewers flagged it as a minor: nothing else in `app/` does). | Fixer rule: explain the why in comments, never cite BUG ids; ids go in fix-notes and the commit. |
| R2 | Parallel reviewers overwrote each other's `chk.py` in the shared session scratchpad. | Orchestrator prompts give each agent its own scratch subfolder (`scratchpad/<unit>/`). |

### Planner and pre-check (batch 3)

| Id | Seen | Fix |
|---|---|---|
| P18 | Rows that name a DAO only through a "via" mention (BUG-342/343 → `machine.py`) get excluded by the two-file rule even when the fix belongs in the DAO. | Planner skill: say which file owns a row (the file the fix changes, not the file the title names). |
| P19 | Clock-bug tests that patch the old `<module>.datetime` name without `create=True` break when the clean fix drops that import (BUG-1441: 33 errors). | Pre-check: for clock bugs, check every patched name survives the clean fix; test designer: patch old and new names with `create=True`. |
| P20 | Unclear whether a fixer may leave a now-unused import to keep tests green. | Fixer rule: remove imports the fix makes unused (ruff F401); the pre-check must make tests tolerate that. |
| P21 | Caller tests passed a plain string where the contract is an enum (BUG-886), so a correct fix failed them. | Pre-check: compare each caller test's argument types against the spec signature. |
