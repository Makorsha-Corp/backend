# Makorsh backend: notes for Claude

FastAPI + SQLAlchemy + Postgres backend. Code lives in `app/`
(`dao/` → `managers/` → `services/` → `api/`).

## Unit-test pipeline (tests/unit/)

Every module in `app/` gets five artifacts in `tests/unit/<layer>/`, made by
the skills in `.claude/skills/`:

| Stage | Skill | Writes |
|---|---|---|
| 1 describe / apply-review / fill-gaps | `test-describer` | `<m>.spec.md` |
| 2 case design (never reads app/) | `test-case-designer` | `<m>.cases.md` |
| 3 tests | `test-executor` | `test_<m>.py`, `<m>.notes.md` |
| 4 verify (read-only, mutation testing) | `test-verifier` | `<m>.verify.md` |

Batch workflows: `.claude/workflows/test-pipeline-describe.js` (args.files)
and `test-pipeline-run.js` (args.items). Pass `args.root` with the absolute
path of this checkout if it is not `E:\Projects\Makorsh-Corp\backend`.
Work bottom-up: the DAOs a manager uses, then the manager, then the service.

Status: all 215 in-scope modules PASS (2026-11-22). Still to do: the
**production** modules (see `docs/testing/HANDOFF.md`) and project
attachments (deferred until after launch).

### Running tests

- Python: `.venv/Scripts/python.exe` on Windows, `.venv/bin/python` on
  macOS/Linux. The skills write the Windows form; use the right one.
- Needs Postgres. `TEST_DATABASE_URL` defaults to
  `postgresql://postgres:postgres@localhost:5432/marker_test`; the name must
  end in `_test`. The database is created and migrated automatically.
- Full suite: `python -m pytest tests/unit -o addopts=""` (about 16 minutes).
- Each test runs in a rolled-back transaction; nothing is ever committed.
- Known bugs are strict `xfail` tests tagged with their BUG id. A strict
  xfail that starts passing means the bug was fixed: remove the marker.

### Rules (from the owner)

- **Never edit `app/` while testing.** Code that is wrong is a bug in
  `docs/testing/bugs.md` plus an xfail test, not a fix.
- Never commit or push unless asked.
- `docs/testing/house-rules.md` (HR-1…) is applied without asking. Key ones:
  money rounds **half up** (HR-15); links across workspaces are **never**
  allowed and are treated as invalid data (HR-16).
- Previous owner decisions are in `docs/testing/owner-questions.md`. Do not
  re-ask anything answered there.
- Review questions: decide them yourself by best practice and record
  "decided by Claude under the reviewer's delegation (<date>)". **Ask the
  human in chat only for money, stock, order workflow, and security**, in plain
  language with a worked example in taka. Record every answer in
  `owner-questions.md`.
- A refused delete or change lists what blocks it (no ids from another
  workspace). The frontend part goes in `bugs.md` as a note.
- Projects (project costing) are deferred: test today's behaviour, log no
  bugs, tag "revisit after launch".
- Notifications, permissions, and the SSLCommerz subscription portal are
  future work: put findings in `docs/future/*.md`, not as bugs.

### Bug ids

Every bug gets a unique `BUG-<n>` in `docs/testing/bugs.md`. To avoid
collisions between people working in parallel, use your own range:

- main sweep (owner): up to BUG-4999 (last used: BUG-3229)
- production testing: **BUG-5000…5999**

Hand each module in a batch its own block of 20–50 ids inside your range.
