# Execution notes — `app/core/cloudinary_client.py`

> Cases: `tests/unit/core/cloudinary_client.cases.md` (revision 3) · Tests: `tests/unit/core/test_cloudinary_client.py` · Source commit: e48a092
> Result: 52 passed · 0 xfailed · 0 discrepancies (DISCREPANCY-1 resolved) · 0 errors — branch coverage 100%
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/core/test_cloudinary_client.py -q -p no:cacheprovider --cov=app.core.cloudinary_client --cov-branch --cov-report=term-missing`

## How the tests are built
- **No database.** Per the spec Overview, nothing here touches a session; the `db` fixture is never requested.
- **Conventions → fixtures/helpers** (top of the test file, each commented):
  - Credentials → autouse fixture `_creds` sets `settings.CLOUDINARY_*` to `demo` / `k` / `s` via `monkeypatch`; `set_creds(mp, cloud, key, secret)` overrides them per case.
  - SDK global config → autouse fixture `_sdk_config`: deep-copies `vars(cloudinary._config)`, sets `PREV` (`prev-cloud` / `prev-key` / `prev-secret` / `secure=False`), and after the test clears and restores the saved `__dict__`. `assert_config_unchanged()` compares against `PREV`; `assert_config_set()` checks the demo/k/s values with `secure is True`.
  - Externals → autouse fixture `sdk` (class `SDK`) installs a `Fake` on each of `cloudinary.api.resource`, `cloudinary.api.update`, `cloudinary.uploader.destroy`, `cloudinary.uploader.rename`. By default each raises `AssertionError("unexpected Cloudinary call")` (the call is still recorded). `sdk.returning(name, RESP)` / `sdk.raising(name, E)` install case-specific fakes. `Fake.received()` asserts exactly one call and binds `(args, kwargs)` to `inspect.signature` of the ORIGINAL SDK function (saved at import time, in `_ORIGINALS`), returning `{"public_id": …, "options": {…}}`. The case's X is compared with `==`, so no extra keys are allowed.
  - `SHA(str)` → `hashlib.sha1(...).hexdigest()`; `MSG` and `SIGSEG` are module constants.
  - "no SDK fake was called" (SIG-10, URL-14) → `sdk.total_calls() == 0`; "no other fake called" (GET-01) → `sdk.total_calls(exclude=("resource",)) == 0`.
- `cloudinary.utils.api_sign_request` / `cloudinary_url` are real (cloudinary 1.44.1), as the spec says.
- Local helpers `_sig(**over)` / `_url(**over)` build the cases' baseline inputs; `_sigseg(url)` pulls the `s--…--` segment after `/image/authenticated/`.
- **Parametrized:** CLD-ENS-02..06 (same setup and assertions, different credential triple). Each has its own `pytest.param` id. The extra `isinstance(exc, RuntimeError)` check runs only for ENS-02, because only that case asks for it.
- Stability: 3 runs, identical outcome (52 passed); re-confirmed on cases revision 3.
- CLD-URL-15 checks "the URLs differ only in the `v…/` segment" as `a.replace("/v123/", "/v124/") == b`.

## Discrepancies
None open. DISCREPANCY-1 (CLD-URL-12 expected `version` to change the URL signature, but the SDK does not sign the version) was resolved in cases revision 2. Spec R2 was corrected and R2a added; CLD-URL-12 sub-case (a) moved to CLD-URL-15 with the corrected expectation.

## Coverage gaps
None — 100% branch coverage (43 statements, 10 branches).

## Factories added
None. The module needs no models. The `Fake`/`SDK` recording-fake pattern, the `_sdk_config` save/restore fixture and the credential setter are local to this file. If another module's tests (for example `AttachmentManager`, `MobileUploadSessionManager`, `ProfileStampManager`) need to stub Cloudinary, move them into a shared `tests/unit/_cloudinary_fakes.py`.

## Notes for maintainers
- Hard-coded signed values (`s--5pmR91cm--`, `s--IoFgbQBd--`, `s--5J5IkvPG--`, `s--KeyAQbUE--`, `s--LQNPH1Ob--`, `s--6_QbkIb2--`, `510bdebd…923f`) are tied to SDK 1.44.1 with SHA-1 and signature_version 2. If an SDK upgrade changes the URL signature algorithm (for example `long_url_signature`), URL-01, 10, 11, 12 and 15 will fail.
- `_sdk_config` restores `cloudinary._config.__dict__` wholesale. It reaches into a private attribute because the SDK has no public reset.

## Revision history
- **Rev 3 (cases revision 3, no case changes).** Cases revision 3 re-ran on the unchanged approved spec: no cases added, changed or retired, and verify.md (cases rev 2) is PASS with no findings routed to the executor. The test file is unchanged; all 52 case IDs are still present exactly once. Re-ran 3 times (52 passed each) and re-measured coverage: 100% branch (43 statements, 10 branches).
- **Rev 2 (cases revision 2 + verify findings).** CLD-URL-11 now uses secret `t` and asserts the exact URL with `s--IoFgbQBd--`; before, it checked only the shape and that the signature differed. CLD-URL-12 no longer has the strict `xfail` marker (DISCREPANCY-1, verify finding 3). The `version=124` sub-case is gone, and sub-cases (b)–(e) now assert the exact known URLs; (e), the transformation case giving `s--6_QbkIb2--`, is new. Added CLD-URL-15: version is not signed, so v123 and v124 share `s--5pmR91cm--`. All other tests are unchanged. No IDs were retired. Result went from 50 passed · 1 xfailed to 52 passed.
- **Rev 1.** First implementation: 50 passed and 1 xfailed (DISCREPANCY-1).
