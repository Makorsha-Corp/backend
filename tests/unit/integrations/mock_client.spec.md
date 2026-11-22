# Spec — `app/integrations/sslcommerz/mock_client.py`

> **Status:** APPROVED
> **Source commit:** e48a092

## Review
> Reviewer: answer each question on its **Answer:** line with one of
> `intended` · `bug` · `bug — <what it should do instead>` · `remove` (unreachable
> code only) · or a question back.
> Then run the describer in `apply-review` mode.

### Precedent matches — confirm all with ok

### Q1. Looking up a transaction by `tran_id` alone always answers "never attempted" — 🐞 BUG-580
**Background:** The reconciliation sweep asks the gateway "what happened to transaction X?" for transactions that never got a callback. The mock gateway keeps no records: it can only tell the outcome of a payment from a `val_id` token, and such a token only reaches our server through a callback, which is exactly what those transactions are missing. The payment manager review already ruled on this (BUG-031) and said the fix belongs in this file.
**What happens today:** `query_by_tran_id` answers `UNATTEMPTED` whenever no `val_id` hint is given (or the hint is empty), even if the mock gateway page was completed with "Success" for that `tran_id`.
**Example:** A tester pays 500 BDT on the mock gateway page with "Drop the browser redirect" checked, and the IPN is lost too. The sweep calls `query_by_tran_id("ab12…")` with no hint. The answer is `UNATTEMPTED`, so the paid transaction becomes `EXPIRED`.
**Rules affected:** `query_by_tran_id` R1, R4
**Answer:** bug — per BUG-031 precedent: the mock answers a lookup by `tran_id` alone from its own record of completed mock payments (every outcome minted by `build_val_id`), returning the same result `validate` would give for that payment; `UNATTEMPTED` only when the mock has never completed that `tran_id`. *(requires the mock to keep state)* (precedent — confirmed: ok)
**Resolution:** same root cause as BUG-031 (pattern `sweep-lookup-requires-callback-data`); logged as BUG-580 against this file. The mock records every outcome it mints and answers `tran_id`-only lookups from that record. Follow-up details decided by best practice (best-practice default, delegated by reviewer): the record lives in the client instance (the app uses one process-wide instance via `get_sslcommerz_client()`); when the same `tran_id` is completed more than once the latest minted outcome wins; a hint that is invalid or belongs to another `tran_id` is ignored and the lookup falls back to the record. Related: TODO-001 — the mock is to be removed or upgraded (and restricted to non-production) before production; this fix may land as part of that upgrade. Rules: `build_val_id` R6; `query_by_tran_id` R1, R1a, R3, R3a, R4.

### New questions

### Q2. A malformed `val_id` crashes validation instead of being rejected — 🐞 BUG-581
**Background:** `validate(val_id)` is the server-to-server check for a `val_id` that arrives on the public `/payments/success`, `/payments/fail` and `/payments/ipn` endpoints, so anyone can send any string. A `val_id` is `<base64 of a JSON object>.<hex signature>`. Garbage that is not valid base64/JSON, or has no `.`, is answered with `INVALID_TRANSACTION`.
**What happens today:** If the part before the last `.` decodes to valid JSON that is not an object with all five fields (`status`, `tran_id`, `amount`, `currency`, `risk_level`) — e.g. `{}`, `[1]`, `null` — or if the signature part contains a non-ASCII character, `validate` raises (`KeyError` / `TypeError`) instead of answering `INVALID_TRANSACTION`.
**Example:** Someone POSTs `tran_id=<a real pending tran_id>&val_id=e30=.x` (`e30=` is base64 for `{}`) to `/payments/success`. Instead of the attempt being rejected as invalid, the request fails with a 500 Internal Server Error.
**Rules affected:** `_decode_val_id` R5, R6; `validate` R1
**Answer:** bug — any val_id that does not decode to a correctly shaped, correctly signed payload is answered with INVALID_TRANSACTION (empty tran_id); validate never raises on caller input (reviewer accepted suggestion)
**Suggested answer:** bug — any `val_id` that does not decode to a correctly shaped, correctly signed payload is answered with `INVALID_TRANSACTION` (empty `tran_id`); `validate` never raises on caller input.
**Resolution:** malformed payloads and non-ASCII signatures are rejected like any other bad token. "Never raises on caller input" also covers a correctly signed payload whose `amount` is not a valid decimal number → `INVALID_TRANSACTION` (best-practice default, delegated by reviewer). Non-string `val_id` values are out of scope (every caller passes a form string) (best-practice default, delegated by reviewer). Rules: `_decode_val_id` R5, R6; `validate` R1a, R1b; `query_by_tran_id` R5.

### Q3. An IPN with a non-ASCII `verify_sign` crashes instead of failing the signature check — 🐞 BUG-582
**Background:** `verify_signature` is the cheap first check on the public IPN webhook (`/payments/ipn`): `False` makes the endpoint answer 400 "Invalid IPN signature".
**What happens today:** When `verify_sign` contains any non-ASCII character (and the five signed fields are present), the comparison raises `TypeError` instead of returning `False`.
**Example:** A request POSTs to `/payments/ipn` with `tran_id`, `val_id`, `status`, `amount`, `currency`, `risk_level` and `verify_sign=é`. Instead of 400 "Invalid IPN signature", the caller gets a 500 Internal Server Error.
**Rules affected:** `verify_signature` R4
**Answer:** bug — any verify_sign that does not match (including non-ASCII or non-string values) returns False; verify_signature never raises (reviewer accepted suggestion)
**Suggested answer:** bug — any `verify_sign` that does not match (including non-ASCII or non-string values) returns `False`; `verify_signature` never raises.
**Resolution:** a non-ASCII or truthy non-string (e.g. `123`, `["x"]`) `verify_sign` returns `False`. Rules: `verify_signature` R4.

### Q4. A `val_id` that is not in canonical form is still accepted — 🐞 BUG-583
**Background:** A `val_id` is `<URL-safe base64 of the payload JSON>.<hex signature>`. The signature covers the five payload *fields*, not the token text. Base64 text never contains `.`, and hex never contains `.`, so a token minted by `build_val_id` always has exactly one `.`. Decoding today is lenient: characters outside the base64 alphabet (such as `.`) are skipped, and anything after the padding `=` is ignored.
**What happens today:** Many different strings decode to the same signed payload and are all accepted as the same payment outcome. For example, `<encoded>.x.<signature>` (an extra `.`-separated segment) validates as fully `VALID` with `verify_sign` = the real signature.
**Example:** A tester completes transaction `TXN-ABC-001` and gets token `T = E + "." + S`. The string `E + ".x." + S` is also answered `VALID` for `TXN-ABC-001`, 500 BDT, and so are other variants with stray characters inside `E`. Anything that de-duplicates or compares tokens by their text (logs, the stored `val_id`) sees different tokens for one payment.
**Rules affected:** `_decode_val_id` R3, R3a; `validate` R1, R5
**Answer:** bug — a signed token has exactly one canonical encoding: a `val_id` with more than one `.`, or whose payload part is not the exact canonical URL-safe base64 of its decoded bytes, is rejected (`None` / `INVALID_TRANSACTION`) (best-practice default, delegated by reviewer)
**Resolution:** raised by the verifier (F1, DISCREPANCY-1) and decided by best practice (best-practice default, delegated by reviewer). Logged as BUG-583 (pattern `non-canonical-token-accepted`). Severity is low: this is a mock-only helper (TODO-001). The JSON *inside* the payload is not required to be canonical, because the signature covers field values and not bytes (best-practice default, delegated by reviewer). Rules: `_decode_val_id` R3, R3a, R3b; `validate` R1, R5.

## Overview
The mock SSLCommerz payment gateway used in local development and on the billing trial page (it is the only gateway client implemented today; `get_sslcommerz_client()` returns it when `SSLCOMMERZ_MOCK_MODE` is true). Today it is stateless: the outcome of a simulated payment is packed into a signed `val_id` token (`build_val_id`), and `validate` checks the signature and decodes it. Intended (BUG-580): it additionally remembers every outcome it mints so the reconciliation sweep can look a payment up by `tran_id` alone. Callers: the payment manager (`validate` for redirect/IPN callbacks, `query_by_tran_id` in the reconciliation sweep), the `/payments/ipn` endpoint (`verify_signature`), and the mock-gateway endpoints (`init_session` via the manager, `build_val_id` + `validate` in `/payments/mock-gateway/{tran_id}/complete`). The invariant it protects: nobody without `settings.SECRET_KEY` can mint a token or form that passes `validate` / `verify_signature`.

**Callables:** 7 specified · 0 not specified
**Externals to mock:** none (this module is itself the SSLCommerz stand-in). Tests control `settings.SECRET_KEY`, `settings.BACKEND_BASE_URL`, `settings.API_V1_STR` (monkeypatch attributes on `app.core.config.settings`).
**Integration-only behavior:** none

**TODO (TODO-001, reviewer):** the mock will be removed or upgraded later; before production it must either be gone or only be enable-able in non-production environments. Left as is for now; nothing in this spec depends on that change.

**Notes for the test designer:**
- BUG-583: after the fix, every accepted token has exactly one `.`, so *where* a token is split (first or last `.`) cannot be observed on any accepted token. Every multi-dot token is `None` / `INVALID_TRANSACTION`, whatever the split. Test the multi-dot case as an xfail(BUG-583) expecting rejection. Do not write a pass case that needs a multi-dot token to be accepted. Mutants that change only the split point (`rsplit(".", 1)` → `rsplit(".", 2)`) are expected to survive until BUG-583 is fixed, and to be equivalent after the fix.
- Everything here is pure (no DB, no network). Instantiate `MockSSLCommerzClient()` directly. For BUG-580 rules, mint (`build_val_id`) and look up (`query_by_tran_id`) on the **same** instance; a fresh instance has an empty record.
- The signature is `HMAC-SHA256(key = settings.SECRET_KEY as UTF-8, message = "<status>|<tran_id>|<amount>|<currency>|<risk_level>")`, lowercase hex (64 chars), where each value is converted with Python `str()`. Tests may compute the expected signature independently with `hmac`/`hashlib`.
- To build malformed tokens: `base64.urlsafe_b64encode(json.dumps(obj).encode()).decode() + "." + sig`.
- Changing `settings.SECRET_KEY` between minting and validating makes a previously valid token invalid (useful to test "signed with another key").

## Not specified
- (none)

---

## `_sign(payload)`
**Shape:** compute
**Persistence:** pure
**Visibility:** internal (used by: `build_val_id`, `_decode_val_id`, `verify_signature`)

**Purpose:** Computes the mock gateway's signature over the five signed fields of a payment outcome.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `payload` | dict (anything indexable by string) | Must contain keys `status`, `tran_id`, `amount`, `currency`, `risk_level`; extra keys are ignored |

**Returns:** 64-character lowercase hex string.

**Rules:**
- **R1.** The result is HMAC-SHA256, keyed with `settings.SECRET_KEY` (UTF-8), of the string `str(status) + "|" + str(tran_id) + "|" + str(amount) + "|" + str(currency) + "|" + str(risk_level)`, as lowercase hex.
- **R2.** Only those five fields affect the result; adding or changing any other key leaves it unchanged.
- **R3.** Values are compared by their `str()` form: `risk_level` `0` (int) and `"0"` (str) give the same signature; `amount` `"10.00"` and `"10.0"` give different signatures. `None` is signed as the text `"None"`.
- **R4.** Different `SECRET_KEY` values give different signatures for the same payload.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| One of the five keys missing from a dict | `KeyError` | the missing key name |
| `payload` is a list / `None` / other non-mapping | `TypeError` | Python's default |

**Side effects:** none

---

## `MockSSLCommerzClient.init_session(req)`
**Shape:** compute
**Persistence:** pure
**Visibility:** public (used by: `PaymentTransactionManager.initiate_payment`)

**Purpose:** Pretends to open a gateway checkout session and returns the URL of the mock gateway page for this transaction.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `req` | `InitSessionRequest` | Only `req.tran_id` is used; amount, currency, URLs, customer and product fields are ignored |

**Returns:** `InitSessionResult` with `status="SUCCESS"`, `session_key`, `gateway_page_url`, `failed_reason=None`.

**Rules:**
- **R1.** Always succeeds: `status` is `"SUCCESS"` and `failed_reason` is `None`, whatever the request contains (including zero/negative amounts or empty strings).
- **R2.** `session_key` is the URL-safe base64 encoding of the SHA-256 digest of `tran_id` (UTF-8), with trailing `=` removed — 43 characters from `A–Z a–z 0–9 - _`. The same `tran_id` always gives the same key; different `tran_id`s give different keys.
- **R3.** `gateway_page_url` is exactly `settings.BACKEND_BASE_URL + settings.API_V1_STR + "/payments/mock-gateway/" + tran_id` (defaults: `http://localhost:8000/api/v1/payments/mock-gateway/<tran_id>`). The `tran_id` is inserted as-is, not URL-encoded.

**Errors:** none

**Side effects:** none

---

## `MockSSLCommerzClient.build_val_id(*, tran_id, amount, currency, status, risk_level=0)`
**Shape:** compute
**Persistence:** pure
**Visibility:** public, mock-only (used by: `POST /payments/mock-gateway/{tran_id}/complete`)

**Purpose:** Mints the signed `val_id` token that encodes a simulated payment outcome.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `tran_id` | str | none |
| `amount` | Decimal | stored as `str(amount)` — keeps the Decimal's own formatting (`Decimal("10.00")` → `"10.00"`, `Decimal("1E+2")` → `"1E+2"`) |
| `currency` | str | none |
| `status` | str | none (endpoint passes `VALID`, `FAILED` or `CANCELLED`) |
| `risk_level` | int, default `0` | none (endpoint passes `1` only for a risky `VALID`, else `0`) |

**Returns:** a string `"<encoded>.<signature>"`.

**Rules:**
- **R1.** `<encoded>` is the URL-safe base64 (padding `=` kept) of the compact JSON (`separators=(",", ":")`) of the object `{"tran_id", "amount", "currency", "status", "risk_level"}` in that key order, with `amount` as `str(amount)` and `risk_level` as given (a JSON number for an int).
- **R2.** `<signature>` is `_sign` (R1) of that same object.
- **R3.** Omitting `risk_level` encodes `0`.
- **R4.** A token built here, passed unchanged to `validate`, is accepted and reproduces every input (see `validate` R2).
- **R5.** The same inputs always produce the identical token (deterministic; no timestamp, nonce or expiry).
- **R6.** [BUG-580] The minted outcome is recorded by the client instance under its `tran_id`, so a later `query_by_tran_id(tran_id)` with no hint on the same instance returns `validate(<this token>)`. Minting again for the same `tran_id` replaces the record (latest wins) (best-practice default, delegated by reviewer). *(Today: nothing is recorded.)* *(requires new per-instance state)*

**Errors:** none for str/Decimal/int inputs.

**Side effects:** [BUG-580] records the outcome in the instance's record of completed mock payments (see R6). *(Today: none.)*

---

## `MockSSLCommerzClient._decode_val_id(val_id)`
**Shape:** validator
**Persistence:** pure
**Visibility:** internal (used by: `validate`)

**Purpose:** Splits a `val_id` token, decodes its payload and checks its signature.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `val_id` | str | see rules |

**Returns:** the decoded payload dict, or `None`.

**Rules:**
- **R1.** A token minted by `build_val_id` with the current `SECRET_KEY` returns its payload dict (keys `tran_id`, `amount`, `currency`, `status`, `risk_level`, values as encoded).
- **R2.** No `.` in the string (including the empty string) → `None`.
- **R3.** A token with exactly one `.` whose part before the `.` is not decodable base64, not UTF-8, or not valid JSON → `None`. (Examples that are rejected today and after the fix: `"!!!.abc"`, a payload part with incorrect padding, a payload part that decodes to non-UTF-8 bytes, a payload part that decodes to `not json`.)
- **R3a.** [BUG-583] A token with **more than one** `.` → `None`, no matter what the segments contain. This includes `<valid encoded>.x.<valid signature>`, `<valid encoded>..<valid signature>` and `<valid encoded>.<valid signature>.` (best-practice default, delegated by reviewer). *(Today: the token is split at the last `.`, and lenient base64 decoding skips the stray `.` and any characters after the padding. So `<valid encoded>.x.<valid signature>` is accepted as the full valid payload, while tokens whose last segment is not the signature fail the signature check.)*
- **R3b.** [BUG-583] A token with exactly one `.` whose payload part is not the exact canonical URL-safe base64 (with `=` padding) of the bytes it decodes to → `None`, even if the decoded payload is correctly signed. This covers: characters outside the URL-safe alphabet `A–Z a–z 0–9 - _` and trailing `=` (for example, whitespace/newline inserted into the part, or standard-alphabet `+` / `/`); extra characters after the padding; and a last character whose unused low bits are non-zero (best-practice default, delegated by reviewer). *(Today: lenient decoding accepts these as long as the decoded bytes are the signed JSON.)* The JSON itself need not be canonical: a correctly signed payload re-serialised with other whitespace, other key order, or extra keys is still accepted (R1 applies to its five fields).
- **R4.** A well-formed payload whose signature does not match (tampered field, wrong/empty signature, signed with a different `SECRET_KEY`, signature in upper-case hex) → `None`.
- **R5.** [BUG-581] A part before the last `.` that decodes to valid JSON which is not an object containing all five signed fields (`{}`, `{"status":"VALID"}`, `[1]`, `null`, `1`) → `None`, no exception. *(Today: raises `KeyError` or `TypeError`.)*
- **R6.** [BUG-581] A correctly shaped payload with a signature part containing a non-ASCII character → `None`, no exception. *(Today: raises `TypeError` "comparing strings with non-ASCII characters is not supported".)*

**Errors:** none for string input (intended; today R5/R6 raise).

**Side effects:** none

---

## `MockSSLCommerzClient.validate(val_id)`
**Shape:** validator
**Persistence:** pure
**Visibility:** public (used by: `PaymentTransactionManager.finalize_from_gateway`, `query_by_tran_id`, mock-gateway complete endpoint)

**Purpose:** The mock's "server-to-server validation" of a `val_id`: returns the payment outcome it encodes, or `INVALID_TRANSACTION`.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `val_id` | str | accepted/rejected per `_decode_val_id` R1–R6 |

**Returns:** `ValidationResult`.

**Rules:**
- **R1.** A token rejected by `_decode_val_id` (R2–R4, including [BUG-583] R3a/R3b) → `ValidationResult(status="INVALID_TRANSACTION", tran_id="")`, every other field `None`.
- **R1a.** [BUG-581] A token hitting `_decode_val_id` R5/R6 gets the same `INVALID_TRANSACTION` result as R1; `validate` never raises for any string input. *(Today: raises `KeyError`/`TypeError`.)*
- **R1b.** [BUG-581] A correctly signed, correctly shaped payload whose `amount` is not a valid decimal number (e.g. `"abc"`; only mintable with the `SECRET_KEY`) → the same `INVALID_TRANSACTION` result as R1 (best-practice default, delegated by reviewer). *(Today: raises `decimal.InvalidOperation`.)*
- **R2.** A valid token → `status`, `tran_id`, `currency` and `risk_level` exactly as encoded; `amount` = `Decimal(<encoded amount string>)` (e.g. `Decimal("10.00")`); `val_id` = the input string unchanged.
- **R3.** `risk_title` is `"Risky"` when `risk_level == 1`, otherwise `"Safe"` (including `0` and any other value such as `2`).
- **R4.** `bank_tran_id` = `"MOCKBANK-" + tran_id`; `card_type` = `"mock-visa"`.
- **R5.** `verify_sign` = the signature part of the token (the text after its only `.`; see `_decode_val_id` R3a); `verify_key` = `"status,tran_id,amount,currency,risk_level"`.
- **R6.** The encoded `status` is returned as-is on every call: validating the same token repeatedly always gives the same answer (a `VALID` token keeps answering `VALID`; there is no `VALIDATED` on repeat and no expiry).
- **R7.** A form built from a valid result's `status`, `tran_id`, `str(amount)`, `currency`, `str(risk_level)` and `verify_sign` passes `verify_signature` (R5).

**Errors:** none for string input (intended; today see R1a, R1b).

**Side effects:** none

---

## `MockSSLCommerzClient.query_by_tran_id(tran_id, val_id_hint=None)`
**Shape:** get
**Persistence:** pure
**Visibility:** public (used by: `PaymentTransactionManager.reconcile_stuck_transactions`, always passing the row's stored `val_id` as hint)

**Purpose:** The mock's "look up a transaction by `tran_id`" call used by the reconciliation sweep.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `tran_id` | str | none |
| `val_id_hint` | str \| None, default `None` | treated as absent when falsy (`None` or `""`) |

**Returns:** `ValidationResult`.

**Rules:**
- **R1.** No hint (`None` or `""`) and this instance has never minted an outcome for `tran_id` → `ValidationResult(status="UNATTEMPTED", tran_id=tran_id)`, all other fields `None`.
- **R1a.** [BUG-580] No hint (`None` or `""`) and this instance has minted an outcome for `tran_id` (`build_val_id` R6) → exactly `validate(<latest token minted for tran_id>)` (any status: `VALID`, `FAILED`, `CANCELLED`, …). Outcomes minted for other `tran_id`s do not match. *(Today: `UNATTEMPTED`.)*
- **R2.** A hint that `validate`s to a result whose `tran_id` equals `tran_id` → exactly that `validate` result (any encoded status: `VALID`, `FAILED`, `CANCELLED`, …).
- **R3.** A hint that is a valid token for a **different** `tran_id`, with no recorded outcome for the asked `tran_id` → `UNATTEMPTED` for the asked `tran_id` (as R1).
- **R3a.** [BUG-580] A hint that is a valid token for a different `tran_id`, with a recorded outcome for the asked `tran_id` → the recorded result (as R1a); the hint is ignored (best-practice default, delegated by reviewer). *(Today: `UNATTEMPTED`.)*
- **R4.** [BUG-580] A hint rejected by `validate` (`INVALID_TRANSACTION`) is ignored: the result is as if no hint were given (R1 / R1a), including when the asked `tran_id` is `""` (→ `UNATTEMPTED` with `tran_id=""`, never `INVALID_TRANSACTION`) (best-practice default, delegated by reviewer). *(Today: always `UNATTEMPTED` even when an outcome was minted; and for asked `tran_id` `""` the `INVALID_TRANSACTION` result itself is returned.)*
- **R5.** [BUG-581] A malformed hint (one that hits `_decode_val_id` R5/R6 or `validate` R1b) is handled like any rejected hint (R4); `query_by_tran_id` never raises for string input. *(Today: the `KeyError`/`TypeError`/`InvalidOperation` from `validate` propagates.)*

**Errors:** none for string input (intended; today see R5).

**Side effects:** none (reads the instance's record, never changes it)

---

## `MockSSLCommerzClient.verify_signature(payload)`
**Shape:** validator
**Persistence:** pure
**Visibility:** public (used by: `POST /payments/ipn`)

**Purpose:** Cheap check that an incoming IPN form was signed by the mock gateway.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `payload` | dict | form fields; reads `verify_sign`, `status`, `tran_id`, `amount`, `currency`, `risk_level`; everything else (incl. `val_id`, `verify_key`) is ignored |

**Returns:** bool.

**Rules:**
- **R1.** `verify_sign` missing, `None` or `""` → `False`.
- **R2.** Any of the five signed fields missing or `None` → `False`. An empty string `""` counts as present and is signed as `""`.
- **R3.** `True` exactly when `verify_sign` equals `_sign` (R1) of the five fields (by `str()` form, so `"0"` and `0` for `risk_level` are equivalent); a changed field, different `SECRET_KEY`, or wrong/upper-case signature → `False`. `val_id` is not covered: changing it alone keeps the result `True`.
- **R4.** [BUG-582] A `verify_sign` containing a non-ASCII character, or a truthy non-string value (e.g. `123`, `["x"]`), with all five fields present → `False`; `verify_signature` never raises for a dict payload. *(Today: raises `TypeError`.)*
- **R5.** The form the mock-gateway endpoint builds from a `validate` result (see `validate` R7) returns `True`.

**Errors:** none (intended; today R4 raises `TypeError`).

**Side effects:** none

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 29 | each of the 5 fields looked up (missing → KeyError / non-dict → TypeError) | `_sign` R1, R2, Errors; `_decode_val_id` R5 |
| 29 | `str()` conversion of values | `_sign` R3 |
| 30 | key = `SECRET_KEY` | `_sign` R4 |
| 35 | session key from tran_id | `init_session` R2 |
| 36–38 | URL built from settings + raw tran_id | `init_session` R3 |
| 39 | always `SUCCESS` | `init_session` R1 |
| 48 | `risk_level` default `0` | `build_val_id` R3 |
| 53–62 | payload/encoding/signature | `build_val_id` R1, R2, R4, R5 |
| (after BUG-580 fix) | record minted outcome, latest wins | `build_val_id` R6 |
| 66 | no `.` → ValueError caught | `_decode_val_id` R2 |
| 66 | split at last `.` (multi-dot token reaches lenient decode) | `_decode_val_id` R3a; `validate` R5 |
| 67 | lenient base64 (non-alphabet chars / data after padding ignored) | `_decode_val_id` R3b |
| (after BUG-583 fix) | more than one `.` / non-canonical base64 → `None` | `_decode_val_id` R3a, R3b |
| 67 | bad base64 / UTF-8 / JSON → caught | `_decode_val_id` R3 |
| 68 | exceptions outside `(ValueError, TypeError, UnicodeDecodeError)` path — `_sign` errors happen after the `try` | `_decode_val_id` R5 |
| 70 | signature mismatch → `None` | `_decode_val_id` R4 |
| 70 | non-ASCII signature → `TypeError` | `_decode_val_id` R6 |
| 72 | valid → payload | `_decode_val_id` R1 |
| 76–77 | `payload is None` → `INVALID_TRANSACTION` | `validate` R1, R1a |
| 80–92 | field mapping | `validate` R2, R4, R5, R6, R7 |
| 84 | `Decimal(amount)` not a number → today raises | `validate` R1b |
| 87 | `risk_level == 1` → Risky / else Safe | `validate` R3 |
| 95 | hint truthy / falsy | `query_by_tran_id` R1, R1a, R2 |
| 96 | `validate` raises | `query_by_tran_id` R5 |
| 97 | `result.tran_id == tran_id` true / false | `query_by_tran_id` R2, R3, R4 |
| 99 | fallback `UNATTEMPTED` | `query_by_tran_id` R1, R3, R4 |
| (after BUG-580 fix) | fallback: recorded outcome for `tran_id` exists / not | `query_by_tran_id` R1, R1a, R3a, R4 |
| 103 | `verify_sign` falsy → False | `verify_signature` R1 |
| 106 | any field `None` → False | `verify_signature` R2 |
| 108 | digest compare true / false | `verify_signature` R3, R5 |
| 108 | non-ASCII `verify_sign` → `TypeError` | `verify_signature` R4 |

## Gap log
- G1 (mock_client.verify.md F1; DISCREPANCY-1) — Intent, decided by best practice (best-practice default, delegated by reviewer); no question left open — tokens that are not canonical (more than one `.`, or a payload part that is not strict canonical URL-safe base64) are rejected. Added resolved Q4 / BUG-583, `_decode_val_id` R3 reworded, R3a and R3b added, `validate` R1 and R5 updated, Branch map rows added, test-designer note on the split point that cannot be observed and on mutants #43 and #59.
