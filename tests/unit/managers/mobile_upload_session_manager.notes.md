# Execution notes — `app/managers/mobile_upload_session_manager.py`

> Cases: `tests/unit/managers/mobile_upload_session_manager.cases.md` (revision 5) · Tests: `tests/unit/managers/test_mobile_upload_session_manager.py` · Source commit: e48a092
> Result: 188 passed · 90 xfailed · 0 discrepancies · 0 errors — branch coverage 100%
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/managers/test_mobile_upload_session_manager.py -q -p no:cacheprovider --cov=app.managers.mobile_upload_session_manager --cov-branch --cov-report=term-missing` (with a private `COVERAGE_FILE`)

## How the tests are built
- **One test per card, 275 tests**, named `test_mobs_<area>_<nn>__<slug>`; first docstring line is the card ID and title, second the rules. `# Then N` precedes the checks of Then line N. For the four cards whose "Fails today on" says the call itself raises (C-06 `DataError`, EA-09, GC-12 `TypeError`, PF-14), the `# Then 1` comment stands before the call, as in `test_project_manager.py` (PRJM-G-07).
- **Fixture `CL` (autouse)** implements "Settings and time" and "Cloudinary": `monkeypatch` on `app.core.config.settings` (the six values); `patch` of `utcnow` in this module and in `app.dao.mobile_upload_session` (NOW); `uuid.uuid4`, `time.time`, `secrets.token_urlsafe` through this module (fixed uuid / time / raw); the six Cloudinary names on `app.managers.mobile_upload_session_manager` (gus, gr, dr, rr, um, bsdu) and the four on `app.managers.attachment_manager` (agr, adr, ags, absdu), each `patch(<target>, autospec=True)` (Revision 4), so a keyword the real function does not have raises `TypeError`. `kw(m)` binds the call to `inspect.signature(m)` and applies defaults (Conventions), so `kw(dr)["delivery_type"]` is exact. No other target is patched; nothing reaches the network. `CL.real("uuid" | "raw" | "gus")` undoes one patch for "real uuid" (PI-04), "real raw" (TK-02), "real gus" (SG-16). `CL.setting(name, value)` is a Given "settings:" line. `cl_called(CL) == []` is the named check **cl_untouched** (it lists any of the ten mocks that was called).
- **Fixture `R`** = Standing rows (W0, W1, W2, U1, U2, UG, their W1 memberships with `R.MG` = UG's, F0, F1, F9, WT1, P1), built in the Conventions order after `SET LOCAL TIME ZONE 'UTC'`. It is named `R` because the cards use `S` for the session row. Pure cards (N, H, E, PI, AF, TK, NP) do not build it.
- **Given helpers**: `member`, `mg_but` ("UG's W1 membership but …"), `REMOVED`, `drop_mg` (`db.delete(MG)`), `set_owner`, `proj`, `pmem`, `comp`, `machine`, `wo`, `po` (Status row of the po's workspace first), `ticket`, `sess(R, "sess" | "staged" | "uploaded", **but)` (returns an unsaved row; `add(db, row)` flushes it), `full(db, R, P)`.
- **Checks**: `reread` (expire_all + `db.get`), `snap` / `unchanged` (all mapped columns), `counts` ("nothing written": the five tables, all workspaces, via `SELECT count(*)`), `count(table, cond, **params)`, `recorder` (GC-12), `warnings_log` (caplog at WARNING on this module's logger), commit spy as in the Conventions ("Rolled back").
- **Generated cards.** The 30 create-session refusal cards (C-08 … C-50) and the 38 promote refusal cards (PM-26 … PM-67) differ only in Given rows and the subset of Then lines; they were written from a table by a scratch script (`atte/mobs/gen_refusals.py`, not part of the repo) that emits plain, individual tests in card order. Each generated test lists its own Then lines exactly as its card does (e.g. PM-40 has no `not db.new`; PM-26 has `nothing written`).
- **Enum names**: the cards write `ET.project`, `MobileUploadSessionStatusEnum.uploaded`; the enums' members are upper case (`ET.PROJECT`, `.UPLOADED`), same values.
- **`delivery_type None` on a saved session** (PV-02, CF-03, DS-02, PM-03): the column is NOT NULL with ORM default `"authenticated"`, and an explicit `None` at insert gets the default (verified). PV-02 and DS-02 call methods that never flush, so they also set `S.delivery_type = None` in memory after the flush, giving the card's input exactly. CF-03 and PM-03 flush inside the call, where a `None` would fail the NOT NULL constraint, so their rows carry the stored default; their Then lines (`kw(…)["delivery_type"] == "authenticated"`) hold either way.

### Verification done
- **3 plain runs**: 188 passed, 87 xfailed each time (no flakiness).
- **`--runxfail`**: all 87 strict xfails fail, each inside the Then block its card names (checked by a scratch pytest plugin that maps the last traceback line in the test file to the preceding `# Then N` comment and compares it with the card's "Fails today on"; 87/87 OK). There are no non-strict xfails in this file.
- **Reference plugin** (`atte/mobs/ref_mobs.py`, scratch only): patches the intended fix of BUG-1282, BUG-2130 … BUG-2136, BUG-2138 … BUG-2141 into the manager class in-process, plus (Revision 3) the link-DAO fixes BUG-1433 (links ORDER BY id) / BUG-1434 (failed uploads not counted toward the capacity check). `-p ref_mobs --runxfail`: **275 passed**, so every line after each xfail's failure point runs and holds against the intended behaviour. Its PR-1 / PR-2 check reads the role from the active W1 membership and `is_platform_admin` (PR-5), uses `ProjectManager.can_access_project` and `HelpTicketManager.can_access_ticket`, and runs, at promote, right after the session-state checks: before any validation error (size, `normalize_upload_request`), the capacity check and `rename_resource` (Revision 4). Revision 4 also lets the workspace owner (`owner_user_id`) open every ticket (BUG-2103); a platform admin gets no grant on a private project or its component (`can_access_project` already ignores `is_platform_admin`).
- **ruff** clean (repo defaults), LF line endings, no unused test arguments.

## Discrepancies
None.

PM-27, PM-35, PM-36: the revision-2 observation (they fail at Then 1 with `IntegrityError` on the parent's activity table after the Cloudinary move, not with "no error") is now the cards' own Fails-today wording (Revision 3). Evidence for BUG-2134 / BUG-2133; no new bug ID.

## Coverage gaps
None — 100% branch coverage (220 statements, 54 branches).

## Factories added
None. Every builder is local to the test file.

## New bugs
None (BUG-2170 … BUG-2179 unused).

## Notes for maintainers
- When a bug is fixed its cards XPASS (strict → fail): remove that bug's `XF…` marker from those tests. BUG-2130/2131: C-08 … C-50 refusal cards; BUG-2134: PM-26 … PM-67 refusal cards; BUG-2133: PM-19; BUG-2132: RL-09, C-06; BUG-2135: PF-10 … PF-14; BUG-2136: DS-07, PM-23; BUG-2138: CN-06, CN-07; BUG-2139: GC-12; BUG-2140: SG-12, SG-13; BUG-2141: CF-19, PM-21; BUG-1282: N-03, C-02, EA-08, EA-09.
- BUG-1282's DAO half (`app.dao.mobile_upload_session._naive_utc`) is the DAO spec's; the reference plugin fixes only this module's copy, and no card here depends on the DAO's.
- GC-12 calls `get_for_creator(..., for_update=True)`; when BUG-2139 is fixed with another parameter name, the card (not the test) must change first.
- `fixed time` patches `time.time` through this module, i.e. the global `time.time`, for the whole test (as `test_profile_stamp_manager.py`). Nothing in the DB layer depends on it today.
- `token_hash` is unique: cards that build several sessions give each its own `H(RAW…)`; keep that when adding cards.

## Revision history
- **2026-11-04 — Revision 2** (first execution): 267 cases → 184 passed · 83 xfailed; no discrepancies; one observation on PM-27 / PM-35 / PM-36 wording.
- **2026-11-04 — Revision 3** (cases updated from these notes; no card added or removed): PM-27, PM-35, PM-36 Fails-today lines now name the IntegrityError (observation closed). No test code changed. Reference plugin extended with BUG-1433 / BUG-1434; 3 plain runs 184 passed · 83 xfailed; `--runxfail` 83/83 fail on their named Then line; `-p ref_mobs --runxfail` 267 passed; coverage 100%; ruff clean.
- **2026-11-04 — Revision 4** (verifier findings 1–4, spec PR-2 revision): 275 cases → 188 passed · 87 xfailed.
  - New C-51, C-52, PM-69, PM-70 (platform admin with no membership refused a private project / its component; strict xfail BUG-2131 / BUG-2134) and C-53, PM-71 (workspace owner with a plain role opens another member's ticket; pass, BUG-2103 guard).
  - New CF-23, PM-68: a stored `delivery_type "upload"` reaches `get_resource` / `rename_resource`.
  - PM-19 and the 31 refusal cards among PM-26 … PM-67 that carry it: the `status` / `public_id` re-read became `unchanged(S)` (whole row, snapshot `before_s` taken just before the When); PM-40 … PM-48, PM-50 … PM-52 gained it as a new last Then line.
  - Every Cloudinary patch is `autospec=True`; `kw(m)` is the bound argument set with defaults; the `.get(…, default)` checks (SG-03, SG-10, CF-02, CF-03, CF-10, DS-01, DS-02, PM-02, PM-03) are now `kw(m)[…]`.
  - Reference plugin: workspace owner opens tickets (BUG-2103); PR-1 / PR-2 at promote moved before any validation error. `--runxfail` 87/87 fail on their named Then; `-p ref_mobs --runxfail` 275 passed; coverage 100%; ruff clean; LF. No discrepancies, no new bugs.
- **2026-11-04 — Revision 5** (spec G6 / BUG-2134; 278 cases → 188 passed · 90 xfailed, all strict):
  - New PM-72 (oversized), PM-73 (MIME mismatch), PM-74 (record at capacity via `full(PV)`): a hidden private project answers 404 with the session row unchanged and Cloudinary untouched. Strict xfail BUG-2134; under `--runxfail` each fails in Then 1 with the error its card names (AttachmentValidationError size / type, AttachmentLimitError).
  - Reference plugin: promote's PR-1 / PR-2 check already ran after the session-state checks and before size, name, type and limit (moved there in Revision 4); `-p ref_mobs --runxfail` 278 passed. Order check: a scratch variant with the visibility check placed after the size check (`late/ref_mobs_late.py`, built by `make_late.py`) fails PM-72 only (1 failed, 277 passed).
  - 3 plain runs 188 passed · 90 xfailed; `--runxfail` 90/90 fail on their named Then; coverage 100%; ruff clean; LF.
