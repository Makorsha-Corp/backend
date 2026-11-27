# Execution notes — `app/utils/attachment_allowlist.py`

> Cases: `tests/unit/utils/attachment_allowlist.cases.md` (revision 4) · Tests: `tests/unit/utils/test_attachment_allowlist.py` · Source commit: e48a092
> Result: 160 passed · 27 xfailed · 0 discrepancies · 0 errors (110 cases: 84 pass cases → 160 test items; 26 xfail cases → 27 test items, AAL-NUR-27 has 2 params) — branch coverage 100%
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/utils/test_attachment_allowlist.py -q -p no:cacheprovider --cov=app.utils.attachment_allowlist --cov-branch --cov-report=term-missing`

## How the tests are built
- **No database, no mocks, no race simulations.** The module is pure (spec Overview: externals none); no test takes the `db` fixture.
- **Conventions → helpers** (top of the test file):
  - `P(name, mime, size=1024, *, entity_type, entity_id, note)` → Payload P: `AttachmentSignRequest.model_construct(...)`, first `AttachmentEntityTypeEnum` member by default. The keyword overrides exist only for AAL-NUR-26 (last enum member, `entity_id=999`, `note="hello"`).
  - `T(rt="image")` / `TK(rt="image")` → Local type entry T / TK: a pdf-like `AttachmentTypeSpec` built positionally / with keywords (AAL-TSP-01, 02, 05).
  - `S(name, mime)` → Schema build S: real `AttachmentSignRequest(...)` validation, `note` omitted, `file_size=1024`. Used only by AAL-NUR-27…29 (target `schema`).
  - `DOCX` / `XLSX` → MIME constants.
  - `_ALLOWED` / `_NOT_ALLOWED` → the 11 table extensions and the 11 "anything else" extensions (DATA-06, EXT-10, EXT-11).
  - `BUG_120` … `BUG_125` → module-level `pytest.mark.xfail(strict=True, reason="BUG-NNN: <title>")` markers; titles copied from `tests/unit/utils/attachment_allowlist.bugs-staging.md` (the bugs are not merged into `docs/testing/bugs.md` yet — batch mode).
- **Collections** in `AttachmentTypeSpec` and `ALLOWED_MIME_TYPES` are compared with `set(...) == {...}` plus the explicit length checks the cases give.
- **Errors**: `pytest.raises(<exact class>)` then `str(exc.value) == <full message>`. AAL-VCR-20 uses `pytest.raises(ValueError)` as designed (regression part must pass before and after the BUG-124 fix).
- **Invisible characters** (AAL-SAN-07, 09…14, NUR-25) are written as Python escapes (` `, `‮`, `​`, `‍`, `﻿`, `­`, `\x85`, `\x80`, `\x9f`), as the cases file (revision 2) asks. An earlier draft of this file had them as literal characters; they were converted in this run (same code points, verified with `unicodedata` before and after).
- **Immutability cases (rev 4)**: AAL-TSP-01 and AAL-NRQ-01 are parametrized per field (`id="AAL-TSP-01-<field>"`, `id="AAL-NRQ-01-<field>"`) and use `setattr`; the re-check compares frozenset fields with `set(...) ==` and `r.spec` with `is`. AAL-TSP-03 assigns to the real shared `EXTENSION_TO_SPEC["pdf"]`; a `finally` block restores the old value with `object.__setattr__` if the assignment ever succeeds, so a regression cannot leak into other tests. `dataclasses.FrozenInstanceError` is the exact class asserted.
- **Parametrization**: cases that list several inputs with identical assertions (DATA-03, SAN-20, SAN-35, EXT-10, EXT-11, NUR-03, NUR-11, NUR-27, NUR-29, VCR-03, VCR-08, VCR-13, VCR-20) are one function each with `id="AAL-…-<variant>"`. Cases with (a)/(b) sub-steps and different expected values (SAN-08, SAN-11, EXT-05, VCR-02, VCR-04, VCR-05) are one test with sequential assertions.
- **xfail honesty** checked with `--runxfail`: every one of the 27 xfailed items fails exactly on the case's "fails today on" point (U+202E/U+200B/C1/Cf kept; no error for SAN-13; `" report.pdf"`, `"report.pdf "`, `" .report.pdf. "` for BUG-120; `….pd` / plain 255 cut / trailing spaces or dots for BUG-121; `AttachmentValidationError` on the MIME check for BUG-123; `Unsupported file extension: .pd` for NUR-24; no `ValidationError` for BUG-125; `AttachmentValidationError` instead of `AttachmentConfirmError` for BUG-124).
- Stability: 3 runs, identical outcome (160 passed, 27 xfailed). `--runxfail`: 27 failed, 160 passed (only the xfail items fail).

## Discrepancies
None.

## Coverage gaps
None — 100% branch coverage (61 statements, 18 branches). The `ext or '(none)'` fallback on line 133 is an inline expression, not a separate branch for coverage.py; the spec marks it unreachable and no case targets it.

## Factories added
None (batch mode; no DB models). `T` / `TK` stay local (only this module builds `AttachmentTypeSpec`). Candidates for promotion later: `P(...)` (`AttachmentSignRequest.model_construct` builder) and `S(...)` (validated `AttachmentSignRequest` builder) if `AttachmentManager` / `MobileUploadSessionManager` tests need sign payloads.

## Notes for maintainers
- When BUG-120 is fixed (repeated trim of whitespace/dots): AAL-SAN-17…19 XPASS → remove the markers.
- When BUG-121 is fixed (keep `.<ext>` on the 255 cut, re-trim at the cut): AAL-SAN-26…29, 31…33 and AAL-NUR-24 XPASS → remove the markers. AAL-SAN-30 and AAL-SAN-35 must keep passing.
- When BUG-122 is fixed (strip Unicode `Cc`/`Cf`): AAL-SAN-09…14 and AAL-NUR-25 XPASS. AAL-SAN-07 (NBSP kept) must keep passing — NBSP is `Zs`, not `Cf`.
- When BUG-123 is fixed (normalised MIME compare/return): AAL-NUR-20…23 XPASS; AAL-NUR-17…19 (message quotes the value as sent) must keep passing.
- When BUG-124 is fixed (confirm-time extension errors raise `AttachmentConfirmError`): AAL-VCR-17…19 XPASS; AAL-VCR-20 keeps passing because it only asks for `ValueError`.
- When BUG-125 is fixed (schema rejects blank `file_name`, fix lives in `app/schemas/attachment.py`): both AAL-NUR-27 params XPASS. AAL-NUR-28 (`" a.pdf "` accepted) and AAL-NUR-29 (`"<>"`, `"..."` accepted by the schema) must keep passing — a fix that strips/rejects too much breaks them.
- If the allowlist table changes, DATA-01…06, EXT-10/11, NUR-03, VCR-03 must change with it (update spec → cases first). The module docstring also points at a frontend mirror and a sync test that must be updated together.
- The file contains literal non-ASCII letters (AAL-SAN-06, 24, 25); keep it UTF-8 encoded.

## Revision history
- **Cases revision 4 (2026-09-29):** added AAL-TSP-01…05 (`AttachmentTypeSpec` frozen + hashable/value equality) and AAL-NRQ-01…03 (`NormalizedUploadRequest` frozen + hashable/value equality), all designed `pass`, all pass — they target verify findings #1/#2 (surviving mutants #31 L28 and #42 L109 `frozen=True` → `False`). Added helpers `T`/`TK` and the `dataclasses` / `AttachmentTypeSpec` imports. Existing 102 tests unchanged (AAL-NUR-27 already used the escapes `"\t \n"`, verify finding #3). No retired IDs. Result 145 → 160 passed, 27 xfailed unchanged.
