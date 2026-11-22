# Execution notes — `app/services/access_control_service.py`

> Cases: `tests/unit/services/access_control_service.cases.md` (revision 5) · Tests: `tests/unit/services/test_access_control_service.py` · Source commit: e48a092
> Result: 63 of 63 cases implemented · 35 passed · 28 xfail as designed (all strict, all xfailed) · 0 discrepancies · 0 errors — branch coverage 100%
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/services/test_access_control_service.py -q -p no:cacheprovider`

## How the tests are built
Same form as `help_ticket_service.notes.md`: one test per card, in card order, `# [claude] <ID>` above each, `# Then N` before the checks of Then line N.
- **Standing rows** (autouse, chained fixtures so the order is fixed): `w0`, `w1`, `w2` (`make_workspace`), profiles `ua` Ana, `uo` Omar, `uz` Zara, then `mo` = owner row of UO in W1.
- **Given rows:** fixture `rule(**but)` (W1, PAGE, "/orders", OWNER), fixture `mem(u, role, status="active", ws=None)`, `add_101(db, w1)`, `commit_point(db)` = `db.commit()`, `add_extra(db, w2, target=...)` for X and P (after the commit point, flushed, not committed).
- **Checks:** `reread`, `snap` / `unchanged` (type, target, role, workspace_id), `counts(db, w0, w1, w2)` = "nothing written", `x_gone`, `idset`, `spies`, `failing_commit`, `failing_refresh`, `failing_dao_create` (patches `app.services.access_control_service.access_control_dao.create`), `call_uid(db, fn, u, **kw)` (adds `user_id=u.id` only when the signature has it).
- The create refusal cards C-07 … C-22 share `_refused_create` (When + Then 1–5, with the `# Then N` comments inside it); D-07 … D-09 share `_refused_delete`. Each test builds its own Given rows and commit point first.
- `committed:` lines run `db.rollback()` once, then read with a fresh `select`; ids are copied to locals before.

## Fails-today check
`--runxfail` with a scratch plugin (`thenmap.py`) that maps the failing test-file line to the nearest `# Then N` above it. Every strict xfail fails where its card says:
- L-02: Then 2, `{AP, AF}` instead of `{AF}`. L-03: Then 1, `2 == 1`.
- C-07 … C-23, U-10 … U-13, D-07 … D-10: Then 1, `TypeError: ... unexpected keyword argument 'user_id'`.
- C-24: Then 1, `KeyError: 'user_id'`.

## Reference run
`refplug_acs.py` (scratch, loaded with `-p`, PYTHONPATH = scratch folder) patches `AccessControlService` in memory: the three writers take a keyword-only `user_id` and refuse, before the `try`, anyone without an `owner` / `active` (exact text) row in that workspace with `PermissionDeniedError(DENY)` (BUG-1875); `get_controls` filters on role and type together when both are given (BUG-2255).
- With `--runxfail`: **63 passed** (revision 5). Revision 3 had 60, with ACS-D-02 failing as DISCREPANCY-1.

## Discrepancies
None. DISCREPANCY-1 (ACS-D-02) was fixed in cases revision 4; see Revision history.

## Coverage gaps
None — 100% branch coverage (48 statements, 8 branches).

## Factories added
None.

## Notes for maintainers
- When BUG-1875 is fixed, the 26 refusal / signature cards XPASS: remove their markers. The 18 owner write cards already go through `call_uid`, so they keep passing.
- When BUG-2255 is fixed, L-02 and L-03 XPASS.
- `AccessControl` has no relationships, so the column-only refresh check of C-01 / U-01 (revision 4) has the same effect as the revision-3 `expired_attributes == set()` check.

## Revision history
- **Revision 4 (2026-11-05)** — cases revision 4. Changed: ACS-C-01 Then 3 and ACS-U-01 Then 2 now check only column attributes (`not ({c.key for c in inspect(result).mapper.column_attrs} & inspect(result).expired_attributes)`). ACS-D-02: Then 6 is now `ws_count(W0) == 1` and the new Then 7 is `ws_count(W1) == 1`; the commit-point `counts` snapshot and the DISCREPANCY-1 marker are removed, and the test passes. No other test changed; no ID added or retired. Re-verified: 35 passed / 26 xfailed in each of 3 plain runs; `--runxfail` gives the same 26 failures on the same Then lines (25 on Then 1, L-02 on Then 2); the reference plugin (unchanged) gives 61 passed under `--runxfail`; branch coverage 100%; ruff check and format clean; LF.
- **Revision 5 (2026-11-06)** — cases revision 5 (verifier findings 1–2).
  - New ACS-U-13 and ACS-D-10: the C-23 shape for update and delete. The `pytest.raises` block sits inside the spies; there is no commit and no rollback, pending P survives, and A is unchanged (U-13) or W1 still has 1 row (D-10). Both are strict xfail BUG-1875 and fail today on Then 1 (`TypeError`).
  - ACS-C-24 gained Then 4–6 (`user_id` default is `Parameter.empty` on each writer). It still fails on Then 1 (`KeyError`).
  - `refplug_acs.py` needed no code change: its `user_id` is already keyword-only with no default.
  - No other test changed; no ID retired.
  - Re-verified: 35 passed / 28 xfailed in each of 3 plain runs. `--runxfail`: 28 failures on their cards' Then lines. The reference gives 63 passed under `--runxfail`. Branch coverage 100%. Ruff check and format clean; LF.
