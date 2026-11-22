# Spec — `app/utils/notification_entity_label.py`

> **Status:** APPROVED
> **Source commit:** e48a092

## Review
> Reviewer: answer each question on its **Answer:** line with one of
> `intended` · `bug` · `bug — <what it should do instead>` · `remove` (unreachable
> code only) · or a question back.
> Then run the describer in `apply-review` mode.

### New questions

### Q1. Missing-record label has two different formats depending on the entity type — 🐞 BUG-200
**Background:** Every notification points at an entity (a purchase order, a project, an inventory, …) by type and id. The notification list shows a human label for it — the business number (e.g. `PO-2026-015`) or name when the record can be found. When it cannot be found (deleted from the database, wrong workspace, or the number/name is empty), a fallback label is shown instead. This module contains a table of friendly type names ("purchase order", "sales order", "project component", …) meant for that fallback, but for every type that attachments also support it is never used — those types use the attachment module's folder-style fallback instead.
**What happens today:** For purchase/sales/expense/transfer/work orders, projects, project components, items, machines and support tickets, the fallback is `<raw_type>-<id>` (e.g. `purchase_order-5`). Only `inventory` (and any unknown type) gets the friendly form `<type name> #<id>` (e.g. `inventory #5`).
**Example:** A user is mentioned in the discussion of purchase order id 5, and that PO row is later removed. Their notification list shows "purchase_order-5", while a mention on inventory id 7 shows "inventory #7". The friendly entries "purchase order", "sales order", … in this module's table are never displayed.
**Rules affected:** `resolve_notification_entity_label` R3, R4, R6
**Suggested answer:** bug — when no business label is available, every entity type shows the friendly form `<type name> #<id>` (e.g. "purchase order #5"), never the raw `purchase_order-5` folder-style fallback.
**Answer:** bug — when no business label is available, every entity type shows the friendly form `<type name> #<id>` (e.g. "purchase order #5"), never the raw `purchase_order-5` folder-style fallback. (reviewer accepted suggestion)
**Resolution:** whenever no business label is available (row not found, found only in another workspace, label empty/`NULL`, or type `scratch`), the result is `"<type name> #<entity_id>"`. Type names come from this module's table; types the table lacks (`account_invoice`, `support_ticket`, `scratch`) use the type with `_` replaced by a space — "account invoice", "support ticket", "scratch" (best-practice default, delegated by reviewer). The fix belongs in `app/utils/notification_entity_label.py`; `AttachmentManager.resolve_entity_label` keeps its `<type>-<id>` fallback, because attachment and mobile-upload callers use it for folder-style labels (best-practice default, delegated by reviewer). Rules: R3a, R4a, R6.

## Overview
Turns a notification's `(entity_type, entity_id)` into a human-readable label for the notification list (`GET /me/notifications/`, via `_to_notification_response` in `app/api/v1/endpoints/notifications.py`, called once per notification in the page). For entity types that attachments also support it reuses `AttachmentManager.resolve_entity_label`, which looks the entity up **within the given workspace** and returns its business number or name; otherwise it builds `"<type name> #<id>"`. Intended (BUG-200): whenever no business label is available, every type gets the `"<type name> #<id>"` form. It only reads; it never writes and never raises for an unknown type.

Entity types notifications actually carry today (from `DiscussionEntityType`, the only notification producer being discussion mentions): `purchase_order`, `transfer_order`, `expense_order`, `work_order`, `sales_order`, `project`, `project_component`, `machine`, `inventory`, `item`, `support_ticket`. `Notification.entity_type` and `entity_id` are NOT NULL, so `None` never reaches this function from the API. `account_invoice` and `scratch` are valid attachment types but are never produced by notifications (reachable only by calling the function directly).

**Callables:** 1 specified · 0 not specified
**Externals to mock:** none (reads Postgres only)
**Integration-only behavior:** none

**Notes for the test designer:** pure function over a real DB session — call it directly with rows created via factories. Label source per type (all looked up by `id` AND `workspace_id`, soft-deleted rows included):

| entity_type | label field |
|---|---|
| `purchase_order` | `PurchaseOrder.po_number` |
| `sales_order` | `SalesOrder.sales_order_number` |
| `expense_order` | `ExpenseOrder.expense_number` |
| `transfer_order` | `TransferOrder.transfer_number` |
| `work_order` | `WorkOrder.work_order_number` |
| `project` | `Project.name` |
| `project_component` | `ProjectComponent.name` |
| `machine` | `Machine.name` |
| `item` | `Item.sku`, or `Item.name` if `sku` is null/empty |
| `account_invoice` | `AccountInvoice.invoice_number` (nullable) |
| `support_ticket` | `HelpTicket.ticket_number` |

Performance note (not a rule): one lookup query per notification, so a 200-row page issues up to 200 extra queries.

## Not specified
- `_ENTITY_TYPE_LABEL` — module constant; its observable effect is covered by R3a/R4a/R6/R7/R8.

---

## `resolve_notification_entity_label(db, *, workspace_id, entity_type, entity_id)`
**Shape:** mapper
**Persistence:** reads
**Visibility:** public (used by: `app/api/v1/endpoints/notifications.py::_to_notification_response`)

**Purpose:** Give a notification's target entity a business-facing label (e.g. `PO-2026-015`, a project name) instead of a raw id.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `db` | `Session` | Real DB session; only read. |
| `workspace_id` | `int` | Workspace the lookup is scoped to. No validation. |
| `entity_type` | `str` | Entity type string; exact, case-sensitive match against known values. Any string accepted. |
| `entity_id` | `int` | Id of the entity. No validation. |

**Returns:** a `str` (see rules); never `None`, never raises for an unknown type.

**Rules:**
- **R1.** Given `entity_type` is one of the attachment-supported types (`purchase_order`, `sales_order`, `expense_order`, `transfer_order`, `work_order`, `project`, `project_component`, `item`, `machine`, `account_invoice`, `support_ticket`) and a row with that `id` exists **in the given workspace**, the result is that row's label field (table in Overview), exactly as stored (no trimming or formatting).
- **R2.** For `item`, the label is the `sku` when it is non-empty; when `sku` is `NULL` or `""`, the label is the item's `name`.
- **R3.** Given an attachment-supported type (R1 list) and **no** row is found — the id does not exist, or it exists only in another workspace — the result is the fallback label (format: R3a), never the label of a row in another workspace.
- **R3a.** [BUG-200] The fallback label is `"<type name> #<entity_id>"`, where the type name is: `purchase_order` → "purchase order", `sales_order` → "sales order", `expense_order` → "expense order", `transfer_order` → "transfer order", `work_order` → "work order", `project` → "project", `project_component` → "project component", `machine` → "machine", `item` → "item", `account_invoice` → "account invoice", `support_ticket` → "support ticket" (e.g. `"purchase order #5"`, `"support ticket #12"`). *(Today: `"<entity_type>-<entity_id>"` with the raw type string, e.g. `"purchase_order-5"`.)* (Names for `account_invoice`/`support_ticket` — best-practice default, delegated by reviewer. Fix belongs in this module; `AttachmentManager.resolve_entity_label` keeps its own `<type>-<id>` fallback for its other callers.)
- **R4.** Given an attachment-supported type and the row is found but its label field is empty (`""` or `NULL` — e.g. an account invoice with no `invoice_number`, or an item with empty `sku` and empty `name`), the result is the fallback label (format: R3a) — never `""` and never `None`.
- **R4a.** [BUG-200] For R4 the fallback has the R3a format, e.g. `"account invoice #5"`, `"item #8"`. *(Today: `"account_invoice-5"`, `"item-8"`.)*
- **R5.** Soft-deleted entities (work orders, projects, machines have `is_deleted`) are still found: a soft-deleted row in the workspace yields its label per R1, not the fallback.
- **R6.** [BUG-200] Given `entity_type == "scratch"`, the result is always `"scratch #<entity_id>"`; no lookup is made (no row can match). *(Today: `"scratch-<entity_id>"`.)* ("scratch" as type name — best-practice default, delegated by reviewer.)
- **R7.** Given `entity_type == "inventory"`, the result is `"inventory #<entity_id>"` — no database lookup, regardless of whether an inventory with that id exists. (Already the intended format per Q1.)
- **R8.** Given any other string that is not an attachment-supported type (unknown, empty, or a known type in different case such as `"Purchase_Order"`), the result is the type with every `_` replaced by a space, followed by `" #<entity_id>"` — e.g. `"custom_thing"` → `"custom thing #9"`, `"Purchase_Order"` → `"Purchase Order #3"`, `""` → `" #4"`. Case is kept.
- **R9.** The function never writes to the database (no rows created/changed, nothing flushed).

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| none — unknown types fall back per R8 | — | — |

**Side effects:** none (read-only queries).

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| notification_entity_label.py:32 | `entity_type` is a valid `AttachmentEntityTypeEnum` value → lookup path | R1–R6 |
| notification_entity_label.py:39 | `ValueError` (not an attachment type) → local fallback | R7, R8 |
| notification_entity_label.py:42 | type present in `_ENTITY_TYPE_LABEL` (only `inventory` reachable here) | R7 |
| notification_entity_label.py:42 | type absent from `_ENTITY_TYPE_LABEL` → `_` replaced by space | R8 |
| attachment_manager.py:160 | `entity_type == SCRATCH` → fallback without lookup | R6 |
| attachment_manager.py:197-198 | type not in DAO map → `None` (only SCRATCH, already handled) | R6 |
| attachment_manager.py:199 / BaseDAO & overrides `get_by_id_and_workspace` | row filtered by `id` and `workspace_id`, no soft-delete filter | R1, R3, R5 |
| attachment_manager.py:168 | row is `None` → fallback | R3, R3a |
| attachment_manager.py:207-227 | per-type label field selection | R1 |
| attachment_manager.py:223 | item `sku or name` | R2 |
| attachment_manager.py:228 | unmatched type → `None` (unreachable: all non-scratch types matched) | R4 |
| attachment_manager.py:173 | label falsy (`""`/`None`) → fallback | R4, R4a |
