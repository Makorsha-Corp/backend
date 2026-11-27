# Test cases — `app/utils/attachment_allowlist.py`

> **Spec:** `tests/unit/utils/attachment_allowlist.spec.md` (source commit `e48a092`)
> **Status:** READY
> **Revision:** 4 — spec G2/G3 added `AttachmentTypeSpec` R1–R2 and `NormalizedUploadRequest` R1–R2 (frozen, hashable, value equality). Added AAL-TSP-01…05 and AAL-NRQ-01…03 (all pass). Verify findings addressed: #1 / mutant #31 (L28 `frozen=True`) → AAL-TSP-01…03; #2 / mutant #42 (L109 `frozen=True`) → AAL-NRQ-01, AAL-NRQ-02; #3 (literal TAB/NEWLINE in AAL-NUR-27 row) → rewritten as the escapes `"\t \n"`. No existing case changed in meaning or renumbered.
> **Revision 3:** spec gap G1 closed: new rule `normalize_upload_request` R2a [BUG-125] (whitespace-only `file_name` rejected by `AttachmentSignRequest` with a Pydantic `ValidationError`; non-blank names that clean to empty still get the module's 400). Added AAL-NUR-27 (xfail BUG-125), AAL-NUR-28…30 (pass); removed the HR-1 Deferred row and Spec gap 1. No existing case changed or renumbered. No verify report exists yet.
> **Revision 2:** re-run on unchanged spec (commit `e48a092`); no case added, removed or renumbered. Invisible characters in AAL-SAN-07, AAL-SAN-09…14 and AAL-NUR-25 are now written as explicit Python escapes (`\u00a0`, `\u202e`, `\u200b`, `\u200d`, `\ufeff`, `\u00ad`) so the executor copies them exactly. No verify report exists yet.
> **Counts:** 110 cases · 84 expected-to-pass · 26 expected-to-fail (bugs) · 4 deferred

## Reviewer summary
- **Per callable:** allowlist data 6 cases (0 bug) · `AttachmentTypeSpec` 5 (0 bug) · `NormalizedUploadRequest` 3 (0 bug) · `sanitize_file_name` 35 (16 bug) · `extract_extension` 11 (0 bug) · `normalize_upload_request` 30 (7 bug) · `validate_cloudinary_resource` 20 (3 bug)
- **Notable design choices:**
  - Pure module: no database rows, no mocks. Tests call the four functions (and the two dataclasses) directly and check return values / raised errors only.
  - All `normalize_upload_request` payloads are built with `AttachmentSignRequest.model_construct(...)` so the unit is isolated from whatever the schema might do to the values (best-practice default, delegated by reviewer).
  - `U+0085` (C1 "next line") is placed in the MIDDLE of the name, because it may count as whitespace for trimming; at the edge it could disappear today and make the strict xfail pass by accident.
  - Characters not in the R2/R2a removal sets are treated as kept; `~` (code 126) is used as the kept upper neighbour of code 127 (best-practice default, delegated by reviewer).
  - The "extension no longer allowed" scenario (BUG-124) is covered with `zip` (never allowed); simulating a shrunken allowlist would mean patching module data, which is not allowed.
  - BUG-125 cases (AAL-NUR-27…29) build `AttachmentSignRequest(...)` for real (not `model_construct`), because the rule is about the schema; they are listed under `normalize_upload_request`, target `schema`. AAL-NUR-28 does not assert whether the schema itself trims `" a.pdf "` — the spec only says it is accepted; the result is checked after `normalize_upload_request` (best-practice default, delegated by reviewer).
  - Immutability cases assign to a freshly built `AttachmentTypeSpec` or to a `normalize_upload_request` result, except AAL-TSP-03, which assigns to the shared `EXTENSION_TO_SPEC["pdf"]` entry exactly as the spec's example does; that test restores the original value in a `finally` block so a regression (assignment succeeding) cannot leak into other tests (best-practice default, delegated by reviewer).
  - Every xfail group has a matching pass case for what already works (length ≤ 255 after a cut; MIME error quoting the value as sent; confirm-time extension errors are a `ValueError` with the exact message).
- **Needs a decision:** None.

## Conventions for this module
- **Module abbreviation:** `AAL` = attachment_allowlist.
- **Callable abbreviations:** `DATA` = module constants (`EXTENSION_TO_SPEC`, `ALLOWED_MIME_TYPES`, `MAX_FILE_SIZE_BYTES`) · `SAN` = `sanitize_file_name` · `EXT` = `extract_extension` · `NUR` = `normalize_upload_request` · `VCR` = `validate_cloudinary_resource` · `TSP` = `AttachmentTypeSpec` · `NRQ` = `NormalizedUploadRequest`.
- **Local type entry T(rt="image"):** `AttachmentTypeSpec(frozenset({"pdf"}), frozenset({"application/pdf"}), rt, frozenset({"pdf"}))` (positional); `TK(rt="image")` = the same values passed as keywords `extensions=…, mime_types=…, resource_type=rt, confirm_formats=…`.
- **Database:** not used (spec: pure functions, no DB session needed). No rows, no rollback assertions.
- **Externals mocked:** none (spec lists none).
- **Race simulations:** none.
- **Schema build S(name, mime):** `AttachmentSignRequest(entity_type=<first member of AttachmentEntityTypeEnum>, entity_id=1, file_name=name, mime_type=mime, file_size=1024)` — real validation, `note` omitted. Used only for R2a (BUG-125) cases.
- **Payload P(name, mime, size=1024):** `AttachmentSignRequest.model_construct(entity_type=<first member of AttachmentEntityTypeEnum>, entity_id=1, file_name=name, mime_type=mime, file_size=size, note=None)` (best-practice default, delegated by reviewer).
- **Collections in `AttachmentTypeSpec`** (`extensions`, `mime_types`, `confirm_formats`) and `ALLOWED_MIME_TYPES` are compared as sets (`set(x) == {...}`), plus an explicit length check where the spec gives a count; the spec does not say which container type is used (best-practice default, delegated by reviewer).
- **Error checks** use `pytest.raises(<exact class>)` and compare `str(exc)` to the full message exactly (not a regex prefix).
- `NormalizedUploadRequest` results are checked field by field.
- MIME constants: `DOCX` = `application/vnd.openxmlformats-officedocument.wordprocessingml.document`, `XLSX` = `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`.
- **The allowlist table** (Overview of the spec) is referred to as "the table"; parametrized cases copy it literally into the test.

## Module data (`EXTENSION_TO_SPEC`, `ALLOWED_MIME_TYPES`, `MAX_FILE_SIZE_BYTES`)

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| AAL-DATA-01 | Overview table | happy | module imported | read `EXTENSION_TO_SPEC` keys | `set(keys) == {"jpg","jpeg","png","webp","heic","heif","pdf","docx","xlsx","txt","csv"}`; `len == 11`; every key is lowercase | pass |
| AAL-DATA-02 | Overview (jpg/jpeg share) | happy | module imported | read `EXTENSION_TO_SPEC["jpg"]` and `["jpeg"]` | `EXTENSION_TO_SPEC["jpg"] is EXTENSION_TO_SPEC["jpeg"]`; its `extensions` as a set == `{"jpg","jpeg"}`; `mime_types` == `{"image/jpeg"}`; `resource_type == "image"`; `confirm_formats` == `{"jpg","jpeg"}` | pass |
| AAL-DATA-03 | Overview table | happy | module imported | parametrized over the 9 other rows: png, webp, heic, heif, pdf, docx, xlsx, txt, csv | for each: `mime_types`, `resource_type`, `confirm_formats` equal the table (e.g. csv → `{"text/csv","text/plain"}`, `"raw"`, `{"csv","txt"}`; pdf → `{"application/pdf"}`, `"image"`, `{"pdf"}`; docx → `{DOCX}`, `"raw"`, `{"docx"}`); `extensions` contains the key | pass |
| AAL-DATA-04 | Overview (MIME union) | happy | module imported | read `ALLOWED_MIME_TYPES` | `set(...) == {"image/jpeg","image/png","image/webp","image/heic","image/heif","application/pdf",DOCX,XLSX,"text/plain","text/csv"}`; `len(ALLOWED_MIME_TYPES) == 10` (`text/plain` once) | pass |
| AAL-DATA-05 | Overview (max size) | happy | module imported | read `MAX_FILE_SIZE_BYTES` | `== 10485760` | pass |
| AAL-DATA-06 | Overview (anything else not allowed) | boundary | module imported | check keys `zip, bin, doc, xls, docm, xlsm, svg, html, js, exe, gif` | none of them is in `EXTENSION_TO_SPEC` | pass |

## `AttachmentTypeSpec`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| AAL-TSP-01 | R1 / Errors row "Assigning" | error | `t = T()` | parametrized over the 4 fields: `t.extensions = frozenset({"exe"})`; `t.mime_types = frozenset({"text/html"})`; `t.resource_type = "raw"`; `t.confirm_formats = frozenset({"exe"})` | each raises `dataclasses.FrozenInstanceError`; afterwards the field still equals its original value (`{"pdf"}`, `{"application/pdf"}`, `"image"`, `{"pdf"}` respectively) | pass |
| AAL-TSP-02 | R1 / Errors row "Assigning / deleting" | error | `t = T()` | (a) `t.extra = 1` (new attribute); (b) `del t.resource_type` | (a) raises `dataclasses.FrozenInstanceError` and `hasattr(t, "extra")` is `False`; (b) raises `dataclasses.FrozenInstanceError` and `t.resource_type == "image"` | pass |
| AAL-TSP-03 | R1 (shared entry) | error | module imported | `EXTENSION_TO_SPEC["pdf"].resource_type = "raw"` (test restores the old value in `finally` if the assignment ever succeeds) | raises `dataclasses.FrozenInstanceError`; `EXTENSION_TO_SPEC["pdf"].resource_type == "image"`; `EXTENSION_TO_SPEC["jpg"].resource_type == "image"` | pass |
| AAL-TSP-04 | R2 (hashable) | happy | module imported | `hash(EXTENSION_TO_SPEC["pdf"])`; `s = set(EXTENSION_TO_SPEC.values())`; `d = {EXTENSION_TO_SPEC["png"]: "x"}` | `hash(...)` returns an `int` (no error); `len(s) == 10` (11 keys, jpg/jpeg share one entry); `d[EXTENSION_TO_SPEC["png"]] == "x"` | pass |
| AAL-TSP-05 | R2 (value equality — both sides) | boundary | `a = T()`, `b = TK()`, `c = T("raw")` | compare | `a == b`; `a is not b`; `hash(a) == hash(b)`; `len({a, b}) == 1`; `a == EXTENSION_TO_SPEC["pdf"]` (same field values as the table's pdf row); `a != c`; `len({a, c}) == 2` | pass |

## `NormalizedUploadRequest`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| AAL-NRQ-01 | R1 / Errors row "Assigning" | error | `r = normalize_upload_request(P("photo.png", "image/png"))` | parametrized over the 5 fields: `r.file_name = "x.exe"`; `r.mime_type = "text/html"`; `r.resource_type = "raw"`; `r.extension = "exe"`; `r.spec = EXTENSION_TO_SPEC["pdf"]` | each raises `dataclasses.FrozenInstanceError`; afterwards the field still equals its original value (`"photo.png"`, `"image/png"`, `"image"`, `"png"`, and `r.spec is EXTENSION_TO_SPEC["png"]` respectively) | pass |
| AAL-NRQ-02 | R1 / Errors row "Assigning / deleting" | error | `r = normalize_upload_request(P("photo.png", "image/png"))` | (a) `r.extra = 1`; (b) `del r.file_name` | (a) raises `dataclasses.FrozenInstanceError` and `hasattr(r, "extra")` is `False`; (b) raises `dataclasses.FrozenInstanceError` and `r.file_name == "photo.png"` | pass |
| AAL-NRQ-03 | R2 (hashable, value equality — both sides) | boundary | `r1 = normalize_upload_request(P("photo.png", "image/png"))`, `r2 = normalize_upload_request(P("photo.png", "image/png"))`, `r3 = normalize_upload_request(P("other.png", "image/png"))` | compare | `r1 == r2`; `r1 is not r2`; `hash(r1) == hash(r2)`; `len({r1, r2}) == 1`; `r1 != r3`; `len({r1, r3}) == 2` | pass |

## `sanitize_file_name`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| AAL-SAN-01 | R1 | happy | — | `sanitize_file_name("a/b\\c.pdf")` (one forward slash, one backslash) | returns `"a-b-c.pdf"` | pass |
| AAL-SAN-02 | R1, R3 | happy | — | `sanitize_file_name("../x.pdf")` | returns `"-x.pdf"` (R1 gives `"..-x.pdf"`, R3 removes the leading dots) | pass |
| AAL-SAN-03 | R1, R4 | boundary | — | `sanitize_file_name("///")` | returns `"---"` (not empty, no error) | pass |
| AAL-SAN-04 | R2 | happy | — | `sanitize_file_name("re\x00po\x1frt\x7f.pdf")` | returns `"report.pdf"` | pass |
| AAL-SAN-05 | R2 | happy | — | `sanitize_file_name('a<b>c:d"e\|f?g*h.pdf')` (chars `< > : " \| ? *`) | returns `"abcdefgh.pdf"` | pass |
| AAL-SAN-06 | R2, R6 | happy | — | `sanitize_file_name("Ünïcödé 报告 O'Brien #1 50% A&B (v2)-final_x.pdf")` | returns the input unchanged | pass |
| AAL-SAN-07 | R2 | boundary | — | `sanitize_file_name("My\u00a0Report.pdf")` (inner non-breaking space) | returns `"My\u00a0Report.pdf"` unchanged | pass |
| AAL-SAN-08 | R2 | boundary | — | (a) `sanitize_file_name("a\x1fb c.pdf")`; (b) `sanitize_file_name("a\x7fb~c.pdf")` | (a) returns `"ab c.pdf"` (code 31 removed, code 32 space kept); (b) returns `"ab~c.pdf"` (code 127 removed, code 126 kept — best-practice default, delegated by reviewer) | pass |
| AAL-SAN-09 | R2a [BUG-122] | bug | — | `sanitize_file_name("invoice\u202efdp.txt")` | returns `"invoicefdp.txt"` | xfail BUG-122 — fails today on: result still contains U+202E |
| AAL-SAN-10 | R2a [BUG-122] | bug | — | `sanitize_file_name("\u200breport.pdf")` | returns `"report.pdf"` | xfail BUG-122 — fails today on: result starts with U+200B |
| AAL-SAN-11 | R2a [BUG-122] | bug | — | (a) `sanitize_file_name("rep\x85ort.pdf")` (U+0085 in the middle); (b) `sanitize_file_name("a\x80b\x9fc.pdf")` (both ends of C1 range) | (a) returns `"report.pdf"`; (b) returns `"abc.pdf"` | xfail BUG-122 — fails today on: C1 characters kept |
| AAL-SAN-12 | R2a [BUG-122] | bug | — | `sanitize_file_name("re\u200dp\ufeffo\u00adrt.pdf")` (ZWJ, BOM, soft hyphen) | returns `"report.pdf"` | xfail BUG-122 — fails today on: Cf characters kept |
| AAL-SAN-13 | R2a, R4 [BUG-122] | bug | — | `sanitize_file_name("\u202e\u200b")` | raises `AttachmentValidationError`, `str == "Invalid file name."` | xfail BUG-122 — fails today on: no error raised (returns `"\u202e\u200b"`) |
| AAL-SAN-14 | R2a, R3 (order) [BUG-122] | bug | — | `sanitize_file_name(" \u200b report.pdf")` | returns `"report.pdf"` (Cf removed before trimming, so the space behind it is trimmed too) | xfail BUG-122 — fails today on: result starts with U+200B |
| AAL-SAN-15 | R3 | happy | — | `sanitize_file_name("  report.pdf  ")` | returns `"report.pdf"` | pass |
| AAL-SAN-16 | R3 | happy | — | `sanitize_file_name("..hidden.txt.")` | returns `"hidden.txt"` | pass |
| AAL-SAN-17 | R3 [BUG-120] | bug | — | `sanitize_file_name(". report.pdf")` | returns `"report.pdf"` | xfail BUG-120 — fails today on: returns `" report.pdf"` |
| AAL-SAN-18 | R3 [BUG-120] | bug | — | `sanitize_file_name("report.pdf .")` | returns `"report.pdf"` | xfail BUG-120 — fails today on: returns `"report.pdf "` |
| AAL-SAN-19 | R3 [BUG-120] | bug | — | `sanitize_file_name(" . .report.pdf. . ")` | returns `"report.pdf"` | xfail BUG-120 — fails today on: returns `" .report.pdf. "` |
| AAL-SAN-20 | R4 | error | — | parametrized: `""`, `"   "`, `"..."`, `" . "`, `"???"`, `"\x00\x01"`, `"<>"` | each raises `AttachmentValidationError` (also an instance of `ValueError`), `str == "Invalid file name."` | pass |
| AAL-SAN-21 | R4 | boundary | — | `sanitize_file_name("a")` | returns `"a"` (one character is not empty; no extension needed here) | pass |
| AAL-SAN-22 | R5 | boundary | — | `sanitize_file_name("a" * 251 + ".pdf")` (exactly 255) | returns the input unchanged; `len == 255` | pass |
| AAL-SAN-23 | R5 | boundary | — | `sanitize_file_name("a" * 300)` (no `.`) | returns `"a" * 255` | pass |
| AAL-SAN-24 | R5 (code points) | boundary | — | `sanitize_file_name("é" * 300)` | returns `"é" * 255` (`len == 255` characters; 510 bytes in UTF-8) | pass |
| AAL-SAN-25 | R5 (code points) | boundary | — | `sanitize_file_name("报" * 251 + ".pdf")` (255 characters, > 255 bytes) | returns the input unchanged | pass |
| AAL-SAN-26 | R5a [BUG-121] | bug | — | `sanitize_file_name("t" * 252 + ".pdf")` (256) | returns `"t" * 251 + ".pdf"`; `len == 255` | xfail BUG-121 — fails today on: result ends with `".pd"` |
| AAL-SAN-27 | R5a [BUG-121] | bug | — | `sanitize_file_name("x" * 300 + ".PDF")` | returns `"x" * 251 + ".PDF"` (extension case kept) | xfail BUG-121 — fails today on: returns `"x" * 255` |
| AAL-SAN-28 | R5a [BUG-121] | bug | — | `sanitize_file_name("a" * 300 + ".tar.csv")` | returns `"a" * 251 + ".csv"` | xfail BUG-121 — fails today on: returns `"a" * 255` |
| AAL-SAN-29 | R5, R5a [BUG-121] | bug | — | `sanitize_file_name("b" * 10 + "." + "e" * 253)` (264; extension 253 = largest keepable) | returns `"b" + "." + "e" * 253`; `len == 255` | xfail BUG-121 — fails today on: returns `"b" * 10 + "." + "e" * 244` |
| AAL-SAN-30 | R5 | boundary | — | `sanitize_file_name("b" * 10 + "." + "e" * 254)` (265; extension 254 = no room) | returns `"b" * 10 + "." + "e" * 244` (plain cut to first 255) | pass |
| AAL-SAN-31 | R5b [BUG-121] | bug | — | `sanitize_file_name("a" * 250 + " " * 10 + ".pdf")` (264) | returns `"a" * 250 + ".pdf"`; `len == 254` | xfail BUG-121 — fails today on: returns `"a" * 250 + " " * 5` |
| AAL-SAN-32 | R5b [BUG-121] | bug | — | `sanitize_file_name("a" * 254 + " b" + "c" * 50)` (no `.`) | returns `"a" * 254` (trailing space at cut removed) | xfail BUG-121 — fails today on: returns `"a" * 254 + " "` |
| AAL-SAN-33 | R5b [BUG-121] | bug | — | `sanitize_file_name("a" * 250 + "." * 10 + ".pdf")` (264) | returns `"a" * 250 + ".pdf"`; `len == 254` | xfail BUG-121 — fails today on: returns `"a" * 250 + "....."` |
| AAL-SAN-34 | R6 | happy | — | `sanitize_file_name("My Report.PDF")` | returns `"My Report.PDF"` | pass |
| AAL-SAN-35 | R5, R5a (regression part) | boundary | — | parametrized over the inputs of SAN-26, SAN-27, SAN-28 | each result has `len <= 255` and starts with the first 251 characters of the input | pass |

## `extract_extension`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| AAL-EXT-01 | R1 | happy | — | `extract_extension("evil.exe.pdf")` | returns `"pdf"` | pass |
| AAL-EXT-02 | R1, R4 | error | — | `extract_extension("report.pdf.exe")` | raises `AttachmentValidationError`, `str == "Unsupported file extension: .exe"` | pass |
| AAL-EXT-03 | R2 | error | — | `extract_extension("README")` | raises `AttachmentValidationError`, `str == "File name must include a supported extension."` | pass |
| AAL-EXT-04 | R2 | boundary | — | `extract_extension("report.")` | raises `AttachmentValidationError`, `str == "File name must include a supported extension."` | pass |
| AAL-EXT-05 | R3 | happy | — | (a) `extract_extension("PHOTO.JPG")`; (b) `extract_extension("a.JpEg")` | (a) returns `"jpg"`; (b) returns `"jpeg"` | pass |
| AAL-EXT-06 | R3, R4 | error | — | `extract_extension("archive.ZIP")` | raises `AttachmentValidationError`, `str == "Unsupported file extension: .zip"` | pass |
| AAL-EXT-07 | R4 | error | — | `extract_extension("a. pdf")` | raises `AttachmentValidationError`, `str == "Unsupported file extension: . pdf"` | pass |
| AAL-EXT-08 | R4 (not cleaned) | boundary | — | `extract_extension("photo.png ")` (trailing space) | raises `AttachmentValidationError`, `str == "Unsupported file extension: .png "` | pass |
| AAL-EXT-09 | R5 | boundary | — | `extract_extension(".pdf")` | returns `"pdf"` | pass |
| AAL-EXT-10 | R1, R3 | happy | — | parametrized over the 11 allowed extensions: `extract_extension("file." + ext)` and `extract_extension("file." + ext.upper())` | both return `ext` (lowercase) | pass |
| AAL-EXT-11 | R4 | error | — | parametrized over `zip, bin, doc, xls, docm, xlsm, svg, html, js, exe, gif`: `extract_extension("file." + ext)` | raises `AttachmentValidationError`, `str == "Unsupported file extension: ." + ext` | pass |

## `normalize_upload_request`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| AAL-NUR-01 | R5 | happy | — | `normalize_upload_request(P("photo.png", "image/png"))` | returns: `file_name == "photo.png"`, `mime_type == "image/png"`, `resource_type == "image"`, `extension == "png"`, `spec is EXTENSION_TO_SPEC["png"]` | pass |
| AAL-NUR-02 | R5 | happy | — | `normalize_upload_request(P("report.docx", DOCX))` | `file_name == "report.docx"`, `mime_type == DOCX`, `resource_type == "raw"`, `extension == "docx"`, `spec is EXTENSION_TO_SPEC["docx"]` | pass |
| AAL-NUR-03 | R5 | happy | — | parametrized (ext, mime): jpg/`image/jpeg`, jpeg/`image/jpeg`, png/`image/png`, webp/`image/webp`, heic/`image/heic`, heif/`image/heif`, pdf/`application/pdf`, docx/DOCX, xlsx/XLSX, txt/`text/plain`, csv/`text/csv`, csv/`text/plain`; name `"file." + ext` | each: `file_name == "file." + ext`, `extension == ext`, `mime_type == mime` (unchanged), `resource_type` per table (`image` for jpg…pdf, `raw` for docx/xlsx/txt/csv), `spec is EXTENSION_TO_SPEC[ext]` | pass |
| AAL-NUR-04 | R5 | happy | — | `normalize_upload_request(P("a.jpeg", "image/jpeg"))` | `extension == "jpeg"`; `spec is EXTENSION_TO_SPEC["jpg"]` (shared object) | pass |
| AAL-NUR-05 | R1 | boundary | — | `normalize_upload_request(P("photo.png", "image/png", size=10485760))` | returns a result with `file_name == "photo.png"` (no error) | pass |
| AAL-NUR-06 | R1 | error | — | `normalize_upload_request(P("photo.png", "image/png", size=10485761))` | raises `AttachmentValidationError`, `str == "File too large (10485761 bytes). Maximum is 10485760 bytes."` | pass |
| AAL-NUR-07 | R1 (order) | error | — | `normalize_upload_request(P("???", "application/zip", size=20000000))` | raises `AttachmentValidationError`, `str == "File too large (20000000 bytes). Maximum is 10485760 bytes."` (size error wins over name and MIME errors) | pass |
| AAL-NUR-08 | R2 | happy | — | `normalize_upload_request(P(" ../My Report.PDF ", "application/pdf"))` | `file_name == "-My Report.PDF"`, `extension == "pdf"`, `mime_type == "application/pdf"` | pass |
| AAL-NUR-09 | R2 | error | — | `normalize_upload_request(P("???", "image/png"))` | raises `AttachmentValidationError`, `str == "Invalid file name."` | pass |
| AAL-NUR-10 | R3 | happy | — | `normalize_upload_request(P("  photo.PNG. ", "image/png"))` | `file_name == "photo.PNG"`, `extension == "png"`, `resource_type == "image"` | pass |
| AAL-NUR-11 | R3 | error | — | parametrized: (a) `P("README", "text/plain")`; (b) `P(".pdf", "application/pdf")`; (c) `P("archive.zip", "text/plain")` | (a) and (b) raise `AttachmentValidationError`, `str == "File name must include a supported extension."`; (c) raises `AttachmentValidationError`, `str == "Unsupported file extension: .zip"` (extension error before MIME check) | pass |
| AAL-NUR-12 | R4 | error | — | `P("photo.png", "image/jpeg")` | raises `AttachmentValidationError`, `str == "MIME type 'image/jpeg' does not match .png (expected one of: image/png)."` | pass |
| AAL-NUR-13 | R4 | error | — | `P("data.csv", "application/pdf")` | raises `AttachmentValidationError`, `str == "MIME type 'application/pdf' does not match .csv (expected one of: text/csv, text/plain)."` | pass |
| AAL-NUR-14 | R4, R5 | boundary | — | `P("data.csv", "text/plain")` | returns: `mime_type == "text/plain"`, `extension == "csv"`, `resource_type == "raw"` | pass |
| AAL-NUR-15 | R4 | error | — | `P("notes.txt", "text/csv")` | raises `AttachmentValidationError`, `str == "MIME type 'text/csv' does not match .txt (expected one of: text/plain)."` | pass |
| AAL-NUR-16 | R4 | error | — | `P("photo.png", "application/octet-stream")` | raises `AttachmentValidationError`, `str == "MIME type 'application/octet-stream' does not match .png (expected one of: image/png)."` | pass |
| AAL-NUR-17 | R4, R4a (quote as sent) | error | — | `P("photo.png", "IMAGE/JPEG")` | raises `AttachmentValidationError`, `str == "MIME type 'IMAGE/JPEG' does not match .png (expected one of: image/png)."` | pass |
| AAL-NUR-18 | R4a (inner spaces) | error | — | `P("photo.png", "image / png")` | raises `AttachmentValidationError`, `str == "MIME type 'image / png' does not match .png (expected one of: image/png)."` | pass |
| AAL-NUR-19 | R4, R4a (params, quote as sent) | error | — | `P("notes.txt", "text/html; charset=utf-8")` | raises `AttachmentValidationError`, `str == "MIME type 'text/html; charset=utf-8' does not match .txt (expected one of: text/plain)."` | pass |
| AAL-NUR-20 | R4a, R5a [BUG-123] | bug | — | `P("photo.png", "Image/PNG")` | returns: `mime_type == "image/png"`, `extension == "png"` | xfail BUG-123 — fails today on: raises `AttachmentValidationError` |
| AAL-NUR-21 | R4a, R5a [BUG-123] | bug | — | `P("photo.png", " image/png ")` | returns `mime_type == "image/png"` | xfail BUG-123 — fails today on: raises `AttachmentValidationError` |
| AAL-NUR-22 | R4a, R5a [BUG-123] | bug | — | `P("photo.png", "image/png;")` | returns `mime_type == "image/png"` | xfail BUG-123 — fails today on: raises `AttachmentValidationError` |
| AAL-NUR-23 | R4a, R5a [BUG-123] | bug | — | `P("data.csv", "text/csv; charset=utf-8")` | returns `mime_type == "text/csv"`, `extension == "csv"`, `resource_type == "raw"` | xfail BUG-123 — fails today on: raises `AttachmentValidationError` |
| AAL-NUR-24 | R2 [BUG-121] | bug | — | `P("t" * 252 + ".pdf", "application/pdf")` (256-char name) | returns `file_name == "t" * 251 + ".pdf"`, `extension == "pdf"` | xfail BUG-121 — fails today on: raises `AttachmentValidationError("Unsupported file extension: .pd")` |
| AAL-NUR-25 | R2 [BUG-122] | bug | — | `P("invoice\u202efdp.txt", "text/plain")` | returns `file_name == "invoicefdp.txt"`, `extension == "txt"` | xfail BUG-122 — fails today on: `file_name` still contains U+202E |
| AAL-NUR-26 | Inputs (ignored fields) | happy | — | call with `P("photo.png","image/png")` and with the same but `entity_type=<last member of AttachmentEntityTypeEnum>`, `entity_id=999`, `note="hello"` | both results have identical `file_name`, `mime_type`, `resource_type`, `extension`, and the same `spec` object | pass |
| AAL-NUR-27 | R2a [BUG-125] | bug | — | target `schema`; parametrized: (a) `S("   ", "text/plain")`; (b) `S("\t \n", "text/plain")` (tab, space, newline) | each raises `pydantic.ValidationError`; at least one error in `exc.errors()` has `loc == ("file_name",)` | xfail BUG-125 — fails today on: no `ValidationError` raised (the model builds) |
| AAL-NUR-28 | R2a (non-blank accepted) | boundary | — | target `schema`: build `S(" a.pdf ", "application/pdf")`, then `normalize_upload_request(<that model>)` | building does not raise; `normalize_upload_request` returns `file_name == "a.pdf"`, `extension == "pdf"`, `mime_type == "application/pdf"`, `resource_type == "image"` | pass |
| AAL-NUR-29 | R2a (not covered: cleans to empty), R2 | error | — | target `schema`, parametrized: (a) `S("<>", "text/plain")`; (b) `S("...", "text/plain")`; each built model passed to `normalize_upload_request` | building does not raise; `normalize_upload_request` raises `AttachmentValidationError`, `str == "Invalid file name."` | pass |
| AAL-NUR-30 | R2a (module defence stays), R2 | error | — | `normalize_upload_request(P("   ", "text/plain"))` (bypasses the schema via `model_construct`) | raises `AttachmentValidationError`, `str == "Invalid file name."` | pass |

## `validate_cloudinary_resource`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| AAL-VCR-01 | R1, R5 | happy | — | `validate_cloudinary_resource(file_name="SCAN.PDF", resource={"resource_type": "image", "format": "pdf"})` | returns `None`, no error | pass |
| AAL-VCR-02 | R1 (last extension) | happy | — | (a) `file_name="evil.exe.pdf"`, `{"resource_type": "image", "format": "pdf"}`; (b) `file_name="report.pdf.docx"`, same resource | (a) returns `None`; (b) raises `AttachmentConfirmError`, `str == "Cloudinary resource_type 'image' does not match .docx (expected 'raw')."` | pass |
| AAL-VCR-03 | R1, R5 | happy | — | parametrized over every (ext, allowed format) pair of the table: jpg/jpg, jpg/jpeg, jpeg/jpg, jpeg/jpeg, png/png, webp/webp, heic/heic, heif/heif, pdf/pdf, docx/docx, xlsx/xlsx, txt/txt, csv/csv, csv/txt; `file_name="file." + ext`, `resource={"resource_type": <table value>, "format": fmt}` | each returns `None` | pass |
| AAL-VCR-04 | R4 (format case) | boundary | — | (a) `file_name="report.pdf"`, `{"resource_type": "image", "format": "PDF"}`; (b) `file_name="a.jpeg"`, `{"resource_type": "image", "format": "Jpg"}` | both return `None` | pass |
| AAL-VCR-05 | R4 (cross pairing) | happy | — | (a) `"a.jpeg"` + `image`/`jpg`; (b) `"a.jpg"` + `image`/`jpeg`; (c) `"data.csv"` + `raw`/`txt` | all return `None` | pass |
| AAL-VCR-06 | Inputs (other keys ignored) | happy | — | `file_name="photo.png"`, `resource={"resource_type": "image", "format": "png", "bytes": 999999999, "public_id": "x"}` | returns `None` | pass |
| AAL-VCR-07 | R2 | error | — | `file_name="report.pdf"`, `{"resource_type": "raw", "format": "pdf"}` | raises `AttachmentConfirmError`, `str == "Cloudinary resource_type 'raw' does not match .pdf (expected 'image')."` | pass |
| AAL-VCR-08 | R2 (missing/None/empty) | boundary | — | parametrized `file_name="report.pdf"` with (a) `{"format": "pdf"}`; (b) `{"resource_type": None, "format": "pdf"}`; (c) `{"resource_type": "", "format": "pdf"}` | each raises `AttachmentConfirmError`, `str == "Cloudinary resource_type '' does not match .pdf (expected 'image')."` | pass |
| AAL-VCR-09 | R2 (case-sensitive) | boundary | — | `file_name="report.pdf"`, `{"resource_type": "IMAGE", "format": "pdf"}` | raises `AttachmentConfirmError`, `str == "Cloudinary resource_type 'IMAGE' does not match .pdf (expected 'image')."` | pass |
| AAL-VCR-10 | R2 | error | — | `file_name="notes.txt"`, `{"resource_type": "image", "format": "txt"}` | raises `AttachmentConfirmError`, `str == "Cloudinary resource_type 'image' does not match .txt (expected 'raw')."` | pass |
| AAL-VCR-11 | R2 (checked before format) | error | — | `file_name="report.pdf"`, `{"resource_type": "raw", "format": "docx"}` | raises `AttachmentConfirmError`, `str == "Cloudinary resource_type 'raw' does not match .pdf (expected 'image')."` | pass |
| AAL-VCR-12 | R3 | error | — | `file_name="photo.jpg"`, `{"resource_type": "image", "format": "png"}` | raises `AttachmentConfirmError`, `str == "Cloudinary format 'png' is not allowed for .jpg (expected one of: jpeg, jpg)."` | pass |
| AAL-VCR-13 | R3 (missing/None/empty) | boundary | — | parametrized `file_name="report.pdf"` with (a) `{"resource_type": "image"}`; (b) `{"resource_type": "image", "format": None}`; (c) `{"resource_type": "image", "format": ""}` | each raises `AttachmentConfirmError`, `str == "Cloudinary format '' is not allowed for .pdf (expected one of: pdf)."` | pass |
| AAL-VCR-14 | R3 (lowercased in message) | error | — | `file_name="photo.jpg"`, `{"resource_type": "image", "format": "PNG"}` | raises `AttachmentConfirmError`, `str == "Cloudinary format 'png' is not allowed for .jpg (expected one of: jpeg, jpg)."` | pass |
| AAL-VCR-15 | R3 (sorted list) | error | — | `file_name="data.csv"`, `{"resource_type": "raw", "format": "xlsx"}` | raises `AttachmentConfirmError`, `str == "Cloudinary format 'xlsx' is not allowed for .csv (expected one of: csv, txt)."` | pass |
| AAL-VCR-16 | R3 (converted to string) | boundary | — | `file_name="report.pdf"`, `{"resource_type": "image", "format": 123}` | raises `AttachmentConfirmError`, `str == "Cloudinary format '123' is not allowed for .pdf (expected one of: pdf)."` | pass |
| AAL-VCR-17 | R1a [BUG-124] | bug | — | `file_name="README"`, `resource={}` | raises `AttachmentConfirmError`, `str == "File name must include a supported extension."`; the error is NOT an instance of `AttachmentValidationError` | xfail BUG-124 — fails today on: `AttachmentValidationError` raised instead of `AttachmentConfirmError` |
| AAL-VCR-18 | R1a [BUG-124] | bug | — | `file_name="archive.zip"`, `resource={"resource_type": "raw", "format": "zip"}` | raises `AttachmentConfirmError`, `str == "Unsupported file extension: .zip"`; not an `AttachmentValidationError` | xfail BUG-124 — fails today on: `AttachmentValidationError` raised |
| AAL-VCR-19 | R1a [BUG-124] | bug | — | `file_name="report."`, `resource={}` | raises `AttachmentConfirmError`, `str == "File name must include a supported extension."` | xfail BUG-124 — fails today on: `AttachmentValidationError` raised |
| AAL-VCR-20 | R1, R1a (regression part) | error | — | parametrized with `resource={}` (which would otherwise fail the resource_type check): (a) `"README"`; (b) `"archive.zip"`; (c) `"report."` | each raises a `ValueError` with exact `str`: (a) `"File name must include a supported extension."`; (b) `"Unsupported file extension: .zip"`; (c) `"File name must include a supported extension."` — proves the extension is checked before the resource | pass |

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| Overview: HTTP status mapping (400 at sign/confirm) | sign-upload / confirm-upload endpoints | `AttachmentValidationError` at sign → 400; `AttachmentConfirmError` at confirm → 400 (after BUG-124 fix, a no-longer-allowed extension at confirm is also 400, not 500) |
| Q4 / BUG-124 caller behavior | `AttachmentManager.confirm_upload`, `MobileUploadSessionManager.confirm_staging_upload` | on `AttachmentConfirmError` the attachment is marked FAILED and a ledger row is written (incl. the bad-extension case) |
| `normalize_upload_request` R5a ("callers store this value") | `AttachmentManager.normalize_upload_request` / sign flow, `MobileUploadSessionManager.promote_to_attachment` | the stored `mime_type` is the normalised form (e.g. `Image/PNG` stored as `image/png`) |
| Q1 / BUG-121 caller scenario | `MobileUploadSessionManager._promote_file_name` / `promote_to_attachment` | promoting `scan.pdf` with a 252-character typed title succeeds and the stored name ends in `.pdf` |

## Spec gaps
None. (Previous gap 1 — HR-1 schema check for `AttachmentSignRequest.file_name` — closed by spec G1 → `normalize_upload_request` R2a, BUG-125.)

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| module data | Overview table (keys, entries) | AAL-DATA-01, AAL-DATA-03 |
| module data | jpg/jpeg share one entry | AAL-DATA-02, AAL-NUR-04 |
| module data | `ALLOWED_MIME_TYPES` union (10) | AAL-DATA-04 |
| module data | `MAX_FILE_SIZE_BYTES` | AAL-DATA-05, AAL-NUR-05, AAL-NUR-06 |
| module data | anything else not allowed | AAL-DATA-06, AAL-EXT-11 |
| `AttachmentTypeSpec` | R1 / Errors row "Assigning / deleting" | AAL-TSP-01, AAL-TSP-02, AAL-TSP-03 |
| `AttachmentTypeSpec` | R2 | AAL-TSP-04, AAL-TSP-05 |
| `NormalizedUploadRequest` | R1 / Errors row "Assigning / deleting" | AAL-NRQ-01, AAL-NRQ-02 |
| `NormalizedUploadRequest` | R2 | AAL-NRQ-03 |
| `sanitize_file_name` | R1 | AAL-SAN-01, AAL-SAN-02, AAL-SAN-03 |
| `sanitize_file_name` | R2 | AAL-SAN-04, AAL-SAN-05, AAL-SAN-06, AAL-SAN-07, AAL-SAN-08 |
| `sanitize_file_name` | R2a [BUG-122] | AAL-SAN-09, AAL-SAN-10, AAL-SAN-11, AAL-SAN-12, AAL-SAN-13, AAL-SAN-14 |
| `sanitize_file_name` | R3 [BUG-120] | AAL-SAN-15, AAL-SAN-16 (pass); AAL-SAN-17, AAL-SAN-18, AAL-SAN-19 (xfail); AAL-SAN-02 |
| `sanitize_file_name` | R4 / Errors row "Nothing left after cleaning" | AAL-SAN-20, AAL-SAN-21, AAL-SAN-03, AAL-SAN-13 |
| `sanitize_file_name` | R5 | AAL-SAN-22, AAL-SAN-23, AAL-SAN-24, AAL-SAN-25, AAL-SAN-30, AAL-SAN-35 |
| `sanitize_file_name` | R5a [BUG-121] | AAL-SAN-26, AAL-SAN-27, AAL-SAN-28, AAL-SAN-29 (xfail); AAL-SAN-35 (pass) |
| `sanitize_file_name` | R5b [BUG-121] | AAL-SAN-31, AAL-SAN-32, AAL-SAN-33 |
| `sanitize_file_name` | R6 | AAL-SAN-34, AAL-SAN-06 |
| `extract_extension` | R1 | AAL-EXT-01, AAL-EXT-02, AAL-EXT-10 |
| `extract_extension` | R2 / Errors row "No `.`" | AAL-EXT-03, AAL-EXT-04 |
| `extract_extension` | R3 | AAL-EXT-05, AAL-EXT-06, AAL-EXT-10 |
| `extract_extension` | R4 / Errors row "Extension not allowed" | AAL-EXT-02, AAL-EXT-06, AAL-EXT-07, AAL-EXT-08, AAL-EXT-11 |
| `extract_extension` | R5 | AAL-EXT-09, AAL-NUR-11(b) |
| `normalize_upload_request` | Inputs (ignored fields) | AAL-NUR-26 |
| `normalize_upload_request` | R1 / Errors row "file_size > max" | AAL-NUR-05, AAL-NUR-06, AAL-NUR-07 |
| `normalize_upload_request` | R2 / Errors row "Name empty" | AAL-NUR-08, AAL-NUR-09, AAL-NUR-24 [BUG-121], AAL-NUR-25 [BUG-122] |
| `normalize_upload_request` | R2a [BUG-125] | AAL-NUR-27 (xfail); AAL-NUR-28, AAL-NUR-29, AAL-NUR-30 (pass) |
| `normalize_upload_request` | R3 / Errors row "Missing / unsupported extension" | AAL-NUR-10, AAL-NUR-11 |
| `normalize_upload_request` | R4 / Errors row "MIME not allowed" | AAL-NUR-12, AAL-NUR-13, AAL-NUR-14, AAL-NUR-15, AAL-NUR-16, AAL-NUR-17, AAL-NUR-19 |
| `normalize_upload_request` | R4a [BUG-123] | AAL-NUR-17, AAL-NUR-18, AAL-NUR-19 (pass); AAL-NUR-20, AAL-NUR-21, AAL-NUR-22, AAL-NUR-23 (xfail) |
| `normalize_upload_request` | R5 | AAL-NUR-01, AAL-NUR-02, AAL-NUR-03, AAL-NUR-04, AAL-NUR-14 |
| `normalize_upload_request` | R5a [BUG-123] | AAL-NUR-20, AAL-NUR-21, AAL-NUR-22, AAL-NUR-23 |
| `validate_cloudinary_resource` | R1 | AAL-VCR-01, AAL-VCR-02, AAL-VCR-20 |
| `validate_cloudinary_resource` | R1a [BUG-124] / Errors row "no / unsupported extension" | AAL-VCR-17, AAL-VCR-18, AAL-VCR-19 (xfail); AAL-VCR-20 (pass) |
| `validate_cloudinary_resource` | R2 / Errors row "resource_type mismatch" | AAL-VCR-07, AAL-VCR-08, AAL-VCR-09, AAL-VCR-10, AAL-VCR-11, AAL-VCR-02(b) |
| `validate_cloudinary_resource` | R3 / Errors row "format not allowed" | AAL-VCR-12, AAL-VCR-13, AAL-VCR-14, AAL-VCR-15, AAL-VCR-16 |
| `validate_cloudinary_resource` | R4 | AAL-VCR-04, AAL-VCR-05 |
| `validate_cloudinary_resource` | R5 | AAL-VCR-01, AAL-VCR-03, AAL-VCR-04, AAL-VCR-05, AAL-VCR-06 |
| — | BUG-120 | AAL-SAN-17, AAL-SAN-18, AAL-SAN-19 |
| — | BUG-121 | AAL-SAN-26…29, AAL-SAN-31…33, AAL-NUR-24 |
| — | BUG-122 | AAL-SAN-09…14, AAL-NUR-25 |
| — | BUG-123 | AAL-NUR-20…23 |
| — | BUG-124 | AAL-VCR-17…19 |
| — | BUG-125 | AAL-NUR-27 |
| — | Branch map line 132–133 `not ext` / `'(none)'` | unreachable per spec — no case |
