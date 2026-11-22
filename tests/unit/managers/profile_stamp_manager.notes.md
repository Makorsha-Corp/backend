# Execution notes — `app/managers/profile_stamp_manager.py`

> Cases: `tests/unit/managers/profile_stamp_manager.cases.md` (revision 3, READY) · Tests: `tests/unit/managers/test_profile_stamp_manager.py` · Source commit: e48a092
> Result: 59 passed · 44 xfailed · 0 discrepancies · 0 errors — branch coverage 100%
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/managers/test_profile_stamp_manager.py -q -p no:cacheprovider`

## How the tests are built
- **No database.** The manager has no persistence; no test requests `db`.
- **Conventions → code.** `M` = `profile_stamp_manager`; `TOKEN`, `OWN5`, `PRE5`, `TOKEN31`, `TOKEN33`, `TOKENU`, `TOKENG`, `VEC`, `KIND_MSG`, `FOREIGN_MSG` are module constants; `IMG(pid)` is a function returning a fresh dict per call; `U5` is a fixture (a fresh `SimpleNamespace` per test, so SG-07's `vars(U5)` check sees only this test). U55 is never used as an object by any card (only the id 55), so it has no fixture.
- **Settings (every test).** Autouse fixture `stamp_settings` sets the five settings with `monkeypatch.setattr(settings, …)` and returns a `setting(name, value)` function for a card's "settings:" Given lines.
- **Externals.** Patched only at the targets the spec names:
  - `dr` — `app.managers.profile_stamp_manager.destroy_resource`, `return_value={"result": "ok"}`, requested by every DS and VS test. A card's other `return_value` / `side_effect` is set on the mock before the When.
  - `gus` — `app.managers.profile_stamp_manager.generate_upload_signature`, `return_value="sig-x"`, only SG-01, SG-02, SG-06.
  - `fixed_uuid` (`…uuid.uuid4` → `uuid.UUID(TOKEN)`), `fixed_time` (`…time.time` → `1767225600.9`).
  - SG-03 … SG-05 and SG-07 sign for real: `generate_upload_signature` computes a SHA-1 locally (`cloudinary.utils.api_sign_request`) and sets the SDK's global config; no network call is made anywhere.
- **warnings** convention = fixture `warnings_log` (sets `caplog` to WARNING for `app.managers.profile_stamp_manager` before the When, returns a function that lists the records; called after the When).
- **xfail cards (user_id=).** Every BUG-1864 / BUG-1865 / BUG-1866 card calls with `user_id=`, which raises `TypeError` today. For "returns:" cards the call stands under the `# Then 1` comment (the card's "Fails today on: Then 1 (the call raises TypeError)"); for "raises:" cards the call is inside `pytest.raises(ValueError)`, which lets the `TypeError` escape at Then 1. Markers are `strict=True`, `raises` not narrowed, per Conventions.
- **Parametrized groups** (each case keeps its own param id): PSM-DS-17 … 24 (same two Then lines; differ in `public_id`, DS-18 in the caller's id) and PSM-VS-23 … 26, 28 … 31, 33 (same four Then lines; differ in `public_id`, VS-23 in the caller's id, VS-33 in the upload environment). VS-22 and VS-27 have a fifth Then line (`dr.call_count == 0`) and are separate tests. Revision 2 adds two more groups, kept apart so the Revision 1 tests stay unchanged: PSM-DS-25 … 32 (`test_psm_ds_25_to_32__not_minted_form_never_deleted`) and PSM-VS-38 … 44 (`test_psm_vs_38_to_44__not_minted_form_refused`), all with caller id 5.
- **VS-19, VS-20** ("for each k"): each `k` gets its own `pytest.raises(ValueError)`; the caught errors are then checked per Then line.

## Verification done at execution
- **Fail points (`--runxfail`, scratch plugin `stamp_ref.py`, mode `failpoint`).** All 42 xfail tests (Revision 2) fail at the card's named Then line: PSM-DS-13 on Then 2 (`AssertionError`, `len(warnings) == 1`, nothing logged); the 41 others on Then 1 with `TypeError` (no `user_id` parameter).
- **Reference fixes (scratch plugin, mode `reference`).** The plugin monkeypatches, in-process only, `ProfileStampManager.validate_saved_stamp_payload` and `destroy_saved_stamp_image` with the fixes (optional `user_id`; minted-form check (Revision 2: `re.fullmatch(<own prefix per build_stamp_public_id R1–R3> + [0-9a-f]{32})`) → `ValueError(FOREIGN_MSG)` / skip delete; url rebuilt with `build_signed_delivery_url(…, delivery_type="authenticated")`; `logger.warning` naming `public_id` and the error on a failed delete). With `--runxfail`: 101 passed, and a line tracer confirms that the last statement of each of the 42 xfail tests ran — every check after the failure point is reachable and holds under the intended behaviour.
- 3 plain runs: 59 passed, 42 xfailed each time (no flakiness). `ruff check` and `ruff format --check` clean; LF line endings.

## Discrepancies
None.

## Coverage gaps
None — 100% branch coverage (55 statements, 16 branches).

## Factories added
None.

## Notes for maintainers
- When BUG-1864 / BUG-1865 are fixed the new `user_id` parameter will probably become required; then the passing cards that call without it (VS-05 … VS-13, DS-09 … DS-14) need `user_id=5` added (spec Facts), and the xfail markers of VS-21 … VS-34, VS-38 … VS-44 / DS-16 … DS-32 come off.
- When BUG-1866 is fixed, VS-35 … VS-37 XPASS; cases gap 2 (is the client `url` still required, 1–2048 chars?) decides whether VS-10 … VS-12 must change.
- When BUG-1713 is fixed, DS-13 XPASSes; the logger must be named `app.managers.profile_stamp_manager` or the `warnings` helper will not see it.
- Running with coverage prints SQLAlchemy `SAWarning`s about re-registered generic functions (coverage re-import); harmless, unrelated to this module.

## Revision history
- **Revision 2 (2026-11-04)** — cases Revision 2 (from `profile_stamp_manager.verify.md` and spec revision 2026-11-04: a stamp id is exactly the user's prefix plus 32 lowercase hex characters). 84 → 101 cases, 59 pass / 42 strict xfail.
  - Added: VS-36, VS-37 (BUG-1866, client url on another cloud / on our cloud but another file); DS-25 … DS-32 (BUG-1865, parametrized); VS-38 … VS-44 (BUG-1864, parametrized). New Conventions PRE5, TOKEN31, TOKEN33, TOKENU, TOKENG as module constants; `SavedStampImage` imported.
  - Changed: VS-06, VS-07 now build `SavedStampImage` directly (target `schema`); renamed to `test_psm_vs_06__schema_accepts_public_id_512_chars` / `test_psm_vs_07__schema_refuses_public_id_513_chars`.
  - Retired: none. All other tests unchanged.
  - Reference plugin: the own-prefix `startswith` check became a `fullmatch` on prefix + exactly 32 lowercase hex, on both the validator and the delete side; url still rebuilt server-side. Under `--runxfail` with the fixes: 101 passed, last line of all 42 xfail tests ran. Without fixes, `--runxfail`: 41 fail with `TypeError` on Then 1, DS-13 with `AssertionError` on Then 2.
  - Coverage still 100% branch. No discrepancies, no new bugs.

- **Revision 3 (2026-11-04).** Cases Revision 3 (verify round 2, R2-1): 101 → 103 cases, 59 pass / 44 strict xfail.
  - Added PSM-DS-33 (BUG-1865) and PSM-VS-45 (BUG-1864), both with `public_id = OWN5 + "\n"`. Each is one more param in its existing group (`test_psm_ds_25_to_32__…`, `test_psm_vs_38_to_44__…`); the setup and checks are identical. Docstrings now name the full ranges.
  - Spec gap 2 is closed (validator R4b keeps the client url required and ignores it), so VS-10 … VS-12 stand unchanged. No test changed, and none were retired.
  - `--runxfail`, no fixes: 43 fail with `TypeError` on Then 1 (DS-33 and VS-45 among them); DS-13 fails with `AssertionError` on Then 2.
  - Reference plugin: `is_minted` uses `re.fullmatch` (prefix + exactly 32 lowercase hex). With it and `--runxfail`: 103 passed, and the last line of all 44 xfail tests ran. Counter-check with `STAMP_ANCHOR=dollar` (a `$`-anchored `re.match`, which accepts a trailing newline): exactly DS-33 and VS-45 fail and the other 101 pass. So the two new cards catch a fix that is not a full match.
  - 3 plain runs: 59 passed, 44 xfailed each time. Branch coverage still 100%. Ruff clean, LF. No discrepancies, no new bugs.
