# Test cases — `app/utils/profile_auth.py`

> **Spec:** `tests/unit/utils/profile_auth.spec.md` (source commit `e48a092`)
> **Status:** READY
> **Revision:** 2 — re-run; spec unchanged (still APPROVED at `e48a092`, no questions, no BUG tags). `profile_auth.verify.md` verdict PASS with no Findings and no surviving mutants (8/8 killed), so there are no case-designer items to address; all IDs and cases are kept as they were.
> **Counts:** 13 cases · 13 expected-to-pass · 0 expected-to-fail (bugs) · 0 deferred

## Reviewer summary
- **Per callable:** `profile_to_auth_dict` 13 cases (0 bug).
- **Notable design choices:**
  - Mixed inputs, as the spec's notes allow: a persisted `Profile` (real id, flush defaults applied) for the happy path and R4; a transient `Profile` for R2 verbatim copying and the `None` flag; a plain `types.SimpleNamespace` for the "attribute absent" branch, non-bool truthy/falsy flags, and the `AttributeError` rows.
  - PAUTH-D-08 checks a falsy non-bool flag (`0`) maps to `False`. The spec says "truthy → True" and "always a real boolean", so falsy → `False` follows; `0` is not named explicitly (best-practice default, delegated by reviewer).
  - The function has no database access, so error cases check "nothing changed" on the input object rather than on the database; R4 still re-reads the persisted row.
- **Needs a decision:** None.

## Conventions for this module
- **Abbreviations:** `PAUTH` = `profile_auth`; `D` = `profile_to_auth_dict`.
- **P1** = a `Profile` persisted in the test DB (flushed, id assigned) with name `"Rahim Uddin"`, email `"rahim@example.com"`, timezone `"Asia/Dhaka"`, `is_platform_admin=False`, a non-empty password hash `"hash-secret-xyz"`, plus whatever other required columns the model needs (set by the executor; any values).
- **Transient Profile** = `Profile(...)` constructed but never added to a session.
- **NS(...)** = `types.SimpleNamespace` with exactly the attributes listed.
- **EXPECTED_KEYS** = `{"id", "name", "email", "timezone", "is_platform_admin"}`.
- Externals mocked: none. Race simulations: none. Time: not mocked.
- "`X is True` / `is False`" means an identity check against the bool singleton (so `1`/`0` would fail it).

## `profile_to_auth_dict`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| PAUTH-D-01 | R1, R2, R3 | happy | P1 persisted | `profile_to_auth_dict(P1)` | result is a `dict`; `set(result.keys()) == EXPECTED_KEYS` (exactly 5 keys); `result == {"id": P1.id, "name": "Rahim Uddin", "email": "rahim@example.com", "timezone": "Asia/Dhaka", "is_platform_admin": False}`; `result["is_platform_admin"] is False`; `"hashed_password"`, `"user_id"`, `"saved_stamp"` are not keys; `"hash-secret-xyz"` is not among `result.values()` | pass |
| PAUTH-D-02 | R2 | boundary | transient Profile with name `"  rahim UDDIN  "`, email `" Rahim@Example.COM "`, timezone `"America/New_York"`, `is_platform_admin=False` | `profile_to_auth_dict(profile)` | `result["name"] == "  rahim UDDIN  "`, `result["email"] == " Rahim@Example.COM "`, `result["timezone"] == "America/New_York"` (exact, no trim / case change); `set(result.keys()) == EXPECTED_KEYS` | pass |
| PAUTH-D-03 | R2 | boundary | transient Profile with name `"Karim"`, email `"karim@example.com"`, `timezone=None`, `is_platform_admin=False` | `profile_to_auth_dict(profile)` | `result["timezone"] is None` (not defaulted, not `""`); `"timezone"` is still a key; `result["name"] == "Karim"`, `result["email"] == "karim@example.com"` | pass |
| PAUTH-D-04 | R3 | happy | P1 but with `is_platform_admin=True` (persisted, flushed) | `profile_to_auth_dict(P1)` | `result["is_platform_admin"] is True`; `set(result.keys()) == EXPECTED_KEYS` | pass |
| PAUTH-D-05 | R3 | boundary | transient Profile built with name `"Nadia"`, email `"nadia@example.com"`, timezone `"Asia/Dhaka"` and NO `is_platform_admin` argument (so the attribute is `None`); precondition assert `profile.is_platform_admin is None` | `profile_to_auth_dict(profile)` | `result["is_platform_admin"] is False` (not `None`) | pass |
| PAUTH-D-06 | R3 | boundary | `NS(id=7, name="Ghost", email="ghost@example.com", timezone="UTC")` — no `is_platform_admin` attribute | `profile_to_auth_dict(obj)` | no error; `result["is_platform_admin"] is False`; `result == {"id": 7, "name": "Ghost", "email": "ghost@example.com", "timezone": "UTC", "is_platform_admin": False}` | pass |
| PAUTH-D-07 | R3 | boundary | `NS(id=8, name="One", email="one@example.com", timezone="UTC", is_platform_admin=1)` | `profile_to_auth_dict(obj)` | `result["is_platform_admin"] is True` (converted to real bool, not `1`) | pass |
| PAUTH-D-08 | R3 | boundary | `NS(id=9, name="Zero", email="zero@example.com", timezone="UTC", is_platform_admin=0)` | `profile_to_auth_dict(obj)` | `result["is_platform_admin"] is False` (not `0`) — falsy non-bool (best-practice default, delegated by reviewer) | pass |
| PAUTH-D-09 | R4 | side-effect | P1 persisted and flushed; record `P1.name`, `P1.email`, `P1.timezone`, `P1.is_platform_admin`, password hash before the call | `profile_to_auth_dict(P1)` | P1 not in `session.dirty`; all recorded attributes unchanged on P1; after `session.expire(P1)` / re-select of the row by id: name `"Rahim Uddin"`, email `"rahim@example.com"`, timezone `"Asia/Dhaka"`, `is_platform_admin` False, password hash `"hash-secret-xyz"`; return value equals the dict in PAUTH-D-01 | pass |
| PAUTH-D-10 | R4 | side-effect | transient Profile as in PAUTH-D-05 (`is_platform_admin` is `None`) | `result = profile_to_auth_dict(profile)`; then set `result["name"] = "Changed"` | `profile.is_platform_admin is None` (flag NOT written back as `False`); `profile.name == "Nadia"` (result is a new dict, not a view of the profile); `result["is_platform_admin"] is False`; a second call `profile_to_auth_dict(profile)` returns a dict that is not the same object as `result` and has `name == "Nadia"` | pass |
| PAUTH-D-11 | Errors row (missing `id`) | error | `NS(name="A", email="a@example.com", timezone="UTC", is_platform_admin=False)` | `profile_to_auth_dict(obj)` | raises `AttributeError`; `obj` still has exactly its 4 attributes with unchanged values | pass |
| PAUTH-D-12 | Errors row (missing `name`) | error | `NS(id=1, email="a@example.com", timezone="UTC", is_platform_admin=False)` | `profile_to_auth_dict(obj)` | raises `AttributeError`; `obj` attributes unchanged | pass |
| PAUTH-D-13 | Errors row (missing `email`, `timezone`) | error | two sub-inputs (parametrize): (a) `NS(id=1, name="A", timezone="UTC", is_platform_admin=False)`; (b) `NS(id=1, name="A", email="a@example.com", is_platform_admin=False)` | `profile_to_auth_dict(obj)` for each | each raises `AttributeError`; `obj` attributes unchanged | pass |

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| _(none — the register/login endpoints consume this dict, but the spec states no endpoint rule)_ | | |

## Spec gaps
None.

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `profile_to_auth_dict` | R1 | PAUTH-D-01, PAUTH-D-02, PAUTH-D-04 |
| `profile_to_auth_dict` | R2 | PAUTH-D-01, PAUTH-D-02, PAUTH-D-03 |
| `profile_to_auth_dict` | R3 (True) | PAUTH-D-04, PAUTH-D-07 |
| `profile_to_auth_dict` | R3 (False / None / absent) | PAUTH-D-01, PAUTH-D-05, PAUTH-D-06, PAUTH-D-08 |
| `profile_to_auth_dict` | R4 | PAUTH-D-09, PAUTH-D-10 |
| `profile_to_auth_dict` | Errors: missing `id` | PAUTH-D-11 |
| `profile_to_auth_dict` | Errors: missing `name` | PAUTH-D-12 |
| `profile_to_auth_dict` | Errors: missing `email` / `timezone` | PAUTH-D-13 |
| `profile_to_auth_dict` | BUG tags | none in spec |
