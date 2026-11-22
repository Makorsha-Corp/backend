# Spec — `app/dao/invoice_item.py`

> **Status:** APPROVED (2026-11-03; nothing open)
> **Source commit:** e48a092

> **Gap round 2026-11-03.** Cases gap 1 answered by the owner (2026-11-03): BUG-1283, `delete_all_for_invoice` R7. Cases gap 2: BUG-638's row now names this DAO as the file to fix.

> **Base behaviour** is in `tests/unit/dao/base.spec.md` and is not restated.
>
> **Standing decisions applied here (not asked again):** a missing `ORDER BY` is a bug, and no order recipe counts as deterministic unless it ends in `id`. Things of a soft-deleted parent are hidden; ledgers and logs are history. HR-16: a row linking to another workspace's row is invalid data. Raw lookups stay raw (HR-4 scope).
>
> **Verified by running** (throwaway scripts `cat1.py`, `v1.py`, `v6.py`, harness `h.py`, `w.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\childdao\`, each transaction rolled back against `marker_test`; nothing committed): the table's columns, constraints, indexes, no trigger, no table references it; order, and a tie before and after the lower `id` was updated; 101 lines; unknown ids, `0`, another workspace; a row of workspace B on an invoice of A; keyword-only parameters; delete with other invoices, a foreign row, an unknown id, a confirmed invoice, and a rollback; the session's stale instance after the delete; a pending line of this invoice and of another invoice (`v8.py`). **Not run:** anything over HTTP; two concurrent transactions; the intended behaviour of BUG-638.

## Review
> Nothing open. Overwrite the pre-filled answer only if the house rule should not apply here.

### House-rule violations — applied automatically

- **HR-6** `get_by_invoice` R5 — ordered by `line_number` alone, and `line_number` is not unique. The schema defaults it to `1`, so two lines added through `POST /invoice-items/` with no number tie. Verified: two lines numbered 1 swapped places after the lower `id` was updated. Intended: `line_number` ascending, then `id` ascending.
**Answer:** bug — per HR-6 (house rule)
**Resolution:** BUG-638 already holds this (logged at `AccountInvoiceManager.get_items`, intended "item `id` ascending"). No new ID; its row names this DAO as the file to fix.

Checked and **not** a new line here: **HR-6** on `get_by_id_and_workspace` — at most one row by primary key. **HR-5, HR-7, HR-8** — no paging, no `LIKE`. **HR-4** — neither this table nor `account_invoices` has a soft-delete column. **HR-9, HR-10** — the DAO stamps nothing; `sync_items_from_list` holds the draft check. **HR-15** — the DAO computes no money. The sum is `_recalculate_invoice_amount`, already specified. It reads session instances, so an unrounded `line_subtotal` not yet read back counts unrounded: two lines of `0.125` in one session gave `0.25` over stored lines of `0.13` (verified). No path found that does this with two lines, because each `PUT /invoice-items/{id}/` touches one line, and one unrounded line among two-decimal lines rounds to the same total. **HR-16** — `delete_all_for_invoice` has no workspace filter (R2), but its one caller passes an invoice it already scoped. No response is affected.

## Overview
`InvoiceItemDAO` reads and bulk-deletes `invoice_items`, the frozen line snapshot of an account invoice. Callers: `AccountInvoiceManager` (`_recalculate_invoice_amount`, `get_items`, `sync_items_from_list`) and the `/invoice-items/` endpoints, which also use inherited `create`, `update` and `remove`. It protects workspace isolation on reads. It takes no lock and does not look at the invoice's status.

**Callables:** 3 specified · 2 not specified
**Externals to mock:** none
**Integration-only behavior:** none

**Model facts (table `invoice_items`):** `workspace_id` FK CASCADE, `invoice_id` FK `account_invoices` CASCADE, `description`, `quantity`, `unit_price`, `line_subtotal` (Numeric(15,2)) are NOT NULL; `line_number` NOT NULL, default `1` in the model, the schema and the database; `created_at` default `utcnow`. `item_id` and `source_order_item_id` are plain integers with no foreign key. No soft delete, no unique constraint, no index on `line_number`. The parent has no soft-delete column.

**Notes for the test designer:**
- `from app.dao.invoice_item import invoice_item_dao`. Workspaces and profiles from `tests/unit/factories.py`. `Account(workspace_id, name)`, then `AccountInvoice(workspace_id, account_id, invoice_type="payable", invoice_status="draft", invoice_amount=0, paid_amount=0, invoice_date, payment_status="unpaid", allow_payments=True)`. Sessions run with `autoflush=False`: flush before calling the DAO.
- **BUG-638:** two lines with one `line_number`, then update the lower `id`, flush, `db.expire_all()`, and force a sequential scan as in the base spec's BUG-100 note. The result rests on physical row order: write the case to the intended result with a **non-strict** xfail.

## Not specified
- `invoice_item_dao` — module-level singleton, no logic.
- Inherited `BaseDAO` methods not overridden — covered by the base spec.

---

## `InvoiceItemDAO.get_by_invoice(db, *, invoice_id, workspace_id)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `_recalculate_invoice_amount`, `AccountInvoiceManager.get_items`, `GET /invoice-items/`)

**Purpose:** All lines of one invoice, in line order.

**Returns:** a `list` of `InvoiceItem` (possibly empty).

**Rules:**
- **R1.** Returns every row with that `invoice_id` and that `workspace_id`; lines of other invoices are not returned.
- **R2.** Workspace isolation follows the row: another workspace returns `[]`. A row of workspace B on an invoice of A is returned for B and not for A. (HR-16: invalid data.)
- **R3.** An unknown invoice, `invoice_id=0`, or an invoice with no lines returns `[]`.
- **R4.** Ordered by `line_number` ascending.
- **R5.** [BUG-638] (HR-6) Lines with one `line_number` are ordered by `id` ascending. *(Today: no tie-break; two tied lines swapped after the lower `id` was updated.)*
- **R6.** No paging and no cap: 101 lines give 101 rows.
- **R7.** Positional `invoice_id` raises `TypeError`.

**Errors:** none of its own.

**Side effects:** none

---

## `InvoiceItemDAO.get_by_id_and_workspace(db, *, id, workspace_id)`
**Shape:** get
**Persistence:** reads
**Visibility:** public (used by: `GET`, `PUT`, `DELETE /invoice-items/{id}/`)

**Purpose:** One line by id, inside one workspace.

**Returns:** the `InvoiceItem`, or `None`.

**Rules:**
- **R1.** An override with the same outcome as `BaseDAO.get_by_id_and_workspace` R1–R3: found, `None` for another workspace, `None` for an unknown id. The model has no `is_deleted`.

**Errors:** none.

**Side effects:** none

---

## `InvoiceItemDAO.delete_all_for_invoice(db, invoice_id)`
**Shape:** delete
**Persistence:** writes
**Visibility:** public (used by: `AccountInvoiceManager.sync_items_from_list`, after its draft check)

**Purpose:** Remove every line of one invoice, so a sync can write them again.

**Returns:** `None`.

**Rules:**
- **R1.** Every row with that `invoice_id` is physically deleted; rows of other invoices stay.
- **R2.** There is no workspace filter: a row of workspace B carrying this `invoice_id` is deleted too.
- **R3.** An unknown id, `0`, or an invoice with no lines deletes nothing and raises nothing.
- **R4.** The invoice's status is not looked at: lines of a `confirmed` invoice are deleted.
- **R5.** The delete is flushed, not committed: a query in the same session finds nothing, and rolling back restores the lines.
- **R6.** Session objects are not synchronised: an instance loaded before the call stays in the session, and `db.get(InvoiceItem, id)` returns it with no query. `get_by_invoice` and `get_by_id_and_workspace` run a query and do not find it.
- **R7.** [BUG-1283] A line of the same invoice that was added to the session but not yet flushed is deleted too: after the call no query finds it. The method's flush does not store it. A pending line of another invoice is stored by that flush as usual. *(Today: the `DELETE` runs before the pending rows are written, then the method's flush inserts them, so the pending line of this invoice survives.)*

**Errors:** none of its own.

**Side effects:** rows deleted, flushed; pending rows of other invoices are inserted by the same flush (R7); no event, no commit.

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 12 | keyword-only parameters | `get_by_invoice` R7 |
| 15 | invoice AND workspace | `get_by_invoice` R1, R2, R3 |
| 16 | `line_number` only (BUG-638) | `get_by_invoice` R4, R5 |
| 17 | `.all()`: no cap; empty / many | `get_by_invoice` R3, R6 |
| 23–24 | id AND workspace; `.first()`: row / `None` | `get_by_id_and_workspace` R1 |
| 28 | invoice only, no workspace; no status; 0 / many rows; `synchronize_session=False` | `delete_all_for_invoice` R1, R2, R3, R4, R6 |
| 28–29 | `DELETE` before pending rows are flushed (BUG-1283); flush inserts them | `delete_all_for_invoice` R7 |
| 29 | flush, no commit | `delete_all_for_invoice` R5 |
| 32 | module singleton | Not specified |

## Gap log
- G1 (invoice_item.cases.md gap 1) — intent — answered by the owner (2026-11-03): a pending line of the same invoice is deleted too. New rule `delete_all_for_invoice` R7, tagged BUG-1283.
- G2 (invoice_item.cases.md gap 2) — fact — BUG-638's row names `app/dao/invoice_item.py` as the file to fix, with `line_number` first and `id` as tie-break.
