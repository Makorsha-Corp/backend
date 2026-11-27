# Test cases — `app/integrations/sslcommerz/client.py`

> **Spec:** `tests/unit/integrations/client.spec.md` (source commit e48a092)
> **Status:** READY
> **Revision:** 2 — re-run on unchanged spec (source commit e48a092, BUG-020 resolution already reflected in R1a/R3a). `client.verify.md` (verdict PASS, 6/6 mutants killed) lists no Findings and no Surviving mutants, so there are no `case-missing` items to address. Re-checked against the self-check list; all case IDs kept, none added, none retired.
> **Counts:** 37 cases · 34 expected-to-pass · 3 expected-to-fail (bugs) · 2 deferred

## Reviewer summary
- **Per callable:** `InitSessionRequest` 13 cases (3 bug) · `InitSessionResult` 6 · `ValidationResult` 7 · `SSLCommerzClient.init_session` 4 · `validate` 2 · `query_by_tran_id` 3 · `verify_signature` 2
- **Notable design choices:**
  - Pure Python module: no database rows, no mocks. The house "re-read the database" and "database unchanged" checks do not apply; every case asserts on the constructed object, the returned value, or the raised exception.
  - BUG-020 is split: REQ-08 (passing) guards that the ten required fields alone still construct; REQ-09..REQ-11 (xfail) cover the new `value_a`..`value_d` fields.
  - REQ-06 is one case parametrised over the ten required fields (each omitted in turn), so a single field silently becoming optional is caught.
  - INIT-01 also asserts the `TypeError` message names all four abstract methods (best-practice default, delegated by reviewer): Python's standard ABC message lists them in every supported version, and it pins the full abstract set on the base class.
  - `NotImplementedError` "no message" is asserted as `exc.args == ()` (best-practice default, delegated by reviewer).
- **Needs a decision:** None.

## Conventions for this module
- **IDs:** `SSLC` = client module. Callables: `REQ` = `InitSessionRequest`, `RES` = `InitSessionResult`, `VAL` = `ValidationResult`, `INIT` = `SSLCommerzClient.init_session`, `VALD` = `SSLCommerzClient.validate`, `QRY` = `SSLCommerzClient.query_by_tran_id`, `SIG` = `SSLCommerzClient.verify_signature`.
- **No database, no externals mocked, no time mocking.** Tests construct the dataclasses directly and define throwaway subclasses inside the test.
- **REQ_KW** = the ten required fields by keyword:
  `tran_id="TXN-0001"`, `amount=Decimal("10.005")`, `currency="BDT"`, `success_url="https://app.example/pay/success"`, `fail_url="https://app.example/pay/fail"`, `cancel_url="https://app.example/pay/cancel"`, `ipn_url="https://api.example/payments/ipn"`, `cus_name="Rahim Uddin"`, `cus_email="rahim@example.com"`, `cus_phone="01700000000"`.
  All ten values are distinct so a field swap is detectable.
- **FullClient** = a test subclass of `SSLCommerzClient` overriding all four methods:
  `init_session(req)` returns `InitSessionResult(status="SUCCESS", session_key="SK-1", gateway_page_url="https://gw.example/pay/SK-1")`;
  `validate(val_id)` returns `ValidationResult(status="VALID", tran_id="TXN-0001", val_id=val_id)`;
  `query_by_tran_id(tran_id, val_id_hint=None)` returns `ValidationResult(status="VALIDATED", tran_id=tran_id, val_id=val_id_hint)`;
  `verify_signature(payload)` returns `True`.
- **Missing<X>** = a test subclass overriding the three methods other than `X` (same bodies as FullClient).
- **SuperClient** = a test subclass overriding all four methods, each body being `return super().<same method>(<same args>)`.

## `InitSessionRequest`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| SSLC-REQ-01 | R1, R2 | happy | — | `InitSessionRequest(**REQ_KW)` | instance is an `InitSessionRequest`; each of the ten fields equals its REQ_KW value; `amount == Decimal("10.005")`, `type(amount) is Decimal`, `str(amount) == "10.005"` (not rounded); `product_name == "Workspace Subscription"`; `product_category == "subscription"` | pass |
| SSLC-REQ-02 | R1 | happy | — | construct positionally with the ten REQ_KW values in declared order (`tran_id, amount, currency, success_url, fail_url, cancel_url, ipn_url, cus_name, cus_email, cus_phone`) | each field equals the value at its position (e.g. `success_url == "https://app.example/pay/success"`, `cus_phone == "01700000000"`); defaults as in REQ-01 | pass |
| SSLC-REQ-03 | R1 | boundary | — | `InitSessionRequest(**{**REQ_KW, "amount": "10.00", "tran_id": "  TXN-0001  ", "cus_email": "NOT-AN-EMAIL", "currency": ""})` | no error; `amount == "10.00"` and `type(amount) is str`; `tran_id == "  TXN-0001  "` (untrimmed); `cus_email == "NOT-AN-EMAIL"`; `currency == ""` | pass |
| SSLC-REQ-04 | R2 | boundary | — | `InitSessionRequest(**REQ_KW, product_name="Pro Plan (12 months)", product_category="plan")` | `product_name == "Pro Plan (12 months)"`; `product_category == "plan"` | pass |
| SSLC-REQ-05 | R2 | boundary | — | `InitSessionRequest(**REQ_KW, product_name="Pro Plan")` | `product_name == "Pro Plan"`; `product_category == "subscription"` (the other default still applies) | pass |
| SSLC-REQ-06 | R3, Err row 1 | error | — | parametrised over each of the ten required field names: construct with REQ_KW minus that one field | raises `TypeError` in every one of the ten runs | pass |
| SSLC-REQ-07 | R3, Err row 1 | error | — | `InitSessionRequest(**REQ_KW, foo="x")` | raises `TypeError` | pass |
| SSLC-REQ-08 | R3a | boundary | — | `InitSessionRequest(**REQ_KW)` (no `value_*` given) | no error; returns an `InitSessionRequest` whose `tran_id == "TXN-0001"`. Must NOT assert anything about `value_a`..`value_d` (regression guard: holds today and after the BUG-020 fix) | pass |
| SSLC-REQ-09 | R1a [BUG-020] | bug | — | `InitSessionRequest(**REQ_KW, value_a="plan:pro;months:12", value_b="ws:42", value_c="coupon:NONE", value_d="src:web")` | no error; `value_a == "plan:pro;months:12"`, `value_b == "ws:42"`, `value_c == "coupon:NONE"`, `value_d == "src:web"`; `tran_id == "TXN-0001"` | xfail BUG-020 — fails today on: construction raises `TypeError` (unknown keyword `value_a`) |
| SSLC-REQ-10 | R1a [BUG-020] | bug | — | `InitSessionRequest(**REQ_KW)` | `value_a is None`, `value_b is None`, `value_c is None`, `value_d is None` | xfail BUG-020 — fails today on: `AttributeError` reading `value_a` |
| SSLC-REQ-11 | R1a [BUG-020] | bug | — | `InitSessionRequest(**REQ_KW, value_c="only-c")` | `value_c == "only-c"`; `value_a is None`, `value_b is None`, `value_d is None` | xfail BUG-020 — fails today on: construction raises `TypeError` (unknown keyword `value_c`) |
| SSLC-REQ-12 | R4 | boundary | — | build `a = InitSessionRequest(**REQ_KW)`, `b = InitSessionRequest(**REQ_KW)`, `c = InitSessionRequest(**{**REQ_KW, "amount": Decimal("10.006")})` | `a == b` is True; `a is not b`; `a == c` is False | pass |
| SSLC-REQ-13 | R4 | happy | `r = InitSessionRequest(**REQ_KW)` | `r.amount = Decimal("99.99")`; `r.product_name = "Changed"` | no error; `r.amount == Decimal("99.99")`; `r.product_name == "Changed"` | pass |

## `InitSessionResult`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| SSLC-RES-01 | R1 | happy | — | `InitSessionResult(status="SUCCESS")` | instance is an `InitSessionResult`; `status == "SUCCESS"`; `session_key is None`; `gateway_page_url is None`; `failed_reason is None` | pass |
| SSLC-RES-02 | R2 | happy | — | `InitSessionResult(status="FAILED", session_key="SK-9", gateway_page_url="https://gw.example/pay/SK-9", failed_reason="Store is de-active")` | each field equals the value passed | pass |
| SSLC-RES-03 | R2 | boundary | — | parametrised: `InitSessionResult(status="success")` and `InitSessionResult(status="")` | no error; `status` equals the value passed (`"success"` / `""`) | pass |
| SSLC-RES-04 | R3, Err row 1 | error | — | `InitSessionResult(session_key="SK-1")` (no status) | raises `TypeError` | pass |
| SSLC-RES-05 | R3, Err row 1 | error | — | `InitSessionResult(status="SUCCESS", foo="x")` | raises `TypeError` | pass |
| SSLC-RES-06 | R4 | boundary | — | `a = InitSessionResult(status="SUCCESS", session_key="SK-1")`, `b` identical, `c = InitSessionResult(status="SUCCESS", session_key="SK-2")` | `a == b` True; `a == c` False | pass |

## `ValidationResult`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| SSLC-VAL-01 | R1 | happy | — | `ValidationResult(status="VALID", tran_id="TXN-0001")` | instance is a `ValidationResult`; `status == "VALID"`; `tran_id == "TXN-0001"`; `val_id`, `amount`, `currency`, `risk_level`, `risk_title`, `bank_tran_id`, `card_type`, `verify_sign`, `verify_key` are all `None` (nine checks) | pass |
| SSLC-VAL-02 | R2 | happy | — | `ValidationResult(status="VALIDATED", tran_id="TXN-0002", val_id="VAL-77", amount=Decimal("100.00"), currency="BDT", risk_level=5, risk_title="Unusual", bank_tran_id="BANK-1", card_type="VISA-Dutch Bangla", verify_sign="sig-abc", verify_key="amount,currency,tran_id")` | each of the eleven fields equals the value passed; `type(amount) is Decimal` and `str(amount) == "100.00"` (trailing zeros kept); `risk_level == 5` | pass |
| SSLC-VAL-03 | R2 | boundary | — | `ValidationResult(status="NOT_A_STATUS", tran_id="TXN-0003")` | no error; `status == "NOT_A_STATUS"` | pass |
| SSLC-VAL-04 | R3, Err row 1 | error | — | `ValidationResult(tran_id="TXN-0001")` (no status) | raises `TypeError` | pass |
| SSLC-VAL-05 | R3, Err row 1 | error | — | `ValidationResult(status="VALID")` (no tran_id) | raises `TypeError` | pass |
| SSLC-VAL-06 | R3, Err row 1 | error | — | `ValidationResult(status="VALID", tran_id="TXN-0001", foo="x")` | raises `TypeError` | pass |
| SSLC-VAL-07 | R4 | boundary | — | `a = ValidationResult(status="VALID", tran_id="TXN-0001", amount=Decimal("5.00"))`, `b` identical, `c` same but `amount=Decimal("6.00")` | `a == b` True; `a == c` False | pass |

## `SSLCommerzClient.init_session`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| SSLC-INIT-01 | R1, Err row 1 | error | — | `SSLCommerzClient()` | raises `TypeError`; message contains each of `"init_session"`, `"validate"`, `"query_by_tran_id"`, `"verify_signature"` | pass |
| SSLC-INIT-02 | R2, Err row 1 | error | Missing`init_session` defined | instantiate it | raises `TypeError` | pass |
| SSLC-INIT-03 | R2 | happy | FullClient defined; `req = InitSessionRequest(**REQ_KW)` | `client = FullClient()`; call `client.init_session(req)`, `client.validate("VAL-1")`, `client.query_by_tran_id("TXN-5", val_id_hint="VAL-5")`, `client.verify_signature({"verify_sign": "x"})` | no error on instantiation; `isinstance(client, SSLCommerzClient)`; `init_session` returns `InitSessionResult(status="SUCCESS", session_key="SK-1", gateway_page_url="https://gw.example/pay/SK-1")`; `validate` returns `ValidationResult(status="VALID", tran_id="TXN-0001", val_id="VAL-1")`; `query_by_tran_id` returns `ValidationResult(status="VALIDATED", tran_id="TXN-5", val_id="VAL-5")`; `verify_signature` returns `True` | pass |
| SSLC-INIT-04 | R3, Err row 2 | error | SuperClient defined; `req = InitSessionRequest(**REQ_KW)` | `SuperClient().init_session(req)` | raises `NotImplementedError`; `exc.args == ()` (no message) | pass |

## `SSLCommerzClient.validate`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| SSLC-VALD-01 | R1, Err row 1 | error | Missing`validate` defined | instantiate it | raises `TypeError` | pass |
| SSLC-VALD-02 | R2, Err row 2 | error | SuperClient defined | `SuperClient().validate("VAL-1")` | raises `NotImplementedError`; `exc.args == ()` | pass |

## `SSLCommerzClient.query_by_tran_id`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| SSLC-QRY-01 | R1, Err row 1 | error | Missing`query_by_tran_id` defined | instantiate it | raises `TypeError` | pass |
| SSLC-QRY-02 | R2, Err row 2 | error | SuperClient whose override is `query_by_tran_id(self, tran_id, val_id_hint=None): return super().query_by_tran_id(tran_id)` | `SuperClient().query_by_tran_id("TXN-5")` | raises `NotImplementedError`; `exc.args == ()` | pass |
| SSLC-QRY-03 | R2, Err row 2 | boundary | SuperClient whose override passes both args: `return super().query_by_tran_id(tran_id, val_id_hint=val_id_hint)` | `SuperClient().query_by_tran_id("TXN-5", val_id_hint="VAL-5")` | raises `NotImplementedError` (not `TypeError` — the base accepts `val_id_hint` as a keyword); `exc.args == ()` | pass |

## `SSLCommerzClient.verify_signature`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| SSLC-SIG-01 | R1, Err row 1 | error | Missing`verify_signature` defined | instantiate it | raises `TypeError` | pass |
| SSLC-SIG-02 | R2, Err row 2 | error | SuperClient defined | `SuperClient().verify_signature({"verify_sign": "abc", "verify_key": "tran_id"})` | raises `NotImplementedError`; `exc.args == ()` | pass |

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| `InitSessionRequest` R1a [BUG-020] (manager half) | `PaymentTransactionManager.initiate_payment` | the transaction's `value_a`..`value_d` are passed into the `InitSessionRequest` handed to the client (assert on the request the mocked client receives) |
| Docstring contracts of `validate` / `query_by_tran_id` / `verify_signature` / `init_session` (what they return) | `MockSSLCommerzClient` (`mock_client.spec.md`) | return values and status mapping of the concrete client |

## Spec gaps
None.

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `InitSessionRequest` | R1 | SSLC-REQ-01, SSLC-REQ-02, SSLC-REQ-03 |
| `InitSessionRequest` | R1a [BUG-020] | SSLC-REQ-09, SSLC-REQ-10, SSLC-REQ-11; manager half deferred |
| `InitSessionRequest` | R2 | SSLC-REQ-01, SSLC-REQ-04, SSLC-REQ-05 |
| `InitSessionRequest` | R3 | SSLC-REQ-06, SSLC-REQ-07 |
| `InitSessionRequest` | R3a | SSLC-REQ-08 |
| `InitSessionRequest` | R4 | SSLC-REQ-12, SSLC-REQ-13 |
| `InitSessionRequest` | Err row 1 (missing / unknown kw) | SSLC-REQ-06, SSLC-REQ-07 |
| `InitSessionResult` | R1 | SSLC-RES-01 |
| `InitSessionResult` | R2 | SSLC-RES-02, SSLC-RES-03 |
| `InitSessionResult` | R3 | SSLC-RES-04, SSLC-RES-05 |
| `InitSessionResult` | R4 | SSLC-RES-06 |
| `InitSessionResult` | Err row 1 | SSLC-RES-04, SSLC-RES-05 |
| `ValidationResult` | R1 | SSLC-VAL-01 |
| `ValidationResult` | R2 | SSLC-VAL-02, SSLC-VAL-03 |
| `ValidationResult` | R3 | SSLC-VAL-04, SSLC-VAL-05, SSLC-VAL-06 |
| `ValidationResult` | R4 | SSLC-VAL-07 |
| `ValidationResult` | Err row 1 | SSLC-VAL-04, SSLC-VAL-05, SSLC-VAL-06 |
| `init_session` | R1 | SSLC-INIT-01 |
| `init_session` | R2 | SSLC-INIT-02, SSLC-INIT-03 |
| `init_session` | R3 | SSLC-INIT-04 |
| `init_session` | Err row 1 (TypeError) | SSLC-INIT-01, SSLC-INIT-02 |
| `init_session` | Err row 2 (NotImplementedError) | SSLC-INIT-04 |
| `validate` | R1 | SSLC-VALD-01 (positive side: SSLC-INIT-03) |
| `validate` | R2 | SSLC-VALD-02 |
| `validate` | Err rows 1, 2 | SSLC-VALD-01, SSLC-VALD-02 |
| `query_by_tran_id` | R1 | SSLC-QRY-01 (positive side: SSLC-INIT-03) |
| `query_by_tran_id` | R2 | SSLC-QRY-02, SSLC-QRY-03 |
| `query_by_tran_id` | Err rows 1, 2 | SSLC-QRY-01, SSLC-QRY-02, SSLC-QRY-03 |
| `verify_signature` | R1 | SSLC-SIG-01 (positive side: SSLC-INIT-03) |
| `verify_signature` | R2 | SSLC-SIG-02 |
| `verify_signature` | Err rows 1, 2 | SSLC-SIG-01, SSLC-SIG-02 |
| (all) | [BUG-020] | SSLC-REQ-09, SSLC-REQ-10, SSLC-REQ-11 |
