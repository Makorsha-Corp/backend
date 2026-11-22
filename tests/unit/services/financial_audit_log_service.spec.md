# Spec — `app/services/financial_audit_log_service.py`

> **Status:** APPROVED (2026-11-06; revised 2026-11-07: OQ-23 answered, deferred to the permissions work)
> **Source commit:** e48a092

> **Revision 2026-11-07 (apply-review).** OQ-23 answered by the owner: who may read the log is decided in the permissions work; today's behaviour (every active member) stays and is tested as is. No bug. No rule changed. The cases file reported no gaps.

> **Form.** As `tests/unit/services/work_order_type_service.spec.md`: this spec covers what the service adds. Below it: `tests/unit/dao/financial_audit_log.spec.md` (APPROVED 2026-11-06), whose rules (filters, order, BUG-2370, BUG-2371) are cited, not restated. This service is **not** a `BaseService` and has no write method, so of the Transaction contract (TC1–TC6, `tests/unit/services/base_service.spec.md`) only **TC6** applies.

> **Review round 2026-11-06.** One house-rule line (BUG-2373). Who may read the log is the owner's (OQ-23, not blocking: the check would sit in the endpoints, which are integration-only; the service's rules stand either way).
>
> **Verified by running** (`v1_fal.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\tpl\C\`, rolled back against `marker_test`): the DAO results the service passes on. The service itself was read: each method is one line passing every argument by keyword. **Not run:** HTTP.

## Review

### House-rule violations — applied automatically

- **HR-7** all six endpoints of `app/api/v1/endpoints/financial_audit_logs.py` — `limit: int = Query(…, le=200)` has no lower bound: `limit=0` returns `[]`, a negative `limit` reaches the database and fails (`DataError` 2201W, a 500; run at the DAO). `skip` already has `ge=0` (`get_recent_logs` has no `skip`). Intended: `limit >= 1`, 422 otherwise; the cap of 200 stays.
**Answer:** bug — per HR-7 (house rule)
**Resolution:** 🐞 BUG-2373 (pattern `missing-limit-lower-bound`, as BUG-1217). Integration-only: the rule sits in the endpoint, and this spec's rules pass `limit` on unchanged (`get_recent_logs` R1).

Checked and **not** violated here: **HR-1 … HR-6, HR-8, HR-9** — the DAO's (BUG-2370, BUG-2371) or not applicable. **HR-10 … HR-15** — reads only; no money computed. **HR-16** — every call is scoped by the caller's workspace (from `get_current_workspace`), and the response shows only that workspace's rows.

### Owner question

### Q1. Every member can read the whole financial audit log — OWNER, ⏸ deferred to the permissions work (OQ-23)
**Background:** The log records every change to accounts, invoices and payments: amounts before and after (`changes`), a description such as "Payment of $2000.00 recorded for invoice ID 10", who did it and when, and (once BUG-140 / BUG-603 are fixed) their IP address and browser.
**What happens today:** All six `GET /financial-audit-logs/…` endpoints require only an active membership (`get_current_workspace`, `get_current_active_user`). Any role, `ground-team` included, can read every row, filter by any colleague (`/user/{id}/`), or by time. Nothing in the service or DAO checks a role. The accounts and invoices themselves are equally open to every member today; only the subscription checkout is owner-only (`payments.py:109`).
**Example:** A `ground-team` member calls `GET /financial-audit-logs/user/12/` and sees every payment the finance person recorded or voided, with amounts, and after BUG-140 from which IP address.
**Rules affected:** none in this service (the check would be at the endpoint); listed so the decision is recorded.
**Suggested answer:** for now owner only (and later the finance role, once roles are settled in the permissions work): other members get 403 on all six endpoints. No web page uses these endpoints yet (`financialAuditLogsApi.ts` has hooks, no page calls them), so nothing visible breaks.
**Alternatives:** (a) intended — every member may read it, as they may read accounts and invoices; decide with the permissions work. (b) Every member may read it, but `ip_address` and `user_agent` are shown to the owner only.
**Answer:** owner, 2026-11-07: decide in the permissions work; today's behaviour stays in the tests.
**Resolution:** deferred to the permissions work, no bug. Today: any active member reads all six endpoints (integration-only; no rule of this service). Noted in `docs/future/permissions.md`.

## Overview
`FinancialAuditLogService` is the read-only front of the financial audit trail. The six `GET /financial-audit-logs/…` endpoints call it with the caller's workspace; it calls the matching `financial_audit_log_dao` reader and returns the result unchanged. It holds no state, never commits, rolls back or flushes, and translates no error.

**Callables:** 6 specified · 1 not specified
**Externals to mock:** none
**Integration-only behavior:** the endpoints: membership gate (Q1 / OQ-23), `limit <= 200` and BUG-2373, `skip >= 0`, `start_date` / `end_date` required and parsed by FastAPI, the response model `FinancialAuditLogResponse` (all columns, `ip_address` and `user_agent` included).

**Facts for the test designer**
- Import: `from app.services.financial_audit_log_service import FinancialAuditLogService, financial_audit_log_service`. `FinancialAuditLogService()` takes no arguments; it does **not** inherit `BaseService`. Parameters are positional-or-keyword; the endpoints pass all after `db` by keyword.
- Rows: build `FinancialAuditLog` directly as in the DAO spec's Notes.

**Notes for the test designer**
- "Unchanged" means the same list the DAO returns for the same arguments: same rows, same order. Cases may compare with a direct DAO call in the same session.
- The defaults are the service's own (they are what a direct caller gets): `limit=50` for `get_recent_logs`, `skip=0`, `limit=100` for the others. Prove a default with 51 (or 101) rows.
- TC6 (read leaves the session alone): flush a pending row of another table first (e.g. `make_workspace`), call the method, then `db.rollback()`: the pending row is gone, so nothing committed it.

## Not specified
- `financial_audit_log_service` — module-level singleton, no logic.

---

## `FinancialAuditLogService.get_recent_logs(db, workspace_id, limit=50)`
**Shape:** list · **Persistence:** reads · **Visibility:** public (used by: `GET /financial-audit-logs/`)

**Rules:**
- **R1.** Returns the DAO's `get_recent_logs` for `workspace_id` and `limit`, unchanged (DAO spec `get_recent_logs` R1–R3; BUG-2370). Default `limit` 50. `limit` is passed on as given: `0` returns `[]`, a negative value raises the DAO's `DataError` (BUG-2373 is the endpoint's).
- **R2.** Read only (TC6): no commit, no rollback; an exception from the DAO reaches the caller unchanged.

---

## `FinancialAuditLogService.get_by_entity(db, entity_type, entity_id, workspace_id, skip=0, limit=100)`
**Shape:** list · **Persistence:** reads · **Visibility:** public (used by: `GET /financial-audit-logs/entity/{entity_type}/{entity_id}/`)

**Rules:**
- **R1.** Returns the DAO's `get_by_entity` for the same arguments, unchanged (DAO spec R1–R5). Defaults `skip=0`, `limit=100`.
- **R2.** Read only (TC6), as `get_recent_logs` R2.

---

## `FinancialAuditLogService.get_related_logs(db, entity_type, entity_id, workspace_id, skip=0, limit=100)`
**Shape:** list · **Persistence:** reads · **Visibility:** public (used by: `GET /financial-audit-logs/related/{entity_type}/{entity_id}/`)

**Rules:**
- **R1.** Returns the DAO's `get_related_logs` for the same arguments, unchanged (DAO spec R1–R5: one level, ✅ DAO Q1). Defaults `skip=0`, `limit=100`.
- **R2.** Read only (TC6), as `get_recent_logs` R2.

---

## `FinancialAuditLogService.get_by_action_type(db, action_type, workspace_id, skip=0, limit=100)`
**Shape:** list · **Persistence:** reads · **Visibility:** public (used by: `GET /financial-audit-logs/action/{action_type}/`)

**Rules:**
- **R1.** Returns the DAO's `get_by_action_type` for the same arguments, unchanged (DAO spec R1–R3). Defaults `skip=0`, `limit=100`.
- **R2.** Read only (TC6), as `get_recent_logs` R2.

---

## `FinancialAuditLogService.get_by_user(db, user_id, workspace_id, skip=0, limit=100)`
**Shape:** list · **Persistence:** reads · **Visibility:** public (used by: `GET /financial-audit-logs/user/{user_id}/`)

**Rules:**
- **R1.** Returns the DAO's `get_by_user` for the same arguments, unchanged (DAO spec R1–R3). Defaults `skip=0`, `limit=100`.
- **R2.** Read only (TC6), as `get_recent_logs` R2.

---

## `FinancialAuditLogService.get_by_date_range(db, start_date, end_date, workspace_id, skip=0, limit=100)`
**Shape:** list · **Persistence:** reads · **Visibility:** public (used by: `GET /financial-audit-logs/date-range/`)

**Rules:**
- **R1.** Returns the DAO's `get_by_date_range` for the same arguments, unchanged (DAO spec R1–R5, BUG-2371 on aware bounds). The bounds are passed on as given, with no check that `start_date <= end_date`. Defaults `skip=0`, `limit=100`.
- **R2.** Read only (TC6), as `get_recent_logs` R2.

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 9 | not a `BaseService` | Overview; Facts |
| 12–14 | recent: DAO, `limit` default 50 | `get_recent_logs` R1, R2 |
| 16–18 | entity | `get_by_entity` R1, R2 |
| 20–22 | related | `get_related_logs` R1, R2 |
| 24–26 | action | `get_by_action_type` R1, R2 |
| 28–30 | user | `get_by_user` R1, R2 |
| 32–34 | date range | `get_by_date_range` R1, R2 |
| 37 | module singleton | Not specified |
