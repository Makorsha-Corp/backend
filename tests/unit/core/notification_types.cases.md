# Test cases — `app/core/notification_types.py`

> **Spec:** `tests/unit/core/notification_types.spec.md` (source commit e48a092)
> **Status:** READY — the spec is **APPROVED** (2026-11-03; nothing open). Q1 was decided by Claude under the reviewer's delegation.
> **Counts:** 5 cases · 5 expected-to-pass · 0 expected-to-fail (bugs) · 1 deferred

## Reviewer summary
- **Per callable:** notification kinds 3 · source kinds 2 (no bug).
- **Depth:** lighter target (skill step 1a). Ten string constants; no data, no stock, money or order state. One card per rule; the five constants of a group share a card.
- **Notable design choices:** plain value assertions, no database. The web app's `NotificationKind` list is copied from the spec's Notes into Conventions (`WEB_KINDS`); if the web app's list changes, that line must change with it.
- **Needs a decision:** None.

## Conventions for this module

**IDs.** `NTY` = `app/core/notification_types.py`. `K` notification kinds · `S` source kinds.

**Names.**
- `nt` = `from app.core import notification_types as nt`. `re` = the standard module.
- **KINDS** = `[nt.APPROVAL_ASSIGNED, nt.APPROVAL_PENDING, nt.SECTION_CONFIRM, nt.INVOICE_ACTION, nt.MENTION]`.
- **SOURCES** = `[nt.SOURCE_APPROVER, nt.SOURCE_ORDER, nt.SOURCE_SECTION, nt.SOURCE_INVOICE, nt.SOURCE_DISCUSSION]`.
- **WEB_KINDS** = `{"approval_pending", "approval_assigned", "section_confirm", "invoice_action", "low_stock", "project_update", "maintenance", "system", "mention"}`.

**Externals.** None. Nothing is mocked. No database. **Race simulations.** None.

## Notification kinds

### NTY-K-01 — the five kind values are exactly as specified
- **Rules:** kinds R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. Nothing beyond Conventions.

**When**
- `values = KINDS`.

**Then**
1. returns: `nt.APPROVAL_ASSIGNED == "approval_assigned"`.
2. returns: `nt.APPROVAL_PENDING == "approval_pending"`.
3. returns: `nt.SECTION_CONFIRM == "section_confirm"`.
4. returns: `nt.INVOICE_ACTION == "invoice_action"`.
5. returns: `nt.MENTION == "mention"`.

### NTY-K-02 — every kind is one the web app knows, and the five are pairwise different
- **Rules:** kinds R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Nothing beyond Conventions.

**When**
- `values = KINDS`.

**Then**
1. returns: `[v for v in values if v not in WEB_KINDS] == []`.
2. returns: `len(set(values)) == 5`.

### NTY-K-03 — every kind fits 30 characters and uses lower-case ASCII letters and "_" only
- **Rules:** kinds R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Nothing beyond Conventions.

**When**
- `values = KINDS`.

**Then**
1. returns: `[v for v in values if len(v) > 30] == []`.
2. returns: `[v for v in values if not re.fullmatch(r"[a-z_]+", v)] == []`.

## Source kinds

### NTY-S-01 — the five source values are exactly as specified and pairwise different
- **Rules:** sources R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. Nothing beyond Conventions.

**When**
- `values = SOURCES`.

**Then**
1. returns: `nt.SOURCE_APPROVER == "approver"`.
2. returns: `nt.SOURCE_ORDER == "order"`.
3. returns: `nt.SOURCE_SECTION == "section"`.
4. returns: `nt.SOURCE_INVOICE == "invoice"`.
5. returns: `nt.SOURCE_DISCUSSION == "discussion"`.
6. returns: `len(set(values)) == 5`.

### NTY-S-02 — every source fits 30 characters and uses lower-case ASCII letters only
- **Rules:** sources R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Nothing beyond Conventions.

**When**
- `values = SOURCES`.

**Then**
1. returns: `[v for v in values if len(v) > 30] == []`.
2. returns: `[v for v in values if not re.fullmatch(r"[a-z]+", v)] == []`.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| FU-1 — `NotificationService` and the notification model default should use `MENTION` / `SOURCE_DISCUSSION` instead of the literals | notification service spec, notification model | Tidy-up, no behavior change; no card here. |

## Spec gaps
None.

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| kinds | R1 | NTY-K-01 |
| kinds | R2 | NTY-K-02 |
| kinds | R3 | NTY-K-03 |
| sources | R4 | NTY-S-01 |
| sources | R5 | NTY-S-02 |
