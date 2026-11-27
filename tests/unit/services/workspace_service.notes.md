# Execution notes — `app/services/workspace_service.py`

> Cases: `tests/unit/services/workspace_service.cases.md` (revision 5) · Tests: `tests/unit/services/test_workspace_service.py` · Source commit: e48a092
> Result: 202 of 202 cases implemented · 134 passed · 68 xfail as designed (all strict, all xfailed) · 0 discrepancies · 0 errors — branch coverage 99% (2 unreachable)
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/services/test_workspace_service.py -q -p no:cacheprovider`

## How the tests are built
One test per card, in card order, `# [claude] <ID>` above each, `# Then N` before the checks of Then line N.
- **Standing rows:** fixture `s` builds them in the Conventions order and returns a namespace with the card names as attributes (`s.PL1`, `s.UA`, `s.W1`, `s.MO`, `s.EA`, `s.TAG`, `s.SL`, ...).
- **Given rows:** `member(db, s, U, role, status="active", ws=None, **but)`, `invitation(db, s, J, email, **but)` (token `tok-J-{TAG}`), `limit(db, s, n)`, `mk_pd`, `mk_px`, `commit_point(db)` = `db.commit()`, `add_x(db, s)` returns `X_ID`. W3 / W4 = `make_workspace(db)`. RM-17 (`Author: claude`) builds a `Factory` and a `Project` of W1 (all required columns) and the `ProjectMember` row.
- **Externals:** `clock()` patches `app.managers.workspace_manager.utcnow` and `app.dao.workspace_invitation.utcnow` to NOW. Every When runs inside it.
- **Checks:** `snap(row)` = every column (taken at the commit point), `reread_snap` (expire_all + `db.get` + snap) = unchanged(X); `counts(db)` = rows of the four workspace tables = "nothing written"; `x_count`; `audit(db, ws_id, action)`; `wsids` / `ids0` / `uids`; `spies`, `failing_commit`, `failing_refresh`, `refresh_trap`; `recorder(db)`. Revision 4 convention: the test first evaluates the When's keyword arguments into `kw` and calls `svc.<method>(db, **kw)`. Entering the recorder runs `expire_all()` and adds a `before_cursor_execute` listener on `db.connection()`, which is removed right after the When.
- `committed:` lines run `db.rollback()` once, then read with a fresh `select`. Ids are copied to locals before the When when a later read needs them after a rollback or inside a recorder.
- Schema cards build only the schema (no `db`).

## Fails-today check
`--runxfail` with the scratch plugin `thenmap.py` (maps the failing test-file line to the nearest `# Then N` above it). Every strict xfail fails where its card says:
- Then 1 on the When call (the card says "the call raises ..."): C-09, U-24, MR-20, RM-18, SI-11, AI-18, XI-14 (`TypeError ... 'ip_address'`); SI-10, AI-16 (`ValidationError ... limit (-1)`); AI-13 (`User is already a member`); MR-31 (`PermissionDeniedError: Cannot change workspace owner's role`); MR-33 (`IntegrityError` 23502 at the commit: `role` is NOT NULL).
- Then 1 `DID NOT RAISE`: C-11, C-13, U-10, U-18, U-19, U-20, U-28, MR-04, MR-10, MR-16, MR-17, MR-24, MR-27, RM-14, RM-15, RM-16, SI-09, SI-14, AI-15, AI-19.
- Then 1, wrong exception: U-13, U-14, MR-13 (`NotFoundError: Workspace not found`); MR-26 (`NotFoundError: Member not found`); MR-28 (`PermissionDeniedError: Cannot change workspace owner's role`); RM-11 … RM-13, XI-08 … XI-12 (`PermissionDeniedError`).
- Then 2: C-10 (`' Acme '`), U-09 (`'  Acme  '`), U-17 (owner message), U-21, U-22, MR-18 (0 audit rows), LW-07 (6 statements), LM-07 (7), LI-06 (8), MI-06 (11), LW-08, LM-08, LI-07, MI-07 (no `ORDER BY`), RM-17 (1 project row), AI-14 (`'pending'`), AI-17 (`None`), XI-13 (`'Invitation not found'`).
- Then 3: U-15, U-16, MR-14, MR-15 (today's owner message).
- MI-04: Then 1, `set()`.

## Reference run
`refplug_wss.py` (scratch, `-p refplug_wss`, PYTHONPATH = scratch folder) replaces, before the test module is imported: the five request schemas (255 caps BUG-2256; `name` trimmed so blank fails `min_length`, BUG-1980); and every `WorkspaceService` method except the two helpers and `get_workspace_with_plan`. The new methods: check membership first on update_workspace / update_member_role (BUG-2250); map not-found to 404 and wrong state to 400 on remove / cancel (BUG-2251, with BUG-1981, BUG-1984); batch reads with `IN` / `joinedload` and `ORDER BY id` (BUG-2252, BUG-1400, BUG-1401); write `workspace_updated` / `member_role_changed` audit rows (BUG-2253); refuse `new_role == "owner"` with a 400 after R1–R2, outside the `try` (BUG-2257); take `new_role=None` as position-only, also on the owner's own row (BUG-2258); treat an inactive target as not found (BUG-2254); take `ip_address` / `user_agent` on every writer (BUG-1404). Manager rules re-done in the plugin: BUG-1280, BUG-1402, BUG-1871, BUG-1872, BUG-1873, BUG-1874, BUG-1982, BUG-1985, BUG-1986, BUG-1987, BUG-1990.
- With `--runxfail`: **202 passed** (revision 5), with no diagnostic plugin.

## Discrepancies
None. DISCREPANCY-1 (the `expired_attributes` check of C-01, U-01, MR-01, SI-01, AI-01) was fixed in cases revision 4; see Revision history.

## Coverage gaps
| Lines | Kind | What the code does there |
|---|---|---|
| 83->79 | unreachable | `list_user_workspaces` skips a membership whose workspace is missing. The FK cascade deletes members with their workspace (spec R3: not testable). |
| 116 | unreachable | `get_workspace_with_plan` raises 404 when the workspace is missing. The membership check before it already answers 403 (spec R3, card G-03). |

## Factories added
None.

## Notes for maintainers
- When a bug is fixed, its cards XPASS: remove the marker. The service bugs (BUG-2250 … BUG-2256, BUG-1404) are in `app/services/workspace_service.py` and the schemas. The pass-through bugs are in `app/managers/workspace_manager.py` and `app/dao/workspace_invitation.py` / `workspace_member.py`.
- The BUG-1404 cards pass `ip_address=` / `user_agent=` as keywords. The fix must accept those names.
- The statement-count cards (LW-07, LM-07, LI-06, MI-06) count every statement after `expire_all()`. Since revision 4 the When's arguments are read before it, so the tests' own reloads are not counted. Counts today: LW-07 6, LM-07 7, LI-06 8, MI-06 11. LI-06 allows 3, so a fix must load the workspace together with the invitations (one join) and the inviters in one `IN`. The membership check is the first of the three.
- The clock patches use the module attributes. A fix that imports `utcnow` under another name, or reads `datetime.now`, escapes them.

## Revision history
- **Revision 4 (2026-11-05)** — cases revision 4.
  - C-01, U-01, MR-01, SI-01, AI-01: the refresh check now covers column attributes only (`not ({c.key for c in sa_inspect(result).mapper.column_attrs} & sa_inspect(result).expired_attributes)`). The DISCREPANCY-1 markers are removed; all five pass.
  - Recorder convention: the eight recorder tests (LW-07, LW-08, LM-07, LM-08, LI-06, LI-07, MI-06, MI-07) now build `kw` before the recorder and call `svc.<method>(db, **kw)`. Statement counts today: LW-07 6 (was 7, matching the card's 6), LM-07 7, LI-06 8, MI-06 11. All still fail on Then 2 as designed.
  - MR-04 rewritten to its new card (strict xfail BUG-2257: 400, MA unchanged, X kept until the rollback, nothing written). New MR-26, MR-27, MR-28 (strict xfail BUG-2257) and MR-29, MR-30 (pass).
  - `refplug_wss.py` gained the BUG-2257 fix.
  - No ID retired.
  - Re-verified: 133 passed / 66 xfailed in each of 3 plain runs. `--runxfail`: every strict xfail fails on its card's Then line (MR-04 and MR-27 Then 1 DID NOT RAISE; MR-26 Then 1 `NotFoundError`; MR-28 Then 1 `PermissionDeniedError`). The reference plugin gives 199 passed under `--runxfail` with no diagnostic plugin. Branch coverage 99% (same 2 unreachable). Ruff check and format clean; LF.
- **Revision 5 (2026-11-06)** — cases revision 5 (verifier findings 1–4).
  - LI-01 … LI-05: each W1 invitation now has its own inviter (UO, UA, UB, `None`). LI-01 Then 2 now checks only the workspace; the new Then 3 (and LI-02 Then 3, LI-03 Then 2, LI-05 Then 1) checks the `{invitation id: inviter id}` map. LI-04 changed only its Given.
  - MI-01: new I5 (W0, no inviter); the other inviters are as the card gives them; Then 1 and 2 assert three invitations and the map.
  - New MR-31 (strict xfail BUG-2258; fails today at the call with `PermissionDeniedError`), MR-32 (pass), MR-33 (strict xfail BUG-2258, `Author: claude`; fails today at the call with `IntegrityError` 23502, gap 5).
  - `refplug_wss.py`: `new_role` defaults to `None`; the role and the owner-row refusal apply only when a role is given (BUG-2258).
  - No other test changed; no ID retired.
  - Re-verified: 134 passed / 68 xfailed in each of 3 plain runs. `--runxfail`: every strict xfail fails on its card's Then line. The reference plugin gives 202 passed under `--runxfail`. Branch coverage 99% (same 2 unreachable). Ruff check and format clean; LF.
- **No revision (2026-11-22)** — TC3 audit: removing `update_member_role`'s own rollback goes unnoticed (MR-22's failing refresh comes after the commit). No card added: spec TX1a (2026-11-06) rules the pre-commit TC3 path of `update_member_role` not unit-testable and asks for no case. The `try` holds only attribute assignments before `_commit_transaction` (no manager or DAO write, no flush), so it fails only at the commit (TC4), where `_commit_transaction` already rolls back; reaching it needs a patch of the target's own code, not an external. Tests unchanged; reopening needs a spec change (describer).
