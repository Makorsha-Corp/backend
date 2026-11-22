# Execution notes — `app/dao/workspace_member.py`

> Cases: `tests/unit/dao/workspace_member.cases.md` (Revision 1, READY, 54 cases) · Tests: `tests/unit/dao/test_workspace_member.py` · Source commit: e48a092
> Result: **54 tests for 54 cases — 49 passed · 5 xfailed · 0 discrepancies · 0 errors** — branch coverage 100% (22 statements, 2 branches). The two non-strict cards may XPASS without turning the run red (seen only under `PGOPTIONS=-c enable_seqscan=off`, see Stability).
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/dao/test_workspace_member.py -q -p no:cacheprovider`

## Who wrote what
Normal mode, no local model: every test sits below a `# [claude] <ID>` comment, in card order, written by hand from the cards.

## How the tests are built
- **Nothing is patched**; no method reads the clock.
- **Constants:** `dao` (the singleton), `MISSING = 999999999`; xfail reasons `BUG_1400` / `BUG_1400_NON_STRICT`.
- **Standing rows:** `w1`, `w2`, `u1`, `u2`, `u3` from `make_workspace` / `make_profile`, chained fixtures so ids rise in Conventions order, all pulled in by the autouse `standing_rows`.
- **Builder:** `mk_member(**columns)` = "member" (W1, U1, `"member"`, `"active"`); keywords are the card's "but" columns; flushes each row.
- Extra `Wk` / `Pk` rows are built inline with `make_workspace(db)` / `make_profile(db)` at the card's place.
- **Reading helpers:** `idset`, `ids`; `pair_count(db, workspace_id, user_id)` for WU-06 Then 4 (Core count); `user_count(db, user_id)` for the `count:` lines of WU-09 and HA-07 (Core count over all workspaces).
- **seqscan:** `seqscan(db)` runs the three `SET LOCAL` statements of the Conventions in order.
- **Statement recorder:** `before_cursor_execute` listener around the When only; `recorder.sql()` is the one SELECT `FROM workspace_members` (fails unless exactly one); `order_part_of(sql)` = text after the first `ORDER BY` (`""` if none); `recorder.written()` = INSERT/UPDATE/DELETE.
- **WU-06:** `with pytest.raises(IntegrityError) as exc:` around `with db.begin_nested(): db.add(p); db.flush()`; the count runs after the savepoint rollback.
- Row letters are lower case in code; a Given row no later line names has no variable.

## xfail location (`--runxfail`, reading the failing value)
| Card | Strict | Fails on | Actual |
|---|---|---|---|
| WSM-GU-04 | no | Then 2 | `[B, C, D, A]` (e.g. `[368300, …, 368302, 368299] == [368299, …, 368302]`): the updated row last |
| WSM-GU-05 | yes | Then 2 | `'ORDER BY' in 'SELECT … FROM workspace_members WHERE workspace_members.user_id = %(user_id_1)s'` |
| WSM-GM-11 | no | Then 2 | `[B, C, D, A]` (`[368305, …, 368304] == [368304, …]`) |
| WSM-GM-12 | yes | Then 2 | no `ORDER BY` after `WHERE workspace_id = … AND status = …` |
| WSM-GW-02 | yes | Then 2 | no `ORDER BY` after `WHERE workspace_id = …` |

**Reference / wrong-order plugin** `wsm_plug.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\wsx\workspace_member` (`-p wsm_plug`, `PYTHONPATH` there, `WSM_MODE=<mode>`): it replaces `get_by_user` and `get_workspace_members` in-process with the same filters plus an explicit `ORDER BY`; nothing in `app/`.

| `WSM_MODE` (ORDER BY) | `--runxfail`: cards that fail | Pass cards that fail | Markers on |
|---|---|---|---|
| `fix` (`id`) | none: all 44 pass, so Then 3–5 of GU-05, GM-12, GW-02 hold | none | 39 passed, 3 failed (`XPASS(strict)`), 2 xpassed |
| `id_desc` | GU-04, GM-11 on Then 2; GU-05, GM-12, GW-02 on Then 4 | none | 39 passed, 5 xfailed |
| `role` | GU-05, GM-12, GW-02 on Then 3 (GU-04, GM-11 pass by accident: "admin" sorts first) | none | 39 passed, 3 xfailed, 2 xpassed |
| `role, id` | GU-05, GM-12, GW-02 on Then 5 | none | 39 passed, 3 xfailed, 2 xpassed |
| `updated_at` | GU-04, GM-11 on Then 2; the three strict on Then 3 | none | 39 passed, 5 xfailed |
| `workspace_id DESC` | GU-04, GM-11 on Then 2; the three strict on Then 3 | none | 39 passed, 5 xfailed |
| `user_id DESC` | GU-04, GM-11 on Then 2; the three strict on Then 3 | none | 39 passed, 5 xfailed |

So both non-strict cards can fail on their Then 2 under an explicit wrong order, every strict card reaches each of its Then 2–5 lines, and no pass card depends on order.

## Discrepancies
None. No card was changed, no marker loosened, no test marked DISCREPANCY.

## Spec gaps of the cases file, checked
Gap 1 (role text `"member"`, `"admin"`, `"owner"`): accepted by the `String(50)` column. Gap 2 (101 workspaces for GU-03): built with `make_workspace`, about 0.3 s. No assumed path or value was wrong.

## Coverage gaps
None — 100% line and branch coverage (private `COVERAGE_FILE`). Inherited `BaseDAO` methods are measured by `test_base.py`.

## Factories added
None.

## Stability
- 5 default runs, 3 more default runs, and the coverage run: `39 passed, 5 xfailed` each.
- Forced plans via `PGOPTIONS`: `enable_seqscan=off`; that plus `enable_hashjoin=off`, `enable_nestloop=off`; `enable_hashjoin=off`; index, bitmap and index-only scans off; that plus hash and merge join off. All `39 passed, 5 xfailed`, except the second plan once at `39 passed, 4 xfailed, 1 xpassed`.
- Time zones `-c timezone=UTC` and `-c timezone=Asia/Dhaka`: `39 passed, 5 xfailed` (no column here is time-zone sensitive; no card compares a real-clock stamp, so no repeat loop was needed).
- **The XPASS:** GU-04 and GM-11 run alone under `enable_seqscan=off` XPASSed in 7 of 8 runs; alone without `PGOPTIONS`, 4 of 4 xfailed. EXPLAIN inside the test's transaction shows a sequential scan in both settings (under the option it is marked `Disabled: true` and is still chosen), so the plan is not the cause. The rows landed on different heap pages (page 13 vs page 0 with reused line pointers), so the updated row's physical position depends on the table's free space. This is exactly why the cards are non-strict; GU-05, GM-12 and GW-02 are the proof of BUG-1400.
- `ruff check`: all checks passed. LF only (0 CR bytes).

## Notes for maintainers
- When BUG-1400 is fixed, GU-05, GM-12 and GW-02 turn the run red (`XPASS(strict)`): remove the five markers.
- Never read a GU-04 or GM-11 XPASS as the bug being gone.
- `recorder.sql()` keeps only SELECTs naming `FROM workspace_members`; `has_access` and `count_active_members` cards use the recorder only for `written`.
- HA-07 is the access gate of every workspace request: if it ever fails, treat it as a security defect, not a flaky test.

## Revision history
- **Revision 1 of the cases (`workspace_member.verify.md`, case-missing Findings 1–5, recipes R-1 … R-5):** added WSM-WU-09, GU-07, GM-14, CA-05, CA-06, HA-07, HA-08, HA-09, HA-10, HA-11, all `pass`, each inserted at its card's place in the same form (`# [claude] ID`, `# Then N`). One reading helper added, `user_count`. No existing card, Convention or ID changed, so no existing test was touched; none retired.
- **Rerun:** `54 passed` with `--runxfail` under the reference (`WSM_MODE=fix`); without a plugin `--runxfail` fails exactly the five BUG-1400 cards, on the same lines as before; with the markers on under the reference, `3 failed (XPASS(strict)), 49 passed, 2 xpassed`. 3 default runs, plans 3–5 and time zones UTC and Asia/Dhaka: `49 passed, 5 xfailed`; plans 1 and 2 (`enable_seqscan=off`, alone and with hash join / nested loop off): `49 passed, 3 xfailed, 2 xpassed` — GU-04 and GM-11, the non-strict cards, as described under Stability. Coverage 100% line and branch, private `COVERAGE_FILE`. `ruff check` passed; LF only.

### The verifier's variants, rebuilt here
`wsm_var.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\wsx\workspace_member` (`-p wsm_var`, `WSM_VAR=<name>`), written from the variant names and Findings of `workspace_member.verify.md`, not the verifier's own files. It replaces the five methods in-process on top of the reference order (`ORDER BY id`), so the BUG-1400 cards stay out of the way; nothing in `app/`. `WSM_VAR=none` with `--runxfail`: 54 passed. Each variant with `--runxfail`, default plan:

| Variant | What it changes | Cards that fail | Other cards that fail |
|---|---|---|---|
| `wu_r2_user_le` | `user_id <= :user_id` in `get_by_workspace_and_user` (so in `has_access` too) | WSM-WU-09, HA-07 | none |
| `gu_r1_user_le` | `user_id <= :user_id` in `get_by_user` | WSM-GU-07 | none |
| `gm_r3_ws_le` | `workspace_id <= :ws` in `get_workspace_members` | WSM-GM-14 | none |
| `ca_r2_ws_le` | `workspace_id <= :ws` in `count_active_members` | WSM-CA-05 | none |
| `ha_r2_strip` | `status.strip() == 'active'` | WSM-HA-09, HA-10 | none |
| `ha_r2_lstrip` | `status.lstrip() == 'active'` | WSM-HA-09 | none |
| `ha_r2_rstrip` | `status.rstrip() == 'active'` | WSM-HA-10 | none |
| `ha_r2_in_const` | `status in 'active'` | WSM-HA-08, HA-11 | none |
| `ha_r2_prefix` | `status.startswith('activ')` | WSM-HA-10, HA-11 | none |
| `ca_r1_cst_prefix` | `status LIKE 'active%'` | WSM-CA-06 | none |
| `ca_r1_cst_part` | `status LIKE 'activ%'` | WSM-CA-06 | none |

Every variant fails exactly the new cards the verifier's recipe table names for it, on Then 1, and no other card. `ha_r2_prefix` is read as "starts with `activ`", the one reading under which both `"active "` and `"activ"` let a member through, as the verifier's table says.
