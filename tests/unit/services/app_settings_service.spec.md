# Spec — `app/services/app_settings_service.py`

> **Status:** APPROVED (2026-11-03; nothing open). Stays APPROVED after fill-gaps (Gap log at the end; decided by Claude under the reviewer's delegation (2026-11-03)).
> **Source commit:** e48a092

> **Form.** As `tests/unit/services/department_service.spec.md`. This service has **no manager** and does **not** inherit `BaseService`: it calls `app_settings_dao` directly and commits and rolls back itself. Its transaction rules are therefore written out below (S1–S5), with the same outcomes as TC1–TC6 where the code is the same. Below it: `tests/unit/dao/app_settings.spec.md` (APPROVED) and `tests/unit/dao/base.spec.md`.

> **Routed here and written as rules:** app settings DAO FU-1: the blank name (HR-1) and the display order (HR-6) are this service's and its schema's; BUG-1225 (unique names) reaches `create_setting`; BUG-1217 (`limit` lower bound) is the endpoint's and only cited.
>
> **House-rule lines logged here (2026-11-03):** BUG-1524, BUG-1525. No question; nothing decided under the delegation.
>
> **Verified by running** (`h.py`, `v3_http.py`, `v4_notif.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\svc1\`, one outer transaction rolled back against `marker_test`, session as the `db` fixture, HTTP through `TestClient` with overridden dependencies; nothing persisted): `POST` with name `"   "` → 201, stored as typed; `" Feat "` → 201, stored with its spaces; a second `feat` → 201 (two rows); `GET /app-settings/` returns rows in insertion order (`zeta`, `Alpha`, `beta` stay in that order); `limit=0` → `[]`; `limit=-1` → 500 (`DataError`, and the request's session is left aborted); `update_setting` / `delete_setting` / `get_by_id` / `get_by_name` of an unknown id or name → `None` / `False` / `None` / `None`, 404 at the API; another workspace's id → 404 on get and delete; `PUT` with `{"enabled": null}` and with `{}` → 200, unchanged; `PUT` with a `name` → the name is ignored; `DELETE` → 204 and the row is gone; `GET /app-settings/name/FEAT/` → 404 for `feat`. **Not run:** the intended behavior of BUG-1524, BUG-1525, BUG-1225.

## Review

### House-rule violations — applied automatically

- **HR-1** `create_setting` R3 — a setting's name is stored as typed: `"   "` and `" Feat "` are accepted (verified). Intended: `AppSettingsCreate` trims the name and refuses a blank one (422 at the API), nothing written; the stored name is trimmed. On the input schema only: `AppSettingsResponse` inherits `AppSettingsBase`, so rows already padded or blank stay readable (precedent BUG-915).
**Answer:** bug — per HR-1 (house rule)
**Resolution:** 🐞 BUG-1524 (pattern `blank-name-accepted`). Rules: `create_setting` R3.
- **HR-6** `get_settings` R2 — the list has no display order (insertion order verified; BUG-100 gives `id` order at the DAO). Intended: name case-insensitive ascending, then `id` ascending, before `skip` / `limit`.
**Answer:** bug — per HR-6 (house rule)
**Resolution:** 🐞 BUG-1525 (pattern `unordered-pagination`). Rules: `get_settings` R2.

Existing bug written as a rule here, no new ID: **BUG-1225** `create_setting` R4 (one name per workspace, case-insensitive after trimming, 409). Cited, not a rule here: BUG-1217 (`GET /app-settings/` accepts `limit <= 0`).

Checked and **not** violated: **HR-4** — no soft delete; a delete is a hard delete, and nothing references the table. **HR-5** — no filter besides the workspace. **HR-7** — BUG-1217, the endpoint's. **HR-8** — no `LIKE`; the by-name lookup is exact (DAO R3, decided there). **HR-9** — no audit columns. **HR-10** — a flag is no harmful state. **HR-11 … HR-15** — none applies. **HR-16** — every lookup compares the row's own `workspace_id`; the hard delete reads the row by id after the workspace check, so another workspace's row is never removed (verified: 404).

**Permission checks:** none; any active member may create, flip and delete the workspace's flags. Nothing in the backend or frontend reads these flags today (app settings DAO Q1), so this changes nothing anyone sees; not a question.

## Overview
`AppSettingsService` keeps a workspace's named on/off flags (`app_settings`: `name`, `enabled`). The `/app-settings/` endpoints call it; it calls `app_settings_dao` directly and owns the transaction. It answers "not found" with `None` (get, update) or `False` (delete), and the endpoint turns each into 404 `App setting not found`.

**Callables:** 6 specified · 1 not specified
**Externals to mock:** none.
**Integration-only behavior:** the 404 `{"detail": "App setting not found"}` the endpoint makes of `None` / `False`; `GET /app-settings/` paging bounds (`skip >= 0`, `limit <= 100`, BUG-1217); schema validation (400 today, BUG-461; 422 intended); the global `IntegrityError` handler (409 for BUG-1225's index).

**Facts for the test designer**
- Import: `from app.services.app_settings_service import AppSettingsService, app_settings_service`. `AppSettingsService()` takes no arguments. Parameters are positional-or-keyword; the endpoints pass all after `db` by keyword.
- Schemas: `AppSettingsCreate(name: str, enabled: bool)`, both required, no other check today. `AppSettingsUpdate(enabled: bool | None = None)`, nothing else: other keys in the body are ignored. `AppSettingsResponse` adds `id` to `AppSettingsBase`.
- Table `app_settings`: app settings DAO spec, Model facts.

**Notes for the test designer**
- Session and commits: as the Notes of `department_service.spec.md` (the `db` fixture makes the service's `db.commit()` a savepoint release). The same "commit setup before an error path" note applies: the service's rollback discards uncommitted rows.
- **S2 / S3 failure paths:** `patch.object(db, "commit", side_effect=RuntimeError("boom"))` and `patch.object(db, "refresh", ...)`, as TC4, TC5.
- **BUG-1524:** build `AppSettingsCreate(name="   ", enabled=True)` inside `pytest.raises(pydantic.ValidationError)` → strict xfail; `AppSettingsCreate(name=" Feat ", enabled=True)` then `create_setting`: stored `"Feat"` → strict xfail. Assert `AppSettingsBase(name="   ", enabled=True)` stays valid.
- **BUG-1525:** names `"zeta"`, `"Alpha"`, `"beta"` created in that order; intended `Alpha`, `beta`, `zeta`. Today's order rests on physical row order → **non-strict** xfail. No row case can show the `id` tie-break: once BUG-1225 holds, two settings never compare equal by name. The tie-break is checked on the emitted statement only (`ORDER BY` ends in `id`), as the cases do.
- **BUG-1225:** the second create raises `IntegrityError` 23505 once the index exists, after the service's rollback (no `begin_nested` needed). Today it is stored → strict xfail. `" feat "` against `Feat` collides too.

## Not specified
- `app_settings_service` — module-level singleton, no logic.

---

### Transaction rules of this service (S)
- **S1.** A write that succeeds (`create_setting`, `update_setting` with a found row, `delete_setting` with a found row) is committed: TC1's outcome.
- **S2.** Any exception inside a write (database error at the flush or commit, anything) rolls the session back and reaches the caller unchanged; nothing the call wrote is saved and other uncommitted changes in the session are discarded too: TC3, TC4's outcome.
- **S3.** `create_setting` and `update_setting` return the row re-read after the commit; if that re-read raises, the exception reaches the caller and the change stays saved: TC2, TC5's outcome. `delete_setting` re-reads nothing.
- **S4.** A "not found" answer (`None`, `False`) neither commits nor rolls back.
- **S5.** The reads (`get_settings`, `get_by_id`, `get_by_name`) neither commit nor roll back: TC6's outcome. A database error in a read reaches the caller unchanged **and leaves the session aborted**; the request's session is then discarded by the API.

---

## `AppSettingsService.get_settings(db, workspace_id, skip=0, limit=100)`
**Shape:** list · **Persistence:** reads · **Visibility:** public (used by: `GET /app-settings/`, always with `skip`, `limit`)

**Rules:**
- **R1.** Only the workspace's settings are listed; another workspace's never appear. At most `limit` after skipping `skip`; `limit=0` gives `[]`.
- **R2.** [BUG-1525] (HR-6) Ordered by name case-insensitive ascending, then `id` ascending, before `skip` / `limit`. *(Today: no order of its own; insertion order observed. Verified.)*
- **R3.** Negative `skip` or `limit` raise `DataError` (base DAO). Read only (S5).

**Errors:** `DataError` on negative paging. **Side effects:** none

---

## `AppSettingsService.get_by_id(db, setting_id, workspace_id)`
**Shape:** get · **Persistence:** reads · **Visibility:** public (used by: `GET /app-settings/{id}/`, which answers 404 for `None`)

**Rules:**
- **R1.** The setting of that id in that workspace is returned.
- **R2.** Unknown id, `0`, another workspace's id → `None`, no error.
- **R3.** Read only (S5).

**Errors:** none. **Side effects:** none

---

## `AppSettingsService.get_by_name(db, name, workspace_id)`
**Shape:** get · **Persistence:** reads · **Visibility:** public (used by: `GET /app-settings/name/{name}/`, 404 for `None`)

**Rules:**
- **R1.** The answer is the DAO's `get_by_name` for this name and workspace, unchanged: exact match, `None` when nothing matches (app settings DAO R1–R4).
- **R2.** Read only (S5).

**Errors:** none. **Side effects:** none

---

## `AppSettingsService.create_setting(db, setting_in, workspace_id)`
**Shape:** create · **Persistence:** writes · **Visibility:** public (used by: `POST /app-settings/`, 201)

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `setting_in` | `AppSettingsCreate` | `name`, `enabled`; nothing else checked today |
| `workspace_id` | int | stored on the row; overrides nothing (the schema has no `workspace_id`) |

**Returns:** the new `AppSettings`, committed and re-read (S1, S3).

**Rules:**
- **R1.** One row is stored with the given `name`, `enabled` and `workspace_id`; committed (S1); returned re-read with its `id` (S3).
- **R2.** No acting user is recorded: the table has no such column.
- **R3.** [BUG-1524] (HR-1) The name is stored trimmed; a blank or whitespace-only name is refused by `AppSettingsCreate` (`pydantic.ValidationError`; 422 at the API) and nothing is written. *(Today: `"   "` and `" Feat "` are stored as typed. Verified.)*
- **R4.** [BUG-1225] (app settings DAO Q1, HR-2) A name already used in the workspace, compared case-insensitively after trimming, is refused: `IntegrityError` 23505 reaches the caller after the rollback, nothing saved (409 at the API). The same name in another workspace is stored. *(Today: stored; two rows. Verified.)*
- **R5.** Any other error follows S2, S3.

**Errors:** `pydantic.ValidationError` (schema, BUG-1524); `IntegrityError` (BUG-1225); database errors unchanged.

**Side effects:** one `app_settings` row, committed; on error, rolled back.

---

## `AppSettingsService.update_setting(db, setting_id, setting_in, workspace_id)`
**Shape:** update · **Persistence:** writes · **Visibility:** public (used by: `PUT /app-settings/{id}/`, 404 for `None`)

**Returns:** the `AppSettings`, committed and re-read; or `None`.

**Rules:**
- **R1.** Unknown id, `0`, another workspace's id → `None`; nothing written, no commit (S4).
- **R2.** A found setting gets `enabled` as sent, committed (S1), returned re-read (S3).
- **R3.** `enabled` omitted or `null` → the setting is unchanged and returned (a no-op commit). The name cannot be changed: `AppSettingsUpdate` has no `name`, and a `name` in the body is ignored (verified).
- **R4.** Any error follows S2, S3.

**Errors:** none of its own. **Side effects:** `enabled`, committed; on error, rolled back.

---

## `AppSettingsService.delete_setting(db, setting_id, workspace_id)`
**Shape:** delete · **Persistence:** writes · **Visibility:** public (used by: `DELETE /app-settings/{id}/`, 204; 404 for `False`)

**Returns:** `True` when deleted, `False` when not found.

**Rules:**
- **R1.** Unknown id, `0`, another workspace's id → `False`; nothing written, no commit (S4); the other workspace's row stays.
- **R2.** A found setting is hard-deleted: the row is gone, committed (S1); `True` is returned.
- **R3.** Any error follows S2.

**Errors:** none of its own. **Side effects:** one row deleted, committed; on error, rolled back.

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 13 | list: base `get_by_workspace`, no order of its own (BUG-1525) | `get_settings` R1–R3 |
| 17 | get by id | `get_by_id` R1–R3 |
| 21 | get by name | `get_by_name` R1, R2 |
| 25–31 | create: dump, add `workspace_id`, DAO create, commit, refresh, return | `create_setting` R1–R4; S1, S3 |
| 32–34 | create: any exception → rollback, re-raise | `create_setting` R4, R5; S2 |
| 39–41 | update: not found → `None` | `update_setting` R1; S4 |
| 42–45 | update: DAO update (`exclude_unset`, `exclude_none`), commit, refresh, return | `update_setting` R2, R3 |
| 46–48 | update: any exception → rollback, re-raise | `update_setting` R4; S2 |
| 53–55 | delete: not found → `False` | `delete_setting` R1; S4 |
| 56–58 | delete: hard delete, commit, `True` | `delete_setting` R2 |
| 59–61 | delete: any exception → rollback, re-raise | `delete_setting` R3; S2 |
| 64 | module singleton | Not specified |

## Gap log
G1 (app_settings_service.cases.md gap 1) — Contradiction — the paging tie-break note removed; the `id` tie-break is asserted on the statement. Notes, `get_settings` R2 unchanged.
