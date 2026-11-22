# Test cases — `app/managers/base_manager.py`

> **Spec:** `tests/unit/managers/base_manager.spec.md` (source commit e48a092)
> **Status:** READY
> **Revision:** 3 (2026-11-10) — executor note (`base_manager.notes.md`): an instance built through a subscripted class also holds `__orig_class__` (set by `typing`), so BMG-I-05 Then 2 now checks `vars(result)["model"] is Department` and that `__orig_class__` is the only other key. No card added or retired. Parallel runs: this module builds no rows (Conventions).
> **Revision:** 2 (2026-11-10) — batch round 2 (owner answers OQ-29 … OQ-33): the spec is unchanged (no question, no gap); no card changed, added or retired.
> **Counts:** 6 cases · 6 expected-to-pass · 0 expected-to-fail (bugs) · 0 deferred

## Reviewer summary
- **Per callable:** `BaseManager.__init__` 6 (R1 1, R2 2, R3 1, R4 1, R5 1).
- **Depth:** lighter target (skill step 1a): a constructor that stores one value; no row, session, money or stock. One card per rule; R2 has two (`None` and a string), so neither a `None` check nor a type check can slip in unseen.
- **Expected-to-fail:** none; the spec has no bug.
- **Notable design choices:**
  - No database is used: the constructor takes no session (spec Facts). No commit spy (nothing writes).
  - "The very object" is checked with `is`; "only attribute" with exact equality on `vars(...)`, except on the subscripted class (I-05), whose instances also carry `typing`'s `__orig_class__`.
  - The "managers do not commit" convention is not tested here (spec Review: it stays a per-manager rule).
- **Needs a decision:** None.

## Conventions for this module

**IDs.** `BMG` = `app/managers/base_manager.py`. `I` = `__init__`.

**Imports.** `from app.managers.base_manager import BaseManager`; `from app.models.department import Department`; `from app.managers.department_manager import DepartmentManager`; `pytest`.

**Fixed values.** `result` = the object the When builds. `S = object()` — a plain sentinel built in the Given.

**Externals.** None is mocked. No database row is built; the `db` fixture is not needed.

**Parallel runs.** No order, transfer or return number is built, so no per-process suffix is needed.

**xfail cards.** None in this module.

**Race simulations.** None.

## `BaseManager.__init__`

### BMG-I-01 — the model passed is stored as the only attribute
- **Rules:** `__init__` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. Nothing.

**When**
- `result = BaseManager(Department)`.

**Then**
1. returns: `result.model is Department`.
2. returns: `vars(result) == {"model": Department}`.

### BMG-I-02 — None is stored without an error
- **Rules:** `__init__` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Nothing.

**When**
- `result = BaseManager(None)`.

**Then**
1. returns: `result.model is None`.
2. returns: `vars(result) == {"model": None}`.

### BMG-I-03 — a string or any object is stored as given
- **Rules:** `__init__` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `S = object()`.

**When**
- `result = BaseManager("x")`.

**Then**
1. returns: `result.model == "x"`.
2. returns: `vars(result) == {"model": "x"}`.
3. returns: `BaseManager(S).model is S`.

### BMG-I-04 — no model raises TypeError
- **Rules:** `__init__` R3; Errors row "no `model` given"
- **Kind:** error
- **Expect:** pass

**Given**
1. Nothing.

**When**
- `BaseManager()` inside `with pytest.raises(TypeError) as exc:`.

**Then**
1. raises: `TypeError`; `"missing 1 required positional argument: 'model'" in str(exc.value)`.

### BMG-I-05 — the subscripted class stores the model the same way
- **Rules:** `__init__` R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. Nothing.

**When**
- `result = BaseManager[Department](Department)`.

**Then**
1. returns: `result.model is Department`.
2. returns: `vars(result)["model"] is Department`.
3. returns: `set(vars(result)) - {"__orig_class__"} == {"model"}`.

### BMG-I-06 — a subclass gets model next to its own attributes
- **Rules:** `__init__` R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. Nothing.

**When**
- `result = DepartmentManager()`.

**Then**
1. returns: `result.model is Department`.
2. returns: `set(vars(result)) == {"department_dao", "model"}`.
3. returns: `isinstance(result, BaseManager) is True`.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| (none) | | |

## Spec gaps
None.

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `__init__` | R1 | BMG-I-01 |
| `__init__` | R2 | BMG-I-02, BMG-I-03 |
| `__init__` | R3 | BMG-I-04 |
| `__init__` | R4 | BMG-I-05 |
| `__init__` | R5 | BMG-I-06 |
| `__init__` | Errors: no `model` given | BMG-I-04 |
