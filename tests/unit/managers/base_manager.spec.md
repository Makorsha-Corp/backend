# Spec — `app/managers/base_manager.py`

> **Status:** APPROVED (2026-11-10; no questions)
> **Source commit:** e48a092

> **Verified by running** (my own script `v1.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\lowsup\bm\`, no database touched): `BaseManager(Department)` has exactly one instance attribute, `model`, which is the class passed (`is`); `BaseManager(None).model is None` and `BaseManager("x").model == "x"` (nothing is checked); `BaseManager()` raises `TypeError` (missing `model`); `BaseManager[Department](Department)` works; `DepartmentManager().model is Department` with attributes `department_dao`, `model`; `app.managers.BaseManager` is the same class. **Read, not run:** every subclass's `__init__` (29 classes in `app/managers/`), and a search of `app/` for any reader of `.model` on a manager (none) and for `commit()` in `app/managers/` (none).

## Review
> No questions.

Checked and **not** violated: **HR-1 … HR-16** — the class stores one value and touches no row, session, name, list, money, external system or workspace.

**Consistency with the verified managers.** The 35 manager specs in `tests/unit/managers/` (all PASS or in the pipeline) treat `BaseManager` as adding only `self.model` (stated outright in `machine_maintenance_log_manager.spec.md`), list each subclass's `__init__` under **Not specified** as wiring, and state "the manager never commits" as **each manager's own** rule (e.g. `department_manager.spec.md` Overview). This spec keeps that split: the docstring's "managers … do NOT commit" is a convention the base class cannot enforce, so it is **not** a rule here; it stays tested per manager. (Fact for reviewers, 2026-11-10: no file in `app/managers/` calls `commit()`.)

## Overview
`BaseManager` is the generic parent of the 29 manager classes in `app/managers/` that call `super().__init__(<Model>)` (account, account invoice, delivery method, department, expense order, factory, factory section, inventory, invoice payment, item, ledger (`MachineItemLedger`), machine maintenance log, machine, order template, payment transaction, production batch, production formula, production line, product, project, purchase order, purchase order return, sales (`SalesOrder`), sales order return, transfer order, workspace, work order, work order template, work order type). It holds no logic: its constructor stores the model class on `self.model`. No first-party code reads `manager.model` today; the DAOs keep their own `self.model`.

**Callables:** 1 specified · 1 not specified
**Externals to mock:** none.
**Integration-only behavior:** none.

**Facts for the test designer**
- Imports: `from app.managers.base_manager import BaseManager` (also re-exported as `app.managers.BaseManager`, the same object). Any model works, e.g. `from app.models.department import Department`.
- No database session is needed; the constructor takes none.

## Not specified
- Module-level `ModelType = TypeVar("ModelType", bound=Base)` — typing only; the bound is not checked at run time (see R2).
- The class docstring's "do NOT commit" — a convention, tested per manager (see Review).

---

## `BaseManager.__init__(model)`
**Shape:** helper
**Persistence:** pure
**Visibility:** internal (used by: every manager subclass's `__init__` via `super().__init__(<Model>)`)

**Purpose:** Remember which SQLAlchemy model the manager is for.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `model` | `type[ModelType]` (annotation only) | required positional/keyword argument; not checked in any way |

**Returns:** a `BaseManager` instance.

**Rules:**
- **R1.** After `BaseManager(M)`, `instance.model` is the very object passed (`instance.model is M`), and `model` is the instance's only attribute (`vars(instance) == {"model": M}`).
- **R2.** The argument is not validated: `None`, a string or any other object is stored as given, with no error.
- **R3.** Calling `BaseManager()` with no argument raises `TypeError` (missing required argument `model`).
- **R4.** The class can be subscripted with a model type (`BaseManager[Department](Department)`) and behaves the same as R1.
- **R5.** A subclass that calls `super().__init__(M)` ends up with `model` set to `M` alongside its own attributes; e.g. `DepartmentManager().model is Department`, and its attributes are exactly `department_dao` and `model`.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| no `model` given | `TypeError` | Python's own "missing 1 required positional argument: 'model'" |

**Side effects:** none.

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 18 | required parameter `model` (missing → `TypeError`) | R3 |
| 24 | stores `model` unconditionally (no branch) | R1, R2, R4, R5 |
