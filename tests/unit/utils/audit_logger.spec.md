# Spec — `app/utils/audit_logger.py`

> **Status:** APPROVED
> **Source commit:** e48a092

## Review
> Reviewer: answer each question on its **Answer:** line with one of
> `intended` · `bug` · `bug — <what it should do instead>` · `remove` (unreachable
> code only) · or a question back.
> Then run the describer in `apply-review` mode.

### Precedent matches — confirm all with ok

### Q1. IP address and user agent are never recorded on financial audit rows — 🐞 BUG-140
**Background:** `log_financial_audit` accepts `ip_address` and `user_agent` and stores them on the audit row. It is called only from `AccountManager` (create/update/delete account) and `InvoicePaymentManager` (record/delete/void payment). None of these calls pass either value, and the managers do not receive the request's IP or user agent.
**What happens today:** Every financial audit row has `ip_address = NULL` and `user_agent = NULL`; the columns exist but can never be filled from the API.
**Example:** A user voids a 5,000 BDT payment from a browser at 203.0.113.7. The audit log shows who did it and when, but "IP address" and "device" are always empty, so a disputed void cannot be traced to a machine.
**Rules affected:** `log_financial_audit` R5
**Answer:** bug — per BUG-010 precedent: the request's client IP and user agent are passed from the endpoint through the service and manager into every `log_financial_audit` call, so audit rows record them (precedent — confirmed: ok)
**Resolution:** every API-driven financial audit row records the request's client IP and user agent; the fix threads both values from the endpoints through the services into `AccountManager`/`InvoicePaymentManager` and on into `log_financial_audit`. The client IP is the address as resolved by the server's trusted-proxy handling (e.g. uvicorn `--proxy-headers`/`forwarded-allow-ips`), never a raw, client-supplied `X-Forwarded-For` value (best-practice default, delegated by reviewer). Rules: `log_financial_audit` R5.

### New questions

### Q2. Money amounts are stored in the audit trail as floating-point numbers — 🐞 BUG-141
**Background:** `extract_relevant_fields` builds the before/after snapshots stored in the audit row's `changes` JSON. Amount columns are exact decimals (`Numeric`), but the helper converts every `Decimal` to a Python `float` before storing.
**What happens today:** Amounts are written to the audit JSON as binary floating-point numbers, not exact decimals. Values with more significant digits than a float can hold (about 15–17) are stored rounded, and trailing zeros are lost (`Decimal("2000.00")` becomes `2000.0`).
**Example:** A payment of `2000.00` shows up in the audit JSON as `2000.0`. A decimal amount with 18 significant digits, e.g. `1234567890123456.78`, is stored as `1234567890123456.8`, so the audit record no longer matches the ledger exactly.
**Rules affected:** `extract_relevant_fields` R3
**Answer:** bug — store Decimal values as their exact string form (e.g. "2000.00") so the audit trail always matches the ledger (reviewer accepted suggestion)
**Suggested answer:** bug — store `Decimal` values as their exact string form (e.g. `"2000.00"`), the usual practice for money in JSON audit trails, so the audit trail always matches the ledger to the cent
**Resolution:** a `Decimal` is stored as its exact fixed-point string, keeping every digit and trailing zero it has (`Decimal("2000.00")` → `"2000.00"`). Exponent notation is never produced: `Decimal("1E+2")` → `"100"`, `Decimal("1E-7")` → `"0.0000001"` (best-practice default, delegated by reviewer). Non-finite decimals are stored as `"NaN"`, `"Infinity"`, `"-Infinity"` (best-practice default, delegated by reviewer). Rules: `extract_relevant_fields` R3; the same conversion applies inside `changes` given to `log_financial_audit` (R7a).

### Q3. A value that cannot be stored as JSON makes the whole business operation fail — 🐞 BUG-142
**Background:** The audit row's `changes` column is a plain JSON column serialised with Python's standard `json.dumps`. The audit row is written in the same transaction as the business change (for example the payment) and is flushed immediately. `extract_relevant_fields` converts only `Decimal`, `datetime` and `date`; other values without an attribute dictionary (e.g. `UUID`, `time`, `timedelta`, `set`, or a `dict`/`list` containing a `Decimal`) are copied unchanged. `log_financial_audit` does no conversion at all on a `changes` dict built by hand.
**What happens today:** If a snapshot or a hand-built `changes` dict contains such a value, the flush raises an error and the caller's whole operation fails (500 at the API). The current callers only snapshot text, boolean, decimal and date fields, so this cannot happen from the API today. It would start as soon as someone audits a UUID, time or JSON-with-decimal column, or passes a raw `Decimal` in a hand-built `changes` dict.
**Example:** A developer adds `'invoice_amount': {'before': invoice.invoice_amount, ...}` (a `Decimal`) to a hand-built `changes` dict. Recording a payment then fails with a server error, and the payment is not saved.
**Rules affected:** `log_financial_audit` R7, `extract_relevant_fields` R7
**Answer:** bug — make every value JSON-safe before writing (recursively convert Decimal/datetime/date/time/UUID/enum, fall back to str()) so an audit write never fails the business operation (reviewer accepted suggestion)
**Suggested answer:** bug — audit logging makes every value JSON-safe before writing (convert `Decimal`/`datetime`/`date`/`time`/`UUID`/enum to strings, recursively inside nested dicts/lists, and fall back to `str()` for anything else) so an audit write never fails the business operation
**Resolution:** both `log_financial_audit` (on the whole `changes` dict) and `extract_relevant_fields` (on every value it keeps) make values JSON-safe, recursively through nested dicts, lists, tuples and sets. The conversion table is in `log_financial_audit` R7a. Choices the answer left open were decided as follows (best-practice default, delegated by reviewer): enum members → `.value` (per Q4, then converted again); `time` → ISO string; `timedelta` → `str()` fallback; tuples → lists; sets/frozensets → lists sorted by the converted elements' string form so the output is deterministic; non-`str` dict keys → `str(key)`; non-finite floats (`nan`, `inf`) → `"NaN"`/`"Infinity"`/`"-Infinity"`, because Postgres `json` rejects the bare `NaN` token; the caller's dict is never modified, and a converted copy is stored. Rules: `log_financial_audit` R4, R7, R7a, R7b; `extract_relevant_fields` R7.

### Q4. Objects in snapshots are dropped from the audit record without any trace — 🐞 BUG-143
**Background:** `extract_relevant_fields` skips any value that has an attribute dictionary and is not a `str`/`int`/`float`/`bool`. The aim is to skip ORM relationships, but the same check also matches plain `Enum` members (not `str`/`int` enums), one-to-many relationship lists, and any custom value object.
**What happens today:** The field is left out of the snapshot entirely, so the audit record does not show that the field was requested or what its value was.
**Example:** If `status` were a plain `Enum` column and a snapshot asked for `['name', 'status']`, the audit record would show only `name`, and a status change from `ACTIVE` to `SUSPENDED` would never appear in the audit trail.
**Rules affected:** `extract_relevant_fields` R6
**Answer:** bug — enum members are stored as their .value; other complex objects are still omitted (intended for relationships) (reviewer accepted suggestion)
**Suggested answer:** bug — enum members are stored as their `.value`; other complex objects are still omitted, which is intended for relationships
**Resolution:** every `Enum` member (plain, `str` or `int` enum) is stored as its `.value` as a plain value, not the member itself, and that value is made JSON-safe in turn. Related ORM objects, relationship collections and other custom class instances are still omitted. Rules: `extract_relevant_fields` R6, R6a.

### Q5. An over-long user agent or IP address would fail the audit write — 🐞 BUG-144
**Background:** The audit row's `user_agent` column holds at most 255 characters and `ip_address` at most 45. `log_financial_audit` stores whatever it is given, with no length check or truncation. Browser user-agent strings longer than 255 characters are common. This matters only once Q1 is fixed and callers start passing these values.
**What happens today:** Passing a `user_agent` longer than 255 characters (or an `ip_address` longer than 45) makes the database reject the row at flush, so the caller's business operation fails.
**Example:** After Q1 is fixed, a user on a browser with a 300-character user agent tries to record a payment. The request fails with a server error and the payment is not saved.
**Rules affected:** `log_financial_audit` R6
**Answer:** bug — truncate user_agent to 255 and ip_address to 45 characters before writing; audit metadata never fails the operation (reviewer accepted suggestion)
**Suggested answer:** bug — `user_agent` is truncated to 255 characters and `ip_address` to 45 before writing; audit metadata never fails the operation
**Resolution:** `user_agent` keeps its first 255 characters and `ip_address` its first 45; shorter values are unchanged. Over-long `entity_type`/`action_type`/`related_entity_type` are set by code, not by users, so they are still rejected at flush (intended, unchanged). Rules: `log_financial_audit` R6, R6a.

## Overview
This module is the single write path for the financial audit trail: an append-only log of changes to accounts, invoices and payments. It also provides two helpers that build the before/after `changes` JSON. It is called by `AccountManager` (create/update/delete account) and `InvoicePaymentManager` (record/delete/void payment, invoice status changes). It is meant to guarantee that every financial change leaves one row in `financial_audit_logs`, scoped to the workspace, stamped with who acted and when (UTC), in the same transaction as the change itself.

**Callables:** 3 specified · 0 not specified
**Externals to mock:** `utcnow` (imported into `app.utils.audit_logger`; patch `app.utils.audit_logger.utcnow`)
**Integration-only behavior:** none

**Notes for the test designer:**
- `create_change_dict` and `extract_relevant_fields` are pure. Test them with plain Python objects, e.g. `types.SimpleNamespace` or a small class. No DB is needed.
- `log_financial_audit` needs a real session plus an existing `workspaces` row and an existing `profiles` row. `workspace_id` and `performed_by` are foreign keys checked at flush.
- The audit model is `app.models.financial_audit_log.FinancialAuditLog` (table `financial_audit_logs`). Its `changes` column is SQLAlchemy `JSON`, not JSONB, and it is serialised with the default `json.dumps`.

## Not specified
_(none)_

---

## `log_financial_audit(session, *, workspace_id, entity_type, entity_id, action_type, performed_by, changes=None, description=None, related_entity_type=None, related_entity_id=None, ip_address=None, user_agent=None)`
**Shape:** event-log
**Persistence:** writes
**Visibility:** public (used by: `AccountManager.create_account`, `update_account`, `delete_account`; `InvoicePaymentManager` record/delete/void payment)

**Purpose:** Append one financial audit row describing an action on an entity.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `session` | Session | Caller's session; the row joins the caller's transaction |
| `workspace_id` | int | Stored as-is; must reference an existing workspace (FK, checked at flush) |
| `entity_type` | str | Required; any string, no allowed-values check; DB column max 50 chars |
| `entity_id` | int | Required; coerced by Pydantic (lax mode, e.g. `"5"` → `5`; non-numeric string → `ValidationError`); no FK |
| `action_type` | str | Required; any string, no allowed-values check; DB max 50 chars |
| `performed_by` | int | Stored as-is; must reference an existing profile (FK, checked at flush) |
| `changes` | dict \| None | No key/shape check; nested `None` values kept; made JSON-safe before storing (R7a, BUG-142) |
| `description` | str \| None | Text, unlimited |
| `related_entity_type` | str \| None | No check that it is paired with `related_entity_id`; DB max 50 |
| `related_entity_id` | int \| None | No FK |
| `ip_address` | str \| None | No format check; DB max 45; truncated to 45 (R6a, BUG-144) |
| `user_agent` | str \| None | DB max 255; truncated to 255 (R6a, BUG-144) |

**Returns:** `None`. The created row is not returned. It has been added to the session and flushed, but not committed.

**Rules:**
- **R1.** Each call creates exactly one new `financial_audit_logs` row, which is visible in the same session straight after the call. Its `workspace_id`, `entity_type`, `entity_id`, `action_type` and `performed_by` hold the given values.
- **R2.** `performed_at` is the application's current UTC time (naive datetime), taken from `utcnow()` when the function is called, not the database's clock. With `utcnow` patched to a fixed value, `performed_at` equals that value exactly.
- **R3.** Every optional argument (`changes`, `description`, `related_entity_type`, `related_entity_id`, `ip_address`, `user_agent`) that is given as non-`None` is stored unchanged, except for the conversions in R6a (truncation) and R7a (JSON-safe `changes`). An argument given as `None` or left out is stored as SQL `NULL`.
- **R4.** A `changes` dict that holds only JSON-native values (str, int, finite float, bool, None, nested dicts with str keys, lists) is stored equal to what was given. This includes nested `None` values (e.g. `{'after': {'email': None}}` keeps the `email: None` key) and an empty dict `{}` (stored as `{}`, not `NULL`).
- **R5.** [BUG-140] Every financial audit row written through the API records the request's client IP address and user agent. The fix belongs in the endpoints, services and `AccountManager`/`InvoicePaymentManager`, which must pass both values into this function. At this module's level the observable part is R3: given values are stored. *(Today: no caller passes `ip_address` or `user_agent`, so rows written through the API always have both as `NULL`.)* *(requires new `ip_address`/`user_agent` parameters on the manager methods and services)*
- **R6.** An `entity_type`, `action_type` or `related_entity_type` longer than 50 characters is rejected by the database at flush with `DataError`. The error propagates to the caller and no row is written. Exactly 50 characters is accepted.
- **R6a.** [BUG-144] A `user_agent` longer than 255 characters is stored as its first 255 characters, and an `ip_address` longer than 45 characters as its first 45. The row is written and no error is raised. Values of exactly 255 / 45 characters or shorter are stored unchanged. *(Today: the database rejects the row at flush with `DataError`, the error propagates and no row is written.)*
- **R7.** [BUG-142] A `changes` dict containing values that `json.dumps` cannot serialise, at any nesting depth (e.g. `Decimal`, `datetime`, `UUID`, a custom object), is still written. The row is created, no error is raised, and each such value is stored in its converted form (R7a). *(Today: the flush fails with a SQLAlchemy `StatementError` wrapping `TypeError`, the error propagates and no row is written.)*
- **R7a.** [BUG-142] Conversion applied to `changes` before storing, recursively at every depth (the same conversion `extract_relevant_fields` applies to each kept value):
  - `Decimal` → exact fixed-point string, never exponent notation: `Decimal("2000.00")` → `"2000.00"`, `Decimal("1E+2")` → `"100"`; `Decimal("NaN")`/`Decimal("Infinity")`/`Decimal("-Infinity")` → `"NaN"`/`"Infinity"`/`"-Infinity"` (BUG-141 format).
  - `datetime` → ISO-8601 string (aware values keep their offset); `date` → `"YYYY-MM-DD"`; `time` → ISO string (`time(9,30)` → `"09:30:00"`).
  - `UUID` → its canonical string (`str(uuid)`).
  - `Enum` member (any kind) → its `.value`, which is then converted by these same rules.
  - `float` `nan` / `inf` / `-inf` → `"NaN"` / `"Infinity"` / `"-Infinity"`; finite floats unchanged.
  - `dict` → dict with every value converted; a key that is not a `str` becomes `str(key)` (`{1: "a"}` → `{"1": "a"}`).
  - `list` and `tuple` → list with every element converted; `set`/`frozenset` → list of converted elements sorted by their string form.
  - `str`, `int`, `bool`, `None` → unchanged.
  - Anything else (e.g. `timedelta`, `bytes`, a custom object) → `str(value)` (`timedelta(days=1)` → `"1 day, 0:00:00"`).
- **R7b.** [BUG-142] (best-practice default, delegated by reviewer) The caller's `changes` dict and its nested containers are never modified by the conversion. After the call they still hold the original objects (e.g. the `Decimal`).
- **R8.** A `workspace_id` or `performed_by` that does not exist makes the flush fail with `IntegrityError` (foreign key) and no row is written.
- **R9.** A value for `entity_id` or `related_entity_id` that Pydantic cannot turn into an int (e.g. `"abc"`), or a non-dict `changes`, raises `pydantic.ValidationError` before anything is written.
- **R10.** The function does not commit. Rolling back the session removes the row.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| Non-integer `entity_id`/`related_entity_id`, non-dict `changes`, non-str text field | `pydantic.ValidationError` | Pydantic default |
| Unknown `workspace_id` / `performed_by` | `sqlalchemy.exc.IntegrityError` | FK violation |
| Over-long `entity_type` / `action_type` / `related_entity_type` (> 50) | `sqlalchemy.exc.DataError` | value too long |

*(Today only, removed by BUG-144 and BUG-142: over-long `user_agent`/`ip_address` → `DataError`; non-JSON-serialisable value in `changes` → `StatementError` wrapping `TypeError`.)*

**Side effects:** Inserts one `financial_audit_logs` row and flushes. `id` is assigned. Nothing is committed and no external calls are made.

---

## `create_change_dict(before=None, after=None)`
**Shape:** helper
**Persistence:** pure
**Visibility:** public (used by: `AccountManager`, `InvoicePaymentManager`)

**Purpose:** Build a `changes` dict containing the `before` and/or `after` snapshot.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `before` | dict \| None | Not type-checked; stored by reference |
| `after` | dict \| None | Not type-checked; stored by reference |

**Returns:** A new dict.

**Rules:**
- **R1.** When `before` is not `None`, the result has key `'before'` whose value is the same object as `before`.
- **R2.** When `after` is not `None`, the result has key `'after'` whose value is the same object as `after`.
- **R3.** An empty dict `{}` counts as given: `create_change_dict(before={})` returns `{'before': {}}`.
- **R4.** With both `None` (or no arguments), the result is `{}`.
- **R5.** The result has no keys other than `'before'` and `'after'`.

**Errors:** none.

**Side effects:** none.

---

## `extract_relevant_fields(obj, fields)`
**Shape:** mapper
**Persistence:** pure
**Visibility:** public (used by: `AccountManager`, `InvoicePaymentManager`)

**Purpose:** Snapshot the named attributes of an object into a dict suitable for the audit `changes` JSON.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `obj` | any | Any object; attributes read with `getattr` |
| `fields` | list of str | Names to read, in order; duplicates allowed (later read overwrites the same key) |

**Returns:** A new dict mapping each copied field name to its converted value. Keys appear in the order of `fields`.

**Rules:**
- **R1.** A name in `fields` that `obj` does not have (attribute lookup raises `AttributeError`) is left out of the result without any error.
- **R2.** An empty `fields` list returns `{}`.
- **R3.** [BUG-141] A `Decimal` value is stored as its exact fixed-point string: `Decimal("2000.00")` → `"2000.00"`, `Decimal("1234567890123456.78")` → `"1234567890123456.78"`, `Decimal("1E+2")` → `"100"`. Non-finite decimals follow `log_financial_audit` R7a. *(Today: stored as a `float`, `Decimal("2000.00")` → `2000.0`, and precision beyond a double is lost.)*
- **R4.** A `datetime` value is stored as its ISO-8601 string (`datetime(2026,1,2,3,4,5)` → `"2026-01-02T03:04:05"`; a timezone-aware value keeps its offset, e.g. `"…+00:00"`). ✅
- **R5.** A `date` value that is not a `datetime` is stored as `"YYYY-MM-DD"`. ✅
- **R6.** A value that is not an `Enum` member, has an instance attribute dictionary, and is not a `str`/`int`/`float`/`bool` (or a subclass of one) is left out of the result without error. This covers a related ORM object, a relationship collection (e.g. SQLAlchemy's `InstrumentedList`, a `list` subclass with an instance dictionary) and any custom class instance.
- **R6a.** [BUG-143] An `Enum` member of any kind (plain `Enum`, `str` enum, `int` enum) is stored as its `.value`. The stored value is the plain value, not the enum member (`type(result[f])` is the value's type, e.g. `str`), converted further per `log_financial_audit` R7a (an enum whose value is a `Decimal` is stored as the decimal's string). *(Today: a plain `Enum` member is left out of the result; `str`/`int` enum members are kept as the enum member itself.)*
- **R7.** [BUG-142] Every other value is made JSON-safe per `log_financial_audit` R7a. `str`, `int`, finite `float`, `bool` and `None` are kept unchanged. A plain `list`/`tuple`/`set`/`dict` has its nested contents converted recursively; nested custom objects become `str(obj)` and are not omitted. `UUID` → string, `time` → ISO string, `timedelta` → `str()`. The returned dict always passes `json.dumps(result, allow_nan=False)`. *(Today: copied unchanged, with nested contents not converted, so `UUID`, `time`, `timedelta`, sets and nested `Decimal`s reach the audit row unconverted and fail the flush.)*
- **R8.** `obj` is never modified.

**Errors:** Only errors raised by the object's own attribute access other than `AttributeError` (those propagate).

**Side effects:** none (reading an attribute on an ORM object can trigger a lazy load).

---

## Branch map
> Lines refer to source commit e48a092 (current code). The bug fixes (BUG-141..144) add branches: an enum check before the `__dict__` check, a recursive JSON-safe converter, and truncation of `user_agent`/`ip_address`. Their rules are listed next to the line they replace.

| Source line | Decision | Rule |
|---|---|---|
| 92–102 | Pydantic validation of inputs (fail → ValidationError) | `log_financial_audit` R9 |
| 104 | `exclude_none=True` — each optional field present / `None` | `log_financial_audit` R3, R4 |
| 105–107 | workspace_id / performed_by / performed_at set | `log_financial_audit` R1, R2 |
| 92–102 (fix) | `user_agent`/`ip_address` longer than limit → truncate | `log_financial_audit` R6a |
| 98 (fix) | `changes` converted to JSON-safe copy | `log_financial_audit` R4, R7, R7a, R7b |
| 109 | `create` + flush: success / FK error / length error | `log_financial_audit` R1, R6, R8, R10 |
| 130 | `before is not None` true / false | `create_change_dict` R1, R3, R4 |
| 132 | `after is not None` true / false | `create_change_dict` R2, R4 |
| 155 | loop over `fields`: empty / one / many | `extract_relevant_fields` R2, R7 |
| 156 | `hasattr(obj, field)` true / false | `extract_relevant_fields` R1 |
| 161 | `isinstance(value, Decimal)` | `extract_relevant_fields` R3 |
| (fix, before 170) | `isinstance(value, Enum)` | `extract_relevant_fields` R6a |
| 164 | `isinstance(value, datetime)` | `extract_relevant_fields` R4 |
| 167 | `isinstance(value, date)` | `extract_relevant_fields` R5 |
| 170 | has `__dict__` and not primitive → `continue` | `extract_relevant_fields` R6 |
| 173 | else → keep as-is (fix: JSON-safe conversion) | `extract_relevant_fields` R7 |
