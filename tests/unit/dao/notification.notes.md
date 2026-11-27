# Execution notes — `app/dao/notification.py`

> Cases: `tests/unit/dao/notification.cases.md` (Revision 1, READY, 39 cases) · Tests: `tests/unit/dao/test_notification.py` · Source commit: e48a092
> Result: **39 tests for 39 cases — 34 passed · 5 xfailed · 0 discrepancies · 0 errors** — branch coverage 100% line and branch (30 statements, 4 branches). The one non-strict card (GF-06) did not XPASS in any plain run.
> Run: `UNIT_TESTS_SKIP_MIGRATE=1 .venv/Scripts/python.exe -m pytest tests/unit/dao/test_notification.py -q -p no:cacheprovider`

## Who wrote what
Normal mode, no local model: every test sits below a `# [claude] <ID>` comment. Test names were generated from the card titles by a throwaway script; bodies were written by hand from the cards.

## How the tests are built
- **Patched:** only `app.dao.notification.utcnow` (constant `CLOCK`), `return_value=NOW`, around every `mark_read` When, as the Conventions' Externals say. `create` and `get_for_user` read no clock.
- **Constants:** `dao`, `MISSING`, `NOW` (naive), `EARLY`, `T1`–`T3` (aware UTC).
- **Standing rows:** `w1`, `w2`, `u1`, `u2`, `u3`, chained so ids rise in the Conventions' order, made present in every test by the autouse `standing_rows`.
- **Builders:** `mk_note(**but)` = "note" with the card's "but" columns, flushed one at a time; `mk_many_notes(count)` builds E1 … Ecount with `add_all` (Ek at 09:00:k UTC) and returns `newest` (ids of Ecount … E1).
- **Reading helpers (no expected values inside):** `ids`, `idset`; `reread(db, row)` = `db.expire_all()` then SELECT by id; `snap(db, row)` = every column by a Core select, for "unchanged"; `utc_read(db, row)` = the Conventions' SQL; `stored_count(db)` = "nothing written"; `w_count(db, workspace_id)` = the raw count of CR-11.
- **Statement recorder:** `StatementRecorder(db)`, a `before_cursor_execute` listener on the session's connection, records text and parameters, also when the When raises. Properties `recorded`, `selects`, `written`, `sql` (the one SELECT from notifications with `LIMIT`), `notify`, `notify_args` (dict values in order), `payload`.
- **Database-error cards:** `with pytest.raises(...) as exc:` around `with db.begin_nested():`; for the `create` errors the recorder wraps that block (Then 1 comment sits on the `pytest.raises` line).
- **"rolled back" (CR-11, MR-09):** `patch.object(db, "commit", wraps=db.commit)` is the spy; `sp = db.begin_nested()` directly before the call, the inside-savepoint check, `sp.rollback()`, the after-rollback check, then `commit_spy.call_count == 0`.
- **Concurrency:** other test runs share `marker_test`; every count is of rows of this test's transaction (uncommitted rows of other sessions are invisible), and no card LISTENs (CR-03 records the `pg_notify` statement; delivery needs a commit and is deferred).

## xfail location (`--runxfail`, reading the failing value)
| Card | Strict | Fails on | Actual |
|---|---|---|---|
| NTF-GF-06 | no | Then 2, every run (5 default, 5 plans, 2 time zones, 20 repeats) | `assert [198, 199, 200] == [200, 199, 198]` |
| NTF-GF-07 | yes | Then 4 | `assert '.id' in ' notifications.created_at DESC \n '` |
| NTF-MR-03 | yes | Then 1 | `assert 2 == 0` |
| NTF-MR-04 | yes | Then 2 | `datetime(2026, 3, 5, 11, 0) == datetime(2026, 3, 5, 17, 0)` (6 h early) |
| NTF-MR-05 | yes | Then 2 | `datetime(2026, 3, 5, 22, 0) == datetime(2026, 3, 5, 17, 0)` (5 h late) |

GF-06's card says the updated row comes last; today the tied rows came back in id ascending order (`A, B, C`), the updated one first. It still fails on Then 2 as designed; prose only.

**Reference plugin** (`ntf_plug.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\wsx\notification`, `-p ntf_plug`, in-process, nothing in `app/`). `NTF_MODE=fix` = `created_at DESC, id DESC`, `ids=[]` marks nothing, `read_at` written as aware UTC: with `--runxfail` all 38 pass (39 at Revision 1), so Then 5–7 of GF-07 and Then 2–3 of MR-03 hold; with the markers on, the four strict cards are `XPASS(strict)` and GF-06 XPASSes.

**Explicit wrong orders** (`NTF_MODE=wrong:<name>`, `--runxfail`):

| `get_for_user` order | Cards that fail | Pass cards that fail |
|---|---|---|
| `created_at DESC, id` | GF-06 Then 2; GF-07 Then 6 | none |
| `created_at DESC, preview` | GF-06 Then 2; GF-07 Then 4 | none |
| `created_at DESC, entity_id` | GF-06 Then 2; GF-07 Then 4 | none |
| `created_at DESC, is_read` | GF-06 Then 2; GF-07 Then 4 | none |
| `created_at DESC, preview DESC, id DESC` | GF-07 Then 7; GF-06 passes (NULLs sort first under DESC, which is the intended order by accident) | none |

(MR-03, MR-04, MR-05 fail on their own lines in every wrong-order run; the plugin leaves `mark_read` as it is there.) So GF-06 can fail on its Then 2 and no pass card depends on the order among ties.

## Discrepancies
None. No card was changed, no marker loosened, no test is marked DISCREPANCY.

## Spec gaps of the cases file, checked
1. `pg_notify` form: the channel is a **bound parameter** (`SELECT pg_notify(:channel, :payload)`, channel `NOTIFICATION_CHANNEL = "user_notifications"` from `app.core.notification_channels`); payload `json.dumps` of `recipient_user_id`, `workspace_id`, `notification_id` in that order. CR-03 accepts either place, as designed; it passes.
2. `created_at` checked after a re-read only (CR-01); it comes back aware (`timestamptz`).
`notification_type=None` stores `"mention"` (the model's Python default applies to an explicit `None`), as CR-02 expects.

## Coverage gaps
None — 100% line and branch coverage (private `COVERAGE_FILE`).

## Factories added
None.

## Stability
5 default runs, 5 forced plans (`PGOPTIONS`: `enable_seqscan=off`; that plus hash join and nested loop off; `enable_hashjoin=off`; index, bitmap and index-only scans off; that plus hash and merge join off), database time zones `UTC` and `Asia/Dhaka`, and 20 more file runs: each `33 passed, 5 xfailed`. Under `Asia/Dhaka` with `--runxfail` the five cards fail on the same lines with the same values (MR-01, MR-04, MR-05 set their own `SET LOCAL TIME ZONE`). No test compares a real-clock stamp (the only clock is patched; CR-01 checks `created_at` is present and aware), so no long repeat loop was needed. `ruff check` (and `--select F841,F811`): all checks passed; AST pass: no unused test argument. LF only.

## Revision history
- **Revision 1 of the cases (`notification.verify.md`, case-missing Finding 1, recipe R-1):** added NTF-GF-19 (the asker is U3; an earlier user U1's notification sits in the same workspace). Inserted after GF-18, at its card's place; no existing test, fixture or Convention changed (U3 was already a standing row). Expect pass: it passes.
- **Rerun of the final text:** 3 default runs and the 5 forced plans, each `34 passed, 5 xfailed`; `--runxfail`: `5 failed, 34 passed` on the same five cards and lines as above; reference plugin `NTF_MODE=fix` with `--runxfail`: 39 passed, with the markers on `4 failed, 34 passed, 1 xpassed` (the four strict `XPASS(strict)`, GF-06 xpassed); coverage 100% line and branch with a private `COVERAGE_FILE`; `ruff check` passed; LF only.

**The verifier's variant, rebuilt here** (`ntf_var.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\wsx\notification`, `-p ntf_var`, `NTF_VAR=<name>`; in-process on the reference above, nothing in `app/`; not the verifier's own files). `--runxfail`, default plan; `ref` alone gives 39 passed.

| Variant | What changes | Cards that fail | Fails on |
|---|---|---|---|
| `gf_r1_user_le` | `recipient_user_id <= user_id` in items, total and unread count | NTF-GF-19 only | Then 1: `{30502, 30503} == {30503}` |
| `gf_r1_user_le_items` | `<=` in the listed items only | NTF-GF-19 only | Then 1 |
| `gf_r1_user_le_total` | `<=` in the total only | NTF-GF-19 only | Then 2: `2 == 1` |
| `gf_r1_user_le_unread` | `<=` in the unread count only | NTF-GF-19 only | Then 3: `2 == 1` |
| `gf_r1_user_ge` (mirror) | `>=` in all three | GF-01, GF-08, GF-14, GF-18 | — (GF-19 passes: U3 is the highest id) |
| `gf_r1_no_user` | no recipient filter | GF-01, GF-08, GF-14, GF-18, GF-19 | — |

So each of GF-19's three Then lines catches the `<=` on its own query, and no other card did before.
## Notes for maintainers
- When BUG-1412 is fixed, GF-07 turns the run red: remove the GF-06 and GF-07 markers. Never read a GF-06 XPASS alone as the bug being gone; GF-07 is the proof.
- When BUG-1414 / BUG-1413 are fixed, MR-03 / MR-04 and MR-05 turn red: remove their markers.
- MR-01 is the passing companion of MR-04/MR-05: it sets `UTC` itself, so it passes under any database default time zone.
