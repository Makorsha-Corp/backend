# Spec — `app/utils/attachment_allowlist.py`

> **Status:** APPROVED
> **Source commit:** `e48a092`

## Review
> Reviewer: answer each question on its **Answer:** line with one of
> `intended` · `bug` · `bug — <what it should do instead>` · `remove` (unreachable
> code only) · or a question back.
> Then run the describer in `apply-review` mode.

### House-rule violations — applied automatically
- **HR-1** `sanitize_file_name` R3 — whitespace and dots are trimmed only once each, so a name wrapped in dots and spaces (`". report.pdf"`) is stored as `" report.pdf"` with a leading space. Intended: the stored file name never starts or ends with whitespace (or a dot); trimming repeats until stable.
**Answer:** bug — per HR-1 (house rule) — 🐞 BUG-120
**Resolution:** leading/trailing whitespace and dots are removed repeatedly until none remain. Rules: `sanitize_file_name` R3.
- **HR-1** `normalize_upload_request` R2a — the sign-upload request schema (`AttachmentSignRequest.file_name`, `min_length=1`) accepts a whitespace-only name such as `"   "`; it reaches this module and fails later as 400 "Invalid file name.". Intended: blank / whitespace-only `file_name` is rejected by the Pydantic schema (422) at every entry point. (Added in fill-gaps, gap G1.)
**Answer:** bug — per HR-1 (house rule) — 🐞 BUG-125
**Resolution:** `AttachmentSignRequest` rejects a `file_name` that is empty after removing surrounding whitespace, with a Pydantic `ValidationError` (fix belongs in `app/schemas/attachment.py`, precedent pattern of BUG-004). This module's own 400 "Invalid file name." stays as defence for callers that bypass the schema (best-practice default, delegated by reviewer). Rules: `normalize_upload_request` R2a.

### New questions

### Q1. Long file names lose their extension when cut to 255 characters — 🐞 BUG-121
**Background:** After cleaning, a file name is cut to its first 255 characters. The sign-upload request already limits `file_name` to 255, but the mobile-upload "promote" step builds a new name as `<name the user typed>.<original extension>`, where the typed name may itself be up to 255 characters, and then runs it through this cleaner.
**What happens today:** When the cleaned name is longer than 255 characters, the end of the name is cut off, including the extension.
**Example:** A user promotes a phone-uploaded `scan.pdf` and types a 252-character title. The name becomes 256 characters, the cut leaves it ending in `…title.pd`, and the promote fails with "Unsupported file extension: .pd", so the user cannot save the file under that title.
**Rules affected:** `sanitize_file_name` R5
**Answer:** bug — shorten the part before the extension so the result is at most 255 characters and still ends with the original .<extension> (reviewer accepted suggestion)
**Suggested answer:** bug — when the name is too long, shorten the part before the extension so the result is at most 255 characters and still ends with the original `.<extension>`
**Resolution:** an over-long name keeps its extension; only the part before it is shortened. Follow-up details decided by best practice (best-practice default, delegated by reviewer): (a) "extension" = the text after the last `.` of the cleaned name; (b) if there is no `.`, or the extension is 254+ characters (no room for any name part), the whole name is simply cut to 255 characters; (c) after any cut, whitespace and dots left at the cut are removed (HR-1 holds for the final result), so the result may be shorter than 255; (d) lengths are counted in characters (Unicode code points), not bytes. Rules: `sanitize_file_name` R5, R5a, R5b.

### Q2. Invisible Unicode control characters stay in file names — 🐞 BUG-122
**Background:** The cleaner removes ASCII control characters (codes 0–31 and 127) and the characters `< > : " | ? *`. It does not remove Unicode formatting characters such as the right-to-left override (U+202E), zero-width characters, or the C1 control range (U+0080–U+009F).
**What happens today:** Those characters are kept in the stored file name, and one of them can make the name look different from what it is when displayed.
**Example:** An uploader names a file `invoice‮fdp.txt`. The server accepts it as a `.txt` file, but other users see it listed as `invoicetxt.pdf` and may open it expecting a PDF from a trusted source.
**Rules affected:** `sanitize_file_name` R2
**Answer:** bug — also remove Unicode control and format characters (categories Cc and Cf, including bidi overrides and zero-width characters) from file names (reviewer accepted suggestion)
**Suggested answer:** bug — also remove Unicode control and format characters (categories Cc and Cf, which include bidi overrides and zero-width characters) from file names
**Resolution:** every character of Unicode general category `Cc` or `Cf` is removed, in the same step as the other unsafe characters (before trimming and the empty check). Category is taken from Python's `unicodedata` (best-practice default, delegated by reviewer). Rules: `sanitize_file_name` R2, R2a.

### Q3. MIME type comparison is case-sensitive and rejects parameters — 🐞 BUG-123
**Background:** At sign time the client sends the file's MIME type, which must be one of the types allowed for the file's extension. By the MIME standard, type names are case-insensitive, and a type can carry parameters (for example `text/csv; charset=utf-8`).
**What happens today:** The MIME type must match the allowlist exactly, character for character. `IMAGE/PNG` or `text/csv; charset=utf-8` is rejected, and the stored MIME type is kept exactly as the client sent it.
**Example:** A client sends `photo.png` with MIME type `Image/PNG`. The user gets 400 "MIME type 'Image/PNG' does not match .png (expected one of: image/png)." although the file is a normal PNG.
**Rules affected:** `normalize_upload_request` R4, R5
**Answer:** bug — trim and lowercase the MIME type and ignore ';' parameters before comparing, and return/store the normalised form (reviewer accepted suggestion)
**Suggested answer:** bug — trim and lowercase the MIME type and ignore any `;` parameters before comparing, and return/store the normalised form
**Resolution:** the MIME type is normalised (text before the first `;`, trimmed, lowercased) before the allowlist check, and the normalised value is returned. Follow-up details decided by best practice (best-practice default, delegated by reviewer): (a) the error message quotes the MIME type **as the client sent it** (so the user recognises their own input); (b) nothing else is normalised — inner spaces such as `image / png` are still rejected. Rules: `normalize_upload_request` R4, R4a, R5, R5a.

### Q4. Confirm step raises a "validation" error, not a "confirm" error, for a stored name with no allowed extension — 🐞 BUG-124
**Background:** `validate_cloudinary_resource` runs at confirm time on the file name saved at sign time. The confirm code in the attachment manager catches only the "confirm" error type: on that error it marks the attachment FAILED, writes a ledger row, and the endpoint answers 400. A stored name can stop having an allowed extension if the allowlist is changed while uploads are still pending.
**What happens today:** If the stored name has no extension or an extension that is no longer allowed, the function raises `AttachmentValidationError` (the sign-time error type). The confirm code does not catch it, so the attachment stays pending with no ledger row, and the confirm endpoint returns a generic 500 "Failed to confirm upload."
**Example:** `.heic` is removed from the allowlist while `IMG_1.heic` is pending. When the browser confirms, the user gets a 500 error, and the attachment row stays in `pending` instead of `failed`.
**Rules affected:** `validate_cloudinary_resource` R1
**Answer:** bug — every failure in validate_cloudinary_resource, including an invalid or no-longer-allowed extension, raises AttachmentConfirmError (reviewer accepted suggestion)
**Suggested answer:** bug — every failure in `validate_cloudinary_resource`, including an invalid or no-longer-allowed extension, raises `AttachmentConfirmError`
**Resolution:** a missing or no-longer-allowed extension at confirm time raises `AttachmentConfirmError`, with the same detail message `extract_extension` uses (best-practice default, delegated by reviewer — keeps the message stable for users and logs). `extract_extension` itself still raises `AttachmentValidationError`. Rules: `validate_cloudinary_resource` R1, R1a.

## Overview
The authoritative allowlist of file types users may attach (Cloudinary direct upload; no file bytes pass through the server). It cleans user-supplied file names, maps the file extension to an allowed type, checks the declared size and MIME type at **sign** time, and at **confirm** time checks that what Cloudinary actually stored matches the type implied by the file name. Callers: `AttachmentManager.normalize_upload_request` / `confirm_upload` (via `AttachmentService`), and `MobileUploadSessionManager` (`confirm_staging_upload`, `_promote_file_name`, `promote_to_attachment`). The invariant it protects: only the listed types are accepted, and the extension, the declared MIME type and Cloudinary's detected format/resource type all agree.

**Allowlist (module data — part of the contract):**

| Extension(s) | Allowed MIME types (sign) | `resource_type` | Allowed Cloudinary formats (confirm) |
|---|---|---|---|
| `jpg`, `jpeg` | `image/jpeg` | `image` | `jpg`, `jpeg` |
| `png` | `image/png` | `image` | `png` |
| `webp` | `image/webp` | `image` | `webp` |
| `heic` | `image/heic` | `image` | `heic` |
| `heif` | `image/heif` | `image` | `heif` |
| `pdf` | `application/pdf` | `image` | `pdf` |
| `docx` | `application/vnd.openxmlformats-officedocument.wordprocessingml.document` | `raw` | `docx` |
| `xlsx` | `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` | `raw` | `xlsx` |
| `txt` | `text/plain` | `raw` | `txt` |
| `csv` | `text/csv`, `text/plain` | `raw` | `csv`, `txt` |

- `jpg` and `jpeg` share one type entry (same object in `EXTENSION_TO_SPEC`).
- `EXTENSION_TO_SPEC` has exactly the 11 keys above (lowercase). `ALLOWED_MIME_TYPES` is the union of all MIME types (10 distinct values; `text/plain` appears once).
- `MAX_FILE_SIZE_BYTES` = 10 × 1024 × 1024 = **10 485 760**.
- Anything else (e.g. `zip`, `bin`, `doc`, `xls`, `docm`, `xlsm`, `svg`, `html`, `js`, `exe`, `gif`) is not allowed.

**Callables:** 6 specified · 2 not specified
**Externals to mock:** none (pure module; no DB, no Cloudinary calls — `validate_cloudinary_resource` takes a plain dict)
**Integration-only behavior:** none. HTTP status mapping of these errors (400 at sign/confirm, the 500 in Q4) lives in the endpoints.

**Notes for the test designer:**
- Pure functions; call them directly. No DB session needed.
- `normalize_upload_request` takes an `AttachmentSignRequest` (`app/schemas/attachment.py`): `entity_type` (enum `AttachmentEntityTypeEnum`), `entity_id` ≥ 1, `file_name` 1–255 chars, `mime_type` 1–128 chars, `file_size` ≥ 1, `note` optional. Values outside those limits are rejected when the model is built. To reach this function with such values (e.g. a 300-character name), use `AttachmentSignRequest.model_construct(...)`.
- Error messages use Python `repr` for quoted values (single quotes, e.g. `'image/png'`).

## Not specified
- `AttachmentValidationError` — `ValueError` subclass, no logic (sign-time / input errors)
- `AttachmentConfirmError` — `ValueError` subclass, no logic (confirm-time errors)

---

## `AttachmentTypeSpec` (dataclass)
**Shape:** helper (value object)
**Persistence:** pure
**Visibility:** public (the entries of `ATTACHMENT_TYPE_SPECS` / `EXTENSION_TO_SPEC`, shared by every upload in the process)

**Purpose:** One allowlist entry: the extensions, sign-time MIME types, Cloudinary `resource_type` and confirm-time formats of one file type. Contents are in the Overview table.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `extensions` | `frozenset[str]` | lowercase extensions, no dot |
| `mime_types` | `frozenset[str]` | allowed MIME types at sign |
| `resource_type` | `str` | `image` or `raw` |
| `confirm_formats` | `frozenset[str]` | allowed Cloudinary formats at confirm |

**Returns:** an instance with those four fields (positional or keyword construction).

**Rules:**
- **R1.** Instances are immutable: assigning any field (e.g. `EXTENSION_TO_SPEC["pdf"].resource_type = "raw"`) or setting a new attribute raises `dataclasses.FrozenInstanceError`, and the field keeps its old value (best-practice default, delegated by reviewer — shared allowlist entries must not be changeable by one caller for the whole process).
- **R2.** Instances are hashable (`hash(spec)` works; an entry can be put in a `set` or used as a `dict` key), and two instances built with equal field values are equal (`==`) and have the same hash. Follows from R1 (frozen dataclass with default equality).

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| Assigning / deleting an attribute | `dataclasses.FrozenInstanceError` | not specified (Python's own text) |

**Side effects:** none

---

## `NormalizedUploadRequest` (dataclass)
**Shape:** helper (value object)
**Persistence:** pure
**Visibility:** public (returned by `normalize_upload_request`)

**Purpose:** The checked result of a sign-upload request. Field values are described under `normalize_upload_request` R5, R5a.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `file_name` | `str` | none enforced by the class |
| `mime_type` | `str` | none enforced by the class |
| `resource_type` | `str` | none enforced by the class |
| `extension` | `str` | none enforced by the class |
| `spec` | `AttachmentTypeSpec` | none enforced by the class |

**Returns:** an instance with those five fields.

**Rules:**
- **R1.** Instances are immutable: assigning any field of a result (e.g. `result.file_name = "x.exe"` or `result.mime_type = "text/html"`) or setting a new attribute raises `dataclasses.FrozenInstanceError`, and the field keeps its old value (best-practice default, delegated by reviewer — a validated result must not be alterable after validation).
- **R2.** Instances are hashable, and two results with equal field values are equal (`==`) with the same hash (e.g. two `normalize_upload_request` calls on the same valid payload give equal results).

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| Assigning / deleting an attribute | `dataclasses.FrozenInstanceError` | not specified (Python's own text) |

**Side effects:** none

---

## `sanitize_file_name(file_name)`
**Shape:** validator / mapper
**Persistence:** pure
**Visibility:** public (used by: `normalize_upload_request`, `MobileUploadSessionManager._promote_file_name`)

**Purpose:** Turn a user-supplied file name into a safe display/storage name, or reject it as empty.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `file_name` | `str` | Any string; no length limit enforced here |

**Returns:** the cleaned name (`str`), at most 255 characters, never starting or ending with whitespace or `.`.

**Rules:**
- **R1.** Every `/` and every `\` is replaced by `-`. `"a/b\\c.pdf"` → `"a-b-c.pdf"`; `"../x.pdf"` → `"..-x.pdf"` after this step (then R3 applies).
- **R2.** ASCII control characters (codes 0–31 and 127) and the characters `<` `>` `:` `"` `|` `?` `*` are removed. Letters in any script, inner spaces (including non-breaking space U+00A0), case, `'`, `#`, `%`, `&`, `(`, `)`, `-`, `_` are kept.
- **R2a.** [BUG-122] Every character of Unicode general category `Cc` (control, incl. the C1 range U+0080–U+009F such as U+0085) or `Cf` (format, e.g. U+202E right-to-left override, U+200B zero-width space, U+200D zero-width joiner, U+FEFF, U+00AD soft hyphen) is also removed, in the same step as R2 — i.e. before R3 and R4. `"invoice\u202efdp.txt"` → `"invoicefdp.txt"`; `"\u200breport.pdf"` → `"report.pdf"`; `"\u202e\u200b"` → rejected per R4. *(Today: these characters are kept.)*
- **R3.** [BUG-120] (HR-1) After R1–R2, the result never starts or ends with whitespace or `.`: leading/trailing whitespace and dots are removed repeatedly until none remain. `"  report.pdf  "` → `"report.pdf"`; `"..hidden.txt."` → `"hidden.txt"`; `". report.pdf"` → `"report.pdf"`. *(Today: whitespace is trimmed once, then dots once, so `". report.pdf"` → `" report.pdf"` and `"report.pdf ."` → `"report.pdf "`.)* Names already clean after one pass (`"  report.pdf  "`, `"..hidden.txt."`) give the same result today.
- **R4.** If the result is empty, `AttachmentValidationError("Invalid file name.")` is raised. Examples that are rejected: `""`, `"   "`, `"..."`, `" . "`, `"???"`, `"\x00\x01"`, `"<>"`. Note: `"///"` is **not** empty (it becomes `"---"`) and is returned.
- **R5.** A result of at most 255 characters (after R1–R4) is returned unchanged; exactly 255 characters is returned unchanged. A result longer than 255 characters with **no** `.` is cut to its first 255 characters (`"a" * 300` → `"a" * 255`). The same plain cut applies when the text after the last `.` is 254 characters or longer (no room for any name part). Lengths are in characters (code points), not bytes.
- **R5a.** [BUG-121] A result longer than 255 characters that has a `.` with an extension of at most 253 characters keeps its extension: the part before the last `.` is shortened to `255 − len("." + extension)` characters and the `.` + extension (as typed, case kept) is appended. Example: a 252-character title + `".pdf"` (256 chars) → the first 251 characters of the title + `".pdf"` (255 chars); `"x" * 300 + ".PDF"` → `"x" * 251 + ".PDF"`. Only the last extension is kept: `"a" * 300 + ".tar.csv"` → first 251 characters (all `a`) + `".csv"`. *(Today: the whole name is cut to 255, e.g. `…title.pd`, so the extension is lost.)*
- **R5b.** [BUG-121] After any cut (R5 or R5a), whitespace and dots left at the cut point are removed (HR-1), so the result can be shorter than 255 and never has whitespace or `.` right before the kept `.extension` or at the end. Examples: `"a" * 250 + " " * 10 + ".pdf"` → `"a" * 250 + ".pdf"` (254 chars); `"a" * 254 + " b" + "c" * 50` (no `.`) → `"a" * 254` (the cut leaves a trailing space, which is removed). The name part can never become empty (R3 guarantees it starts with a non-space, non-dot character). *(Today: the cut is not re-trimmed.)*
- **R6.** Inner whitespace and letter case are kept as typed: `"My Report.PDF"` → `"My Report.PDF"`.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| Nothing left after cleaning (R1–R3, incl. R2a) | `AttachmentValidationError` | `Invalid file name.` |

**Side effects:** none

---

## `extract_extension(file_name)`
**Shape:** validator
**Persistence:** pure
**Visibility:** public (used by: `normalize_upload_request`, `validate_cloudinary_resource`)

**Purpose:** Get the lowercase extension of a file name and require that it is allowed.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `file_name` | `str` | Used as given; not cleaned here |

**Returns:** the extension in lowercase, without the dot (one of the 11 keys in the Overview table).

**Rules:**
- **R1.** The extension is the text after the **last** `.`. Only the last extension counts: `"evil.exe.pdf"` → `"pdf"` (accepted); `"report.pdf.exe"` → rejected (R4).
- **R2.** A name with no `.` (`"README"`), or ending with `.` (`"report."`), raises `AttachmentValidationError("File name must include a supported extension.")`.
- **R3.** The extension is lowercased before the check and in the return value: `"PHOTO.JPG"` → `"jpg"`; `"a.JpEg"` → `"jpeg"`.
- **R4.** An extension not in the allowlist raises `AttachmentValidationError("Unsupported file extension: .<ext>")`, with `<ext>` lowercased and otherwise as it appears (spaces included): `"archive.ZIP"` → `Unsupported file extension: .zip`; `"a. pdf"` → `Unsupported file extension: . pdf`.
- **R5.** A name that is only a dot plus an allowed extension is accepted when called directly: `".pdf"` → `"pdf"`. (Through `normalize_upload_request` the leading dot is removed first, so `".pdf"` there becomes `"pdf"` and fails R2.)

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| No `.`, or nothing after the last `.` | `AttachmentValidationError` | `File name must include a supported extension.` |
| Extension not allowed | `AttachmentValidationError` | `Unsupported file extension: .<ext lowercased>` |

**Side effects:** none

---

## `normalize_upload_request(payload)`
**Shape:** validator / mapper
**Persistence:** pure
**Visibility:** public (used by: `AttachmentManager.normalize_upload_request` → sign upload; `MobileUploadSessionManager.promote_to_attachment`)

**Purpose:** Check a sign-upload request against the size limit and the type allowlist, and return the cleaned name with its type details.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `payload` | `AttachmentSignRequest` | Only `file_size`, `file_name`, `mime_type` are used; `entity_type`, `entity_id`, `note` are ignored |

**Returns:** `NormalizedUploadRequest(file_name=<cleaned name>, mime_type=<normalised MIME type, R4a>, resource_type=<type's resource_type>, extension=<lowercase ext>, spec=<the type entry>)`.

**Rules:**
- **R1.** `file_size` greater than 10 485 760 raises `AttachmentValidationError("File too large (<file_size> bytes). Maximum is 10485760 bytes.")`. Exactly 10 485 760 is accepted. The size is checked first: an oversized request with a bad name or MIME type gets the size error.
- **R2.** The file name is cleaned per `sanitize_file_name` R1–R6 (incl. R2a, R5a, R5b); its error is raised unchanged. So an over-long name keeps its extension and passes the extension check (Q1 scenario).
- **R2a.** [BUG-125] A sign request whose `file_name` is whitespace-only (e.g. `"   "`, `"\t \n"` (tab, space, newline)) cannot be built: constructing `AttachmentSignRequest(...)` with it raises Pydantic `ValidationError` (422 at the API) on the `file_name` field, so `normalize_upload_request` is never reached. A name with at least one non-whitespace character (e.g. `" a.pdf "`) is still accepted by the schema (trimming is `sanitize_file_name`'s job). Names that are non-blank but become empty only after removing unsafe characters or dots (e.g. `"<>"`, `"..."`) are **not** covered: they still pass the schema and get the R2 400 "Invalid file name." (best-practice default, delegated by reviewer — HR-1 covers blank/whitespace-only input only). *(Today: the schema only requires length ≥ 1, so `"   "` is accepted and fails later in `sanitize_file_name` R4 with `AttachmentValidationError("Invalid file name.")`. Fix belongs in `app/schemas/attachment.py`.)*
- **R3.** The extension is taken from the **cleaned** name per `extract_extension` R1–R5; its errors are raised unchanged. So `"  photo.PNG. "` is treated as `png`.
- **R4.** The MIME type must be one of the allowed MIME types for that extension (Overview table), compared exactly. Otherwise `AttachmentValidationError("MIME type <repr of mime_type> does not match .<ext> (expected one of: <allowed types sorted alphabetically, joined by ', '>).")`. Examples: `photo.png` + `image/jpeg` → `MIME type 'image/jpeg' does not match .png (expected one of: image/png).`; `data.csv` + `application/pdf` → `… (expected one of: text/csv, text/plain).`; `data.csv` + `text/plain` → accepted; `notes.txt` + `text/csv` → rejected; `photo.png` + `application/octet-stream` → rejected.
- **R4a.** [BUG-123] Before the check, the MIME type is normalised: only the text before the first `;` is used, surrounding whitespace is removed, and it is lowercased. `Image/PNG`, `" image/png "`, `image/png;` and `text/csv; charset=utf-8` (for `.csv`) are accepted. A value that normalises to something not allowed is rejected with the R4 message, which quotes the MIME type **as sent** (e.g. `MIME type 'IMAGE/JPEG' does not match .png (expected one of: image/png).`). Inner spaces are not fixed: `image / png` is rejected. *(Today: exact, case-sensitive match; `IMAGE/PNG` and parameters are rejected.)*
- **R5.** On success the result has the cleaned `file_name`, the lowercase `extension`, and the matching type's `resource_type` (`image` for jpg/jpeg/png/webp/heic/heif/pdf, `raw` for docx/xlsx/txt/csv) and `spec` (the same object as `EXTENSION_TO_SPEC[extension]`). A MIME type sent already in normalised form (e.g. `image/png`) is returned unchanged.
- **R5a.** [BUG-123] The returned `mime_type` is the normalised form from R4a: `Image/PNG` → `image/png`; `text/csv; charset=utf-8` → `text/csv`. Callers store this value. *(Today: returned exactly as sent.)*

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| `file_size` > 10 485 760 | `AttachmentValidationError` | `File too large (<n> bytes). Maximum is 10485760 bytes.` |
| Name empty after cleaning | `AttachmentValidationError` | see `sanitize_file_name` |
| Missing / unsupported extension | `AttachmentValidationError` | see `extract_extension` |
| MIME type (after R4a normalisation) not allowed for the extension | `AttachmentValidationError` | `MIME type '<m as sent>' does not match .<ext> (expected one of: <sorted list>).` |

**Side effects:** none

---

## `validate_cloudinary_resource(*, file_name, resource)`
**Shape:** validator
**Persistence:** pure
**Visibility:** public (used by: `AttachmentManager.confirm_upload`, `MobileUploadSessionManager.confirm_staging_upload`)

**Purpose:** At confirm time, check that the asset Cloudinary stored has the resource type and format expected for the file's extension.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `file_name` | `str` (keyword-only) | The stored file name; not cleaned again |
| `resource` | `dict` (keyword-only) | Cloudinary Admin API resource; only `resource_type` and `format` are read. Other keys (e.g. `bytes`) are not checked here |

**Returns:** `None` when the resource matches.

**Rules:**
- **R1.** The expected type comes from `file_name`'s extension per `extract_extension` R1–R5 (last extension, case-insensitive): `"SCAN.PDF"` expects type `pdf`.
- **R1a.** [BUG-124] A `file_name` with no extension, or with an extension that is not (or no longer) allowed, raises **`AttachmentConfirmError`** (not `AttachmentValidationError`) with the same detail message as `extract_extension`: `File name must include a supported extension.` or `Unsupported file extension: .<ext>`. This is checked before the resource is looked at. *(Today: `AttachmentValidationError` is raised, which the confirm callers do not catch → attachment stays pending, endpoint answers 500.)*
- **R2.** `resource["resource_type"]` must equal the type's `resource_type` exactly (case-sensitive). A missing key, `None` or `""` counts as `''`. Otherwise `AttachmentConfirmError("Cloudinary resource_type <repr> does not match .<ext> (expected <repr of expected>).")`, e.g. `Cloudinary resource_type 'raw' does not match .pdf (expected 'image').`. This is checked before the format: a resource where both are wrong gets the resource_type error.
- **R3.** `resource["format"]` is converted to a string and lowercased, then must be one of the type's allowed Cloudinary formats. A missing key, `None` or `""` counts as `''` and is rejected. Otherwise `AttachmentConfirmError("Cloudinary format <repr of lowercased format> is not allowed for .<ext> (expected one of: <allowed formats sorted, joined by ', '>).")`, e.g. `Cloudinary format 'png' is not allowed for .jpg (expected one of: jpeg, jpg).`
- **R4.** Format matching ignores case (`"PDF"` is accepted for `.pdf`); the extension/format pairing does not have to be identical within a type: a `.jpeg` file with format `jpg` and a `.csv` file with format `txt` are accepted.
- **R5.** When resource_type and format both match, nothing is raised and nothing is returned.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| `file_name` has no / unsupported extension | `AttachmentConfirmError` [BUG-124] | same message as `extract_extension` |
| resource_type mismatch | `AttachmentConfirmError` | `Cloudinary resource_type '<got>' does not match .<ext> (expected '<want>').` |
| format not allowed | `AttachmentConfirmError` | `Cloudinary format '<got>' is not allowed for .<ext> (expected one of: <sorted list>).` |

**Side effects:** none

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 28 | `@dataclass(frozen=True)` on `AttachmentTypeSpec` | `AttachmentTypeSpec` R1, R2 |
| 100–102 | build extension map (jpg/jpeg share one type) | Overview table |
| 104–106 | build MIME union | Overview table |
| 109 | `@dataclass(frozen=True)` on `NormalizedUploadRequest` | `NormalizedUploadRequest` R1, R2 |
| 119 | `/` and `\` replaced | `sanitize_file_name` R1 |
| 120 | unsafe-character regex removes chars / keeps others | `sanitize_file_name` R2, R2a (Cc/Cf removal — new after fix) |
| 121 | strip whitespace, then dots (repeat until stable after fix) | `sanitize_file_name` R3 |
| 122–123 | empty after cleaning → error / non-empty continues | `sanitize_file_name` R4 |
| 124 | length ≤ 255 kept / > 255 cut; after fix: keepable extension → shorten name part, else plain cut; re-trim at cut | `sanitize_file_name` R5, R5a, R5b |
| 129 | no `.` (`len(parts) < 2`) | `extract_extension` R2 |
| 129 | nothing after last `.` (`not parts[1]`) | `extract_extension` R2 |
| 131 | lowercase | `extract_extension` R3 |
| 132 | `not ext` — unreachable (non-empty already guaranteed by line 129); the `'(none)'` fallback on line 133 is also unreachable | — (unreachable) |
| 132–133 | extension not in allowlist → error | `extract_extension` R4 |
| 134 | allowed → return | `extract_extension` R1, R3, R5 |
| 138–141 | size > max → error; = max passes | `normalize_upload_request` R1 |
| 143 | sanitize may raise | `normalize_upload_request` R2 |
| schema `AttachmentSignRequest.file_name` (`app/schemas/attachment.py:13`) | whitespace-only name rejected at build (after fix) | `normalize_upload_request` R2a |
| 144 | extract may raise | `normalize_upload_request` R3 |
| 147–151 | MIME (normalised after fix) not in type's set → error | `normalize_upload_request` R4, R4a |
| 153–159 | success result (normalised MIME after fix) | `normalize_upload_request` R5, R5a |
| 168 | extract may raise (confirm error type after fix) | `validate_cloudinary_resource` R1, R1a |
| 171 | `format` falsy → `''`; lowercased | `validate_cloudinary_resource` R3, R4 |
| 172 | `resource_type` falsy → `''` | `validate_cloudinary_resource` R2 |
| 174–178 | resource_type mismatch → error | `validate_cloudinary_resource` R2 |
| 180–184 | format not allowed → error | `validate_cloudinary_resource` R3 |
| 184 (fall-through) | both match → return `None` | `validate_cloudinary_resource` R5 |

## Gap log
- G1 (attachment_allowlist.cases.md gap 1) — house rule not applied — HR-1's "blank / whitespace-only names rejected by the Pydantic schema (422)" was not applied to `AttachmentSignRequest.file_name`. Added HR-1 violation line (pre-answered, 🐞 BUG-125, pattern `blank-name-accepted` as BUG-004), new rule `normalize_upload_request` R2a (schema-level `ValidationError` for whitespace-only names; unsafe-only/dot-only names still get the 400), Branch-map row. Kept here rather than deferred to a separate schema spec because no schema-layer spec exists and this spec already documents the payload's constraints (best-practice default, delegated by reviewer).
- G2 (attachment_allowlist.verify.md finding 1, mutant #31) — fact — `AttachmentTypeSpec` is `frozen=True` (source L28) but the spec only listed it as "Not specified", so immutability was untested. Moved it to a specified section with R1 (assignment raises `FrozenInstanceError`, best-practice default, delegated by reviewer) and R2 (hashable, value equality); Branch-map row for L28; Callables count now 6 · 2. Holds today — no bug.
- G3 (attachment_allowlist.verify.md finding 2, mutant #42) — fact — same for `NormalizedUploadRequest` (source L109): new section with R1 (immutable result, best-practice default, delegated by reviewer) and R2 (hashable, value equality); Branch-map row for L109. Holds today — no bug.
- G4 (attachment_allowlist.verify.md finding 4) — formatting — `normalize_upload_request` R2a contained a literal TAB and NEWLINE in its example; replaced with the escapes `"\t \n"` so the rule stays on one line.
