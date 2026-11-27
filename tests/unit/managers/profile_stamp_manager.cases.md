# Test cases — `app/managers/profile_stamp_manager.py`

> **Spec:** `tests/unit/managers/profile_stamp_manager.spec.md` (source commit e48a092)
> **Status:** READY
> **Revision:** 3 (2026-11-04) — from verify round 2 (R2-1): new PSM-VS-45 and PSM-DS-33, a `public_id` of OWN5 plus a trailing newline (a `$`-anchored regex without full match accepts it), strict xfail BUG-1864 / BUG-1865. Gap 2 closed: the spec (validator R4b) keeps the client `url` required (1–2048) and ignored, so VS-10 … VS-12 stand. No card changed or retired.
> **Revision:** 2 (2026-11-04) — from `profile_stamp_manager.verify.md` and spec revision 2026-11-04 (a stamp id is exactly the user's prefix plus 32 lowercase hex characters). Finding 1: new VS-36 (client url on another cloud) and VS-37 (client url on our cloud, another file), xfail BUG-1866. Finding 2: new DS-25 (`stamp` without the dash), xfail BUG-1865. Finding 3 / gap 3 (closed by the spec): new VS-38 … VS-44 (validator) and DS-26 … DS-32 (destroy) for an empty token, 31 and 33 hex characters, upper-case hex, a non-hex letter, and a suffix after the token (`/x`, `.png`), strict xfail on BUG-1864 / BUG-1865. Changed: VS-06, VS-07 now build `SavedStampImage` directly (target `schema`), because a 512-character id under the prefix is no longer a valid stamp id; the 1–512 limit is the schema's. Conventions: `SavedStampImage` and the token variants added. None retired.
> **Counts:** 103 cases · 59 expected-to-pass · 44 expected-to-fail (bugs) · 2 deferred

## Reviewer summary
- **Per callable:** `build_stamp_public_id` 7 · `build_stamp_asset_folder` 11 · `sign_stamp_image_upload` 7 · `destroy_saved_stamp_image` 33 (19 bug) · `validate_saved_stamp_payload` 45 (25 bug).
- **Revision 2:** the minted-form rule (prefix + exactly 32 lowercase hex characters, nothing after) has its own refusal cards on both sides: VS-38 … VS-44 and DS-26 … DS-32. BUG-1866 now also refuses a client url on Cloudinary, another cloud's (VS-36) or ours pointing at another file (VS-37). DS-25 is the delete-side twin of VS-31.
- **Depth:** full for which stamp file may be saved and deleted (owner's OQ-11, OQ-12: BUG-1864 … 1866); lighter for the two name builders and the signer (pure string work, no stock, money or orders).
- **BUG-1864 (22 strict cards, VS-21 … VS-34, VS-38 … VS-45) and BUG-1865 (18 strict cards, DS-16 … DS-33):** one shape per card: another user with a higher id (55) and a caller with a higher id asking for the lower user's file; `avatar-` instead of `stamp-`; the production form in development; `production/…`; an attachment id; other capitals; a leading space; the prefix in the middle; `stamp` without the dash. Accepted: the own id in development, in production, and with `ENVIRONMENT` used when `CLOUDINARY_UPLOAD_ENV` is empty. Every refusal: exact type and message, the payload not changed, Cloudinary never called. Every one of these calls passes `user_id=`, so today it raises `TypeError` (spec Notes).
- **BUG-1866:** VS-35 (with VS-36, VS-37 since Revision 2), strict: the url starts with `https://res.cloudinary.com/demo-cloud/image/authenticated/`, contains the `public_id`, and never the client's `https://tracker.example/p.png`. No pass card asserts the returned `url`: today's value is the bug.
- **BUG-1713:** DS-13, strict: one WARNING naming the `public_id` and the error. DS-12, DS-14 (no warning on success or "not found") pass today.
- **Kept passing:** validation and deletion of an own-prefix id without the new parameter (VS-05, DS-09), as the spec's Notes say.
- **Notable design choices:** Cloudinary is patched only where the spec names it (`destroy_resource`, and `generate_upload_signature` in SG-01, SG-02, SG-06); SG-03 … SG-05 sign for real with the test credentials and check the signature with `cloudinary.utils.api_sign_request`.
- **Needs a decision:** None. Gap 1 is minor; gap 3 closed (Revision 2); gap 2 closed (Revision 3).

## Conventions for this module

**IDs.** `PSM` = `app/managers/profile_stamp_manager.py`. `PI` build_stamp_public_id · `AF` build_stamp_asset_folder · `SG` sign_stamp_image_upload · `DS` destroy_saved_stamp_image · `VS` validate_saved_stamp_payload.

**Actors and fixed values.**
- `M` = `profile_stamp_manager` (`from app.managers.profile_stamp_manager import ProfileStampManager, profile_stamp_manager`). `result` = what the When returns. No database.
- `CloudinaryNotConfiguredError` (`app.core.cloudinary_client`). `settings` (`app.core.config`). `PydanticValidationError` = `pydantic.ValidationError`. `SimpleNamespace` (`types`). `api_sign_request` (`cloudinary.utils`). `patch` (`unittest.mock`). `copy`, `logging`, `re`, `uuid`.
- U5 = `SimpleNamespace(id=5, name="Ann Lee")`. U55 = `SimpleNamespace(id=55, name="Bob")`.
- TOKEN = `"0123456789abcdef0123456789abcdef"`. OWN5 = `"development/profiles/5/stamp-" + TOKEN`. PRE5 = `"development/profiles/5/stamp-"`.
- Token variants: TOKEN31 = `TOKEN[:31]`; TOKEN33 = `TOKEN + "0"`; TOKENU = `TOKEN.upper()`; TOKENG = `TOKEN[:31] + "g"` (32 characters, one not hex).
- `SavedStampImage` (`app.schemas.saved_stamp`).
- **IMG(pid)** = `{"kind": "image", "public_id": pid, "url": "https://tracker.example/p.png", "width": 10, "height": 10}`.
- **VEC** = `{"kind": "vector", "strokes": [{"color": "#000000", "width": 0.5, "points": []}], "viewBox": {"width": 100, "height": 50}}`.
- KIND_MSG = `"saved_stamp.kind must be 'vector' or 'image'."`. FOREIGN_MSG = `"saved_stamp.public_id is not a stamp of this user"`.

**Settings (every test).** With `monkeypatch.setattr(settings, …)`: `CLOUDINARY_UPLOAD_ENV "development"`, `ENVIRONMENT "development"`, `CLOUDINARY_CLOUD_NAME "demo-cloud"`, `CLOUDINARY_API_KEY "123456"`, `CLOUDINARY_API_SECRET "s3cret"`. A Given line "settings: NAME value" overrides one of them the same way.

**Externals.**
- **dr** (every `DS` and `VS` card): `patch("app.managers.profile_stamp_manager.destroy_resource", return_value={"result": "ok"})` around the When; the card may set another `return_value` or a `side_effect`.
- **gus** (only where a card names it): `patch("app.managers.profile_stamp_manager.generate_upload_signature", return_value="sig-x")` around the When. Elsewhere it runs for real.
- **fixed uuid** = `patch("app.managers.profile_stamp_manager.uuid.uuid4", return_value=uuid.UUID(TOKEN))` around the When. **fixed time** = `patch("app.managers.profile_stamp_manager.time.time", return_value=1767225600.9)` around the When.

**Named checks.**
- `raises: <Type>` = `with pytest.raises(<Type>) as exc:` around the call; further `raises:` lines on `exc.value`. `type(exc.value) is ValueError` means exactly that class (not a Pydantic error).
- **payload kept** = `payload == before`, where `before = copy.deepcopy(payload)` is taken just before the When.
- **warnings** = `[r for r in caplog.records if r.levelno == logging.WARNING and r.name == "app.managers.profile_stamp_manager"]`, with `caplog.set_level(logging.WARNING, logger="app.managers.profile_stamp_manager")` before the When.
- **kw** = `dr.call_args.kwargs`. A default argument may be left out by the code, so a check written `kw.get("resource_type", "image") == "image"` accepts either.

**xfail cards.** `pytest.mark.xfail(strict=True, reason="BUG-n")`, `raises` not narrowed. Write the call exactly as shown, `user_id=` included.

**Race simulations.** None.

## `ProfileStampManager.build_stamp_public_id`

### PSM-PI-01 — outside production the id is `<env>/profiles/<id>/stamp-<token>`
- **Rules:** `build_stamp_public_id` R3, R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. fixed uuid.

**When**
- `result = M.build_stamp_public_id(user_id=5)`.

**Then**
1. returns: `result == "development/profiles/5/stamp-0123456789abcdef0123456789abcdef"`.

### PSM-PI-02 — in production the id has no environment prefix
- **Rules:** `build_stamp_public_id` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. settings: `CLOUDINARY_UPLOAD_ENV "production"`.
2. fixed uuid.

**When**
- `result = M.build_stamp_public_id(user_id=5)`.

**Then**
1. returns: `result == "profiles/5/stamp-0123456789abcdef0123456789abcdef"`.

### PSM-PI-03 — an empty upload environment falls back to ENVIRONMENT
- **Rules:** `build_stamp_public_id` R1, R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. settings: `CLOUDINARY_UPLOAD_ENV ""`.
2. settings: `ENVIRONMENT "production"`.
3. fixed uuid.

**When**
- `result = M.build_stamp_public_id(user_id=5)`.

**Then**
1. returns: `result == "profiles/5/stamp-0123456789abcdef0123456789abcdef"`.

### PSM-PI-04 — a non-empty upload environment wins over ENVIRONMENT
- **Rules:** `build_stamp_public_id` R1, R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. settings: `CLOUDINARY_UPLOAD_ENV "staging"`.
2. settings: `ENVIRONMENT "production"`.
3. fixed uuid.

**When**
- `result = M.build_stamp_public_id(user_id=5)`.

**Then**
1. returns: `result == "staging/profiles/5/stamp-0123456789abcdef0123456789abcdef"`.

### PSM-PI-05 — "Production" with a capital is not production
- **Rules:** `build_stamp_public_id` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. settings: `CLOUDINARY_UPLOAD_ENV "Production"`.
2. fixed uuid.

**When**
- `result = M.build_stamp_public_id(user_id=5)`.

**Then**
1. returns: `result == "Production/profiles/5/stamp-0123456789abcdef0123456789abcdef"`.

### PSM-PI-06 — both settings empty give a leading slash
- **Rules:** `build_stamp_public_id` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. settings: `CLOUDINARY_UPLOAD_ENV ""`.
2. settings: `ENVIRONMENT ""`.
3. fixed uuid.

**When**
- `result = M.build_stamp_public_id(user_id=5)`.

**Then**
1. returns: `result == "/profiles/5/stamp-0123456789abcdef0123456789abcdef"`.

### PSM-PI-07 — each call gives a new 32-character lowercase hex token
- **Rules:** `build_stamp_public_id` R4, R2
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. No uuid patch.
2. `first = M.build_stamp_public_id(user_id=5)`.

**When**
- `result = M.build_stamp_public_id(user_id=5)`.

**Then**
1. returns: `result != first`.
2. returns: `re.fullmatch(r"development/profiles/5/stamp-[0-9a-f]{32}", result) is not None`.
3. returns: `re.fullmatch(r"development/profiles/5/stamp-[0-9a-f]{32}", first) is not None`.

## `ProfileStampManager.build_stamp_asset_folder`

### PSM-AF-01 — a slash becomes a dash
- **Rules:** `build_stamp_asset_folder` R1, R3
- **Kind:** happy
- **Expect:** pass

**When**
- `result = M.build_stamp_asset_folder(user_name="Ann / Lee", user_id=5)`.

**Then**
1. returns: `result == "Dev/Profile stamps/Ann - Lee"`.

### PSM-AF-02 — a backslash becomes a dash
- **Rules:** `build_stamp_asset_folder` R1
- **Kind:** happy
- **Expect:** pass

**When**
- `result = M.build_stamp_asset_folder(user_name="Ann\\Lee", user_id=5)` (one backslash in the name).

**Then**
1. returns: `result == "Dev/Profile stamps/Ann-Lee"`.

### PSM-AF-03 — outer spaces are removed
- **Rules:** `build_stamp_asset_folder` R1
- **Kind:** boundary
- **Expect:** pass

**When**
- `result = M.build_stamp_asset_folder(user_name=" Ann ", user_id=5)`.

**Then**
1. returns: `result == "Dev/Profile stamps/Ann"`.

### PSM-AF-04 — case, inner spaces and other characters are kept
- **Rules:** `build_stamp_asset_folder` R1
- **Kind:** boundary
- **Expect:** pass

**When**
- `result = M.build_stamp_asset_folder(user_name="  Mary  O'NEIL_é ", user_id=5)`.

**Then**
1. returns: `result == "Dev/Profile stamps/Mary  O'NEIL_é"`.

### PSM-AF-05 — an empty name becomes user-<id>
- **Rules:** `build_stamp_asset_folder` R2
- **Kind:** boundary
- **Expect:** pass

**When**
- `result = M.build_stamp_asset_folder(user_name="", user_id=5)`.

**Then**
1. returns: `result == "Dev/Profile stamps/user-5"`.

### PSM-AF-06 — a whitespace-only name becomes user-<id>
- **Rules:** `build_stamp_asset_folder` R2
- **Kind:** boundary
- **Expect:** pass

**When**
- `result = M.build_stamp_asset_folder(user_name="   ", user_id=5)`.

**Then**
1. returns: `result == "Dev/Profile stamps/user-5"`.

### PSM-AF-07 — a name of only slashes is not empty
- **Rules:** `build_stamp_asset_folder` R2
- **Kind:** boundary
- **Expect:** pass

**When**
- `result = M.build_stamp_asset_folder(user_name="//", user_id=5)`.

**Then**
1. returns: `result == "Dev/Profile stamps/--"`.

### PSM-AF-08 — production has no Dev prefix
- **Rules:** `build_stamp_asset_folder` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. settings: `CLOUDINARY_UPLOAD_ENV "production"`.

**When**
- `result = M.build_stamp_asset_folder(user_name="Ann Lee", user_id=5)`.

**Then**
1. returns: `result == "Profile stamps/Ann Lee"`.

### PSM-AF-09 — any other environment gets the Dev prefix, whatever its name
- **Rules:** `build_stamp_asset_folder` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. settings: `CLOUDINARY_UPLOAD_ENV "staging"`.

**When**
- `result = M.build_stamp_asset_folder(user_name="Ann Lee", user_id=5)`.

**Then**
1. returns: `result == "Dev/Profile stamps/Ann Lee"`.

### PSM-AF-10 — production is read from ENVIRONMENT when the upload environment is empty
- **Rules:** `build_stamp_asset_folder` R3 (via `build_stamp_public_id` R1)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. settings: `CLOUDINARY_UPLOAD_ENV ""`.
2. settings: `ENVIRONMENT "production"`.

**When**
- `result = M.build_stamp_asset_folder(user_name="Ann Lee", user_id=5)`.

**Then**
1. returns: `result == "Profile stamps/Ann Lee"`.

### PSM-AF-11 — a None name raises AttributeError
- **Rules:** `build_stamp_asset_folder` Errors
- **Kind:** error
- **Expect:** pass

**When**
- `M.build_stamp_asset_folder(user_name=None, user_id=5)`.

**Then**
1. raises: `AttributeError`.

## `ProfileStampManager.sign_stamp_image_upload`

### PSM-SG-01 — an empty cloud name raises before anything is signed
- **Rules:** `sign_stamp_image_upload` R1, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. settings: `CLOUDINARY_CLOUD_NAME ""`.
2. gus.

**When**
- `M.sign_stamp_image_upload(U5)`.

**Then**
1. raises: `CloudinaryNotConfiguredError`.
2. raises: `str(exc.value) == "Cloudinary cloud name and API key are required."`.
3. mock called: `gus.call_count == 0`.

### PSM-SG-02 — an empty API key raises before anything is signed
- **Rules:** `sign_stamp_image_upload` R1, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. settings: `CLOUDINARY_API_KEY ""`.
2. gus.

**When**
- `M.sign_stamp_image_upload(U5)`.

**Then**
1. raises: `CloudinaryNotConfiguredError`.
2. raises: `str(exc.value) == "Cloudinary cloud name and API key are required."`.
3. mock called: `gus.call_count == 0`.

### PSM-SG-03 — an empty API secret raises the client's error
- **Rules:** `sign_stamp_image_upload` R2, Errors row 2
- **Kind:** error
- **Expect:** pass

**Given**
1. settings: `CLOUDINARY_API_SECRET ""`.

**When**
- `M.sign_stamp_image_upload(U5)`.

**Then**
1. raises: `CloudinaryNotConfiguredError`.
2. raises: `str(exc.value) == "Cloudinary is not configured. Set CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, and CLOUDINARY_API_SECRET."`.

### PSM-SG-04 — the response holds every field as stated
- **Rules:** `sign_stamp_image_upload` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. fixed uuid.
2. fixed time.

**When**
- `result = M.sign_stamp_image_upload(U5)`.

**Then**
1. returns: `result.cloud_name == "demo-cloud"`, `result.api_key == "123456"`.
2. returns: `result.timestamp == 1767225600`.
3. returns: `result.public_id == "development/profiles/5/stamp-0123456789abcdef0123456789abcdef"`.
4. returns: `result.asset_folder == "Dev/Profile stamps/Ann Lee"`.
5. returns: `result.display_name == "saved-stamp"`, `result.type == "authenticated"`, `result.resource_type == "image"`.
6. returns: `result.upload_url == "https://api.cloudinary.com/v1_1/demo-cloud/image/upload"`.

### PSM-SG-05 — the signature is the signature of the response's own fields
- **Rules:** `sign_stamp_image_upload` R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. fixed uuid.
2. fixed time.

**When**
- `result = M.sign_stamp_image_upload(U5)`.

**Then**
1. returns: `result.signature == api_sign_request({"timestamp": result.timestamp, "public_id": result.public_id, "asset_folder": result.asset_folder, "display_name": result.display_name, "type": "authenticated"}, "s3cret")`.
2. returns: `re.fullmatch(r"[0-9a-f]{40}", result.signature) is not None`.

### PSM-SG-06 — the signer receives exactly the response's values
- **Rules:** `sign_stamp_image_upload` R4
- **Kind:** external
- **Expect:** pass

**Given**
1. fixed uuid.
2. fixed time.
3. gus.

**When**
- `result = M.sign_stamp_image_upload(U5)`.

**Then**
1. returns: `result.signature == "sig-x"`.
2. mock called: `gus.call_count == 1`.
3. mock called: `gus.call_args.kwargs["public_id"] == "development/profiles/5/stamp-0123456789abcdef0123456789abcdef"`.
4. mock called: `gus.call_args.kwargs["asset_folder"] == "Dev/Profile stamps/Ann Lee"`.
5. mock called: `gus.call_args.kwargs["display_name"] == "saved-stamp"`, `gus.call_args.kwargs["timestamp"] == 1767225600`.
6. mock called: `gus.call_args.kwargs.get("delivery_type", "authenticated") == "authenticated"`.

### PSM-SG-07 — two calls give different public ids; the user is not changed
- **Rules:** `sign_stamp_image_upload` R5
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. No uuid patch.
2. `first = M.sign_stamp_image_upload(U5)`.

**When**
- `result = M.sign_stamp_image_upload(U5)`.

**Then**
1. returns: `result.public_id != first.public_id`.
2. unchanged: `vars(U5) == {"id": 5, "name": "Ann Lee"}`.

## `ProfileStampManager.destroy_saved_stamp_image`

### PSM-DS-01 — None deletes nothing
- **Rules:** `destroy_saved_stamp_image` R1
- **Kind:** boundary
- **Expect:** pass

**When**
- `result = M.destroy_saved_stamp_image(None)`.

**Then**
1. returns: `result is None`.
2. mock called: `dr.call_count == 0`.

### PSM-DS-02 — an empty dict deletes nothing
- **Rules:** `destroy_saved_stamp_image` R1
- **Kind:** boundary
- **Expect:** pass

**When**
- `result = M.destroy_saved_stamp_image({})`.

**Then**
1. returns: `result is None`.
2. mock called: `dr.call_count == 0`.

### PSM-DS-03 — a vector stamp deletes nothing
- **Rules:** `destroy_saved_stamp_image` R2
- **Kind:** boundary
- **Expect:** pass

**When**
- `result = M.destroy_saved_stamp_image({"kind": "vector", "public_id": OWN5})`.

**Then**
1. returns: `result is None`.
2. mock called: `dr.call_count == 0`.

### PSM-DS-04 — a stamp without kind deletes nothing
- **Rules:** `destroy_saved_stamp_image` R2
- **Kind:** boundary
- **Expect:** pass

**When**
- `result = M.destroy_saved_stamp_image({"public_id": OWN5})`.

**Then**
1. returns: `result is None`.
2. mock called: `dr.call_count == 0`.

### PSM-DS-05 — kind "IMAGE" in capitals deletes nothing
- **Rules:** `destroy_saved_stamp_image` R2
- **Kind:** boundary
- **Expect:** pass

**When**
- `result = M.destroy_saved_stamp_image({"kind": "IMAGE", "public_id": OWN5})`.

**Then**
1. returns: `result is None`.
2. mock called: `dr.call_count == 0`.

### PSM-DS-06 — an image stamp without public_id deletes nothing
- **Rules:** `destroy_saved_stamp_image` R3
- **Kind:** boundary
- **Expect:** pass

**When**
- `result = M.destroy_saved_stamp_image({"kind": "image"})`.

**Then**
1. returns: `result is None`.
2. mock called: `dr.call_count == 0`.

### PSM-DS-07 — public_id None deletes nothing
- **Rules:** `destroy_saved_stamp_image` R3
- **Kind:** boundary
- **Expect:** pass

**When**
- `result = M.destroy_saved_stamp_image({"kind": "image", "public_id": None})`.

**Then**
1. returns: `result is None`.
2. mock called: `dr.call_count == 0`.

### PSM-DS-08 — public_id "" deletes nothing
- **Rules:** `destroy_saved_stamp_image` R3
- **Kind:** boundary
- **Expect:** pass

**When**
- `result = M.destroy_saved_stamp_image({"kind": "image", "public_id": ""})`.

**Then**
1. returns: `result is None`.
2. mock called: `dr.call_count == 0`.

### PSM-DS-09 — the user's own stamp file is deleted as an authenticated image
- **Rules:** `destroy_saved_stamp_image` R4
- **Kind:** external
- **Expect:** pass

**When**
- `result = M.destroy_saved_stamp_image(IMG(OWN5))`.

**Then**
1. returns: `result is None`.
2. mock called: `dr.call_count == 1`.
3. mock called: `kw["public_id"] == OWN5`.
4. mock called: `kw.get("resource_type", "image") == "image"`.
5. mock called: `kw.get("delivery_type", "authenticated") == "authenticated"`.

### PSM-DS-10 — "not configured" from Cloudinary is swallowed
- **Rules:** `destroy_saved_stamp_image` R5
- **Kind:** error
- **Expect:** pass

**Given**
1. dr, but `side_effect=CloudinaryNotConfiguredError("x")`.

**When**
- `result = M.destroy_saved_stamp_image(IMG(OWN5))` (no exception escapes).

**Then**
1. returns: `result is None`.
2. mock called: `dr.call_count == 1`.

### PSM-DS-11 — a network error is swallowed
- **Rules:** `destroy_saved_stamp_image` R5
- **Kind:** error
- **Expect:** pass

**Given**
1. dr, but `side_effect=RuntimeError("network down")`.

**When**
- `result = M.destroy_saved_stamp_image(IMG(OWN5))` (no exception escapes).

**Then**
1. returns: `result is None`.
2. mock called: `dr.call_count == 1`.

### PSM-DS-12 — a "not found" answer is not an error and logs no warning
- **Rules:** `destroy_saved_stamp_image` R5, R5a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. dr, but `return_value={"result": "not found"}`.
2. caplog at WARNING (see **warnings**).

**When**
- `result = M.destroy_saved_stamp_image(IMG(OWN5))`.

**Then**
1. returns: `result is None`.
2. mock called: `dr.call_count == 1`.
3. log: `warnings == []`.

### PSM-DS-13 — a failed delete logs one warning naming the public_id and the error
- **Rules:** `destroy_saved_stamp_image` R5a [BUG-1713]
- **Kind:** bug
- **Expect:** xfail BUG-1713
- **Fails today on:** Then 2 (nothing is logged)

**Given**
1. dr, but `side_effect=RuntimeError("network down")`.
2. caplog at WARNING (see **warnings**).

**When**
- `result = M.destroy_saved_stamp_image(IMG(OWN5))`.

**Then**
1. returns: `result is None`.
2. log: `len(warnings) == 1`.
3. log: `OWN5 in warnings[0].getMessage()`.
4. log: `"network down" in warnings[0].getMessage()`.

### PSM-DS-14 — a successful delete logs no warning
- **Rules:** `destroy_saved_stamp_image` R5a
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. caplog at WARNING (see **warnings**).

**When**
- `result = M.destroy_saved_stamp_image(IMG(OWN5))`.

**Then**
1. returns: `result is None`.
2. log: `warnings == []`.

### PSM-DS-15 — a non-dict value raises AttributeError
- **Rules:** `destroy_saved_stamp_image` R6
- **Kind:** error
- **Expect:** pass

**When**
- `M.destroy_saved_stamp_image("image")`.

**Then**
1. raises: `AttributeError`.
2. mock called: `dr.call_count == 0`.

### PSM-DS-16 — with the user's id, the user's own file is still deleted
- **Rules:** `destroy_saved_stamp_image` R4 [BUG-1865]
- **Kind:** bug
- **Expect:** xfail BUG-1865
- **Fails today on:** Then 1 (the call raises TypeError: no `user_id` parameter)

**When**
- `result = M.destroy_saved_stamp_image(IMG(OWN5), user_id=5)`.

**Then**
1. returns: `result is None`.
2. mock called: `dr.call_count == 1`.
3. mock called: `kw["public_id"] == OWN5`.

### PSM-DS-17 — another user's (higher id) stamp file is never deleted
- **Rules:** `destroy_saved_stamp_image` R4a [BUG-1865]
- **Kind:** bug
- **Expect:** xfail BUG-1865
- **Fails today on:** Then 1 (the call raises TypeError: no `user_id` parameter)

**When**
- `result = M.destroy_saved_stamp_image(IMG("development/profiles/55/stamp-" + TOKEN), user_id=5)`.

**Then**
1. returns: `result is None`.
2. mock called: `dr.call_count == 0`.

### PSM-DS-18 — a caller with a higher id cannot delete the lower user's stamp file
- **Rules:** `destroy_saved_stamp_image` R4a [BUG-1865]
- **Kind:** bug
- **Expect:** xfail BUG-1865
- **Fails today on:** Then 1 (the call raises TypeError: no `user_id` parameter)

**When**
- `result = M.destroy_saved_stamp_image(IMG(OWN5), user_id=55)`.

**Then**
1. returns: `result is None`.
2. mock called: `dr.call_count == 0`.

### PSM-DS-19 — an attachment's file is never deleted
- **Rules:** `destroy_saved_stamp_image` R4a [BUG-1865]
- **Kind:** bug
- **Expect:** xfail BUG-1865
- **Fails today on:** Then 1 (the call raises TypeError: no `user_id` parameter)

**When**
- `result = M.destroy_saved_stamp_image(IMG("ws-12/9f2c" + TOKEN), user_id=5)`.

**Then**
1. returns: `result is None`.
2. mock called: `dr.call_count == 0`.

### PSM-DS-20 — the production form is foreign in development
- **Rules:** `destroy_saved_stamp_image` R4a [BUG-1865]
- **Kind:** bug
- **Expect:** xfail BUG-1865
- **Fails today on:** Then 1 (the call raises TypeError: no `user_id` parameter)

**When**
- `result = M.destroy_saved_stamp_image(IMG("profiles/5/stamp-" + TOKEN), user_id=5)`.

**Then**
1. returns: `result is None`.
2. mock called: `dr.call_count == 0`.

### PSM-DS-21 — the prefix compare is case-sensitive
- **Rules:** `destroy_saved_stamp_image` R4a [BUG-1865]
- **Kind:** bug
- **Expect:** xfail BUG-1865
- **Fails today on:** Then 1 (the call raises TypeError: no `user_id` parameter)

**When**
- `result = M.destroy_saved_stamp_image(IMG("Development/profiles/5/stamp-" + TOKEN), user_id=5)`.

**Then**
1. returns: `result is None`.
2. mock called: `dr.call_count == 0`.

### PSM-DS-22 — a leading space makes the id foreign
- **Rules:** `destroy_saved_stamp_image` R4a [BUG-1865]
- **Kind:** bug
- **Expect:** xfail BUG-1865
- **Fails today on:** Then 1 (the call raises TypeError: no `user_id` parameter)

**When**
- `result = M.destroy_saved_stamp_image(IMG(" " + OWN5), user_id=5)`.

**Then**
1. returns: `result is None`.
2. mock called: `dr.call_count == 0`.

### PSM-DS-23 — the own prefix in the middle of the id is foreign
- **Rules:** `destroy_saved_stamp_image` R4a [BUG-1865]
- **Kind:** bug
- **Expect:** xfail BUG-1865
- **Fails today on:** Then 1 (the call raises TypeError: no `user_id` parameter)

**When**
- `result = M.destroy_saved_stamp_image(IMG("ws-12/" + OWN5), user_id=5)`.

**Then**
1. returns: `result is None`.
2. mock called: `dr.call_count == 0`.

### PSM-DS-24 — the user's own folder but not a stamp file is foreign
- **Rules:** `destroy_saved_stamp_image` R4a [BUG-1865]
- **Kind:** bug
- **Expect:** xfail BUG-1865
- **Fails today on:** Then 1 (the call raises TypeError: no `user_id` parameter)

**When**
- `result = M.destroy_saved_stamp_image(IMG("development/profiles/5/avatar-" + TOKEN), user_id=5)`.

**Then**
1. returns: `result is None`.
2. mock called: `dr.call_count == 0`.

### PSM-DS-25 — `stamp` without the dash is foreign
- **Rules:** `destroy_saved_stamp_image` R4a [BUG-1865]
- **Kind:** bug
- **Expect:** xfail BUG-1865
- **Fails today on:** Then 1 (the call raises TypeError: no `user_id` parameter)

**When**
- `result = M.destroy_saved_stamp_image(IMG("development/profiles/5/stamp" + TOKEN), user_id=5)`.

**Then**
1. returns: `result is None`.
2. mock called: `dr.call_count == 0`.

### PSM-DS-26 — the bare prefix (empty token) is foreign
- **Rules:** `destroy_saved_stamp_image` R4a [BUG-1865]
- **Kind:** bug
- **Expect:** xfail BUG-1865
- **Fails today on:** Then 1 (the call raises TypeError: no `user_id` parameter)

**When**
- `result = M.destroy_saved_stamp_image(IMG(PRE5), user_id=5)`.

**Then**
1. returns: `result is None`.
2. mock called: `dr.call_count == 0`.

### PSM-DS-27 — a token of 31 hex characters is foreign
- **Rules:** `destroy_saved_stamp_image` R4a [BUG-1865]
- **Kind:** bug
- **Expect:** xfail BUG-1865
- **Fails today on:** Then 1 (the call raises TypeError: no `user_id` parameter)

**When**
- `result = M.destroy_saved_stamp_image(IMG(PRE5 + TOKEN31), user_id=5)`.

**Then**
1. returns: `result is None`.
2. mock called: `dr.call_count == 0`.

### PSM-DS-28 — a token of 33 hex characters is foreign
- **Rules:** `destroy_saved_stamp_image` R4a [BUG-1865]
- **Kind:** bug
- **Expect:** xfail BUG-1865
- **Fails today on:** Then 1 (the call raises TypeError: no `user_id` parameter)

**When**
- `result = M.destroy_saved_stamp_image(IMG(PRE5 + TOKEN33), user_id=5)`.

**Then**
1. returns: `result is None`.
2. mock called: `dr.call_count == 0`.

### PSM-DS-29 — an upper-case hex token is foreign
- **Rules:** `destroy_saved_stamp_image` R4a [BUG-1865]
- **Kind:** bug
- **Expect:** xfail BUG-1865
- **Fails today on:** Then 1 (the call raises TypeError: no `user_id` parameter)

**When**
- `result = M.destroy_saved_stamp_image(IMG(PRE5 + TOKENU), user_id=5)`.

**Then**
1. returns: `result is None`.
2. mock called: `dr.call_count == 0`.

### PSM-DS-30 — a 32-character token with a non-hex letter is foreign
- **Rules:** `destroy_saved_stamp_image` R4a [BUG-1865]
- **Kind:** bug
- **Expect:** xfail BUG-1865
- **Fails today on:** Then 1 (the call raises TypeError: no `user_id` parameter)

**When**
- `result = M.destroy_saved_stamp_image(IMG(PRE5 + TOKENG), user_id=5)`.

**Then**
1. returns: `result is None`.
2. mock called: `dr.call_count == 0`.

### PSM-DS-31 — a suffix `.png` after a valid token is foreign
- **Rules:** `destroy_saved_stamp_image` R4a [BUG-1865]
- **Kind:** bug
- **Expect:** xfail BUG-1865
- **Fails today on:** Then 1 (the call raises TypeError: no `user_id` parameter)

**When**
- `result = M.destroy_saved_stamp_image(IMG(OWN5 + ".png"), user_id=5)`.

**Then**
1. returns: `result is None`.
2. mock called: `dr.call_count == 0`.

### PSM-DS-32 — a suffix `/x` after a valid token is foreign
- **Rules:** `destroy_saved_stamp_image` R4a [BUG-1865]
- **Kind:** bug
- **Expect:** xfail BUG-1865
- **Fails today on:** Then 1 (the call raises TypeError: no `user_id` parameter)

**When**
- `result = M.destroy_saved_stamp_image(IMG(OWN5 + "/x"), user_id=5)`.

**Then**
1. returns: `result is None`.
2. mock called: `dr.call_count == 0`.

### PSM-DS-33 — a trailing newline after a valid token is foreign
- **Rules:** `destroy_saved_stamp_image` R4a [BUG-1865]
- **Kind:** bug
- **Expect:** xfail BUG-1865
- **Fails today on:** Then 1 (the call raises TypeError: no `user_id` parameter)

**When**
- `result = M.destroy_saved_stamp_image(IMG(OWN5 + "\n"), user_id=5)`.

**Then**
1. returns: `result is None`.
2. mock called: `dr.call_count == 0`.

## `ProfileStampManager.validate_saved_stamp_payload`

### PSM-VS-01 — None gives None
- **Rules:** `validate_saved_stamp_payload` R1
- **Kind:** boundary
- **Expect:** pass

**When**
- `result = M.validate_saved_stamp_payload(None)`.

**Then**
1. returns: `result is None`.

### PSM-VS-02 — a vector stamp is returned as its dump, unknown keys dropped
- **Rules:** `validate_saved_stamp_payload` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. `payload = {"kind": "vector", "extra": 1, "strokes": [{"color": "#000000", "width": 0.5, "points": [], "junk": "x"}], "viewBox": {"width": 100, "height": 50}}`.

**When**
- `result = M.validate_saved_stamp_payload(payload)`.

**Then**
1. returns: `result == VEC`.
2. mock called: `dr.call_count == 0`.

### PSM-VS-03 — strokes default to an empty list
- **Rules:** `validate_saved_stamp_payload` R2
- **Kind:** boundary
- **Expect:** pass

**When**
- `result = M.validate_saved_stamp_payload({"kind": "vector", "viewBox": {"width": 100, "height": 50}})`.

**Then**
1. returns: `result == {"kind": "vector", "strokes": [], "viewBox": {"width": 100, "height": 50}}`.

### PSM-VS-04 — a stroke width of exactly 1 is accepted
- **Rules:** `validate_saved_stamp_payload` R5 (boundary)
- **Kind:** boundary
- **Expect:** pass

**When**
- `result = M.validate_saved_stamp_payload({"kind": "vector", "strokes": [{"color": "#000000", "width": 1, "points": []}], "viewBox": {"width": 100, "height": 50}})`.

**Then**
1. returns: `result["strokes"][0]["width"] == 1`.

### PSM-VS-05 — an image stamp under the user's own prefix is returned with five keys, unknown keys dropped
- **Rules:** `validate_saved_stamp_payload` R3, R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. `payload = IMG(OWN5)`, then `payload["extra"] = 1`.

**When**
- `result = M.validate_saved_stamp_payload(payload)`.

**Then**
1. returns: `set(result) == {"kind", "public_id", "url", "width", "height"}`.
2. returns: `result["kind"] == "image"`, `result["public_id"] == OWN5`.
3. returns: `result["width"] == 10`, `result["height"] == 10`.
4. mock called: `dr.call_count == 0`.

### PSM-VS-06 — the image schema accepts a public_id of 512 characters
- **Rules:** `validate_saved_stamp_payload` R4 (schema limit)
- **Kind:** boundary
- **Expect:** pass

**When**
- `result = SavedStampImage(kind="image", public_id="a" * 512, url="https://x/a", width=10, height=10)` (target `schema`; the manager is not called).

**Then**
1. returns: `result.public_id == "a" * 512`.

### PSM-VS-07 — the image schema refuses a public_id of 513 characters
- **Rules:** `validate_saved_stamp_payload` R4, R5 (schema limit)
- **Kind:** boundary
- **Expect:** pass

**When**
- build `SavedStampImage(kind="image", public_id="a" * 513, url="https://x/a", width=10, height=10)` (target `schema`; the manager is not called).

**Then**
1. raises: `PydanticValidationError`.

### PSM-VS-08 — an empty public_id is refused by the schema
- **Rules:** `validate_saved_stamp_payload` R5, Errors row 3
- **Kind:** error
- **Expect:** pass

**When**
- `M.validate_saved_stamp_payload(IMG(""))`.

**Then**
1. raises: `PydanticValidationError`.

### PSM-VS-09 — width 0 is refused by the schema
- **Rules:** `validate_saved_stamp_payload` R4, R5
- **Kind:** error
- **Expect:** pass

**Given**
1. `payload = IMG(OWN5)`, then `payload["width"] = 0`.

**When**
- `M.validate_saved_stamp_payload(payload)`.

**Then**
1. raises: `PydanticValidationError`.

### PSM-VS-10 — a url of 2048 characters is accepted
- **Rules:** `validate_saved_stamp_payload` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `payload = IMG(OWN5)`, then `payload["url"] = "https://x/" + "a" * 2038` (2048 characters).

**When**
- `result = M.validate_saved_stamp_payload(payload)`.

**Then**
1. returns: `result["public_id"] == OWN5`.

### PSM-VS-11 — a url of 2049 characters is refused by the schema
- **Rules:** `validate_saved_stamp_payload` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `payload = IMG(OWN5)`, then `payload["url"] = "https://x/" + "a" * 2039` (2049 characters).

**When**
- `M.validate_saved_stamp_payload(payload)`.

**Then**
1. raises: `PydanticValidationError`.

### PSM-VS-12 — an empty url is refused by the schema
- **Rules:** `validate_saved_stamp_payload` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `payload = IMG(OWN5)`, then `payload["url"] = ""`.

**When**
- `M.validate_saved_stamp_payload(payload)`.

**Then**
1. raises: `PydanticValidationError`.

### PSM-VS-13 — height 0 is refused; width and height 1 are accepted
- **Rules:** `validate_saved_stamp_payload` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `ok = IMG(OWN5)`, then `ok["width"] = 1`, `ok["height"] = 1`.
2. `bad = IMG(OWN5)`, then `bad["height"] = 0`.
3. `accepted = M.validate_saved_stamp_payload(ok)`.

**When**
- `M.validate_saved_stamp_payload(bad)`.

**Then**
1. raises: `PydanticValidationError`.
2. returns: `accepted["width"] == 1`, `accepted["height"] == 1`.

### PSM-VS-14 — a vector without viewBox is refused by the schema
- **Rules:** `validate_saved_stamp_payload` R5
- **Kind:** error
- **Expect:** pass

**When**
- `M.validate_saved_stamp_payload({"kind": "vector", "strokes": []})`.

**Then**
1. raises: `PydanticValidationError`.

### PSM-VS-15 — a viewBox width of 0 is refused by the schema
- **Rules:** `validate_saved_stamp_payload` R5
- **Kind:** error
- **Expect:** pass

**When**
- `M.validate_saved_stamp_payload({"kind": "vector", "viewBox": {"width": 0, "height": 50}})`.

**Then**
1. raises: `PydanticValidationError`.

### PSM-VS-16 — a stroke width above 1 is refused by the schema
- **Rules:** `validate_saved_stamp_payload` R5
- **Kind:** boundary
- **Expect:** pass

**When**
- `M.validate_saved_stamp_payload({"kind": "vector", "strokes": [{"color": "#000000", "width": 1.5, "points": []}], "viewBox": {"width": 100, "height": 50}})`.

**Then**
1. raises: `PydanticValidationError`.

### PSM-VS-17 — a stroke width of 0 is refused by the schema
- **Rules:** `validate_saved_stamp_payload` R5
- **Kind:** boundary
- **Expect:** pass

**When**
- `M.validate_saved_stamp_payload({"kind": "vector", "strokes": [{"color": "#000000", "width": 0, "points": []}], "viewBox": {"width": 100, "height": 50}})`.

**Then**
1. raises: `PydanticValidationError`.

### PSM-VS-18 — an empty dict raises the kind error
- **Rules:** `validate_saved_stamp_payload` R6, Errors row 1
- **Kind:** error
- **Expect:** pass

**When**
- `M.validate_saved_stamp_payload({})`.

**Then**
1. raises: `ValueError`.
2. raises: `type(exc.value) is ValueError`.
3. raises: `str(exc.value) == KIND_MSG`.

### PSM-VS-19 — kind None, "" and "text" raise the kind error
- **Rules:** `validate_saved_stamp_payload` R6
- **Kind:** error
- **Expect:** pass

**When**
- for each `k` in `[None, "", "text"]`: `M.validate_saved_stamp_payload({"kind": k, "viewBox": {"width": 100, "height": 50}})`, each inside its own `pytest.raises(ValueError)`.

**Then**
1. raises: for every k, `type(exc.value) is ValueError`.
2. raises: for every k, `str(exc.value) == KIND_MSG`.

### PSM-VS-20 — kind is compared exactly: "Vector", "IMAGE" and " vector" raise the kind error
- **Rules:** `validate_saved_stamp_payload` R6
- **Kind:** boundary
- **Expect:** pass

**When**
- for each `k` in `["Vector", "IMAGE", " vector"]`: `M.validate_saved_stamp_payload({"kind": k, "public_id": OWN5, "url": "https://x/a", "width": 10, "height": 10, "viewBox": {"width": 100, "height": 50}})`, each inside its own `pytest.raises(ValueError)`.

**Then**
1. raises: for every k, `type(exc.value) is ValueError`.
2. raises: for every k, `str(exc.value) == KIND_MSG`.

### PSM-VS-21 — with the user's id, the user's own stamp is accepted
- **Rules:** `validate_saved_stamp_payload` R4, R4a [BUG-1864]
- **Kind:** bug
- **Expect:** xfail BUG-1864
- **Fails today on:** Then 1 (the call raises TypeError: no `user_id` parameter)

**When**
- `result = M.validate_saved_stamp_payload(IMG(OWN5), user_id=5)`.

**Then**
1. returns: `result["public_id"] == OWN5`.
2. returns: `result["kind"] == "image"`.

### PSM-VS-22 — another user's (higher id) stamp is refused
- **Rules:** `validate_saved_stamp_payload` R4a [BUG-1864], Errors row 2
- **Kind:** bug
- **Expect:** xfail BUG-1864
- **Fails today on:** Then 1 (the call raises TypeError: no `user_id` parameter)

**Given**
1. `payload = IMG("development/profiles/55/stamp-" + TOKEN)`.

**When**
- `M.validate_saved_stamp_payload(payload, user_id=5)`.

**Then**
1. raises: `ValueError`.
2. raises: `type(exc.value) is ValueError`.
3. raises: `str(exc.value) == FOREIGN_MSG`.
4. unchanged: payload kept.
5. mock called: `dr.call_count == 0`.

### PSM-VS-23 — a caller with a higher id cannot save the lower user's stamp
- **Rules:** `validate_saved_stamp_payload` R4a [BUG-1864]
- **Kind:** bug
- **Expect:** xfail BUG-1864
- **Fails today on:** Then 1 (the call raises TypeError: no `user_id` parameter)

**Given**
1. `payload = IMG(OWN5)`.

**When**
- `M.validate_saved_stamp_payload(payload, user_id=55)`.

**Then**
1. raises: `ValueError`.
2. raises: `type(exc.value) is ValueError`.
3. raises: `str(exc.value) == FOREIGN_MSG`.
4. unchanged: payload kept.

### PSM-VS-24 — the user's own folder but an avatar file is refused
- **Rules:** `validate_saved_stamp_payload` R4a [BUG-1864]
- **Kind:** bug
- **Expect:** xfail BUG-1864
- **Fails today on:** Then 1 (the call raises TypeError: no `user_id` parameter)

**Given**
1. `payload = IMG("development/profiles/5/avatar-" + TOKEN)`.

**When**
- `M.validate_saved_stamp_payload(payload, user_id=5)`.

**Then**
1. raises: `ValueError`.
2. raises: `type(exc.value) is ValueError`.
3. raises: `str(exc.value) == FOREIGN_MSG`.
4. unchanged: payload kept.

### PSM-VS-25 — the production form is refused in development
- **Rules:** `validate_saved_stamp_payload` R4a [BUG-1864]
- **Kind:** bug
- **Expect:** xfail BUG-1864
- **Fails today on:** Then 1 (the call raises TypeError: no `user_id` parameter)

**Given**
1. `payload = IMG("profiles/5/stamp-" + TOKEN)`.

**When**
- `M.validate_saved_stamp_payload(payload, user_id=5)`.

**Then**
1. raises: `ValueError`.
2. raises: `type(exc.value) is ValueError`.
3. raises: `str(exc.value) == FOREIGN_MSG`.
4. unchanged: payload kept.

### PSM-VS-26 — another environment's prefix is refused
- **Rules:** `validate_saved_stamp_payload` R4a [BUG-1864]
- **Kind:** bug
- **Expect:** xfail BUG-1864
- **Fails today on:** Then 1 (the call raises TypeError: no `user_id` parameter)

**Given**
1. `payload = IMG("production/profiles/5/stamp-" + TOKEN)`.

**When**
- `M.validate_saved_stamp_payload(payload, user_id=5)`.

**Then**
1. raises: `ValueError`.
2. raises: `type(exc.value) is ValueError`.
3. raises: `str(exc.value) == FOREIGN_MSG`.
4. unchanged: payload kept.

### PSM-VS-27 — an attachment's id is refused
- **Rules:** `validate_saved_stamp_payload` R4a [BUG-1864]
- **Kind:** bug
- **Expect:** xfail BUG-1864
- **Fails today on:** Then 1 (the call raises TypeError: no `user_id` parameter)

**Given**
1. `payload = IMG("ws-12/9f2c" + TOKEN)`.

**When**
- `M.validate_saved_stamp_payload(payload, user_id=5)`.

**Then**
1. raises: `ValueError`.
2. raises: `type(exc.value) is ValueError`.
3. raises: `str(exc.value) == FOREIGN_MSG`.
4. unchanged: payload kept.
5. mock called: `dr.call_count == 0`.

### PSM-VS-28 — the prefix compare is case-sensitive
- **Rules:** `validate_saved_stamp_payload` R4a [BUG-1864]
- **Kind:** bug
- **Expect:** xfail BUG-1864
- **Fails today on:** Then 1 (the call raises TypeError: no `user_id` parameter)

**Given**
1. `payload = IMG("Development/profiles/5/stamp-" + TOKEN)`.

**When**
- `M.validate_saved_stamp_payload(payload, user_id=5)`.

**Then**
1. raises: `ValueError`.
2. raises: `type(exc.value) is ValueError`.
3. raises: `str(exc.value) == FOREIGN_MSG`.
4. unchanged: payload kept.

### PSM-VS-29 — a leading space makes the id foreign
- **Rules:** `validate_saved_stamp_payload` R4a [BUG-1864]
- **Kind:** bug
- **Expect:** xfail BUG-1864
- **Fails today on:** Then 1 (the call raises TypeError: no `user_id` parameter)

**Given**
1. `payload = IMG(" " + OWN5)`.

**When**
- `M.validate_saved_stamp_payload(payload, user_id=5)`.

**Then**
1. raises: `ValueError`.
2. raises: `type(exc.value) is ValueError`.
3. raises: `str(exc.value) == FOREIGN_MSG`.
4. unchanged: payload kept.

### PSM-VS-30 — the own prefix in the middle of the id is refused
- **Rules:** `validate_saved_stamp_payload` R4a [BUG-1864]
- **Kind:** bug
- **Expect:** xfail BUG-1864
- **Fails today on:** Then 1 (the call raises TypeError: no `user_id` parameter)

**Given**
1. `payload = IMG("ws-12/" + OWN5)`.

**When**
- `M.validate_saved_stamp_payload(payload, user_id=5)`.

**Then**
1. raises: `ValueError`.
2. raises: `type(exc.value) is ValueError`.
3. raises: `str(exc.value) == FOREIGN_MSG`.
4. unchanged: payload kept.

### PSM-VS-31 — `stamp` without the dash is refused
- **Rules:** `validate_saved_stamp_payload` R4a [BUG-1864]
- **Kind:** bug
- **Expect:** xfail BUG-1864
- **Fails today on:** Then 1 (the call raises TypeError: no `user_id` parameter)

**Given**
1. `payload = IMG("development/profiles/5/stamp" + TOKEN)`.

**When**
- `M.validate_saved_stamp_payload(payload, user_id=5)`.

**Then**
1. raises: `ValueError`.
2. raises: `type(exc.value) is ValueError`.
3. raises: `str(exc.value) == FOREIGN_MSG`.
4. unchanged: payload kept.

### PSM-VS-32 — in production the bare form of the user's own id is accepted
- **Rules:** `validate_saved_stamp_payload` R4a [BUG-1864]
- **Kind:** bug
- **Expect:** xfail BUG-1864
- **Fails today on:** Then 1 (the call raises TypeError: no `user_id` parameter)

**Given**
1. settings: `CLOUDINARY_UPLOAD_ENV "production"`.

**When**
- `result = M.validate_saved_stamp_payload(IMG("profiles/5/stamp-" + TOKEN), user_id=5)`.

**Then**
1. returns: `result["public_id"] == "profiles/5/stamp-0123456789abcdef0123456789abcdef"`.

### PSM-VS-33 — in production the development form is refused
- **Rules:** `validate_saved_stamp_payload` R4a [BUG-1864]
- **Kind:** bug
- **Expect:** xfail BUG-1864
- **Fails today on:** Then 1 (the call raises TypeError: no `user_id` parameter)

**Given**
1. settings: `CLOUDINARY_UPLOAD_ENV "production"`.
2. `payload = IMG(OWN5)`.

**When**
- `M.validate_saved_stamp_payload(payload, user_id=5)`.

**Then**
1. raises: `ValueError`.
2. raises: `type(exc.value) is ValueError`.
3. raises: `str(exc.value) == FOREIGN_MSG`.
4. unchanged: payload kept.

### PSM-VS-34 — the prefix follows ENVIRONMENT when the upload environment is empty
- **Rules:** `validate_saved_stamp_payload` R4a [BUG-1864]
- **Kind:** bug
- **Expect:** xfail BUG-1864
- **Fails today on:** Then 1 (the call raises TypeError: no `user_id` parameter)

**Given**
1. settings: `CLOUDINARY_UPLOAD_ENV ""`.
2. settings: `ENVIRONMENT "staging"`.

**When**
- `result = M.validate_saved_stamp_payload(IMG("staging/profiles/5/stamp-" + TOKEN), user_id=5)`.

**Then**
1. returns: `result["public_id"] == "staging/profiles/5/stamp-0123456789abcdef0123456789abcdef"`.

### PSM-VS-35 — the server builds the url; the client's url is ignored
- **Rules:** `validate_saved_stamp_payload` R4b [BUG-1866]
- **Kind:** bug
- **Expect:** xfail BUG-1866
- **Fails today on:** Then 1 (the call raises TypeError: no `user_id` parameter)

**When**
- `result = M.validate_saved_stamp_payload(IMG(OWN5), user_id=5)`.

**Then**
1. returns: `result["url"].startswith("https://res.cloudinary.com/demo-cloud/image/authenticated/")`.
2. returns: `OWN5 in result["url"]`.
3. returns: `"tracker.example" not in result["url"]`.
4. returns: `result["public_id"] == OWN5`.

### PSM-VS-36 — the client's url on another Cloudinary account is ignored
- **Rules:** `validate_saved_stamp_payload` R4b [BUG-1866]
- **Kind:** bug
- **Expect:** xfail BUG-1866
- **Fails today on:** Then 1 (the call raises TypeError: no `user_id` parameter)

**Given**
1. `payload = IMG(OWN5)`, then `payload["url"] = "https://res.cloudinary.com/other-cloud/image/upload/x.png"`.

**When**
- `result = M.validate_saved_stamp_payload(payload, user_id=5)`.

**Then**
1. returns: `result["url"].startswith("https://res.cloudinary.com/demo-cloud/image/authenticated/")`.
2. returns: `OWN5 in result["url"]`.
3. returns: `"other-cloud" not in result["url"]`.
4. returns: `result["url"] != "https://res.cloudinary.com/other-cloud/image/upload/x.png"`.

### PSM-VS-37 — the client's url on our cloud but another file is ignored
- **Rules:** `validate_saved_stamp_payload` R4b [BUG-1866]
- **Kind:** bug
- **Expect:** xfail BUG-1866
- **Fails today on:** Then 1 (the call raises TypeError: no `user_id` parameter)

**Given**
1. `payload = IMG(OWN5)`, then `payload["url"] = "https://res.cloudinary.com/demo-cloud/image/upload/ws-12/9f2c.png"`.

**When**
- `result = M.validate_saved_stamp_payload(payload, user_id=5)`.

**Then**
1. returns: `result["url"].startswith("https://res.cloudinary.com/demo-cloud/image/authenticated/")`.
2. returns: `OWN5 in result["url"]`.
3. returns: `"ws-12" not in result["url"]`.
4. returns: `result["url"] != "https://res.cloudinary.com/demo-cloud/image/upload/ws-12/9f2c.png"`.

### PSM-VS-38 — the bare prefix (empty token) is refused
- **Rules:** `validate_saved_stamp_payload` R4a [BUG-1864], Errors row 2
- **Kind:** bug
- **Expect:** xfail BUG-1864
- **Fails today on:** Then 1 (the call raises TypeError: no `user_id` parameter)

**Given**
1. `payload = IMG(PRE5)`.

**When**
- `M.validate_saved_stamp_payload(payload, user_id=5)`.

**Then**
1. raises: `ValueError`.
2. raises: `type(exc.value) is ValueError`.
3. raises: `str(exc.value) == FOREIGN_MSG`.
4. unchanged: payload kept.

### PSM-VS-39 — a token of 31 hex characters is refused
- **Rules:** `validate_saved_stamp_payload` R4a [BUG-1864], Errors row 2
- **Kind:** bug
- **Expect:** xfail BUG-1864
- **Fails today on:** Then 1 (the call raises TypeError: no `user_id` parameter)

**Given**
1. `payload = IMG(PRE5 + TOKEN31)`.

**When**
- `M.validate_saved_stamp_payload(payload, user_id=5)`.

**Then**
1. raises: `ValueError`.
2. raises: `type(exc.value) is ValueError`.
3. raises: `str(exc.value) == FOREIGN_MSG`.
4. unchanged: payload kept.

### PSM-VS-40 — a token of 33 hex characters is refused
- **Rules:** `validate_saved_stamp_payload` R4a [BUG-1864], Errors row 2
- **Kind:** bug
- **Expect:** xfail BUG-1864
- **Fails today on:** Then 1 (the call raises TypeError: no `user_id` parameter)

**Given**
1. `payload = IMG(PRE5 + TOKEN33)`.

**When**
- `M.validate_saved_stamp_payload(payload, user_id=5)`.

**Then**
1. raises: `ValueError`.
2. raises: `type(exc.value) is ValueError`.
3. raises: `str(exc.value) == FOREIGN_MSG`.
4. unchanged: payload kept.

### PSM-VS-41 — an upper-case hex token is refused
- **Rules:** `validate_saved_stamp_payload` R4a [BUG-1864], Errors row 2
- **Kind:** bug
- **Expect:** xfail BUG-1864
- **Fails today on:** Then 1 (the call raises TypeError: no `user_id` parameter)

**Given**
1. `payload = IMG(PRE5 + TOKENU)`.

**When**
- `M.validate_saved_stamp_payload(payload, user_id=5)`.

**Then**
1. raises: `ValueError`.
2. raises: `type(exc.value) is ValueError`.
3. raises: `str(exc.value) == FOREIGN_MSG`.
4. unchanged: payload kept.

### PSM-VS-42 — a 32-character token with a non-hex letter is refused
- **Rules:** `validate_saved_stamp_payload` R4a [BUG-1864], Errors row 2
- **Kind:** bug
- **Expect:** xfail BUG-1864
- **Fails today on:** Then 1 (the call raises TypeError: no `user_id` parameter)

**Given**
1. `payload = IMG(PRE5 + TOKENG)`.

**When**
- `M.validate_saved_stamp_payload(payload, user_id=5)`.

**Then**
1. raises: `ValueError`.
2. raises: `type(exc.value) is ValueError`.
3. raises: `str(exc.value) == FOREIGN_MSG`.
4. unchanged: payload kept.

### PSM-VS-43 — a suffix `.png` after a valid token is refused
- **Rules:** `validate_saved_stamp_payload` R4a [BUG-1864], Errors row 2
- **Kind:** bug
- **Expect:** xfail BUG-1864
- **Fails today on:** Then 1 (the call raises TypeError: no `user_id` parameter)

**Given**
1. `payload = IMG(OWN5 + ".png")`.

**When**
- `M.validate_saved_stamp_payload(payload, user_id=5)`.

**Then**
1. raises: `ValueError`.
2. raises: `type(exc.value) is ValueError`.
3. raises: `str(exc.value) == FOREIGN_MSG`.
4. unchanged: payload kept.

### PSM-VS-44 — a suffix `/x` after a valid token is refused
- **Rules:** `validate_saved_stamp_payload` R4a [BUG-1864], Errors row 2
- **Kind:** bug
- **Expect:** xfail BUG-1864
- **Fails today on:** Then 1 (the call raises TypeError: no `user_id` parameter)

**Given**
1. `payload = IMG(OWN5 + "/x")`.

**When**
- `M.validate_saved_stamp_payload(payload, user_id=5)`.

**Then**
1. raises: `ValueError`.
2. raises: `type(exc.value) is ValueError`.
3. raises: `str(exc.value) == FOREIGN_MSG`.
4. unchanged: payload kept.

### PSM-VS-45 — a trailing newline after a valid token is refused
- **Rules:** `validate_saved_stamp_payload` R4a [BUG-1864], Errors row 2
- **Kind:** bug
- **Expect:** xfail BUG-1864
- **Fails today on:** Then 1 (the call raises TypeError: no `user_id` parameter)

**Given**
1. `payload = IMG(OWN5 + "\n")`.

**When**
- `M.validate_saved_stamp_payload(payload, user_id=5)`.

**Then**
1. raises: `ValueError`.
2. raises: `type(exc.value) is ValueError`.
3. raises: `str(exc.value) == FOREIGN_MSG`.
4. unchanged: payload kept.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| FU-1 (a): the current user's id reaches `validate_saved_stamp_payload` / `destroy_saved_stamp_image`; a refused stamp answers 400, nothing saved | `AuthService.update_current_user` | `PATCH /auth/me/` with a foreign `public_id` → 400, profile unchanged; removing a stored foreign stamp clears it without a Cloudinary delete |
| Endpoint translation: `CloudinaryNotConfiguredError` → 503, `ValueError` → 400 | `POST /auth/me/stamp-image/sign`, `PATCH /auth/me/` | integration-only per the spec |

## Spec gaps
| # | Where | What is missing | How it blocked the design |
|---|---|---|---|
| 1 | `validate_saved_stamp_payload` R2 | The fields of a stroke's `points` entries, so "unknown keys dropped inside points" cannot be given a concrete point | Not carded; strokes use `points: []`. The describer should give a valid point (e.g. its keys). |
| 2 | R4 vs R4b [BUG-1866] | **Closed (Revision 3):** the spec (validator R4b) keeps the client `url` required (1–2048 characters) and ignores its value | VS-10, VS-11, VS-12 stand as written. |
| 3 | R4a [BUG-1864] | **Closed (Revision 2):** the spec (revision 2026-11-04) requires exactly the prefix plus 32 lowercase hex characters | Carded: VS-38 … VS-44, DS-26 … DS-32. |

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `build_stamp_public_id` | R1 | PSM-PI-03, PSM-PI-04 |
| `build_stamp_public_id` | R2 | PSM-PI-02, PSM-PI-03 |
| `build_stamp_public_id` | R3 | PSM-PI-01, PSM-PI-05, PSM-PI-06 |
| `build_stamp_public_id` | R4 | PSM-PI-07 |
| `build_stamp_asset_folder` | R1 | PSM-AF-01, PSM-AF-02, PSM-AF-03, PSM-AF-04 |
| `build_stamp_asset_folder` | R2 | PSM-AF-05, PSM-AF-06, PSM-AF-07 |
| `build_stamp_asset_folder` | R3 | PSM-AF-08, PSM-AF-09, PSM-AF-10 |
| `build_stamp_asset_folder` | Errors (None) | PSM-AF-11 |
| `sign_stamp_image_upload` | R1, Errors row 1 | PSM-SG-01, PSM-SG-02 |
| `sign_stamp_image_upload` | R2, Errors row 2 | PSM-SG-03 |
| `sign_stamp_image_upload` | R3 | PSM-SG-04 |
| `sign_stamp_image_upload` | R4 | PSM-SG-05, PSM-SG-06 |
| `sign_stamp_image_upload` | R5 | PSM-SG-07 |
| `destroy_saved_stamp_image` | R1 | PSM-DS-01, PSM-DS-02 |
| `destroy_saved_stamp_image` | R2 | PSM-DS-03, PSM-DS-04, PSM-DS-05 |
| `destroy_saved_stamp_image` | R3 | PSM-DS-06, PSM-DS-07, PSM-DS-08 |
| `destroy_saved_stamp_image` | R4 | PSM-DS-09; with `user_id` PSM-DS-16 |
| `destroy_saved_stamp_image` | R4a [BUG-1865] | PSM-DS-17 … PSM-DS-33 |
| `destroy_saved_stamp_image` | R5 | PSM-DS-10, PSM-DS-11, PSM-DS-12 |
| `destroy_saved_stamp_image` | R5a [BUG-1713] | PSM-DS-13; no warning PSM-DS-12, PSM-DS-14 |
| `destroy_saved_stamp_image` | R6 | PSM-DS-15 |
| `validate_saved_stamp_payload` | R1 | PSM-VS-01 |
| `validate_saved_stamp_payload` | R2 | PSM-VS-02, PSM-VS-03, PSM-VS-04 (points: gap 1) |
| `validate_saved_stamp_payload` | R3 | PSM-VS-05 |
| `validate_saved_stamp_payload` | R4 | PSM-VS-05, PSM-VS-06, PSM-VS-07, PSM-VS-09 … PSM-VS-13 |
| `validate_saved_stamp_payload` | R4a [BUG-1864], Errors row 2 | PSM-VS-21 … PSM-VS-34, PSM-VS-38 … PSM-VS-45 |
| `validate_saved_stamp_payload` | R4b [BUG-1866] | PSM-VS-35, PSM-VS-36, PSM-VS-37 |
| `validate_saved_stamp_payload` | R5, Errors row 3 | PSM-VS-07, PSM-VS-08, PSM-VS-09, PSM-VS-14 … PSM-VS-17 |
| `validate_saved_stamp_payload` | R6, Errors row 1 | PSM-VS-18, PSM-VS-19, PSM-VS-20 |
