# Execution notes — `app/services/auth_service.py`

> Cases: `tests/unit/services/auth_service.cases.md` (revision 5) · Tests: `tests/unit/services/test_auth_service.py` · Source commit: e48a092
> Result: 220 of 220 cases implemented · 183 passed · 37 xfailed (all strict, bugs) · 0 open discrepancies (2 closed) · 0 errors — branch coverage 98% (3 lines, all unreachable)
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/services/test_auth_service.py -q -p no:cacheprovider -o addopts=""`

## How the tests are built
One test per card, in card order, `# [claude] <ID>` above each, `# Then N` before the checks of Then line N. AUTH-SW-04 … SW-07 are one parametrized test (ids `AUTH-SW-04` … `AUTH-SW-07`, identical setup, one status differs), so 215 functions give 218 items. Written by three parallel forks (A: TP/RG/RU/RI/RW, B: LI/SW/RF/LO/FP/RP, C: AR/P34/VI/ME) on one shared scaffold, then merged into this file ("Part A/B/C" banners).

- **Conventions → code.** Constants at the top (NOW, US, DAY, PAST, EARLY, LATER, FAR, NOW14, EXP15, PW, PW2, AGENT, IP, HEX32, messages, TOKEN/TOKEN2, ATT, SRV, FOREIGN, KIND_MSG); `OWN(U)`, `OWN2(U)`, `IMG(pid)` and `VEC_()` return fresh values; `VEC` is a comparison constant only (Given lines assign `VEC_()`).
- **Fixture `S`** = standing rows 1–4 (PL0–2, U0 … UQ in id order, W0 < W1 < W2, owner rows M0/MO/M2) plus the per-test TAG values (`S.TAG`, `S.E0` … `S.EN`, `S.LOWER`/`MIXED`/`UPPER`, `S.RAW1–6`, `S.FAM1/2`, `S.WSNAME`, `S.SL`).
- **Given rows:** `member`, `token`, `invitation(db, S, J, e, **but)`, `PD`, `limit`, `extra_row` → `(X, X_ID)`; `commit_point(db, *objs)` commits (releases a savepoint) and returns the counts (`["n"]`) and per-object snapshots. Part-local helpers: `a_rows`, `a_slug_count`, `b_add`, `b_failing_commit`, `b_hpw`, `c_rt`, `c_committed_ua`, `c_stamp`.
- **Checks:** `claims`, `row_of`, `tokens`, `live`, `msgs`, `reread`, `snap` (all columns), `counts` (six tables, all workspaces = "nothing written"), `audit`, `profile`, `count_ci`, `not_expired`, `x_count` (x_kept `== 1` / x_gone `== 0`), `Recorder` (statement recorder; `inserts(t)`).
- **Patches** (only these): the four `utcnow` clocks via `clock()`; fixture `dr` (every ME test) patches `app.managers.profile_stamp_manager.destroy_resource` and sets the five Cloudinary/environment settings — no Cloudinary call is ever made; `spies(db)`, failing commit / failing refresh as Conventions; RACE-EMAIL (`patch.object(DAOProfile, "get_by_email", return_value=None)`) in AUTH-RG-11 … 13; the fake `refresh_token_dao` (`SimpleNamespace(create=lambda *a, **k: None)`) via `monkeypatch.setattr(auth_service, …)` in AUTH-TP-13. No email or network call exists in this module (request_password_reset only builds messages).
- **Autouse `default_lifetimes`** (Conventions, revision 3) pins `ACCESS_TOKEN_EXPIRE_MINUTES = 15`, `REFRESH_TOKEN_EXPIRE_DAYS = 14`. AUTH-TP-09 sets them again inside the test.
- **Race cards** (Author: claude): RG-11 strict xfail BUG-2564 (IntegrityError inside `raises(ValueError)`), RG-12 passing recorder (one `INSERT INTO profiles`, nothing stays), RG-13 strict xfail BUG-1862. RF-15 (BUG-2560) is a recorder card: the `SELECT … refresh_tokens … token_hash` lookup has no `FOR UPDATE`; RF-14 is the sequential replay (pass).
- **Checks run:**
  - `--runxfail`: all 37 marked tests fail, each inside the Then line its card's "Fails today on" names (failures on the When line correspond to cards that say "Then 1 (the call raises …)").
  - In-process reference plugin (scratch `authe/merge/ref_auth.py` + `authe/authA|B|C/ref_auth*.py`, loaded with `-p ref_auth`, nothing under app/ touched): 217 passed with `--runxfail`.
  - 3 plain runs: 181 passed, 37 xfailed each time.
  - ruff clean, LF line endings.

## Discrepancies
Both closed by cases revision 3 (2026-11-10).

| ID | Case | Designed | Actual | Evidence | Likely cause |
|---|---|---|---|---|---|
| DISCREPANCY-1 (closed, rev 3) | all token cards (EXP15, NOW14, 900 / 1 209 600) | spec defaults 15 min / 14 days | the dev `.env` loaded by `settings` sets 30 / 7, so `exp` was 1772713800, not EXP15 | first smoke run: `assert 1772713800 == 1772712900` | Conventions gap: they assume the defaults but don't pin them. Handled by the autouse `default_lifetimes` fixture (environment, not the target's code; same as `security.cases.md`'s "Settings in every test"). Conventions should name it. |
| DISCREPANCY-2 (closed, rev 3) | AUTH-RG-22, LI-11, SW-13, RF-16, LO-12, AR-27, ME-31 | `rb.call_count == 1` after a failing commit | `2` | `BaseService._commit_transaction` rolls back and re-raises, then the method's own `except` rolls back again; every other Then line of these cards holds (checked with the count line relaxed in a scratch copy) | Card over-specifies: spec TC4 says only "rolled back" (department spec recorded the same double rollback). Route to describer / case designer: `rb.call_count >= 1`, or decide the double rollback is a defect. |

Card-text notes (fixed in revision 3): the Race simulations list named RG-12 … 14 and RF-18 / RF-17; it now says RG-11 … 13, RF-15 recorder, RF-14 replay.

## Coverage gaps
| Lines | Kind | What the code does there |
|---|---|---|
| 501 | unreachable | `switch_workspace`: "Workspace not found" after an active membership was found — the membership's foreign key cascades with the workspace (spec R2, no card) |
| 578 | unreachable | `refresh_access_token`: "User no longer exists" — the refresh row cascades with the profile (spec R5, no card) |
| 839 | unreachable | `reset_password_by_admin`: "Target user not found" — the membership row is deleted with the profile (spec R4, no card) |

## Factories added
None.

## Notes for maintainers
- Xfail reasons are `BUG_*` constants (title from `docs/testing/bugs.md`). When a bug is fixed its tests XPASS (strict → fail): remove the marker. Fixing BUG-1860 flips RG-05/06/07, LI-10 and FP-03 together.
- P34-01 … 03 pin today's R7 (pending OQ-34); an OQ-34 answer changes only those three.
- Slug cards use TAG so parallel runs never share a slug; `!!!` accepts `workspace` or `workspace-<n>`.
- No new bugs (BUG-2571 … 2589 unused).

## Revision history
- **Revision 5 (2026-11-22).** Cases revision 5 (TC3 audit: stripping the method's own rollback went unnoticed in `login_user` and `switch_workspace`, because LI-11 / SW-13 fail at the commit and `_commit_transaction` rolls back itself). New pass tests AUTH-LI-13 (after LI-12) and AUTH-SW-14 (after SW-13), helper `failing_issue()` (the clock with `app.core.security.utcnow` raising `RuntimeError("clock down")`, so the issue fails before any refresh row or commit). Each adds extra row X, checks x_gone straight after the call, `cm.call_count == 0` (db.commit spy), `rb.call_count == 1`, no refresh row. The trigger is the spec's clock external, not a patch of `_issue_token_pair`: the designer skill allows patching the target's own code only for race simulations. Proof: scratch plugin `C:/Users/User/AppData/Local/Temp/makorsh-pipeline/tc3fix/tc3fix_method.py` (in memory, strips `self._rollback_transaction(db)` in one method; app/ untouched): `login_user` stripped → LI-13 fails on Then 2 (`x_count == 1`), LI-11 still passes; `switch_workspace` stripped → SW-14 fails on Then 2, SW-13 still passes (`C:/Users/User/AppData/Local/Temp/makorsh-pipeline/tc3fix/proof.txt`). Result 183 passed / 37 strict xfail over 3 runs; `--runxfail` 37 failed / 183 passed (unchanged xfails); ruff clean, LF.
- **Revision 4 (2026-11-10).** Cases revision 4 (verifier routing, `login_user` R2): new pass test AUTH-LI-12 (UO, active owner of W1, logs in: no `workspace_id` claim, refresh row `workspace_id is None`), placed after LI-11. Variant check: an in-process plugin (scratch `authe/merge/mut_li12.py`) making login put the user's first active workspace into the session fails LI-12 on Then 2. Result 181 passed / 37 strict xfail over 3 runs; `--runxfail` 37 failed / 181 passed; reference plugin 218 passed with `--runxfail`; ruff clean, LF.
- **Revision 3 (2026-11-10).** Cases revision 3: AUTH-RG-22, LI-11, SW-13, RF-16, LO-12, AR-27, ME-31 now check `rb.call_count >= 1`; the seven tests were updated and their DISCREPANCY-2 strict-xfail markers (and `DISC_2`) removed. DISCREPANCY-1 closed: Conventions name the autouse `default_lifetimes` fixture (no code change). Race / recorder IDs fixed in Conventions (no test change). Result 180 passed / 37 strict xfail over 3 runs; `--runxfail` 37 fail on their named Then lines; reference plugin 217 passed with `--runxfail`; ruff clean, LF.
- **Revision 2 (2026-11-10).** First execution: 173 passed, 44 xfailed (37 bugs + 7 DISCREPANCY-2), DISCREPANCY-1 handled by the autouse fixture.
