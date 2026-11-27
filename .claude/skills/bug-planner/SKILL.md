---
name: bug-planner
description: Bug-fix pipeline stage 1. Picks the next batch of fix units (one source file each, default 3) from docs/testing/bugs.md, sets up each unit's folder and blind worktree, and writes each unit's fix brief - the ONLY input the bug-fixer ever sees. Use at the start of every bug-fix batch (docs/bugfix/pipeline.md).
---

# Bug planner

You turn open rows in `docs/testing/bugs.md` into **fix units** and write the
brief the fixer works from. Read `docs/bugfix/pipeline.md` first.

All paths below are relative to the **main checkout** (`E:\Projects\Makorsh-Corp\backend`)
unless they say "worktree". Python is the main checkout's venv
(`.venv/Scripts/python.exe` on Windows, `.venv/bin/python` elsewhere); worktrees have none.

## 0. Preconditions

- `git fetch origin`. The unit files must be the same on `origin/main` as in the
  main checkout (`git diff origin/main -- <file>` is empty). Units are cut from
  `origin/main`.
- `docs/testing/bugs.md` on `origin/main` must have the same rows for your bugs
  (`git diff origin/main -- docs/testing/bugs.md`). If main is ahead, plan from main.
- Create these once if missing, with a short header:
  - `docs/bugfix/state.md`, with columns `| Unit | File | Bugs | Risk | Status | Date |`.
  - `docs/bugfix/questions.md`, with sections `## Open` and `## Answered`, and "_none_" when empty.
  - `docs/bugfix/wrong-tests.md`, with a header only.

  Creating them yourself means parallel testers never race to create them.

**Status values** for `state.md`, used by every stage:
`planned → prechecked → fixing → review → approved → testing → branch-pushed → pr-open → merged`,
or `parked` / `dropped` (with a reason).

## 1. Pick the batch

- A unit is **one source file** in `app/` plus the open bugs whose Module column
  names it in backticks. A row that says "(fix in X)" belongs to X's unit.
- **Open means:** Status starts with `open` and contains none of `defer`,
  `revisit`, `future`, `superseded`, `note`, `withdrawn`. Skip frontend-only notes and
  future work (notifications, permissions, subscription portal).
- **A bug that names two files without "(fix in X)"** (for example BUG-2440,
  `sales_order.py` and `sales_delivery.py`): leave it out of single-file units.
  Plan it later as a two-file unit, with both files in scope, in a batch where neither file has another unit.
- Skip bugs that are in `docs/bugfix/wrong-tests.md` (waiting on a test fix),
  in `docs/bugfix/questions.md` → Open, or already in a unit in `state.md`.
- **Order bottom-up:** `app/dao` → `app/managers` → `app/services` → `app/api` → others.
- **Unit size:** prefer about **3–8 bugs** per unit. Don't chase files with many
  bugs early on; big units make big PRs.
- **No overlap within a batch:**
  - the units' files must differ;
  - no unit's file may import another unit's file (`grep -n "^from app" <file>`);
  - skip a file that already has an open `bugfix/*` branch (`git branch -r | grep bugfix/`).
- Default batch size is 3 (owner, 2026-11-26).
- Out of scope: production modules (`docs/future/production-revamp.md`) and
  project costing (deferred until after launch).

## 2. Tag each unit's risk

Use pipeline.md §7 exactly.

- **`owner-area`:** a bug about money (prices, payments, invoices, ledgers,
  balances), stock, order workflow, or security whose intended behaviour is NOT
  already settled by the bug row, the spec or `docs/testing/owner-questions.md`.
  Put the exact question in `docs/bugfix/questions.md` → Open, and leave that bug
  out of the brief. The rest of the unit goes ahead.
- **`db-change`:** the fix needs a migration (unique index, constraint, column, NOT NULL).
- **`trivial`:** all of the following hold:
  - **every** bug's pattern is on the trivial list;
  - one file;
  - not `db-change`;
  - **and** no bug touches money, stock, order workflow or security, even if settled.
- **`normal`:** everything else.

## 3. Set up the unit

The slug is `<layer>-<module>`, keeping underscores (for example `dao-order_template`).

```
python scripts/bugfix/worktree.py create <unit>     # branch bugfix/<unit> from origin/main
python scripts/bugfix/worktree.py blind  <unit>     # tests/ and pipeline notes removed for the fixer
```

Make the folder `docs/bugfix/units/<unit>/` in the **main checkout**. The brief
lives there, not in the worktree.

## 4. Write `brief.md`

The fixer sees nothing but this file and later feedback. It must be complete,
and it must not leak any test. Sections:

1. **Unit:** slug, source file, worktree path, branch, risk tag.
2. **Bugs:** one block per bug, with id, title, pattern, "Where", "Today" and
   "Intended" copied from the row as text (no links).
3. **Intended behaviour:** for **each affected method**, copy **all** of its
   spec rules, not just the bug rules, so the fixer can see what must not break
   (paging limits, error cases, keyword-only parameters, and so on).
   - **Finding the spec:** the row's Spec column links relative to
     `docs/testing/` (`../../tests/unit/<layer>/<m>.spec.md`; sometimes
     `../../../`, or two specs). Resolve every link and copy from each spec named.
   - **Copy only rule text.** Leave out:
     - the "Cases" and "Notes for the test designer" sections;
     - "Verified by running" notes and the script paths in them;
     - card ids and test names;
     - paths to other specs or files under `tests/`.

     Paraphrase references to the base spec (for example "per `base_service` TC3")
     into plain words. Keep the spec's rule ids (R3c) so feedback can refer to them.
4. **Rules that apply:** the house rules (`docs/testing/house-rules.md`, HR-n)
   and owner answers (OQ-n) that touch these bugs, copied as text. Write
   "No owner answer touches these bugs" if none do.
5. **Scope:** the file(s) the fix may change. For `db-change`, say a migration is expected.
6. **Out of scope:** other open bugs in the same file, or in its callers, that
   are NOT in this unit (id and one-line title), so the fixer leaves them alone.

Then run the firewall. It must print `clean`:

```
python scripts/bugfix/firewall.py docs/bugfix/units/<unit>/brief.md
```

If it rejects the brief, reword it (describe behaviour, keep rule ids) until it is clean.

## 5. Record and hand over

- Add a row per unit to `docs/bugfix/state.md` with status `planned`. Re-read the
  file right before one single edit; other agents edit it too.
- Questions go to `questions.md` → Open, in the form
  `- **Q-<unit>-<n>** (<area>): <plain question with a worked example in taka> — bugs: <ids> — status: open`.
- **Next stage:** the orchestrator runs the tester's **pre-check** (bug-tester §A)
  on each unit. A unit is ready for the fixer only when `state.md` says `prechecked`.

Report: the units, their bugs and risk tags, firewall results, any questions
parked, and anything in this skill that was unclear (under "Skill improvements").
