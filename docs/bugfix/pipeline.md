# Bug-fix pipeline (design, draft 1, 2026-11-26)

How agents fix the bugs in `docs/testing/bugs.md`, and any future bug logged in
the same format. Status: **design for owner review**. No skills are built yet.

## 1. Principles

1. **The fixer never sees a test.** It fixes the behaviour described by the bug
   and its spec rule. Tests are the hidden exam.
2. **Only the intended tests may change.** After a fix, the only tests whose
   result changes are this unit's own xfail tests, which flip to pass. Any other
   change, in either direction, rejects the fix.
3. **Small units, one PR each.** One fix unit is one source file and the related
   bugs in it. Each unit gets its own branch and PR.
4. **Keep running.** Questions park one unit, not the whole loop.
5. **The owner decides business rules,** and only those the spec and
   `docs/testing/owner-questions.md` don't already settle.

## 2. Agents and flow

```
            ┌─────────── per batch of 3 units ───────────┐
 Planner ──►│ Fixer ─► Systems engineer ─► Tester ─pass─► Frontend ─► PR
 (briefs)   │   ▲           │      ▲          │                       │
            │   └─feedback──┘      └───fail───┘              trivial? comment "good to auto-merge"
            └────────────────────────────────────────────┘     owner always merges
```

### 2.1 Planner (once per batch)

- Reads `bugs.md` and picks the next **3 units** (one file each) that don't
  overlap: different files, and no unit that calls another unit's file.
  Order is bottom-up: DAO → manager → service → API.
- For each unit it writes a **fix brief**, `docs/bugfix/units/<unit>/brief.md`:
  - the bug rows (id, title, today, intended);
  - the spec rules they point to, **copied as text** (specs live under
    `tests/`, which the fixer can't see);
  - the house rules that apply (HR-15 rounding, HR-16 workspaces, refusals
    list blockers, …);
  - the relevant owner answers (OQ-…), copied as text.
- It filters the brief through the feedback firewall (§3) before handing it on.
- It tags the unit's risk: `trivial`, `normal`, `db-change`, or `owner-area`
  (money, stock, order workflow, security).
- **The tester's pre-check** (§2.4 step 1) runs here, before any fix exists.

### 2.2 Fixer (one per unit, in parallel)

- Works in its own **git worktree with `tests/` removed** (sparse checkout).
  It can't read tests, `.cases.md`, `.notes.md` or `.verify.md`, because they aren't there.
- Input: the fix brief, plus feedback from the systems engineer on later rounds.
- Makes the **smallest change in `app/`** that gives the intended behaviour. No
  refactors and no drive-by fixes. A second bug it notices goes in its report,
  not in its diff.
- It may write its own throwaway checks (scripts or a scratch pytest file) to
  reproduce the bug and confirm the fix. They're deleted before handing over.
- Writes `docs/bugfix/units/<unit>/fix-notes.md`: what it changed, why, and
  anything it was unsure about.
- Never touches tests and never removes xfail markers. The tester does both.

### 2.3 Systems engineer (impact check, static)

For every fix:
- **Upstream:** every caller of the changed functions, through services up to
  the API endpoints. Does any caller rely on the old behaviour?
- **Downstream:** what the changed code calls. Does the fix assume a DAO, lock
  or constraint behaves in a way it doesn't?
- **API contract:** changes to response shape, status codes, error messages or
  blocker lists. This becomes the **contract note** for the frontend agent.
- **Database:** a new constraint or migration. Can existing rows break it?
  If so, it writes a read-only check script (like
  `scripts/find_cross_workspace_rows.py`) and a separate repair script, and the
  unit becomes `owner-area`.
- **Neighbouring bugs:** does this fix clash with, or partly fix, another open
  bug?
- **Shortcuts:** special-casing one input instead of fixing the rule.
- Verdict: **approve** (to the tester) or **revise** (feedback to the fixer).

### 2.4 Tester

1. **Pre-check, at planning time, before any fix exists.** Reads the bug row,
   the spec rule and the unit's xfail tests, and judges whether each test
   checks the right thing.
   - **Test is right:** go on.
   - **Test is wrong:** record it in `docs/bugfix/wrong-tests.md` (§5) and
     **skip that bug for this round.** The other bugs in the unit go ahead.
2. **After the systems engineer approves:**
   1. Remove the xfail markers for this unit's bugs.
   2. Run the unit's test files. All must pass.
   3. Run the **flip check** (§4) over the full suite.
   4. **Pass** → frontend agent (if there's a contract note), then PR.
   5. **Fail** → a failure report to the **systems engineer only**, written as
      behaviour ("when X, the system must Y (spec R3c); today it does Z").
      The systems engineer weighs whether the failure points to a wider
      effect, then writes its own feedback to the fixer. Back to 2.2.

### 2.5 Frontend agent (only after the tester passes)

- Runs only when the systems engineer wrote a contract note. Sorting, locking
  and validation-only fixes usually need no frontend change.
- Works in `../frontend` on a branch with the same name as the backend branch.
- Input: the contract note. It doesn't need the backend diff.
- Must pass `npm run typecheck`, `npm run lint` and `npm test`. It runs
  `npm run test:e2e` when the change touches a page that has e2e coverage.
- Opens a frontend PR linked to the backend PR. **The backend merges first.**

## 3. The feedback firewall

Anything that reaches the fixer (the brief and every feedback message) is
checked by a script before it's delivered. It's rejected if it contains:
- a path under `tests/`, or the words `xfail`, `assert`, `pytest` or `fixture`;
- a card or test id (`RX8m`, `test_…`, `SR8c-…`);
- code copied from a test file.

The tester describes failures as behaviour plus a spec rule. That's fair to the
fixer, since the behaviour is the requirement. It just never sees how it's checked.

## 4. The flip check

A script (`tests/unit/_tools/flipcheck.py`, to be built):
1. **Before:** runs the full suite on the base commit (4 workers, about 6 min)
   and records each test id's outcome. This is cached per base commit.
2. **After:** runs it again on the fix branch.
3. **Allowed:** exactly this unit's bug tests go from xfail to passed.
   - Non-strict physical-order tests may go either way and are ignored.
4. **Anything else** (a pass turning into a failure, another bug's xfail
   flipping, a new error) **rejects the fix**, and the tester reports it as
   behaviour.

## 5. Wrong tests

`docs/bugfix/wrong-tests.md` gets one entry per wrong test:
- the bug id, test id and test file;
- why it's wrong, quoting the bug row and spec rule;
- **a proposed correction, as a diff**.

That bug is skipped this round. A later round sends these back through the
test pipeline (designer → executor → verifier), then the bug is fixed.

## 6. Loop control and questions

- **The loop runs until the tests pass.** If the same failure comes back twice
  in a row, the unit is **parked**, with a summary in
  `docs/bugfix/units/<unit>/parked.md`, and the batch moves on.
- **Questions don't stop the loop.** A question parks its unit in
  `docs/bugfix/questions.md`, and the other units keep going.
- **Ask the owner only for:**
  - a business rule on money, stock, order workflow or security that the
    spec and owner answers don't settle;
  - a change to existing production data (migrations or repairs);
  - an API change that breaks the frontend in a way users would notice;
  - anything security-sensitive.
- Everything else is decided by the agents and recorded as "decided by
  Claude under the reviewer's delegation (<date>)".

## 7. Branches, PRs and merging

- **Branch per unit:** `bugfix/<layer>-<module>`, for example
  `bugfix/dao-department`. It's cut from `main`.
- **PR per unit**, titled `fix(<module>): BUG-001, BUG-002, …`. The body
  lists the bugs, the systems engineer's impact summary, the flip-check
  result, and a link to the frontend PR if there is one.
- On merge, the tester's commit marks the bugs **Fixed** in `bugs.md` with the
  PR number.
- **No agent ever merges.** Every PR waits for the owner.
- When a unit is `trivial`, the tester leaves a PR comment:
  **"Good to auto-merge"**, plus the reasons. A unit is trivial when all of these hold:
  - one file, no migration, no API contract change, no frontend PR;
  - not money, stock, order workflow or security;
  - a pattern on the trivial list: `unordered-pagination`,
    `tied-timestamp-no-tiebreak`, `blank-name-accepted`,
    `audit-stamp-on-noop`, `falsy-zero-treated-as-missing`,
    `local-clock-instead-of-utc` (the list can grow as patterns prove safe);
  - the flip check is exact and CI is green.

## 8. Before the first batch

1. **Merge the test branch into `main`.** The bug-fix branches are cut from
   `main`, which needs the tests, `bugs.md` and the CI jobs first. That means
   resolving the 6 conflicts with the help-ticket commits and redoing the
   help-ticket tests.
2. **Install and log in to the GitHub CLI** on this machine, so agents can open PRs:
   `winget install GitHub.cli`, then `gh auth login`.
3. **GitHub settings:** protect `main` with the required checks `legacy`, `unit` and `migrations`.
4. ~~Build the tools and skills~~ **done 2026-11-26**:

   | Piece | File |
   |---|---|
   | Planner | `.claude/skills/bug-planner/SKILL.md` |
   | Fixer (agent with a guard hook) | `.claude/agents/bug-fixer.md`, `.claude/hooks/fixer_guard.py` |
   | Systems engineer | `.claude/skills/bug-systems-engineer/SKILL.md` |
   | Tester | `.claude/skills/bug-tester/SKILL.md` |
   | Frontend | `.claude/skills/bug-frontend/SKILL.md` |
   | Flip check | `tests/unit/_tools/flipcheck.py` |
   | Feedback firewall | `scripts/bugfix/firewall.py` |
   | Blind worktrees | `scripts/bugfix/worktree.py` |

   Unit folders: `docs/bugfix/units/<unit>/` in the main checkout. The fixer may
   open only `brief.md`, `feedback-<n>.md` and its own `fix-notes.md` there. The
   guard hook blocks everything else, plus `tests/`, test plans, test reports
   and git history. Batch state is in `docs/bugfix/state.md`, owner questions
   in `docs/bugfix/questions.md`, wrong tests in `docs/bugfix/wrong-tests.md`.
   `bug-fixer`, `bug-systems-engineer`, `bug-tester`, `bug-frontend`.

## 9. Decisions log

- **2026-11-26 (owner):**
  - the fixer never sees tests;
  - a systems engineer checks impact upstream and downstream;
  - the tester judges the test against the bug, then runs it;
  - failures go tester → systems engineer → fixer, never as test details;
  - the frontend agent runs only after the tests pass;
  - the owner is asked only about critical business decisions and
    high-impact things that aren't already settled;
  - the loop keeps running otherwise.
- **2026-11-26 (owner):**
  - a branch and PR per unit;
  - auto-merge only when extremely trivial (superseded below: comment only);
  - wrong tests are documented with a diff and skipped until a later round;
  - 3 units (files) at a time;
  - the frontend repo is `../frontend`.
- **2026-11-26 (owner):** no auto-merge. Agents open the PR. For a trivial
  unit they leave a comment saying it's good to auto-merge, and the owner merges.
