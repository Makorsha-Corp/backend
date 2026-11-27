# Spec — `app/core/notification_types.py`

> **Status:** APPROVED (2026-11-03; nothing open)
> **Source commit:** e48a092

> **Review round 2026-11-03.** No owner answer in this round. **Delegated:** Q1 decided by Claude under the reviewer's delegation (2026-11-03); it is not the owner's own answer.
>
> **Verified by running** (throwaway script `v_core.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\acctdao\`): the ten values and their lengths (longest 17). **Read, not run:** the frontend type `NotificationKind` (`frontend/src/components/newcomponents/customui/notifications/notificationTypes.ts`), `app/models/notification.py` (`notification_type`, `source_type`: `String(30)`), `ApprovalNotificationService` (the only importer), `NotificationService.create_mention_notifications` (writes `"mention"` and `"discussion"` as literals).

## Review
> All answered; applied 2026-11-03.

### Quick list — all answered
| # | What the code does today, in plain words | Answer | Decided by |
|---|---|---|---|
| Q1 | Two names, "mention" and "discussion", are defined here but the mention code types the same words itself instead of using them | intended — keep both names: they are part of the list the web app relies on; the mention code should use them (tidy-up, not a bug) | Claude, delegated |

No house rule applies (constants; no data, lists or money).

### Q1. "mention" and "discussion" are defined but not used — ✅ intended
**Background:** This file lists the notification kinds and source kinds the web app understands. The approval notifications import their names from here. Mention notifications (`NotificationService`) write the words `"mention"` and `"discussion"` directly, and the notification table's default kind is also the literal `"mention"`.
**What happens today:** `MENTION` and `SOURCE_DISCUSSION` are imported nowhere. The stored words are the same, so nothing a user sees differs.
**Example:** If someone renamed `MENTION` here to `"user_mention"`, mention notifications would still be written as `"mention"`; the two would drift apart without any test noticing.
**Rules affected:** R1, R4
**Suggested answer:** intended — keep both constants (they complete the list matched to the web app's `NotificationKind`); `NotificationService` should import them instead of repeating the words (tidy-up for that module's review, no bug, no ID). Alternative: `remove` them — but the words stay in use, so the list would no longer be complete.
**Answer:** intended
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-03): rules unchanged (R1 ✅, R4 ✅); follow-up FU-1. Not dead code: the values are in use.

## Follow-ups for other reviews
| # | Where it must be looked at | What | Came from |
|---|---|---|---|
| FU-1 | **Notification service** (`app/services/notification_service.py`), **notification model** (`app/models/notification.py`) | Use `MENTION` / `SOURCE_DISCUSSION` instead of the literals `"mention"` / `"discussion"` (service, lines 88 and 91; model default). Tidy-up, no behavior change. | Q1 |

## Overview
Constants naming the kind of a notification (`notifications.notification_type`) and what produced it (`notifications.source_type`). The docstring says the kinds match the web app's `NotificationKind`. Imported by `ApprovalNotificationService` (approval assigned / pending, section confirmation, invoice action). Invariant: every stored kind is one the web app knows, and every value fits the 30-character columns.

**Callables:** 10 specified (constants, in two groups) · 0 not specified
**Externals to mock:** none
**Integration-only behavior:** none

**Notes for the test designer:** `from app.core import notification_types as nt`. Plain value assertions; no database needed. The web app's list for R2: `approval_pending`, `approval_assigned`, `section_confirm`, `invoice_action`, `low_stock`, `project_update`, `maintenance`, `system`, `mention`.

---

## Notification kinds: `APPROVAL_ASSIGNED`, `APPROVAL_PENDING`, `SECTION_CONFIRM`, `INVOICE_ACTION`, `MENTION`
**Shape:** helper (constants) · **Persistence:** pure · **Visibility:** public (used by: `ApprovalNotificationService`; `MENTION` by nothing — Q1)

**Rules:**
- **R1.** ✅ The values are exactly: `APPROVAL_ASSIGNED = "approval_assigned"`, `APPROVAL_PENDING = "approval_pending"`, `SECTION_CONFIRM = "section_confirm"`, `INVOICE_ACTION = "invoice_action"`, `MENTION = "mention"`.
- **R2.** Each kind is one of the web app's `NotificationKind` values (Notes), and the five are pairwise different.
- **R3.** Each value is at most 30 characters (the `notification_type` column), lower-case ASCII letters and `_` only.

---

## Source kinds: `SOURCE_APPROVER`, `SOURCE_ORDER`, `SOURCE_SECTION`, `SOURCE_INVOICE`, `SOURCE_DISCUSSION`
**Shape:** helper (constants) · **Persistence:** pure · **Visibility:** public (used by: `ApprovalNotificationService`; `SOURCE_DISCUSSION` by nothing — Q1)

**Rules:**
- **R4.** ✅ The values are exactly: `SOURCE_APPROVER = "approver"`, `SOURCE_ORDER = "order"`, `SOURCE_SECTION = "section"`, `SOURCE_INVOICE = "invoice"`, `SOURCE_DISCUSSION = "discussion"`; pairwise different.
- **R5.** Each value is at most 30 characters (the `source_type` column), lower-case ASCII letters only.

**Errors:** none · **Side effects:** none

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 3–7 | kind constants | R1, R2, R3 |
| 9–13 | source constants | R4, R5 |
