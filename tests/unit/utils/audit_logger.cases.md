# Test cases — `app/utils/audit_logger.py`

> **Spec:** `tests/unit/utils/audit_logger.spec.md` (source commit e48a092)
> **Status:** READY
> **Revision:** 4 — re-run: spec unchanged (APPROVED, source commit e48a092, file older than revision 3); verify.md verdict PASS with no case-designer findings and no surviving mutants; self-check re-done, no gaps found. No case added, changed or retired.
> **Previous revision:** 3 — verifier feedback (audit_logger.verify.md, Finding 1, case-weakness): AUD-X-05 now gives every read a distinct value and asserts the stored value equals the last read (`{"n": obj.reads}`), so a first-read-wins implementation fails (best-practice default, delegated by reviewer). Spec unchanged (same APPROVED spec, source commit e48a092, no Gap log change); all other case IDs and designs kept.
> **Counts:** 65 cases · 45 expected-to-pass · 20 expected-to-fail (bugs) · 2 deferred

## Reviewer summary
- **Per callable:** `log_financial_audit` 31 cases (10 bug) · `create_change_dict` 8 cases (0 bug) · `extract_relevant_fields` 26 cases (10 bug).
- **Notable design choices:**
  - DB errors raised at flush (`DataError`, `IntegrityError`) are provoked inside a SAVEPOINT so the test can re-query afterwards; "no row written" is then checked after the savepoint rollback (best-practice default, delegated by reviewer).
  - "Stored as SQL `NULL`" (R3) is checked with raw SQL `... IS NULL`, because SQLAlchemy `JSON` can store Python `None` as the JSON literal `null`, which a plain ORM re-read cannot tell apart (best-practice default, delegated by reviewer).
  - BUG-142 split: values the standard `json.dumps` already serialises today (tuples, non-`str` dict keys, `str`/`int` enum members) are covered by a passing case (AUD-L-20); values it cannot serialise (Decimal, datetime, UUID, plain Enum, non-finite float, set, custom object) are xfail. This relies on the spec's note that `changes` is serialised with default `json.dumps` (best-practice default, delegated by reviewer).
  - BUG-140 (R5) has no failing behavior at this module's level; the module-level half is covered by AUD-L-02 (given IP/UA are stored) and the rest is deferred to the managers/services/endpoints.
  - Two `extract_relevant_fields` bug rules keep passing regression cases: Decimal fields are kept and numerically equal (AUD-X-09); `str`/`int` enum members compare equal to their value (AUD-X-17).
- **Needs a decision:** None.

## Conventions for this module

- **IDs:** `AUD` = `app/utils/audit_logger.py`; `L` = `log_financial_audit`; `CD` = `create_change_dict`; `X` = `extract_relevant_fields`.
- **DB setup (L cases only):** W1, W2 = two workspaces; U1 = a profile in W1. Both workspaces start with zero `financial_audit_logs` rows (fresh rows per test).
- **Minimal call (MIN):** `log_financial_audit(session, workspace_id=W1.id, entity_type="account", entity_id=42, action_type="create", performed_by=U1.id)`; cases list only the arguments they add or change.
- **Clock:** `app.utils.audit_logger.utcnow` is patched in every L case to return `NOW = datetime(2001, 2, 3, 4, 5, 6, 789000)` (naive; deliberately far from the database clock).
- **Re-read:** after the call, `session.expire_all()` then select `FinancialAuditLog` (table `financial_audit_logs`) rows by `workspace_id`, ordered by `id`. JSON values are compared on the re-read row, never the in-memory object.
- **Error-at-flush pattern (FLUSH-ERR):** the call is made inside `session.begin_nested()`; the expected exception is asserted with `pytest.raises`; after the savepoint has rolled back, the row count for the scope named in the case is re-read.
- **xfail cases that fail today with a DB error at flush** (AUD-L-11 … AUD-L-19, AUD-L-21): make the call inside `session.begin_nested()` too, so today's flush error rolls back only the savepoint and the outer test transaction can still be torn down cleanly. The assertions stay as written: no error, and the row is re-read after the call (best-practice default, delegated by reviewer).
- **Unknown id:** `SELECT max(id) FROM <table>` + 1000 (or 1000 if the table is empty).
- **Test-only types** (defined in the test file):
  - `Status(Enum)`: `ACTIVE = "active"`, `SUSPENDED = "suspended"` (plain enum).
  - `Color(str, Enum)`: `RED = "red"`.
  - `Level(IntEnum)`: `HIGH = 3`.
  - `Money(Enum)`: `X = Decimal("9.90")`.
  - `Custom`: plain class with an instance attribute and `__str__` returning `"custom-obj"`.
  - `RelList(list)`: empty `list` subclass (instances have `__dict__`).
  - `MyStr(str)`, `MyInt(int)`, `MyFloat(float)`: empty subclasses.
  - `U = UUID("12345678-1234-5678-1234-567812345678")`.
- **pure callables (CD, X):** no DB, no mocks; objects are `types.SimpleNamespace` or the classes above.
- **Race simulations:** none.

## `log_financial_audit`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| AUD-L-01 | R1, R2, R3 | happy | W1, W2, U1; no audit rows | MIN | returns `None`; W1 has exactly 1 row: `id` not None, `workspace_id`=W1.id, `entity_type`="account", `entity_id`=42, `action_type`="create", `performed_by`=U1.id, `performed_at`==NOW and `performed_at.tzinfo` is None; `description`, `related_entity_type`, `related_entity_id`, `ip_address`, `user_agent` are None; raw SQL `changes IS NULL` is true; W2 still has 0 rows | pass |
| AUD-L-02 | R3, R5 | side-effect | W1, U1 | MIN + `changes={"before": {"name": "Cash"}, "after": {"name": "Petty Cash"}}`, `description="Renamed account"`, `related_entity_type="invoice"`, `related_entity_id=7`, `ip_address="203.0.113.7"`, `user_agent="Mozilla/5.0 (X11; Linux x86_64)"` | returns `None`; the one W1 row holds exactly those six values (changes equal to the given dict) | pass |
| AUD-L-03 | R3 | boundary | W1, U1 | MIN + all six optional args passed explicitly as `None` | returns `None`; 1 row; raw SQL on that row: `changes IS NULL`, `description IS NULL`, `related_entity_type IS NULL`, `related_entity_id IS NULL`, `ip_address IS NULL`, `user_agent IS NULL` all true | pass |
| AUD-L-04 | R4, R7b | happy | W1, U1; `c = {"after": {"email": None, "count": 3, "rate": 1.5, "active": True, "tags": ["a", "b"], "meta": {"k": "v"}}}`; `snapshot = copy.deepcopy(c)` | MIN + `changes=c` | returns `None`; re-read `changes == snapshot`; `"email" in changes["after"]` and its value is None; after the call `c == snapshot` | pass |
| AUD-L-05 | R4 | boundary | W1, U1 | MIN + `changes={}` | returns `None`; raw SQL `changes IS NULL` is false; re-read `changes == {}` | pass |
| AUD-L-06 | R6 | boundary | W1, U1 | MIN with `entity_type="e"*50`, `action_type="a"*50`, `related_entity_type="r"*50`, `related_entity_id=1` | returns `None`; 1 row; the three values stored in full (length 50 each) | pass |
| AUD-L-07 | R6, Err row 3 | error | W1, U1 | FLUSH-ERR: MIN with `entity_type="e"*51` | raises `sqlalchemy.exc.DataError`; W1 has 0 rows | pass |
| AUD-L-08 | R6, Err row 3 | error | W1, U1 | FLUSH-ERR: MIN with `action_type="a"*51` | raises `DataError`; W1 has 0 rows | pass |
| AUD-L-09 | R6, Err row 3 | error | W1, U1 | FLUSH-ERR: MIN + `related_entity_type="r"*51`, `related_entity_id=1` | raises `DataError`; W1 has 0 rows | pass |
| AUD-L-10 | R6a | boundary | W1, U1 | MIN + `user_agent="U"*255`, `ip_address="1"*45` | returns `None`; 1 row; `user_agent == "U"*255`, `ip_address == "1"*45` | pass |
| AUD-L-11 | R6a [BUG-144] | bug | W1, U1 | MIN + `user_agent="A"*255 + "Z"` (256 chars) | no error; returns `None`; 1 row with `user_agent == "A"*255` | xfail BUG-144 — fails today on: `DataError` raised at flush |
| AUD-L-12 | R6a [BUG-144] | bug | W1, U1 | MIN + `ip_address="1"*45 + "9"` (46 chars) | no error; returns `None`; 1 row with `ip_address == "1"*45` | xfail BUG-144 — fails today on: `DataError` raised at flush |
| AUD-L-13 | R7, R7a (Decimal) [BUG-142] | bug | W1, U1 | MIN + `changes={"invoice_amount": {"before": Decimal("1500.00"), "after": Decimal("2000.00")}}` | no error; returns `None`; 1 row; re-read `changes == {"invoice_amount": {"before": "1500.00", "after": "2000.00"}}` | xfail BUG-142 — fails today on: flush raises (`StatementError` wrapping `TypeError`) |
| AUD-L-14 | R7a (Decimal formats) [BUG-142] | bug | W1, U1 | MIN + `changes={"a": Decimal("1E+2"), "b": Decimal("1E-7"), "c": Decimal("1234567890123456.78"), "d": Decimal("-5.50"), "e": Decimal("NaN"), "f": Decimal("Infinity"), "g": Decimal("-Infinity")}` | no error; re-read `changes == {"a": "100", "b": "0.0000001", "c": "1234567890123456.78", "d": "-5.50", "e": "NaN", "f": "Infinity", "g": "-Infinity"}` | xfail BUG-142 — fails today on: flush raises |
| AUD-L-15 | R7a (datetime/date/time) [BUG-142] | bug | W1, U1 | MIN + `changes={"dt": datetime(2026,1,2,3,4,5), "dta": datetime(2026,1,2,3,4,5,tzinfo=timezone.utc), "d": date(2026,1,2), "t": time(9,30)}` | no error; re-read `changes == {"dt": "2026-01-02T03:04:05", "dta": "2026-01-02T03:04:05+00:00", "d": "2026-01-02", "t": "09:30:00"}` | xfail BUG-142 — fails today on: flush raises |
| AUD-L-16 | R7a (UUID, Enum) [BUG-142] | bug | W1, U1 | MIN + `changes={"u": U, "status": Status.ACTIVE, "m": Money.X}` | no error; re-read `changes == {"u": "12345678-1234-5678-1234-567812345678", "status": "active", "m": "9.90"}` | xfail BUG-142 — fails today on: flush raises |
| AUD-L-17 | R7a (non-finite float) [BUG-142] | bug | W1, U1 | MIN + `changes={"a": float("nan"), "b": float("inf"), "c": float("-inf"), "d": 1.25}` | no error; re-read `changes == {"a": "NaN", "b": "Infinity", "c": "-Infinity", "d": 1.25}` | xfail BUG-142 — fails today on: flush raises (Postgres rejects the `NaN` token) |
| AUD-L-18 | R7, R7a (containers) [BUG-142] | bug | W1, U1 | MIN + `changes={"s": {10, 9}, "fs": frozenset({"b", "a"}), "nested": [{"x": Decimal("1.10")}, (Decimal("2"), "y")], "deep": {"lvl": {"when": date(2026,1,2)}}}` | no error; re-read `changes == {"s": [10, 9], "fs": ["a", "b"], "nested": [{"x": "1.10"}, ["2", "y"]], "deep": {"lvl": {"when": "2026-01-02"}}}` (set sorted by string form: "10" < "9") | xfail BUG-142 — fails today on: flush raises |
| AUD-L-19 | R7a (fallback) [BUG-142] | bug | W1, U1 | MIN + `changes={"td": timedelta(days=1), "b": b"ab", "obj": Custom()}` | no error; re-read `changes == {"td": "1 day, 0:00:00", "b": "b'ab'", "obj": "custom-obj"}` | xfail BUG-142 — fails today on: flush raises |
| AUD-L-20 | R7a (tuple, non-str key, str/int enum) | side-effect | W1, U1 | MIN + `changes={"t": (1, "a"), 5: "five", "nested": {2: [True, None]}, "se": Color.RED, "ie": Level.HIGH}` | returns `None`; 1 row; re-read `changes == {"t": [1, "a"], "5": "five", "nested": {"2": [True, None]}, "se": "red", "ie": 3}` | pass |
| AUD-L-21 | R7b [BUG-142] | bug | W1, U1; `amt = Decimal("2000.00")`; `tags = {"x"}`; `c = {"after": {"amount": amt, "tags": tags}}` | MIN + `changes=c` | no error; re-read `changes == {"after": {"amount": "2000.00", "tags": ["x"]}}`; after the call `c["after"]["amount"] is amt`, `c["after"]["tags"] is tags` (still a `set`), `c == {"after": {"amount": Decimal("2000.00"), "tags": {"x"}}}` | xfail BUG-142 — fails today on: flush raises |
| AUD-L-22 | R8, Err row 2 | error | U1; `bad_ws` = unknown workspace id | FLUSH-ERR: MIN with `workspace_id=bad_ws` | raises `sqlalchemy.exc.IntegrityError`; 0 rows with `performed_by == U1.id` | pass |
| AUD-L-23 | R8, Err row 2 | error | W1; `bad_p` = unknown profile id | FLUSH-ERR: MIN with `performed_by=bad_p` | raises `IntegrityError`; W1 has 0 rows | pass |
| AUD-L-24 | R9, Err row 1 | error | W1, U1 | MIN with `entity_id="abc"` | raises `pydantic.ValidationError`; `session.new` is empty; W1 has 0 rows | pass |
| AUD-L-25 | R9, Err row 1 | error | W1, U1 | MIN + `related_entity_id="abc"` | raises `pydantic.ValidationError`; `session.new` empty; W1 has 0 rows | pass |
| AUD-L-26 | R9, Err row 1 | error | W1, U1 | MIN + `changes=["not", "a", "dict"]` | raises `pydantic.ValidationError`; `session.new` empty; W1 has 0 rows | pass |
| AUD-L-27 | R9 (other side) | boundary | W1, U1 | MIN with `entity_id="5"`, + `related_entity_id="8"` | returns `None`; 1 row with `entity_id == 5` and `related_entity_id == 8` (ints) | pass |
| AUD-L-28 | Err row 1 (non-str text) | error | W1, U1 | MIN with `entity_type=123` | raises `pydantic.ValidationError`; `session.new` empty; W1 has 0 rows | pass |
| AUD-L-29 | R10 | side-effect | W1, U1 | open `sp = session.begin_nested()`; MIN; record the W1 row id; `sp.rollback()` | before rollback: W1 has 1 row; after rollback: no row with that id exists and W1 has 0 rows | pass |
| AUD-L-30 | R1 | happy | W1, U1 | MIN twice with identical arguments | both return `None`; W1 has exactly 2 rows with different ids, identical `entity_type`/`entity_id`/`action_type`/`performed_by`, both `performed_at == NOW` | pass |
| AUD-L-31 | R3 (no pairing / no format check) | boundary | W1, U1 | MIN + `related_entity_type="invoice"` (no `related_entity_id`), `ip_address="not-an-ip"`, `description="D"*10000` | returns `None`; 1 row: `related_entity_type == "invoice"`, `related_entity_id` is None, `ip_address == "not-an-ip"`, `description == "D"*10000` | pass |

## `create_change_dict`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| AUD-CD-01 | R1, R2, R5 | happy | `b = {"name": "A"}`, `a = {"name": "B"}` | `create_change_dict(before=b, after=a)` | result `== {"before": {"name": "A"}, "after": {"name": "B"}}`; `result["before"] is b`; `result["after"] is a`; `set(result) == {"before", "after"}` | pass |
| AUD-CD-02 | R1, R5 | happy | `b = {"name": "A"}` | `create_change_dict(before=b)` | result `== {"before": {"name": "A"}}`; `"after" not in result`; `result["before"] is b` | pass |
| AUD-CD-03 | R2, R5 | happy | `a = {"name": "B"}` | `create_change_dict(after=a)` | result `== {"after": {"name": "B"}}`; `"before" not in result`; `result["after"] is a` | pass |
| AUD-CD-04 | R3 | boundary | `b = {}` | `create_change_dict(before=b)` | result `== {"before": {}}`; `result["before"] is b` | pass |
| AUD-CD-05 | R3 | boundary | `a = {}` | `create_change_dict(after=a)` | result `== {"after": {}}`; `result["after"] is a` | pass |
| AUD-CD-06 | R4 | boundary | — | `r1 = create_change_dict()`; `r2 = create_change_dict()` | `r1 == {}`; `r2 == {}`; `r1 is not r2`; after `r1["x"] = 1`, `r2 == {}` | pass |
| AUD-CD-07 | R4 | boundary | — | `create_change_dict(before=None, after=None)` | result `== {}` | pass |
| AUD-CD-08 | R1 (no type check) | boundary | `b = [1, 2]` | `create_change_dict(before=b)` | result `== {"before": [1, 2]}`; `result["before"] is b` | pass |

## `extract_relevant_fields`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| AUD-X-01 | R7 (natives), Returns | happy | `o = SimpleNamespace(name="Cash", code=101, rate=1.5, active=True, note=None)` | `extract_relevant_fields(o, ["name", "code", "rate", "active", "note"])` | result `== {"name": "Cash", "code": 101, "rate": 1.5, "active": True, "note": None}`; `list(result) == ["name", "code", "rate", "active", "note"]`; `result is not o.__dict__` | pass |
| AUD-X-02 | Returns (order) | happy | same `o` | `extract_relevant_fields(o, ["note", "active", "name"])` | `list(result) == ["note", "active", "name"]`; values None, True, "Cash" | pass |
| AUD-X-03 | R1 | boundary | same `o` | `extract_relevant_fields(o, ["name", "missing", "code"])` | no error; result `== {"name": "Cash", "code": 101}`; `"missing" not in result` | pass |
| AUD-X-04 | R2 | boundary | same `o` | `extract_relevant_fields(o, [])` | result `== {}` (a dict) | pass |
| AUD-X-05 | Inputs (duplicates) | boundary | class `Counter` whose instance keeps `reads = 0`; property `n` increments `reads` and returns the new `reads` value, so every read returns a distinct value (1, 2, 3, …) whatever the number of reads per field (best-practice default, delegated by reviewer) | `obj = Counter()`; `result = extract_relevant_fields(obj, ["n", "n"])` | `obj.reads >= 2` (the field was read for both list entries); result `== {"n": obj.reads}` (the stored value is the one returned by the LAST read, so first-read-wins fails); `len(result) == 1` | pass |
| AUD-X-06 | R3 [BUG-141] | bug | `o = SimpleNamespace(amount=Decimal("2000.00"))` | `extract_relevant_fields(o, ["amount"])` | `result["amount"] == "2000.00"`; `type(result["amount"]) is str` | xfail BUG-141 — fails today on: value is float `2000.0` |
| AUD-X-07 | R3 [BUG-141] | bug | `o = SimpleNamespace(big=Decimal("1234567890123456.78"), e=Decimal("1E+2"), tiny=Decimal("1E-7"), neg=Decimal("-5.50"))` | `extract_relevant_fields(o, ["big", "e", "tiny", "neg"])` | result `== {"big": "1234567890123456.78", "e": "100", "tiny": "0.0000001", "neg": "-5.50"}` | xfail BUG-141 — fails today on: values are floats (`1234567890123456.8`, …) |
| AUD-X-08 | R3 (non-finite) [BUG-141] | bug | `o = SimpleNamespace(a=Decimal("NaN"), b=Decimal("Infinity"), c=Decimal("-Infinity"))` | `extract_relevant_fields(o, ["a", "b", "c"])` | result `== {"a": "NaN", "b": "Infinity", "c": "-Infinity"}`; `json.dumps(result, allow_nan=False)` succeeds | xfail BUG-141 — fails today on: values are float `nan`/`inf` |
| AUD-X-09 | R3 (regression) | happy | `o = SimpleNamespace(amount=Decimal("2000.00"))` | `extract_relevant_fields(o, ["amount"])` | `"amount" in result`; `Decimal(str(result["amount"])) == Decimal("2000")` | pass |
| AUD-X-10 | R4 | happy | `o = SimpleNamespace(at=datetime(2026,1,2,3,4,5))` | `extract_relevant_fields(o, ["at"])` | result `== {"at": "2026-01-02T03:04:05"}` | pass |
| AUD-X-11 | R4 (aware) | boundary | `o = SimpleNamespace(u=datetime(2026,1,2,3,4,5,tzinfo=timezone.utc), d6=datetime(2026,1,2,3,4,5,tzinfo=timezone(timedelta(hours=6))))` | `extract_relevant_fields(o, ["u", "d6"])` | result `== {"u": "2026-01-02T03:04:05+00:00", "d6": "2026-01-02T03:04:05+06:00"}` | pass |
| AUD-X-12 | R5 | happy | `o = SimpleNamespace(due=date(2026,1,2))` | `extract_relevant_fields(o, ["due"])` | result `== {"due": "2026-01-02"}` | pass |
| AUD-X-13 | R6 | boundary | `o = SimpleNamespace(name="Cash", related=Custom(), items=sqlalchemy.orm.collections.InstrumentedList([1, 2]), rel=RelList([1]))` | `extract_relevant_fields(o, ["name", "related", "items", "rel"])` | no error; result `== {"name": "Cash"}` | pass |
| AUD-X-14 | R6 (primitive subclasses kept) | boundary | `o = SimpleNamespace(s=MyStr("abc"), i=MyInt(7), f=MyFloat(2.5))` (each instance has `__dict__`) | `extract_relevant_fields(o, ["s", "i", "f"])` | result `== {"s": "abc", "i": 7, "f": 2.5}` (all three keys present) | pass |
| AUD-X-15 | R6a [BUG-143] | bug | `o = SimpleNamespace(name="Cash", status=Status.ACTIVE)` | `extract_relevant_fields(o, ["name", "status"])` | result `== {"name": "Cash", "status": "active"}`; `type(result["status"]) is str` | xfail BUG-143 — fails today on: `"status"` missing from result |
| AUD-X-16 | R6a [BUG-143] | bug | `o = SimpleNamespace(c=Color.RED, lvl=Level.HIGH)` | `extract_relevant_fields(o, ["c", "lvl"])` | `type(result["c"]) is str`; `type(result["lvl"]) is int`; `result == {"c": "red", "lvl": 3}` | xfail BUG-143 — fails today on: `type(result["c"])` is `Color` |
| AUD-X-17 | R6a (regression) | happy | same as AUD-X-16 | `extract_relevant_fields(o, ["c", "lvl"])` | `result["c"] == "red"`; `result["lvl"] == 3` | pass |
| AUD-X-18 | R6a, R7a [BUG-143] | bug | `o = SimpleNamespace(m=Money.X)` | `extract_relevant_fields(o, ["m"])` | result `== {"m": "9.90"}` | xfail BUG-143 — fails today on: `"m"` missing from result |
| AUD-X-19 | R7 (UUID/time/timedelta) [BUG-142] | bug | `o = SimpleNamespace(u=U, t=time(9,30), td=timedelta(days=1))` | `extract_relevant_fields(o, ["u", "t", "td"])` | result `== {"u": "12345678-1234-5678-1234-567812345678", "t": "09:30:00", "td": "1 day, 0:00:00"}`; `json.dumps(result, allow_nan=False)` succeeds | xfail BUG-142 — fails today on: `result["u"]` is a `UUID` |
| AUD-X-20 | R7 (containers) [BUG-142] | bug | `o = SimpleNamespace(l=[Decimal("1.10"), date(2026,1,2)], tp=(1, Decimal("2")), st={10, 9}, d={"k": Decimal("3.30"), 4: "four"})` | `extract_relevant_fields(o, ["l", "tp", "st", "d"])` | result `== {"l": ["1.10", "2026-01-02"], "tp": [1, "2"], "st": [10, 9], "d": {"k": "3.30", "4": "four"}}`; `json.dumps(result, allow_nan=False)` succeeds | xfail BUG-142 — fails today on: nested `Decimal` unconverted |
| AUD-X-21 | R7 (nested custom object) [BUG-142] | bug | `o = SimpleNamespace(items=[Custom()])` (plain `list`) | `extract_relevant_fields(o, ["items"])` | result `== {"items": ["custom-obj"]}`; `json.dumps(result, allow_nan=False)` succeeds | xfail BUG-142 — fails today on: list holds the `Custom` object |
| AUD-X-22 | R7 (JSON-native containers) | happy | `o = SimpleNamespace(l=["a", 1, None], d={"k": "v", "n": [True]})` | `extract_relevant_fields(o, ["l", "d"])` | result `== {"l": ["a", 1, None], "d": {"k": "v", "n": [True]}}`; `json.dumps(result, allow_nan=False)` succeeds | pass |
| AUD-X-23 | R7a (non-finite float) [BUG-142] | bug | `o = SimpleNamespace(a=float("nan"), b=float("inf"), c=float("-inf"), d=1.25)` | `extract_relevant_fields(o, ["a", "b", "c", "d"])` | result `== {"a": "NaN", "b": "Infinity", "c": "-Infinity", "d": 1.25}`; `json.dumps(result, allow_nan=False)` succeeds | xfail BUG-142 — fails today on: `result["a"]` is float `nan` |
| AUD-X-24 | R8 | side-effect | `amt = Decimal("2000.00")`; `when = datetime(2026,1,2)`; `tags = [Decimal("1.1")]`; `o = SimpleNamespace(amount=amt, when=when, tags=tags)`; `before = dict(vars(o))` | `extract_relevant_fields(o, ["amount", "when", "tags"])` | `o.amount is amt`; `o.when is when`; `o.tags is tags`; `tags == [Decimal("1.1")]` and `type(tags[0]) is Decimal`; `vars(o) == before` | pass |
| AUD-X-25 | Errors (non-AttributeError) | error | class `Boom` with property `x` raising `ValueError("boom")` | `extract_relevant_fields(Boom(), ["x"])` | raises `ValueError` with message "boom" | pass |
| AUD-X-26 | R1 (AttributeError from property) | boundary | class `Half` with attribute `name="Cash"` and property `y` raising `AttributeError` | `extract_relevant_fields(Half(), ["name", "y"])` | no error; result `== {"name": "Cash"}` | pass |

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| `log_financial_audit` R5 [BUG-140] | `AccountManager.create_account` / `update_account` / `delete_account`; `InvoicePaymentManager` record / delete / void payment | the manager method accepts `ip_address` and `user_agent` and the audit row it writes has both values (today NULL) — xfail BUG-140 |
| `log_financial_audit` R5 [BUG-140] | account and invoice-payment services + endpoints | the request's client IP (as resolved by trusted-proxy handling, never a raw client-supplied `X-Forwarded-For`) and `User-Agent` header are passed down to the manager |

## Spec gaps
None.

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `log_financial_audit` | R1 | AUD-L-01, AUD-L-30 |
| `log_financial_audit` | R2 | AUD-L-01, AUD-L-30 |
| `log_financial_audit` | R3 | AUD-L-01, AUD-L-02, AUD-L-03, AUD-L-31 |
| `log_financial_audit` | R4 | AUD-L-04, AUD-L-05 |
| `log_financial_audit` | R5 [BUG-140] | AUD-L-02 (module-level part); Deferred ×2 |
| `log_financial_audit` | R6 | AUD-L-06, AUD-L-07, AUD-L-08, AUD-L-09 |
| `log_financial_audit` | R6a [BUG-144] | AUD-L-10, AUD-L-11, AUD-L-12 |
| `log_financial_audit` | R7 [BUG-142] | AUD-L-13, AUD-L-18 |
| `log_financial_audit` | R7a [BUG-142] | AUD-L-13 … AUD-L-19, AUD-L-20 |
| `log_financial_audit` | R7b [BUG-142] | AUD-L-04 (JSON-native, pass), AUD-L-21 |
| `log_financial_audit` | R8 | AUD-L-22, AUD-L-23 |
| `log_financial_audit` | R9 | AUD-L-24, AUD-L-25, AUD-L-26, AUD-L-27 |
| `log_financial_audit` | R10 | AUD-L-29 |
| `log_financial_audit` | Err: ValidationError | AUD-L-24, AUD-L-25, AUD-L-26, AUD-L-28 |
| `log_financial_audit` | Err: IntegrityError | AUD-L-22, AUD-L-23 |
| `log_financial_audit` | Err: DataError | AUD-L-07, AUD-L-08, AUD-L-09 |
| `create_change_dict` | R1 | AUD-CD-01, AUD-CD-02, AUD-CD-08 |
| `create_change_dict` | R2 | AUD-CD-01, AUD-CD-03 |
| `create_change_dict` | R3 | AUD-CD-04, AUD-CD-05 |
| `create_change_dict` | R4 | AUD-CD-06, AUD-CD-07 |
| `create_change_dict` | R5 | AUD-CD-01, AUD-CD-02, AUD-CD-03 |
| `extract_relevant_fields` | Returns (order, duplicates) | AUD-X-01, AUD-X-02, AUD-X-05 |
| `extract_relevant_fields` | R1 | AUD-X-03, AUD-X-26 |
| `extract_relevant_fields` | R2 | AUD-X-04 |
| `extract_relevant_fields` | R3 [BUG-141] | AUD-X-06, AUD-X-07, AUD-X-08, AUD-X-09 |
| `extract_relevant_fields` | R4 | AUD-X-10, AUD-X-11 |
| `extract_relevant_fields` | R5 | AUD-X-12 |
| `extract_relevant_fields` | R6 | AUD-X-13, AUD-X-14 |
| `extract_relevant_fields` | R6a [BUG-143] | AUD-X-15, AUD-X-16, AUD-X-17, AUD-X-18 |
| `extract_relevant_fields` | R7 [BUG-142] | AUD-X-01, AUD-X-19, AUD-X-20, AUD-X-21, AUD-X-22, AUD-X-23 |
| `extract_relevant_fields` | R8 | AUD-X-24 |
| `extract_relevant_fields` | Errors | AUD-X-25 |
