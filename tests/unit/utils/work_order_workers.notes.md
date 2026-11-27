# Execution notes — `app/utils/work_order_workers.py`

> Cases: `tests/unit/utils/work_order_workers.cases.md` (revision 3) · Tests: `tests/unit/utils/test_work_order_workers.py` · Source commit: e48a092
> Result: 61 passed · 16 xfailed · 0 discrepancies · 0 errors — branch coverage 100%
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/utils/test_work_order_workers.py -q -p no:cacheprovider --cov=app.utils.work_order_workers --cov-branch --cov-report=term-missing`

## How the tests are built
- **Pure callables (P, J, R, T):** no DB. Module constants `M7`, `M9`, `M12`, `M31` implement the Conventions members; ad-hoc members are built inline. `assert_res(res, ids, unmatched, display)` implements the "Result notation" and asserts in that order (ids, unmatched, display), so each xfail fails on the first differing field.
- **DB callables (L, D):**
  - W1/W2/W3 → fixtures `w1`, `w2`, `w3` (`make_workspace`).
  - P7/P9 → fixtures `p7`, `p9`; other profiles via local `prof(db, name, email)` (wraps `make_profile` with the exact name/email).
  - Unique emails → local `email(local)` adds `+<10 hex>` to the local part (Conventions allow it); expectations use the stored `p.email`. Blank / whitespace emails (D-04 `""`, D-12 `"   "`, D-13 `"\t "`) are inserted exactly as written.
  - "Active/suspended/invited member" → local `member(db, ws, profile, status)` inserts a `WorkspaceMember` with `role="ground-team"` (role is NOT NULL; value irrelevant to the module).
  - `MISSING` → `missing_profile_id(db)` = `max(Profile.id) + 1000` (committed rows only; the id sequence is far above that, so no collision). L-06's unknown workspace → `missing_workspace_id(db)` likewise.
  - "Session clean" → `assert_session_clean(db)` (`new`, `dirty`, `deleted` all empty). L-01's row count uses a fresh `COUNT(*)` after `expire_all()`.
  - L results compared as sets of `(user_id, name, email)` via `as_set`; order never asserted.
- **Parametrized:** WOW-P-01..03 and WOW-T-02..04 (one `pytest.param` id per case).
- **Mocks:** none (spec lists no externals).
- **xfail honesty** (checked with `--runxfail`): R-21/22/23/24 fail on `ids` (`[7]`, `[12]`, `[7]`, `[7, 9]`); R-25 on `unmatched`; R-26 on `unmatched` (2 entries); R-27/28/30/32 on `display`; R-33 on `unmatched` (`['Zed', 'zed']`, the first named field; display would also differ); D-08 on the first call (`""`); D-10 `"Rahim, Karim, Rahim"`; D-11 repeated label; D-12 `""`; D-13 `"Rahim"`. All match the "fails today on" column.
- Stability: 3 runs, identical outcome.

## Discrepancies
None.

## Coverage gaps
None — 100% branch coverage (67 statements, 22 branches). Note: the spec-declared unreachable branches (`load_active_member_lookups` R5 `if profile else None`, and the typed-name fallback `or token` in `resolve_names_to_members` R8) sit inside single-line conditional expressions, which coverage.py does not track as branches; they are unreachable as the spec says, but the report does not show them.

## Factories added
None (batch mode: `tests/unit/factories.py` not edited). Worth promoting later:
- `make_workspace_member(db, workspace, profile, status="active", role="ground-team")` — the local `member()` helper; any manager/DAO test around workspace membership needs it.

## Notes for maintainers
- When BUG-380 / BUG-381 / BUG-382 is fixed, its xfail tests XPASS (strict → fail): remove the markers. The paired pass cases (R-18, R-17, R-29, R-31) must keep passing after the fixes.
- `M31`'s name is three spaces; R-32's name is space-tab-space, D-13's name space-tab-space and email tab-space — keep the exact whitespace when editing.
- D-04/D-12/D-13 insert blank emails without a suffix; a parallel uncommitted insert of the same blank email would make this insert wait for that transaction (not fail), since all test transactions roll back.

## Revision history
- **Cases revision 3 (2026-09-29):** added `test_wow_r_33__repeated_unmatched_kept_at_first_position` (new WOW-R-33, R7a/R9a [BUG-381], `xfail(strict=True)`). No other test changed; no Retired IDs; verify report had no executor findings. `--runxfail` confirms it fails on `unmatched == ["Zed"]` (today `['Zed', 'zed']`). Three runs: 61 passed, 16 xfailed each. Coverage unchanged at 100% branch.
