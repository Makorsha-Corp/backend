# Spec — `app/services/order_hub_stats_helpers.py`

> **Status:** APPROVED (2026-11-04; no questions)
> **Source commit:** e48a092
> **Revision 2026-11-04 (fill-gaps, `order_hub_stats_helpers.cases.md` gap 1):** model import modules added to Facts. No new question; stays APPROVED. See `## Gap log`.

> **Form.** As `tests/unit/services/department_service.spec.md`, light depth. Four pure mappers, no session, no manager. Which orders reach them (recent, pending, oldest drafts) is decided by the order services and managers that call them, not here.
>
> **Verified by running** (`v4_hub.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\svc4d\`, unsaved model instances, no database): every field of all three summaries; `status_name` `None` with no status loaded and `"Draft"` with one; expense `status_id = 0`; a transfer's money and expense fields `None`; a pending dict with an extra key and an ISO date-time string; `ValidationError` for a missing `id`, a `None` `order_number`, and an order with no `created_at`.

## Review
> No questions.

Checked and **not** violated: **HR-15** — `total_amount` is passed through as the `Decimal` it is; nothing is rounded or computed. **HR-16** — the mappers read only the order and its loaded `current_status`; whether that status can belong to another workspace is decided where the order is written (follow-up FU-1), the mappers have no workspace to compare with. **HR-1 … HR-14** — nothing named, listed, paged, audited or external.

**Permission checks:** none.

## Overview
The purchase, expense and transfer order hubs show a "recent orders" list and, for purchase and transfer orders, "pending" highlights. These helpers turn one order model (or one dict from the order DAOs) into the shared DTOs `OrderHubRecentSummary` and `OrderHubPendingHighlight` (`app/schemas/order_hub.py`). Callers: `PurchaseOrderService.get_purchase_order_hub_stats`, `ExpenseOrderService.get_expense_order_hub_stats`, `TransferOrderService.get_transfer_order_hub_stats`.

**Callables:** 4 specified · 0 not specified
**Externals to mock:** none.
**Integration-only behavior:** none.

**Facts for the test designer**
- Import: `from app.services.order_hub_stats_helpers import purchase_order_to_recent_summary, expense_order_to_recent_summary, transfer_order_to_recent_summary, pending_highlight_from_dict`.
- The DTOs: `OrderHubRecentSummary` — required `id: int`, `order_number: str`, `status_id: int`, `created_at: datetime`; every other field optional, default `None` (`status_name`, `updated_at`, `account_id`, `invoice_id`, `total_amount: Decimal`, `expense_category`, `expense_date`, `due_date`, `source_location_type`, `destination_location_type`). `OrderHubPendingHighlight` — required `id: int`, `order_number: str`; optional `status_name`, `created_at: datetime`. Pydantic's default: unknown keys are ignored.
- Orders need not be saved: `PurchaseOrder(id=…, po_number=…, current_status_id=…, created_at=…, …)` works, and `current_status` can be set to an unsaved `Status(id=…, name=…)` (`app.models.status`). `created_at` is set by the model default only on insert, so an unsaved order must be given one.
- Model imports (the ones the module itself uses): `from app.models.purchase_order import PurchaseOrder`; `from app.models.expense_order import ExpenseOrder`; `from app.models.transfer_order import TransferOrder`; `from app.models.status import Status`. Also `import app.db.base` (registers every model, so the string relationships such as `current_status` resolve when the first instance is built; the verification run `v4_hub.py` did this).

## Not specified
- nothing.

---

## `purchase_order_to_recent_summary(order)`
**Shape:** mapper · **Persistence:** pure · **Visibility:** public (used by: `PurchaseOrderService.get_purchase_order_hub_stats`)

**Returns:** `OrderHubRecentSummary`.

**Rules:**
- **R1.** `id`, `created_at`, `updated_at`, `account_id`, `invoice_id`, `total_amount` are the order's own values; `order_number` = `po_number`; `status_id` = `current_status_id`.
- **R2.** `status_name` is the name of the order's `current_status`; `None` when no status row is loaded or linked.
- **R3.** `expense_category`, `expense_date`, `due_date`, `source_location_type`, `destination_location_type` are `None`.
- **R4.** A value the DTO cannot take (no `created_at`, a `None` `po_number` or `current_status_id`) raises `pydantic.ValidationError`.

**Errors:** `ValidationError` (R4). **Side effects:** none (reading `current_status` may lazy-load it).

---

## `expense_order_to_recent_summary(order)`
**Shape:** mapper · **Persistence:** pure · **Visibility:** public (used by: `ExpenseOrderService.get_expense_order_hub_stats`)

**Rules:**
- **R1.** `id`, `created_at`, `updated_at`, `account_id`, `invoice_id`, `total_amount`, `expense_category`, `expense_date`, `due_date` are the order's own values; `order_number` = `expense_number`.
- **R2.** `status_id` is always `0` and `status_name` always `None`: expense orders have no status row.
- **R3.** `source_location_type`, `destination_location_type` are `None`.
- **R4.** A value the DTO cannot take (no `created_at`, a `None` `expense_number`) raises `ValidationError`.

**Errors:** `ValidationError` (R4). **Side effects:** none

---

## `transfer_order_to_recent_summary(order)`
**Shape:** mapper · **Persistence:** pure · **Visibility:** public (used by: `TransferOrderService.get_transfer_order_hub_stats`)

**Rules:**
- **R1.** `id`, `created_at`, `updated_at`, `source_location_type`, `destination_location_type` are the order's own values; `order_number` = `transfer_number`; `status_id` = `current_status_id`.
- **R2.** `status_name` as `purchase_order_to_recent_summary` R2.
- **R3.** `account_id`, `invoice_id`, `total_amount`, `expense_category`, `expense_date`, `due_date` are `None`.
- **R4.** A value the DTO cannot take raises `ValidationError`.

**Errors:** `ValidationError` (R4). **Side effects:** none

---

## `pending_highlight_from_dict(data)`
**Shape:** mapper · **Persistence:** pure · **Visibility:** public (used by: the purchase and transfer order hub stats, one call per dict of the order DAOs' `get_pending_highlights_for_hub`)

**Rules:**
- **R1.** The dict's `id`, `order_number`, `status_name`, `created_at` become the highlight's fields; a missing optional key is `None`; keys the DTO does not know are ignored; Pydantic's usual conversion applies (an ISO date-time string becomes a `datetime`).
- **R2.** A missing `id` or `order_number`, or a value that cannot convert (`order_number: None`), raises `ValidationError`.

**Errors:** `ValidationError` (R2). **Side effects:** none

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 9, 14 | purchase: status loaded / none | `purchase_order_to_recent_summary` R2 |
| 10–20 | purchase: DTO built (validation) | `purchase_order_to_recent_summary` R1, R3, R4 |
| 24–37 | expense: fixed `status_id = 0`, DTO built | `expense_order_to_recent_summary` R1–R4 |
| 41, 46 | transfer: status loaded / none | `transfer_order_to_recent_summary` R2 |
| 42–51 | transfer: DTO built | `transfer_order_to_recent_summary` R1, R3, R4 |
| 55 | dict unpacked into the DTO | `pending_highlight_from_dict` R1, R2 |

## Gap log
- G1 (`order_hub_stats_helpers.cases.md` gap 1) — Fact — Facts now give the import modules `app.models.purchase_order` (`PurchaseOrder`), `app.models.expense_order` (`ExpenseOrder`), `app.models.transfer_order` (`TransferOrder`), as imported by the module itself (source lines 2–4); the designer's assumption is confirmed.

## Follow-ups for other reviews
> Nothing below is a rule of this module.

| # | Where it must be looked at | What | Came from |
|---|---|---|---|
| FU-1 | Purchase / transfer order managers (writes of `current_status_id`) | HR-16: an order's `current_status` must be a status of its own workspace; the hub shows its name. The refusal belongs to the writes (status service BUG-035 family), not to this mapper. | HR-16 check |
