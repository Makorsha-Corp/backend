# Test cases — `app/integrations/sslcommerz/mock_client.py`

> **Spec:** `tests/unit/integrations/mock_client.spec.md` (source commit e48a092)
> **Status:** READY
> **Revision:** 2 — spec added BUG-583 (non-canonical tokens rejected: `_decode_val_id` R3 reworded, new R3a multi-dot, new R3b strict canonical base64 with non-canonical JSON still accepted; `validate` R1/R5 updated). Addressed verify F2 (case-missing, split point): the `extra-segment` row left MOCK-DEC-03 (it was parked as DISCREPANCY-1) and is now the xfail BUG-583 case MOCK-DEC-07 (and MOCK-VAL-11, MOCK-QRY-17); multi-dot tokens rejected today and after the fix are the pass case MOCK-DEC-08. Per the spec's note, mutants #43/#59 (split point only) are expected to survive until BUG-583 is fixed and are equivalent after. New: DEC-07..10, VAL-11, VAL-12, QRY-17.
> **Counts:** 69 cases · 53 expected-to-pass · 16 expected-to-fail (bugs) · 4 deferred

## Reviewer summary
- **Per callable:** `_sign` 10 · `init_session` 4 · `build_val_id` 7 (its BUG-580 rule R6 is tested through `query_by_tran_id`) · `_decode_val_id` 10 (4 bug) · `validate` 12 (3 bug) · `query_by_tran_id` 17 (8 bug) · `verify_signature` 9 (1 bug)
- **BUG-583 split (pass vs xfail):** per the spec's `Today` note, multi-dot tokens whose last segment is not the signature (`E.S1.`, `E.S1.x`) are rejected today and after the fix → pass (DEC-08). Tokens accepted today (`E.x.S1`, `E..S1`, and every non-canonical base64 form) → xfail (DEC-07, DEC-09, VAL-11, QRY-17). No pass case needs a multi-dot token to be accepted. The "JSON need not be canonical" half of R3b holds today and after → pass (DEC-10, VAL-12).
- **Notable design choices:**
  - Pure module: no database rows, no mocks. The usual "re-read the database" / "database unchanged" checks do not apply; every case asserts on the return value or raised exception. Only `settings` attributes are monkeypatched.
  - BUG-580 is split: passing cases guard what holds before and after the fix (fresh instance → `UNATTEMPTED`, hint for the asked `tran_id` wins, records are per instance, `validate`/hint lookups never record anything); xfail cases cover the recorded-outcome lookups (QRY-04, 05, 09, 11, 16).
  - A hint that validates for the asked `tran_id` beats the record (QRY-07, QRY-16), read straight from `query_by_tran_id` R2, which is unconditional.
  - Split point (first vs last `.`): after BUG-583 every accepted token has exactly one `.`, so the split point is not observable on any accepted token (spec note). `verify_sign` = text after the only `.` is checked by VAL-01.
  - `INVALID_TRANSACTION` / `UNATTEMPTED` results are asserted by whole-object equality with `ValidationResult(status=…, tran_id=…)`, so "every other field `None`" is checked field by field through dataclass equality (the defaults come from `client.spec.md`).
  - `init_session` URL defaults (`http://localhost:8000/api/v1`) are not asserted, because they depend on the environment. Every URL case sets `BACKEND_BASE_URL` / `API_V1_STR` explicitly.
  - TODO-001 (remove the mock or restrict it to non-production before launch) is noted but has no case: nothing in this spec depends on it.
- **Needs a decision:** None.

## Conventions for this module
- **IDs:** `MOCK` = mock_client. Callables: `SIGN` = `_sign` (module function), `INIT` = `init_session`, `BVI` = `build_val_id`, `DEC` = `_decode_val_id`, `VAL` = `validate`, `QRY` = `query_by_tran_id`, `VSIG` = `verify_signature`.
- **No database, no externals mocked, no time mocking.** Each test instantiates `MockSSLCommerzClient()` directly. `A`, `B`, `C` = three separate fresh instances created inside the test (a fresh instance has an empty record).
- **Settings (monkeypatched on `app.core.config.settings` in every test):** `SECRET_KEY = K1 = "unit-test-secret-K1"`, `BACKEND_BASE_URL = "http://api.test:9000"`, `API_V1_STR = "/api/v9"`. `K2 = "unit-test-secret-K2"` is a second key used where a case says so.
- **H(key, msg)** = `hmac.new(key.encode("utf-8"), msg.encode("utf-8"), hashlib.sha256).hexdigest()`, computed independently in the test.
- **ENC(obj, compact=True)** = `base64.urlsafe_b64encode(json.dumps(obj, separators=(",", ":")).encode()).decode()`. **TOK(obj, sig)** = `ENC(obj) + "." + sig` (for hand-built tokens, the JSON formatting does not matter because the signature covers the field values, not the bytes).
- **T1** = `"TXN-ABC-001"`, **T2** = `"TXN-XYZ-002"`.
- **P1** = `{"tran_id": T1, "amount": "10.00", "currency": "BDT", "status": "VALID", "risk_level": 0}`; **S1** = `H(K1, "VALID|TXN-ABC-001|10.00|BDT|0")`.
- **mint(inst, tran_id, amount, status, currency="BDT", risk_level=0)** = `inst.build_val_id(tran_id=…, amount=…, currency=…, status=…, risk_level=…)`.
- **INV** = `ValidationResult(status="INVALID_TRANSACTION", tran_id="")`. **UNATT(t)** = `ValidationResult(status="UNATTEMPTED", tran_id=t)`.
- **VKEY** = `"status,tran_id,amount,currency,risk_level"`.
- **REQ(tran_id, **overrides)** = `InitSessionRequest` built with the ten required fields of `client.cases.md` REQ_KW (`amount=Decimal("10.005")`, `currency="BDT"`, success/fail/cancel/ipn URLs, `cus_name`, `cus_email`, `cus_phone`), with `tran_id` and any overrides replaced.
- **SK(t)** = `base64.urlsafe_b64encode(hashlib.sha256(t.encode("utf-8")).digest()).decode().rstrip("=")`.
- **Malformed-payload set MAL** (hits `_decode_val_id` R5): `TOK({}, "0"*64)` (= `"e30=.x"` style), `TOK({"status": "VALID"}, "0"*64)`, `TOK([1], "0"*64)`, `TOK(None, "0"*64)`, `TOK(1, "0"*64)`, `TOK({k: v for k, v in P1.items() if k != "risk_level"}, "0"*64)`, plus the literal `"e30=.x"`.
- **Non-ASCII signature NAS** (hits R6): `ENC(P1) + "." + "é" + S1[1:]`.
- **Bad-amount token BAD_AMT** (hits `validate` R1b): `TOK({"tran_id": T1, "amount": "abc", "currency": "BDT", "status": "VALID", "risk_level": 0}, H(K1, "VALID|TXN-ABC-001|abc|BDT|0"))`.
- **E** = `ENC(P1)` = `"eyJ0cmFuX2lkIjoiVFhOLUFCQy0wMDEiLCJhbW91bnQiOiIxMC4wMCIsImN1cnJlbmN5IjoiQkRUIiwic3RhdHVzIjoiVkFMSUQiLCJyaXNrX2xldmVsIjowfQ=="` (124 chars, ends `fQ==`).
- **Multi-dot set MD_OK** (accepted today, [BUG-583] R3a): `E + ".x." + S1`, `E + ".." + S1`. **Multi-dot set MD_REJ** (rejected today and after the fix): `E + "." + S1 + "."`, `E + "." + S1 + ".x"`, `"a.b.c"`.
- **Non-canonical base64 set NCB** ([BUG-583] R3b; each decodes to correctly signed bytes and is accepted today): `E[:10] + "\n" + E[10:] + "." + S1` (newline inserted); `E[:10] + " " + E[10:] + "." + S1` (space inserted); `E + "AAAA" + "." + S1` (data after padding); `E[:-3] + "R==" + "." + S1` (last data char `Q`→`R`, non-zero unused low bits); `tok_dash.replace("-", "+")` where `tok_dash = mint(A, "TXN->>>?", Decimal("10.00"), "VALID")` (its encoded part contains `-`; the signature part is hex so unaffected); `enc_us.replace("_", "/") + "." + sig_us` where `enc_us, sig_us` = the two parts of `mint(A, "TXN-??", Decimal("10.00"), "VALID")` (its encoded part contains `_`).
- **Non-canonical JSON set NCJ** (R3b, still accepted): `base64.urlsafe_b64encode(json.dumps(P1).encode()).decode() + "." + S1` (default `", "`/`": "` separators); `ENC({"risk_level": 0, "status": "VALID", "currency": "BDT", "amount": "10.00", "tran_id": T1}) + "." + S1` (reversed key order); `ENC({**P1, "extra": "x"}) + "." + S1` (extra key).
- **FORM(r)** (built from a `ValidationResult` r, as the mock-gateway endpoint does) = `{"status": r.status, "tran_id": r.tran_id, "amount": str(r.amount), "currency": r.currency, "risk_level": str(r.risk_level), "verify_sign": r.verify_sign, "val_id": r.val_id, "verify_key": r.verify_key}`.
- **F1** = `{"status": "VALID", "tran_id": T1, "amount": "10.00", "currency": "BDT", "risk_level": "0", "verify_sign": S1, "val_id": "VAL-ANY", "verify_key": VKEY}`.
- Race simulations: none.

## `_sign(payload)`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| MOCK-SIGN-01 | R1 | happy | SECRET_KEY = K1 | `_sign(P1)` | returns a `str` equal to S1; matches `^[0-9a-f]{64}$` | pass |
| MOCK-SIGN-02 | R1 | boundary | SECRET_KEY = `"clé-secrète-ü"` (non-ASCII) | `_sign(P1)` | equals `H("clé-secrète-ü", "VALID|TXN-ABC-001|10.00|BDT|0")` (key UTF-8 encoded) | pass |
| MOCK-SIGN-03 | R2 | boundary | K1 | `_sign({**P1, "val_id": "VAL-9", "foo": 1, "verify_key": "x"})` | equals S1 | pass |
| MOCK-SIGN-04 | R1, R2 | boundary | K1; parametrised over the five fields: `status→"FAILED"`, `tran_id→T2`, `amount→"11.00"`, `currency→"USD"`, `risk_level→1` | `_sign({**P1, field: new})` | result != S1 and equals `H(K1, <message with that one value replaced, same field order>)` | pass |
| MOCK-SIGN-05 | R3 | boundary | K1 | `_sign(P1)` and `_sign({**P1, "risk_level": "0"})` | the two results are equal (both S1) | pass |
| MOCK-SIGN-06 | R3 | boundary | K1 | `_sign(P1)` and `_sign({**P1, "amount": "10.0"})` | results differ; the second equals `H(K1, "VALID|TXN-ABC-001|10.0|BDT|0")` | pass |
| MOCK-SIGN-07 | R3 | boundary | K1 | `_sign({**P1, "currency": None})` | equals `H(K1, "VALID|TXN-ABC-001|10.00|None|0")` | pass |
| MOCK-SIGN-08 | R4 | boundary | compute `s1 = _sign(P1)` with K1, then set SECRET_KEY = K2 | `_sign(P1)` | result != s1; equals `H(K2, "VALID|TXN-ABC-001|10.00|BDT|0")` (key read at call time) | pass |
| MOCK-SIGN-09 | Err row 1 | error | K1; parametrised over the five keys | `_sign(P1 without that key)` | raises `KeyError` whose `args[0]` is the missing key name | pass |
| MOCK-SIGN-10 | Err row 2 | error | K1; parametrised: `[1, 2]`, `None`, `42` | `_sign(value)` | raises `TypeError` | pass |

## `MockSSLCommerzClient.init_session(req)`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| MOCK-INIT-01 | R1, R2, R3 | happy | settings as in Conventions; A | `A.init_session(REQ("TXN-ABC-001"))` | returns an `InitSessionResult`; `status == "SUCCESS"`; `failed_reason is None`; `session_key == SK("TXN-ABC-001")`, `len == 43`, matches `^[A-Za-z0-9_-]{43}$`; `gateway_page_url == "http://api.test:9000/api/v9/payments/mock-gateway/TXN-ABC-001"` | pass |
| MOCK-INIT-02 | R1 | boundary | A; parametrised requests: `REQ(T1, amount=Decimal("0"))`; `REQ(T1, amount=Decimal("-5.00"), currency="", success_url="", fail_url="", cancel_url="", ipn_url="", cus_name="", cus_email="", cus_phone="")` | `A.init_session(req)` | `status == "SUCCESS"`; `failed_reason is None`; `session_key == SK(T1)`; `gateway_page_url == "http://api.test:9000/api/v9/payments/mock-gateway/TXN-ABC-001"` (other fields ignored) | pass |
| MOCK-INIT-03 | R2 | boundary | A and B | `A.init_session(REQ(T1))`, `B.init_session(REQ(T1, amount=Decimal("99.00"), currency="USD"))`, `A.init_session(REQ(T2))`, `A.init_session(REQ(""))` | first two `session_key`s are equal (== SK(T1)); T2's key == SK(T2) and != SK(T1); `""`'s key == SK("") and has length 43 | pass |
| MOCK-INIT-04 | R3 | boundary | A; BACKEND_BASE_URL = `"https://pay.example.org"`, API_V1_STR = `"/v2"` | `A.init_session(REQ("a b/c?d=é"))` | `gateway_page_url == "https://pay.example.org/v2/payments/mock-gateway/a b/c?d=é"` exactly (no URL-encoding); `session_key == SK("a b/c?d=é")` | pass |

## `MockSSLCommerzClient.build_val_id(...)`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| MOCK-BVI-01 | R1, R2 | happy | A, K1 | `A.build_val_id(tran_id=T1, amount=Decimal("10.00"), currency="BDT", status="VALID", risk_level=1)` | returns `str` equal to `ENC({"tran_id": T1, "amount": "10.00", "currency": "BDT", "status": "VALID", "risk_level": 1}) + "." + H(K1, "VALID|TXN-ABC-001|10.00|BDT|1")`; the decoded JSON bytes are exactly `{"tran_id":"TXN-ABC-001","amount":"10.00","currency":"BDT","status":"VALID","risk_level":1}` (key order, no spaces, `risk_level` a JSON number) | pass |
| MOCK-BVI-02 | R1 | boundary | A, K1; parametrised tran_id `"TXN->>>?"` (URL-safe `-` in output) and `"TXN-??"` (URL-safe `_` in output) | `mint(A, tran_id, Decimal("10.00"), "VALID")` | encoded part (before the `.`) == `ENC({"tran_id": tran_id, "amount": "10.00", "currency": "BDT", "status": "VALID", "risk_level": 0})`; it ends with `=` (padding kept); contains `-` (first param) / `_` (second param); contains no `+` and no `/` | pass |
| MOCK-BVI-03 | R1 | boundary | A, K1; parametrised amount `Decimal("1E+2")`, `Decimal("10.00")`, `Decimal("10.0")` | `mint(A, T1, amount, "VALID")`, decode the encoded part with `base64.urlsafe_b64decode` + `json.loads` | `payload["amount"] == str(amount)` (`"1E+2"`, `"10.00"`, `"10.0"`) and is a `str`; `payload["risk_level"] == 0` and `type(...) is int` | pass |
| MOCK-BVI-04 | R3 | happy | A, K1 | `A.build_val_id(tran_id=T1, amount=Decimal("10.00"), currency="BDT", status="VALID")` (no risk_level) and the same call with `risk_level=0` | both tokens identical; decoded `risk_level == 0` | pass |
| MOCK-BVI-05 | R4 | happy | A and B, K1 | `tok = mint(A, T1, Decimal("250.50"), "FAILED", currency="USD", risk_level=0)`; `B.validate(tok)` | equals `ValidationResult(status="FAILED", tran_id=T1, val_id=tok, amount=Decimal("250.50"), currency="USD", risk_level=0, risk_title="Safe", bank_tran_id="MOCKBANK-TXN-ABC-001", card_type="mock-visa", verify_sign=tok.rsplit(".", 1)[1], verify_key=VKEY)`; `str(amount) == "250.50"` | pass |
| MOCK-BVI-06 | R5 | boundary | A and B, K1 | `t1 = mint(A, T1, Decimal("10.00"), "VALID")`, `t2 = mint(A, T1, Decimal("10.00"), "VALID")`, `t3 = mint(B, T1, Decimal("10.00"), "VALID")`, `t4 = mint(A, T1, Decimal("10.01"), "VALID")` | `t1 == t2 == t3`; `t4 != t1` | pass |
| MOCK-BVI-07 | R2 | boundary | A; mint `ta` with K1, then set SECRET_KEY = K2 and mint `tb` with the same inputs (`T1, Decimal("10.00"), "VALID"`) | split both at the `.` | encoded parts equal; signature parts differ; `tb`'s signature == `H(K2, "VALID|TXN-ABC-001|10.00|BDT|0")` | pass |

`build_val_id` R6 [BUG-580] and its side effect are tested through `query_by_tran_id`: MOCK-QRY-04, 05, 09, 11, 16 (xfail) and MOCK-QRY-02, 03 (pass).

## `MockSSLCommerzClient._decode_val_id(val_id)`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| MOCK-DEC-01 | R1 | happy | A, K1; `tok = mint(A, T1, Decimal("10.00"), "VALID", risk_level=1)` | `A._decode_val_id(tok)` | returns a dict equal to `{"tran_id": T1, "amount": "10.00", "currency": "BDT", "status": "VALID", "risk_level": 1}` | pass |
| MOCK-DEC-02 | R2 | boundary | A, K1; parametrised `""`, `"abcdef"`, `ENC(P1) + S1` (valid parts, dot removed) | `A._decode_val_id(value)` | returns `None` (no exception) | pass |
| MOCK-DEC-03 | R3 | error | A, K1; parametrised (each has exactly one `.`): `"a." + S1` (undecodable base64, one char); `"!!!.abc"`; `E[:-2] + "." + S1` (incorrect padding: `==` removed); `base64.urlsafe_b64encode(b"\xff\xfe\xfd").decode() + "." + S1` (not UTF-8); `base64.urlsafe_b64encode(b"not json").decode() + "." + S1` (not JSON) | `A._decode_val_id(value)` | returns `None` (no exception) | pass |
| MOCK-DEC-04 | R4 | error | A, K1; `tok = mint(A, T1, Decimal("500.00"), "VALID")`, `sig = tok.rsplit(".",1)[1]`; parametrised: tampered `TOK({**P1, "amount": "5.00"}, sig)` (P1 with amount changed, original sig of 500.00 payload re-used as in the token); empty signature `ENC(P1) + "."`; `TOK(P1, "0"*64)`; `TOK(P1, S1.upper())`; a token minted with K2 then validated with K1 restored | `A._decode_val_id(value)` | returns `None` | pass |
| MOCK-DEC-05 | R5 [BUG-581] | bug | A, K1; parametrised over MAL | `A._decode_val_id(value)` | returns `None`; no exception raised | xfail BUG-581 — fails today on: raises `KeyError` / `TypeError` |
| MOCK-DEC-06 | R6 [BUG-581] | bug | A, K1 | `A._decode_val_id(NAS)` | returns `None`; no exception raised | xfail BUG-581 — fails today on: raises `TypeError` |
| MOCK-DEC-07 | R3a [BUG-583] | bug | A, K1; parametrised over MD_OK | `A._decode_val_id(value)` | returns `None` | xfail BUG-583 — fails today on: returns the P1 payload dict instead of `None` |
| MOCK-DEC-08 | R3a (rejected today and after) | boundary | A, K1; parametrised over MD_REJ | `A._decode_val_id(value)` | returns `None` (no exception) | pass |
| MOCK-DEC-09 | R3b [BUG-583] | bug | A, K1; parametrised over NCB | `A._decode_val_id(value)` | returns `None` | xfail BUG-583 — fails today on: returns the decoded payload dict instead of `None` |
| MOCK-DEC-10 | R3b (JSON need not be canonical), R1 | boundary | A, K1; parametrised over NCJ | `d = A._decode_val_id(value)` | `d` is a dict (not `None`); `d["tran_id"] == T1`, `d["amount"] == "10.00"`, `d["currency"] == "BDT"`, `d["status"] == "VALID"`, `d["risk_level"] == 0` | pass |

## `MockSSLCommerzClient.validate(val_id)`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| MOCK-VAL-01 | R2, R3, R4, R5 | happy | A, K1; `tok = mint(A, T1, Decimal("10.00"), "VALID", risk_level=0)` | `A.validate(tok)` | equals `ValidationResult(status="VALID", tran_id=T1, val_id=tok, amount=Decimal("10.00"), currency="BDT", risk_level=0, risk_title="Safe", bank_tran_id="MOCKBANK-TXN-ABC-001", card_type="mock-visa", verify_sign=S1, verify_key=VKEY)`; `type(amount) is Decimal`, `str(amount) == "10.00"`; `verify_sign == tok.rsplit(".", 1)[1]`; `val_id == tok` (the input string unchanged) | pass |
| MOCK-VAL-02 | R2, R4 | happy | A, K1; parametrised status `"FAILED"`, `"CANCELLED"`; tran_id T2; amount `Decimal("1E+2")`; currency `"USD"` | `A.validate(mint(A, T2, Decimal("1E+2"), status, currency="USD"))` | `status` == the param; `tran_id == T2`; `amount == Decimal("1E+2")` and `str(amount) == "1E+2"`; `currency == "USD"`; `bank_tran_id == "MOCKBANK-TXN-XYZ-002"`; `card_type == "mock-visa"` | pass |
| MOCK-VAL-03 | R3 | boundary | A, K1 | `A.validate(mint(A, T1, Decimal("10.00"), "VALID", risk_level=1))` | `risk_level == 1`; `risk_title == "Risky"`; `status == "VALID"` | pass |
| MOCK-VAL-04 | R3 | boundary | A, K1 | `A.validate(mint(A, T1, Decimal("10.00"), "VALID", risk_level=2))` | `risk_level == 2`; `risk_title == "Safe"` | pass |
| MOCK-VAL-05 | R1 | error | A, K1; parametrised over every input of MOCK-DEC-02, MOCK-DEC-03, MOCK-DEC-04 and MOCK-DEC-08 (MD_REJ) | `A.validate(value)` | returns a value equal to INV (status `"INVALID_TRANSACTION"`, tran_id `""`, all nine other fields `None`); no exception | pass |
| MOCK-VAL-06 | R1a [BUG-581] | bug | A, K1; parametrised over MAL and NAS | `A.validate(value)` | returns a value equal to INV; no exception raised | xfail BUG-581 — fails today on: raises `KeyError` / `TypeError` |
| MOCK-VAL-07 | R1b [BUG-581] | bug | A, K1 | `A.validate(BAD_AMT)` | returns a value equal to INV; no exception raised | xfail BUG-581 — fails today on: raises `decimal.InvalidOperation` |
| MOCK-VAL-08 | R6 | boundary | A, K1; `tok = mint(A, T1, Decimal("10.00"), "VALID")` | call `A.validate(tok)` three times | all three results are equal to each other; each has `status == "VALID"` (never `"VALIDATED"`) | pass |
| MOCK-VAL-09 | R7; `verify_signature` R5 | happy | A, K1; parametrised risk_level 0 and 1 | `r = A.validate(mint(A, T1, Decimal("10.00"), "VALID", risk_level=rl))`; `A.verify_signature(FORM(r))` | `verify_signature` returns `True` (identity `is True`) | pass |
| MOCK-VAL-11 | R1 [BUG-583] (R3a/R3b inputs) | bug | A, K1; parametrised over MD_OK and NCB | `A.validate(value)` | returns a value equal to INV | xfail BUG-583 — fails today on: returns a `VALID` result instead of INV |
| MOCK-VAL-12 | R2, R5 (non-canonical JSON) | boundary | A, K1; parametrised over NCJ | `r = A.validate(value)` | `r.status == "VALID"`; `r.tran_id == T1`; `r.amount == Decimal("10.00")`; `r.currency == "BDT"`; `r.risk_level == 0`; `r.risk_title == "Safe"`; `r.val_id == value`; `r.verify_sign == S1`; `r.verify_key == VKEY` | pass |
| MOCK-VAL-10 | R2; side effects none | side-effect | A and C, K1; `tok = mint(A, T1, Decimal("10.00"), "VALID")` | `rc = C.validate(tok)`; then `C.query_by_tran_id(T1)` | `rc == A.validate(tok)` (validation does not depend on the minting instance); the query returns a value equal to UNATT(T1) (validating does not record anything) | pass |

## `MockSSLCommerzClient.query_by_tran_id(tran_id, val_id_hint=None)`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| MOCK-QRY-01 | R1 | happy | fresh A, K1; parametrised: no hint argument, `val_id_hint=None`, `val_id_hint=""` | `A.query_by_tran_id(T1, …)` | equals UNATT(T1) (all nine other fields `None`) | pass |
| MOCK-QRY-02 | R1; `build_val_id` R6 (per-instance) | isolation | K1; `mint(A, T1, Decimal("500.00"), "VALID")`; fresh B | `B.query_by_tran_id(T1)` | equals UNATT(T1) | pass |
| MOCK-QRY-03 | R1, R1a (other tran_id) | isolation | K1; A mints only for T2 (`mint(A, T2, Decimal("500.00"), "VALID")`) | `A.query_by_tran_id(T1)` | equals UNATT(T1) | pass |
| MOCK-QRY-04 | R1a [BUG-580]; `build_val_id` R6 | bug | K1; A; parametrised status `"VALID"` / `"FAILED"` / `"CANCELLED"` × hint `None` / `""`; `tok = mint(A, T1, Decimal("500.00"), status)` | `A.query_by_tran_id(T1, val_id_hint=hint)` | equals `A.validate(tok)`; `status` == the param; `amount == Decimal("500.00")`; `val_id == tok` | xfail BUG-580 — fails today on: returns UNATT(T1) (`status == "UNATTEMPTED"`) |
| MOCK-QRY-05 | R1a [BUG-580]; `build_val_id` R6 (latest wins) | bug | K1; A; `tok1 = mint(A, T1, Decimal("500.00"), "VALID")`, then `tok2 = mint(A, T1, Decimal("500.00"), "CANCELLED")` | `A.query_by_tran_id(T1)` | equals `A.validate(tok2)`; `status == "CANCELLED"`; `val_id == tok2` | xfail BUG-580 — fails today on: returns UNATT(T1) |
| MOCK-QRY-06 | R2 | happy | K1; `hint = mint(B, T1, Decimal("75.25"), status)` parametrised status `"VALID"` / `"FAILED"` / `"CANCELLED"`; fresh C | `C.query_by_tran_id(T1, hint)` | equals `C.validate(hint)`; `status` == the param; `tran_id == T1`; `amount == Decimal("75.25")` | pass |
| MOCK-QRY-07 | R2 (hint beats record) | boundary | K1; A; `tok1 = mint(A, T1, Decimal("500.00"), "FAILED")`, `tok2 = mint(A, T1, Decimal("500.00"), "VALID")` | `A.query_by_tran_id(T1, tok1)` | equals `A.validate(tok1)`; `status == "FAILED"`; `val_id == tok1` | pass |
| MOCK-QRY-08 | R3 | boundary | K1; `hint = mint(B, T2, Decimal("500.00"), "VALID")`; fresh C | `C.query_by_tran_id(T1, hint)` | equals UNATT(T1) | pass |
| MOCK-QRY-09 | R3a [BUG-580] | bug | K1; `tok = mint(A, T1, Decimal("500.00"), "VALID")`; `hint = mint(B, T2, Decimal("20.00"), "VALID")` | `A.query_by_tran_id(T1, hint)` | equals `A.validate(tok)`; `tran_id == T1`; `status == "VALID"` | xfail BUG-580 — fails today on: returns UNATT(T1) |
| MOCK-QRY-10 | R4 (no record) | error | K1; fresh C; parametrised hint: `"abcdef"`, `TOK(P1, "0"*64)`, a T1 token minted under K2 (K1 restored before the query) | `C.query_by_tran_id(T1, hint)` | equals UNATT(T1) | pass |
| MOCK-QRY-11 | R4 [BUG-580] (record present) | bug | K1; `tok = mint(A, T1, Decimal("500.00"), "VALID")`; parametrised hint: `"abcdef"`, `TOK(P1, "0"*64)` | `A.query_by_tran_id(T1, hint)` | equals `A.validate(tok)`; `status == "VALID"` | xfail BUG-580 — fails today on: returns UNATT(T1) |
| MOCK-QRY-12 | R4 [BUG-580] (asked `""`) | bug | K1; fresh C; parametrised hint: `"abcdef"`, a T1 token minted under K2 (K1 restored) | `C.query_by_tran_id("", hint)` | equals UNATT("") (`status == "UNATTEMPTED"`, `tran_id == ""`) | xfail BUG-580 — fails today on: returns INV (`status == "INVALID_TRANSACTION"`) |
| MOCK-QRY-13 | R1 (asked `""`, no hint) | boundary | K1; fresh C | `C.query_by_tran_id("")` | equals UNATT("") | pass |
| MOCK-QRY-14 | R5 [BUG-581] | bug | K1; fresh C; parametrised hint over MAL, NAS and BAD_AMT | `C.query_by_tran_id(T1, hint)` | equals UNATT(T1); no exception raised | xfail BUG-581 — fails today on: `KeyError` / `TypeError` / `decimal.InvalidOperation` propagates |
| MOCK-QRY-15 | side effects none | side-effect | K1; `hint = mint(B, T1, Decimal("500.00"), "VALID")`; fresh C | `r1 = C.query_by_tran_id(T1, hint)`; then `r2 = C.query_by_tran_id(T1)` | `r1 == C.validate(hint)` with `status == "VALID"`; `r2` equals UNATT(T1) (a hint lookup does not record anything) | pass |
| MOCK-QRY-16 | side effects none; R1a [BUG-580] | bug | K1; `tok = mint(A, T1, Decimal("500.00"), "VALID")`; `other = mint(B, T1, Decimal("500.00"), "FAILED")` | `r0 = A.query_by_tran_id(T2)`; `r1 = A.query_by_tran_id(T1, other)`; `r2 = A.query_by_tran_id(T1)` | `r0` equals UNATT(T2); `r1 == A.validate(other)` (`status == "FAILED"`); `r2 == A.validate(tok)` (`status == "VALID"`: the record was not replaced by the hint lookup) | xfail BUG-580 — fails today on: `r2` is UNATT(T1) |
| MOCK-QRY-17 | R4 via `validate` R1 [BUG-583] (no record) | bug | K1; fresh C; parametrised hint over MD_OK and the NCB rows built from P1 (newline, space, data after padding, low bits) | `C.query_by_tran_id(T1, hint)` | equals UNATT(T1) | xfail BUG-583 — fails today on: returns a `VALID` result for T1 (the non-canonical hint is accepted) |

## `MockSSLCommerzClient.verify_signature(payload)`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| MOCK-VSIG-01 | R3 | happy | A, K1 | `A.verify_signature(F1)` | returns `True` (`is True`) | pass |
| MOCK-VSIG-02 | R3 | boundary | A, K1 | `A.verify_signature({**F1, "risk_level": 0})` (int) | returns `True` | pass |
| MOCK-VSIG-03 | R3 | error | A, K1; parametrised one field changed: `status "FAILED"`, `tran_id T2`, `amount "10.0"`, `currency "USD"`, `risk_level "1"` | `A.verify_signature({**F1, field: new})` | returns `False` (`is False`) | pass |
| MOCK-VSIG-04 | R3 (unsigned fields) | boundary | A, K1; parametrised: `val_id` changed to `"VAL-OTHER"`; `val_id` removed; `verify_key` changed to `"x"`; extra key `"bank_tran_id": "B-1"` added | `A.verify_signature(modified F1)` | returns `True` | pass |
| MOCK-VSIG-05 | R3 | error | A, K1; parametrised `verify_sign`: `S1.upper()`, `"0"*64`, `H(K2, "VALID|TXN-ABC-001|10.00|BDT|0")`, `S1[:-1]` | `A.verify_signature({**F1, "verify_sign": sig})` | returns `False` | pass |
| MOCK-VSIG-06 | R1 | error | A, K1; parametrised: `verify_sign` removed; `verify_sign=None`; `verify_sign=""` | `A.verify_signature(modified F1)` | returns `False` | pass |
| MOCK-VSIG-07 | R2 | error | A, K1; parametrised over the five fields × {removed, set to `None`} (10 runs) | `A.verify_signature(modified F1)` (verify_sign stays S1) | returns `False`; no exception | pass |
| MOCK-VSIG-08 | R2 (empty string present) | boundary | A, K1 | `A.verify_signature({**F1, "currency": "", "verify_sign": H(K1, "VALID|TXN-ABC-001|10.00||0")})` | returns `True` | pass |
| MOCK-VSIG-09 | R4 [BUG-582] | bug | A, K1; parametrised `verify_sign`: `"é"`, `"é" + S1[1:]`, `123`, `["x"]` | `A.verify_signature({**F1, "verify_sign": value})` | returns `False`; no exception raised | xfail BUG-582 — fails today on: raises `TypeError` |

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| Q2 / `validate` R1a (endpoint half) | `POST /payments/success`, `/payments/fail`, `/payments/ipn` (via `PaymentTransactionManager.finalize_from_gateway`) | a malformed `val_id` such as `e30=.x` is rejected as invalid, never a 500 |
| Q3 / `verify_signature` R4 (endpoint half) | `POST /payments/ipn` | `verify_sign=é` with all fields present → 400 "Invalid IPN signature", not 500 |
| BUG-580 / BUG-031 (sweep half) | `PaymentTransactionManager.reconcile_stuck_transactions` | a transaction completed "Success" on the mock page with no callback is not marked `EXPIRED` by the sweep |
| BUG-580 (single instance assumption) | `get_sslcommerz_client()` | returns the same `MockSSLCommerzClient` instance on repeated calls when `SSLCOMMERZ_MOCK_MODE` is true (the record lives in that instance) |

## Spec gaps
None.

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `_sign` | R1 | MOCK-SIGN-01, 02, 04 |
| `_sign` | R2 | MOCK-SIGN-03, 04 |
| `_sign` | R3 | MOCK-SIGN-05, 06, 07 |
| `_sign` | R4 | MOCK-SIGN-08 |
| `_sign` | Err: missing key → KeyError | MOCK-SIGN-09 |
| `_sign` | Err: non-mapping → TypeError | MOCK-SIGN-10 |
| `init_session` | R1 | MOCK-INIT-01, 02 |
| `init_session` | R2 | MOCK-INIT-01, 03, 04 |
| `init_session` | R3 | MOCK-INIT-01, 02, 04 |
| `build_val_id` | R1 | MOCK-BVI-01, 02, 03 |
| `build_val_id` | R2 | MOCK-BVI-01, 07 |
| `build_val_id` | R3 | MOCK-BVI-04 |
| `build_val_id` | R4 | MOCK-BVI-05 |
| `build_val_id` | R5 | MOCK-BVI-06 |
| `build_val_id` | R6 [BUG-580] / side effect | MOCK-QRY-04, 05, 09, 11, 16 (xfail); MOCK-QRY-02, 03 (pass) |
| `_decode_val_id` | R1 | MOCK-DEC-01 |
| `_decode_val_id` | R2 | MOCK-DEC-02 |
| `_decode_val_id` | R3 | MOCK-DEC-03 |
| `_decode_val_id` | R3a [BUG-583] | MOCK-DEC-07 (xfail), MOCK-DEC-08 (pass) |
| `_decode_val_id` | R3b [BUG-583] | MOCK-DEC-09 (xfail); MOCK-DEC-10 (pass, JSON need not be canonical) |
| `_decode_val_id` | R4 | MOCK-DEC-04 |
| `_decode_val_id` | R5 [BUG-581] | MOCK-DEC-05 |
| `_decode_val_id` | R6 [BUG-581] | MOCK-DEC-06 |
| `validate` | R1 | MOCK-VAL-05; MOCK-VAL-11 (xfail, BUG-583 inputs) |
| `validate` | R1a [BUG-581] | MOCK-VAL-06 |
| `validate` | R1b [BUG-581] | MOCK-VAL-07 |
| `validate` | R2 | MOCK-VAL-01, 02, 10, 12; MOCK-BVI-05 |
| `validate` | R3 | MOCK-VAL-01, 03, 04 |
| `validate` | R4 | MOCK-VAL-01, 02 |
| `validate` | R5 | MOCK-VAL-01, 12; MOCK-VAL-11 (multi-dot rejected) |
| `validate` | R6 | MOCK-VAL-08 |
| `validate` | R7 | MOCK-VAL-09 |
| `validate` | Side effects none | MOCK-VAL-10 |
| `query_by_tran_id` | R1 | MOCK-QRY-01, 02, 03, 13 |
| `query_by_tran_id` | R1a [BUG-580] | MOCK-QRY-04, 05, 16 |
| `query_by_tran_id` | R2 | MOCK-QRY-06, 07 |
| `query_by_tran_id` | R3 | MOCK-QRY-08 |
| `query_by_tran_id` | R3a [BUG-580] | MOCK-QRY-09 |
| `query_by_tran_id` | R4 [BUG-580] | MOCK-QRY-10 (pass part), 11, 12; MOCK-QRY-17 (BUG-583 hint) |
| `query_by_tran_id` | R5 [BUG-581] | MOCK-QRY-14 |
| `query_by_tran_id` | Side effects none | MOCK-QRY-15, 16 |
| `verify_signature` | R1 | MOCK-VSIG-06 |
| `verify_signature` | R2 | MOCK-VSIG-07, 08 |
| `verify_signature` | R3 | MOCK-VSIG-01, 02, 03, 04, 05 |
| `verify_signature` | R4 [BUG-582] | MOCK-VSIG-09 |
| `verify_signature` | R5 | MOCK-VAL-09 |
| (all) | [BUG-580] | MOCK-QRY-04, 05, 09, 11, 12, 16 |
| (all) | [BUG-581] | MOCK-DEC-05, 06; MOCK-VAL-06, 07; MOCK-QRY-14 |
| (all) | [BUG-582] | MOCK-VSIG-09 |
| (all) | [BUG-583] | MOCK-DEC-07, 09; MOCK-VAL-11; MOCK-QRY-17 |
