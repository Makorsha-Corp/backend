# Spec — `app/dao/financial_audit_log.py`

> **Status:** APPROVED (2026-11-06; revised 2026-11-07; OQ-23 answered: deferred to the permissions work)
> **Source commit:** e48a092

> **Revision 2026-11-07 (fill-gaps, `financial_audit_log.cases.md` gaps 1–2; decided by Claude under the reviewer's delegation (2026-11-07)):** `get_recent_logs` R1a added (a `skip=` argument raises `TypeError`). Gap 1 stays a note by design. OQ-23 answered by the owner (2026-11-07): deferred to the permissions work, no bug; no rule here changes. Stays APPROVED.

> **Review round 2026-11-06.** House-rule lines are applied automatically (BUG-2370, BUG-2371). Q1 and P1 decided by Claude under the reviewer's delegation (2026-11-06). Who may read this log is a money / access question for the owner, parked as **OQ-23** in `docs/testing/owner-questions.md`. It lives in the endpoints, so no rule here waits on it.

> **Standing decisions applied here (not asked again):** a missing `ORDER BY` tie-break is a bug, and no order recipe is deterministic unless it ends in `id` (BUG-1210). A chosen "newest first" order stays (BUG-600, BUG-1190, BUG-1210). Raw lookups stay raw (HR-4 scope; this table has no soft delete anyway). Base behaviour is in `tests/unit/dao/base.spec.md` and is not restated. The writer is `app/utils/audit_logger.py` (`tests/unit/utils/audit_logger.spec.md`, APPROVED).
>
> **Verified by running** (`v1_fal.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\tpl\C\`, one outer transaction rolled back against `marker_test`, private `COVERAGE_FILE`; nothing persisted): the table's columns, defaults, indexes, constraints, no trigger; the database's own `TimeZone` (`America/New_York` on `marker_test`); **five rows of one `performed_at`: paging one at a time gave `[20396], [20396], [20398], [20399], [20400]` (20397 never shown), and after one row was updated `[20397], [20397], [20399], [20400], [20396]`**; the server default giving `18:05` local for `23:05` UTC; `get_related_logs` on an invoice; case-sensitive `entity_type` and `action_type`; `get_by_date_range` with aware and naive bounds under `UTC`, `Asia/Dhaka`, `America/New_York`; inclusive bounds; `start > end`; `get_by_user` in another workspace; `get_recent_logs` default cap (60 rows → 50), `limit=0`, `limit=-1` (`DataError` 2201W); a positional call (`TypeError`). **Not run:** HTTP; the intended behavior of any bug.

## Review

### House-rule violations — applied automatically

- **HR-6** all six readers (`get_by_entity` R4, `get_related_logs` R5, `get_by_action_type` R3, `get_by_user` R3, `get_by_date_range` R5, `get_recent_logs` R2) — ordered by `performed_at` alone. Rows of one timestamp have no order, and paging repeated one row and missed another (verified). Intended: `performed_at` descending, then `id` descending, before paging. Newest first stays (a chosen order, as BUG-1210).
**Answer:** bug — per HR-6 (house rule)
**Resolution:** 🐞 BUG-2370 (pattern `tied-timestamp-no-tiebreak`). Rules: the six listed.

### Precedent matches — confirmed under the delegation

- **BUG-992 precedent** `get_by_date_range` R3 — a bound with a time zone (`…Z`, `+06:00`) is compared with the stored naive UTC through the database session's `TimeZone`. Under `UTC` an entry at 12:00 UTC is found by 11:30Z–12:30Z; under `Asia/Dhaka` and `America/New_York` it is not (verified). Naive bounds are exact.
**Answer:** bug — per BUG-992 precedent: a bound with a zone is turned into naive UTC before the compare; a bound with no zone means UTC, whatever the database's `TimeZone` (precedent — confirmed by Claude under the reviewer's delegation (2026-11-06))
**Resolution:** 🐞 BUG-2371 (pattern `aware-datetime-against-naive-column`). Rules: `get_by_date_range` R3.

Checked and **not** a new line here: **HR-4** — no soft-delete column; audit rows are never deleted by the app. **HR-5** — every filter is in the query before `skip` / `limit`. **HR-7** — the endpoints' missing lower bound is BUG-2373, logged with the service (`tests/unit/services/financial_audit_log_service.spec.md`). **HR-8** — no `LIKE`. **HR-3** — `entity_type` and `action_type` are codes the application writes (`account`, `invoice`, `payment`; `created`, `updated`, `deleted`, `status_changed`, `voided`), not user text, so the exact compare is right (Q1 of the order template DAO, same reasoning). **HR-9, HR-10** — reads only. **HR-15** — amounts sit inside `changes` as written by the managers; this DAO does no arithmetic. **HR-16** — every reader compares the row's own `workspace_id`; `entity_id` and `related_entity_id` have no foreign key, so a row's ids are trusted as the writer set them (the writers pass their own workspace's rows).

### New questions

### Q1. "Related logs" of an account do not include its invoices or payments — ✅ intended
**Background:** The docstring of `get_related_logs` (and of `GET /financial-audit-logs/related/…`) says that for an account it returns the account's rows, "all invoices for that account" and "all payments for those invoices". The code matches one level: rows **about** the entity, plus rows that name it as `related_entity`. The writers set `related_entity` only on payment rows (→ their invoice); account rows and invoice rows name nothing.
**What happens today:** For an invoice, its own rows plus its payments' rows (verified). For an account, only the account's own rows.
**Example:** Account 5 has invoice 10 with two payments. `GET …/related/account/5/` returns the account's `created` / `updated` rows only; `…/related/invoice/10/` returns the invoice's `status_changed` rows and both payments' rows.
**Rules affected:** `get_related_logs` R1–R3
**Suggested answer:** `intended — one level, as coded; the docstrings are corrected`. No web screen calls this endpoint (`frontend/src/features/financialAuditLogs/financialAuditLogsApi.ts` defines the hooks, no page uses them), so nothing depends on the deeper reading. Alternative: follow invoices of an account and their payments (needs a join to `account_invoices`, or `related_entity` set on invoice rows).
**Answer:** intended — one level, as coded; the docstrings are corrected
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-06): rules unchanged, marked ✅. The docstring fix is FU-1 (b); no BUG ID (no behavior change).

### P1. A row written without `performed_at` gets the database's local time — 🐞 BUG-2372
**Background:** `performed_at` is `timestamp without time zone`, NOT NULL, with server default `now()`. The only writer (`log_financial_audit`) always passes `utcnow()` (audit_logger spec R2), so the default is used only by a row built elsewhere.
**What happens today, verified:** a row inserted without `performed_at` reads `18:05` at `23:05` UTC on `marker_test`, whose `TimeZone` is `America/New_York`. Such a row sorts and filters 5 hours away from the rows around it.
**Example:** a future writer forgets the field; its entries appear five hours "earlier" than they happened in every list and date filter here.
**Rules affected:** Model facts, `N1`
**Suggested answer:** `bug — per BUG-1337 precedent: the default is utcnow(), naive UTC, as the writer already does`.
**Answer:** bug — per BUG-1337 precedent (decided by Claude under the reviewer's delegation (2026-11-06))
**Resolution:** 🐞 BUG-2372 (pattern `database-clock-timestamp`). Fix in `app/models/financial_audit_log.py` (`default=utcnow`; the `server_default` may stay for raw SQL, or go). Rules: N1.

### Owner question parked (not blocking)

### OQ-23. Who may read the financial audit log — OWNER, deferred to the permissions work
**Answer:** owner, 2026-11-07: decide in the permissions work; today's behaviour stays in the tests. No bug.
Recorded in `docs/testing/owner-questions.md` and `docs/future/permissions.md`. The access check lives in `app/api/v1/endpoints/financial_audit_logs.py`, which is integration-only; no rule of this DAO changes with the answer. See the service spec for the facts.

## Overview
`FinancialAuditLogDAO` is the read side of the financial audit trail: an append-only table of changes to accounts, invoices and payments, one row per change, written by `log_financial_audit` (`AccountManager`, `InvoicePaymentManager`). The DAO adds six workspace-scoped readers, newest first: by entity, by entity and its related rows, by action, by user, by time range, and the latest N. Its only caller is `FinancialAuditLogService`, behind `GET /financial-audit-logs/…`. The module also defines `FinancialAuditLogCreate`, the input model `log_financial_audit` builds.

**Callables:** 6 specified · 3 not specified
**Externals to mock:** none
**Integration-only behavior:** none here (the endpoints' `limit` bounds and access are the service spec's).

**Model facts (table `financial_audit_logs`, class `app.models.financial_audit_log.FinancialAuditLog`, verified):**
| Column | Type / constraint | Default |
|---|---|---|
| `id` | Integer PK | sequence |
| `workspace_id` | Integer NOT NULL, FK `workspaces.id` ON DELETE CASCADE, indexed | — |
| `entity_type` | varchar(50) NOT NULL, indexed | — |
| `entity_id` | Integer NOT NULL, indexed, **no FK** | — |
| `action_type` | varchar(50) NOT NULL, indexed | — |
| `related_entity_type` | varchar(50) nullable | `NULL` |
| `related_entity_id` | Integer nullable, indexed, no FK | `NULL` |
| `changes` | `json` (not JSONB) nullable | `NULL` |
| `description` | text nullable | `NULL` |
| `ip_address`, `user_agent` | varchar(45), varchar(255), nullable | `NULL` |
| `performed_by` | Integer NOT NULL, FK `profiles.id` (no delete action) | — |
| `performed_at` | `timestamp without time zone` NOT NULL, indexed | server `now()` (BUG-2372) |
No trigger. No soft delete, no `updated_*` columns.

- **N1.** [BUG-2372] A row flushed without `performed_at` gets the current **UTC** time, naive, whatever the database's `TimeZone`. *(Today: the database's local `now()`: 18:05 for 23:05 UTC under `America/New_York`. Verified.)* *(Fix in the model: `default=utcnow`.)*

**Notes for the test designer:**
- Use the singleton `financial_audit_log_dao`. Every parameter after `db` is keyword-only (a positional call raises `TypeError`).
- Build rows directly: `FinancialAuditLog(workspace_id, entity_type, entity_id, action_type, performed_by, performed_at=…)` with `make_workspace` / `make_profile` from `tests/unit/factories.py`. Give `performed_at` explicitly, distinct unless the case is about a tie.
- **The ties (BUG-2370):** five rows of one `performed_at`, page one at a time, then update one row (e.g. `description`), flush, `db.expire_all()`, page again. Today's order rests on physical row order: write the case to the intended result and mark it **non-strict** xfail (as BUG-1210).
- **Time zones (BUG-2371, BUG-2372):** `db.execute(text("SET LOCAL TIME ZONE 'Asia/Dhaka'"))` inside the test's transaction (note the space in `TIME ZONE`). `marker_test`'s own default is `America/New_York`, so N1 fails there without any `SET`; set `UTC` explicitly for cases that must not depend on it.
- **Database errors:** wrap calls expected to raise `DataError` in `with db.begin_nested():` inside `pytest.raises(...)`.

## Not specified
- `FinancialAuditLogCreate` — a Pydantic model with no validators: `entity_type`, `entity_id`, `action_type` required; the six others optional, default `None`. Its use is specified in `tests/unit/utils/audit_logger.spec.md` (BUG-142 and BUG-144 are about its content).
- `financial_audit_log_dao` — module-level singleton, no logic.
- Inherited `BaseDAO` methods — `tests/unit/dao/base.spec.md`. Only `create` is called (by `log_financial_audit`). `update`, `remove`, `get_multi`, `get_by_workspace` have no caller; the table is append-only by convention, nothing in the database enforces it.

## Follow-ups for other reviews
> Nothing below is a rule of this DAO.

| # | Where it must be looked at | What | Came from |
|---|---|---|---|
| FU-1 | **Financial audit log service and endpoints** (`app/services/financial_audit_log_service.py`, `app/api/v1/endpoints/financial_audit_logs.py`) | (a) OQ-23, who may read the log. (b) Q1: the `get_related_logs` docstrings in the DAO and the endpoint describe two levels; correct them to one. (c) BUG-2373, `limit >= 1` on the six endpoints. | this review |

---

## `FinancialAuditLogDAO.get_by_entity(db, *, entity_type, entity_id, workspace_id, skip=0, limit=100)`
**Shape:** list · **Persistence:** reads · **Visibility:** public (used by: `FinancialAuditLogService.get_by_entity` ← `GET /financial-audit-logs/entity/{entity_type}/{entity_id}/`)

**Purpose:** The history of one account, invoice or payment, newest first.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `entity_type` | str | exact compare with `entity_type` |
| `entity_id` | int | equality on `entity_id` |
| `workspace_id` | int | equality on the row's `workspace_id` |
| `skip`, `limit` | int, `0`, `100` | not validated |

**Returns:** a `list` of `FinancialAuditLog` (possibly empty).

**Rules:**
- **R1.** Returns the workspace's rows whose `entity_type` and `entity_id` both match. Rows where the entity appears only as `related_entity` are not returned.
- **R2.** Workspace isolation: rows of the same type and id in another workspace are not returned; an unknown workspace returns `[]`.
- **R3.** `entity_type` is compared exactly: `"Invoice"` finds nothing for `invoice` rows (verified); `""` finds nothing.
- **R4.** [BUG-2370] (HR-6) Rows are ordered by `performed_at` descending, then `id` descending, before `skip` / `limit`; consecutive pages neither repeat nor miss a row. *(Today: `performed_at` only. Verified: a repeat and a miss with five tied rows.)*
- **R5.** At most `limit` rows after `skip` (default 100). `limit=0` or `skip` past the end returns `[]`; a negative value raises (Errors).

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| negative `limit` | `sqlalchemy.exc.DataError`, `.orig.pgcode == "2201W"` | `LIMIT must not be negative` |
| negative `skip` | `sqlalchemy.exc.DataError`, `.orig.pgcode == "2201X"` | `OFFSET must not be negative` |

The same two errors apply to every reader below that takes the parameter (`get_recent_logs` has no `skip`).

**Side effects:** none

---

## `FinancialAuditLogDAO.get_related_logs(db, *, entity_type, entity_id, workspace_id, skip=0, limit=100)`
**Shape:** list · **Persistence:** reads · **Visibility:** public (used by: `FinancialAuditLogService.get_related_logs` ← `GET /financial-audit-logs/related/{entity_type}/{entity_id}/`)

**Purpose:** The history of an entity together with the rows that name it as their related entity (e.g. an invoice and its payments).

**Returns:** a `list` of `FinancialAuditLog` (possibly empty).

**Rules:**
- **R1.** ✅ (Q1) Returns the workspace's rows where (`entity_type`, `entity_id`) match, **or** (`related_entity_type`, `related_entity_id`) match. Each row at most once. Verified for invoice 10: its `status_changed` row and the payment row with `related_entity = invoice 10`.
- **R2.** ✅ (Q1) One level only: a payment of an invoice of an account is not returned for the account (account and invoice rows name no related entity).
- **R3.** ✅ (Q1) Both halves need type **and** id: a row of `payment` 10 (not related to anything) is not returned for `invoice` 10 (verified); a row related to `account` 10 is not returned for `invoice` 10.
- **R4.** Workspace isolation, exact compares, `skip` / `limit`: as `get_by_entity` R2, R3, R5.
- **R5.** [BUG-2370] (HR-6) Order as `get_by_entity` R4, applied to the combined rows. *(Today: `performed_at` only.)*

**Errors:** as `get_by_entity`. **Side effects:** none

---

## `FinancialAuditLogDAO.get_by_action_type(db, *, action_type, workspace_id, skip=0, limit=100)`
**Shape:** list · **Persistence:** reads · **Visibility:** public (used by: `FinancialAuditLogService.get_by_action_type` ← `GET /financial-audit-logs/action/{action_type}/`)

**Purpose:** Every row of one kind of action (e.g. all `voided` payments), newest first.

**Rules:**
- **R1.** Returns the workspace's rows whose `action_type` equals the argument exactly, of any entity type: `"STATUS_CHANGED"` finds nothing (verified).
- **R2.** Workspace isolation and `skip` / `limit`: as `get_by_entity` R2, R5.
- **R3.** [BUG-2370] (HR-6) Order as `get_by_entity` R4. *(Today: `performed_at` only.)*

**Errors:** as `get_by_entity`. **Side effects:** none

---

## `FinancialAuditLogDAO.get_by_user(db, *, user_id, workspace_id, skip=0, limit=100)`
**Shape:** list · **Persistence:** reads · **Visibility:** public (used by: `FinancialAuditLogService.get_by_user` ← `GET /financial-audit-logs/user/{user_id}/`)

**Purpose:** Every financial change one person made in the workspace.

**Rules:**
- **R1.** Returns the workspace's rows with `performed_by == user_id`.
- **R2.** Workspace isolation: the same person's rows in another workspace are not returned (verified: `[]`); an unknown user returns `[]`. `skip` / `limit` as `get_by_entity` R5.
- **R3.** [BUG-2370] (HR-6) Order as `get_by_entity` R4. *(Today: `performed_at` only.)*

**Errors:** as `get_by_entity`. **Side effects:** none

---

## `FinancialAuditLogDAO.get_by_date_range(db, *, start_date, end_date, workspace_id, skip=0, limit=100)`
**Shape:** list · **Persistence:** reads · **Visibility:** public (used by: `FinancialAuditLogService.get_by_date_range` ← `GET /financial-audit-logs/date-range/`, both bounds required)

**Purpose:** The workspace's financial changes between two moments, newest first.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `start_date`, `end_date` | `datetime`, naive or aware | not checked against each other |

**Rules:**
- **R1.** Returns the workspace's rows with `start_date <= performed_at <= end_date`. Both bounds are inclusive: a row exactly at `start_date == end_date` is returned (verified).
- **R2.** `start_date` later than `end_date` returns `[]`, with no error (verified).
- **R3.** [BUG-2371] A bound with a time zone is the moment it names: an entry at 12:00 UTC is found by `11:30Z`–`12:30Z`, and by `17:30+06:00`–`18:30+06:00`, whatever the database's `TimeZone`. A naive bound means UTC. *(Today: an aware bound is compared through the session's `TimeZone`: found under `UTC`, not under `Asia/Dhaka` or `America/New_York`. Naive bounds already behave as intended. Verified.)*
- **R4.** Workspace isolation and `skip` / `limit`: as `get_by_entity` R2, R5.
- **R5.** [BUG-2370] (HR-6) Order as `get_by_entity` R4. *(Today: `performed_at` only.)*

**Errors:** as `get_by_entity`. **Side effects:** none

---

## `FinancialAuditLogDAO.get_recent_logs(db, *, workspace_id, limit=50)`
**Shape:** list · **Persistence:** reads · **Visibility:** public (used by: `FinancialAuditLogService.get_recent_logs` ← `GET /financial-audit-logs/`)

**Purpose:** The workspace's latest financial changes.

**Rules:**
- **R1.** Returns the workspace's rows, at most `limit` (default 50: 60 rows give 50, verified). No `skip`. `limit=0` returns `[]`; a negative `limit` raises `DataError` 2201W (verified).
- **R1a.** There is no `skip` parameter: a call passing `skip=` raises `TypeError` (`… got an unexpected keyword argument 'skip'`) before any query (verified). Callers page only by `limit`.
- **R2.** [BUG-2370] (HR-6) The newest rows by `performed_at`, ties broken by `id` descending, so "the latest 50" is one fixed set. *(Today: `performed_at` only; with ties at the cut-off, which row is the 50th is not fixed.)*
- **R3.** Workspace isolation: as `get_by_entity` R2.

**Errors:** negative `limit`, as `get_by_entity`. **Side effects:** none

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 12–22 | input model, no validators | Not specified |
| 28–37, 65–74, 115–123, 149–157, 183–192, 220–226 | keyword-only parameters; defaults 0 / 100 (50) | Notes; R5 of `get_by_entity`, `get_recent_logs` R1 |
| 55–57 | workspace AND type AND id | `get_by_entity` R1, R2, R3 |
| 59–62 | `performed_at` desc, no tie-break (BUG-2370); offset / limit | `get_by_entity` R4, R5, Errors |
| 97–108 | workspace AND (own match OR related match) | `get_related_logs` R1–R4 |
| 109–112 | order, paging | `get_related_logs` R5 |
| 140–146 | workspace AND action | `get_by_action_type` R1–R3 |
| 174–180 | workspace AND performer | `get_by_user` R1–R3 |
| 210–212 | inclusive bounds, compare through session `TimeZone` for aware values (BUG-2371) | `get_by_date_range` R1, R2, R3 |
| 214–217 | order, paging | `get_by_date_range` R4, R5 |
| 220–226 | signature has no `skip` | `get_recent_logs` R1a |
| 240–243 | workspace; order; limit, no offset | `get_recent_logs` R1–R3 |
| 248 | module singleton | Not specified |
| model `performed_at` server default | `now()` (BUG-2372) | N1 |

## Gap log
G1 (`financial_audit_log.cases.md` gap 1) — Test mechanics — keyword-only parameters stay a note for the test designer, not a rule (as `order_template.spec.md`); no card needed. No spec change.
G2 (`financial_audit_log.cases.md` gap 2) — Fact, verified — `get_recent_logs` R1a: `skip=` raises `TypeError` with the message quoted. Branch map row added.
