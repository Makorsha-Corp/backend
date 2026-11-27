# Spec — `app/core/exceptions.py`

> **Status:** APPROVED
> **Source commit:** e48a092

## Review
> Reviewer: answer each question on its **Answer:** line with one of
> `intended` · `bug` · `bug — <what it should do instead>` · `remove` (unreachable
> code only) · or a question back.
> Then run the describer in `apply-review` mode.

### New questions

### Q1. Validation failures write the raw submitted values (e.g. passwords) to the error log — 🐞 BUG-460
**Background:** When a request body/query fails schema validation, Pydantic produces a list of error entries. Each entry carries an `input` field holding the value that failed — for a "field missing" error it is the **whole request body**. The handler logs that full list verbatim, at ERROR level, three times (plus one WARNING with the sanitized list).
**What happens today:** Every submitted value involved in a validation failure — including passwords, tokens, personal data — is copied into the application logs.
**Example:** A user posts `{"email": "a@b.com", "password": "Hunter2!"}` to a login/sign-up endpoint that also requires a `name` field. The response is a normal 400, but the server log now contains the line `[VALIDATION] Full error details: [{'type': 'missing', 'loc': ('body', 'name'), ..., 'input': {'email': 'a@b.com', 'password': 'Hunter2!'}}]`.
**Rules affected:** `validation_exception_handler` R6
**Answer:** bug — log once at WARNING with only field/message/code; never log input values (reviewer accepted suggestion)
**Suggested answer:** bug — log a validation failure once, at WARNING, with only field path, message and code (the sanitized `errors` list); never log `input` values.
**Resolution:** a validation failure produces exactly one log record — the existing WARNING `"Validation error"` with the sanitized `errors` list — and no log record contains any submitted value. Rules: `validation_exception_handler` R6, R6a.

### Q2. Request validation errors return 400, but the house rules expect 422 — 🐞 BUG-461
**Background:** FastAPI's default for a request that fails schema validation is 422. This handler overrides it to 400 for every such failure (bad body, bad query parameter, missing field). House rules HR-1 (blank names rejected by the schema, "422") and HR-7 (`limit >= 1`, "422 otherwise") were written assuming 422, and the app's own `BusinessRuleError` uses 422.
**What happens today:** Any schema-level rejection reaches the client as HTTP 400 with `type .../validation_error`.
**Example:** `GET /items/?limit=0` after the HR-7 fix adds `ge=1`: the client gets **400**, not the 422 that HR-7 and the tests written from it expect. Same for a blank department name after the HR-1 fix.
**Rules affected:** `validation_exception_handler` R1
**Answer:** bug — return 422 for request-schema validation failures (consistent with HR-1/HR-7); keep 400 for the explicit ValidationError class, or else edit the house rules (reviewer accepted suggestion)
**Suggested answer:** bug — return 422 (`"status": 422`) for request-schema validation failures, consistent with HR-1/HR-7 and FastAPI's convention; keep 400 for the explicit `ValidationError` class. (If 400 is kept deliberately, HR-1/HR-7 must be edited instead.)
**Resolution:** request-schema validation failures return HTTP 422 with `"status": 422`; house rules HR-1/HR-7 stay as written (422 chosen over editing the house rules — best-practice default, delegated by reviewer). The explicit `ValidationError` class stays 400. Rules: `validation_exception_handler` R1a.

### Q3. Database-constraint errors are classified by searching the whole error text, including the SQL and submitted values — 🐞 BUG-462
**Background:** When the database rejects a write (unique, foreign-key, not-null, check constraint), the handler picks the client message by searching the error's text for words. That text contains not only the database's message but also the full SQL statement and every parameter value the user submitted. The words are checked in the order "unique"/"duplicate" → "foreign key" → "not null"/"null value".
**What happens today:** A column name, table name, constraint name or user-entered value that contains "unique" or "duplicate" makes any constraint error look like a duplicate.
**Example:** A user creates an item with description "Unique handmade bowl" and an unknown `category_id`. The real error is a foreign-key violation, but because the SQL parameters contain "Unique" the user sees 409 "This resource already exists. Please use a different value."
**Rules affected:** `integrity_error_handler` R3–R6
**Answer:** bug — classify by exc.orig.pgcode (23505/23503/23502/23514), never by message text (reviewer accepted suggestion)
**Suggested answer:** bug — classify by the database error code (`exc.orig.pgcode`: 23505 unique, 23503 foreign key, 23502 not null, 23514 check), never by searching the message/SQL text.
**Resolution:** classification uses the SQLSTATE code of the underlying driver error only. An error without a code (non-driver cause) is treated as unclassified (best-practice default, delegated by reviewer). Rules: `integrity_error_handler` R2.

### Q4. Deleting a record that other records still reference says "Referenced resource does not exist" — 🐞 BUG-463
**Background:** A foreign-key violation happens in two directions: inserting a child that points to a missing parent, **or** deleting/updating a parent that children still point to. The handler gives both the same message.
**What happens today:** Any foreign-key violation returns 409 "Referenced resource does not exist."
**Example:** A user hard-deletes a supplier that still has purchase orders. The database refuses ("is still referenced from table purchase_orders"), and the user is told 409 "Referenced resource does not exist." — the opposite of the real reason.
**Rules affected:** `integrity_error_handler` R4
**Answer:** bug — a delete/update blocked by references returns 409 'This resource is still in use by other records.' (reviewer accepted suggestion)
**Suggested answer:** bug — a delete/update blocked by existing references returns 409 "This resource is still in use by other records."; only a missing referenced row returns "Referenced resource does not exist."
**Resolution:** the two directions get different messages. Both share SQLSTATE 23503, so the direction is read from the driver's structured primary message (`exc.orig.diag.message_primary` starts with `update or delete on table` → still referenced), never from the SQL/parameters (best-practice default, delegated by reviewer). Rules: `integrity_error_handler` R4, R4a.

### Q5. Check-constraint and other constraint violations are reported as "may already exist" (409) — 🐞 BUG-464
**Background:** Constraint errors that are not unique / foreign-key / not-null (e.g. a CHECK constraint such as `quantity > 0`, or an exclusion constraint) fall into the default branch.
**What happens today:** They return 409 with "A database constraint was violated. The resource may already exist."
**Example:** A table has `CHECK (quantity >= 0)`; a request that would store `-5` gets 409 "The resource may already exist." — the client treats it as a duplicate and the user cannot tell what to fix.
**Rules affected:** `integrity_error_handler` R6
**Answer:** bug — check violations return 422 validation_error with a value-not-allowed message; generic fallback drops the 'may already exist' guess (reviewer accepted suggestion)
**Suggested answer:** bug — check-constraint violations return 422 "A value is outside the allowed range." (type `validation_error`); only the truly unclassified case keeps the generic 409 message, without the "may already exist" guess.
**Resolution:** check violations (23514) → 422, title `"Validation Error"`, type slug `validation_error`, detail `"A value is outside the allowed range."` (text taken from the accepted suggestion). Unclassified violations (e.g. exclusion 23P01, or no code) → 409 conflict with detail `"A database constraint was violated."` (best-practice default for the exact fallback text, delegated by reviewer). Rules: `integrity_error_handler` R5a, R6a.

### Q6. A missing required field (not-null) is returned as 400 but labelled "Resource Conflict" — 🐞 BUG-465
**Background:** For a not-null violation the handler switches the HTTP status to 400 but keeps the conflict labelling used for 409s.
**What happens today:** The body says `"status": 400`, `"title": "Resource Conflict"`, `"type": ".../errors/conflict"`.
**Example:** A create request that leaves a required DB column null gets HTTP 400 whose body claims a "Resource Conflict" of type `conflict`; a client that switches on `type` shows a duplicate-entry message.
**Rules affected:** `integrity_error_handler` R5, R7
**Answer:** bug — 400 not-null uses title 'Validation Error' and type validation_error (reviewer accepted suggestion)
**Suggested answer:** bug — title and type follow the status: 400 not-null → `title "Validation Error"`, `type .../errors/validation_error`; 409 cases keep `conflict`.
**Resolution:** not-null stays HTTP 400 but is labelled `"Validation Error"` / `validation_error`. Rules: `integrity_error_handler` R7a.

### Q7. Every SQL programming error is reported as "database temporarily unavailable" (503) — 🐞 BUG-466
**Background:** The handler is meant for migrations not applied (missing table/column), but it catches every `ProgrammingError`: SQL syntax errors, calling an unknown function, wrong operator types, insufficient privileges — i.e. code bugs. 503 tells clients the failure is temporary and worth retrying. `settings.DEBUG` defaults to `True`.
**What happens today:** All of these return 503 "Service Unavailable"; with DEBUG on the detail says "Database schema is out of date — run `alembic upgrade head` and restart the API.", with DEBUG off "Database service is temporarily unavailable. Please try again later."
**Example:** A query with a typo in a raw SQL fragment fails on every call; clients see 503 "try again later" (and in DEBUG, "run alembic upgrade"), retry forever, and the error is not counted as a 500 in monitoring.
**Rules affected:** `schema_error_handler` R1, R2
**Answer:** bug — only undefined table/column (42P01, 42703) return 503; other ProgrammingErrors return the generic 500 (reviewer accepted suggestion)
**Suggested answer:** bug — only undefined table/column (pgcode 42P01, 42703) return 503 with the schema message; every other `ProgrammingError` is treated as an unexpected error (500, same body as `generic_exception_handler`).
**Resolution:** 503 only for SQLSTATE 42P01 / 42703; any other `ProgrammingError` (other code, or no code) → 500 with the `generic_exception_handler` body. The single `"Database schema error"` ERROR log is kept for every `ProgrammingError` (best-practice default, delegated by reviewer). Rules: `schema_error_handler` R1, R1a.

### Q8. Error `type` URLs point at the placeholder domain `api.yourdomain.com` — 🐞 BUG-467
**Background:** In the RFC 7807 error format, `type` is a URI identifying the kind of error, which clients may follow or switch on.
**What happens today:** Every error body's `type` is `https://api.yourdomain.com/errors/<error_type>` — a template placeholder domain the company does not own.
**Example:** A 404 returns `"type": "https://api.yourdomain.com/errors/not_found"`; anyone following the link lands on an unrelated or non-existent site.
**Rules affected:** `api_exception_handler` R3, `validation_exception_handler` R1, `integrity_error_handler` R7, `database_error_handler` R1, `schema_error_handler` R1, `generic_exception_handler` R1
**Answer:** bug — build type from a configured owned base URL or use relative /errors/<type> (reviewer accepted suggestion)
**Suggested answer:** bug — build `type` from a configured base URL on a domain we own (setting, e.g. `ERROR_TYPE_BASE_URL`), or use a relative URI `/errors/<error_type>`; never a placeholder domain.
**Resolution:** both options combined: new setting `ERROR_TYPE_BASE_URL` (default `""`); `type` = `ERROR_TYPE_BASE_URL + "/errors/<error_type>"`, so the default is the relative URI `/errors/<error_type>` (best-practice default, delegated by reviewer). Rules: `api_exception_handler` R3a (applies to every handler).

### Q9. Error responses claim RFC 7807 but are sent as `application/json` — 🐞 BUG-468
**Background:** The docstrings say responses are "RFC 7807 Problem Details". RFC 7807 specifies the media type `application/problem+json` so clients can recognise the format.
**What happens today:** All handler responses have `Content-Type: application/json`.
**Example:** A client library that detects problem documents by `Content-Type: application/problem+json` does not recognise our 404 body as one.
**Rules affected:** `api_exception_handler` R3 (and the same for every handler)
**Answer:** bug — send Content-Type application/problem+json (body unchanged) (reviewer accepted suggestion)
**Suggested answer:** bug — send `Content-Type: application/problem+json` on every handler response (body unchanged).
**Resolution:** every handler response has media type `application/problem+json`; body unchanged. Rules: `api_exception_handler` R3b (applies to every handler).

### Q10. `AuthenticationError` (401) is never raised anywhere — 🗑 removed
**Background:** Authentication failures in the app are raised elsewhere (FastAPI `HTTPException`/security dependencies); no code under `app/` raises or imports `AuthenticationError`.
**What happens today:** The class exists and works if raised, but no request can ever produce it.
**Example:** A grep for `AuthenticationError` in `app/` finds only its definition; a test for it protects nothing a user can hit.
**Rules affected:** `AuthenticationError.__init__` R1–R2
**Answer:** remove (reviewer accepted suggestion)
**Suggested answer:** remove
**Resolution:** moved to Not specified as dead code; logged in `tests/unit/core/exceptions.deadcode-staging.md`.

### Q11. An empty or `null` request id set by upstream code is used as-is — 🐞 BUG-469
**Background:** The request-id middleware normally stores a `req_…` id on `request.state.request_id`; each handler reuses it, or generates a fresh one only when the attribute does not exist at all. Raised during fill-gaps (cases gap 2).
**What happens today:** If the attribute exists but is `None`, building the response crashes (`AttributeError: 'NoneType' object has no attribute 'encode'` while encoding the `X-Request-ID` header), so the error handler itself fails. If it is `""`, the response carries an empty `X-Request-ID` header and `"request_id": ""` in the body.
**Example:** Some code sets `request.state.request_id = ""` and a route then raises `NotFoundError`; the client gets a 404 whose request id is empty, so support cannot correlate it with the server logs.
**Rules affected:** `api_exception_handler` R1a (request-id rule, every handler)
**Answer:** bug — a falsy request id counts as absent; generate a fresh `req_…` id (best-practice default, delegated by reviewer)
**Resolution:** falsy `request.state.request_id` (`None`, `""`) is treated as not set and a fresh `req_` + 32-hex id is generated; a response never carries an empty or null request id (best-practice default, delegated by reviewer). Rules: `api_exception_handler` R1a (applies to every handler).

## Overview
Defines the app's typed business exceptions (`APIException` and its 4xx
subclasses raised by managers/services) and the six FastAPI exception handlers
that turn exceptions into JSON error bodies in an RFC 7807-like shape
(`type`, `title`, `status`, `detail`, `instance`, `request_id`, optional
`errors`) with an `X-Request-ID` header. `app/main.py` registers the handlers:
`APIException`, `RequestValidationError`, `IntegrityError`, `OperationalError`,
`ProgrammingError`, and `Exception` as catch-all. Invariant it protects: clients
never see raw exception text, SQL or stack traces — only fixed, sanitized
messages plus a request id that correlates with server logs.

**Callables:** 12 specified · 1 not specified
**Externals to mock:** none (`uuid.uuid4` may be patched to pin the fallback request id; `settings.DEBUG` and — after BUG-467 — `settings.ERROR_TYPE_BASE_URL` patched as needed)
**Integration-only behavior:** which handler Starlette picks for a given exception (registration in `app/main.py`, MRO lookup) and whether CORS/security headers are added to the response — needs the real app stack.

**Notes for the test designer:**
- This is framework glue. Handlers are plain `async` functions: call them directly
  (`asyncio.run(...)` or `pytest.mark.anyio`) with a `starlette.requests.Request`
  built from a minimal scope, e.g.
  `{"type": "http", "method": "POST", "path": "/api/v1/x", "headers": [(b"user-agent", b"ua")], "client": ("1.2.3.4", 5), "query_string": b"", "state": {}}`.
  Put `request_id` into `scope["state"]` to simulate the middleware; omit it to
  exercise the fallback; set `"client": None` for the no-client branch.
- Alternatively register the handler(s) on a **minimal** `FastAPI()` app with a
  route that raises, and use `TestClient` (for `generic_exception_handler` use
  `TestClient(app, raise_server_exceptions=False)`). Never start `app.main.app`.
- `RequestValidationError` can be built directly: `RequestValidationError([{"type": "missing", "loc": ("body", "name"), "msg": "Field required", "input": {...}}])`, or produced by a minimal route with a Pydantic body model.
- `IntegrityError` / `OperationalError` / `ProgrammingError` can be built as
  `IntegrityError("INSERT ...", {"p": "v"}, Exception("<db message>"))`; their
  `str()` contains the db message, the SQL (`[SQL: ...]`) and the parameters
  (`[parameters: ...]`). Such a synthetic cause (`Exception`) has **no SQLSTATE
  code** — after BUG-462/BUG-466 it takes the "no code" path. To get a real code,
  provoke the violation on the test Postgres through the session (driver is
  psycopg2; `exc.orig.pgcode` holds the SQLSTATE and `exc.orig.diag.message_primary`
  the database's primary message), e.g. insert a duplicate into a unique column
  (23505), insert a row with an unknown FK (23503, primary message starts
  `insert or update on table`), delete a parent that is still referenced (23503,
  primary message starts `update or delete on table`), insert NULL into a NOT NULL
  column (23502), violate a CHECK constraint (23514; a temp table with a CHECK is
  fine), `SELECT * FROM no_such_table` (42P01), `SELECT no_such_col FROM <table>`
  (42703), `SELEC 1` (42601 syntax error). Use a savepoint (`begin_nested`) so the
  per-test transaction survives the error. A stand-in cause object with `pgcode`
  and `diag.message_primary` attributes is also acceptable.
- No DB state is read or written by the module itself. Log assertions via
  `caplog` (logger name `app.core.exceptions`); extra fields appear as attributes
  on the log record.

## Not specified
- `AuthenticationError.__init__` — dead code, to be removed (reviewer)

---

## `APIException.__init__(status_code, error_type, title, detail, errors=None)`
**Shape:** helper
**Persistence:** pure
**Visibility:** public (base of all subclasses below; also raised/caught directly in a few places)

**Purpose:** Carry everything needed to render a structured API error.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| status_code | int | HTTP status; not validated |
| error_type | str | machine slug used in the `type` URI; not validated |
| title | str | short human title; not validated |
| detail | str | human message; not validated |
| errors | list[dict] \| None | optional field-level errors; default `None` |

**Returns:** the exception instance.

**Rules:**
- **R1.** The five arguments are stored unchanged as attributes `status_code`, `error_type`, `title`, `detail`, `errors`.
- **R2.** `errors` defaults to `None` when not given.
- **R3.** `str(exc)` equals `detail`, and `exc.args == (detail,)`.
- **R4.** It is an `Exception` subclass (can be raised/caught as `Exception`).

**Errors:** none
**Side effects:** none

---

## `ValidationError.__init__(detail, errors=None)`
**Shape:** helper · **Persistence:** pure · **Visibility:** public

**Purpose:** Explicit 400 for input the app rejects itself (not the schema-level handler).

**Rules:**
- **R1.** Produces an `APIException` with `status_code 400`, `error_type "validation_error"`, `title "Validation Error"`, the given `detail`, and the given `errors`. (Stays 400 — see Q2.)
- **R2.** `errors` defaults to `None`.
- **R3.** `detail` is required (no default).

**Errors:** none · **Side effects:** none

---

## `PermissionDeniedError.__init__(detail="You do not have permission to perform this action")`
**Shape:** helper · **Persistence:** pure · **Visibility:** public

**Rules:**
- **R1.** Produces an `APIException` with `status_code 403`, `error_type "permission_denied"`, `title "Permission Denied"`, `errors None`.
- **R2.** `detail` defaults to `"You do not have permission to perform this action"`; a given detail is used as-is.

**Errors:** none · **Side effects:** none

---

## `NotFoundError.__init__(detail)`
**Shape:** helper · **Persistence:** pure · **Visibility:** public

**Rules:**
- **R1.** Produces an `APIException` with `status_code 404`, `error_type "not_found"`, `title "Resource Not Found"`, the given `detail`, `errors None`.
- **R2.** `detail` is required (no default).

**Errors:** none · **Side effects:** none

---

## `ConflictError.__init__(detail)`
**Shape:** helper · **Persistence:** pure · **Visibility:** public

**Rules:**
- **R1.** Produces an `APIException` with `status_code 409`, `error_type "conflict"`, `title "Resource Conflict"`, the given `detail`, `errors None`.
- **R2.** `detail` is required (no default).

**Errors:** none · **Side effects:** none

---

## `BusinessRuleError.__init__(detail, errors=None)`
**Shape:** helper · **Persistence:** pure · **Visibility:** public

**Rules:**
- **R1.** Produces an `APIException` with `status_code 422`, `error_type "business_rule_violation"`, `title "Business Rule Violation"`, the given `detail` and `errors`.
- **R2.** `errors` defaults to `None`.
- **R3.** `detail` is required (no default).

**Errors:** none · **Side effects:** none

---

## `api_exception_handler(request, exc)` *(async)*
**Shape:** mapper
**Persistence:** pure
**Visibility:** public (registered in `app/main.py` for `APIException` and all subclasses)

**Purpose:** Render a typed business exception as a structured JSON error.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| request | Request | may or may not carry `state.request_id`; `client` may be `None` |
| exc | APIException | any instance / subclass instance |

**Returns:** `JSONResponse`.

**Rules:**
- **R1.** Request id: if `request.state.request_id` is set, that value is used; otherwise a new id of the form `req_` + 32 lowercase hex chars is generated (fresh per call). *(Same rule applies to every handler below — referred to as "request-id rule".)* ✅
- **R1a.** [BUG-469] A `request.state.request_id` that is present but falsy (`None` or `""`) counts as **not set**: a fresh `req_` + 32 lowercase hex id is generated and used in the `X-Request-ID` header, the body `request_id` and the log record; the response is rendered normally. A response never carries an empty or `null` request id. *(Today: `None` → the handler raises `AttributeError` while encoding the header, no response is produced; `""` → empty `X-Request-ID` header and `"request_id": ""`.)* **Part of the request-id rule — applies identically to every handler below.** (best-practice default, delegated by reviewer)
- **R2.** HTTP status = `exc.status_code`; header `X-Request-ID` = the request id. ✅
- **R3.** Body = `{"type": <type URI ending in "/errors/<exc.error_type>">, "title": exc.title, "status": exc.status_code, "detail": exc.detail, "instance": <request URL path only, no query string>, "request_id": <id>}` — no other keys except `errors` (R4).
- **R3a.** [BUG-467] `type` is `settings.ERROR_TYPE_BASE_URL + "/errors/<error_type>"`. With the default setting (`""`) this is the relative URI `/errors/<error_type>` (e.g. `/errors/not_found`); with the setting set to e.g. `https://api.example.com` it is `https://api.example.com/errors/not_found`. It never contains `yourdomain`. *(requires new setting `ERROR_TYPE_BASE_URL: str = ""` in `app/core/config.py`)* *(Today: always `https://api.yourdomain.com/errors/<error_type>`.)* **Applies identically to every handler below.**
- **R3b.** [BUG-468] The response media type (`Content-Type`) is `application/problem+json`; the body is unchanged. *(Today: `application/json`.)* **Applies identically to every handler below.**
- **R4.** If `exc.errors` is a non-empty list, the body additionally has `"errors": exc.errors` (unchanged). If `errors` is `None` **or an empty list**, the `errors` key is absent. ✅
- **R5.** One ERROR log record, message `"API Error: <title>"`, with extra fields `request_id`, `error_type`, `status_code`, `detail`, `path`, `method`, `user_agent` (the `user-agent` header or `None`), `ip_address` (client host, or `None` when the request has no client). Logged at ERROR for every status, including 4xx.

**Errors:** none raised.
**Side effects:** one log record.

---

## `validation_exception_handler(request, exc)` *(async)*
**Shape:** mapper
**Persistence:** pure
**Visibility:** public (registered for FastAPI `RequestValidationError`)

**Purpose:** Render request-schema validation failures with per-field errors.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| request | Request | as above |
| exc | RequestValidationError | `exc.errors()` is a list of dicts with at least `loc`, `msg`, `type` |

**Returns:** `JSONResponse`.

**Rules:**
- **R1.** Header `X-Request-ID`; body `{"type": <type URI ending in "/errors/validation_error">, "title": "Validation Error", "status": <R1a>, "detail": "Request validation failed", "instance": <path>, "request_id": <id>, "errors": [...]}`. Request id per `api_exception_handler` R1; `type` per `api_exception_handler` R3a; media type per R3b.
- **R1a.** [BUG-461] HTTP status is **422** and the body's `"status"` is `422`, for every request-schema validation failure (body, query, path, header). *(Today: 400.)*
- **R2.** `errors` has one entry per validation error, in the same order, each `{"field": ..., "message": <msg>, "code": <type>}`. With zero validation errors, `errors` is `[]` (key present). ✅
- **R3.** `field` is the error location joined with `.`, every element converted to text (list indices become digits: `("body","items",0,"qty")` → `"items.0.qty"`), with every element equal to the string `"body"` dropped. ✅
- **R4.** Other location prefixes are kept: `("query","limit")` → `"query.limit"`, `("path","id")` → `"path.id"`, `("header","x-workspace-id")` → `"header.x-workspace-id"`. ✅
- **R5.** If nothing is left after dropping `"body"` (location `("body",)` — e.g. whole body missing or not an object), `field` is `"body"`. ✅
- **R6.** One WARNING log record `"Validation error"` with extra `request_id`, `errors` (the formatted list from R2, i.e. only `field`/`message`/`code`), `path`, `method`.
- **R6a.** [BUG-460] That WARNING is the **only** log record the handler emits (no ERROR records), and no log record — message text or extra fields — contains any submitted `input` value (e.g. a password in the request body must not appear anywhere in `caplog`). *(Today: three additional ERROR records `"[VALIDATION] Request validation failed for <METHOD> <path>"`, `"[VALIDATION] Full error details: <raw exc.errors()>"` (includes raw `input` values), `"[VALIDATION] Formatted errors: <errors list>"`.)*
- **R7.** The response body never contains the submitted `input` values or Pydantic `ctx`/`url` fields — only `field`, `message`, `code`. ✅

**Errors:** none raised.
**Side effects:** one log record (intended; four today).

---

## `integrity_error_handler(request, exc)` *(async)*
**Shape:** mapper
**Persistence:** pure
**Visibility:** public (registered for SQLAlchemy `IntegrityError`)

**Purpose:** Turn a database constraint violation into a sanitized client error.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| request | Request | as above |
| exc | IntegrityError | `exc.orig` is the driver (psycopg2) error with `pgcode` (SQLSTATE) and `diag.message_primary`; `str(exc)` = DB message + `[SQL: …]` + `[parameters: …]` |

**Returns:** `JSONResponse`.

**Rules:**
- **R1.** Request id per `api_exception_handler` R1; header `X-Request-ID`; media type per `api_exception_handler` R3b.
- **R2.** [BUG-462] The kind of violation is decided **only** by the SQLSTATE code of the underlying driver error (`exc.orig.pgcode`): `23505` → R3, `23503` → R4/R4a, `23502` → R5, `23514` → R5a, any other code or no code at all → R6/R6a. The text of the message, SQL, constraint/table/column names and parameter values never influences the outcome — e.g. a foreign-key violation (23503) whose parameters contain "Unique handmade bowl" gets the R4 answer, and a cause with no code whose text contains "unique" gets the R6 answer. *(Today: case-insensitive substring search over the whole `str(exc)`, first match wins: `unique`/`duplicate` → `foreign key` → `not null`/`null value` → default.)*
- **R3.** Unique violation → 409, detail `"This resource already exists. Please use a different value."` ✅
- **R4.** Foreign-key violation because the referenced row does not exist (insert/update of the referencing row; Postgres primary message `insert or update on table …`) → 409, detail `"Referenced resource does not exist."` ✅
- **R4a.** [BUG-463] Foreign-key violation because the row being deleted/updated is still referenced by other rows (Postgres primary message `update or delete on table …`) → 409, detail `"This resource is still in use by other records."` The direction is read from the driver's structured primary message, never from the SQL/parameters. *(Today: `"Referenced resource does not exist."`.)*
- **R4b.** [BUG-462] A foreign-key violation (SQLSTATE `23503`) whose direction cannot be read — `exc.orig.diag` missing or `None`, `diag.message_primary` missing or `None`, or a primary message starting with neither `insert or update on table` nor `update or delete on table` — gets the R4 answer: 409, title `"Resource Conflict"`, type slug `conflict`, detail `"Referenced resource does not exist."` It never falls to R6 and never raises. (best-practice default, delegated by reviewer) *(Today: classification is by text, so the outcome follows the exception text: if `str(exc)` contains `foreign key` (case-insensitive) → R4 answer; otherwise → today's R6 default, 409 "A database constraint was violated. The resource may already exist.". Real Postgres 23503 errors always carry a primary message, so this branch is reachable only with a stand-in cause object.)*
- **R5.** Not-null violation → **400**, detail `"Required field is missing."` ✅
- **R5a.** [BUG-464] Check-constraint violation (23514) → **422**, title `"Validation Error"`, type slug `validation_error`, detail `"A value is outside the allowed range."` *(Today: falls into the default → 409, conflict, "A database constraint was violated. The resource may already exist.")*
- **R6.** Any other violation (e.g. exclusion constraint 23P01) or a cause without a code → 409, title `"Resource Conflict"`, type slug `conflict`.
- **R6a.** [BUG-464] The R6 detail is `"A database constraint was violated."` — no "may already exist" guess. *(Today: `"A database constraint was violated. The resource may already exist."`.)*
- **R7.** Body `{"type": <type URI per api_exception_handler R3a>, "title": …, "status": <same as HTTP status>, "detail": <as above>, "instance": <path>, "request_id": <id>}` (no `errors` key). For every 409 outcome (R3, R4, R4a, R6) the title is `"Resource Conflict"` and the type slug `conflict`.
- **R7a.** [BUG-465] For the not-null outcome (R5, HTTP 400) the title is `"Validation Error"` and the type slug `validation_error`. *(Today: `"Resource Conflict"` / `conflict`.)*
- **R8.** The response never contains the raw DB message, SQL, constraint names or parameters. ✅
- **R9.** One ERROR log `"Database integrity error"` with extra `request_id`, `error` (full exception text), `path`, and the traceback attached (`exc_info`).

**Errors:** none raised.
**Side effects:** one log record. Does not roll back the session.

---

## `database_error_handler(request, exc)` *(async)*
**Shape:** mapper
**Persistence:** pure
**Visibility:** public (registered for SQLAlchemy `OperationalError` — connection loss, timeouts, deadlocks, etc.)

**Rules:**
- **R1.** Always HTTP 503, header `X-Request-ID`; body `{"type": <type URI ending in "/errors/service_unavailable">, "title": "Service Unavailable", "status": 503, "detail": "Database service is temporarily unavailable. Please try again later.", "instance": <path>, "request_id": <id>}`, regardless of the exception content. Request id per `api_exception_handler` R1; `type` per R3a; media type per R3b.
- **R2.** No `Retry-After` header; raw error text never in the response.
- **R3.** One ERROR log `"Database operational error"` with extra `request_id`, `error` (full text), `path`, traceback attached.

**Errors:** none raised · **Side effects:** one log record.

---

## `schema_error_handler(request, exc)` *(async)*
**Shape:** mapper
**Persistence:** pure
**Visibility:** public (registered for SQLAlchemy `ProgrammingError` — any SQLSTATE class 42 error, not only missing tables/columns)

**Rules:**
- **R1.** A `ProgrammingError` whose driver SQLSTATE (`exc.orig.pgcode`) is `42P01` (undefined table) or `42703` (undefined column) → HTTP 503, header `X-Request-ID`; body `{"type": <type URI ending in "/errors/service_unavailable">, "title": "Service Unavailable", "status": 503, "detail": <R2>, "instance": <path>, "request_id": <id>}`. Request id per `api_exception_handler` R1; `type` per R3a; media type per R3b.
- **R1a.** [BUG-466] Any other `ProgrammingError` — another SQLSTATE (e.g. `42601` syntax error, `42883` undefined function, `42501` insufficient privilege) or no code at all — → HTTP 500 with header `X-Request-ID` and the same body as `generic_exception_handler` R1 (`title "Internal Server Error"`, `status 500`, type slug `internal_error`, detail `"An unexpected error occurred. Please contact support with the request ID."`), independent of `settings.DEBUG`. *(Today: 503 with the R2 detail for every `ProgrammingError`.)*
- **R2.** For the 503 case, `detail` is `"Database schema is out of date — run \`alembic upgrade head\` and restart the API."` (em dash, backticks literal) when `settings.DEBUG` is truthy, else `"Database service is temporarily unavailable. Please try again later."`. `settings.DEBUG` defaults to `True`.
- **R3.** Raw error text never in the response (both outcomes).
- **R4.** One ERROR log `"Database schema error"` with extra `request_id`, `error`, `path`, traceback attached — for every `ProgrammingError`, both outcomes (best-practice default, delegated by reviewer).

**Errors:** none raised · **Side effects:** one log record.

---

## `generic_exception_handler(request, exc)` *(async)*
**Shape:** mapper
**Persistence:** pure
**Visibility:** public (registered for `Exception` — anything not handled above, e.g. `DataError`, `ValueError`, `KeyError`)

**Rules:**
- **R1.** Always HTTP 500, header `X-Request-ID`; body `{"type": <type URI ending in "/errors/internal_error">, "title": "Internal Server Error", "status": 500, "detail": "An unexpected error occurred. Please contact support with the request ID.", "instance": <path>, "request_id": <id>}`. Request id per `api_exception_handler` R1; `type` per R3a; media type per R3b.
- **R2.** The exception class name and message never appear in the response.
- **R3.** One ERROR log with traceback (`logger.exception`), message `"Unexpected error"`, extra `request_id`, `error_type` (exception class name), `error` (`str(exc)`), `path`, `method`, `user_agent` (or `None`), `ip_address` (client host or `None`).

**Errors:** none raised · **Side effects:** one log record.

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 30 | `errors` default `None` | `APIException.__init__` R2 |
| 37 | message passed to `Exception` | `APIException.__init__` R3 |
| 44 | `errors` default | `ValidationError.__init__` R2 |
| 67 | `detail` default | `PermissionDeniedError.__init__` R2 |
| 100 | `errors` default | `BusinessRuleError.__init__` R2 |
| 119 | `state.request_id` present / absent | `api_exception_handler` R1 |
| 119 (intended; all handlers: 119, 162, 209, 258, 289, 326) | `state.request_id` present but falsy (`None` / `""`) | `api_exception_handler` R1a |
| 131 | `user-agent` header present / absent | `api_exception_handler` R5 |
| 132 | `request.client` present / `None` | `api_exception_handler` R5 |
| 138 | `type` URI construction (all handlers: 138, 193, 244, 275, 311, 348) | `api_exception_handler` R3a |
| 147 | `exc.errors` truthy / `None` / `[]` | `api_exception_handler` R4 |
| 150 | response media type (all handlers: 150, 189, 240, 271, 307, 344) | `api_exception_handler` R3b |
| 162 | request id present / absent | `validation_exception_handler` R1 |
| 166 | loop over errors: zero / one / many | `validation_exception_handler` R2 |
| 167 | location element == `"body"` dropped / kept; non-str elements | `validation_exception_handler` R3, R4 |
| 169 | joined path empty → `"body"` | `validation_exception_handler` R5 |
| 175–187 | logging | `validation_exception_handler` R6, R6a |
| 190 | status 400 (intended 422) | `validation_exception_handler` R1a |
| 209 | request id present / absent | `integrity_error_handler` R1 |
| 226 | classification input (text today; SQLSTATE intended) | `integrity_error_handler` R2 |
| 227 | `unique` / `duplicate` in text (intended: 23505) | `integrity_error_handler` R3 |
| 229 | `foreign key` in text (intended: 23503 + direction) | `integrity_error_handler` R4, R4a |
| — (intended new branch) | 23503 with missing / `None` / unrecognised primary message | `integrity_error_handler` R4b |
| 231 | `not null` / `null value` in text (intended: 23502) | `integrity_error_handler` R5 |
| — (intended new branch) | 23514 check violation | `integrity_error_handler` R5a |
| 223 (fallthrough) | none matched / other code / no code | `integrity_error_handler` R6, R6a |
| 234–238, 244–245 | status 400 iff not-null detail, else 409; title/type per outcome | `integrity_error_handler` R5, R7, R7a |
| 258 | request id present / absent | `database_error_handler` R1 |
| 289 | request id present / absent | `schema_error_handler` R1 |
| — (intended new branch) | SQLSTATE 42P01/42703 vs other / none | `schema_error_handler` R1, R1a |
| 303 | `settings.DEBUG` truthy / falsy | `schema_error_handler` R2 |
| 326 | request id present / absent | `generic_exception_handler` R1 |
| 337 | `user-agent` present / absent | `generic_exception_handler` R3 |
| 338 | `request.client` present / `None` | `generic_exception_handler` R3 |

## Gap log
- G1 (exceptions.cases.md gap 1) — Intent (decided by best practice, delegated by reviewer) — added `integrity_error_handler` R4b: a 23503 whose direction cannot be read (diag / primary message missing, `None`, or unrecognised) gets the R4 answer (409 "Referenced resource does not exist."); tagged under existing BUG-462 (code-based classification), no new bug; Branch-map row added.
- G2 (exceptions.cases.md gap 2) — Intent (decided by best practice, delegated by reviewer) + Fact — added `api_exception_handler` R1a: a falsy `request.state.request_id` (`None`, `""`) counts as absent and a fresh `req_…` id is generated, for every handler; today `None` crashes the handler (`AttributeError`) and `""` yields an empty id — logged as BUG-469, resolved question Q11 added; Branch-map row added.
