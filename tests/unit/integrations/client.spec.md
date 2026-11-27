# Spec — `app/integrations/sslcommerz/client.py`

> **Status:** APPROVED
> **Source commit:** e48a092

## Review
> Reviewer: answer each question on its **Answer:** line with one of
> `intended` · `bug` · `bug — <what it should do instead>` · `remove` (unreachable
> code only) · or a question back.
> Then run the describer in `apply-review` mode.

### Precedent matches — confirm all with ok

### P1. The gateway session request has no place for `value_a`..`value_d` — 🐞 BUG-020
**Background:** SSLCommerz lets a merchant attach four free-form correlation fields (`value_a`..`value_d`) to a checkout session; the gateway echoes them back on every callback. Our payment transaction stores these four fields. `InitSessionRequest` is the data object every client implementation receives when a checkout session is started. BUG-020 (payment manager spec Q2) already ruled that these values must be sent to the gateway, and noted the fix needs new fields on `InitSessionRequest`.
**What happens today:** `InitSessionRequest` has no `value_a`..`value_d` fields, so no client implementation (mock or a future real one) can send them; constructing it with `value_a=...` raises `TypeError`.
**Example:** A caller starts a payment with `value_a = "plan:pro;months:12"`. The request object handed to the gateway client cannot carry it, so the gateway session is created without it and callbacks never contain it.
**Rules affected:** `InitSessionRequest` R1, R3
**Answer:** bug — per BUG-020 precedent: `InitSessionRequest` has optional fields `value_a`, `value_b`, `value_c`, `value_d` (each `str | None`, default `None`) so the session request can carry them to the gateway. Same fix as BUG-020 — record against BUG-020 rather than a new ID. (precedent — confirmed: ok)
**Resolution:** `InitSessionRequest` gains four optional fields `value_a`..`value_d` (`str | None`, default `None`); recorded against existing BUG-020 (same fix), no new ID. Rules: `InitSessionRequest` R1a, R3 (example changed), R3a.

## Overview
Defines the contract between payment business logic and the SSLCommerz payment
gateway: three plain data objects (`InitSessionRequest`, `InitSessionResult`,
`ValidationResult`) whose field names mirror SSLCommerz's own API vocabulary,
and the abstract base class `SSLCommerzClient` that every gateway client
(today only `MockSSLCommerzClient`; a real client is not written yet) must
implement. Business logic obtains a client via `get_sslcommerz_client()` and
never talks to the gateway directly. The file contains no logic of its own —
no validation, no I/O — so its observable behavior is: dataclass construction
and defaults, and the abstract-class enforcement.

Callers: `app/managers/payment_transaction_manager.py` (builds
`InitSessionRequest`, consumes `InitSessionResult` / `ValidationResult`),
`app/integrations/sslcommerz/mock_client.py` (subclass),
`app/integrations/sslcommerz/__init__.py` (return type),
`app/api/v1/endpoints/payments.py` (calls `verify_signature` on IPN).
The manager never sets `product_name` or `product_category`, so only their
defaults are ever sent.

**Callables:** 7 specified · 0 not specified
**Externals to mock:** none
**Integration-only behavior:** none

**Notes for the test designer:** pure Python, no DB, no settings, no network.
Test the dataclasses by constructing them directly. Test the ABC by defining
small throwaway subclasses inside the test (one overriding all four methods,
others omitting one method each) and by calling the base implementation via
`super()` from a subclass. The behavioral contracts in the docstrings (what
`validate` / `query_by_tran_id` / `verify_signature` must return) are tested in
the mock client's spec, not here.

## Not specified
_(none)_

---

## `InitSessionRequest(...)`
**Shape:** mapper
**Persistence:** pure
**Visibility:** public (used by: `PaymentTransactionManager.initiate_payment`, `MockSSLCommerzClient.init_session`)

**Purpose:** Carry everything needed to open a checkout session at the gateway.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `tran_id` | `str` | our transaction id; required; not type-checked |
| `amount` | `Decimal` | amount to charge; required; not type-checked, no range/precision check |
| `currency` | `str` | currency code; required; not validated |
| `success_url` | `str` | browser redirect on success; required |
| `fail_url` | `str` | browser redirect on failure; required |
| `cancel_url` | `str` | browser redirect on cancel; required |
| `ipn_url` | `str` | server-to-server notification URL; required |
| `cus_name` | `str` | customer name; required |
| `cus_email` | `str` | customer email; required |
| `cus_phone` | `str` | customer phone; required |
| `product_name` | `str` | default `"Workspace Subscription"` |
| `product_category` | `str` | default `"subscription"` |
| `value_a`..`value_d` | `str \| None` | [BUG-020] intended: four optional correlation fields, each default `None`, echoed back by the gateway on callbacks. *(Today: these fields do not exist.)* |

**Returns:** an `InitSessionRequest` instance holding exactly the given values.

**Rules:**
- **R1.** Constructed with the ten required fields (positionally in the order above, or by keyword), every field holds exactly the value passed — no conversion, trimming or validation (e.g. `amount=Decimal("10.005")` stays `Decimal("10.005")`; a `str` passed as `amount` is stored as that `str`).
- **R1a.** [BUG-020] `InitSessionRequest` accepts the optional keyword fields `value_a`, `value_b`, `value_c`, `value_d`; each holds exactly the value passed (e.g. `value_a="plan:pro;months:12"`), and each is `None` when not given. *(Today: the fields do not exist — passing any of them raises `TypeError`.)* *(requires new fields on `InitSessionRequest`; the fix also touches `PaymentTransactionManager.initiate_payment`, see BUG-020)*
- **R2.** When `product_name` / `product_category` are not given, they are `"Workspace Subscription"` and `"subscription"`; when given, the given values are kept.
- **R3.** Omitting any of the ten required fields, or passing a keyword that is not a declared field (e.g. `foo="x"`), raises `TypeError`.
- **R3a.** Constructing with only the ten required fields (no `value_*` given) succeeds — `value_a`..`value_d` are optional, never required. Holds today and must keep holding after the BUG-020 fix (untagged regression guard; not expected-to-fail).
- **R4.** Two instances with equal field values compare equal (`==`); instances are mutable (fields can be reassigned after construction).

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| required field missing / unknown keyword | `TypeError` | Python's standard dataclass `__init__` message |

**Side effects:** none

---

## `InitSessionResult(...)`
**Shape:** mapper
**Persistence:** pure
**Visibility:** public (used by: `MockSSLCommerzClient.init_session`, `PaymentTransactionManager.initiate_payment`)

**Purpose:** Carry the gateway's answer to a session-start request.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `status` | `str` | `'SUCCESS'` or `'FAILED'` by convention; required; any string accepted |
| `session_key` | `str \| None` | gateway session key; default `None` |
| `gateway_page_url` | `str \| None` | URL to redirect the customer to; default `None` |
| `failed_reason` | `str \| None` | gateway's refusal reason; default `None` |

**Returns:** an `InitSessionResult` instance.

**Rules:**
- **R1.** With only `status` given, `session_key`, `gateway_page_url` and `failed_reason` are all `None`.
- **R2.** Any string is accepted as `status` (e.g. `"success"` lowercase, `""`) — no enum check; given optional values are kept as passed.
- **R3.** Omitting `status` or passing an unknown keyword raises `TypeError`.
- **R4.** Equal field values → instances compare equal.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| `status` missing / unknown keyword | `TypeError` | standard dataclass message |

**Side effects:** none

---

## `ValidationResult(...)`
**Shape:** mapper
**Persistence:** pure
**Visibility:** public (used by: `MockSSLCommerzClient.validate` / `query_by_tran_id`, `PaymentTransactionManager` result handling)

**Purpose:** Carry the gateway's authoritative answer about one transaction, from either the `val_id` lookup or the `tran_id` lookup (same shape for both).

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `status` | `str` | by convention one of `VALID`, `VALIDATED`, `FAILED`, `CANCELLED`, `EXPIRED`, `UNATTEMPTED`, `INVALID_TRANSACTION`; required; any string accepted |
| `tran_id` | `str` | transaction id the gateway resolved; required |
| `val_id` | `str \| None` | default `None` |
| `amount` | `Decimal \| None` | default `None` |
| `currency` | `str \| None` | default `None` |
| `risk_level` | `int \| None` | `0` = safe, `1` = risky by convention; default `None` |
| `risk_title` | `str \| None` | default `None` |
| `bank_tran_id` | `str \| None` | default `None` |
| `card_type` | `str \| None` | default `None` |
| `verify_sign` | `str \| None` | default `None` |
| `verify_key` | `str \| None` | default `None` |

**Returns:** a `ValidationResult` instance.

**Rules:**
- **R1.** With only `status` and `tran_id` given, all nine other fields are `None`.
- **R2.** All given values are kept exactly as passed — no status enum check, no conversion (e.g. `amount=Decimal("100.00")` stays `Decimal("100.00")`, `risk_level=5` is accepted).
- **R3.** Omitting `status` or `tran_id`, or passing an unknown keyword, raises `TypeError`.
- **R4.** Equal field values → instances compare equal.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| `status`/`tran_id` missing / unknown keyword | `TypeError` | standard dataclass message |

**Side effects:** none

---

## `SSLCommerzClient.init_session(req)`
**Shape:** helper (abstract)
**Persistence:** pure
**Visibility:** public (used by: `PaymentTransactionManager.initiate_payment`)

**Purpose:** Contract: start a checkout session at the gateway and return an `InitSessionResult` with the page URL to send the customer to.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `req` | `InitSessionRequest` | not checked by the base class |

**Returns:** base implementation never returns (see R3).

**Rules:**
- **R1.** `SSLCommerzClient` itself cannot be instantiated: `SSLCommerzClient()` raises `TypeError` (it has four abstract methods: `init_session`, `validate`, `query_by_tran_id`, `verify_signature`).
- **R2.** A subclass that overrides the other three methods but not `init_session` cannot be instantiated (`TypeError`); a subclass overriding all four can be instantiated and its own `init_session` is what runs.
- **R3.** Calling the base implementation (e.g. `super().init_session(req)` from a subclass) raises `NotImplementedError`.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| instantiate class missing the override | `TypeError` | standard ABC message |
| base implementation called | `NotImplementedError` | none (no message) |

**Side effects:** none

---

## `SSLCommerzClient.validate(val_id)`
**Shape:** helper (abstract)
**Persistence:** pure
**Visibility:** public (used by: `PaymentTransactionManager` callback handling; `MockSSLCommerzClient.query_by_tran_id`)

**Purpose:** Contract: the authoritative server-to-server check of a `val_id` received via redirect or IPN, returning a `ValidationResult`.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `val_id` | `str` | not checked by the base class |

**Returns:** base implementation never returns (see R2).

**Rules:**
- **R1.** A subclass that overrides the other three methods but not `validate` cannot be instantiated (`TypeError`). (Base-class non-instantiability: see `init_session` R1.)
- **R2.** Calling the base implementation via `super().validate(val_id)` raises `NotImplementedError`.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| instantiate class missing the override | `TypeError` | standard ABC message |
| base implementation called | `NotImplementedError` | none |

**Side effects:** none

---

## `SSLCommerzClient.query_by_tran_id(tran_id, val_id_hint=None)`
**Shape:** helper (abstract)
**Persistence:** pure
**Visibility:** public (used by: `PaymentTransactionManager` reconciliation sweep)

**Purpose:** Contract: look up a transaction by our `tran_id` (for transactions that never received a callback), returning a `ValidationResult`.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `tran_id` | `str` | not checked |
| `val_id_hint` | `str \| None` | default `None`; not checked |

**Returns:** base implementation never returns (see R2).

**Rules:**
- **R1.** A subclass that overrides the other three methods but not `query_by_tran_id` cannot be instantiated (`TypeError`).
- **R2.** Calling the base implementation via `super().query_by_tran_id(tran_id)` (with or without `val_id_hint`) raises `NotImplementedError`.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| instantiate class missing the override | `TypeError` | standard ABC message |
| base implementation called | `NotImplementedError` | none |

**Side effects:** none

---

## `SSLCommerzClient.verify_signature(payload)`
**Shape:** validator (abstract)
**Persistence:** pure
**Visibility:** public (used by: `POST /payments/ipn`)

**Purpose:** Contract: cheap first-pass check of an incoming IPN payload's `verify_sign`, returning `bool`; never a substitute for `validate`.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `payload` | `dict` | not checked |

**Returns:** base implementation never returns (see R2).

**Rules:**
- **R1.** A subclass that overrides the other three methods but not `verify_signature` cannot be instantiated (`TypeError`).
- **R2.** Calling the base implementation via `super().verify_signature(payload)` raises `NotImplementedError`.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| instantiate class missing the override | `TypeError` | standard ABC message |
| base implementation called | `NotImplementedError` | none |

**Side effects:** none

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 13–26 | required fields present / missing / unknown keyword | `InitSessionRequest` R1, R3 |
| 25–26 | `product_name` / `product_category` given vs default | `InitSessionRequest` R2 |
| — (missing today) | `value_a`..`value_d` given vs default `None` | `InitSessionRequest` R1a, R3a |
| 29–34 | optional fields given vs default `None` | `InitSessionResult` R1, R2, R3 |
| 37–52 | optional fields given vs default `None` | `ValidationResult` R1, R2, R3 |
| 55 | ABC with abstract methods → base not instantiable | `init_session` R1 |
| 59–63 | override missing / present; base body raises | `init_session` R2, R3 |
| 65–70 | override missing / present; base body raises | `validate` R1, R2 |
| 72–77 | override missing / present; base body raises; `val_id_hint` default | `query_by_tran_id` R1, R2 |
| 79–83 | override missing / present; base body raises | `verify_signature` R1, R2 |
