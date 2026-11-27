# Test cases — `app/core/cloudinary_client.py`

> **Spec:** `tests/unit/core/cloudinary_client.spec.md` (source commit e48a092)
> **Status:** READY
> **Revision:** 3 — re-run on the unchanged spec (APPROVED, commit e48a092, Gap log G1 already applied). verify.md (cases revision 2) is PASS: no findings, and its one surviving mutant (#34, `"secure"` key in URL options) is marked equivalent with Fix by "—", so nothing is routed to the case designer. No cases were added, changed or retired.
> **Revision (previous):** 2 — spec gap G1 / verify finding 1 (DISCREPANCY-1): R2 no longer lists `version` as a signature input, new R2a says version is not signed, and R2 now gives known signature values. Verify finding 2 addressed: CLD-URL-12 sub-case (a) (version changes signature) removed; (b)–(d) now assert the exact known signatures, plus new sub-case (e) transformation → `s--6_QbkIb2--`. New case CLD-URL-15 covers R2a (v123 and v124 share `s--5pmR91cm--`). CLD-URL-11 now uses secret `t` and asserts the known `s--IoFgbQBd--`. Verify finding 3 (remove the xfail marker) belongs to the executor.
> **Counts:** 52 cases · 52 expected-to-pass · 0 expected-to-fail (bugs) · 1 deferred

## Reviewer summary
- **Per callable:** `_ensure_configured` 7 · `generate_upload_signature` 10 · `build_signed_delivery_url` 15 · `get_resource` 5 · `destroy_resource` 5 · `rename_resource` 4 · `update_resource_metadata` 6 (no bug cases; the spec has no BUG tags).
- **Notable design choices:**
  - No database. The module is pure or calls Cloudinary, so these tests use no session. That is the one departure from the usual Postgres setup (the spec's Overview says so).
  - The four Cloudinary SDK calls are replaced with recording fakes. Arguments are checked by binding each recorded call to the real SDK function's signature, so it doesn't matter whether the module passes them by position or by keyword. *(best-practice default, delegated by reviewer)*
  - The SDK's global config is saved before each test, set to known "prev-…" values, and put back afterwards. This makes "config overwritten" and "config left unchanged" observable. *(best-practice default, delegated by reviewer)*
  - Upload signatures are checked against an independent SHA-1 recipe built with `hashlib`, plus the spec's literal example. Delivery-URL signatures are checked against the spec's known values (`s--5pmR91cm--` and the R2 list for public id, fmt, flags, transformation, secret). Only where the spec gives no value (URL-05 cloud `acme-co`, URL-09 transformation+flags together) are they checked by shape (`s--` + 8 chars + `--`) and by differing from `s--5pmR91cm--`.
  - Version is not signed (R2a): CLD-URL-15 asserts the SAME signature for v123 and v124. This follows the spec's correction (best-practice default, delegated by reviewer — standard Cloudinary behavior), not a bug.
  - `_ensure_configured` R5 ("before signing / building a URL") is covered for the pure functions only by the error being raised: the real `api_sign_request` / `cloudinary_url` are not spied on.
- **Needs a decision:** None.

## Conventions for this module

**Abbreviations:** `CLD` = cloudinary_client. Methods: `ENS` = `_ensure_configured`, `SIG` = `generate_upload_signature`, `URL` = `build_signed_delivery_url`, `GET` = `get_resource`, `DEL` = `destroy_resource`, `REN` = `rename_resource`, `UPD` = `update_resource_metadata`.

**Credentials (default in every test unless the case says otherwise):** `settings.CLOUDINARY_CLOUD_NAME = "demo"`, `settings.CLOUDINARY_API_KEY = "k"`, `settings.CLOUDINARY_API_SECRET = "s"`, set with `monkeypatch.setattr(settings, ...)`. "Creds OK" means these defaults.

**SDK global config:** before each test, save the SDK global config state and then set it to `cloud_name="prev-cloud"`, `api_key="prev-key"`, `api_secret="prev-secret"`, `secure=False`. Put the saved state back after the test. "Config unchanged" means `cloudinary.config()` still shows these four prev values. *(best-practice default, delegated by reviewer)*

**Externals mocked in every test:** `cloudinary.api.resource`, `cloudinary.api.update`, `cloudinary.uploader.destroy`, `cloudinary.uploader.rename`. Each is replaced with a recording fake (via `monkeypatch.setattr` on the SDK module attribute). By default a fake raises `AssertionError("unexpected Cloudinary call")` if it is called, so no test can reach the network. A case that expects a call installs a fake that returns the canned response it names, as a fresh dict object `RESP`. "Returns RESP" means the return value `is` that same object.
- **Argument check:** "SDK received X" means the fake was called exactly once, and binding the recorded `(args, kwargs)` to `inspect.signature` of the ORIGINAL SDK function gives exactly X. The original function is saved before patching. X is written as `public_id=…` (or `from_public_id=…, to_public_id=…`) plus `options={…}` for the `**options` part. "Exactly" means no extra keys. *(best-practice default, delegated by reviewer)*

**Real SDK helpers:** `cloudinary.utils.api_sign_request` and `cloudinary.utils.cloudinary_url` are NOT mocked.

**Recipe `SHA(str)`:** `hashlib.sha1(str.encode()).hexdigest()`.

**Error message `MSG`:** `"Cloudinary is not configured. Set CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, and CLOUDINARY_API_SECRET."`

**Signature segment pattern `SIGSEG`:** `s--[^/]{8}--`.

**Race simulations:** none.

**Time:** not mocked; nothing in this module depends on the current time.

## `_ensure_configured`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| CLD-ENS-01 | R3 | happy | Creds OK; global config = prev values (secure False) | call `_ensure_configured()` | returns `None`, no error; `cloudinary.config()` has `cloud_name == "demo"`, `api_key == "k"`, `api_secret == "s"`, `secure is True` | pass |
| CLD-ENS-02 | R1, R4, Errors | error | cloud name `""`, key `"k"`, secret `"s"` | call `_ensure_configured()` | raises `CloudinaryNotConfiguredError`; `str(exc) == MSG`; `isinstance(exc, RuntimeError)`; config unchanged (prev values, secure False) | pass |
| CLD-ENS-03 | R1, R4, Errors | error | cloud `"demo"`, key `""`, secret `"s"` | call `_ensure_configured()` | raises `CloudinaryNotConfiguredError` with `str(exc) == MSG`; config unchanged | pass |
| CLD-ENS-04 | R1, R4, Errors | error | cloud `"demo"`, key `"k"`, secret `""` | call `_ensure_configured()` | raises `CloudinaryNotConfiguredError` with `str(exc) == MSG`; config unchanged | pass |
| CLD-ENS-05 | R1, R4 | error | all three `""` | call `_ensure_configured()` | raises `CloudinaryNotConfiguredError` with `str(exc) == MSG`; config unchanged | pass |
| CLD-ENS-06 | R1, R4 | boundary | cloud `"demo"`, key `None`, secret `"s"` | call `_ensure_configured()` | raises `CloudinaryNotConfiguredError` with `str(exc) == MSG`; config unchanged | pass |
| CLD-ENS-07 | R2, R3 | boundary | all three set to `" "` (single space) | call `_ensure_configured()` | returns `None`, no error; `cloudinary.config()` has `cloud_name == " "`, `api_key == " "`, `api_secret == " "`, `secure is True` | pass |

## `generate_upload_signature`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| CLD-SIG-01 | R2, R3, R5 | happy | Creds OK (secret `"s"`) | `generate_upload_signature(public_id="p", asset_folder="", display_name="d", timestamp=1)` (no `delivery_type`) | returns exactly `"510bdebded8f7df0736f986c8d03a6408d67923f"` (spec example) | pass |
| CLD-SIG-02 | R2, R4 (resource_type not signed), side effect | happy | Creds OK | `generate_upload_signature(public_id="ws1/att-9", asset_folder="ws1/attachments", display_name="invoice.pdf", timestamp=1700000000, delivery_type="authenticated")` | result is a `str` of length 40 matching `^[0-9a-f]{40}$`; equals `SHA("asset_folder=ws1/attachments&display_name=invoice.pdf&public_id=ws1/att-9&timestamp=1700000000&type=authenticated" + "s")`; equals `cloudinary.utils.api_sign_request({"timestamp":1700000000,"public_id":"ws1/att-9","asset_folder":"ws1/attachments","display_name":"invoice.pdf","type":"authenticated"}, "s")`; afterwards `cloudinary.config()` has cloud_name `"demo"`, api_key `"k"`, api_secret `"s"`, secure `True` | pass |
| CLD-SIG-03 | R2 (`&` escaping) | boundary | Creds OK | `generate_upload_signature(public_id="p", asset_folder="f", display_name="a&b", timestamp=1, delivery_type="upload")` | equals `SHA("asset_folder=f&display_name=a%26b&public_id=p&timestamp=1&type=upload" + "s")`; differs from `SHA("asset_folder=f&display_name=a&b&public_id=p&timestamp=1&type=upload" + "s")` | pass |
| CLD-SIG-04 | R3 | boundary | Creds OK | three calls, each with one empty string (the others are `public_id="p"`, `asset_folder="f"`, `display_name="d"`, `timestamp=1`, `delivery_type="upload"`): (a) `asset_folder=""`, (b) `display_name=""`, (c) `public_id=""` | (a) == `SHA("display_name=d&public_id=p&timestamp=1&type=upload" + "s")`; (b) == `SHA("asset_folder=f&public_id=p&timestamp=1&type=upload" + "s")`; (c) == `SHA("asset_folder=f&display_name=d&timestamp=1&type=upload" + "s")`; the all-non-empty call equals `SHA("asset_folder=f&display_name=d&public_id=p&timestamp=1&type=upload" + "s")` and differs from each of (a), (b), (c) | pass |
| CLD-SIG-05 | R3 (timestamp 0) | boundary | Creds OK | call with `public_id="p"`, `asset_folder="f"`, `display_name="d"`, `delivery_type="upload"`: once with `timestamp=0`, once with `timestamp=1` | `timestamp=0` result == `SHA("asset_folder=f&display_name=d&public_id=p&type=upload" + "s")`; `timestamp=1` result == `SHA("asset_folder=f&display_name=d&public_id=p&timestamp=1&type=upload" + "s")`; the two differ | pass |
| CLD-SIG-06 | R4 | boundary | Creds OK; baseline B = call with `public_id="p"`, `asset_folder="f"`, `display_name="d"`, `timestamp=1`, `delivery_type="upload"` | five more calls, each changing one parameter from B: `public_id="p2"`, `asset_folder="f2"`, `display_name="d2"`, `timestamp=2`, `delivery_type="authenticated"` | each of the five results differs from B and from each other (six distinct values in total) | pass |
| CLD-SIG-07 | R4 (secret) | boundary | first call with secret `"s"`, then `monkeypatch` secret to `"s2"` | same inputs both times: `public_id="p"`, `asset_folder="f"`, `display_name="d"`, `timestamp=1`, `delivery_type="upload"` | results differ; the second equals `SHA("asset_folder=f&display_name=d&public_id=p&timestamp=1&type=upload" + "s2")` | pass |
| CLD-SIG-08 | R5 | boundary | Creds OK | call `public_id="p"`, `asset_folder="f"`, `display_name="d"`, `timestamp=1` three times: with no `delivery_type`, with `delivery_type="authenticated"`, with `delivery_type="upload"` | the no-arg result equals the explicit `"authenticated"` result and equals `SHA("asset_folder=f&display_name=d&public_id=p&timestamp=1&type=authenticated" + "s")`; the `"upload"` result is different | pass |
| CLD-SIG-09 | R6 | happy | Creds OK | call twice with identical inputs `public_id="p"`, `asset_folder="f"`, `display_name="d"`, `timestamp=1`, `delivery_type="upload"` | both results are equal | pass |
| CLD-SIG-10 | R1, Errors, ENS R5 | error | cloud `"demo"`, key `"k"`, secret `""`; global config = prev values | `generate_upload_signature(public_id="p", asset_folder="f", display_name="d", timestamp=1)` | raises `CloudinaryNotConfiguredError` with `str(exc) == MSG`; config unchanged; no SDK fake was called | pass |

## `build_signed_delivery_url`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| CLD-URL-01 | R2, R4, side effect | happy | Creds OK (demo/k/s) | `build_signed_delivery_url(public_id="a/b", resource_type="image", delivery_type="authenticated", version=123, fmt="jpg")` | result is a `str` equal to `"https://res.cloudinary.com/demo/image/authenticated/s--5pmR91cm--/v123/a/b.jpg"`; afterwards `cloudinary.config()` has cloud_name `"demo"`, api_key `"k"`, api_secret `"s"`, secure `True` | pass |
| CLD-URL-02 | R3, R4 (Q1) | happy | Creds OK | `public_id="ws/invoice-1"`, `resource_type="image"`, `delivery_type="upload"`, `version=123`, `fmt="pdf"` | equals `"https://res.cloudinary.com/demo/image/upload/v123/ws/invoice-1.pdf"`; contains no `"s--"` | pass |
| CLD-URL-03 | R3 | boundary | Creds OK | `public_id="a/b"`, `image`, `delivery_type="private"`, `version=123`, `fmt="jpg"` | equals `"https://res.cloudinary.com/demo/image/private/v123/a/b.jpg"`; no match for `SIGSEG` | pass |
| CLD-URL-04 | R2/R3 (exact match) | boundary | Creds OK | `public_id="a/b"`, `image`, `delivery_type="Authenticated"`, `version=123`, `fmt="jpg"` | equals `"https://res.cloudinary.com/demo/image/Authenticated/v123/a/b.jpg"`; no match for `SIGSEG` | pass |
| CLD-URL-05 | R4 | happy | cloud name `"acme-co"`, key `"k"`, secret `"s"` | (a) `public_id="docs/x"`, `resource_type="raw"`, `delivery_type="upload"`, `version=7`, `fmt="pdf"`; (b) the same with `delivery_type="authenticated"` | (a) equals `"https://res.cloudinary.com/acme-co/raw/upload/v7/docs/x.pdf"`; (b) matches `^https://res\.cloudinary\.com/acme-co/raw/authenticated/s--[^/]{8}--/v7/docs/x\.pdf$` | pass |
| CLD-URL-06 | R5 | boundary | Creds OK | `public_id="a/b"`, `image`, `upload`, `version=123`, `fmt="jpg"` with (a) `transformation=[{"width": 400, "crop": "limit"}]`, (b) `transformation=[]`, (c) `transformation=None` | (a) equals `"https://res.cloudinary.com/demo/image/upload/c_limit,w_400/v123/a/b.jpg"`; (b) and (c) each equal `"https://res.cloudinary.com/demo/image/upload/v123/a/b.jpg"` | pass |
| CLD-URL-07 | R6 | boundary | Creds OK | `public_id="a/b"`, `image`, `upload`, `version=123`, `fmt="jpg"` with (a) `flags="attachment"`, (b) `flags=""`, (c) `flags=None` | (a) equals `"https://res.cloudinary.com/demo/image/upload/fl_attachment/v123/a/b.jpg"`; (b) and (c) each equal `"https://res.cloudinary.com/demo/image/upload/v123/a/b.jpg"`; (b) and (c) do not contain `"fl_"` | pass |
| CLD-URL-08 | R5, R6 | happy | Creds OK | `public_id="a/b"`, `image`, `upload`, `version=123`, `fmt="jpg"`, `transformation=[{"width": 400, "crop": "limit"}]`, `flags="attachment"` | equals `"https://res.cloudinary.com/demo/image/upload/c_limit,w_400/fl_attachment/v123/a/b.jpg"` (spec example) | pass |
| CLD-URL-09 | R2, R5, R6 | happy | Creds OK | `public_id="a/b"`, `image`, `authenticated`, `version=123`, `fmt="jpg"`, `transformation=[{"width": 400, "crop": "limit"}]`, `flags="attachment"` | matches `^https://res\.cloudinary\.com/demo/image/authenticated/s--[^/]{8}--/c_limit,w_400/fl_attachment/v123/a/b\.jpg$`; the signature segment is not `s--5pmR91cm--` | pass |
| CLD-URL-10 | R2, R5, R6 (empty = none, signed path) | boundary | Creds OK | signed call as in URL-01 with (a) `transformation=[]`, (b) `flags=""` | (a) and (b) each equal `"https://res.cloudinary.com/demo/image/authenticated/s--5pmR91cm--/v123/a/b.jpg"` | pass |
| CLD-URL-11 | R2 (depends on secret) | boundary | cloud `"demo"`, key `"k"`, secret `"t"` | URL-01 inputs | equals `"https://res.cloudinary.com/demo/image/authenticated/s--IoFgbQBd--/v123/a/b.jpg"` (differs from the secret-`s` signature `s--5pmR91cm--`) | pass |
| CLD-URL-12 | R2 (depends on signed path) | boundary | Creds OK (demo/k/s) | four signed calls, each changing one thing from URL-01 (`public_id="a/b"`, `image`, `authenticated`, `version=123`, `fmt="jpg"`): (b) `public_id="a/c"`, (c) `fmt="png"`, (d) `flags="attachment"`, (e) `transformation=[{"width": 400, "crop": "limit"}]` | (b) equals `"https://res.cloudinary.com/demo/image/authenticated/s--5J5IkvPG--/v123/a/c.jpg"`; (c) equals `"https://res.cloudinary.com/demo/image/authenticated/s--KeyAQbUE--/v123/a/b.png"`; (d) equals `"https://res.cloudinary.com/demo/image/authenticated/s--LQNPH1Ob--/fl_attachment/v123/a/b.jpg"`; (e) equals `"https://res.cloudinary.com/demo/image/authenticated/s--6_QbkIb2--/c_limit,w_400/v123/a/b.jpg"`; none of the four signatures is `s--5pmR91cm--`. (Old sub-case (a) `version=124` moved to CLD-URL-15 with the corrected expectation.) | pass |
| CLD-URL-13 | R7 | happy | Creds OK | call twice with URL-09 inputs | both results are equal | pass |
| CLD-URL-14 | R1, Errors, ENS R5 | error | cloud `""`, key `"k"`, secret `"s"`; global config = prev values | URL-01 inputs | raises `CloudinaryNotConfiguredError` with `str(exc) == MSG`; config unchanged; no SDK fake was called | pass |
| CLD-URL-15 | R2a (version not signed), R4 | boundary | Creds OK (demo/k/s) | URL-01 inputs twice: (a) `version=123`, (b) `version=124` | (a) equals `"https://res.cloudinary.com/demo/image/authenticated/s--5pmR91cm--/v123/a/b.jpg"`; (b) equals `"https://res.cloudinary.com/demo/image/authenticated/s--5pmR91cm--/v124/a/b.jpg"`; the two signature segments are equal and the URLs differ only in the `v…/` segment | pass |

## `get_resource`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| CLD-GET-01 | R2, R4 | external | Creds OK; `cloudinary.api.resource` fake returns RESP = `{"public_id": "ws1/att-9", "bytes": 1234}` | `get_resource(public_id="ws1/att-9", resource_type="raw", delivery_type="upload")` | returns RESP (`is`); SDK received exactly `public_id="ws1/att-9"`, `options={"resource_type": "raw", "type": "upload"}`; no other fake called | pass |
| CLD-GET-02 | R3 | external | Creds OK; resource fake returns RESP = `{"public_id": "x"}` | `get_resource(public_id="x")` | returns RESP; SDK received exactly `public_id="x"`, `options={"resource_type": "image", "type": "authenticated"}` | pass |
| CLD-GET-03 | R5, Errors (SDK) | error | Creds OK; resource fake raises E = `cloudinary.exceptions.NotFound("Resource not found - x")` | `get_resource(public_id="x")` | raises `cloudinary.exceptions.NotFound`; the raised object `is` E (not wrapped) | pass |
| CLD-GET-04 | R5 | error | Creds OK; resource fake raises E = `ConnectionError("network down")` | `get_resource(public_id="x")` | raises `ConnectionError`; the raised object `is` E; not a `CloudinaryNotConfiguredError` | pass |
| CLD-GET-05 | R1, Errors, ENS R5 | error | cloud `"demo"`, key `""`, secret `"s"`; resource fake installed as a recorder that returns `{}` | `get_resource(public_id="x")` | raises `CloudinaryNotConfiguredError` with `str(exc) == MSG`; resource fake was called 0 times | pass |

## `destroy_resource`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| CLD-DEL-01 | R2, R4 | external | Creds OK; `cloudinary.uploader.destroy` fake returns RESP = `{"result": "ok"}` | `destroy_resource(public_id="ws1/att-9", resource_type="raw", delivery_type="upload")` | returns RESP (`is`); SDK received exactly `public_id="ws1/att-9"`, `options={"resource_type": "raw", "type": "upload", "invalidate": True}` | pass |
| CLD-DEL-02 | R3 | external | Creds OK; destroy fake returns RESP = `{"result": "ok"}` | `destroy_resource(public_id="x")` | returns RESP; SDK received exactly `public_id="x"`, `options={"resource_type": "image", "type": "authenticated", "invalidate": True}` | pass |
| CLD-DEL-03 | R4 | boundary | Creds OK; destroy fake returns RESP = `{"result": "not found"}` | `destroy_resource(public_id="missing")` | no exception; returns RESP (`is`), still `{"result": "not found"}` | pass |
| CLD-DEL-04 | R5, Errors (SDK) | error | Creds OK; destroy fake raises E = `cloudinary.exceptions.Error("boom")` | `destroy_resource(public_id="x")` | raises `cloudinary.exceptions.Error`; the raised object `is` E | pass |
| CLD-DEL-05 | R1, Errors | error | cloud `"demo"`, key `"k"`, secret `None`; destroy fake is a recorder that returns `{"result": "ok"}` | `destroy_resource(public_id="x")` | raises `CloudinaryNotConfiguredError` with `str(exc) == MSG`; destroy fake called 0 times | pass |

## `rename_resource`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| CLD-REN-01 | R2, R4 | external | Creds OK; `cloudinary.uploader.rename` fake returns RESP = `{"public_id": "ws1/att/abc"}` | `rename_resource(from_public_id="ws1/tmp/abc", to_public_id="ws1/att/abc", resource_type="raw", delivery_type="upload")` | returns RESP (`is`); SDK received exactly `from_public_id="ws1/tmp/abc"`, `to_public_id="ws1/att/abc"`, `options={"resource_type": "raw", "type": "upload", "to_type": "upload", "invalidate": True}`; `"overwrite"` is not a key in options | pass |
| CLD-REN-02 | R3 | external | Creds OK; rename fake returns RESP = `{"public_id": "b"}` | `rename_resource(from_public_id="a", to_public_id="b")` | returns RESP; SDK received exactly `from_public_id="a"`, `to_public_id="b"`, `options={"resource_type": "image", "type": "authenticated", "to_type": "authenticated", "invalidate": True}` | pass |
| CLD-REN-03 | R4, Errors (SDK) | error | Creds OK; rename fake raises E = `cloudinary.exceptions.BadRequest("to_public_id already exists")` | `rename_resource(from_public_id="a", to_public_id="b")` | raises `cloudinary.exceptions.BadRequest`; the raised object `is` E | pass |
| CLD-REN-04 | R1, Errors | error | cloud `""`, key `"k"`, secret `"s"`; rename fake is a recorder that returns `{}` | `rename_resource(from_public_id="a", to_public_id="b")` | raises `CloudinaryNotConfiguredError` with `str(exc) == MSG`; rename fake called 0 times | pass |

## `update_resource_metadata`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| CLD-UPD-01 | R2, R3, R4, R6 | external | Creds OK; `cloudinary.api.update` fake returns RESP = `{"public_id": "ws1/att-9"}` | `update_resource_metadata(public_id="ws1/att-9", resource_type="raw", delivery_type="upload", asset_folder="ws1/attachments", display_name="invoice.pdf")` | returns RESP (`is`); SDK received exactly `public_id="ws1/att-9"`, `options={"resource_type": "raw", "type": "upload", "asset_folder": "ws1/attachments", "display_name": "invoice.pdf"}` | pass |
| CLD-UPD-02 | R2, R5, defaults | boundary | Creds OK; update fake returns RESP = `{}` | `update_resource_metadata(public_id="x")` | returns RESP (`is`); the fake was called once (the update is still sent); SDK received exactly `public_id="x"`, `options={"resource_type": "image", "type": "authenticated"}` (no `asset_folder`, no `display_name` key) | pass |
| CLD-UPD-03 | R3 (`""` vs None) | boundary | Creds OK; update fake returns RESP = `{}` | `update_resource_metadata(public_id="x", asset_folder="")` | returns RESP; SDK received exactly `public_id="x"`, `options={"resource_type": "image", "type": "authenticated", "asset_folder": ""}`; no `display_name` key | pass |
| CLD-UPD-04 | R4 (`""` vs None) | boundary | Creds OK; update fake returns RESP = `{}` | `update_resource_metadata(public_id="x", display_name="")` | returns RESP; SDK received exactly `public_id="x"`, `options={"resource_type": "image", "type": "authenticated", "display_name": ""}`; no `asset_folder` key | pass |
| CLD-UPD-05 | R6, Errors (SDK) | error | Creds OK; update fake raises E = `cloudinary.exceptions.NotFound("Resource not found - x")` | `update_resource_metadata(public_id="x", display_name="n")` | raises `cloudinary.exceptions.NotFound`; the raised object `is` E | pass |
| CLD-UPD-06 | R1, Errors | error | cloud `"demo"`, key `""`, secret `"s"`; update fake is a recorder that returns `{}` | `update_resource_metadata(public_id="x", asset_folder="f")` | raises `CloudinaryNotConfiguredError` with `str(exc) == MSG`; update fake called 0 times | pass |

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| Overview: endpoints translate `CloudinaryNotConfiguredError` into an HTTP error | endpoints `attachments`, `mobile_upload`, `auth` (and `AttachmentManager`, `MobileUploadSessionManager`, `ProfileStampManager` as callers) | When Cloudinary credentials are missing, each endpoint returns its HTTP error and does not return a 500 |

## Spec gaps
None. (G1 from the spec's Gap log, the version-signing error, is closed by R2a; see Revision.)

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `_ensure_configured` | R1 | CLD-ENS-02, 03, 04, 05, 06 |
| `_ensure_configured` | R2 | CLD-ENS-07 |
| `_ensure_configured` | R3 | CLD-ENS-01, 07; CLD-SIG-02; CLD-URL-01 |
| `_ensure_configured` | R4 | CLD-ENS-02, 03, 04, 05, 06; CLD-SIG-10; CLD-URL-14 |
| `_ensure_configured` | R5 | CLD-SIG-10, CLD-URL-14, CLD-GET-05, CLD-DEL-05, CLD-REN-04, CLD-UPD-06 |
| `_ensure_configured` | Errors: credentials falsy | CLD-ENS-02, 03, 04, 05, 06 |
| `generate_upload_signature` | R1 / Errors | CLD-SIG-10 |
| `generate_upload_signature` | R2 | CLD-SIG-01, 02, 03 |
| `generate_upload_signature` | R3 | CLD-SIG-01, 04, 05 |
| `generate_upload_signature` | R4 | CLD-SIG-02 (resource_type not signed), 06, 07 |
| `generate_upload_signature` | R5 | CLD-SIG-01, 08 |
| `generate_upload_signature` | R6 | CLD-SIG-09 |
| `build_signed_delivery_url` | R1 / Errors | CLD-URL-14 |
| `build_signed_delivery_url` | R2 | CLD-URL-01, 05, 09, 10, 11, 12 |
| `build_signed_delivery_url` | R2a | CLD-URL-15 |
| `build_signed_delivery_url` | R3 | CLD-URL-02, 03, 04, 05 |
| `build_signed_delivery_url` | R4 | CLD-URL-01, 02, 05, 15 |
| `build_signed_delivery_url` | R5 | CLD-URL-06, 08, 09, 10, 12 |
| `build_signed_delivery_url` | R6 | CLD-URL-07, 08, 09, 10, 12 |
| `build_signed_delivery_url` | R7 | CLD-URL-13 |
| `get_resource` | R1 / Errors: credentials | CLD-GET-05 |
| `get_resource` | R2 | CLD-GET-01 |
| `get_resource` | R3 | CLD-GET-02 |
| `get_resource` | R4 | CLD-GET-01, 02 |
| `get_resource` | R5 / Errors: SDK error | CLD-GET-03, 04 |
| `destroy_resource` | R1 / Errors: credentials | CLD-DEL-05 |
| `destroy_resource` | R2 | CLD-DEL-01 |
| `destroy_resource` | R3 | CLD-DEL-02 |
| `destroy_resource` | R4 | CLD-DEL-01, 03 |
| `destroy_resource` | R5 / Errors: SDK error | CLD-DEL-04 |
| `rename_resource` | R1 / Errors: credentials | CLD-REN-04 |
| `rename_resource` | R2 | CLD-REN-01 |
| `rename_resource` | R3 | CLD-REN-02 |
| `rename_resource` | R4 / Errors: SDK error | CLD-REN-01, 02, 03 |
| `update_resource_metadata` | R1 / Errors: credentials | CLD-UPD-06 |
| `update_resource_metadata` | R2 | CLD-UPD-01, 02 |
| `update_resource_metadata` | R3 | CLD-UPD-01, 02, 03 |
| `update_resource_metadata` | R4 | CLD-UPD-01, 02, 04 |
| `update_resource_metadata` | R5 | CLD-UPD-02 |
| `update_resource_metadata` | R6 / Errors: SDK error | CLD-UPD-01, 05 |
