# Spec — `app/core/cloudinary_client.py`

> **Status:** APPROVED
> **Source commit:** e48a092

## Review
> Reviewer: answer each question on its **Answer:** line with one of
> `intended` · `bug` · `bug — <what it should do instead>` · `remove` (unreachable
> code only) · or a question back.
> Then run the describer in `apply-review` mode.

### New questions

### Q1. "Signed" delivery URL is left unsigned for any type other than `authenticated` — ✅ intended
**Background:** Cloudinary stores each file under a *delivery type*. `authenticated`
files can only be downloaded through a URL carrying a signature; `upload` files
are public and need no signature. Our attachments use `authenticated`; older
attachments (the "legacy upload type") use `upload`. The function's docstring
says it builds "a signed delivery URL (authenticated or legacy upload type)".
**What happens today:** the URL is signed only when the delivery type is exactly
`authenticated`; for `upload` (and any other value, e.g. `private`) an unsigned
URL is returned. In practice callers only ever pass `authenticated` or `upload`.
**Example:** a legacy attachment with delivery type `upload`, public id
`ws/invoice-1`, version 123, format `pdf` gets
`https://res.cloudinary.com/<cloud>/image/upload/v123/ws/invoice-1.pdf` — no
`s--…--` signature segment — and it still opens, because `upload` files are public.
**Rules affected:** `build_signed_delivery_url` R2, R3
**Answer:** intended (reviewer accepted suggestion)
**Resolution:** only `authenticated` assets need a signed URL; `upload` (legacy, public) and any other type are returned unsigned by design. Rules unchanged: `build_signed_delivery_url` R2, R3.

**Suggested answer:** intended

## Overview
Single integration point between the backend and the Cloudinary SDK. It
refuses to talk to Cloudinary unless all three credentials are configured,
signs browser direct-upload parameters, builds delivery URLs (signed for
`authenticated` assets), and wraps four Admin/Upload API calls (fetch metadata,
delete, rename/move, update folder/display name). Callers:
`AttachmentManager`, `MobileUploadSessionManager`, `ProfileStampManager`;
endpoints (`attachments`, `mobile_upload`, `auth`) translate
`CloudinaryNotConfiguredError` into an HTTP error.

**Callables:** 7 specified · 1 not specified
**Externals to mock:** Cloudinary (`cloudinary.api.resource`,
`cloudinary.api.update`, `cloudinary.uploader.destroy`,
`cloudinary.uploader.rename`). `cloudinary.utils.api_sign_request` and
`cloudinary.utils.cloudinary_url` are pure/offline and may be used for real.
**Integration-only behavior:** none

**Notes for the test designer:**
- No database involved; every function is pure or calls Cloudinary. Tests need no session.
- Credentials are read from `app.core.config.settings` at call time
  (`CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, `CLOUDINARY_API_SECRET`, all
  default `""`). Set them per test with `monkeypatch.setattr(settings, ...)`.
- Every successful credential check also writes the SDK's process-global
  `cloudinary.config(...)`; tests that run it should restore/reset that global
  (or read it back via `cloudinary.config()` to assert R3 of `_ensure_configured`).
- Admin/Upload wrappers: patch the SDK function (e.g.
  `monkeypatch.setattr(cloudinary.uploader, "destroy", fake)`) — the module
  calls them through the `cloudinary.uploader` / `cloudinary.api` module
  attributes, so patching the attribute on the SDK module works. Assert on the
  arguments the fake received and on the returned value.
- Signature/URL results can be checked against known values computed with the
  real SDK (cloudinary 1.44.1) or by the recipe given in the rules.

## Not specified
- `CloudinaryNotConfiguredError` — plain `RuntimeError` subclass, no logic (its
  use is specified under `_ensure_configured`).
- `AUTHENTICATED_DELIVERY_TYPE` — module constant `"authenticated"` (value is
  relied on by the rules below).

---

## `_ensure_configured()`
**Shape:** validator
**Persistence:** pure (writes process-global SDK config)
**Visibility:** internal (used by: every public function in this module)

**Purpose:** Refuse to use Cloudinary unless all credentials are set, and load
them into the SDK.

**Inputs:** none (reads `settings.CLOUDINARY_CLOUD_NAME`,
`settings.CLOUDINARY_API_KEY`, `settings.CLOUDINARY_API_SECRET`).

**Returns:** `None`.

**Rules:**
- **R1.** If any one of cloud name, API key or API secret is empty (`""`) or
  `None`, `CloudinaryNotConfiguredError` is raised with the message
  `"Cloudinary is not configured. Set CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, and CLOUDINARY_API_SECRET."`.
  Each of the three missing on its own triggers it; all three missing too.
- **R2.** A value made only of whitespace (e.g. `" "`) counts as configured (no error).
- **R3.** When all three are set, no error is raised and the SDK's global
  configuration afterwards has `cloud_name`, `api_key`, `api_secret` equal to the
  settings values and `secure = True`.
- **R4.** When R1 raises, the SDK's global configuration is left unchanged.
- **R5.** Because every public function runs this check first, every public
  function raises `CloudinaryNotConfiguredError` (R1) before signing anything,
  building any URL, or contacting Cloudinary when credentials are incomplete —
  no Cloudinary API function is invoked.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| cloud name, API key or API secret falsy | `CloudinaryNotConfiguredError` (subclass of `RuntimeError`) | `Cloudinary is not configured. Set CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, and CLOUDINARY_API_SECRET.` |

**Side effects:** on success, overwrites the SDK's process-global config
(`cloud_name`, `api_key`, `api_secret`, `secure=True`).

---

## `generate_upload_signature(*, public_id, asset_folder, display_name, timestamp, delivery_type="authenticated")`
**Shape:** compute
**Persistence:** pure
**Visibility:** public

**Purpose:** Produce the signature a browser sends with a signed direct upload,
covering the timestamp, public id, Media Library folder, display name and
delivery type.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `public_id` | `str` | Target public id. Not validated. |
| `asset_folder` | `str` | Media Library folder. Not validated. |
| `display_name` | `str` | Media Library display name. Not validated. |
| `timestamp` | `int` | Unix seconds. Not validated (no range/freshness check). |
| `delivery_type` | `str` | Default `"authenticated"`. Not validated. |

**Returns:** the signature as a 40-character lowercase hex string.

**Rules:**
- **R1.** Credentials are checked first (`_ensure_configured` R1/R5).
- **R2.** The signature is SHA-1 (hex) of the string
  `"<k1>=<v1>&<k2>=<v2>&…" + API_SECRET`, where the pairs are the five
  parameters `timestamp`, `public_id`, `asset_folder`, `display_name`, `type`
  (= `delivery_type`), sorted alphabetically by the `k=v` text, and any `&`
  inside a pair is written as `%26`. It equals
  `cloudinary.utils.api_sign_request({...5 params...}, API_SECRET)`.
  Example (secret `s`, timestamp `1`, public id `p`, asset folder `""`,
  display name `d`, type `authenticated`) → `510bdebded8f7df0736f986c8d03a6408d67923f`.
- **R3.** A parameter whose value is empty/falsy (`""`, or `timestamp=0`) is left
  out of the signed string entirely — the signature is identical to one computed
  without that parameter (see R2 example: empty `asset_folder` gives the same
  signature as omitting it).
- **R4.** The signature changes when any one of the five non-empty parameters
  changes, and when the API secret changes. `resource_type` is not part of the
  signature.
- **R5.** When `delivery_type` is omitted, `type=authenticated` is signed.
- **R6.** Same inputs and secret → same signature (deterministic).

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| credentials incomplete | `CloudinaryNotConfiguredError` | see `_ensure_configured` |

**Side effects:** SDK global config set (`_ensure_configured` R3). No network call.

---

## `build_signed_delivery_url(*, public_id, resource_type, delivery_type, version, fmt, transformation=None, flags=None)`
**Shape:** compute
**Persistence:** pure
**Visibility:** public

**Purpose:** Build the HTTPS URL a client uses to view/download an asset,
signed when the asset is `authenticated`.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `public_id` | `str` | Asset public id (may contain `/`). |
| `resource_type` | `str` | e.g. `image`, `raw`, `video`. Not validated. |
| `delivery_type` | `str` | e.g. `authenticated`, `upload`. Not validated. |
| `version` | `int` | Asset version. |
| `fmt` | `str` | File extension appended to the URL. |
| `transformation` | `list[dict] \| None` | Cloudinary transformation chain; empty list treated as none. |
| `flags` | `str \| None` | Delivery flag, e.g. `"attachment"`; `""` treated as none. |

**Returns:** the URL string (the SDK's leftover options are discarded).

**Rules:**
- **R1.** Credentials are checked first (`_ensure_configured` R1/R5).
- **R2.** When `delivery_type` is exactly `"authenticated"`, the URL carries a
  signature segment `s--<8 chars>--` right after the delivery type, e.g.
  (cloud `demo`, key `k`, secret `s`) public id `a/b`, `image`, version 123, fmt
  `jpg` → `https://res.cloudinary.com/demo/image/authenticated/s--5pmR91cm--/v123/a/b.jpg`.
  The signature depends on the API secret and on the signed part of the path:
  the transformation segment (including a `fl_<flags>` segment), the public id
  and the format. ✅ Known values (cloud `demo`, key `k`, secret `s`, `image`,
  version 123, public id `a/b`, fmt `jpg` unless stated):
  public id `a/c` → `s--5J5IkvPG--`; fmt `png` → `s--KeyAQbUE--`;
  flags `"attachment"` → `s--LQNPH1Ob--`; transformation
  `[{"width": 400, "crop": "limit"}]` → `s--6_QbkIb2--`; secret `t` → `s--IoFgbQBd--`.
- **R2a.** The signature does **not** depend on `version`: the `v<version>/`
  segment is outside the signed string (standard Cloudinary signed-URL
  behavior, SDK 1.44.1). Same inputs with version 123 and version 124 give the
  same signature `s--5pmR91cm--`; only the `v…/` segment differs
  (`…/s--5pmR91cm--/v124/a/b.jpg`). Not a bug (best-practice default, delegated
  by reviewer): Cloudinary's signature protects the transformation and asset
  identity; the version only selects a cached revision.
- **R3.** For any other `delivery_type` (e.g. `"upload"`, `"private"`, or
  `"Authenticated"` with different case), the URL has no signature segment.
  *(See Q1.)* ✅
- **R4.** The URL always uses `https://res.cloudinary.com/<cloud_name>/<resource_type>/<delivery_type>/…`,
  includes `v<version>/`, and ends with `<public_id>.<fmt>`.
- **R5.** A non-empty `transformation` list is rendered into the URL path
  (e.g. `[{"width": 400, "crop": "limit"}]` → segment `c_limit,w_400`); `None` or
  `[]` adds no transformation segment.
- **R6.** A non-empty `flags` value is rendered as a `fl_<flags>` segment (e.g.
  `"attachment"` → `fl_attachment`); `None` or `""` adds none. Example unsigned
  (`upload`) with both: `https://res.cloudinary.com/demo/image/upload/c_limit,w_400/fl_attachment/v123/a/b.jpg`.
- **R7.** Same inputs and credentials → same URL (deterministic; no timestamp/expiry in the URL).

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| credentials incomplete | `CloudinaryNotConfiguredError` | see `_ensure_configured` |

**Side effects:** SDK global config set. No network call.

---

## `get_resource(*, public_id, resource_type="image", delivery_type="authenticated")`
**Shape:** get
**Persistence:** reads (Cloudinary Admin API)
**Visibility:** public

**Purpose:** Fetch an asset's metadata from Cloudinary.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `public_id` | `str` | Asset public id. |
| `resource_type` | `str` | Default `"image"`. |
| `delivery_type` | `str` | Default `"authenticated"`. |

**Returns:** Cloudinary's response, unchanged.

**Rules:**
- **R1.** Credentials are checked first; if incomplete, Cloudinary is not contacted (`_ensure_configured` R5).
- **R2.** Cloudinary's Admin "resource" lookup receives the `public_id`,
  `resource_type` and `type = delivery_type`, and nothing else.
- **R3.** With defaults, the lookup is for `resource_type="image"`, `type="authenticated"`.
- **R4.** Whatever Cloudinary returns is returned as-is.
- **R5.** Any exception raised by the SDK (e.g. `cloudinary.exceptions.NotFound`
  for an unknown asset, network errors) propagates unchanged — nothing is
  caught or wrapped.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| credentials incomplete | `CloudinaryNotConfiguredError` | see `_ensure_configured` |
| SDK error | the SDK's exception, unchanged | SDK's |

**Side effects:** one Cloudinary Admin API read.

---

## `destroy_resource(*, public_id, resource_type="image", delivery_type="authenticated")`
**Shape:** delete
**Persistence:** writes (Cloudinary)
**Visibility:** public

**Purpose:** Delete an asset from Cloudinary and invalidate CDN caches.

**Inputs:** as `get_resource`.

**Returns:** Cloudinary's response, unchanged (e.g. `{"result": "ok"}` or
`{"result": "not found"}` — neither is treated as an error here).

**Rules:**
- **R1.** Credentials are checked first; if incomplete, Cloudinary is not contacted.
- **R2.** Cloudinary's destroy receives `public_id`, `resource_type`,
  `type = delivery_type` and `invalidate=True`, nothing else.
- **R3.** Defaults: `resource_type="image"`, `type="authenticated"`.
- **R4.** The response is returned as-is; a `"not found"` result does not raise.
- **R5.** SDK exceptions propagate unchanged.

**Errors:** as `get_resource`.

**Side effects:** asset deleted in Cloudinary with CDN invalidation.

---

## `rename_resource(*, from_public_id, to_public_id, resource_type="image", delivery_type="authenticated")`
**Shape:** update
**Persistence:** writes (Cloudinary)
**Visibility:** public

**Purpose:** Move an asset to a new public id, keeping its delivery type.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `from_public_id` | `str` | Current public id. |
| `to_public_id` | `str` | New public id. |
| `resource_type` | `str` | Default `"image"`. |
| `delivery_type` | `str` | Default `"authenticated"`; used as both source and target type. |

**Returns:** Cloudinary's response, unchanged.

**Rules:**
- **R1.** Credentials are checked first; if incomplete, Cloudinary is not contacted.
- **R2.** Cloudinary's rename receives `from_public_id`, `to_public_id`,
  `resource_type`, `type = delivery_type`, `to_type = delivery_type` (same value)
  and `invalidate=True`, nothing else — in particular no `overwrite` option, so
  Cloudinary's default (do not overwrite an existing target) applies.
- **R3.** Defaults: `resource_type="image"`, `type` and `to_type` `"authenticated"`.
- **R4.** The response is returned as-is; SDK exceptions propagate unchanged.

**Errors:** as `get_resource`.

**Side effects:** asset moved in Cloudinary with CDN invalidation.

---

## `update_resource_metadata(*, public_id, resource_type="image", delivery_type="authenticated", asset_folder=None, display_name=None)`
**Shape:** update
**Persistence:** writes (Cloudinary)
**Visibility:** public

**Purpose:** Change an asset's Media Library folder and/or display name.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `public_id` | `str` | Asset public id. |
| `resource_type` | `str` | Default `"image"`. |
| `delivery_type` | `str` | Default `"authenticated"`. |
| `asset_folder` | `str \| None` | `None` = leave unchanged (not sent). `""` is sent. |
| `display_name` | `str \| None` | `None` = leave unchanged (not sent). `""` is sent. |

**Returns:** Cloudinary's response, unchanged.

**Rules:**
- **R1.** Credentials are checked first; if incomplete, Cloudinary is not contacted.
- **R2.** Cloudinary's Admin update always receives `public_id`, `resource_type`
  and `type = delivery_type`.
- **R3.** `asset_folder` is sent only when it is not `None`; an empty string `""` is sent as `""`.
- **R4.** `display_name` is sent only when it is not `None`; an empty string `""` is sent as `""`.
- **R5.** With both `None`, the update is still sent, carrying only
  `resource_type` and `type`.
- **R6.** The response is returned as-is; SDK exceptions propagate unchanged.

**Errors:** as `get_resource`.

**Side effects:** asset metadata updated in Cloudinary.

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 19 | cloud name falsy | `_ensure_configured` R1, R4 |
| 19 | API key falsy | `_ensure_configured` R1, R4 |
| 19 | API secret falsy | `_ensure_configured` R1, R4 |
| 19 | all truthy (incl. whitespace-only) | `_ensure_configured` R2, R3 |
| 40 | `delivery_type` default | `generate_upload_signature` R5 |
| 51 (SDK `api_string_to_sign`) | param value falsy → omitted | `generate_upload_signature` R3 |
| 51 (SDK) | `&` in value → `%26` | `generate_upload_signature` R2 |
| 69 | `delivery_type == "authenticated"` → sign | `build_signed_delivery_url` R2 |
| 69 | other delivery type → unsigned | `build_signed_delivery_url` R3 |
| 74 | `transformation` truthy / `None` / `[]` | `build_signed_delivery_url` R5 |
| 76 | `flags` truthy / `None` / `""` | `build_signed_delivery_url` R6 |
| 85–86 | defaults | `get_resource` R3 |
| 100–101 | defaults | `destroy_resource` R3 |
| 117–118 | defaults | `rename_resource` R3 |
| 146 | `asset_folder is not None` | `update_resource_metadata` R3, R5 |
| 148 | `display_name is not None` | `update_resource_metadata` R4, R5 |
| 43, 65, 89, 104, 121, 141 | credential check before any work | `_ensure_configured` R5 and R1 of each public function |
| 78 (SDK `cloudinary_url`) | signed string = transformation + `public_id.fmt` (version excluded) | `build_signed_delivery_url` R2, R2a |

## Gap log
- G1 (cloudinary_client.verify.md finding 1, DISCREPANCY-1) — Fact (spec error) — `build_signed_delivery_url` R2 wrongly listed `version` as a signature input. Verified against cloudinary 1.44.1: the SDK signs `transformation` + `public_id.fmt` only. Removed `version` from R2, added known signature values for each signed input, and added R2a (version is not signed: v123 and v124 both give `s--5pmR91cm--`). Treated as intended SDK behavior, not a bug (best-practice default, delegated by reviewer). Added a Branch-map row. No new question; status stays APPROVED.
