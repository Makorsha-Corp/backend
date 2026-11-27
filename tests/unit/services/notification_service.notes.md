# Execution notes — `app/services/notification_service.py`

> Cases: `tests/unit/services/notification_service.cases.md` (revision 2) · Tests: `tests/unit/services/test_notification_service.py` · Source commit: e48a092
> Result: 47 of 47 cases implemented (no NSV-M-05 exists) · 39 passed · 8 xfail as designed (7 strict, all xfailed; 1 non-strict, L-06, xfailed in every run) · 0 errors · 0 discrepancies — branch coverage 100%
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/services/test_notification_service.py -q -p no:cacheprovider`

## How the tests are built
Same form as `department_service.notes.md`.
- **Standing rows:** `w1`, `w2`, profiles `ua` "Ann", `ub` "Bob", `us` "Sue", `ui` "Ivy", `uo` "Otto", `un` "Nora", then the `memberships` fixture (UA, UB active, US suspended, UI invited in W1; UO active in W2; UN none); autouse `standing_rows`.
- **Given rows:** `mk_note(**but)`, `mk_notes(n)` (by `add_all`), `READ` (`is_read True`, `read_at EARLY`).
- **Reading helpers:** `reread`, `snap_before` / `snap`, `idset`, `mentions(db, w1)` (a fresh SELECT), `utc_read`, `count_notes`, `written`, `spies`. The statement recorder is `record_sql`, filtered by `selects_of` / `writes_of`.
- **Patches:** the clock patch on M-08; the failing commit on M-06; on M-11, `patch.object(notification_dao, "mark_read", side_effect=RuntimeError("boom"))` combined with the spies. Nothing else.
- **Savepoint wraps:** L-07 and F-09 wrap the call in `db.begin_nested()` inside `pytest.raises`, as Conventions say (neither method rolls back).
- **M-10:** `db.refresh(a)` after the commit point, then `a.is_read` read straight off the object after the call.

## Fails-today check
`--runxfail`, failing line mapped to its `# Then N`, value read:
- H-09, H-10, H-11 (BUG-1534): `TypeError` (no `workspace_id`) in the When, as the cards say.
- H-14 (BUG-1536): Then 1 `'@Ann'` against `'@[<Bengali digits>]'`.
- M-07 (BUG-1414): Then 1 `2 == 0`. M-08 (BUG-1413): Then 2 `11:00` against `17:00` (Dhaka offset). F-04 (BUG-1535): Then 1, the actor's id is in the set.
- L-06 (non-strict, BUG-1412): Then 2 `[B, C, A]` against `[C, B, A]`, in every run.

## Reference run
`refplug.py` (scratch) replaced:
- `humanize_mention_preview`: ASCII digits only, and profiles scoped by membership when `workspace_id` is given;
- the DAO's `get_for_user`: ordered by `created_at DESC, id DESC`;
- the DAO's `mark_read`: `[]` marks nothing, and `read_at` is an aware UTC instant from the patched clock;
- `fan_out_mentions`: drops the actor.

In the reference, `workspace_id` is optional: the 13 preview cards that pass today call without it and gain it when the fix lands (Conventions, spec G1). With `--runxfail` all 46 tests passed. Without it all 7 strict cards XPASSed (strict, so they failed) and L-06 XPASSed.

## Stability
5 plain runs plus seqscan off and index/bitmap scans off: 38 passed, 8 xfailed in all 7; no test moved. Ruff passes; LF.

## Discrepancies
None. The spec gaps filled in parallel hold: `mark_read` R3 (M-10) passes, and R4's failing update (M-11) passes with no commit and no rollback.

## Coverage gaps
None — 100% branch coverage (37 statements, 6 branches) of `app/services/notification_service.py`.

## Factories added
None.

## Revision history
- **Cases revision 2:** added NSV-F-10 (spies outermost, then `raises`, then `db.begin_nested()`), from verify R-NT-1; pass. No other test changed. 3 plain runs and the reference with `--runxfail`: as for the sibling files. Verifier variant `f_r6_rollback_on_error` (rollback on any error), rebuilt in scratch `varplug.py`: F-10 fails at Then 4, `rb.call_count` 1.

## Notes for maintainers
- When BUG-1534 lands, `workspace_id` is required: H-01 … H-08, H-12, H-13, H-15, H-16 and H-17 each gain `workspace_id=w1.id` (cases Conventions).
- H-17 Then 3, L-05 Then 5 and F-07 Then 4 count all `notifications` rows absolutely, so `marker_test` must hold none committed (it held none on 2026-11-03).
