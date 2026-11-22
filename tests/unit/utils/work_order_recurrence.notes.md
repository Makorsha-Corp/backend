# Execution notes — `app/utils/work_order_recurrence.py`

> Cases: `tests/unit/utils/work_order_recurrence.cases.md` (revision 5) · Tests: `tests/unit/utils/test_work_order_recurrence.py` · Source commit: e48a092
> Result: 82 cases → 111 passed · 37 xfailed (test items, incl. parametrised variants; 70 pass cases / 12 xfail cases) · 0 discrepancies · 0 errors — branch coverage 100%
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/utils/test_work_order_recurrence.py -q -p no:cacheprovider --cov=app.utils.work_order_recurrence --cov-branch --cov-report=term-missing`

## How the tests are built
- **No database, no mocks** (Conventions). The `db` fixture is not used; the module is pure. Nothing is patched.
- **`T(recurrence_type, **overrides)`** implements the "Template stand-in" convention: a `types.SimpleNamespace` with the six attributes, defaults from prior state P (`_PRIOR`: recurring, day 4, start 2025-01-01, end 2025-02-01, next 2025-01-15).
- **`snap(t)`** implements "Unchanged": `vars(t).copy()` before the call, `vars(t) == before` after it. "Re-read" is not applicable (in-memory object only; the spec says nothing is persisted).
- **`create(**fields)`** implements the schema convention: `WorkOrderTemplateCreate(template_name="T", work_order_type_id=1, **fields)`. `WorkOrderTemplateUpdate` is built directly with only the named fields.
- **`assert_rejected(exc, field=None)`** implements "Rejected": the `ValidationError` loc must include `recurrence_type`, `recurrence_day`, or be the model root `()`. Cases that name the field (ADV-23, ADV-25: "on `recurrence_type`") pass `field="recurrence_type"`; the day-range and missing-type cases (ADV-27, -29, -31) accept any of the three, since the fix may be a field or model validator.
- **`adv(from, type, day)`** is a keyword-forwarding wrapper around `advance_next_generation_date` (all calls keyword-only as the cases require).
- `E_BACK` / `E_SPAN` hold the exact messages; errors are asserted with `str(exc.value) == ...`.
- ADV-37 is one parametrised test over (schema, value): three `create(...)` variants and one `WorkOrderTemplateUpdate(...)` variant, each asserting `.recurrence_type.strip().lower() == expected` (the non-rejection half of ADV-22/-24; passes today and after the BUG-360 fix).
- Multi-input cases are parametrised with per-variant ids `WOR-<C>-NN-<variant>`. ACT-03/04/05 and SHA-01/02/03, SHA-04/05 share identical setup and differ in one input, so each is one parametrised test with the case ID as the param id.
- Every xfail was checked with `--runxfail`: each fails on the designed "fails today on" assertion (`DID NOT RAISE ValueError` / `DID NOT RAISE ValidationError` / the un-normalised value such as `' Weekly ' == 'weekly'`), never on setup.

## Discrepancies
None.

## Coverage gaps
None — 100% branch coverage (55 statements, 26 branches).

## Factories added
None (batch mode: `tests/unit/factories.py` not edited). `T(...)` / `snap(...)` are module-local; a `make_template_namespace` builder could be promoted later if other work-order-template helper tests (e.g. `work_order_generation`, `work_order_calendar`) need the same six-attribute stand-in.

## Notes for maintainers
- When **BUG-360** is fixed: ADV-19, -22, -23, -24, -25, APR-09 (non-`None` variants), RESEED-06 will XPASS (strict) → remove their markers. APR-09 carries both BUG-360 and BUG-361 in one marker; all variants must be fixed together or split the parametrisation.
- When **BUG-361** is fixed: ADV-20, ADV-27, APR-09 (`None`), SEED-07 will XPASS → remove markers.
- When **BUG-362** is fixed: ADV-29, ADV-31 will XPASS → remove markers. ADV-30/32/33/34/35/36 are guard tests: they must keep passing (the fix must not range-check daily/untyped templates or the update schema alone).
- **BUG-363** has no xfail here: its fill logic is deferred to `WorkOrderTemplateManager`; ADV-18 (helper side) passes today.
- APR-10 pins the validation order (range error before type error); a BUG-360/361 fix that checks the type first will break it — that would contradict spec APR R4a.
- The R7 upper clamp (>31 → 31) is observationally equivalent to the R6 month-end cap; a mutant removing only the upper clamp survives (documented in the cases file, not a gap).

## Revision history
- **Cases rev 4 (post-verify fix):** verify.md finding #1 (test-weakness, fix-by executor) fixed — `test_wor_apr_04__monthly_day_overwritten` now asserts `_apply_recurrence_range(...) is None`, as the `_apply_recurrence_range` section preamble requires for every success case. No cases added, changed or retired in rev 4; no other tests touched. Re-run: 107 passed · 37 xfailed · 100% branch coverage (unchanged). Surviving mutants #7/#28/#78/#40 (BUG-360/361 fallback path) and #38/#39/#74 (equivalent) need no test change (cases rev 4, best-practice default, delegated by reviewer).
- **Cases rev 5:** new pass case WOR-ADV-37 added as `test_wor_adv_37__padded_mixed_case_supported_type_not_rejected` (4 param variants). WOR-APR-04's Then now names `returns None` explicitly; the test already asserted it since rev 4, so it was not changed. No other tests touched, no IDs retired. Re-run (x3, stable): 111 passed · 37 xfailed; `--runxfail`: 37 failed / 111 passed (all xfails still fail on their designed assertions); branch coverage 100%.
