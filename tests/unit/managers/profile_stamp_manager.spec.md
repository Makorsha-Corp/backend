# Spec — `app/managers/profile_stamp_manager.py`

> **Status:** APPROVED (Q1, Q2 answered by the owner (2026-11-04) as OQ-11, OQ-12: BUG-1864, BUG-1865, BUG-1866; Q3 resolved as BUG-1713). Nothing else is open.
> **Source commit:** e48a092
> **Revision 2026-11-04 (verification R2-2, wording):** `destroy_saved_stamp_image` R4 and `validate_saved_stamp_payload` R4 now say "exact minted form" (prefix + exactly 32 lowercase hex, matched in full) instead of "under the user's own stamp prefix"; R4a adds that a trailing newline or any other character after the token is refused.
> **Revision 2026-11-04 (cases gap 2):** `validate_saved_stamp_payload` R4b — the client's `url` stays in the schema, required and 1–2048 characters as today; the server ignores its value and stores the url it builds (BUG-1866). Decided by Claude under the reviewer's delegation (2026-11-04), so today's web app does not break.
> **Revision 2026-11-04 (verification gap, `profile_stamp_manager.verify.md` finding 3 / cases gap 3):** following the owner's OQ-11 answer, an accepted (and deletable) image `public_id` must be **exactly the minted form**: the user's own stamp prefix followed by the token `build_stamp_public_id` mints, `uuid.uuid4().hex` = exactly 32 lowercase hex characters (`[0-9a-f]{32}`). The bare prefix, a shorter / longer / upper-case / non-hex token, or anything after the token is refused (validator) or never deleted (destroy). `validate_saved_stamp_payload` R4a, `destroy_saved_stamp_image` R4a and the BUG-1864 / BUG-1865 rows updated. Decided by Claude under the reviewer's delegation (2026-11-04). Stays APPROVED.

> **Below:** `tests/unit/core/cloudinary_client.spec.md` (APPROVED; `generate_upload_signature`, `destroy_resource`, `_ensure_configured`), `app/schemas/saved_stamp.py`, `tests/unit/core/config.spec.md` (`CLOUDINARY_UPLOAD_ENV`, `ENVIRONMENT`). **Above:** `POST /auth/me/stamp-image/sign` (`sign_stamp_image_upload`; `CloudinaryNotConfiguredError` → 503) and `AuthService.update_current_user` ← `PATCH /auth/me/` (`validate_saved_stamp_payload`, `destroy_saved_stamp_image`; a `ValueError`, Pydantic's included, → 400 at the endpoint).
>
> **Read, not run.** No database is involved; every rule follows from the code and the cloudinary client spec.

## Review
> All questions answered.

Checked and **not** violated: **HR-1 … HR-9** — no name, list, search or audit stamp (the asset folder comes from the profile name, which this module only reads). **HR-10** — no state check. **HR-11, HR-12** — nothing is verified with Cloudinary and no money is involved. **HR-13** — the upload is signed, not started, here; the delete is a cleanup (Q3). **HR-14** — no batch. **HR-15** — no money. **HR-16** — a stamp belongs to a person (profiles are global), not to a workspace; the access side is Q1.

### New questions

### Q1. OWNER — Removing your stamp can delete any image file the company stores in Cloudinary — 🐞 BUG-1864, BUG-1865 (answered by the owner (2026-11-04), OQ-11)
**Background:** A user's "saved stamp" is a small picture they place on attachment markups. To upload one, the app asks the server to sign an upload; the server picks the file's name in Cloudinary (`profiles/<user id>/stamp-<random>`). The browser then saves the stamp to the profile by sending `{"kind": "image", "public_id": …, "url": …, "width": …, "height": …}`. The server checks only that `public_id` is 1–512 characters; it does not check that it is the name it signed for this user. When the user later removes or replaces the stamp, the server deletes the stored `public_id` from Cloudinary, as an authenticated image. Attachment images are stored the same way, and the attachment API shows their `public_id` to every member of the workspace.
**What happens today:** Any logged-in user can save a stamp whose `public_id` is another file's name, then remove the stamp: the server deletes that file from Cloudinary. No workspace role or attachment permission is checked.
**Example:** A ground-team member opens an invoice photo in workspace A and copies its `public_id` `ws-12/9f2c…`. They send `PATCH /auth/me/` with that id as their stamp, then `PATCH /auth/me/` with `saved_stamp: null`. The invoice photo is gone from Cloudinary; the attachment row stays and shows a broken image for everyone.
**Rules affected:** `validate_saved_stamp_payload` R4; `destroy_saved_stamp_image` R4
**Suggested answer:** `bug — an image stamp is accepted only if its public_id is one this server signs for this user (it starts with the user's own stamp prefix, profiles/<user id>/stamp-, with the environment prefix outside production); anything else is refused with 400 "saved_stamp.public_id is not a stamp of this user" and nothing is saved. destroy_saved_stamp_image deletes only such a public_id and ignores any other, so stamps already stored with a foreign id can be removed without deleting the foreign file.`
**Alternatives:** (a) also keep a list of signed ids per user and accept only those (stricter, needs storage). (b) never delete from Cloudinary on removal; clean up with a periodic job instead.
**Answer:** bug — the suggested answer: an image stamp is accepted only if its `public_id` starts with the user's own `profiles/<user id>/stamp-` prefix (with the environment prefix outside production), otherwise 400 and nothing saved; the delete only ever touches such a `public_id` (answered by the owner (2026-11-04), OQ-11).
**Resolution:** 🐞 BUG-1864 (`validate_saved_stamp_payload` R4a: a foreign `public_id` is refused) and 🐞 BUG-1865 (`destroy_saved_stamp_image` R4a: a foreign `public_id` is never deleted), pattern `unverified-client-file-reference`. Both need the user's id passed in (new parameter). Rules: `validate_saved_stamp_payload` R4, R4a; `destroy_saved_stamp_image` R4, R4a.

### Q2. OWNER — A stamp picture can point at any web address, and other members' screens load it — 🐞 BUG-1866 (answered by the owner (2026-11-04), OQ-12)
**Background:** The stamp's `url` is stored as sent: any text of 1–2048 characters, not checked to be a Cloudinary address or to match `public_id`. When anyone lists the markups of an attachment, each author's saved stamp, `url` included, is sent with them (`AttachmentMarkupManager._resolve_saved_stamp`), so the web app shows it to every member who opens that attachment.
**What happens today:** A user can set their stamp's `url` to an image on any server. Every colleague who opens an attachment that user marked up loads that address, which tells the other server their IP address and when they looked.
**Example:** A user saves `{"kind": "image", "public_id": "x", "url": "https://tracker.example/p.png", "width": 10, "height": 10}`. A manager opens a drawing the user marked up; the manager's browser fetches `https://tracker.example/p.png`.
**Rules affected:** `validate_saved_stamp_payload` R4
**Suggested answer:** `bug — the server does not take url from the client: it builds it from the accepted public_id (the Cloudinary delivery address for this cloud, authenticated, as attachments do), or refuses a url that is not https://res.cloudinary.com/<our cloud>/… for that public_id with 400.`
**Alternatives:** (a) intended — stamps are personal and the risk is small. (b) only require `https://res.cloudinary.com/<our cloud>/` as the start, without matching the public id.
**Answer:** bug — the server builds the stamp's `url` from the accepted `public_id` (our authenticated Cloudinary delivery address, as attachments do) and ignores the `url` the client sends (the suggested answer, first form; answered by the owner (2026-11-04), OQ-12).
**Resolution:** 🐞 BUG-1866 (pattern `derived-value-accepted-from-client`, per BUG-627). Rules: `validate_saved_stamp_payload` R4b. Stamps already stored keep their old `url` until saved again (FU-1).

### Q3. A failed delete of the old stamp picture is silently ignored — 🐞 BUG-1713
**Background:** When a user removes or replaces an image stamp, the server asks Cloudinary to delete the old file. If that call fails for any reason (Cloudinary down, credentials missing, network), the error is swallowed with no log line, and the profile change goes ahead.
**What happens today:** The profile change succeeds; the old file stays in Cloudinary and nothing records that it was left behind.
**Example:** Cloudinary has an outage while 200 users replace their stamps. All 200 saves succeed; 200 old files stay in Cloudinary forever and no log shows which.
**Rules affected:** `destroy_saved_stamp_image` R5
**Suggested answer:** `bug — the profile change still goes ahead, but the failure is logged as a warning with the public_id and the error, so orphaned files can be found and removed.` Alternative: `intended` — orphaned stamp files are tiny and rare.
**Answer:** bug — as suggested (decided by Claude under the reviewer's delegation (2026-11-04))
**Resolution:** the profile change still succeeds and the method still returns `None`, but a failed delete is logged as a WARNING naming the `public_id` (and the error). Rules: `destroy_saved_stamp_image` R5 (split: R5 swallowing, R5a [BUG-1713] the warning).

## Follow-ups for other reviews
> Nothing below is a rule of this manager and no bug is logged for it here.

| # | Where it must be looked at | What | Came from |
|---|---|---|---|
| FU-1 | **Auth service** (`AuthService.update_current_user`, not yet specified) and **attachment markup manager** (`_resolve_saved_stamp`) | (a) The service must pass the current user's id to `validate_saved_stamp_payload` and `destroy_saved_stamp_image` (BUG-1864, BUG-1865), and a refused stamp answers 400 with nothing saved. (b) Stamps already stored keep a client-sent `url` and possibly a foreign `public_id` until saved again; whether old rows are repaired (url rebuilt, foreign stamps cleared) belongs to the fix of BUG-1866 / BUG-1864, not to this module. | Q1, Q2 |

## Overview
`ProfileStampManager` handles the image half of a user's saved stamp: it signs a direct browser upload to Cloudinary for a new stamp picture, checks the stamp payload a user saves on their profile (vector drawing or uploaded image), and deletes the old picture from Cloudinary when a stamp is removed or replaced. It has no database access and no state. Callers: the auth endpoint (sign) and `AuthService.update_current_user` (validate, destroy). It is meant to keep stamp uploads in the right place in Cloudinary and stored stamps well-formed.

**Callables:** 5 specified · 2 not specified
**Externals to mock:** Cloudinary (`destroy_resource`, patched as `app.managers.profile_stamp_manager.destroy_resource`; `generate_upload_signature` may run for real with credentials set, or be patched as `app.managers.profile_stamp_manager.generate_upload_signature`); the clock (`app.managers.profile_stamp_manager.time.time`); `uuid.uuid4` (`app.managers.profile_stamp_manager.uuid.uuid4`); settings (`monkeypatch.setattr(settings, …)` on `app.core.config.settings`).
**Integration-only behavior:** the endpoint's 503 for `CloudinaryNotConfiguredError` and 400 for `ValueError`.

**Facts for the test designer**
- Import: `from app.managers.profile_stamp_manager import ProfileStampManager, profile_stamp_manager`. No constructor arguments. `build_stamp_public_id` and `build_stamp_asset_folder` take keyword-only arguments.
- `AUTHENTICATED_DELIVERY_TYPE` is `"authenticated"`. `CloudinaryNotConfiguredError` subclasses `RuntimeError`.
- Settings read at call time: `CLOUDINARY_UPLOAD_ENV` (default `"development"`), `ENVIRONMENT` (default `"development"`), `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, `CLOUDINARY_API_SECRET` (default `""`).
- `user` may be any object with `id` and `name` (`types.SimpleNamespace`); no database needed.
- **BUG-1864, BUG-1865, BUG-1866** (owner, Q1/Q2): the user's id is a new parameter of `validate_saved_stamp_payload` and `destroy_saved_stamp_image`; call it by keyword (`user_id=`). Until the fix the call with that keyword raises `TypeError`, so these cases are **strict** xfail (`raises` not narrowed). Set `CLOUDINARY_UPLOAD_ENV` explicitly (e.g. `"development"`) and, for BUG-1866, `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, `CLOUDINARY_API_SECRET` non-empty; the behaviour with Cloudinary unconfigured is not specified by OQ-12 and gets no case. Cases that pass today (R1–R3, R5, R6 of the validator; R1–R3, R5, R5a of the delete, with a `public_id` under the user's own prefix) keep calling without the new parameter today; the fix of BUG-1864 / BUG-1865 adds `user_id=` to those calls when it makes the parameter required.
- Schemas: `SavedStampVector(kind="vector", strokes: list[MarkupStroke] = [], viewBox: {width > 0, height > 0})`; `SavedStampImage(kind="image", public_id: 1–512 chars, url: 1–2048 chars, width: int > 0, height: int > 0)`; `MarkupStroke(color: 1–32 chars, width: 0 < w <= 1, points: list = [])`. Unknown keys are dropped (Pydantic default).

## Not specified
- `ProfileStampManager._upload_env` — one expression; its effect is stated in `build_stamp_public_id` R1–R3 and `build_stamp_asset_folder` R3
- `profile_stamp_manager` — module-level singleton, no logic

---

## `ProfileStampManager.build_stamp_public_id(*, user_id)`
**Shape:** helper
**Persistence:** pure
**Visibility:** public (used by: `sign_stamp_image_upload`)

**Purpose:** The Cloudinary file name for a new stamp picture.

**Returns:** a `str`.

**Rules:**
- **R1.** The upload environment is `CLOUDINARY_UPLOAD_ENV` when it is non-empty, else `ENVIRONMENT`.
- **R2.** In the `"production"` environment: `profiles/<user_id>/stamp-<token>`, where `<token>` is `uuid4().hex` (32 lowercase hex characters).
- **R3.** In any other environment `<env>`: `<env>/profiles/<user_id>/stamp-<token>` (e.g. `development/profiles/5/stamp-<token>`). The comparison is exact: `"Production"` is not production. Both settings empty → `"/profiles/5/stamp-<token>"`.
- **R4.** Each call gives a new token.

**Errors:** none. **Side effects:** none

---

## `ProfileStampManager.build_stamp_asset_folder(*, user_name, user_id)`
**Shape:** helper
**Persistence:** pure
**Visibility:** public (used by: `sign_stamp_image_upload`)

**Purpose:** The human-readable Cloudinary Media Library folder for a user's stamps.

**Returns:** a `str`.

**Rules:**
- **R1.** The name has every `/` and `\` replaced by `-`, then outer whitespace removed: `"Ann / Lee"` → `"Ann - Lee"`, `" Ann "` → `"Ann"`. Nothing else is changed (case, inner spaces, other characters kept).
- **R2.** A name that is empty after R1 (`""`, `"   "`) becomes `user-<user_id>`. A name of only slashes is not empty (`"//"` → `"--"`).
- **R3.** Production (as `build_stamp_public_id` R1): `Profile stamps/<name>`; any other environment: `Dev/Profile stamps/<name>` (the prefix is `Dev`, whatever the environment's name).

**Errors:** `user_name` `None` raises `AttributeError` (`profiles.name` is NOT NULL, so no caller passes it). **Side effects:** none

---

## `ProfileStampManager.sign_stamp_image_upload(user)`
**Shape:** compute
**Persistence:** pure (no database; no network)
**Visibility:** public (used by: `POST /auth/me/stamp-image/sign`)

**Purpose:** Signed parameters the browser uses to upload a stamp picture straight to Cloudinary.

**Returns:** a `StampImageSignResponse`.

**Rules:**
- **R1.** `CLOUDINARY_CLOUD_NAME` or `CLOUDINARY_API_KEY` empty → `CloudinaryNotConfiguredError("Cloudinary cloud name and API key are required.")`, nothing signed.
- **R2.** Both set but `CLOUDINARY_API_SECRET` empty → `CloudinaryNotConfiguredError` from the client, with its own message (cloudinary client spec `_ensure_configured` R1).
- **R3.** Otherwise the response holds: `cloud_name` and `api_key` from settings; `timestamp` = `int(time.time())`; `public_id` per `build_stamp_public_id` for `user.id`; `asset_folder` per `build_stamp_asset_folder` for `user.name`, `user.id`; `display_name` `"saved-stamp"`; `type` `"authenticated"`; `resource_type` `"image"`; `upload_url` `https://api.cloudinary.com/v1_1/<cloud_name>/image/upload`.
- **R4.** `signature` is `generate_upload_signature` of exactly that `public_id`, `asset_folder`, `display_name`, `timestamp` and delivery type `authenticated` (cloudinary client spec R2): signing the response's own fields with the secret gives the same value.
- **R5.** Two calls give different `public_id`s (R4 of `build_stamp_public_id`). Nothing is stored; the user is not changed.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| cloud name or API key empty | `CloudinaryNotConfiguredError` | `Cloudinary cloud name and API key are required.` |
| API secret empty | `CloudinaryNotConfiguredError` | the client's message |

**Side effects:** none (the client sets the SDK's global config on success).

---

## `ProfileStampManager.destroy_saved_stamp_image(saved_stamp)`
**Shape:** delete
**Persistence:** writes (Cloudinary)
**Visibility:** public (used by: `AuthService.update_current_user`, on removing a stamp and on replacing an image stamp with a different `public_id`)

**Purpose:** Delete the picture of an image stamp from Cloudinary, best effort.

**Inputs:** `saved_stamp` — the stamp as stored on the profile (`dict`), or `None`.

**Returns:** `None`, always.

**Rules:**
- **R1.** `None` or `{}` → nothing is deleted.
- **R2.** A stamp whose `kind` is not exactly `"image"` (a vector stamp, `kind` missing, `"IMAGE"`) → nothing is deleted.
- **R3.** An image stamp whose `public_id` is missing, `None` or `""` → nothing is deleted.
- **R4.** Otherwise, for a `public_id` of the exact minted form (the user's own stamp prefix followed by exactly 32 lowercase hex characters, the whole `public_id` matched in full, as `validate_saved_stamp_payload` R4a; revision R2-2, 2026-11-04), Cloudinary is asked to delete that `public_id` as resource type `image`, delivery type `authenticated` (client `destroy_resource` R2, R3).
- **R4a.** [BUG-1865] (Q1, owner) A `public_id` that is not exactly the minted form of `validate_saved_stamp_payload` R4a — the user's own stamp prefix followed by exactly 32 lowercase hex characters and nothing else (another user's stamp, an attachment's `ws-12/9f2c…`, the production form in a non-production environment, the bare prefix, a token of 31 or 33 characters, upper-case or non-hex, or anything after the token; revision 2026-11-04) — is never deleted: Cloudinary is not called, the method returns `None` and raises nothing, so the caller can still remove such a stamp from the profile. *(Today: any `public_id` is deleted. Requires a new parameter for the user's id, e.g. `user_id`; read, not run.)* Whether a log line is written for a skipped foreign id is not specified (no case asserts it).
- **R5.** Any error of that call (`CloudinaryNotConfiguredError`, an SDK or network error) is swallowed: the method returns `None` and raises nothing, so the caller's profile change goes ahead. A `"not found"` answer is not an error either.
- **R5a.** [BUG-1713] When that call raises, one WARNING log record is emitted whose message contains the `public_id` and the error; a successful call (a `"not found"` answer included) logs no warning. *(Today: nothing is logged. Requires a module logger, `logging.getLogger(__name__)`, i.e. `app.managers.profile_stamp_manager`; assert with `caplog` at WARNING.)*
- **R6.** A non-dict value raises `AttributeError` (not reachable: stored stamps come from `validate_saved_stamp_payload`).

**Errors:** none raised for Cloudinary failures (R5). **Side effects:** at most one Cloudinary delete; on its failure, one WARNING log record (R5a, BUG-1713).

---

## `ProfileStampManager.validate_saved_stamp_payload(payload)`
**Shape:** validator
**Persistence:** pure
**Visibility:** public (used by: `AuthService.update_current_user`, for a non-`null` `saved_stamp`)

**Purpose:** Check a stamp a user wants to save and return its clean form.

**Inputs:** `payload` — `dict` or `None`.

**Returns:** the normalised `dict`, or `None`.

**Rules:**
- **R1.** `None` → `None`.
- **R2.** `kind` exactly `"vector"` → validated as `SavedStampVector` and returned as its dump: `{"kind": "vector", "strokes": [...], "viewBox": {"width", "height"}}`; `strokes` defaults to `[]`; unknown keys are dropped (at the top level and inside strokes and points).
- **R3.** `kind` exactly `"image"` → validated as `SavedStampImage` and returned as `{"kind": "image", "public_id", "url", "width", "height"}`, unknown keys dropped.
- **R4.** For an image, `public_id` must be 1–512 characters and `url` 1–2048 characters (schema); `width` and `height` must be integers above 0. An image stamp whose `public_id` is of the exact minted form — the user's own stamp prefix followed by exactly 32 lowercase hex characters, matched in full (R4a; revision R2-2, 2026-11-04) — is accepted.
- **R4a.** [BUG-1864] (Q1, owner) The `public_id` must start with the user's own stamp prefix, the prefix `build_stamp_public_id` gives that user in the current environment (its R1–R3): `profiles/<user_id>/stamp-` in production, `<env>/profiles/<user_id>/stamp-` elsewhere (e.g. `development/profiles/5/stamp-` for user 5). The prefix must be followed by **exactly the minted token**: 32 lowercase hex characters (`uuid.uuid4().hex`), and nothing after it — the whole `public_id` matches `<prefix>[0-9a-f]{32}` in full: a trailing newline (`…<32 hex>
`), a trailing space or any other character after the token is refused (a `$`-anchored regex that tolerates a final newline is not enough; use a full match) (revision 2026-11-04, decided by Claude under the reviewer's delegation (2026-11-04) following OQ-11). The comparison is exact and case-sensitive. Anything else → `ValueError("saved_stamp.public_id is not a stamp of this user")` (400 at the endpoint), nothing returned to save. Examples for user 5 in `development`: `development/profiles/5/stamp-<32 lowercase hex>` accepted; `development/profiles/55/stamp-<hex>` (another user), `development/profiles/5/avatar-<hex>`, `profiles/5/stamp-<hex>` (production form), `production/profiles/5/stamp-<hex>`, `ws-12/9f2c…` (an attachment) all refused; so are `development/profiles/5/stamp-` (empty token), `development/profiles/5/stamp-<31 hex>`, `…/stamp-<33 hex>`, `…/stamp-<32 upper-case hex>`, `…/stamp-<32 chars with a non-hex letter>`, `…/stamp-<32 hex>/x` and `…/stamp-<32 hex>.png` (a suffix). *(Today: any text of 1–512 characters is accepted. Requires a new parameter for the user's id, e.g. `user_id`; read, not run.)*
- **R4b.** [BUG-1866] (Q2, owner) The returned `url` is built by the server from the accepted `public_id`: the authenticated Cloudinary delivery address of this cloud (as attachments build theirs, `build_signed_delivery_url`), i.e. it starts with `https://res.cloudinary.com/<CLOUDINARY_CLOUD_NAME>/image/authenticated/` and contains the `public_id`. The `url` the client sent is ignored: `"https://tracker.example/p.png"` never appears in the result. The field itself stays in the schema as today — required, 1–2048 characters — so today's web app keeps working: a missing or over-long `url` is still refused by the schema (R4), any valid value is accepted and then replaced (cases gap 2; decided by Claude under the reviewer's delegation (2026-11-04)). The exact remainder (signature, version, format) is the fix's choice and is not asserted. *(Today: the client's `url` is returned as sent; read, not run.)*
- **R5.** A payload that breaks its schema (`viewBox` missing or with a size of 0; a stroke `width` above 1; image `width` 0; `public_id` `""`) → Pydantic `ValidationError` (a `ValueError`).
- **R6.** Any other `kind` (missing, `None`, `""`, `"Vector"`, `"text"`) → `ValueError("saved_stamp.kind must be 'vector' or 'image'.")`. `{}` gives this error too.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| unknown `kind` | `ValueError` | `saved_stamp.kind must be 'vector' or 'image'.` |
| image `public_id` not under the user's stamp prefix (R4a, BUG-1864) | `ValueError` | `saved_stamp.public_id is not a stamp of this user` |
| schema broken | `pydantic.ValidationError` | Pydantic's (not asserted) |

**Side effects:** none

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 23 | `CLOUDINARY_UPLOAD_ENV` non-empty / else `ENVIRONMENT` | `build_stamp_public_id` R1 |
| 26–30 | production → bare; else `<env>/` prefix | `build_stamp_public_id` R2, R3, R4 |
| 33 | replace `/` `\`, strip, empty → `user-<id>` | `build_stamp_asset_folder` R1, R2 |
| 35–37 | production → bare; else `Dev/` | `build_stamp_asset_folder` R3 |
| 40–41 | cloud name or key falsy → error | `sign_stamp_image_upload` R1 |
| 47–53 | signature (client checks secret) | `sign_stamp_image_upload` R2, R4 |
| 54–68 | response fields | `sign_stamp_image_upload` R3, R5 |
| 71–72 | falsy or kind != image → return | `destroy_saved_stamp_image` R1, R2, R6 |
| 74–75 | no public_id → return | `destroy_saved_stamp_image` R3 |
| 76–79 | destroy, no prefix check (BUG-1865); any exception swallowed (no log: BUG-1713) | `destroy_saved_stamp_image` R4, R4a, R5, R5a |
| 82–83 | None → None | `validate_saved_stamp_payload` R1 |
| 85–88 | vector → validate, dump | `validate_saved_stamp_payload` R2, R5 |
| 89–90 | image → validate, dump (no prefix check: BUG-1864; client `url` kept: BUG-1866) | `validate_saved_stamp_payload` R3, R4, R4a, R4b, R5 |
| 91 | else → ValueError | `validate_saved_stamp_payload` R6 |
