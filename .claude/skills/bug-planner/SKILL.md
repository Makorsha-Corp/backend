---
name: bug-planner
description: Bug-fix pipeline stage 1. Picks the next batch of fix units (one source file each, default 3) from docs/testing/bugs.md, sets up each unit's folder and blind worktree, and writes each unit's fix brief - the ONLY input the bug-fixer ever sees. Use at the start of every bug-fix batch (docs/bugfix/pipeline.md).
---

# Bug planner

You turn open rows in `docs/testing/bugs.md` into **fix units** and write the
brief the fixer works from. Read `docs/bugfix/pipeline.md` first.

## 1. Pick the batch

- A unit is **one source file** in `app/` plus the open bugs whose Module column
  names it (the file in backticks). A bug row that names a file "(fix in X)" belongs
  to X's unit.
- Status must be open: skip rows that are Fixed, Withdrawn, deferred, "revisit
  after launch", frontend-only notes, and future work (notifications,
  permissions, subscription portal).
- Skip bugs already in `docs/bugfix/wrong-tests.md` (wrong test, later round) or in
  `docs/bugfix/questions.md` (waiting for the owner), and units already in
  `docs/bugfix/state.md`.
- **Order bottom-up:** `app/dao` → `app/managers` → `app/services` →
  `app/api` → others. Within a layer, prefer files with many bugs of a
  `trivial`-listed pattern first.
- **No overlap within a batch:** the units' files must differ, and no unit's
  file may import another unit's file (`grep -n "^from app" <file>`). Also skip a
  file that has an open `bugfix/*` branch already.
- Default batch size is 3 (owner, 2026-11-26).
- Production modules and project-costing modules are out of scope (see
  `docs/future/production-revamp.md`, projects deferred).

## 2. Tag each unit's risk

- `owner-area`: any bug about money (prices, payments, invoices, ledgers,
  balances), stock, order workflow, or security, whose intended behaviour is NOT
  already settled by the bug row, the spec or `docs/testing/owner-questions.md`.
  Write the exact question to `docs/bugfix/questions.md` (format below) and
  leave that bug out of the brief. The rest of the unit still goes ahead.
- `db-change`: the intended fix needs a migration (unique index, constraint,
  column, NOT NULL).
- `trivial`: every bug's pattern is on the trivial list in pipeline.md §7, the
  unit is one file, and nothing is `db-change` or `owner-area`.
- `normal`: everything else.

## 3. Set up the unit

For unit slug `<layer>-<module>` (for example `dao-department`):

```
python scripts/bugfix/worktree.py create <unit>     # branch bugfix/<unit> from origin/main
python scripts/bugfix/worktree.py blind  <unit>     # tests/ removed before the fixer runs
```

Make the folder `docs/bugfix/units/<unit>/` in the **main checkout**.

## 4. Write `brief.md`

The fixer sees nothing but this file and later feedback. It must be complete,
and it must not leak any test. Sections:

1. **Unit:** slug, source file, worktree path, branch, risk tag.
2. **Bugs**, one block per bug: id, title, "Today" and "Intended" from the row,
   the pattern. Copy the text; do not link to it.
3. **Intended behaviour:** for each bug, the spec rules it points to, **copied
   as plain text** from the `.spec.md` under `tests/` (the fixer can't open specs).
   Copy the rule text only: no "Cases"/"Notes for the test designer" sections,
   no card ids, no test names. Keep the spec's rule ids (R3c) so feedback can
   refer to them.
4. **Rules that apply:** the house rules (`docs/testing/house-rules.md`,
   HR-n) and owner answers (OQ-n) that touch these bugs, copied as text.
5. **Scope:** the file(s) the fix may change. For `db-change`, note that a
   migration is expected.
6. **Out of scope:** other open bugs in the same file that are NOT in this unit
   (so the fixer leaves them alone).

Then run the firewall. It must print `clean`:

```
python scripts/bugfix/firewall.py docs/bugfix/units/<unit>/brief.md
```

If it rejects the brief, reword (describe behaviour, keep spec rule ids) until clean.

## 5. Record

Append each unit to `docs/bugfix/state.md` (create it if missing):
`| <unit> | <file> | <bug ids> | <risk> | planned | <date> |`.

Questions go to `docs/bugfix/questions.md`:
`- **Q-<unit>-<n>** (<area>): <plain question with a worked example in taka> — bugs: <ids> — status: open`.

Report: the units, their bugs and risk tags, and any questions parked.
