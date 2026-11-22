# Test cases — `app/core/exceptions.py`

> **Spec:** `tests/unit/core/exceptions.spec.md` (source commit e48a092)
> **Status:** READY
> **Revision:** 5 — re-run; spec unchanged since revision 3 (same rules, same Gap log G1/G2, still APPROVED at source commit e48a092). No verify report exists, so there are no case-designer findings to address. Inventory and coverage matrix re-checked against every rule, error row and BUG tag (BUG-460…469): no case was added, changed or retired.
> *(Revision 4 — re-run on the updated spec. The Gap log (G1, G2) is the same as in revision 3, and no rule has changed since then. Every G1/G2 rule (R4b; R1a / BUG-469) is already covered, so no case was added, changed or retired. No verify report exists yet.)*
> *(Revision 3 — spec gap log G1/G2 closed both earlier gaps. New `integrity_error_handler` R4b (23503 whose direction cannot be read → R4 answer, under BUG-462) → EXC-HINT-21..27. New `api_exception_handler` R1a [BUG-469] (falsy `request.state.request_id` counts as absent, every handler) → EXC-HAPI-10/11, EXC-HVAL-13, EXC-HINT-28, EXC-HDB-06, EXC-HSCH-09, EXC-HGEN-07. No existing case changed or retired.)*
> *(Revision 2 — spec unchanged. Self-check fix: EXC-HINT-10 and EXC-HSCH-06 also assert `instance` and `body["request_id"]`.)*
> **Counts:** 89 cases · 51 expected-to-pass · 38 expected-to-fail (bugs) · 3 deferred

## Reviewer summary
- **Per callable:** `APIException.__init__` 3 · `ValidationError.__init__` 3 · `PermissionDeniedError.__init__` 2 · `NotFoundError.__init__` 2 · `ConflictError.__init__` 2 · `BusinessRuleError.__init__` 3 · `api_exception_handler` 11 (4 bug) · `validation_exception_handler` 13 (5 bug) · `integrity_error_handler` 28 (17 bug) · `database_error_handler` 6 (3 bug) · `schema_error_handler` 9 (6 bug) · `generic_exception_handler` 7 (3 bug).
- **Notable design choices:**
  - The module keeps no database state, so no case checks "database unchanged". The test Postgres is used only to produce real driver errors with real SQLSTATE codes: temporary tables with neutral names, inside a savepoint. *(best-practice default, delegated by reviewer)*
  - Exclusion violation (23P01) and undefined function (42883) use a stand-in cause object with `pgcode` / `diag.message_primary` (the spec allows this). Building a real exclusion constraint is not needed. *(best-practice default, delegated by reviewer)*
  - Every handler is called inside the `except` block that caught the exception, the way Starlette calls it. This means "traceback attached" can be checked as `record.exc_info[1] is exc`. *(best-practice default, delegated by reviewer)*
  - BUG-467 (type URI) and BUG-468 (media type) each get one xfail case per handler, so a later fix that misses one handler is caught. All other body checks use "type ends with `/errors/<slug>`", which is true both today and after the fix.
  - The new setting `ERROR_TYPE_BASE_URL` is patched with `monkeypatch.setattr(..., raising=False)` in the BUG-467 cases. Its default value (`""`) is deferred to the config spec. *(best-practice default, delegated by reviewer)*
  - Classification cases (BUG-462) cover both directions: real SQLSTATE errors whose text contains misleading words, and code-less causes whose text contains the words that the text search matches today.
  - R4b (23503 with unreadable direction) uses stand-in causes only, since real Postgres always sends a primary message. The xfail cases use text without "foreign key", so today they fall to the old default. The pass cases (HINT-26/27) use text that contains "foreign key", so they hold both today and after the fix. They guard "never raises" when `diag` is `None` or missing. *(best-practice default, delegated by reviewer)*
  - BUG-469 (falsy request id) gets one xfail case per handler, the same pattern as BUG-467/468. `api_exception_handler` splits `None` and `""` into two cases. The other handlers check both values in one case.
- **Needs a decision:** none. Both earlier gaps were closed by the spec (R4b, R1a).

## Conventions for this module

**Abbreviations:** `EXC` = exceptions. Callables: `API` = `APIException.__init__`, `VAL` = `ValidationError.__init__`, `PERM` = `PermissionDeniedError.__init__`, `NF` = `NotFoundError.__init__`, `CONF` = `ConflictError.__init__`, `BR` = `BusinessRuleError.__init__`, `HAPI` = `api_exception_handler`, `HVAL` = `validation_exception_handler`, `HINT` = `integrity_error_handler`, `HDB` = `database_error_handler`, `HSCH` = `schema_error_handler`, `HGEN` = `generic_exception_handler`.

**Requests** (a `starlette.requests.Request` built from a scope dict):
- `REQ` = `{"type": "http", "method": "POST", "path": "/api/v1/x", "headers": [(b"user-agent", b"ua-test/1.0")], "client": ("1.2.3.4", 5), "query_string": b"", "state": {"request_id": "req-t-1"}}`.
- `REQ-noid` = `REQ` with `"state": {}` (no request id).
- `REQ-bare` = `REQ` with `"headers": []` and `"client": None`.
- `REQ-q` = `REQ` with `"path": "/api/v1/suppliers/7"` and `"query_string": b"include=all"`.
- `REQ-nullid` = `REQ` with `"state": {"request_id": None}`; `REQ-emptyid` = `REQ` with `"state": {"request_id": ""}` (BUG-469).

**Calling a handler:** raise `exc`, catch it, and inside that `except` block run `resp = asyncio.run(handler(request, exc))` (this mirrors Starlette, so `exc_info` is live). `body` = `json.loads(resp.body)`. "Body text" = `resp.body.decode()`. *(best-practice default, delegated by reviewer)*

**Shorthands used in Then:**
- `STD(slug, title, status, detail)` means all of: `resp.status_code == status`; `resp.headers["X-Request-ID"] == "req-t-1"`; `set(body) == {"type","title","status","detail","instance","request_id"}`; `body["type"].endswith("/errors/<slug>")`; `body["title"] == title`; `body["status"] == status`; `body["detail"] == detail`; `body["instance"] == "/api/v1/x"`; `body["request_id"] == "req-t-1"`.
- `GENID` means: `body["request_id"]` matches `^req_[0-9a-f]{32}$` and `resp.headers["X-Request-ID"] == body["request_id"]`.
- `FALSYID(handler, exc)` (BUG-469) means: (a) with `REQ-nullid`, call the handler with `exc` → no exception raised; `GENID`; the handler's single `app.core.exceptions` log record has `request_id == body["request_id"]`; (b) the same with a new `REQ-emptyid` request → `GENID`; the log record's `request_id == body["request_id"]`; `resp.headers["X-Request-ID"] != ""`.
- `NOLEAK(a, b, …)` means none of the listed strings occurs in the body text.
- `LOG1(level, message)` means: with `caplog` at DEBUG, there is exactly one record whose `name == "app.core.exceptions"`; it has `levelno == level` and `getMessage() == message`. Extra fields are read as attributes of that record.

**Real DB errors (setup `TBL`):** on the test session, create:
`CREATE TEMP TABLE exc_parent (id int PRIMARY KEY, code text CONSTRAINT exc_parent_code_key UNIQUE)`,
`CREATE TEMP TABLE exc_child (id int PRIMARY KEY, parent_id int CONSTRAINT exc_child_parent_fk REFERENCES exc_parent(id), description text, qty int CONSTRAINT exc_child_qty_ck CHECK (qty >= 0), label text NOT NULL)`.
Insert the offending statement with `session.execute(text(...), params)` inside `session.begin_nested()`, and catch the SQLAlchemy exception it raises. Every statement passes every column explicitly (no NULL except where the case says so), so the text of a CHECK error's "Failing row" contains no `null`. The per-test transaction is rolled back as usual. *(best-practice default, delegated by reviewer)*

**Stand-in cause `SC(code, primary, text)`:** an object with `pgcode = code`, `diag.message_primary = primary`, and `str()` returning `text`. It is wrapped as `IntegrityError / ProgrammingError("INSERT INTO exc_booking (room) VALUES (%(room)s)", {"room": 3}, SC(...))`.
Stand-in variants for R4b: `SC-diagnone(code, text)` has `diag = None`; `SC-nodiag(code, text)` has no `diag` attribute at all; `SC-noprimary(code, text)` has a `diag` object with no `message_primary` attribute. Each has `pgcode = code` and `str()` returning `text`, and each is wrapped the same way as `SC`.
**Code-less cause:** `IntegrityError / OperationalError / ProgrammingError("<sql>", {"p": "v"}, Exception("<text>"))`.

**Settings:** `settings.DEBUG` is patched with `monkeypatch.setattr` wherever a case names it. In the BUG-467 cases, `settings.ERROR_TYPE_BASE_URL` is patched with `monkeypatch.setattr(settings, "ERROR_TYPE_BASE_URL", value, raising=False)`.
**Externals mocked:** none. `uuid.uuid4` is not patched; generated ids are checked by pattern.
**Race simulations:** none.

## `APIException.__init__`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| EXC-API-01 | R1, R3 | happy | `E = [{"field": "x", "message": "m", "code": "c"}]` | `exc = APIException(418, "teapot", "I'm a teapot", "Short and stout", E)` | `exc.status_code == 418`; `exc.error_type == "teapot"`; `exc.title == "I'm a teapot"`; `exc.detail == "Short and stout"`; `exc.errors is E`; `str(exc) == "Short and stout"`; `exc.args == ("Short and stout",)` | pass |
| EXC-API-02 | R2 | boundary | — | `exc = APIException(400, "bad", "Bad", "d")` | `exc.errors is None`; `str(exc) == "d"` | pass |
| EXC-API-03 | R4 | happy | — | raise `APIException(500, "x", "X", "boom")` inside `try` / `except Exception as caught` | the exception is caught by `except Exception`; `isinstance(caught, Exception)`; `caught.detail == "boom"` | pass |

## `ValidationError.__init__`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| EXC-VAL-01 | R1 | happy | `E = [{"field": "sku", "message": "taken", "code": "dup"}]` | `exc = ValidationError("Bad SKU", errors=E)` | `isinstance(exc, APIException)`; `status_code == 400`; `error_type == "validation_error"`; `title == "Validation Error"`; `detail == "Bad SKU"`; `errors is E`; `str(exc) == "Bad SKU"` | pass |
| EXC-VAL-02 | R2 | boundary | — | `exc = ValidationError("Bad SKU")` | `exc.errors is None`; `exc.status_code == 400` | pass |
| EXC-VAL-03 | R3 | error | — | `ValidationError()` | raises `TypeError` | pass |

## `PermissionDeniedError.__init__`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| EXC-PERM-01 | R1, R2 | happy | — | `exc = PermissionDeniedError()` | `isinstance(exc, APIException)`; `status_code == 403`; `error_type == "permission_denied"`; `title == "Permission Denied"`; `errors is None`; `detail == "You do not have permission to perform this action"`; `str(exc)` equals that same text | pass |
| EXC-PERM-02 | R2 | boundary | — | `exc = PermissionDeniedError("Only owners can delete")` | `detail == "Only owners can delete"`; `str(exc) == "Only owners can delete"`; `status_code == 403`; `title == "Permission Denied"` | pass |

## `NotFoundError.__init__`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| EXC-NF-01 | R1 | happy | — | `exc = NotFoundError("Supplier 7 not found")` | `isinstance(exc, APIException)`; `status_code == 404`; `error_type == "not_found"`; `title == "Resource Not Found"`; `detail == "Supplier 7 not found"`; `errors is None`; `str(exc) == "Supplier 7 not found"` | pass |
| EXC-NF-02 | R2 | error | — | `NotFoundError()` | raises `TypeError` | pass |

## `ConflictError.__init__`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| EXC-CONF-01 | R1 | happy | — | `exc = ConflictError("Name already used")` | `isinstance(exc, APIException)`; `status_code == 409`; `error_type == "conflict"`; `title == "Resource Conflict"`; `detail == "Name already used"`; `errors is None`; `str(exc) == "Name already used"` | pass |
| EXC-CONF-02 | R2 | error | — | `ConflictError()` | raises `TypeError` | pass |

## `BusinessRuleError.__init__`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| EXC-BR-01 | R1 | happy | `E = [{"field": "qty", "message": "too high", "code": "max"}]` | `exc = BusinessRuleError("Stock too low", errors=E)` | `isinstance(exc, APIException)`; `status_code == 422`; `error_type == "business_rule_violation"`; `title == "Business Rule Violation"`; `detail == "Stock too low"`; `errors is E`; `str(exc) == "Stock too low"` | pass |
| EXC-BR-02 | R2 | boundary | — | `exc = BusinessRuleError("Stock too low")` | `exc.errors is None`; `status_code == 422` | pass |
| EXC-BR-03 | R3 | error | — | `BusinessRuleError()` | raises `TypeError` | pass |

## `api_exception_handler`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| EXC-HAPI-01 | R1, R2, R3, R4 | happy | `REQ-q` | handle `NotFoundError("Supplier 7 not found")` | `resp.status_code == 404`; `resp.headers["X-Request-ID"] == "req-t-1"`; `set(body) == {"type","title","status","detail","instance","request_id"}` (no `errors`); `body["type"].endswith("/errors/not_found")`; `title == "Resource Not Found"`; `status == 404`; `detail == "Supplier 7 not found"`; `instance == "/api/v1/suppliers/7"` (no `include=all`); `request_id == "req-t-1"` | pass |
| EXC-HAPI-02 | R1 | boundary | `REQ-noid` | handle `NotFoundError("x")` twice (two separate calls, each with its own new `REQ-noid` request) | for each response `GENID`; the two request ids differ | pass |
| EXC-HAPI-03 | R4 | happy | `REQ`; `E = [{"field": "sku", "message": "taken", "code": "dup"}, {"field": "qty", "message": "neg", "code": "min"}]` | handle `ValidationError("Bad input", errors=E)` | `resp.status_code == 400`; `set(body)` = the 6 standard keys + `"errors"`; `body["errors"] == E` (same order); `title == "Validation Error"`; `type` ends `/errors/validation_error`; `status == 400` | pass |
| EXC-HAPI-04 | R4 | boundary | `REQ` | handle `BusinessRuleError("Stock too low", errors=[])` | `STD("business_rule_violation", "Business Rule Violation", 422, "Stock too low")` (so `errors` key absent) | pass |
| EXC-HAPI-05 | R2, R3 | happy | `REQ` | handle `APIException(418, "teapot", "I'm a teapot", "Short and stout")` | `STD("teapot", "I'm a teapot", 418, "Short and stout")` — status, title and slug come from the instance, not from a class table | pass |
| EXC-HAPI-06 | R5 | side-effect | `REQ` | handle `NotFoundError("Supplier 7 not found")` | returns 404 with header `X-Request-ID == "req-t-1"`; `LOG1(ERROR, "API Error: Resource Not Found")`; record `request_id == "req-t-1"`, `error_type == "not_found"`, `status_code == 404`, `detail == "Supplier 7 not found"`, `path == "/api/v1/x"`, `method == "POST"`, `user_agent == "ua-test/1.0"`, `ip_address == "1.2.3.4"` (ERROR level even though 4xx) | pass |
| EXC-HAPI-07 | R5 | boundary | `REQ-bare` | handle `ConflictError("dup")` | `STD("conflict", "Resource Conflict", 409, "dup")`; `LOG1(ERROR, "API Error: Resource Conflict")`; record `user_agent is None`; `ip_address is None` | pass |
| EXC-HAPI-08 | R3a [BUG-467] | bug | `REQ` | (a) `ERROR_TYPE_BASE_URL = ""`, handle `NotFoundError("x")`; (b) `ERROR_TYPE_BASE_URL = "https://api.example.com"`, handle it again | (a) `body["type"] == "/errors/not_found"`; (b) `body["type"] == "https://api.example.com/errors/not_found"`; neither contains `"yourdomain"` | xfail BUG-467 — fails today on: (a) `type == "/errors/not_found"` (today `https://api.yourdomain.com/errors/not_found`) |
| EXC-HAPI-09 | R3b [BUG-468] | bug | `REQ` | handle `NotFoundError("x")` | `resp.media_type == "application/problem+json"`; `resp.headers["content-type"] == "application/problem+json"`; `body["detail"] == "x"`, `body["status"] == 404` (body unchanged) | xfail BUG-468 — fails today on: media type (today `application/json`) |
| EXC-HAPI-10 | R1a [BUG-469] | bug | `REQ-nullid` | handle `NotFoundError("Supplier 7 not found")` | no exception raised; `resp.status_code == 404`; `GENID`; `body["detail"] == "Supplier 7 not found"`; `LOG1(ERROR, "API Error: Resource Not Found")` with record `request_id == body["request_id"]` | xfail BUG-469 — fails today on: no exception raised (today `AttributeError` while encoding the header) |
| EXC-HAPI-11 | R1a [BUG-469] | bug | `REQ-emptyid` | handle `NotFoundError("Supplier 7 not found")` | `resp.status_code == 404`; `GENID`; `resp.headers["X-Request-ID"] != ""`; `LOG1(ERROR, "API Error: Resource Not Found")` with record `request_id == body["request_id"]` | xfail BUG-469 — fails today on: `GENID` (today `body["request_id"] == ""`) |

## `validation_exception_handler`

`PW` = `RequestValidationError([{"type": "missing", "loc": ("body", "name"), "msg": "Field required", "input": {"email": "a@b.com", "password": "Hunter2!"}}])`.

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| EXC-HVAL-01 | R1, R2, R3, R7 | happy | `REQ` | handle `PW` | `resp.headers["X-Request-ID"] == "req-t-1"`; `set(body) == {"type","title","status","detail","instance","request_id","errors"}`; `type` ends `/errors/validation_error`; `title == "Validation Error"`; `detail == "Request validation failed"`; `instance == "/api/v1/x"`; `request_id == "req-t-1"`; `body["status"] == resp.status_code`; `errors == [{"field": "name", "message": "Field required", "code": "missing"}]`; `NOLEAK("Hunter2!", "a@b.com", "input")` | pass |
| EXC-HVAL-02 | R1 | boundary | `REQ-noid` | handle `PW` | `GENID` | pass |
| EXC-HVAL-03 | R1a [BUG-461] | bug | `REQ` | (a) handle `PW`; (b) handle `RequestValidationError([{"type": "greater_than_equal", "loc": ("query", "limit"), "msg": "Input should be greater than or equal to 1", "input": "0", "ctx": {"ge": 1}}])` | (a) and (b): `resp.status_code == 422` and `body["status"] == 422` | xfail BUG-461 — fails today on: status 422 (today 400) |
| EXC-HVAL-04 | R2 | boundary | `REQ` | handle `RequestValidationError([])` | `"errors" in body` and `body["errors"] == []`; `detail == "Request validation failed"`; `title == "Validation Error"`; header `X-Request-ID == "req-t-1"` | pass |
| EXC-HVAL-05 | R2, R3, R7 | happy | `REQ` | handle `RequestValidationError([{"type": "greater_than", "loc": ("body", "items", 0, "qty"), "msg": "Input should be greater than 0", "input": -5, "ctx": {"gt": 0}, "url": "https://errors.pydantic.dev/2/v/greater_than"}, {"type": "string_too_short", "loc": ("body", "name"), "msg": "String should have at least 1 character", "input": "", "ctx": {"min_length": 1}}])` | `body["errors"] == [{"field": "items.0.qty", "message": "Input should be greater than 0", "code": "greater_than"}, {"field": "name", "message": "String should have at least 1 character", "code": "string_too_short"}]` (order kept; each entry exactly these 3 keys); `NOLEAK("errors.pydantic.dev", "ctx", "min_length")` | pass |
| EXC-HVAL-06 | R3 | boundary | `REQ` | handle errors with loc `("body", "meta", "body", "note")` (type `"missing"`, msg `"Field required"`) and loc `("body", "bodyweight")` (type `"float_type"`, msg `"Input should be a valid number"`) | `fields == ["meta.note", "bodyweight"]` — `"body"` is dropped anywhere in the path, but a segment that only starts with "body" is kept | pass |
| EXC-HVAL-07 | R4 | happy | `REQ` | handle errors with locs `("query", "limit")`, `("path", "id")`, `("header", "x-workspace-id")` (type `"int_parsing"`, msg `"bad"`) | `fields == ["query.limit", "path.id", "header.x-workspace-id"]` | pass |
| EXC-HVAL-08 | R5 | boundary | `REQ` | handle errors with locs `("body",)` and `("body", "body")` (type `"model_attributes_type"`, msg `"Input should be a valid dictionary"`) | `fields == ["body", "body"]` | pass |
| EXC-HVAL-09 | R6 | side-effect | `REQ` | handle `PW` | returns a response with header `X-Request-ID == "req-t-1"`; exactly one record from `app.core.exceptions` at WARNING with `getMessage() == "Validation error"`; its `request_id == "req-t-1"`, `errors == [{"field": "name", "message": "Field required", "code": "missing"}]`, `path == "/api/v1/x"`, `method == "POST"`; that record's message and extras do not contain `"Hunter2!"` | pass |
| EXC-HVAL-10 | R6a [BUG-460] | bug | `REQ`; `caplog` at DEBUG for all loggers | handle `PW` | `LOG1(WARNING, "Validation error")` (so no ERROR records); in every captured record (any logger), neither `getMessage()` nor any `str()` of a value in `record.__dict__` contains `"Hunter2!"` or `"a@b.com"` | xfail BUG-460 — fails today on: exactly one record (today 3 extra ERROR records, one containing `Hunter2!`) |
| EXC-HVAL-11 | R1, R3a [BUG-467] | bug | `REQ` | (a) base URL `""`, handle `PW`; (b) base URL `"https://api.example.com"`, handle it again | (a) `type == "/errors/validation_error"`; (b) `type == "https://api.example.com/errors/validation_error"`; neither contains `"yourdomain"` | xfail BUG-467 — fails today on: (a) |
| EXC-HVAL-12 | R1, R3b [BUG-468] | bug | `REQ` | handle `PW` | `resp.media_type == "application/problem+json"`; `resp.headers["content-type"] == "application/problem+json"`; `body["detail"] == "Request validation failed"` | xfail BUG-468 — fails today on: media type |
| EXC-HVAL-13 | R1, R1a (api) [BUG-469] | bug | `caplog` at DEBUG | `FALSYID(validation_exception_handler, PW)`; the log record checked is the WARNING `"Validation error"` | as `FALSYID`; also `body["detail"] == "Request validation failed"` in both (a) and (b) | xfail BUG-469 — fails today on: (a) no exception raised (today `AttributeError`) |

## `integrity_error_handler`

All `HINT` cases with a real error use `TBL`. "Parent 1" = `INSERT INTO exc_parent (id, code) VALUES (1, 'SKU-1')`. Child insert = `INSERT INTO exc_child (id, parent_id, description, qty, label) VALUES (:id, :parent_id, :description, :qty, :label)`.

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| EXC-HINT-01 | R1, R2, R3, R7, R8 | happy | `TBL`; parent 1; `REQ` | `INSERT INTO exc_parent (id, code) VALUES (:id, :code)` with `{id: 2, code: "SKU-1"}` → real 23505; handle it | `STD("conflict", "Resource Conflict", 409, "This resource already exists. Please use a different value.")`; `NOLEAK("exc_parent", "exc_parent_code_key", "SKU-1", "INSERT", "duplicate key", "[SQL")` | pass |
| EXC-HINT-02 | R1, R2, R6, R7 | happy | `REQ-noid` | handle code-less `IntegrityError("UPDATE t SET a=1", {"p": "v"}, Exception("constraint check failed"))` | `GENID`; `resp.status_code == 409`; `body["status"] == 409`; `title == "Resource Conflict"`; `type` ends `/errors/conflict`; `set(body)` = the 6 standard keys; `NOLEAK("constraint check failed", "UPDATE t")` | pass |
| EXC-HINT-03 | R4, R7, R8 | happy | `TBL`; parent 1; `REQ` | child insert `{id: 1, parent_id: 999, description: "Bowl", qty: 1, label: "L"}` → real 23503 (`insert or update on table …`); handle | `STD("conflict", "Resource Conflict", 409, "Referenced resource does not exist.")`; `NOLEAK("exc_child", "exc_child_parent_fk", "999", "Bowl")` | pass |
| EXC-HINT-04 | R4a [BUG-463] | bug | `TBL`; parent 1; child `{id: 1, parent_id: 1, description: "Bowl", qty: 1, label: "L"}`; `REQ` | `DELETE FROM exc_parent WHERE id = :id` with `{id: 1}` → real 23503 (`update or delete on table …`); handle | `body["detail"] == "This resource is still in use by other records."` | xfail BUG-463 — fails today on: detail (today `"Referenced resource does not exist."`) |
| EXC-HINT-05 | R4a, R7, R8 | happy | same as HINT-04 | same as HINT-04 | `resp.status_code == 409`; `body["status"] == 409`; `title == "Resource Conflict"`; `type` ends `/errors/conflict`; header `X-Request-ID == "req-t-1"`; `set(body)` = the 6 standard keys; `NOLEAK("exc_parent", "exc_child", "exc_child_parent_fk")` | pass |
| EXC-HINT-06 | R4a | boundary | `TBL`; parent 1; `REQ` | child insert `{id: 1, parent_id: 999, description: "update or delete on table exc_parent", qty: 1, label: "L"}` → real 23503 (insert direction); handle | `body["detail"] == "Referenced resource does not exist."` (the direction comes from the primary message, not from the parameters); `status == 409` | pass |
| EXC-HINT-07 | R5, R8 | happy | `TBL`; parent 1; `REQ` | child insert `{id: 1, parent_id: 1, description: "Bowl", qty: 1, label: None}` → real 23502; handle | `resp.status_code == 400`; `body["status"] == 400`; `detail == "Required field is missing."`; header `X-Request-ID == "req-t-1"`; `set(body)` = the 6 standard keys; `instance == "/api/v1/x"`; `NOLEAK("exc_child", "label", "Bowl")` | pass |
| EXC-HINT-08 | R7a [BUG-465] | bug | same as HINT-07 | same as HINT-07 | `body["title"] == "Validation Error"`; `body["type"].endswith("/errors/validation_error")`; `status == 400` | xfail BUG-465 — fails today on: title (today `"Resource Conflict"`) |
| EXC-HINT-09 | R5a [BUG-464] | bug | `TBL`; parent 1; `REQ` | child insert `{id: 1, parent_id: 1, description: "Bowl", qty: -5, label: "L"}` → real 23514; handle | `STD("validation_error", "Validation Error", 422, "A value is outside the allowed range.")` | xfail BUG-464 — fails today on: status 422 (today 409) |
| EXC-HINT-10 | R5a, R8 | happy | same as HINT-09 | same as HINT-09 | header `X-Request-ID == "req-t-1"`; `body["request_id"] == "req-t-1"`; `body["instance"] == "/api/v1/x"`; `body["status"] == resp.status_code`; `set(body)` = the 6 standard keys; `NOLEAK("exc_child_qty_ck", "exc_child", "check constraint")` | pass |
| EXC-HINT-11 | R6, R7, R8 | happy | `REQ` | handle `IntegrityError(<sql>, {"room": 3}, SC("23P01", 'conflicting key value violates exclusion constraint "exc_booking_excl"', 'conflicting key value violates exclusion constraint "exc_booking_excl"'))` | `resp.status_code == 409`; `body["status"] == 409`; `title == "Resource Conflict"`; `type` ends `/errors/conflict`; `set(body)` = the 6 standard keys; `NOLEAK("exc_booking_excl", "exc_booking")` | pass |
| EXC-HINT-12 | R6a [BUG-464] | bug | same as HINT-11 | same as HINT-11 | `body["detail"] == "A database constraint was violated."`; `"may already exist" not in body text` | xfail BUG-464 — fails today on: detail (today has `" The resource may already exist."`) |
| EXC-HINT-13 | R2 [BUG-462] | bug | `TBL`; parent 1; `REQ` | child insert `{id: 1, parent_id: 999, description: "Unique handmade bowl", qty: 1, label: "L"}` → real 23503; handle | `body["detail"] == "Referenced resource does not exist."`; `status == 409` | xfail BUG-462 — fails today on: detail (today `"This resource already exists. …"`) |
| EXC-HINT-14 | R2 [BUG-462] | bug | `TBL`; parent 1; `REQ` | child insert `{id: 1, parent_id: 1, description: "duplicate", qty: 1, label: None}` → real 23502; handle | `resp.status_code == 400`; `detail == "Required field is missing."` | xfail BUG-462 — fails today on: status 400 (today 409, "already exists") |
| EXC-HINT-15 | R2, R6a [BUG-462] | bug | `REQ` | handle code-less `IntegrityError("INSERT INTO t", {"p": "v"}, Exception('duplicate key value violates unique constraint "t_key"'))` | `status == 409`; `title == "Resource Conflict"`; `detail == "A database constraint was violated."` | xfail BUG-462 — fails today on: detail (today `"This resource already exists. …"`) |
| EXC-HINT-16 | R2, R6a [BUG-462] | bug | `REQ` | handle code-less `IntegrityError("INSERT INTO t", {"p": "v"}, Exception('null value in column "x" violates not-null constraint'))` | `resp.status_code == 409`; `title == "Resource Conflict"`; `detail == "A database constraint was violated."` | xfail BUG-462 — fails today on: status 409 (today 400) |
| EXC-HINT-17 | R2, R3 [BUG-462] | bug | `REQ` | handle `IntegrityError(<sql>, {"room": 3}, SC("23505", "row rejected", "row rejected"))` | `status == 409`; `detail == "This resource already exists. Please use a different value."` | xfail BUG-462 — fails today on: detail (today the generic "may already exist" text) |
| EXC-HINT-18 | R9 | side-effect | as HINT-01 | as HINT-01 (handle the real 23505 `exc`) | returns 409 with header `X-Request-ID == "req-t-1"`; `LOG1(ERROR, "Database integrity error")`; record `request_id == "req-t-1"`, `error == str(exc)`, `path == "/api/v1/x"`, `record.exc_info[1] is exc` | pass |
| EXC-HINT-19 | R7, R3a [BUG-467] | bug | `REQ` | code-less `IntegrityError("X", {}, Exception("boom"))`: (a) base URL `""`, handle; (b) base URL `"https://api.example.com"`, handle again | (a) `type == "/errors/conflict"`; (b) `type == "https://api.example.com/errors/conflict"`; no `"yourdomain"` | xfail BUG-467 — fails today on: (a) |
| EXC-HINT-20 | R1, R3b [BUG-468] | bug | `REQ` | handle code-less `IntegrityError("X", {}, Exception("boom"))` | `resp.media_type == "application/problem+json"`; `resp.headers["content-type"] == "application/problem+json"`; `status == 409` | xfail BUG-468 — fails today on: media type |
| EXC-HINT-21 | R4b [BUG-462] | bug | `REQ` | handle `IntegrityError(<sql>, {"room": 3}, SC("23503", None, "row rejected"))` (`diag.message_primary is None`) | no exception raised; `STD("conflict", "Resource Conflict", 409, "Referenced resource does not exist.")` | xfail BUG-462 — fails today on: detail (today `"A database constraint was violated. The resource may already exist."`) |
| EXC-HINT-22 | R4b [BUG-462] | bug | `REQ` | handle `IntegrityError(<sql>, {"room": 3}, SC-diagnone("23503", "row rejected"))` | no exception raised; `STD("conflict", "Resource Conflict", 409, "Referenced resource does not exist.")` | xfail BUG-462 — fails today on: detail (today the "may already exist" text) |
| EXC-HINT-23 | R4b [BUG-462] | bug | `REQ` | handle `IntegrityError(<sql>, {"room": 3}, SC-nodiag("23503", "row rejected"))` | no exception raised; `STD("conflict", "Resource Conflict", 409, "Referenced resource does not exist.")` | xfail BUG-462 — fails today on: detail (today the "may already exist" text) |
| EXC-HINT-24 | R4b [BUG-462] | bug | `REQ` | handle `IntegrityError(<sql>, {"room": 3}, SC-noprimary("23503", "row rejected"))` | no exception raised; `STD("conflict", "Resource Conflict", 409, "Referenced resource does not exist.")` | xfail BUG-462 — fails today on: detail (today the "may already exist" text) |
| EXC-HINT-25 | R4b [BUG-462] | bug | `REQ` | handle `IntegrityError(<sql>, {"room": 3}, SC("23503", "row rejected by referential rule", "row rejected by referential rule"))` (primary starts with neither known prefix) | `STD("conflict", "Resource Conflict", 409, "Referenced resource does not exist.")` — not the R4a text, not the R6 text | xfail BUG-462 — fails today on: detail (today the "may already exist" text) |
| EXC-HINT-26 | R4b | boundary | `REQ` | handle `IntegrityError(<sql>, {"room": 3}, SC-diagnone("23503", 'violates foreign key constraint "exc_booking_fk"'))` | no exception raised; `STD("conflict", "Resource Conflict", 409, "Referenced resource does not exist.")`; `NOLEAK("exc_booking_fk", "exc_booking")` | pass |
| EXC-HINT-27 | R4b | boundary | `REQ` | handle `IntegrityError(<sql>, {"room": 3}, SC-nodiag("23503", 'violates foreign key constraint "exc_booking_fk"'))` | no exception raised; `STD("conflict", "Resource Conflict", 409, "Referenced resource does not exist.")` | pass |
| EXC-HINT-28 | R1, R1a (api) [BUG-469] | bug | `caplog` at DEBUG | `FALSYID(integrity_error_handler, IntegrityError("X", {}, Exception("boom")))`; the log record checked is the ERROR `"Database integrity error"` | as `FALSYID`; also `resp.status_code == 409` in both (a) and (b) | xfail BUG-469 — fails today on: (a) no exception raised (today `AttributeError`) |

## `database_error_handler`

`OPX` = `OperationalError("SELECT 1", {"p": "v"}, Exception("connection to server at 10.0.0.5 failed: password authentication failed for user admin"))`.

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| EXC-HDB-01 | R1, R2 | happy | `REQ` | handle `OPX` | `STD("service_unavailable", "Service Unavailable", 503, "Database service is temporarily unavailable. Please try again later.")`; `"retry-after" not in resp.headers`; `NOLEAK("10.0.0.5", "password authentication", "SELECT 1", "admin")` | pass |
| EXC-HDB-02 | R1 | boundary | `REQ-noid` | handle `OperationalError("UPDATE t", {}, Exception("deadlock detected"))` | `GENID`; `status_code == 503`; `title == "Service Unavailable"`; `detail == "Database service is temporarily unavailable. Please try again later."`; `NOLEAK("deadlock")` (same body whatever the content) | pass |
| EXC-HDB-03 | R3 | side-effect | `REQ` | handle `OPX` | returns 503 with header `X-Request-ID == "req-t-1"`; `LOG1(ERROR, "Database operational error")`; record `request_id == "req-t-1"`, `error == str(OPX)`, `path == "/api/v1/x"`, `exc_info[1] is OPX` | pass |
| EXC-HDB-04 | R1, R3a [BUG-467] | bug | `REQ` | (a) base URL `""`, handle `OPX`; (b) base URL `"https://api.example.com"`, handle again | (a) `type == "/errors/service_unavailable"`; (b) `type == "https://api.example.com/errors/service_unavailable"`; no `"yourdomain"` | xfail BUG-467 — fails today on: (a) |
| EXC-HDB-05 | R1, R3b [BUG-468] | bug | `REQ` | handle `OPX` | `resp.media_type == "application/problem+json"`; `resp.headers["content-type"] == "application/problem+json"` | xfail BUG-468 — fails today on: media type |
| EXC-HDB-06 | R1, R1a (api) [BUG-469] | bug | `caplog` at DEBUG | `FALSYID(database_error_handler, OPX)`; the log record checked is the ERROR `"Database operational error"` | as `FALSYID`; also `resp.status_code == 503` in both (a) and (b) | xfail BUG-469 — fails today on: (a) no exception raised (today `AttributeError`) |

## `schema_error_handler`

`SCHEMA_MSG` = ``"Database schema is out of date — run `alembic upgrade head` and restart the API."`` (em dash, literal backticks). `TEMP_MSG` = `"Database service is temporarily unavailable. Please try again later."`. `GEN_MSG` = `"An unexpected error occurred. Please contact support with the request ID."`.

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| EXC-HSCH-01 | R1, R2, R3, R4 | happy | `settings.DEBUG = True`; `REQ` | `SELECT * FROM exc_no_such_table` → real `ProgrammingError`, 42P01; handle | `STD("service_unavailable", "Service Unavailable", 503, SCHEMA_MSG)`; `NOLEAK("exc_no_such_table", "SELECT", "does not exist")`; `LOG1(ERROR, "Database schema error")` with `request_id == "req-t-1"`, `error == str(exc)`, `path == "/api/v1/x"`, `exc_info[1] is exc` | pass |
| EXC-HSCH-02 | R1, R2 | boundary | `settings.DEBUG = False`; `REQ-noid` | `SELECT exc_no_such_col FROM (SELECT 1 AS a) s` → real 42703; handle | `GENID`; `status_code == 503`; `body["status"] == 503`; `title == "Service Unavailable"`; `type` ends `/errors/service_unavailable`; `detail == TEMP_MSG`; `NOLEAK("exc_no_such_col")` | pass |
| EXC-HSCH-03 | R1a [BUG-466] | bug | `settings.DEBUG = True`; `REQ` | `SELEC 1` → real 42601; handle | `STD("internal_error", "Internal Server Error", 500, GEN_MSG)` | xfail BUG-466 — fails today on: status 500 (today 503) |
| EXC-HSCH-04 | R1a [BUG-466] | bug | `settings.DEBUG = False`; `REQ` | handle `ProgrammingError("SELECT f()", {}, SC("42883", "function f() does not exist", "function f() does not exist"))` | `STD("internal_error", "Internal Server Error", 500, GEN_MSG)` | xfail BUG-466 — fails today on: status 500 |
| EXC-HSCH-05 | R1a [BUG-466] | bug | `settings.DEBUG = True`; `REQ` | handle code-less `ProgrammingError("SELECT x", {}, Exception('relation "t" does not exist'))` | `STD("internal_error", "Internal Server Error", 500, GEN_MSG)` (no code → not 503, even though the text looks like a missing table) | xfail BUG-466 — fails today on: status 500 |
| EXC-HSCH-06 | R1a, R3, R4 | side-effect | `settings.DEBUG = True`; `REQ` | `SELEC 1` → real 42601; handle | `resp.headers["X-Request-ID"] == "req-t-1"`; `body["request_id"] == "req-t-1"`; `body["instance"] == "/api/v1/x"`; `set(body) == {"type","title","status","detail","instance","request_id"}`; `body["status"] == resp.status_code`; `NOLEAK("SELEC", "syntax error")`; `LOG1(ERROR, "Database schema error")` with `request_id == "req-t-1"`, `error == str(exc)`, `path == "/api/v1/x"`, `exc_info[1] is exc` | pass |
| EXC-HSCH-07 | R1, R3a [BUG-467] | bug | `settings.DEBUG = True`; `REQ` | `ProgrammingError("SELECT", {}, SC("42P01", "relation missing", "relation missing"))`: (a) base URL `""`, handle; (b) base URL `"https://api.example.com"`, handle again | (a) `type == "/errors/service_unavailable"`; (b) `type == "https://api.example.com/errors/service_unavailable"`; no `"yourdomain"` | xfail BUG-467 — fails today on: (a) |
| EXC-HSCH-08 | R1, R3b [BUG-468] | bug | `settings.DEBUG = True`; `REQ` | handle the HSCH-07 exception | `resp.media_type == "application/problem+json"`; `resp.headers["content-type"] == "application/problem+json"` | xfail BUG-468 — fails today on: media type |
| EXC-HSCH-09 | R1, R1a (api) [BUG-469] | bug | `settings.DEBUG = True`; `caplog` at DEBUG | `FALSYID(schema_error_handler, ProgrammingError("SELECT", {}, SC("42P01", "relation missing", "relation missing")))`; the log record checked is the ERROR `"Database schema error"` | as `FALSYID`; also `resp.status_code == 503` in both (a) and (b) | xfail BUG-469 — fails today on: (a) no exception raised (today `AttributeError`) |

## `generic_exception_handler`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| EXC-HGEN-01 | R1, R2 | happy | `REQ` | handle `ValueError("secret-token-123")` | `STD("internal_error", "Internal Server Error", 500, "An unexpected error occurred. Please contact support with the request ID.")`; `NOLEAK("ValueError", "secret-token-123")` | pass |
| EXC-HGEN-02 | R1, R2 | boundary | `REQ-noid` | handle `KeyError("sku")` | `GENID`; `status_code == 500`; `title == "Internal Server Error"`; `detail` = the same generic text; `NOLEAK("KeyError", "sku")` | pass |
| EXC-HGEN-03 | R3 | side-effect | `REQ` | handle `exc = ValueError("secret-token-123")` | returns 500 with header `X-Request-ID == "req-t-1"`; `LOG1(ERROR, "Unexpected error")`; `record.exc_info[1] is exc`; `request_id == "req-t-1"`, `error_type == "ValueError"`, `error == "secret-token-123"`, `path == "/api/v1/x"`, `method == "POST"`, `user_agent == "ua-test/1.0"`, `ip_address == "1.2.3.4"` | pass |
| EXC-HGEN-04 | R3 | boundary | `REQ-bare` | handle `ValueError("x")` | `STD("internal_error", "Internal Server Error", 500, <generic text>)`; `LOG1(ERROR, "Unexpected error")`; `user_agent is None`; `ip_address is None` | pass |
| EXC-HGEN-05 | R1, R3a [BUG-467] | bug | `REQ` | (a) base URL `""`, handle `ValueError("x")`; (b) base URL `"https://api.example.com"`, handle again | (a) `type == "/errors/internal_error"`; (b) `type == "https://api.example.com/errors/internal_error"`; no `"yourdomain"` | xfail BUG-467 — fails today on: (a) |
| EXC-HGEN-06 | R1, R3b [BUG-468] | bug | `REQ` | handle `ValueError("x")` | `resp.media_type == "application/problem+json"`; `resp.headers["content-type"] == "application/problem+json"` | xfail BUG-468 — fails today on: media type |
| EXC-HGEN-07 | R1, R1a (api) [BUG-469] | bug | `caplog` at DEBUG | `FALSYID(generic_exception_handler, ValueError("x"))`; the log record checked is the ERROR `"Unexpected error"` | as `FALSYID`; also `resp.status_code == 500` in both (a) and (b) | xfail BUG-469 — fails today on: (a) no exception raised (today `AttributeError`) |

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| Which handler Starlette picks for each exception type (MRO lookup); CORS/security headers on error responses | integration tests on `app/main.py` | `APIException` subclasses → `api_exception_handler`; `IntegrityError` → integrity handler rather than the catch-all; headers present on error responses |
| `api_exception_handler` R3a — default value of the new setting `ERROR_TYPE_BASE_URL` is `""` | `app/core/config.py` spec | `Settings().ERROR_TYPE_BASE_URL == ""` with no env override |
| `validation_exception_handler` R1a — HR-1 / HR-7 schema rejections reach clients as 422 | endpoint tests (e.g. `GET /items/?limit=0`, blank department name) | full-stack 422 with `type` slug `validation_error` |

## Spec gaps
None. (Revision 2 gaps 1 and 2 were closed by spec Gap log G1 → `integrity_error_handler` R4b and G2 → `api_exception_handler` R1a / BUG-469. They are covered by EXC-HINT-21..27 and EXC-HAPI-10/11, EXC-HVAL-13, EXC-HINT-28, EXC-HDB-06, EXC-HSCH-09, EXC-HGEN-07.)

## Not specified (no cases)
- `AuthenticationError.__init__` — dead code, to be removed (reviewer; see `exceptions.deadcode-staging.md`).

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `APIException.__init__` | R1 | EXC-API-01 |
| | R2 | EXC-API-02 |
| | R3 | EXC-API-01, EXC-API-02 |
| | R4 | EXC-API-03 |
| `ValidationError.__init__` | R1 | EXC-VAL-01 |
| | R2 | EXC-VAL-02 |
| | R3 | EXC-VAL-03 |
| `PermissionDeniedError.__init__` | R1 | EXC-PERM-01 |
| | R2 | EXC-PERM-01, EXC-PERM-02 |
| `NotFoundError.__init__` | R1 | EXC-NF-01 |
| | R2 | EXC-NF-02 |
| `ConflictError.__init__` | R1 | EXC-CONF-01 |
| | R2 | EXC-CONF-02 |
| `BusinessRuleError.__init__` | R1 | EXC-BR-01 |
| | R2 | EXC-BR-02 |
| | R3 | EXC-BR-03 |
| `api_exception_handler` | R1 | EXC-HAPI-01, EXC-HAPI-02 |
| | R1a [BUG-469] | EXC-HAPI-10 (`None`), EXC-HAPI-11 (`""`) (and EXC-HVAL-13, EXC-HINT-28, EXC-HDB-06, EXC-HSCH-09, EXC-HGEN-07) |
| | R2 | EXC-HAPI-01, EXC-HAPI-05 |
| | R3 | EXC-HAPI-01, EXC-HAPI-04, EXC-HAPI-05 |
| | R3a [BUG-467] | EXC-HAPI-08 (and EXC-HVAL-11, EXC-HINT-19, EXC-HDB-04, EXC-HSCH-07, EXC-HGEN-05) |
| | R3b [BUG-468] | EXC-HAPI-09 (and EXC-HVAL-12, EXC-HINT-20, EXC-HDB-05, EXC-HSCH-08, EXC-HGEN-06) |
| | R4 | EXC-HAPI-01 (None), EXC-HAPI-03 (non-empty), EXC-HAPI-04 (`[]`) |
| | R5 | EXC-HAPI-06, EXC-HAPI-07 |
| `validation_exception_handler` | R1 | EXC-HVAL-01, EXC-HVAL-02 |
| | R1a [BUG-461] | EXC-HVAL-03 |
| | R2 | EXC-HVAL-01, EXC-HVAL-04, EXC-HVAL-05 |
| | R3 | EXC-HVAL-01, EXC-HVAL-05, EXC-HVAL-06 |
| | R4 | EXC-HVAL-07 |
| | R5 | EXC-HVAL-08 |
| | R6 | EXC-HVAL-09 |
| | R6a [BUG-460] | EXC-HVAL-10 |
| | R7 | EXC-HVAL-01, EXC-HVAL-05 |
| `integrity_error_handler` | R1 | EXC-HINT-01, EXC-HINT-02, EXC-HINT-20 |
| | R2 [BUG-462] | EXC-HINT-13, EXC-HINT-14, EXC-HINT-15, EXC-HINT-16, EXC-HINT-17 (xfail); EXC-HINT-01, -02, -06 (pass) |
| | R3 | EXC-HINT-01, EXC-HINT-17 |
| | R4 | EXC-HINT-03, EXC-HINT-06, EXC-HINT-13 |
| | R4a [BUG-463] | EXC-HINT-04 (xfail); EXC-HINT-05, EXC-HINT-06 (pass) |
| | R4b [BUG-462] | EXC-HINT-21 (primary `None`), -22 (`diag` `None`), -23 (no `diag`), -24 (no `message_primary`), -25 (unknown prefix) (xfail); EXC-HINT-26, -27 (pass) |
| | R5 | EXC-HINT-07, EXC-HINT-14 |
| | R5a [BUG-464] | EXC-HINT-09 (xfail); EXC-HINT-10 (pass) |
| | R6 | EXC-HINT-02, EXC-HINT-11 |
| | R6a [BUG-464] | EXC-HINT-12, EXC-HINT-15, EXC-HINT-16 |
| | R7 | EXC-HINT-01, EXC-HINT-03, EXC-HINT-05, EXC-HINT-11, EXC-HINT-19 |
| | R7a [BUG-465] | EXC-HINT-08 |
| | R8 | EXC-HINT-01, -03, -05, -07, -10, -11 |
| | R9 | EXC-HINT-18 |
| | Side effect "does not roll back the session" | not testable at unit level (the handler receives no session); no case |
| `database_error_handler` | R1 | EXC-HDB-01, EXC-HDB-02 |
| | R2 | EXC-HDB-01, EXC-HDB-02 |
| | R3 | EXC-HDB-03 |
| `schema_error_handler` | R1 | EXC-HSCH-01, EXC-HSCH-02 |
| | R1a [BUG-466] | EXC-HSCH-03, -04, -05 (xfail); EXC-HSCH-06 (pass) |
| | R2 | EXC-HSCH-01 (DEBUG true), EXC-HSCH-02 (DEBUG false) |
| | R3 | EXC-HSCH-01, EXC-HSCH-02, EXC-HSCH-06 |
| | R4 | EXC-HSCH-01, EXC-HSCH-06 |
| `generic_exception_handler` | R1 | EXC-HGEN-01, EXC-HGEN-02 |
| | R2 | EXC-HGEN-01, EXC-HGEN-02 |
| | R3 | EXC-HGEN-03, EXC-HGEN-04 |
