# Spec — `app/services/base_service.py`

> **Status:** APPROVED (2026-11-04; no questions)
> **Source commit:** e48a092

> **Form.** As `tests/unit/services/department_service.spec.md`. This is the **home of the Transaction contract (TC1–TC6)** for `BaseService` itself. The six rules were first written in `department_service.spec.md`; they are repeated below **word for word in meaning**, and every approved service spec that cites "TC1–TC6" of the department spec cites these same rules. Nothing here changes or narrows them. What this spec adds are the rules of the two helpers on their own (B1–B7), testable without any subclass.
>
> **Verified by running** (`v3_base.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\svc4d\`, one outer transaction rolled back against `marker_test`, session as the unit-test `db` fixture, `join_transaction_mode="create_savepoint"`; nothing persisted): `BaseService()` takes no arguments; a committed workspace survives a later `db.rollback()`; `_rollback_transaction` discards a flushed, uncommitted row and is harmless on a clean session; a patched `commit` that raises gives exactly one rollback, the same exception object, the pending row gone, and a usable session; when the rollback also raises, the rollback's exception reaches the caller with the commit's as `__context__`; a raising `rollback` passes through `_rollback_transaction`; both helpers return `None`.

## Review
> No questions.

Checked and **not** violated: **HR-1 … HR-16** — the helpers touch no row, name, list, money, external system or workspace; they only end a transaction. **HR-10** — locking is the subclasses' choice.

**Permission checks:** none.

## Overview
`BaseService` is the parent of 36 service classes (`app/services/*_service.py`). It holds no state and two helpers that end the session's transaction: `_commit_transaction` commits and, if the commit fails, rolls back and re-raises; `_rollback_transaction` rolls back. The subclasses call them around their managers (480 call sites); neither helper is overridden anywhere. Not every service inherits it (`NotificationService` does not; `CalendarService` inherits it but never calls either helper).

**Callables:** 2 specified · 1 not specified
**Externals to mock:** none.
**Integration-only behavior:** none.

### Transaction contract (TC) — every `BaseService` write
Repeated from `department_service.spec.md`, unchanged. A service write method calls the manager, commits (`_commit_transaction`), re-reads the row with `db.refresh` and returns it, all inside one `try`; any exception rolls back (`_rollback_transaction`) and is re-raised. As outcomes:
- **TC1.** A write that succeeds is committed: the change survives a later rollback of the same session.
- **TC2.** The returned object is the manager's row, re-read from the database after the commit: columns the database sets (`created_at`, `updated_at`) are loaded on it, and it is not expired.
- **TC3.** Any exception from the manager (`HTTPException`, `IntegrityError`, `DataError`, `pydantic.ValidationError`, anything) rolls the session back and reaches the caller **as the same object**: same type, same `status_code` and `detail` for an `HTTPException`. Nothing the call wrote is saved, **and every other uncommitted change pending in that session is discarded with it**. The session is usable afterwards.
- **TC4.** If the commit itself raises, the session is rolled back and the commit's exception reaches the caller unchanged; nothing is saved.
- **TC5.** If the re-read after a successful commit raises, that exception reaches the caller, and the change **stays saved** (the rollback after a commit has nothing to undo).
- **TC6.** A read (get, list) neither commits nor rolls back: changes pending in the session stay pending, and an exception from the manager reaches the caller unchanged.

TC1–TC6 are tested **in each service's own spec** (they need that service's write method). A service that departs from the pattern says so in its own spec (e.g. `notification_service.spec.md` `mark_read` R4: no rollback). This spec's own tests cover only B1–B7.

**Facts for the test designer**
- Import: `from app.services.base_service import BaseService`. `BaseService()` takes no arguments (it has no `__init__` of its own). Both helpers take `db` positionally.
- Any row will do as "a change": `make_workspace(db)` from `tests/unit/factories.py` (flushes, does not commit).

**Notes for the test designer**
- Session and commits: as the Notes of `department_service.spec.md`. Under the `db` fixture `commit()` only releases a savepoint. Assert "committed" with a test-level `db.rollback()` and a re-select; "discarded" with a re-select that finds nothing.
- Failing commit: `unittest.mock.patch.object(db, "commit", side_effect=RuntimeError("boom"))`. To count rollbacks, wrap the real one: `patch.object(db, "rollback", side_effect=real_rollback)` where `real_rollback = db.rollback` taken before patching (the mock calls it and records the call).
- Failing rollback: `patch.object(db, "rollback", side_effect=ValueError("rb"))`.

## Not specified
- `BaseService` class body — docstring only, no attributes.

---

## `BaseService._commit_transaction(db)`
**Shape:** helper · **Persistence:** writes · **Visibility:** internal (used by: every `BaseService` subclass write method)

**Purpose:** Save the session's pending changes; if saving fails, undo them and pass the failure on.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `db` | `Session` | the request's session; not checked |

**Returns:** `None`.

**Rules:**
- **B1.** Every change pending in the session (added, flushed, or modified) is committed: it survives a later `db.rollback()` of the same session.
- **B2.** If the commit raises, the session is rolled back **exactly once**, every pending change is discarded, and the commit's exception reaches the caller as **the same object** (no wrapping, no translation). The session is usable afterwards (a new row can be flushed).
- **B3.** If the commit raises and the rollback raises too, the **rollback's** exception reaches the caller; the commit's exception is its `__context__`.
- **B4.** A commit with nothing pending succeeds and returns `None`.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| commit fails | the commit's exception, unchanged | — |
| commit fails and rollback fails | the rollback's exception (`__context__` = commit's) | — |

**Side effects:** commit, or rollback after a failed commit.

---

## `BaseService._rollback_transaction(db)`
**Shape:** helper · **Persistence:** writes · **Visibility:** internal (used by: every `BaseService` subclass, in its `except` block)

**Purpose:** Undo the session's pending changes.

**Returns:** `None`.

**Rules:**
- **B5.** Every uncommitted change in the session is discarded, including rows flushed earlier in the same transaction; changes committed before the call stay.
- **B6.** On a session with nothing pending it does nothing and returns `None`.
- **B7.** If the rollback raises, that exception reaches the caller unchanged.

**Errors:** the rollback's own exception, unchanged. **Side effects:** rollback.

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 26–27 | commit succeeds | B1, B4; TC1 |
| 28–30 | commit raises → rollback, re-raise | B2; TC4 |
| 29 | rollback inside the `except` raises | B3 |
| 39 | rollback | B5, B6, B7; TC3 |
