# Test cases — `app/services/order_hub_stats_helpers.py`

> **Spec:** `tests/unit/services/order_hub_stats_helpers.spec.md` (source commit e48a092)
> **Status:** READY
> **Revision:** 2 (2026-11-04) — from `order_hub_stats_helpers.verify.md` finding 1 (money scale). Changed: OHS-P-01 (new Then 7, `str(result.total_amount) == "1234.50"`), OHS-E-01 (amount `Decimal("99.90")`, new Then 8, `str(result.total_amount) == "99.90"`). No other card maps a money value (P-03 and E-02 check it is `None`). No card added or retired.
> **Counts:** 19 cases · 19 expected-to-pass · 0 expected-to-fail (bugs) · 0 deferred

## Reviewer summary
- **Per callable:** `purchase_order_to_recent_summary` 6 · `expense_order_to_recent_summary` 4 · `transfer_order_to_recent_summary` 5 · `pending_highlight_from_dict` 4.
- **Depth:** lighter target (skill step 1a): four pure mappers, no session, no decision beyond "status loaded or not". One full-mapping card per mapper, one "optional fields absent" card, one card per R4 / R2 refusal shape.
- **Expected-to-fail:** none; the spec has no bug.
- **Notable design choices:**
  - Orders are **unsaved model instances** (spec Facts): no database row, no flush. The `db` fixture is not needed.
  - Every id-like input has its own value (11, 4, 21, 31 …) and `created_at` differs from `updated_at`, so a field copied from the wrong source fails.
  - `total_amount` is checked as the same `Decimal` (HR-15: no rounding, no float).
  - Error cards assert only `ValidationError`; the spec gives no message text.
- **Needs a decision:** None. One small gap (model import paths), see Spec gaps.

## Conventions for this module

**IDs.** `OHS` = `app/services/order_hub_stats_helpers.py`. `P` purchase_order_to_recent_summary · `E` expense_order_to_recent_summary · `T` transfer_order_to_recent_summary · `H` pending_highlight_from_dict.

**Imports.** `from app.services.order_hub_stats_helpers import purchase_order_to_recent_summary, expense_order_to_recent_summary, transfer_order_to_recent_summary, pending_highlight_from_dict`. `OrderHubRecentSummary`, `OrderHubPendingHighlight` (`app.schemas.order_hub`). `PurchaseOrder` (`app.models.purchase_order`), `ExpenseOrder` (`app.models.expense_order`), `TransferOrder` (`app.models.transfer_order`), `Status` (`app.models.status`). `ValidationError` (`pydantic`). `Decimal` (`decimal`); `date`, `datetime` (`datetime`).

**Fixed values.** T1 = `datetime(2026, 5, 1, 9, 30, 0)`. T2 = `datetime(2026, 5, 3, 14, 0, 0)`. `result` = what the When call returns.

**Given rows.** Every order is an **unsaved** model instance built with keyword arguments exactly as the card writes them; nothing is added to a session. A status is an unsaved `Status(id=…, name=…)` assigned to the order's `current_status` attribute when the card says so. No card uses the `db` fixture.

**Named checks.**
- `raises: ValidationError` = `with pytest.raises(ValidationError):` around the When call.
- **none of (fields)** = each named attribute of `result` `is None`; one Then line lists them, one assertion per field.

**Externals.** None.

**Race simulations.** None.

## `purchase_order_to_recent_summary`

### OHS-P-01 — every field of a full purchase order is mapped
- **Rules:** `purchase_order_to_recent_summary` R1, R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. `S = Status(id=4, name="Draft")`.
2. `O = PurchaseOrder(id=11, po_number="PO-0011", current_status_id=4, created_at=T1, updated_at=T2, account_id=21, invoice_id=31, total_amount=Decimal("1234.50"))`.
3. `O.current_status = S`.

**When**
- `result = purchase_order_to_recent_summary(O)`.

**Then**
1. returns: `isinstance(result, OrderHubRecentSummary)`.
2. returns: `result.id == 11`, `result.order_number == "PO-0011"`, `result.status_id == 4`.
3. returns: `result.status_name == "Draft"`.
4. returns: `result.created_at == T1`, `result.updated_at == T2`.
5. returns: `result.account_id == 21`, `result.invoice_id == 31`.
6. returns: `result.total_amount == Decimal("1234.50")`, `isinstance(result.total_amount, Decimal)`.
7. returns: `str(result.total_amount) == "1234.50"`.

### OHS-P-02 — a purchase order leaves the expense and transfer fields empty
- **Rules:** `purchase_order_to_recent_summary` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. `S = Status(id=4, name="Draft")`.
2. `O = PurchaseOrder(id=11, po_number="PO-0011", current_status_id=4, created_at=T1, updated_at=T2, account_id=21, invoice_id=31, total_amount=Decimal("1234.50"))`.
3. `O.current_status = S`.

**When**
- `result = purchase_order_to_recent_summary(O)`.

**Then**
1. returns: none of (`expense_category`, `expense_date`, `due_date`, `source_location_type`, `destination_location_type`).

### OHS-P-03 — no status loaded: status_name is None, status_id still the order's
- **Rules:** `purchase_order_to_recent_summary` R1, R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `O = PurchaseOrder(id=12, po_number="PO-0012", current_status_id=6, created_at=T1)`; `current_status` is not set.

**When**
- `result = purchase_order_to_recent_summary(O)`.

**Then**
1. returns: `result.status_name is None`.
2. returns: `result.id == 12`, `result.order_number == "PO-0012"`, `result.status_id == 6`, `result.created_at == T1`.
3. returns: none of (`updated_at`, `account_id`, `invoice_id`, `total_amount`).

### OHS-P-04 — no created_at is refused
- **Rules:** `purchase_order_to_recent_summary` R4; Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. `O = PurchaseOrder(id=13, po_number="PO-0013", current_status_id=4)`; `created_at` not passed.

**When**
- `purchase_order_to_recent_summary(O)`.

**Then**
1. raises: `ValidationError`.

### OHS-P-05 — a None po_number is refused
- **Rules:** `purchase_order_to_recent_summary` R4; Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. `O = PurchaseOrder(id=14, po_number=None, current_status_id=4, created_at=T1)`.

**When**
- `purchase_order_to_recent_summary(O)`.

**Then**
1. raises: `ValidationError`.

### OHS-P-06 — a None current_status_id is refused
- **Rules:** `purchase_order_to_recent_summary` R4; Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. `O = PurchaseOrder(id=15, po_number="PO-0015", current_status_id=None, created_at=T1)`.

**When**
- `purchase_order_to_recent_summary(O)`.

**Then**
1. raises: `ValidationError`.

## `expense_order_to_recent_summary`

### OHS-E-01 — every field of a full expense order is mapped; status is fixed and location fields are empty
- **Rules:** `expense_order_to_recent_summary` R1, R2, R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. `O = ExpenseOrder(id=22, expense_number="EXP-0022", created_at=T1, updated_at=T2, account_id=23, invoice_id=33, total_amount=Decimal("99.90"), expense_category="other", expense_date=date(2026, 5, 10), due_date=date(2026, 5, 20))`.

**When**
- `result = expense_order_to_recent_summary(O)`.

**Then**
1. returns: `isinstance(result, OrderHubRecentSummary)`.
2. returns: `result.id == 22`, `result.order_number == "EXP-0022"`.
3. returns: `result.status_id == 0`, `result.status_name is None`.
4. returns: `result.created_at == T1`, `result.updated_at == T2`.
5. returns: `result.account_id == 23`, `result.invoice_id == 33`, `result.total_amount == Decimal("99.90")`.
6. returns: `result.expense_category == "other"`, `result.expense_date == date(2026, 5, 10)`, `result.due_date == date(2026, 5, 20)`.
7. returns: none of (`source_location_type`, `destination_location_type`).
8. returns: `str(result.total_amount) == "99.90"`.

### OHS-E-02 — a minimal expense order: optional fields are None
- **Rules:** `expense_order_to_recent_summary` R1, R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `O = ExpenseOrder(id=24, expense_number="EXP-0024", created_at=T1)`.

**When**
- `result = expense_order_to_recent_summary(O)`.

**Then**
1. returns: `result.id == 24`, `result.order_number == "EXP-0024"`, `result.status_id == 0`, `result.created_at == T1`.
2. returns: none of (`status_name`, `updated_at`, `account_id`, `invoice_id`, `total_amount`, `expense_category`, `expense_date`, `due_date`).

### OHS-E-03 — no created_at is refused
- **Rules:** `expense_order_to_recent_summary` R4; Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. `O = ExpenseOrder(id=25, expense_number="EXP-0025")`; `created_at` not passed.

**When**
- `expense_order_to_recent_summary(O)`.

**Then**
1. raises: `ValidationError`.

### OHS-E-04 — a None expense_number is refused
- **Rules:** `expense_order_to_recent_summary` R4; Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. `O = ExpenseOrder(id=26, expense_number=None, created_at=T1)`.

**When**
- `expense_order_to_recent_summary(O)`.

**Then**
1. raises: `ValidationError`.

## `transfer_order_to_recent_summary`

### OHS-T-01 — every field of a full transfer order is mapped
- **Rules:** `transfer_order_to_recent_summary` R1, R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. `S = Status(id=5, name="In Transit")`.
2. `O = TransferOrder(id=41, transfer_number="TR-0041", current_status_id=5, created_at=T1, updated_at=T2, source_location_type="storage", destination_location_type="machine")`.
3. `O.current_status = S`.

**When**
- `result = transfer_order_to_recent_summary(O)`.

**Then**
1. returns: `isinstance(result, OrderHubRecentSummary)`.
2. returns: `result.id == 41`, `result.order_number == "TR-0041"`, `result.status_id == 5`.
3. returns: `result.status_name == "In Transit"`.
4. returns: `result.created_at == T1`, `result.updated_at == T2`.
5. returns: `result.source_location_type == "storage"`, `result.destination_location_type == "machine"`.

### OHS-T-02 — a transfer order leaves money and expense fields empty
- **Rules:** `transfer_order_to_recent_summary` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. `S = Status(id=5, name="In Transit")`.
2. `O = TransferOrder(id=41, transfer_number="TR-0041", current_status_id=5, created_at=T1, updated_at=T2, source_location_type="storage", destination_location_type="machine")`.
3. `O.current_status = S`.

**When**
- `result = transfer_order_to_recent_summary(O)`.

**Then**
1. returns: none of (`account_id`, `invoice_id`, `total_amount`, `expense_category`, `expense_date`, `due_date`).

### OHS-T-03 — no status loaded: status_name is None
- **Rules:** `transfer_order_to_recent_summary` R1, R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `O = TransferOrder(id=42, transfer_number="TR-0042", current_status_id=7, created_at=T1)`; `current_status` is not set.

**When**
- `result = transfer_order_to_recent_summary(O)`.

**Then**
1. returns: `result.status_name is None`.
2. returns: `result.id == 42`, `result.order_number == "TR-0042"`, `result.status_id == 7`, `result.created_at == T1`.
3. returns: none of (`updated_at`, `source_location_type`, `destination_location_type`).

### OHS-T-04 — no created_at is refused
- **Rules:** `transfer_order_to_recent_summary` R4; Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. `O = TransferOrder(id=43, transfer_number="TR-0043", current_status_id=5)`; `created_at` not passed.

**When**
- `transfer_order_to_recent_summary(O)`.

**Then**
1. raises: `ValidationError`.

### OHS-T-05 — a None transfer_number is refused
- **Rules:** `transfer_order_to_recent_summary` R4; Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. `O = TransferOrder(id=44, transfer_number=None, current_status_id=5, created_at=T1)`.

**When**
- `transfer_order_to_recent_summary(O)`.

**Then**
1. raises: `ValidationError`.

## `pending_highlight_from_dict`

### OHS-H-01 — a full dict becomes the highlight; an extra key is ignored; an ISO string becomes a datetime
- **Rules:** `pending_highlight_from_dict` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. `data = {"id": 51, "order_number": "PO-0051", "status_name": "Pending approval", "created_at": "2026-05-01T09:30:00", "total_amount": "5.00"}`.

**When**
- `result = pending_highlight_from_dict(data)`.

**Then**
1. returns: `isinstance(result, OrderHubPendingHighlight)`.
2. returns: `result.id == 51`, `result.order_number == "PO-0051"`.
3. returns: `result.status_name == "Pending approval"`.
4. returns: `result.created_at == T1`.
5. returns: `not hasattr(result, "total_amount")`.

### OHS-H-02 — only the required keys: the optional fields are None
- **Rules:** `pending_highlight_from_dict` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `data = {"id": 52, "order_number": "TR-0052"}`.

**When**
- `result = pending_highlight_from_dict(data)`.

**Then**
1. returns: `result.id == 52`, `result.order_number == "TR-0052"`.
2. returns: none of (`status_name`, `created_at`).

### OHS-H-03 — a missing id is refused
- **Rules:** `pending_highlight_from_dict` R2; Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. `data = {"order_number": "PO-0053", "status_name": "Draft"}`.

**When**
- `pending_highlight_from_dict(data)`.

**Then**
1. raises: `ValidationError`.

### OHS-H-04 — a None order_number is refused
- **Rules:** `pending_highlight_from_dict` R2; Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. `data = {"id": 54, "order_number": None}`.

**When**
- `pending_highlight_from_dict(data)`.

**Then**
1. raises: `ValidationError`.

## Deferred to other specs
None.

## Spec gaps
| # | Where | What is missing | How it blocked the design |
|---|---|---|---|
| 1 | Facts | The import modules of `PurchaseOrder`, `ExpenseOrder`, `TransferOrder` are not given (only `Status`'s, `app.models.status`). | Not blocking: Conventions use `app.models.purchase_order`, `app.models.expense_order`, `app.models.transfer_order`, the paths the existing unit tests import. Describer to confirm. |

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `purchase_order_to_recent_summary` | R1 | OHS-P-01, OHS-P-03 |
| `purchase_order_to_recent_summary` | R2 | OHS-P-01, OHS-P-03 |
| `purchase_order_to_recent_summary` | R3 | OHS-P-02 |
| `purchase_order_to_recent_summary` | R4; Errors | OHS-P-04, OHS-P-05, OHS-P-06 |
| `expense_order_to_recent_summary` | R1 | OHS-E-01, OHS-E-02 |
| `expense_order_to_recent_summary` | R2 | OHS-E-01, OHS-E-02 |
| `expense_order_to_recent_summary` | R3 | OHS-E-01 |
| `expense_order_to_recent_summary` | R4; Errors | OHS-E-03, OHS-E-04 |
| `transfer_order_to_recent_summary` | R1 | OHS-T-01, OHS-T-03 |
| `transfer_order_to_recent_summary` | R2 | OHS-T-01, OHS-T-03 |
| `transfer_order_to_recent_summary` | R3 | OHS-T-02 |
| `transfer_order_to_recent_summary` | R4; Errors | OHS-T-04, OHS-T-05 |
| `pending_highlight_from_dict` | R1 | OHS-H-01, OHS-H-02 |
| `pending_highlight_from_dict` | R2; Errors | OHS-H-03, OHS-H-04 |
