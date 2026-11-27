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
| P1 | The pre-check timing is in pipeline.md, but the planner skill doesn't say who triggers it or whether planning waits for it. | Orchestrator runs the tester pre-check right after planning; units are "ready" only after it. Write this into both skills. | open |
| P2 | How to find a bug's spec is unclear: Spec links are relative (`../../tests/...`) and sometimes name two specs. | Tell the planner to resolve links relative to `docs/testing/`, and to copy from every spec named. | open |
| P3 | Copying only the bug rules hides sibling rules the fixer must not break. | Copy **all rules of each affected method**. | open |
| P4 | Rows naming two files without "(fix in X)" (BUG-2440) have no rule. | Skip such bugs, or make it a two-file unit with both files in scope. Decide. | open |
| P5 | What to strip from spec text is given only by example. | List it: "Verified by running" script paths, other spec paths under `tests/`, base-spec references (paraphrase them). | open |
| P6 | Status matching is fuzzy ("open (deferred)", "open — revisit after launch", "superseded by…"). | Exact rule: Status starts with `open` and contains none of: defer, revisit, future, superseded, note. | open |
| P7 | The planner's `trivial` misses §7's no-money/stock/workflow/security condition, and doesn't say whether every bug must be trivial or most. | Use the §7 definition verbatim: every bug trivial, plus the area exclusions. | open |
| P8 | No `state.md` header or status values, no "none" form for `questions.md`, and `wrong-tests.md` is never created. | Define the status values: planned → prechecked → fixing → review → testing → pr-open / parked. Give file templates. | open |
| P9 | "Prefer many trivial bugs" pulls toward big files. | Prefer moderate units (about 3–8 bugs), especially early. | open |
| P10 | Preconditions aren't stated: origin/main must match, and the brief lives in the main checkout. | Add a preconditions section. | open |
| P11 | The slug keeps underscores (`dao-order_template`). | Fine; state it. | open |

### Tools (batch 1)

| # | Finding | Change made | Status |
|---|---|---|---|
| T1 | The baseline flip check showed 2 failures in `tests/test_attachments.py`: it didn't set the dummy Cloudinary env that CI's legacy job sets. | `flipcheck.py run` sets `CLOUDINARY_*=ci` when they're unset. Baseline re-recorded. | done |

### Tester pre-check (batch 1)

| # | Finding | Proposed change | Status |
|---|---|---|---|
| A1 | It's unclear whether to create `wrong-tests.md` when a unit has none, and parallel testers could race to create it. | The planner creates `wrong-tests.md` once, with a header. | open |
| A2 | The `state.md` status after a pre-check isn't named, and neither is the status for a unit with every bug removed. | Use `prechecked`, and `dropped (all bugs wrong-tested)`. | open |
| A3 | `grep "BUG-<n>"` also hits specs, cases and verify files, and the bare number hits `.local-run.json`. | Search `tests/**/*.py` for markers first, then open the matching cards. | open |
| A4 | No rule for a non-strict xfail that already passes before the fix (physical-order tie). | The strict card is the proof; a non-strict pass is fine if the card allows it. | open |
| A5 | Running the target tests at pre-check is not mentioned; it takes seconds and confirms each failing line. | Add as a step. | open |
| A6 | Findings outside the unit (the same pattern in a caller in another file) have no home. | Add an "Outside this unit" section to `tester-precheck.md`. The systems engineer reads it, and the planner reads it for later batches. | open |
| A7 | Markers often use reason constants (`R2330 = "BUG-2330: …"`), so grepping for `BUG-<n>` near `xfail` misses them. | Pre-check: grep the bare number in `tests/**/*.py`, then map constants to their `xfail(... reason=CONST)` uses. (flipcheck is fine: it reads the runtime reason text.) | open |
| A8 | The "no wrong tests" path isn't described (create the file? re-run the firewall?), and `state.md` isn't given as a full path. | Add: "No wrong tests: leave wrong-tests.md alone, set `docs/bugfix/state.md` to `prechecked`." | open |
| A9 | A bug's tests can sit in callers' test files (manager or service). | Pre-check: also search the test files of every module that calls the unit's file. | open |
| A10 | Several testers edit `state.md` at once. | Re-read it right before a single one-row Edit. | open |
| A11 | Strict SQL-text checks (`".id" in order_part`) depend on how the fix is written: an ORM sort passes, a raw `text("id")` fails. | Accept them when a normal fix passes. The systems engineer warns about raw-SQL ordering. | open |

### Fixer (batch 1)

| # | Finding | Proposed change | Status |
|---|---|---|---|
| F1 | A script in `.scratch/` can't import `app` without `PYTHONPATH=.`. | Fixer instructions: run checks with `PYTHONPATH=.` from the worktree root, or `python -m`. | open |
| F2 | `ruff` leaves `.ruff_cache/` in the worktree (git-ignored). | Mention it as expected. | open |
| F3 | dao-order_template's fixer checked the generated SQL only, not tied rows against the DB. That's acceptable for a sort fix, but the instructions don't say when a DB repro is expected. | Say: reproduce against the test DB when the bug is about data or rows; SQL inspection is enough for pure ordering or query-shape bugs. | open |
| F4 | The guard blocks every git command, including `git diff --stat` on the fixer's own worktree. | Keep the block (the diff shows history and other refs). Say plainly that all git is off-limits, and that the fixer lists its changes in fix-notes. | open |
| F5 | `.scratch/` in the worktree vs the session scratchpad is ambiguous. | Say: the worktree's `.scratch/` only. | open |
| F6 | Building rows for a DB check means a long chain of required parents (plan, workspace, factory, section, type, profiles), so the fixer skipped checking BUG-2331 rows. | Give the fixer a small row-builder helper outside `tests/` (e.g. `scripts/bugfix/rowkit.py`), or let it import `tests/unit/factories.py` through a copied, test-free module. | open |

### Systems engineer (batch 1)

| # | Finding | Proposed change | Status |
|---|---|---|---|
| S1 | No status vocabulary for `state.md`. | Shared vocabulary (see P8). | open |
| S2 | Unclear whether `contract.md` is written when there's no change. | Always write it; "No contract change" means the frontend is skipped. | open |
| S3 | `grep "<name>("` matches same-named methods on other DAOs. | Also grep the DAO instance name (e.g. `order_template_item_dao`). | open |
| S4 | Callers that re-sort or re-filter a DAO result decide whether an order fix matters (stable `sorted`). | Add "callers that re-sort or re-filter" to the upstream checklist. | open |
| S5 | Unclear whether to run `blind` on approval. | No: blind only before a fixer round; the tester unblinds. | open |
| T2 | Testers running full-suite flip checks in parallel would share the `marker_gw*_test` databases. | Each unit runs with its own `TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/bf_<slug>_test`. conftest derives the worker databases from it. Put this in the tester skill. | applied by orchestrator in batch 1; skill update open |
| S6 | A caller's sibling fallback can hide a DAO fix end to end (work_order_template manager section fallback). | Upstream checklist: "when a caller merges the fixed result with another unfiltered path, check the intended behaviour still holds at the endpoint". | open |
| S7 | No way to record a newly found bug. | The systems engineer reports it; the orchestrator logs it in `bugs.md` from the owner range (done: BUG-3300). | open |
| S8 | Compiling the changed query with the Postgres dialect is a cheap check of joins and AND/OR precedence. | Add `scripts/bugfix/compile_query.py`, plus a skill step. | open |
| S9 | HR-16: new subqueries and joins need a workspace bound. | Checklist item: "is every new subquery bounded by workspace, directly or through the outer filter?" | open |
| S10 | A value-only change (same field, different value, e.g. `slot_count`) isn't covered by "contract change". | Define it: shape, status, message, **or meaning/value** changes are contract changes; the frontend agent decides if UI work is needed. | open |
| S11 | The reviewer didn't know to check `../frontend` for how a changed value is shown. | Step: grep `../frontend/src` for each changed response field. | open |
| S12 | Paths that bypass a guard (re-confirming a failed upload skips the capacity check). | Checklist: "for a guard change, find every path that reaches the guarded state without the guard". | open |
| S13 | A spec claimed a note existed in `docs/future/subscription-payments.md`, and the systems engineer said it didn't. It did (line 254). | Tell the systems engineer to grep before claiming a note is missing. It may append to `docs/future/*` itself. | open |
| S14 | `state.md` updates are named only for PARK. | Update the row on every verdict. | open |

### Tester run (batch 1)

| # | Finding | Proposed change | Status |
|---|---|---|---|
| T3 | Worktrees are cut from main, which lacks the uncommitted Cloudinary-dummy change to flipcheck. The tester had to export the env vars itself. | Commit the flipcheck change to main (batch-1 bookkeeping PR). | open |
| T4 | A relative `compare --json docs/bugfix/units/...` resolves against the worktree and fails. | Skill gives absolute main-checkout paths for the unit folder. | open |
| T5 | Worktrees have no `.venv`. | Skill: use the main checkout's interpreter. `app` imports from the worktree because pytest runs there. | open |
| T6 | `.scratch-flip/` isn't git-ignored, so it risks an accidental commit. | Add `.scratch-flip/` and `.scratch/` to `.gitignore`. | open |
| T7 | Where `pr.md` lives isn't specified, and there's no status for "branch pushed, PR not opened". | `pr.md` lives in the main-checkout unit folder; status is `branch-pushed`, then `pr-open` once a PR exists. | open |
| T8 | Worktrees have no `.env`, so the 2 Cloudinary legacy tests fail there. This caused a false REJECT on the first attachment_link run, and the flip check caught it as a non-target change. | Same fix as T3: flipcheck sets `CLOUDINARY_*=ci`. Once committed to main, worktrees get it. Never copy `.env`. | open (T3) |
| T9 | Quick spot-check pytest runs used the default `marker_test`. | Skill: every pytest call in C uses the unit's own `TEST_DATABASE_URL`. | open |
| T10 | Helper marker constants used only by this unit (`X1434 = pytest.mark.xfail(...)`) should go with their decorators. | Add to C3. | open |
| T11 | The raw xpassed total moves between runs (77 vs 97) because of non-strict ties. | Skill: never compare raw totals; only the compare verdict counts. | open |
| T12 | All 3 testers hit the Cloudinary false rejection. The real cause: `tests/test_attachments.py` patches `attachment_manager.settings`, but `cloudinary_client._ensure_configured` reads the core settings. | Short term: flipcheck dummies (T3). Long term: fix those 2 legacy tests through the test pipeline (added to the wrong-tests backlog). | open |
| T13 | The baseline `_meta` doesn't record the test environment (`TEST_DATABASE_URL`, `CLOUDINARY_*`). | flipcheck records the env names it depends on and warns about a mismatch before REJECT. | open |
| T14 | "Direct callers' test files" is vague. | Grep `tests/unit/managers` and `tests/unit/services` for the DAO instance names. | open |

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
| C3 | Every baseline and tester run was on Windows, so platform differences only show up in CI. | Treat CI (Linux, PG 18) as the reference. A tester's PR isn't "green" until GitHub CI passes. Consider running the baseline in CI too. | open |
