# Execution notes — `app/dao/workspace_invitation.py`

> Cases: `tests/unit/dao/workspace_invitation.cases.md` (Revision 1, READY, 43 cases) · Tests: `tests/unit/dao/test_workspace_invitation.py` · Source commit: e48a092
> Result: **43 tests for 43 cases — 33 passed · 10 xfailed · 0 discrepancies · 0 errors** — branch coverage 100% (17 statements, 0 branches). The three non-strict cards (GP-06, UI-08, GA-05) xfailed in every run.
> Run: `UNIT_TESTS_SKIP_MIGRATE=1 .venv/Scripts/python.exe -m pytest tests/unit/dao/test_workspace_invitation.py -q -p no:cacheprovider`

## Who wrote what
Normal mode, no local model: every test sits below a `# [claude] <ID>` comment, in card order, with `# Then N` before each numbered Then line. LF only.

## How the tests are built
- **Patched:** `app.dao.workspace_invitation.utcnow` → `NOW` around every When (`with patch(CLOCK, return_value=NOW)`, `as clock` only where a Then reads it: GP-08, GA-02). Nothing else is mocked.
- **Constants:** `dao`, `MISSING` (no card uses it), `NOW`, `US`, `DAY`, `T1` to `T3`.
- **Standing rows:** `w1`, `w2` from `make_workspace`, through the autouse `standing_rows`. `tag` fixture = `uuid.uuid4().hex[:12]`, once per test.
- **Builders:** `mk_inv(name, **columns)` = "invitation X" (token `f"tok-{name}-{tag}"`, flushed one at a time); `mk_many_inv(count, **columns)` = the 101-row `add_all` Givens (token `f"tok-{k}-{tag}"`).
- **Reading helpers:** `idset`, `ids`, `reread(db, id)` (`expire_all` then `db.get`).
- **Statement recorder:** `before_cursor_execute` listener on the session's connection, around the When only. `sql()` is the one SELECT naming `workspace_invitations` (fails loudly otherwise); `order_part_of(sql)` is the text after the first `ORDER BY`; `written()` is every INSERT / UPDATE / DELETE.
- The "writes nothing" cards build `P` with `db.add` and no flush and set `B.role` unflushed, exactly as the card's code lines.

## xfail location (`--runxfail`, reading the failing value)
| Card | Strict | Fails on | Actual |
|---|---|---|---|
| WSI-GP-06 | no | Then 2, every run | `assert [518, 519, 520, 521] == [521, 519, 518, 520]` (id order) |
| WSI-GP-07 | yes | Then 2 | `'ORDER BY' in 'SELECT … AND workspace_invitations.expires_at > %(expires_at_1)s'` |
| WSI-UI-02 | yes | Then 2 | `assert [] == [531]` |
| WSI-UI-03 | yes | Then 2 | `assert [] == [532]` |
| WSI-UI-04 | yes | Then 2 | `assert [] == [533]` |
| WSI-UI-08 | no | Then 2, every run | `assert [637, 638, 639, 640] == [640, 638, 637, 639]` |
| WSI-UI-09 | yes | Then 2 | no `ORDER BY` in the email query |
| WSI-UI-13 | yes | Then 2 | `assert [] == [76163]` (rev. 1; the stored email has a leading space) |
| WSI-GA-05 | no | Then 2, every run | `assert [766, 767, 768, 769] == [769, 767, 766, 768]` |
| WSI-GA-06 | yes | Then 2 | no `ORDER BY` in the workspace query |

**Reference plugin** `wsi_plug.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\wsx\workspace_invitation` (`-p wsi_plug`, `WSI_MODE=…`, in-process; nothing in `app/`). `WSI_MODE=fix` (`ORDER BY invited_at DESC, id DESC`; email `lower(trim())` on both sides): with `--runxfail` **37 passed** (rev. 1: **43 passed**), so every line past each failure point holds, and UI-05 / UI-06 (R2a) still pass after the fix. With the markers on: 6 strict `XPASS(strict)`, 3 non-strict XPASS, 28 passed (rev. 1: 7 strict `XPASS(strict)`, 3 XPASS, 33 passed).

**Explicit wrong orders, `--runxfail`** (email exact, as today):

| Order | Non-strict cards | Strict SQL cards | Pass cards that fail |
|---|---|---|---|
| `invited_at DESC, id` | GP-06, UI-08, GA-05 on Then 2 (`[1650, 1652, 1649, 1651] == [1652, 1650, 1649, 1651]`) | Then 6 | none |
| `invited_at DESC, token` | the same three on Then 2 | Then 4 | none |
| `id DESC` | the same three on Then 2 | Then 3 | none |
| `invited_at, id` | the same three on Then 2 | Then 6 | none |
| `invited_at DESC, email, role` | the same three on Then 2 | Then 4 | none |

## Discrepancies
None. No card was changed, no marker loosened, no test is marked DISCREPANCY.

## Spec gaps of the cases file, checked
1. `role` free text: `"member"` / `"admin"` accepted (VARCHAR(50), no check). Held.
2. `utcnow` call count: GP-08 checks only `clock.called is True`; the code calls it once per query. Held.
3. `invited_at` default: the model's default is `app.utils.time.utcnow` (not the patched DAO name), so the patch does not reach it; the order cards set `invited_at` explicitly, as designed. Held.

## Coverage gaps
None — 100% line and branch coverage (`--cov=app.dao.workspace_invitation --cov-branch`, private `COVERAGE_FILE`). Inherited `BaseDAO` methods are measured by `tests/unit/dao/test_base.py`.

## Factories added
None.

## Stability
5 default runs; 5 forced plans via `PGOPTIONS` (`enable_seqscan=off`; that plus hash join and nested loop off; `enable_hashjoin=off`; index, bitmap and index-only scans off; that plus hash and merge join off); 3 database time zones (`UTC`, `Asia/Dhaka`, `Pacific/Kiritimati`; `PGOPTIONS` checked to apply with `SHOW`); 20 more whole-file runs: each `28 passed, 9 xfailed`. No test compares a real-clock stamp (every compared time is a constant; `NOW` is patched), so no high-count repeat was needed. `ruff check`: all checks passed.

## Notes for maintainers
- When BUG-1401 is fixed, GP-07, UI-09, GA-06 turn the run red (`XPASS(strict)`): remove the six BUG-1401 markers. Never read a GP-06 / UI-08 / GA-05 XPASS as the bug being gone; the SQL cards are the proof.
- When BUG-1402 is fixed, UI-02 to UI-04 and UI-13 XPASS(strict): remove their markers. UI-05 and UI-06 must keep passing — an unescaped `ILIKE` fix would fail UI-06.
- Tokens carry the per-test `tag`, so concurrent runs never wait on the unique token index.

## Revision history
- **Revision 1 of the cases (`workspace_invitation.verify.md`, case-missing Findings 1 … 4):** added WSI-GP-09, UI-12, UI-13, CP-05, CP-06, GA-08, each inserted at its card's place in the same form (`# [claude] <ID>`, `# Then N`); UI-13 is a strict xfail on BUG-1402. No existing card or Convention changed, so no existing test changed. 43 IDs, one test each, in card order.
- **Runs:** 3 default runs, the 5 forced plans and time zones `UTC`, `Asia/Dhaka`: each `33 passed, 10 xfailed`. Coverage run the same, 100% line and branch, private `COVERAGE_FILE`. `--runxfail`: `10 failed, 33 passed`, exactly the ten bug cards. `ruff check` passed; LF only.
- **Reference and wrong orders, rerun on the new file:** `WSI_MODE=fix` gives 43 passed with `--runxfail`. Each of the five wrong orders fails only the ten bug cards (UI-13 because the email stays exact in those modes); no pass card fails, the new ones included.

## Verifier's variants, rebuilt
Plugin `wsi_var.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\wsx\workspace_invitation` (`-p wsi_var`, `WSI_VAR=<name>`, in-process; nothing in `app/`; written here, not the verifier's files). Base = the verifier's reference (`ORDER BY invited_at DESC, id DESC`; email `lower(btrim(col)) == arg.strip().lower()`), one edit on top. Each run with `--runxfail`, default plan; `WSI_VAR=ref` alone: 43 passed.

| Variant | Edit | Cards that fail |
|---|---|---|
| `ui_r1_status_lower_col` | UI: `lower(status) == 'pending'` | WSI-UI-12 |
| `ui_r1_status_trim_col` | UI: `btrim(status) == 'pending'` | WSI-UI-12 |
| `ui_r1_status_ltrim_col` | UI: `ltrim(status) == 'pending'` | WSI-UI-12 |
| `ui_r1_status_ilike` | UI: `status ILIKE 'pending'` | WSI-UI-12 |
| `ui_r1_status_not_accepted` | UI: `status != 'accepted'` | WSI-UI-12 |
| `cp_r1_status_trim_col` | CP: `btrim(status) == 'pending'` | WSI-CP-05 |
| `cp_r1_status_ltrim_col` | CP: `ltrim(status) == 'pending'` | WSI-CP-05 |
| `gp_r3_ws_le` | GP: `workspace_id <= arg` | WSI-GP-09 |
| `cp_r3_ws_le` | CP: `workspace_id <= arg` | WSI-CP-06 |
| `ga_r1_ws_le` | GA: `workspace_id <= arg` | WSI-GA-08 |
| `ui_r2_no_trim_col` | UI: `lower(email) == arg.strip().lower()` (the fix that trims only the argument) | WSI-UI-13 |
| `ui_r2_no_trim_arg` | UI: `lower(btrim(email)) == arg.lower()` | WSI-UI-03 (bug path) |
| `ui_r2_exact` | UI: `email == arg` (today) | WSI-UI-02, UI-03, UI-04, UI-13 (bug path) |

Every named variant fails the new card it was written for, and only that card; no other pass card breaks.
