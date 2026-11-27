# Future work: subscription payments (SSLCommerz)

Notes collected 2026-11-04, during the unit-testing sweep, for the coming
customer-facing payment portal: a workspace owner picks a plan and pays for it
through SSLCommerz (Bangladesh). The approved specs and their tests are the
reference for how the payment pieces must behave; this file says where they are
and what is still undecided. Nothing here changes a spec.

Conventions: every claim cites its source (`file:line`, BUG / OQ / HR id, or
`spec rule`). "(guess)" marks an unverified guess; "Suggestion:" marks an idea,
not a decision.

---

## Today

**What exists**
- A generic checkout ledger: one `payment_transactions` row per checkout attempt, keyed by a unique `tran_id` (`app/models/payment_transaction.py:25-43`). It knows only "collect `amount` `currency` from `workspace_id`", not why (`app/models/payment_transaction.py:3-7`).
- Statuses: `INITIATED`, `VALIDATED_SUCCESS`, `VALIDATED_FAILED`, `CANCELLED`, `EXPIRED`, `RISK_HOLD` (`app/models/payment_transaction.py:28-35`). Every step is written to an append-only event log `payment_transaction_events` (`payment_transaction_event.spec.md` Overview).
- Endpoints (`app/api/v1/endpoints/payments.py`):
  - `POST /payments/initiate/`: any active member of the workspace; the caller sends `amount`, `currency`, phone (`payments.py:52-66`, `app/schemas/payment_transaction.py:8-18`).
  - `GET /payments/` and `GET /payments/{tran_id}/`: any member sees the workspace's ledger and event history (`payments.py:69-93`).
  - `POST /payments/{id}/resolve-risk/`: workspace owner only, 403 otherwise (`payments.py:96-114`).
  - Public gateway callbacks with no login: `/success`, `/fail`, `/cancel` (browser redirects, 30/minute) and `/ipn` (server-to-server, 60/minute, signature checked first) (`payments.py:122-198`). All redirect the browser to `FRONTEND_BASE_URL/billing/trial?tran_id=…` (`payments.py:139-141`).
  - Mock gateway page and its "complete" action, public, only when `SSLCOMMERZ_MOCK_MODE` is on (`payments.py:203-208`, `215-340`); it can simulate a lost redirect and a high-risk payment (`payments.py:257-258`, `297`).
- Only a mock gateway exists. `get_sslcommerz_client()` returns `MockSSLCommerzClient` when `SSLCOMMERZ_MOCK_MODE` is true and raises `NotImplementedError` otherwise (`app/integrations/sslcommerz/__init__.py:14-25`).
- Settings: `SSLCOMMERZ_MOCK_MODE=True`, `SSLCOMMERZ_STORE_ID=""`, `SSLCOMMERZ_STORE_PASSWORD=""`, `SSLCOMMERZ_SANDBOX=True`, `FRONTEND_BASE_URL`, `BACKEND_BASE_URL` (`app/core/config.py:61-72`). Store id, password and sandbox are read nowhere (`config.spec.md` `Settings` R9).
- The mock signs its tokens with `SECRET_KEY` (HMAC-SHA256) (`mock_client.spec.md` `_sign` R1).
- A reconciliation sweep for transactions no callback ever closed: `scripts/reconcile_payments.py`, "intended to run on a schedule (Railway cron or similar)" (`scripts/reconcile_payments.py:1-11`). The `Procfile` starts only the web process; whether a Railway cron runs the sweep cannot be seen from the repository.

**Plans and limits**
- Three plans are seeded at startup: `free` (default; 3 members, 1 factory, 5 machines, 3 projects, no price), `pro` (99 / 990 USD; 10 members), `enterprise` (299 / 2990 USD; `-1` everywhere = unlimited) (`app/db/seed_default_subscription_plans.py:12-64`). Plan prices are in USD (`seed_default_subscription_plans.py:19`, model default `app/models/subscription_plan.py:22`); a payment defaults to BDT (`app/schemas/payment_transaction.py:11`).
- `-1 means unlimited` is only a comment (`app/models/subscription_plan.py:24`).
- A workspace holds `subscription_plan_id`, `subscription_status` (default `trial`), `trial_ends_at`, `subscription_started_at`, `subscription_ends_at`, `billing_cycle`, `billing_email`, two unused `stripe_*` columns, and six usage counters (`app/models/workspace.py:22-42`).
- A new workspace gets the requested plan if it is active, else the default plan, and a 14-day trial (`app/managers/workspace_manager.py:91-114`).
- Only `max_members` is enforced, when adding a member or inviting (`workspace_manager.py:204-213`, `352-365`). `max_factories`, `max_machines`, `max_projects`, `max_storage_mb`, `max_orders_per_month` are read by no code (`factory_manager.spec.md` Q4 / FU-4; grep of `app/`).
- The usage counters (`current_members_count` …) are never written by any code; only the model default sets them (grep of `app/`).

**The gap for the portal**
- **A successful payment changes nothing on the workspace.** No code sets `subscription_status`, `subscription_plan_id`, `subscription_started_at` or `subscription_ends_at` after `VALIDATED_SUCCESS`; the only writes of `VALIDATED_SUCCESS` are in the payment manager (`app/managers/payment_transaction_manager.py:176`, `244`; grep of `app/` for the workspace fields).
- **Nothing reads the subscription state.** An expired trial or a cancelled subscription does not restrict a workspace (`deps.spec.md` Q3, `get_current_workspace` R10, answered "intended").
- **The amount is whatever the browser sends.** `InitiatePaymentRequest` takes `amount` from the caller and links to no plan (`app/schemas/payment_transaction.py:8-18`).
- **The plan is whatever the creator asks for.** `POST /workspaces/` accepts `subscription_plan_id`, and any active plan is accepted, Enterprise included, with no payment (`app/schemas/workspace.py:18`, `app/services/workspace_service.py:96`, `workspace_manager.py:92-95`). The endpoint text says "Assigns default subscription plan" (`app/api/v1/endpoints/workspaces.py:81`).
- **Deleting a workspace deletes its payment ledger** (`payment_transactions.workspace_id` is `ON DELETE CASCADE`, `app/models/payment_transaction.py:40`).
- `last_ipn_payload` exists on the row but no code writes it (`app/models/payment_transaction.py:67`; grep of `app/`).

## Decided already

**Owner answers**
- **OQ-2:** a plan limit of `-1`, or any negative value, means "no member limit"; neither the invitation check nor the direct add refuses. `None` / `0` keep today's handling until the `workspace_manager` spec decides them. → BUG-1871 (invitation), BUG-1872 (direct add, also reached by accepting an invitation).
- **OQ-3:** one email holds at most one seat. A new invitation to an email with a pending, unexpired invitation in the workspace is refused ("already invited"); accepting an invitation cancels the other pending invitations to that email in the workspace. → BUG-1873, BUG-1874.
- **BUG-1224 (owner, 2026-11-02, subscription plan spec O1):** at most one plan may be both default and active (partial unique index); check the live table for a second default first.
- **Config Q6 / TODO-001 (reviewer):** the mock gateway stays on by default for now. **Before production** the mock must be removed or only be possible outside production; today anyone can approve their own checkout on the mock page (`config.spec.md` Q6, `bugs.md` TODO-001).
- **deps Q3 (reviewer):** `get_current_workspace` does not look at subscription state; this is "intended" for the dependency (`deps.spec.md` Q3). Where enforcement should live instead is open (see below).
- **factory manager Q4 (reviewer, 2026-10-11):** plan limits other than members are "intended for now" not enforced; recorded as a product follow-up (`factory_manager.spec.md` Q4, FU-4).

**House rules that came from the payment spec and bind the portal**
- **HR-10:** a state change on a money row reads it with `SELECT … FOR UPDATE`; the loser of a race gets the normal "wrong state" error (payment spec Q11).
- **HR-11:** only a server-to-server verified gateway result is authoritative. Browser redirects, timeouts and sweeps that find nothing never make a record final; unknown or foreign ids are logged and ignored (payment spec Q5, Q8, Q9).
- **HR-12:** a confirmation missing the amount or currency goes to manual review (`RISK_HOLD`), never to success (payment spec Q6).
- **HR-13:** every call that starts a business process leaves a record, even when the gateway refuses (payment spec Q1).
- **HR-14:** a sweep handles each row on its own; one failure is logged and skipped (payment spec Q14).
- **HR-15:** money rounds half up, everywhere (owner, 2026-10-30; BUG-1040). Applies to any price, proration or tax the portal computes.
- **HR-16:** nothing links across workspaces (applies to the payment event log: BUG-1191).

**Payment spec review answers** (`tests/unit/managers/payment_transaction_manager.spec.md`, all "best-practice default, delegated by reviewer")
- Q1 → BUG-019: a refused checkout start is saved as `INIT_FAILED` with `failed_reason` (fallback `unknown error`), event `initiation_failed`, returned normally, not as 502.
- Q2 → BUG-020: `value_a`..`value_d` are sent to the gateway (also client spec P1).
- Q3 → BUG-021: amounts with more than 2 decimals or 13+ integer digits are refused with 422 before the gateway is called.
- Q4 → BUG-022: currency is upper-cased; only `BDT` and `USD` accepted.
- Q5 → BUG-023: an unknown or foreign `val_id` changes nothing; event `validation_rejected`; a later genuine result still finalizes.
- Q6 → BUG-024: a VALID answer missing amount or currency → `RISK_HOLD`.
- Q7 → BUG-025: a gateway-reported `CANCELLED` is `CANCELLED` on every channel.
- Q8, Q16 → BUG-026: redirect outcomes are unverified (new column `outcome_verified`, default `false`) and a later verified result replaces them.
- Q9 → BUG-027: `EXPIRED` is not final; a later verified result replaces it.
- Q10 → BUG-028: event names follow the documented list (`redirect_success`, `redirect_fail`, `redirect_cancel`, `ipn_received`, …).
- Q11 → BUG-029: resolving a risk hold locks the row.
- Q12 → BUG-030: the sweep maps `FAILED` → `VALIDATED_FAILED`, `CANCELLED` → `CANCELLED`; only "no result" answers become `EXPIRED`.
- Q13 → BUG-031: the sweep looks the payment up by `tran_id` alone.
- Q14, Q17 → BUG-032: one failing row in the sweep is skipped with a `reconciliation_error` event; the error text is `str(exc)` or the exception class name.
- Q15: four new event types adopted: `initiation_failed`, `validation_rejected`, `validated_cancelled`, `reconciliation_error`.

**Mock client and event log answers**
- Mock Q1 → BUG-580: the mock remembers the outcomes it mints, so a `tran_id`-only lookup works.
- Mock Q2 → BUG-581: a malformed `val_id` → `INVALID_TRANSACTION`, never a 500.
- Mock Q3 → BUG-582: a bad `verify_sign` → signature check fails (400), never a 500.
- Mock Q4 → BUG-583: a `val_id` must be in its one canonical form.
- Event log Q1: the payment history reads oldest first, on purpose (`payment_transaction_event.spec.md` Q1, R5).
- Event log HR-6 → BUG-1190 (ties broken by `id`); HR-16 → BUG-1191 (read filtered by workspace).

## Known bugs and gaps that touch it

**Open bugs** (all in `docs/testing/bugs.md`, status open)
- Payment manager: BUG-019, BUG-020, BUG-021, BUG-022, BUG-023, BUG-024, BUG-025, BUG-026, BUG-027, BUG-028, BUG-029, BUG-030, BUG-031, BUG-032.
- Mock gateway: BUG-580, BUG-581, BUG-582, BUG-583.
- Payment event log: BUG-1190 (no tie-break), BUG-1191 (no workspace filter on read).
- Plans: BUG-1224 (two default plans possible; BUG-1212 superseded by it).
- Member limit and seats: BUG-1871, BUG-1872 (`-1` blocks everyone), BUG-1873, BUG-1874 (duplicate invitations hold seats).
- Config (production safety, not payments only): BUG-422 (short `SECRET_KEY` accepted in production; the mock signs with it), BUG-423 (`ENVIRONMENT` not normalised, so a "production" check can be skipped), BUG-424 (`DEBUG` on by default).
- TODO-001: mock gateway on by default with public endpoints.

**Gaps with no bug ID** (found while writing this file; not yet reviewed)
- No real SSLCommerz client (`app/integrations/sslcommerz/__init__.py:20-24`).
- A paid transaction does not activate or extend a plan (see Today).
- Nothing enforces trial end or subscription end (`deps.spec.md` Q3).
- Amount comes from the browser, not from the plan price (`app/schemas/payment_transaction.py:10`).
- A workspace can be created directly on any active plan, unpaid (`workspace_manager.py:92-95`).
- Plan prices are USD; payments default to BDT; no conversion exists (`seed_default_subscription_plans.py:19`, `payment_transaction.py` schema `:11`).
- Only `max_members` is enforced (`factory_manager.spec.md` FU-4).
- The member-limit check is read-then-insert with no lock (`workspace_member.spec.md` FU-2 (b): "HR-10 does not cover plan limits; owner's call").
- Usage counters on `workspaces` are never updated (grep of `app/`).
- Any member can start a checkout and read the whole payment ledger; only risk resolution is owner-only (`payments.py:58-114`).
- The sweep has no visible schedule (`Procfile`; `scripts/reconcile_payments.py:6`).
- The ledger list is ordered by `created_at` only, no `id` tie-break (`app/dao/payment_transaction.py:67`); HR-6 would apply (guess: it will be logged when that DAO is described).
- Deleting a workspace deletes its payment history (`payment_transaction.py:40`).
- Rate limits on the callbacks count per client address; see OQ-7 (boxed) for how that address is read in production.

## Open questions for the feature

Nobody has decided these yet.
- **Plan change.** On `VALIDATED_SUCCESS`, what changes: `subscription_plan_id`, `subscription_status` (which values: `trial`, `active`, `past_due`, `cancelled`?), `subscription_started_at`, `subscription_ends_at`, `billing_cycle`? In the same database transaction as the payment?
- **Which payment is for what.** How a transaction records the plan and period it pays for: `value_a`..`value_d` (as the model suggests, `payment_transaction.py:4-7`), or new columns?
- **Price source.** The server must compute the amount from the plan (guess: yes, never trust the browser). Monthly vs yearly; what currency is charged (plans are USD, SSLCommerz checkout usually BDT (guess)); who sets the exchange rate, and HR-15 rounding of the result.
- **Who may pay.** Owner only, or any member (today any member, `payments.py:58`)? Who may see the ledger? (Overlaps with the permissions feature.)
- **Upgrade / downgrade.** Mid-period upgrade: prorate or start a new period? Downgrade when the workspace is above the smaller plan's limits (e.g. 8 members on a 3-member plan)?
- **Renewal.** SSLCommerz hosted checkout is one payment per session (guess: no stored-card auto-renewal in this integration). Manual renewal reminders? Grace period after `subscription_ends_at`?
- **Expiry enforcement.** What happens when a trial or subscription ends: read-only, blocked, or fall back to `free`? Where is it enforced, given `get_current_workspace` deliberately does not (`deps.spec.md` Q3)?
- **Plan creation at workspace creation.** Should `POST /workspaces/` still accept `subscription_plan_id`, or always start on the default plan / a trial?
- **Other limits.** Enforce `max_factories`, `max_machines`, `max_projects`, `max_storage_mb`, `max_orders_per_month` (`factory_manager.spec.md` FU-4)? With what message and status? Does `-1` mean unlimited for all of them (OQ-2 decided it for members only)?
- **`max_members` of `0` or `None`.** Left open by BUG-1871.
- **Concurrent seat check.** Lock the member-limit check (HR-10 style), or accept a rare overshoot (`workspace_member.spec.md` FU-2 (b))?
- **Refunds.** No refund flow or status exists. Needed? Through SSLCommerz's refund API or by hand?
- **Invoices / receipts.** Does the customer get a receipt or VAT invoice for the subscription? (Separate from the workspace's own customer invoices.)
- **Ledger retention.** Should payment history survive workspace deletion (today it cascades)?
- **Real client details.** Sandbox vs live URLs, `SSLCOMMERZ_SANDBOX` handling, timeouts and retries, IPN source checks, how `verify_signature` works for the real gateway.
- **Mock in production.** TODO-001: remove the mock or guard it before the portal goes live.
- **Sweep schedule.** Who runs `scripts/reconcile_payments.py`, how often?
- **Return page.** All callbacks redirect to `/billing/trial` (`payments.py:140`); the portal will need its own result page.
- **Plan admin.** Plans are only seeded; no API writes them (`bugs.md` BUG-1224 "No API writes plans"). Who edits prices and limits, and do existing subscribers keep their old price?

## What the tests already pin down

These approved specs are the reference for intended behaviour. Each has a cases file, a test file and a verify report with verdict PASS. Rules tagged `[BUG-…]` describe the intended behaviour; their tests are expected to fail until the bug is fixed.

**SSLCommerz client contract**: `tests/unit/integrations/client.spec.md` (+ `client.cases.md`, `test_client.py`, `client.verify.md`, PASS)
- `InitSessionRequest` R1: holds values as given, no conversion. R1a [BUG-020]: optional `value_a`..`value_d`. R2: `product_name` "Workspace Subscription", `product_category` "subscription" by default. R3: missing field / unknown keyword → `TypeError`. R3a: the `value_*` fields stay optional. R4: equality, mutable.
- `InitSessionResult` R1–R4: only `status` required; `session_key`, `gateway_page_url`, `failed_reason` default `None`; any status string accepted.
- `ValidationResult` R1–R4: `status` and `tran_id` required; nine optional fields (`val_id`, `amount`, `currency`, `risk_level`, `risk_title`, `bank_tran_id`, `card_type`, `verify_sign`, `verify_key`); no conversion.
- `SSLCommerzClient` (abstract): `init_session` R1–R3, `validate` R1–R2, `query_by_tran_id` R1–R2, `verify_signature` R1–R2. A real client must implement all four methods; the base methods raise `NotImplementedError`.
- Overview: business logic only ever gets a client through `get_sslcommerz_client()`; `verify_signature` is a cheap first check and "never a substitute for `validate`".

**Mock gateway**: `tests/unit/integrations/mock_client.spec.md` (+ cases, `test_mock_client.py`, verify PASS)
- `_sign` R1–R4: HMAC-SHA256 with `SECRET_KEY` over `status|tran_id|amount|currency|risk_level`.
- `init_session` R1–R3: always `SUCCESS`; deterministic `session_key`; page URL `BACKEND_BASE_URL + API_V1_STR + /payments/mock-gateway/<tran_id>`.
- `build_val_id` R1–R5: signed, deterministic token; R6 [BUG-580]: remembers the outcome per `tran_id`, latest wins.
- `_decode_val_id` R1–R6: rejects missing dot, bad base64/JSON, bad signature; R3a/R3b [BUG-583] canonical form only; R5/R6 [BUG-581] never raises.
- `validate` R1–R7: invalid token → `INVALID_TRANSACTION` with empty `tran_id`; R1a/R1b [BUG-581] never raises; `risk_title` "Risky" when `risk_level == 1`; same answer on every call; the form built from a result passes `verify_signature`.
- `query_by_tran_id` R1–R5: no record → `UNATTEMPTED`; R1a, R3a, R4 [BUG-580] answer from the record, ignore bad or foreign hints; R5 [BUG-581] never raises.
- `verify_signature` R1–R5: missing `verify_sign` or signed field → `False`; R4 [BUG-582] never raises.
- These rules describe the mock only. A real client needs its own spec (see below); the mock is to be removed or fenced off (TODO-001).

**Payment transactions**: `tests/unit/managers/payment_transaction_manager.spec.md` (+ cases, `test_payment_transaction_manager.py`, verify PASS round 3, 172 cases)
- `_log_event` R1–R2: one event row per call, copies the transaction's workspace.
- `_generate_tran_id` R1–R4: 26 lowercase hex characters, unique across all workspaces, 5 tries then 500.
- `initiate_payment`:
  - R1: the session request carries the four callback URLs (`BACKEND_BASE_URL + API_V1_STR + /payments/success|fail|cancel|ipn`); R1a [BUG-020] also `value_a`..`value_d`.
  - R2: name/email fall back to the profile.
  - R3, R5a, R7a [BUG-019]: refusal → `INIT_FAILED` row + `initiation_failed` event, no exception.
  - R4: a gateway exception writes nothing. R5, R6: the `INITIATED` row and `initiated` event. R7: no deduplication. R8: unknown workspace fails at flush.
  - R9, R9a [BUG-021]: amount > 0, at most 2 decimals, at most 13 integer digits.
  - R10, R10a [BUG-022]: currency default `BDT`, upper-cased, only `BDT`/`USD`.
- `_apply_validation_result`:
  - R1, R1a, R2, R2a [BUG-023]: foreign or unknown `val_id` rejected, nothing changes.
  - R3: gateway fields copied. R4: non-valid status → `VALIDATED_FAILED`. R4a, R4b [BUG-025]: gateway `CANCELLED` → `CANCELLED`.
  - R5: amount mismatch → `VALIDATED_FAILED`. R7: currency mismatch → `VALIDATED_FAILED`. R6, R8 [BUG-024]: missing amount/currency → `RISK_HOLD`.
  - R9: `risk_level == 1` → `RISK_HOLD`. R10: otherwise `VALIDATED_SUCCESS`.
  - R11: does not check the current status. R12 [BUG-026]: sets `outcome_verified = true`.
- `finalize_from_gateway` (redirect with `val_id`, IPN):
  - R1, R2: found by `tran_id` across workspaces, row locked; unknown → 404.
  - R3: a verified outcome is final, `duplicate_ignored`. R3a [BUG-026]: unverified outcomes are replaced. R3b [BUG-027]: `EXPIRED` is replaced. R3c [BUG-025].
  - R4, R4a [BUG-028]: received event, then one gateway `validate` call. R5, R5a: second callbacks. R6: a gateway error rolls back. R7: only three source labels.
- `mark_terminal_without_validation` (redirect without `val_id`, cancel): R1–R4; R3a [BUG-026] unverified; R3b [BUG-028] event names.
- `resolve_risk`: R1–R6; R2 only from `RISK_HOLD`; R3a keeps the verified marker; R6a [BUG-029] row lock. (The owner-only check lives in the endpoint, `payments.py:108-110`, not covered by a spec.)
- `reconcile_stuck_transactions`:
  - R1–R3: only `INITIATED` rows older than the cutoff, oldest first, re-locked.
  - R4, R4a [BUG-031]: lookup by `tran_id` alone. R5, R5a [BUG-030], R5b [BUG-023]: how answers are applied. R6: `EXPIRED`.
  - R7: each candidate once. R8 [BUG-032]: one failure is isolated. R9: cutoff arithmetic. R10: works across workspaces.
- Overview invariants: once verified, an outcome never changes (except risk resolution); only the gateway's server-to-server answer marks success; amount and currency must match; every attempt leaves an event.

**Payment event log**: `tests/unit/dao/payment_transaction_event.spec.md` (+ cases, test, verify PASS)
- `get_by_payment_transaction` R1–R8: R2 [BUG-1191] filtered by workspace; R5 oldest first (Q1, intended); R6 [BUG-1190] `id` tie-break; R7 no cap.
- FU-1: `PaymentTransactionService.get_transaction_by_tran_id` must pass `workspace_id` once BUG-1191 is fixed.

**Plans and limits**
- `tests/unit/dao/subscription_plan.spec.md` (+ cases, test, verify PASS): `get_default_plan` R1–R4 (active default only, else `None`); R5 [BUG-1224] one default-and-active plan, enforced by index. `get_by_name` is dead code, to be removed (Q1).
- `tests/unit/dao/workspace.spec.md` (+ cases, test, verify PASS): `get_by_slug` R1–R5 (exact, no subscription check); model facts: `subscription_status` default `trial`, plan FK with no delete action.
- `tests/unit/dao/workspace_member.spec.md` (+ cases, test, verify PASS): `count_active_members` R1–R2 (only `status == 'active'` counts; the owner counts); FU-2 (plan limits, OQ-2, no lock).
- `tests/unit/dao/workspace_invitation.spec.md` (+ cases, test, verify PASS): `count_pending_invitations` R1–R2 (one per row, so two invitations to one email count 2, see OQ-3); `get_pending_invitations` R1–R2 (expired means `expires_at <= now`); FU-1 (OQ-3), FU-2 (expiry boundary differs by one microsecond in `validate_invitation_for_user`).
- `tests/unit/core/deps.spec.md` `get_current_workspace` R10: subscription state not checked (intended, Q3).
- `tests/unit/managers/factory_manager.spec.md` `create_factory` R9: `max_factories` not checked (intended for now, Q4).

**Config**: `tests/unit/core/config.spec.md` (+ cases, `test_config.py`, verify PASS)
- `Settings` R4: SSLCommerz defaults (`MOCK_MODE=True`, empty store id/password, `SANDBOX=True`, base URLs). R9: store id/password/sandbox read nowhere.
- Module import guard R4: `SSLCOMMERZ_MOCK_MODE` is never checked, even in production (Q6, TODO-001). R3 [BUG-422]: production refuses a short `SECRET_KEY`.

**No spec yet: write the reference tests here when these modules are reached**
- `app/api/v1/endpoints/payments.py`: the owner-only risk check, callback form handling (`Missing tran_id` 400), IPN signature 400, the redirect target, the mock-gateway pages and their 404 when mock mode is off.
- `app/services/payment_transaction_service.py`: commit/rollback around each manager call, response shaping (`failed_reason` per BUG-019), `workspace_id` passed to the event read (FU-1 / BUG-1191).
- `app/dao/payment_transaction.py`: `get_by_tran_id_for_update` (lock), workspace-scoped reads, `get_stuck_initiated`, list order (`:67`, see gaps).
- `app/schemas/payment_transaction.py`: where BUG-021 and BUG-022 are fixed (amount and currency validation).
- `app/integrations/sslcommerz/__init__.py`: `get_sslcommerz_client()` (mock vs `NotImplementedError`, one shared instance).
- A real SSLCommerz client (not written yet): it should meet the `client.spec.md` contract and the behaviour the manager spec expects of `validate` / `query_by_tran_id`.
- `app/managers/workspace_manager.py`: plan assignment on creation, member limit (BUG-1871…1874), and where the plan change after payment will probably live (guess).
- `app/services/workspace_service.py`, `app/api/v1/endpoints/workspaces.py`: `subscription_plan_id` on creation.
- `app/db/seed_default_subscription_plans.py`: idempotent by name; its docstring says it commits, but the code only flushes (`:80-99`).
- `app/schemas/subscription_plan.py`, `app/schemas/workspace.py` plan fields.
- `scripts/reconcile_payments.py`: commits at the end (manager spec Overview); BUG-032 also touches it.

## Ideas for later

All suggestions, not decisions.
- Suggestion: a `subscription` record (or a set of workspace columns) changed only by a verified `VALIDATED_SUCCESS`, inside the same locked database transaction (HR-10, HR-11), and never by a redirect.
- Suggestion: the client sends a plan id and a billing cycle, and the server works out the amount and currency. `value_a` carries `plan:<id>;cycle:<monthly|yearly>`, which the client spec example already uses (`client.spec.md` P1 example).
- Suggestion: only the owner (perhaps also a billing role) can start a checkout and see the ledger. Decide this together with the permissions feature.
- Suggestion: a startup guard that refuses `SSLCOMMERZ_MOCK_MODE=True` in production, as config Q6's suggested answer proposed (TODO-001).
- Suggestion: the real client gets its own spec and tests against the `client.spec.md` contract, with a recorded sandbox exchange as fixtures.
- Suggestion: one shared "check plan limit" helper for all six limits, with `-1` (or any negative value) meaning unlimited (OQ-2) and one message format ("Workspace has reached maximum … limit (N). Upgrade subscription …", `workspace_manager.py:211-212`).
- Suggestion: keep the payment ledger when a workspace is deleted (soft-delete the workspace, or `SET NULL` and keep the rows), for accounting.
- Suggestion: run the reconciliation sweep on a schedule that can be seen from the repository (Railway cron entry or a documented setup).
- Suggestion: `GET /subscription-plans/`, a public, read-only list of active plans for the pricing page (none exists today, BUG-1224 "No API writes plans").
- Suggestion: retire the unused `stripe_customer_id` / `stripe_subscription_id` columns (`app/models/workspace.py:32-33`), or rename them for SSLCommerz.
- Suggestion: fill the usage counters (`current_*`) or drop them and count live; today they are stale defaults.

## Added during the sweep

- 2026-11-04, `workspace_manager` spec (`tests/unit/managers/workspace_manager.spec.md`, read, not run):
  - **Raised to the owner (this module must decide now):** OQ-16 (spec Q1), a new workspace can start on any active plan, Enterprise included, unpaid. The suggested answer is that the default plan is always used and other plans come only through a verified payment. OQ-17 (spec Q2): `max_members = 0` today means no limit, and the suggested answer is that `0` is a real limit. BUG-1988 and BUG-1989 are reserved for them. OQ-2 / OQ-3 are now spec rules: `add_member_to_workspace` R5a (BUG-1872), `create_invitation` R4 (BUG-1873), R8 (BUG-1871), and `accept_invitation` R5 (BUG-1874; the other invitations are cancelled with an `invitation_cancelled` audit row, reason `superseded`).
  - Confirmed in code: `POST /workspaces/` accepts any active plan without payment (`workspace_manager.py:92-95`). The web app never sends `subscription_plan_id` (`frontend/src/pages/newpages/WorkspaceSelectorPage.tsx:228-232`), so only direct API calls can do this.
  - Confirmed in code: only `max_members` is enforced, in two places (`workspace_manager.py:204-213` add, `352-365` invite). The invite check counts active members plus pending unexpired invitations; the add / accept check counts active members only.
  - `None` limit cannot happen: `max_members` is NOT NULL, and a workspace's plan always exists (FK NOT NULL, no delete action). An **inactive** plan is still enforced for the workspaces on it.
  - A removed member who comes back takes a seat again only when they accept (BUG-1982: their old row is reactivated after the seat check).
  - Every new workspace gets `subscription_status = 'trial'` and `trial_ends_at` = now + 14 days, **free plan included** (`workspace_manager.py:113`). Registration's message says "created successfully with 14-day trial" (`auth_service.py`). The portal must say what a trial means on the free plan and what happens when it ends.
  - `billing_email` is stored as given, with no email check (`app/schemas/workspace.py:19`). At registration it is the account's email. If receipts go to it, validate it (and lower-case it, OQ-1).
  - The seat check is read-then-insert with no lock. Two invitations sent at once can overshoot by one seat. Still open (see "Concurrent seat check" above); not asked now, because a plan change through the portal is the first place a lock really matters.
  - Suggestion: put the plan change after `VALIDATED_SUCCESS` in `WorkspaceManager` (a new method, e.g. `apply_paid_plan`). It would write an audit row (`plan_changed`, metadata old / new plan, payment `tran_id`) like the other workspace actions here, and refuse a downgrade below the current active members + pending invitations (the same count as the invite check).
- 2026-11-04, owner answers on the `workspace_manager` spec:
  - **OQ-16 (plan at creation): left for the portal.** The spec keeps today's behaviour (any active plan is accepted at `POST /workspaces/`, unpaid) in its own rule, `create_workspace_with_owner` R1, marked *pending the payment portal (OQ-16)*. No bug; BUG-1988 is unused. The portal must decide whether creation still accepts `subscription_plan_id`; only that rule's cards then change.
  - **OQ-17 (`max_members = 0`): bug, deferred** → BUG-1989. Owner: "we need to go over what the plans will be in future… figure out how to combine plans and subscriptions later." **Plans and subscriptions need combining in the portal design:** what a plan's limits mean (`0`, negative, the five unenforced limits), how a subscription (status, period, trial) ties a workspace to a plan, and how a paid plan change updates both. The spec rules (`add_member_to_workspace` R6, `create_invitation` R9) keep today's behaviour until then.
- 2026-11-04, workspace_manager tests (the reference for plans, seats and limits: `tests/unit/managers/test_workspace_manager.py`, header explains how to read it; P16 / P17 sections hold the pending OQ-16 / OQ-17 behaviour):
  - Inviting counts active members (owner included) plus pending invitations with `expires_at > now`, this workspace only; adding or accepting counts active members only. Suspended and removed members, and accepted, cancelled or expired invitations, take no seat; an invitation expiring exactly at now frees its seat.
  - An inactive plan's limit is still enforced. Every plan gets a 14-day trial at creation, and the owner gets no seat check.
  - Open for the portal: the seat check has no lock (two invites at once can both pass), and nothing covers lowering a limit below the current member count (downgrade path).

- 2026-11-04, `attachment_manager` spec: plans carry `max_storage_mb` (free 1000, pro 10000, enterprise -1) but nothing reads it: uploads check only 10 MB per file and 25 attachments per record (`MAX_ATTACHMENTS_PER_ENTITY`, one global setting, not per plan). Pending uploads never confirmed and failed uploads keep files in Cloudinary (BUG-2099; no clean-up job, attachment manager FU-3), and phone staging files can be left behind (mobile spec). For the portal: decide whether storage is a plan limit, what counts (ready files only?), and add the clean-up first so the count is honest.
- 2026-11-04, attachment family tests: for storage quotas, failed uploads still take one of a record's 25 places (BUG-1434) and keep their Cloudinary file (BUG-2099); a phone upload to a missing record moves the file then crashes, leaving an orphan (BUG-2133/2134). Clean these up before counting storage.

- 2026-11-04, attachment / mobile upload service specs (storage): three more ways the Cloudinary storage and the database drift apart, to fix before storage is counted per plan. A phone attach that fails verification after the file was moved leaves the file at an id no row names (BUG-2204). Deleting an attachment, cancelling a QR session or re-signing on the phone deletes the Cloudinary file before the change is saved, so a failed save leaves a row pointing at a file that is gone (BUG-2202, BUG-2205). A storage count should be built from rows only after these and the clean-up job (attachment manager FU-3, mobile FU-2) exist.
- 2026-11-04, `workspace_service` spec: any signed-in user may create any number of workspaces (`POST /workspaces/`), each on the plan of their choice today (OQ-16) and each with a 14-day `trial`; nothing limits workspaces per account. `PATCH /workspaces/{id}/` lets the owner change `billing_email` (unchecked string); BUG-2253 records such edits in the audit log. For the portal: decide whether workspaces per account are limited and whether `billing_email` must be a verified email.
- 2026-11-05, `workspace_service` spec: `billing_email` (on `POST /workspaces/` and `PATCH /workspaces/{id}/`) is a plain string with no email format check and, today, no length check (over 255 characters gives a 500, BUG-2256). Before the portal sends receipts or invoices to it, validate it as an email (and decide whether it must be verified).
- 2026-11-05, attachment / mobile service tests: the pattern for external side effects is now pinned by tests (`tests/unit/services/test_attachment_service.py` D-15…D-20, `test_mobile_upload_service.py` CN-10/11, PS-09…11): the external call runs only after the commit succeeds, a failed commit never triggers it, and its error is logged as a WARNING and swallowed. Reuse it for SSLCommerz voids, refunds and any payment-gateway call. Don't reuse the QR bearer-token pattern for payment links without an expiry and single use.

- 2026-11-06, financial audit log specs: the log covers accounts, invoices and invoice payments only. Subscription payments (SSLCommerz `payment_transactions`) have their own event table and write nothing here. If the portal wants one money history per workspace, either write a `financial_audit_logs` row on `VALIDATED_SUCCESS` / refund (entity_type `subscription_payment`) or keep the two apart on purpose; decide before building a billing history page.
- 2026-11-09, template / audit log tests: a subscription-payment audit trail on `financial_audit_log` would need BUG-2370 (id tie-break) and BUG-2372 (UTC timestamps) fixed first; `get_related_logs` follows one level only, so an account does not see its invoices' payments.
- 2026-11-09, `payment_transaction` DAO spec (`tests/unit/dao/payment_transaction.spec.md`, run on the test database, rolled back) — the reference for the ledger reads:
  - **Raised to the owner:** OQ-25 (not blocking). The sweep only re-checks `INITIATED` rows; a payment closed by an unverified redirect (`CANCELLED` / `VALIDATED_FAILED` with `outcome_verified = false`) or `EXPIRED` is never asked about again, so a lost IPN leaves a paid customer recorded as not paid. Suggested: re-check those for 72 hours. Rule `get_stuck_initiated` R7 keeps today's behaviour until answered.
  - The ledger list (`GET /payments/`) now has a fixed order: `created_at` newest first, then `id` descending (BUG-2402; the gap noted above as "ordered by `created_at` only"). The sweep's batch: `initiated_at` oldest first, then `id` ascending (BUG-2403).
  - The database has its own `now()` defaults on `initiated_at`, `created_at`, `updated_at` (local time, not in the model); a row written outside the model would be swept early or late (BUG-2401).
  - BUG-029's lock (risk resolution) cannot be a plain `FOR UPDATE`: the lookup outer-joins the initiator's profile and Postgres refuses it (0A000, verified). It must lock `OF payment_transactions`; specified as a new `for_update=True` keyword on `get_by_id_and_workspace_with_initiator` (R5). Any new portal read that joins profiles and needs a lock has the same constraint.
  - Facts for the portal: `tran_id` is unique across all workspaces (two unique indexes, one redundant); the database checks neither `status` nor `amount` (any text, negative amounts are stored), so only the schema and the manager keep them valid. The list has no status or date filter; a billing-history page that needs "paid only" or a period would need one (with `id` in its order).
- 2026-11-09, `invoice_payment` DAO spec: customer invoice payments are a separate ledger from SSLCommerz `payment_transactions` (as noted 2026-11-06). Their `created_at` is the database's local clock (BUG-2400); a combined money history per workspace would need both fixed to UTC first (with BUG-2401).
- 2026-11-10, OQ-25 (owner: decide in the portal work): the payment sweep only re-checks INITIATED payments; one closed as cancelled/failed by an unconfirmed redirect, or EXPIRED, is never re-asked, so a lost IPN can leave a paying customer unpaid. Suggested: re-check those for 72 h, only a verified gateway answer changes the outcome (needs BUG-026's `outcome_verified`). Tests pin today's behaviour in PTX-OQ25 cards.

- 2026-11-10, auth service spec: registration (`POST /auth/register/` with a workspace name) always starts the new workspace on the default plan with a 14-day `trial` and `billing_email` = the account's email as typed (lower-cased after BUG-1861); it never passes a plan id, so OQ-16 does not reach it. `AuthService` holds `subscription_plan_dao` and never uses it. The slug is derived from the name (BUG-2566, BUG-2567). Account-only registration creates no workspace, so no plan or trial until the user creates one through `POST /workspaces/`.
- 2026-11-10, money DAO tests: risk resolution needs `with_for_update(of=PaymentTransaction)` (BUG-029; a plain lock is refused because of the outer join to profiles). Ledger list and reconciliation sweep need an id tie-break (BUG-2402/2403). DB defaults for time columns should be `timezone('utc', now())` (BUG-2400/2401). Portal invoice/receipt numbers should use the UTC year, be unique per workspace and skip a taken number; today's order/delivery/return numbering gets all three wrong (BUG-726, 2440, 2420…2422, 2426…2428). Reference test: `tests/unit/dao/test_payment_transaction.py` (card → code table at the top).
- 2026-11-10, payment_transaction verify: risk resolution's lock must be exactly `FOR UPDATE OF payment_transactions` (no `SKIP LOCKED`, no `NOWAIT`: a second resolver must wait and get the normal 400, HR-10). The `…with_initiator` reads return a positional pair; nothing pins `initiated_by_name`, so callers must not rely on it.
- 2026-11-14, order DAO verify: any number parser for portal invoices / receipts must accept only `^[0-9]+$` suffixes (today `int()` accepts `1_000`, `+9`, Arabic-Indic or Bengali digits; BUG-2676 family).

- 2026-11-21, invoice payment and payment transaction service reviews — **idempotency decided** (BUG-3002 and BUG-3023, pattern `missing-idempotency-key`, [OQ-61](../testing/owner-questions.md)): the client sends a fresh `Idempotency-Key` per payment / "Pay" form; it is compared exactly and stored per workspace under a partial unique index on `(workspace_id, idempotency_key)` over non-null keys. A repeat returns the first result and writes nothing (even if that result has since changed state: voided, paid, `INIT_FAILED`; a new attempt needs a new key); a different body gets 409 `This idempotency key was already used for a different payment`; a lost index race is answered as a repeat or 409, never 500; no key behaves as today. For checkout the key is checked **before** the gateway call, so a repeat opens no second SSLCommerz session. The portal's subscription checkout uses the same rule ([invoice payment spec](../../tests/unit/services/invoice_payment_service.spec.md) R9–R9e, [payment transaction spec](../../tests/unit/services/payment_transaction_service.spec.md) R7–R7e).
- 2026-11-21, invoice payment review: if the re-read after a successful commit fails (TC5), the caller gets an error for a saved payment and will likely retry; with the key, that retry returns the saved payment (BUG-3002, [OQ-61](../testing/owner-questions.md)). Portal failures after the commit should rely on the same guarantee.
- 2026-11-21, payment transaction review — **order of calls**: both gateway calls (open session, validate `val_id`) run before the commit, once each. Applying the plan, receipts, notifications and refunds must run after the commit, once per change, never on `duplicate_ignored` or a repeated key; a failure is logged and ignored (spec Overview, "Payment-flow contract"). Any receipt or email on invoice payments follows the same rule.
- 2026-11-21, payment transaction review — gateway errors (spec Q4): the real SSLCommerz client should raise its own error type, mapped to 502/503 "payment gateway unavailable, try again"; today an outage is a plain 500.
- 2026-11-21, payment transaction review — redirects: if the service fails during `/payments/success`, `/fail` or `/cancel`, the customer sees a JSON error page; the portal should always redirect back to the billing page with an error flag. The public redirect endpoints let anyone holding a `tran_id` add `duplicate_ignored` events (about 30 a minute per IP); consider not saving an event for repeats from unverified redirects, or limiting it per `tran_id`.
- 2026-11-21, locks: callbacks use a plain `FOR UPDATE`; risk resolution `FOR UPDATE OF payment_transactions` (BUG-029), both held until the service commits. The invoice payment lock is a plain `FOR UPDATE` on `account_invoices`; any lock on a read that joins the recorder's profile must be `FOR UPDATE OF invoice_payments`.
- 2026-11-21, numbering: `tran_id` is an opaque 26-character hex key, matched exactly; invoice payments have no number. `^[0-9]+$` applies to future receipt and invoice numbers only.
- 2026-11-21, patterns to reuse: payments are voided, never deleted (BUG-609) — portal refunds keep the record and mark it reversed. Invoice void locks, then cancels every payment and releases the linked order in one commit (`account_invoice_service` X2–X8; BUG-2962 adds the order lock before the checks) — portal refunds and cancellations should lock the payment row first, check state, change payment, subscription and plan in one transaction, and make any external call after the commit.
- 2026-11-21, still open: OQ-25 — the sweep never re-checks a payment closed by an unverified redirect, or one marked `EXPIRED`. The ledger will show `failed_reason` and `outcome_verified` (BUG-3022); the frontend types need them (BUG-3024).
- 2026-11-22, purchase order service spec ([spec](../../tests/unit/services/purchase_order_service.spec.md); OQ-63 → BUG-3176): new non-cash payment method `payment_method = 'settled_by_replacement'`.
  - Written by the system when a PO `replace` return's replacements are received; it links to its receipt (new nullable source column on `invoice_payments`).
  - It can never be deleted or edited, only voided with a reason.
  - Payment reports, gateway reconciliation and any portal listing of payments must treat it as non-cash (no gateway transaction, no cash movement) and must not offer delete or edit.
  - `payment_method` is free text today (`String(50)`; the comment lists cash, bank_transfer, cheque, card), so the allowed values should become a fixed list.
  - The sales twin (OQ-64 → BUG-3217) adds the same method for sales replacements, linked to the delivery.
- 2026-11-22, sales service spec ([spec](../../tests/unit/services/sales_service.spec.md)):
  - Nothing in this module goes through SSLCommerz.
  - Sales return credit notes are payable invoices with `allow_payments = True`, payable at once. Worth a look if customer refunds ever go through the portal.
- 2026-11-22, work order service spec ([spec](../../tests/unit/services/work_order_service.spec.md)): nothing relevant to payments or the portal.
- 2026-11-22, purchase order and sales service fill-gaps: both settlement twins link the system-made payment through new columns `invoice_payments.source_type` / `source_id` (`purchase_order_event` / `sales_order_event`). `settled_by_replacement` is reserved: the payments API refuses it on create and update (400), and a settlement skips the `allow_payments` refusal because it isn't cash. The payment audit description still reads "Payment of $X", an existing wording issue.
