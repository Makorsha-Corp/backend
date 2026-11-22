# Execution notes — `app/dao/work_order_assignee.py`

> Cases: `tests/unit/dao/work_order_assignee.cases.md` (Revision 1, READY, 35 cases) · Tests: `tests/unit/dao/test_work_order_assignee.py` · Source commit: e48a092
> Result: **35 tests for 35 cases — 35 passed · 0 xfailed · 0 discrepancies · 0 errors** — branch coverage 100% line and branch (25 statements, 8 branches).
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/dao/test_work_order_assignee.py -q -p no:cacheprovider`

## Who wrote what
Normal mode, no local model: every test sits below a `# [claude] <ID>` comment, written by hand from the cards. `test_work_order_completer.py` is derived from this file by a substitution script of my own (`gen_woc.py`, scratch), as the completer cases file repeats these cards. My audit script (`check.py`, scratch, `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\attx\E`) checked: one test per ID in card order, title in the docstring, `# Then 1..N` matching the card, marker matching Expect, no unused argument. LF only.

## How the tests are built
- **Nothing is patched.** The "rolled back" convention's commit spy is fixture `commit_spy`: a `MagicMock(wraps=db.commit)` set on the session with `monkeypatch` (still callable, records calls).
- **Constants:** `dao`, `MISSING`, `TABLE`.
- **Standing rows** (autouse `standing_rows`): `w1`, `w2`, `u1`–`u4`, `f1`, `f9`, `wt1`, `wt9`, `wo1`, `wo2`, `wod`, `wo9`, each depending on the one before so ids rise in the Conventions' order. WO9 is built though no card names it.
- **Builder:** `mk_row(user_id=, **columns)` = "row".
- `bump(db, row)` = bumpA; `seqscan(db)` = the three `SET LOCAL` lines.
- **Reading helpers (no expected values inside):** `users_of(db, wo, ws)` and `row_ids_of(db, wo)` are the Conventions' SQL verbatim; `snap(db, row)` = every column by a Core select, for "unchanged" (snapshot after the last Given line); `stored_count(db)` = "nothing written".
- **`id_of(row)`** — WOA-RP-01 and RP-02 read `A.id`, `B.id` after the call deleted A and B; a plain `.id` after `expire_all()` raises `ObjectDeletedError`, so the id is read from the identity key (the same value).
- **re-read** lines run `db.expire_all()` before the SQL helper.
- **IntegrityError cards:** `with pytest.raises(IntegrityError) as exc:` around `with db.begin_nested():`; the re-reads after it see the savepoint rolled back.
- **Statement recorder:** `recorder.selects()` = every SELECT; `recorder.sql()` = the one SELECT from `work_order_assignees`; `recorder.written()`.
- WOA-RP-13 keeps the card's `loaded = list(WO1.assignee_links)` and `result = ...` as written (`noqa: F841`); no Then reads either.

## Order proof (no xfail cards)
`e_plug.py` (`-p e_plug`, `E_WO=<mode>`) replaces both reads in-process; nothing in `app/`:

| `E_WO` | Pass cards that fail (assignee + completer) |
|---|---|
| `none` (no ORDER BY) | WOA-GO-05, GO-10 (Then 3), GU-05; WOC-GO-05, GO-10 |
| `user` (`user_id`) | WOA-GO-01, GO-05, GU-01, GU-05; WOC-GO-01, GO-05 |
| `id_desc` | WOA-GO-01, GO-05, GU-01, GU-05; WOC-GO-01, GO-05 |
| `order_then_id` (`work_order_id DESC, id`) | none — the per-order lists are identical, so not a fault |

## Discrepancies
None.

## Spec gaps of the cases file, checked
- Gap 1: the guessed paths are right — `app.models.work_order.WorkOrder`, `app.models.work_order_type.WorkOrderType`, `app.models.factory.Factory`. `WorkOrder` needs no other NOT NULL column without a default (`priority`, `status`, `uses_inventory`, `created_at`, `is_active`, `is_deleted` all default). No change to any card.
- Gap 2: WOD carries `is_deleted True` only, as written.

## Coverage gaps
None — 100% line and branch coverage (private `COVERAGE_FILE`).

## Factories added
None.

## Stability
5 default runs, 5 forced plans (as in `project_component_task.notes.md`), database time zones `UTC` and `Asia/Dhaka`: `34 passed` in every one. No card compares a real-clock stamp. `ruff check`: all checks passed.

## Notes for maintainers
- Keep this file and `test_work_order_completer.py` in step: the cards are the same with the spec's substitutions.

## Revision history
- **Revision 1 of the cases (work_order_assignee.verify.md, case-missing findings):** added WOA-GU-10 (pass). Patched in place, no other test changed. 3 default runs, 5 forced plans (as above) and the database time zones `UTC` and `Asia/Dhaka`, `ruff check` passed, coverage with a private `COVERAGE_FILE`, LF only. Card audit (my own `audit.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\attx\R`): every ID once, in card order, `# Then 1..N` per card, markers as the Expect lines. Reference plugin `attxr_plug.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\attx\R` (`-p attxr_plug`, `ATTXR_MODE=ref`, in-process, nothing in `app/`; covers the seven revised modules): with `--runxfail` all 371 tests of the seven files pass, so the lines past every failure point hold. The verifier's named variants, rebuilt in the same plugin (`ATTXR_MODE=<variant>`, the reference with one change, `--runxfail`, default plan; each asserted applied): `gu_ws_le` → GU-10. No other test failed under any of them.
