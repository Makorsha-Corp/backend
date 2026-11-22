# Execution notes — `app/services/item_tag_service.py`

> Cases: `tests/unit/services/item_tag_service.cases.md` (revision 2) · Tests: `tests/unit/services/test_item_tag_service.py` · Source commit: e48a092
> Result: 68 of 68 cases implemented · 38 passed · 30 xfail as designed (28 strict, all xfailed; 2 non-strict: Y-04 xfailed in every run, T-08 XPASSed in every run on this server, see below) · 0 errors · 0 discrepancies — branch coverage 96% (the 3 missed lines are unreachable)
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/services/test_item_tag_service.py -q -p no:cacheprovider`

## How the tests are built
Same form as `department_service.notes.md`. This service has no manager and its own transaction (S1–S4).
- **Standing rows:** `w1`, `w2`, `u1`, `i1`, `ix` (autouse `standing_rows`).
- **Given rows:** `mk_tag(name, tag_code, **but)`, `mk_system_tag(name, tag_code, **but)`, `DELETED` (`is_active False`), `mk_link(item, tag)`. Index cards C-14, C-15 and C-23 insert with `ItemTag(**_tag_fields(...))` directly, as Conventions say (C-14 and C-23 inside `db.begin_nested()`).
- **Reading helpers:** `reread` (any model, also used for links), `snap_before` / `snap`, `stored_count(db, tag)` (a plain SELECT, no expire), `count_tags`, `written`, `new_row(db, w1, given=())`, `ids`, `unloaded`, `usable`, `spies`.
- **Race simulation:** C-29 only, `patch.object(item_tag_dao, "get_by_code_in_workspace", return_value=None)` inside the `raises:` wrap.
- **S3:** C-11, U-01, U-05 and D-02 keep an uncommitted extra tag and check that it is still there after the refusal. The failing-commit cards check that it is gone.

## Fails-today check
`--runxfail`, failing line mapped to its `# Then N`, value read:
- T-06, T-07: Then 2, `ItemTagResponse` refuses `café` / `""`.
- C-04 … C-06, C-08, C-09: Then 1, codes `café`, `""`, 60 × `a`, `_bolt_`, `কচমল`.
- C-10, U-10, U-13: Then 1 `DID NOT RAISE ValidationError`.
- C-13, C-16, C-17: the 409 in the When, just before `# Then 1`, the error their cards name.
- C-14, C-23: Then 1 `DID NOT RAISE IntegrityError`.
- C-18, C-19, C-29, U-03, U-04, U-11, D-04: Then 1 `DID NOT RAISE HTTPException`.
- C-20: Then 3, the code's message comes instead of the name's.
- U-09: Then 2 `'#000000' is None`. U-14: Then 2 `'  Steel  '`.
- Y-04 (non-strict, BUG-929): Then 2 `['Tool', 'consumable', 'Bolt']`, in every run.
- **T-08 (non-strict, BUG-930): XPASS in all 7 runs.** The DAO orders by `name` in the server's collation, and `marker_test` is `English_United States.1252`, which already sorts case-insensitively. The card says the order "rests on the server's collation", and it is non-strict, so this is as designed. Proof with a scratch plugin that orders the same query by `name COLLATE "C"` (a C-locale server): T-08 fails at Then 2, `['Alpha', 'Charlie', 'bravo']`, its card's line and reason.

## Reference run
`refplug.py` (scratch) replaced the five service methods with the spec's intended behaviour:
- codes: derived from the trimmed name in ASCII, cut to 50, `tag` when nothing is left, first free `_2`, `_3`…; only live tags block a code (through the DAO, so C-29's patch applies);
- names: the live-name check comes before the code check;
- refusals: 404 for a deleted tag;
- update: explicit nulls clear `color`, `icon`, `description`;
- lists: ordered by `lower(name), id`;
- a unique violation at the flush becomes the 409 after the rollback.

Schemas: `ItemTagCreate` / `ItemTagUpdate` trim, refuse blank names and refuse null `name` / `is_active`; `ItemTagResponse` takes any stored code. Inside each test's transaction the plugin created partial unique indexes on live tags for `(workspace_id, tag_code)` and `(workspace_id, lower(btrim(name)))`.

With `--runxfail` all 64 tests passed. The first reference run had 1 failure, C-13: my reference still counted deleted tags' codes, so I fixed the reference. No test changed. Without `--runxfail` all 25 strict cards XPASSed (strict, so they failed) and both non-strict cards XPASSed.

## Stability
5 plain runs plus seqscan off and index/bitmap scans off: 37 passed, 26 xfailed, 1 xpassed (T-08) in all 7; no test moved. Ruff passes; LF.

## Discrepancies
None. The spec gap filled in parallel (R4 covers a sent code only, G1) holds: C-11 passes; C-16 and C-17 are R7's xfails.

## Coverage gaps
| Lines | Kind | What the code does there |
|---|---|---|
| 53, 71, 87 | unreachable | `except HTTPException: raise` in `create_tag`, `update_tag`, `delete_tag`: nothing inside those `try` blocks raises an `HTTPException` (spec Branch map, FU-3). |

96% line coverage (69 statements, 3 missed); all 14 branches covered, 0 partial.

## Factories added
None.

## Revision history
- **Cases revision 2:** added ITS-C-30, C-31, U-18 (strict xfail BUG-1531, fail today at Then 1 `DID NOT RAISE HTTPException`) and D-07 (pass), from verify R-IT-1 … R-IT-4. No other test changed. 3 plain runs: 110 passed, 43 xfailed, 1 xpassed for the three revised files; reference with `--runxfail`: all pass. Verifier variants rebuilt in scratch `varplug.py` (the BUG-1531 ones on top of `refplug.py`, `--runxfail`): `delete_s3_rollback_on_403` fails D-07 at Then 3 (`0 == 1`); `create_s3_rollback_on_name_409` fails C-30 at Then 3; `update_s3_rollback_on_name_409` fails U-18 at Then 3; `create_r8_untrimmed_message` fails C-31 at Then 3 (`' PAINT '` in the message).

## Notes for maintainers
- T-08 XPASSes on a case-insensitive collation; on a C-locale server it fails at Then 2. Both are fine while BUG-930 is open. The card stays non-strict until the fix orders by `lower(name), id`.
- The 3 unreachable `raise` lines go away with the fixes (spec FU-3).
