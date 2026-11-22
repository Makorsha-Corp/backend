# Execution notes — `app/dao/work_order_completer.py`

> Cases: `tests/unit/dao/work_order_completer.cases.md` (READY, 25 cases) · Tests: `tests/unit/dao/test_work_order_completer.py` · Source commit: e48a092
> Result: **25 tests for 25 cases — 25 passed · 0 xfailed · 0 discrepancies · 0 errors** — branch coverage 94% (25 statements, 2 missed: lines 36–45, `get_user_ids_by_order`, dead code; 8 of 8 branches).
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/dao/test_work_order_completer.py -q -p no:cacheprovider`

## Who wrote what
Normal mode, no local model: every test sits below a `# [claude] <ID>` comment. The file is `test_work_order_assignee.py` passed through a substitution script of my own (`gen_woc.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\attx\E`): DAO, model, table, constraint `uq_wo_completer_wo_user`, relationship `completer_links`, `WOA` → `WOC`, and the GU section dropped. The script refuses to write if any "assignee" text or GU test is left. My audit script (`check.py`) then checked it against this cases file: one test per ID in card order, title, `# Then 1..N`, marker, no unused argument — OK. LF only.

## How the tests are built
As in `work_order_assignee.notes.md`, with `TABLE = "work_order_completers"` and `Row = WorkOrderCompleter`; `bump` is the card's bumpC.

## Order proof
See the assignee notes: `E_WO=none` fails WOC-GO-05 and GO-10; `user` and `id_desc` fail WOC-GO-01 and GO-05.

## Discrepancies
None.

## Spec gaps of the cases file, checked
- Gap 1: the guessed paths are right (`app.models.work_order`, `app.models.work_order_type`, `app.models.factory`); no other NOT NULL column is needed.
- Gaps 2–4: as written; nothing to change.

## Coverage gaps
| Lines | Kind | What the code does there |
|---|---|---|
| 36–45 | dead | `get_user_ids_by_order`: the single-order read, dead code here (spec P3; `docs/testing/dead-code-removal-checklist.md`) |

## Factories added
None.

## Stability
5 default runs, 5 forced plans, time zones `UTC` and `Asia/Dhaka`: `25 passed` in every one. No card compares a real-clock stamp. `ruff check`: all checks passed.
