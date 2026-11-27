# Questions waiting for the owner

Questions the test pipeline could not settle under the reviewer's delegation,
because they touch money, stock, the order workflow, or a security / access
decision that changes who can see or do what. Each one lists the facts from the
code, a suggested answer and the alternatives. Answer on the **Answer:** line;
the describer then applies it (`apply-review`) to the spec named.

**Blocking** means a spec stays IN REVIEW until it is answered. **Not blocking**
means the item was found while reading a module's callers; it is a rule of a
module not yet described, and its spec will ask it again.

---

## OQ-1. Should an email identify an account whatever its capital letters? — blocking

**Module:** `app/dao/profile.py` — spec `tests/unit/dao/profile.spec.md` Q1 (IN REVIEW). Also reaches `AuthService` (register, login, password reset).
**Kind:** security / access (who can log in, and whether one person can hold two accounts).
**Facts from the code:**
- `profile_dao.get_by_email` is an exact comparison (`Profile.email == email`); login (`authenticate`), registration's "already registered" check and password reset all use it.
- The database's unique index on `profiles.email` is exact.
- Pydantic `EmailStr` lowers only the domain: `Ann.Lee@Example.COM` is stored `Ann.Lee@example.com`.
- Verified on the test database: `Ann.Lee@example.com` and `ann.lee@example.com` register as two accounts; logging in as `ANN.LEE@example.com` fails with "Invalid email or password".
- Invitations are stored lower-cased and accepted case-insensitively; the waitlist lower-cases emails. Profiles are the only place that does not.
- Whether production already holds case-variant pairs is unknown: `SELECT lower(email), count(*) FROM profiles GROUP BY 1 HAVING count(*) > 1`.

**Suggested answer:** bug — an email identifies one account whatever its capitals. `get_by_email` compares `lower(trim(email))`; registration stores the email lower-cased; a unique index on `lower(email)` replaces the exact one; a script lists any existing case-variant pairs for you to merge or close by hand (no automatic merge: each has its own password and workspaces).
**Alternatives:**
- (a) intended — keep exact matching as today.
- (b) only login and the "already registered" check become case-insensitive; existing pairs stay; no new index. Smaller, but an existing pair then cannot log in predictably.

**Answer:** owner, 2026-11-04: suggested answer (ignore capitals; store lower-cased; unique index on lower(email); script lists existing pairs for manual merge). → BUG-1860, BUG-1861, BUG-1862

---

## OQ-2. "Unlimited" plans (`max_members = -1`) cannot add anyone — not blocking

**Module:** `app/managers/workspace_manager.py` (`add_member_to_workspace`, `create_invitation`); found while describing `app/dao/workspace_member.py` (spec FU-2).
**Kind:** money (plan limits).
**Facts from the code:**
- `app/models/subscription_plan.py:24` says "-1 means unlimited"; the seeded Enterprise plan has `max_members = -1` (and -1 for storage, orders, factories, machines, projects).
- Both checks are `if plan and plan.max_members:` then `count >= plan.max_members`. `-1` is truthy, and any count is `>= -1`.
- Verified on the test database: on a plan with `max_members = -1`, both an invitation and a direct add are refused with "Workspace has reached maximum member limit (-1). Upgrade subscription to add more members."
- The other `-1` limits were not checked here; each is read by its own module.

**Suggested answer:** bug — `-1` (and, to be safe, any negative value) means no member limit: neither check refuses.
**Alternatives:** (a) `-1` is not meant to be used; change the seed to a large number instead. (b) intended (Enterprise workspaces add members some other way).

**Answer:** owner, 2026-11-04: suggested answer (-1, or any negative value, means no member limit; neither check refuses). → BUG-1871, BUG-1872 (logged for the future `workspace_manager` spec)

---

## OQ-3. Two open invitations to one email take two seats — not blocking

**Module:** `app/managers/workspace_manager.py` (`create_invitation`); found while describing `app/dao/workspace_invitation.py` (spec FU-1).
**Kind:** money (plan limits).
**Facts from the code:**
- The seat check is `active members + pending, unexpired invitations >= max_members`; `count_pending_invitations` counts rows, one per invitation.
- `create_invitation`'s docstring says "Email not already invited (pending)", but nothing checks it.
- Verified on the test database: on a 3-seat plan, the owner plus two invitations to `a@x.com` block a third invitation to anyone.
- Accepting one invitation leaves the other pending, and counted, until it expires (3 days after sending).

**Suggested answer:** bug — a new invitation to an email that already has a pending, unexpired invitation in the workspace is refused ("already invited"), so each email holds at most one seat; accepting an invitation cancels any other pending invitation to the same email in that workspace.
**Alternatives:** (a) allow re-sending, but the new invitation replaces the old one (old one set to `cancelled`). (b) keep both, but count distinct emails, not rows. (c) intended.

**Answer:** owner, 2026-11-04: suggested answer (refuse a new invitation while one to that email is pending and unexpired, 'already invited'; accepting one cancels the others in that workspace). → BUG-1873, BUG-1874 (logged for the future `workspace_manager` spec)

---

## OQ-4. Any member can change the workspace's permission table — not blocking

**Module:** `app/api/v1/endpoints/access_control.py`, `app/services/access_control_service.py`; found while describing `app/dao/access_control.py` (spec FU-1).
**Kind:** security / access.
**Facts from the code:**
- `POST`, `PUT`, `DELETE /access-control/…` require only `get_current_workspace` (an active membership): a `ground-team` member can create, change or delete permission rows of the workspace.
- Nothing in the backend reads `access_control` to allow or refuse a request. If the web app uses these rows to decide which pages to show, a member can grant themselves pages (the API behind those pages has its own checks).
- The same `type` + `target` + `role` can be stored twice.

**Suggested answer:** bug — only the workspace owner may create, change or delete permission rows (403 for anyone else); any member may still read them.
**Alternatives:** (a) owner and managers may change them. (b) intended — the table is advisory.

**Answer:** owner, 2026-11-04: suggested answer (only the workspace owner may create, change or delete permission rows, 403 otherwise; any member may read). → BUG-1875 (logged for the future `access_control_service` / endpoint spec)

## OQ-5. Private projects: any member can see their attachments and discussions — not blocking

**Module:** attachment service FU-1 (a), discussion service FU-1 (b); found while describing `tests/unit/dao/attachment.spec.md` and `discussion.spec.md` (2026-11-03).
**Facts:** on a private project, any workspace member can list its attachments and read or post its discussions. Nothing checks who may see the record.
**Suggested answer:** bug — attachments and discussions follow the record's own visibility; a member who cannot open the private project gets 404.
**Alternatives:** (a) intended — attachments and discussions are workspace-wide.
**Same case, help tickets (added 2026-11-04):** any member can read and post on the discussion of any help ticket (`support_ticket`), though only its creator and the owner/ground-team-manager may open the ticket itself (`tests/unit/services/discussion_service.spec.md` Q2; read in the code, not run). The suggested answer above covers it: the discussion follows the ticket's visibility.
**Same case, calendar (added 2026-11-04):** `GET /calendar/events` shows every project of the workspace to every member: name, start date, end date, deadline, status and the first 120 characters of its description, private projects included (verified on `marker_test`). The project pages hide a private project from members who may not open it (owner, privileged roles, its creator, its members). Rule `_collect_projects` R6 of `tests/unit/services/calendar_service.spec.md`, written to today's behavior, *pending OQ-5*. If the suggested answer stands, the calendar shows a private project only to those who may open it (the service then needs the caller's user id).

**Answer:** owner, 2026-11-04: suggested answer (attachments, discussions and calendar entries follow the record's own visibility; a member who cannot open the private project or help ticket gets 404 / does not see it). → BUG-1867 (discussions of private projects and their components), BUG-1868 (help ticket discussions), BUG-1869 (calendar), BUG-1870 (attachments; logged for the future attachment service spec). Applied 2026-11-04 to `discussion_service.spec.md` and `calendar_service.spec.md`; recorded in the attachment and discussion DAO specs (no DAO rule changes). Follow-ups 2026-11-04: recorded in `attachment_link.spec.md` FU-1 (a); mentions on such records skip people who cannot open them → BUG-1879 (decided by Claude as a consequence of this answer).

## OQ-6. A member removed from the workspace stays a planned worker on open work orders — not blocking

**Module:** work order assignee FU-1 (a); found while describing `tests/unit/dao/work_order_assignee.spec.md` (2026-11-03).
**Facts:** removing a member leaves their assignee rows on open work orders. The precedents removed such people: approvers (BUG-1201) and project members (BUG-1280).
**Suggested answer:** bug — removing a member takes them off open work orders' assignees, with an event; completed orders keep their record.
**Alternatives:** (a) intended — someone reassigns by hand.

**Answer:** owner, 2026-11-04: suggested answer (removing a member takes them off open work orders' assignees, with an event; completed orders keep their record). → BUG-1883 (logged for the future `workspace_manager` spec; recorded in work order assignee DAO FU-1)

## OQ-7. Does production tell the server which proxy to trust? Login rate limits may be shared by everyone — not blocking

**Module:** `app/core/limiter.py` — spec `tests/unit/core/limiter.spec.md` P1 (APPROVED: the module is right; this is about the production server). Found while describing it (2026-11-03).
**Kind:** security / access (protection of login, registration, password reset and the public upload pages against floods and guessing).
**Facts:**
- Rate limits (login 10 per minute, registration and forgot-password 5, and others) count requests per address of whoever connects to the server. The audit-logger review already decided that "the client address" is the one the server's trusted-proxy handling gives, never a raw `X-Forwarded-For` header.
- `scripts/railway_start.sh` starts `uvicorn` without `--forwarded-allow-ips`. Uvicorn then trusts the forwarded address only from `127.0.0.1`, unless the `FORWARDED_ALLOW_IPS` environment variable is set on Railway, which the repository cannot show.
- If it is not set and Railway's proxy connects from another address, every user arrives with the proxy's address: one person's 10 logins in a minute block login for the whole company for the rest of that minute, and a password guesser is not slowed down any more than everyone else.
- Counters are kept in the server's memory: each running copy of the API counts on its own, and a restart clears them.
**Suggested answer:** check Railway's variables; if `FORWARDED_ALLOW_IPS` is missing, set it (for Railway, `*` is the usual value, because the app can only be reached through its proxy) or add `--forwarded-allow-ips` to `scripts/railway_start.sh`.
**Alternatives:** (a) it is already set — nothing to do. (b) Key the limits on something else as well (e.g. the e-mail being logged into), so a shared address cannot lock out everyone.

**Answer:** owner, 2026-11-04: set aside for later (boxed). Not blocking.

## OQ-8. Can an owner or manager rewrite what another member wrote to support? — blocking

**Module:** `app/services/help_ticket_service.py` — spec `tests/unit/services/help_ticket_service.spec.md` Q1 (IN REVIEW). The rule lives in `app/managers/help_ticket_manager.py` (`can_access_ticket`, used for both reading and changing a ticket).
**Kind:** security / access (who may change a ticket).
**Facts from the code:**
- A help ticket is a member's message to the platform's support team. `owner` and `ground-team-manager` see every ticket of their workspace; every other member sees only their own; platform admins see all.
- Whoever may see a ticket may also change it: title, description, category, and close / reopen. The ticket keeps no record of who changed the text (only of who closed it).
- The web app offers only Close / Reopen; changing the text is possible through the API alone (`PATCH /help/tickets/{id}`).
- Verified on the test database: a `ground-team-manager` replaced the title and description of a ticket a `ground-team` member opened (200).

**Suggested answer:** bug — only the ticket's creator may change its title, description and category; owner, ground-team-manager and platform admins may still close and reopen any ticket they can see. A text change by anyone else answers 403 "You do not have access to this help ticket.".
**Alternatives:**
- (a) intended — managers may tidy up tickets.
- (b) nobody may change the text after the ticket is opened; only close / reopen.

**Answer:** owner, 2026-11-04: suggested answer (only the creator edits title/description/category; owner, ground-team-manager and admins may still close/reopen). → BUG-1863

## OQ-9. Is the waitlist's bot check switched on in production? — not blocking

**Module:** `app/services/waitlist_service.py` — spec `tests/unit/services/waitlist_service.spec.md` (APPROVED; `verify_turnstile` R1). Found while describing it (2026-11-04).
**Kind:** security / access (protection of the public waitlist form against bots).
**Facts:**
- The public `POST /waitlist` checks a Cloudflare Turnstile token only when `TURNSTILE_SECRET_KEY` is set. With the setting empty (its default), every submission is accepted without a check; the code's comment says this is meant "until TURNSTILE_SECRET_KEY is set".
- What remains without it: the hidden "website" field that catches simple bots, and 5 submissions a minute per client address (`app/core/limiter.py`; see OQ-7 on how that address is read in production).
- Whether Railway sets `TURNSTILE_SECRET_KEY` (and the frontend's `VITE_TURNSTILE_SITE_KEY`) cannot be seen from the repository.

**Suggested answer:** check Railway's variables; if the key is missing, set both keys (setup in `landingPage/docs/LANDING_WAITLIST.md`, in the landing page repository).
**Alternatives:** (a) it is already set — nothing to do. (b) Make the server refuse signups (503) when it runs in production without the key, so a missing setting cannot silently turn the check off.

**Answer:** owner, 2026-11-04: set aside for later (boxed). Not blocking.

## OQ-10. Old work orders that point at another workspace's project component: stuck, or carry on without the log entry? — blocks `work_order_manager` only

**Module:** `app/managers/work_order_manager.py` (`_consume_item`, `finalize_completion`; no spec yet), which waits for you anyway. Found while describing `tests/unit/managers/project_component_activity_manager.spec.md` Q1. That module is not blocked: `log_event` refusing the foreign component is settled by HR-16 / BUG-1192, and the question is only how the work order manager reacts (2026-11-04).
**Kind:** order workflow (whether a work order can be started and completed).
**Facts from the code (read, not run):**
- Using stock on a work order and completing it write an entry to its project component's activity log through `log_event`.
- BUG-1016 (your rule, 2026-10-30) stops new work orders from naming another workspace's component. Orders saved before that fix may already do so; `scripts/find_cross_workspace_rows.py` lists them (`work_orders.project_component_id -> project_components`).
- BUG-1192 (house rule HR-16) makes `log_event` refuse such a component with 404 `Project component with ID <id> not found`. Nothing earlier in the work order flow checks the component, so starting such an order with stock lines, adding a stock line once started, and completing it would all fail and roll back. A started order's component cannot be changed (structural fields are locked), so it would stay in progress.
- For machines this did not come up: an order with another workspace's machine already stops at start today.

**Suggested answer:** `log_event` still refuses; the work order manager writes no component log entry when the order's component is not in the order's workspace, and the step goes on. The bad links are repaired by hand from the audit script's list.
**Alternatives:** (a) refuse: the step fails with the 404 until the link is fixed in the data. (b) refuse with a message naming the work order ("Work order WO-0412 has an invalid project component; contact support").

**Answer:** owner, 2026-11-04: suggested answer (log_event still refuses; the work order manager writes no component log entry when the order's component is not in the order's workspace, and the step goes on; bad links repaired by hand from the audit script's list). → BUG-1884 (logged for the future `work_order_manager` spec)

## OQ-11. Removing your stamp can delete any image the company stores in Cloudinary — blocking

**Module:** `app/managers/profile_stamp_manager.py` — spec `tests/unit/managers/profile_stamp_manager.spec.md` Q1 (IN REVIEW). Reached through `PATCH /auth/me/` (`AuthService.update_current_user`).
**Kind:** security / access (who can delete stored files).
**Facts from the code (read, not run):**
- A saved image stamp is sent by the browser as `{"kind": "image", "public_id", "url", "width", "height"}`. The server checks only that `public_id` is 1–512 characters, not that it is the name it signed for this user (`profiles/<user id>/stamp-<random>`).
- Removing the stamp, or replacing it with another image, deletes the stored `public_id` from Cloudinary as an authenticated image. Attachment images are stored the same way, and the attachment API shows their `public_id` to every workspace member.
- So any logged-in user can save another file's `public_id` as their stamp, remove the stamp, and the server deletes that file. No role or attachment permission is checked.

**Suggested answer:** bug — an image stamp is accepted only if its `public_id` starts with the user's own stamp prefix (`profiles/<user id>/stamp-`, with the environment prefix outside production); otherwise 400 and nothing saved. The delete only ever touches such a `public_id`, so stamps already stored with a foreign id can be removed without deleting the foreign file.
**Alternatives:** (a) keep a list of ids signed per user and accept only those. (b) never delete from Cloudinary on removal; clean up with a periodic job.

**Answer:** owner, 2026-11-04: suggested answer (accept and delete only public_ids under the user's own profiles/<id>/stamp- prefix; else 400). → BUG-1864, BUG-1865

## OQ-12. A stamp picture can point at any web address, loaded on colleagues' screens — blocking

**Module:** `app/managers/profile_stamp_manager.py` — spec `tests/unit/managers/profile_stamp_manager.spec.md` Q2 (IN REVIEW).
**Kind:** security / access (what other members' browsers are made to load).
**Facts from the code (read, not run):**
- The image stamp's `url` is stored as sent: any text of 1–2048 characters, not checked to be a Cloudinary address or to match `public_id`.
- Listing an attachment's markups sends each author's saved stamp, `url` included (`AttachmentMarkupManager._resolve_saved_stamp`), so every member who opens that attachment loads the address, telling that server their IP address and when they looked.

**Suggested answer:** bug — the server builds the stamp's `url` from the accepted `public_id` (our Cloudinary delivery address, authenticated, as attachments do), or refuses a `url` that is not `https://res.cloudinary.com/<our cloud>/…` for that `public_id` with 400.
**Alternatives:** (a) intended — stamps are personal and the risk is small. (b) only require the `https://res.cloudinary.com/<our cloud>/` prefix.

**Answer:** owner, 2026-11-04: suggested answer (server builds the stamp url from the accepted public_id). → BUG-1866

## OQ-13. A status spelled like a purchase stage in other capitals can stop the stage being created — not blocking

**Module:** `app/services/status_service.py` — spec `tests/unit/services/status_service.spec.md` `update_status` R4b, gap G4 (APPROVED; added 2026-11-04 by fill-gaps).
**Kind:** order workflow (how purchase stages are found by name).
**Facts from the code (read, not run):**
- The purchase order code finds each stage's status by its exact name (`Draft`, `Planning`, `Receiving`, `Complete`: `purchase_order_manager`, `ensure_po_stage_statuses`, `dao/purchase_order`), and creates a missing one with that exact name.
- BUG-1221 (owner O3) will make status names unique per workspace ignoring capitals and outer spaces. BUG-1220 protects rows named exactly like a stage; the status spec now matches stage names exactly, as the order code does.
- So in a workspace that has no `Receiving` row (an old workspace, or seeded data) but has a status `receiving`, the next stage seeding tries to create `Receiving`, the unique index refuses it, and purchase orders of that workspace can no longer reach the stage. Today's seeding creates all four stages with every workspace, so it needs old or hand-made data.

**Suggested answer:** the order code finds stage rows ignoring capitals and outer spaces (the same comparison as BUG-1221), and BUG-1220 protects them the same way; a migration renames any such row to the exact stage name.
**Alternatives:** (a) intended as specified — exact names only; old data is repaired by hand if it ever occurs. (b) keep exact matching in the order code but have the stage seeding reuse a case-different row instead of inserting.

**Answer:** owner, 2026-11-04: suggested answer (the order code finds stage rows ignoring capitals and outer spaces, as BUG-1221; BUG-1220 protects them the same way; a migration renames such rows to the exact stage name). → BUG-1880 (status service, applied to `update_status` R4b), BUG-1881 (order code lookups), BUG-1882 (migration)

## OQ-14. Voided work orders still appear on the calendar — not blocking

**Module:** `app/services/calendar_service.py` — spec `tests/unit/services/calendar_service.spec.md` `_collect_work_orders` R3 (APPROVED; added 2026-11-04).
**Kind:** which orders count.
**Facts from the code (work orders verified on `marker_test`, the rest read):**
- The calendar hides voided purchase orders and expense orders, voided invoices and payments, cancelled deliveries and cancelled production batches.
- Work orders are hidden only when deleted. A voided work order (status `VOIDED`) keeps showing its planned date and end date, with `status: VOIDED` in the event's details.
- Drafts are shown for every kind of order and invoice. That looks deliberate (planned work belongs on a calendar) and is not part of this question.

**Suggested answer:** bug — a voided work order is hidden from the calendar, like voided purchase and expense orders; drafts, in-progress and completed work orders stay.
**Alternatives:** (a) intended — a voided work order stays visible so people can see what was planned and dropped (the frontend could grey it out using the status).

**Answer:** owner, 2026-11-04: suggested answer (a voided work order is hidden from the calendar; drafts, in-progress and completed stay). → BUG-1876 (applied to calendar `_collect_work_orders` R3)

## OQ-15. Work and sales orders of a deleted factory still appear on the calendar — not blocking

**Module:** `app/services/calendar_service.py` — spec `tests/unit/services/calendar_service.spec.md` `_collect_work_orders` R4, `_collect_sales_orders` R3 (APPROVED; added 2026-11-04).
**Kind:** which orders count.
**Facts from the code (read, not run):**
- Work orders and sales orders each belong to a factory. A factory is soft-deleted (the row stays).
- Projects and production batches of a deleted factory are hidden from their lists (BUG-1446; BUG-1330, your rule of 2026-11-02), and now from the calendar too (BUG-1806, BUG-1807).
- The calendar does not look at the factory of work orders or sales orders, so their dates keep showing after the factory is deleted. How the work order and sales order pages treat a deleted factory's orders has not been described yet.

**Suggested answer:** follow the order pages: whatever the work order and sales order lists decide for a deleted factory's orders, the calendar does the same. Until those lists are described, keep showing them (orders are business records with money and stock attached).
**Alternatives:** (a) hide them from the calendar now, as projects and batches. (b) always show them: an order is history, unlike a project or batch plan.

**Answer:** owner, 2026-11-04: alternative (a), hide them now: work and sales orders of a deleted factory are hidden from the calendar, like projects and batches. → BUG-1877 (work orders), BUG-1878 (sales orders) (applied to calendar `_collect_work_orders` R4, `_collect_sales_orders` R3)

## OQ-16. A new workspace can start on any plan, Enterprise included, without paying — blocking

**Module:** `app/managers/workspace_manager.py` — spec `tests/unit/managers/workspace_manager.spec.md` Q1 (IN REVIEW). Reached through `POST /workspaces/` (`WorkspaceService.create_workspace`).
**Kind:** money (which plan a customer gets without paying). The coming SSLCommerz portal depends on it (`docs/future/subscription-payments.md`).
**Facts from the code (read, not run):**
- `WorkspaceCreate` has an optional `subscription_plan_id` (`app/schemas/workspace.py:18`). `create_workspace_with_owner` uses it whenever it is given and not `0`, if the plan exists and is active (`workspace_manager.py:92-95`); otherwise it uses the default plan (`free`).
- Seeded plans: `free` (default, 3 members, no price), `pro` (99 USD/month, 10 members), `enterprise` (299 USD/month, unlimited). Nothing is charged at creation, and no payment changes a plan later (the portal is not built).
- The web app never sends `subscription_plan_id` (`frontend/src/pages/newpages/WorkspaceSelectorPage.tsx:228-232`), and registration passes none, so only a direct API call can pick a plan.
- Every new workspace gets `subscription_status = 'trial'` and `trial_ends_at` = now + 14 days, whatever the plan. Nothing reads either one (deps spec Q3).

**Suggested answer:** bug — a new workspace always starts on the default plan. A `subscription_plan_id` that is not the default plan's id is refused with 400 "A new workspace starts on the default plan. Choose a paid plan from billing after it is created." and nothing is written. No id, or the default plan's own id, works as today. Other plans are reached only through a verified payment (the portal). The web app is unaffected.
**Alternatives:** (a) silently ignore the field and always use the default plan. (b) Accept only plans with no price. (c) intended until the portal exists.

**Answer:** owner, 2026-11-04: leave it for the payment portal work. Tests describe today's behaviour (any active plan accepted), kept in its own cards so the portal decision changes only those. Noted in docs/future/subscription-payments.md. No bug (BUG-1988 stays unused). Applied 2026-11-04 to `workspace_manager.spec.md` Q1, `create_workspace_with_owner` R1.

## OQ-17. A plan with `max_members = 0` has no member limit — blocking

**Module:** `app/managers/workspace_manager.py` — spec `tests/unit/managers/workspace_manager.spec.md` Q2 (IN REVIEW). Left open by your OQ-2 answer ("`None` / `0` keep today's handling until the spec decides them").
**Kind:** money (plan limits).
**Facts from the code (read, not run):**
- Both seat checks (adding a member, inviting) start with `if plan and plan.max_members:` (`workspace_manager.py:205`, `353`). `0` is false, so a `0` plan has no limit at all.
- `None` cannot happen: `max_members` is NOT NULL, and a workspace's plan always exists (the FK is NOT NULL and has no delete action). So `0` is the only open case.
- The member count includes the owner. No seeded plan uses `0`, and no API writes plans.

**Suggested answer:** bug — `0` is a limit like any other: nobody can be added or invited, and the owner alone holds the workspace. Only a negative value means unlimited (OQ-2). This follows earlier fixes where a zero was wrongly treated as "not set" (BUG-501, BUG-707).
**Alternatives:** (a) `0` also means unlimited, as today; document it next to `-1`. (b) `0` is not a valid plan value; a check constraint refuses it.

**Answer:** owner, 2026-11-04: "This seems like a bug; we need to go over what the plans will be in future. Put that work with the payment portal; we need to figure out how to combine plans and subscriptions later." Logged as a bug, deferred to the payment portal's plans/subscriptions design. Tests keep today's behaviour in its own card. → BUG-1989 (applied 2026-11-04 to `workspace_manager.spec.md` Q2, `add_member_to_workspace` R6, `create_invitation` R9)

## OQ-18. A private project answers "no access" (403) on its pages but "not found" (404) on its discussions and files — blocking

**Module:** `app/managers/project_manager.py` — spec `tests/unit/managers/project_manager.spec.md` Q1 (IN REVIEW). Reached through every `/projects/{id}/…` page and every project component page (`require_project_access`, `require_component_access`).
**Kind:** security / access (who learns which private projects exist).
**Facts from the code:**
- A project set to `invited_only` opens only for the workspace owner, an active `owner` / `ground-team-manager`, its creator and its project members.
- For anyone else every project page answers **403 "You do not have access to this project"**: details, members, activity, edit, delete, visibility, and each component page through its project. A missing project, or another workspace's, answers **404 "Project with ID <id> not found"**. Verified on `marker_test`: a `ground-team` member got 403 on another member's private project.
- Your OQ-5 answer gives **404** for the same private project's discussions (BUG-1867), attachments (BUG-1870) and calendar (BUG-1869), so a hidden record cannot be told from a missing one. The workspace switch made the same choice for non-members (BUG-440).
- So today a member can tell from the ids which private projects exist, and the project page and its own discussion panel give different answers.
- Help tickets are not part of this: your OQ-8 answer kept 403 for them.

**Suggested answer:** bug — a project the caller may not open answers exactly as a missing one: 404 "Project with ID <id> not found". A component of such a project answers 404 "Project component not found", as a missing component (so a component id does not reveal its project's id). One rule for every page of a private project, matching OQ-5 and BUG-440.
**Alternatives:** (a) intended — keep 403 on the project pages (it tells a member to ask for access) and accept that discussions, files and calendar answer differently. (b) 404 for projects **and** help tickets: one rule for every record that has its own visibility.

**Answer:** owner, 2026-11-04: alternative, keep 403 on project pages. Discussions, files and calendar entries still answer 404 under OQ-5. No bug; reserved BUG-1965 unused. Applied to `project_manager.spec.md` Q1 (APPROVED).

## OQ-19. A section's "Plan day" run makes drafts for recurring templates that are not due — not blocking

**Module:** `app/managers/work_order_template_manager.py` (`generate_drafts`) — spec `tests/unit/managers/work_order_template_manager.spec.md` Q1, rule `generate_drafts` R4 (written to today's behaviour).
**Kind:** order workflow (which draft work orders are made).
**Facts (verified on `marker_test`):**
- `POST /work-order-templates/generate-drafts/` with a section takes every active template of that section, recurring ones included even when not due.
- A weekly template due 16 March got a draft on 10 March and again on 11 March; its next date did not move. An unscoped run gave it none.
- The endpoint is labelled deprecated and no web app screen calls it; the planning sheet makes recurring drafts another way (anchored range).

**Suggested answer:** bug — in a section run a recurring template gets a draft only when it is due; non-recurring templates of the section still get one every run.
**Alternatives:** (a) retire the endpoint and `generate_drafts`; (b) intended.

**Answer:** owner, 2026-11-07: suggested answer (a recurring template gets a draft only when due). → BUG-2345 (applied 2026-11-07 to `work_order_template_manager.spec.md` `generate_drafts` R1, R4)

---

## OQ-20. A late "Plan day" run skips a recurring template's missed dates — not blocking

**Module:** same; spec Q2, rule `generate_drafts` R10.
**Kind:** order workflow (recurrence advancing).
**Facts (verified):** a weekly template due 16 March, planned on 30 March, gets one draft (30 March); 16 and 23 March get none; its next date becomes 6 April. Same deprecated endpoint as OQ-19.

**Suggested answer:** intended — a run plans the day asked for; catching up is a manual decision.
**Alternatives:** (a) one draft per missed date up to the run's date, as the sheet's anchored range does.

**Answer:** owner, 2026-11-07: suggested answer (intended: missed dates are skipped; catching up stays manual). No bug; `generate_drafts` R10 ✅ (applied 2026-11-07).

---

## OQ-21. A template that "requires approval" but has no approvers gives orders approved at once — not blocking

**Module:** `app/managers/work_order_template_manager.py` (`create_template`, `update_template`); spec Q3, rules `create_template` R6, `update_template` R9.
**Kind:** order workflow (approvals on generated work orders).
**Facts (verified):** `requires_approval: true` with no approvers is accepted; a work order made from it is stamped "Ready to start — no approval required" on creation. Approvers who have since become inactive are skipped when copied, with the same result. Your BUG-1204 answer keeps "no approval required" for orders that never had an approver.

**Suggested answer:** bug — such a template is refused on create / update: 400 `Choose at least one approver, or turn off "requires approval"`, nothing written.
**Alternatives:** (a) allow it, but a generated order with no approvers is not approved until someone is added; (b) intended.

**Answer:** owner, 2026-11-07: suggested answer (create and update refuse a template that requires approval but has no approvers, 400, nothing saved). → BUG-2346 (applied 2026-11-07 to `create_template` R6, `update_template` R9)

---

## OQ-22. Any member can make a template whose expense orders skip approval — not blocking

**Module:** `app/managers/order_template_manager.py` — spec `tests/unit/managers/order_template_manager.spec.md` Q1 (APPROVED; rules `create_template` R9, `update_template` R9 written to today's behaviour, own cards). Reached through `POST`, `PUT /order-templates/…`.
**Kind:** order workflow and money (who may skip expense approval).
**Facts from the code (template writes run on `marker_test`; the order side read):**
- A template has `requires_approval` (default true) and `auto_approve` (default false). An expense order made from a template with `requires_approval = false`, or `auto_approve = true`, gets `required_approvals = 0` (`expense_order_manager.py:638-647`), so it counts as approved at once and can go on to its draft invoice.
- Templates have no role check: any active member may create one or switch either flag.
**Suggested answer:** bug — only the workspace owner may create a template with `requires_approval = false` or `auto_approve = true`, or switch either flag on an existing one (403 "Only the workspace owner can skip approval on a template", nothing written); everything else on templates stays open to every member.
**Alternatives:** (a) intended — templates are trusted. (b) keep the flags, but the expense order honours them only when the person making the order is the owner.

**Answer:** owner, 2026-11-07: suggested answer (only the workspace owner may set or switch approval-off / auto-approve on expense templates; 403 otherwise). → BUG-2347 (applied 2026-11-07 to `order_template_manager.spec.md` `create_template` R9, `update_template` R9; the manager reads the caller's role from the existing `user_id`, as PR-5)

---

## OQ-23. Who may read the financial audit log? Today every member can — not blocking

**Module:** `app/api/v1/endpoints/financial_audit_logs.py`; specs `tests/unit/services/financial_audit_log_service.spec.md` Q1 and `tests/unit/dao/financial_audit_log.spec.md` (both APPROVED; no rule waits on this, the check would sit in the endpoints).
**Kind:** money / access (who sees financial history).
**Facts from the code:**
- The log holds every change to accounts, invoices and payments: amounts before and after, a description ("Payment of $2000.00 recorded for invoice ID 10"), who and when, and, once BUG-140 / BUG-603 are fixed, the IP address and browser.
- All six `GET /financial-audit-logs/…` endpoints need only an active membership. Any role, `ground-team` included, can read everything and filter by any colleague (`/user/{id}/`).
- Accounts and invoices themselves are open to every member too; only the subscription checkout is owner-only.
- No web page calls these endpoints yet (hooks exist in `financialAuditLogsApi.ts`, unused).

**Suggested answer:** bug — owner only for now (the finance role to be added in the permissions work); other members get 403 on all six endpoints. Nothing visible breaks.
**Alternatives:** (a) intended — every member, as for accounts and invoices; decide in the permissions work. (b) every member, but `ip_address` / `user_agent` shown to the owner only.

**Answer:** owner, 2026-11-07: decide in the permissions work. Today's behaviour stays in the tests; noted in docs/future/permissions.md. No bug (applied 2026-11-07: both financial audit log specs mark it deferred).

---

## OQ-24. `POST /order-workflows/` can create the purchase workflow with any steps — not blocking

**Module:** `app/services/order_workflow_service.py` — spec `tests/unit/services/order_workflow_service.spec.md` Q2 (APPROVED; rule `create_workflow` R6 written to today's behaviour, own card).
**Kind:** order workflow (which purchase stage counts as finished).
**Facts from the code:**
- Your answer of 2026-11-02 (BUG-1223) made the purchase workflow's steps read-only through `PUT`; the system rewrites them on every purchase order write. `POST` was not covered.
- Every workspace is seeded with its `purchase` row, so `POST type=purchase` is normally refused as a duplicate (409). It succeeds only where the row is missing (old workspaces; deleting it is blocked from now on by BUG-1222).
- There it is stored as sent: `[<Draft>]` makes draft orders count as finished and finished ones as open, until the next purchase order write puts the four stages back. No web page calls `/order-workflows/`.

**Suggested answer:** bug — `POST` with `type: purchase` is refused (400 "The purchase workflow is managed by the system"), nothing written, as for `PUT`; the system creates the row on the next purchase order write.
**Alternatives:** (a) intended — the next purchase order write repairs it. (b) accept the row but ignore the sent steps, filling in the four stages.

**Answer:** owner, 2026-11-07: suggested answer (creating the purchase workflow through the API is refused with 400, as for PUT under BUG-1223). → BUG-2348 (applied 2026-11-07 to `order_workflow_service.spec.md` `create_workflow` R6)

---

## OQ-25. The payment sweep never re-checks a payment closed by an unverified redirect, or `EXPIRED` — not blocking

**Module:** `app/dao/payment_transaction.py` — spec `tests/unit/dao/payment_transaction.spec.md` OQ-25 (APPROVED; rule `get_stuck_initiated` R7 written to today's behaviour, own rule). The sweep itself is `PaymentTransactionManager.reconcile_stuck_transactions` (R1).
**Kind:** money (whether a customer's real payment can end up recorded as not paid for good).
**Facts from the code:**
- The reconciliation sweep (`scripts/reconcile_payments.py`) asks the gateway only about rows with status exactly `INITIATED` started before the cutoff (default 30 minutes), oldest first, at most 200 (`get_stuck_initiated`). Verified: `EXPIRED`, `CANCELLED`, `VALIDATED_FAILED`, `INIT_FAILED` rows of any age are never returned.
- Your delegated answers on the payment manager (BUG-026, BUG-027) made three outcomes replaceable by a later gateway-verified result: `VALIDATED_FAILED` / `CANCELLED` set by a browser redirect that the gateway never confirmed (`outcome_verified = false`), and `EXPIRED` set by the sweep. But only the IPN webhook can bring that later result. If it is lost, nothing asks the gateway again.
- So: a customer pays, an old tab's "Cancel" redirect arrives first, the IPN is lost. The row stays `CANCELLED`, the gateway kept the money, and (once the portal exists) the plan is never applied.
- Cost of re-checking: one gateway query per row per sweep run.

**Suggested answer:** bug — the sweep also re-checks rows with an unverified outcome (`EXPIRED`, and `VALIDATED_FAILED` / `CANCELLED` with `outcome_verified = false`) until 72 hours after `initiated_at`; each at most once per run, oldest first, within the same `limit`. A verified answer replaces the outcome (as `finalize_from_gateway` R3a/R3b already says); an answer that is not final leaves the row unchanged, with no new `expired` event.
**Alternatives:** (a) intended — only `INITIATED` rows are swept; a lost IPN after an unverified outcome is fixed by hand. (b) re-check unverified outcomes with no time limit.

**Answer:** owner, 2026-11-10: decide in the payment portal work. Today's behaviour stays in the tests (own cards); noted in docs/future/subscription-payments.md.

---

## OQ-26. `PUT /sales-orders/{id}/` lets a client set an order's total, "fully delivered" and "invoiced" flags — not blocking

**Module:** `app/services/sales_service.py` (`update_sales_order`) with `app/schemas/sales_order.py` (`SalesOrderUpdate`); found while describing `app/dao/sales_order.py` (spec `tests/unit/dao/sales_order.spec.md` FU-1 (a)). Not a rule of the DAO; the sales service spec will ask it again.
**Kind:** money and order workflow (an order's amount and its delivered / invoiced state).
**Facts from the code:**
- `SalesOrderUpdate` has `total_amount`, `is_fully_delivered`, `is_invoiced` (and `invoice_id`, already ruled system-only: BUG-1019). `update_sales_order` stores whatever is sent through the inherited `update`, with no check and no event, on any order, including one whose invoice is finalized or that is completed.
- The system sets these itself: `total_amount` is the sum of the line totals at creation (the endpoint computes it); `is_fully_delivered` is recomputed after each delivery or fulfilment; `is_invoiced` is cleared when an invoice is unlinked.
- `total_amount` is what the orders overview and the calendar show and sum per factory; the lines and the invoice are not changed by the edit.
- The web app never sends these three fields (it sends contact name / phone, description, expected delivery date, `required_approvals`), so only direct API calls do this.

**Suggested answer:** bug — `total_amount`, `is_fully_delivered` and `is_invoiced` are system-only, like `invoice_id` (BUG-1019, BUG-751 precedent): removed from `SalesOrderUpdate`; a request that still sends them has them ignored (or 422), nothing else changes.
**Alternatives:** (a) intended — keep them editable as a manual correction tool. (b) editable only while the order is not finalized, and logged as an event.

**Answer:** owner, 2026-11-10: suggested answer (total_amount, is_fully_delivered and is_invoiced are system-only; an edit that sends them gets 422).

---

## OQ-27. Nothing writes the project component item ledger, so component item cost is always 0.00 — not blocking

**Module:** `app/dao/project_component_item_ledger.py` — spec `tests/unit/dao/project_component_item_ledger.spec.md` Q1 (APPROVED; no rule of the DAO depends on it).
**Kind:** stock / money (what a project component's item cost is).
**Facts from the code:**
- The table is built to record item movements into, out of and within a project component (`transfer_in`, `transfer_out`, `consumption`, `damaged`, …) with cost, value and average price before and after.
- Searched all of `app/` (2026-11-09): no code creates a row. Work orders linked to a component, transfer orders and project component items (planned quantities only) write nothing here. The test database holds no rows.
- So `GET /ledgers/project-component/` is always empty and `GET /ledgers/project-component/{id}/total-cost/` always answers `0.0`. Only hand-typed miscellaneous costs put money on a project.
- The project component item service spec says this ledger "is written by work orders"; it is not.

**Suggested answer:** intended for now — project item costing is not built yet. The read paths stay and are tested on hand-made rows. When it is built, decide which movements write here (e.g. a transfer to a component, work-order consumption on a component), priced at the source's average cost, half up.
**Alternatives:** (a) bug — work orders on a project component (and transfers to one) must write a ledger row now, so component cost is real.

**Answer:** owner, 2026-11-10: projects are skipped for now; revisit after launch. Tests keep today's behaviour, no bug.

---

## OQ-28. A miscellaneous project cost may be negative or zero — not blocking

**Module:** `app/schemas/miscellaneous_project_cost.py` (via `MiscellaneousProjectCostService`, not yet specified); found while describing `app/dao/miscellaneous_project_cost.py` (spec Q2).
**Kind:** money (what a cost amount may be).
**Facts from the code:**
- `amount` is a plain `float` with no bound on create and update; the column is `Numeric(15,2)` NOT NULL.
- The web "Add misc cost" dialog refuses 0 or less before sending; the API does not. Verified: `-5` is stored as `-5.00`.
- Negative project budgets (BUG-1962) and negative stock / prices (BUG-711) were refused.

**Suggested answer:** bug — the amount must be greater than 0 (422, nothing written), as the web form already requires; rows already stored are left alone.
**Alternatives:** (a) `>= 0`, zero allowed as a placeholder. (b) intended — a negative cost is a credit.

**Answer:** owner, 2026-11-10: projects are skipped for now; revisit after launch. Tests keep today's behaviour (negative and zero stored), no bug.

---

## OQ-29. The orders overview counts drafts and orders awaiting approval as spend and revenue — not blocking

**Module:** `app/services/orders_overview_service.py` (`get_stats`, `_build_top_factories`) — spec `tests/unit/services/orders_overview_service.spec.md` Q4 (APPROVED; rules marked *pending owner*).
**Kind:** money (which orders count in spend / revenue totals).
**Facts from the code:**
- `GET /orders/overview/stats` (web Orders → Overview) has no status filter: every purchase, sales, expense, transfer and work order in the date range counts, whatever its status (draft, awaiting approval, approved, complete). Voided ones will be left out once BUG-2500 is fixed.
- A draft PO's amount can still change. For invoices, drafts were ruled out of money totals (BUG-634). The calendar shows drafts.

**Suggested answer:** intended — the overview ranks order activity in the period, drafts included, as the calendar does; only voided orders are left out (BUG-2500).
**Alternatives:** (a) bug — the money columns (vendor spend, customer totals, item spend, factory value) count only orders past approval; order counts keep every order. (b) bug — drafts are left out entirely.

**Answer:** owner, 2026-11-10, in their words: "show like this is for sure being spent cause approved, but then draft should count towards maybe projected ... but then also the total of both, like have bar charts kinda deal". Confirmed by the owner (2026-11-10): the overview reports three figures per measure: committed (approved and later, not voided), projected (drafts and orders awaiting approval), and the total of both; the web app shows them as a chart. Voided orders are in none. → BUG-2480

---

## OQ-30. Orders overview totals add purchases, transfers and sales together — not blocking

**Related:** same root as OQ-31 (item summary "Total spend"); answer them together.

**Module:** `app/services/orders_overview_service.py` (`get_stats` top items, `_build_top_factories`) — spec `tests/unit/services/orders_overview_service.spec.md` Q5 (APPROVED; rules marked *pending owner*).
**Kind:** money and stock (how totals roll up).
**Facts from the code:**
- Top items: `total_spend` = purchase line subtotals **plus** sales line totals; `total_quantity` = purchased + transferred + sold quantity (bought 10, moved 10, sold 10 → 30). Items are ranked by `total_quantity`. Per-kind quantities (`purchase_qty`, `transfer_qty`, `sales_qty`) are also returned.
- Top factories: `total_value` = PO totals + sales order totals + work order costs.
- The web page ranks items by `total_quantity` showing "PO x · TR y", and shows `total_value` per factory.

**Suggested answer:** bug — keep the per-kind quantities; split money into purchase spend and sales revenue (new fields); rank items by purchased quantity and factories by order count, then purchase spend.
**Alternatives:** (a) intended — the overview measures activity volume, not money. (b) only leave transfers out of `total_quantity`.

**Answer:** owner, 2026-11-10: suggested answer (split: spend = purchases only; sales revenue its own figure; transfers left out of money totals; items ranked by purchased quantity). → BUG-2481

---

## OQ-31. The item summary's "Total spend" adds sales revenue to purchase spend — not blocking

**Related:** same root as OQ-30 (orders overview `total_spend`); answer them together.

**Module:** `app/services/item_summary_service.py` (`_order_stats_for_item`) — spec `tests/unit/services/item_summary_service.spec.md` Q7, rule `_order_stats_for_item` R5 (written to today's behaviour, *pending owner*).
**Kind:** money (what a report total means).
**Facts from the code:**
- For one item, the summary sums purchase lines (quantity, line subtotal), transfer lines (quantity only) and sales lines (quantity, **line total**) per 30 days, 90 days and all time.
- `total_spend` = purchase subtotals **+ sales line totals**; `total_quantity` = bought + transferred + sold.
- The item dialog's KPI strip shows `order_stats.all_time.total_spend` labelled **"Total spend"**.
- Verified: 20 bought for 50.00 and 3 sold for 300.00 → total_spend 350.00 (plus 102.00 from a voided PO and a bad cross-workspace line, which are separate bugs).

**Suggested answer:** bug — `total_spend` is purchase spend only; sales value becomes its own figure (e.g. `sales_total`); `total_quantity` stays the volume of all lines.
**Alternatives:** (a) intended — an "order value" across types, and only the label is wrong. (b) drop `total_spend`; show purchase and sales value side by side.

**Answer:** owner, 2026-11-10: suggested answer (same as OQ-30: "Total spend" counts purchases only, sales value is its own figure). → BUG-2485

---

## OQ-32. The item summary's open purchase lines include orders already closed — not blocking

**Module:** `app/services/item_summary_service.py` (`_pricing`) — spec `tests/unit/services/item_summary_service.spec.md` Q8, rule `_pricing` R4 (written to today's behaviour, *pending owner*).
**Kind:** stock counting (what counts as still incoming).
**Facts from the code:**
- "Open PO lines" and "outstanding quantity" count every purchase line with ordered > received + refunded, whatever the order's status.
- The stock page's incoming summary (`InventoryManager.get_incoming_summary_for_factory`) leaves out orders in their workflow's last (terminal) status.
- Voided orders are already ruled out (BUG-2521, BUG-717 precedent).

**Suggested answer:** bug — a line is open only when its order is not voided and not in its workflow's terminal status, the same rule as the incoming summary.
**Alternatives:** (a) intended — the summary shows everything never delivered, closed or not.

**Answer:** owner, 2026-11-10: suggested answer (open PO lines leave out orders in the last workflow status as well as voided ones). → BUG-2486

---

## OQ-33. An item's order list spreads a partly priced order's total over all its quantity, and shows no total for an order priced at 0.00 — not blocking

**Module:** `app/services/item_orders_service.py` (`_purchase_rows`, `_sales_rows`, `_weighted_unit_price`; `GET /items/{id}/orders/`); spec `tests/unit/services/item_orders_service.spec.md` Q5 (APPROVED; the rules are marked "pending owner" and tested to today's behaviour).
**Kind:** money (which purchase / sales price a user sees for an item).
**Facts from the code:**
- One row per order. `quantity` = sum of the item's ordered quantities on the order; `line_total` = sum of the priced line subtotals (unpriced PO lines have none); `unit_price` = `line_total / quantity`.
- A `line_total` of 0 or less is shown as empty, but the unit price is still computed (0).
- Verified: PO with 10 bolts at 5.00 and 10 unpriced bolts → quantity 20, unit price 2.50, line total 50.00. PO priced at 0.00 → unit price 0, line total empty.
- The web app shows these rows as "recent purchases" on the item page, in the item's Purchasing section and in the PO "purchase history" dialog (last price paid).

**Suggested answer:** bug — unit price = priced subtotal / **priced** quantity (5.00 in the example); `line_total` = priced subtotal, 0.00 included; both empty only when no line of the item is priced. Rounded half up to 2 places (HR-15, BUG-2554).
**Alternatives:** (a) intended — keep today's spread and blank zero total. (b) unit price empty whenever any line is unpriced.

**Answer:** owner, 2026-11-10: suggested answer (divide by the priced quantity only; a zero-priced order shows 0.00). → BUG-2490, BUG-2491

---

## OQ-34. A workspace owner can take over a member's whole account by resetting its password — not blocking

**Module:** `app/services/auth_service.py` (`reset_password_by_admin`; `POST /auth/admin/reset-password/`). Spec `tests/unit/services/auth_service.spec.md` Q1 (APPROVED; rule `reset_password_by_admin` R7 written to today's behaviour, *pending OQ-34*). Found 2026-11-10.
**Kind:** security / access (who can get into an account).
**Facts from the code:**
- An account is global: one email and password for every workspace the person belongs to, and for the platform admin flag (`profiles.is_platform_admin`).
- The endpoint lets the owner of the current workspace set any new password for any **active** member of that workspace. No old password, no email to the person and no consent are needed. All of the member's sessions are revoked. Nothing is audited (BUG-2569).
- Anyone can register, become the owner of a new workspace and invite any email (the web app shows the token for the owner to pass on).
- Verified on `marker_test` (rolled back): the owner of workspace A reset the password of a member of A who is a platform admin and the owner of workspace B, then logged in as that member and switched into B.
- The web app has no screen for this endpoint; it is reachable through the API only. Forgot-password does not work yet (it sends nothing, and reset-password answers 501), so this endpoint is today the only way back into a forgotten account.

**Suggested answer:** bug — the owner may reset the password only of an account that belongs to **no other workspace** (no membership elsewhere with a status other than `inactive`) and is **not a platform admin**, and never their own (they have the normal login). Otherwise 403 "This account is also used outside this workspace; the person must reset the password themselves." and nothing changes. The reset writes the audit row of BUG-2569. When email reset exists (notifications work), the owner's reset becomes "send a reset link" instead of setting a password.
**Alternatives:**
- (a) intended — owners are trusted and keep today's power.
- (b) switch the endpoint off (403 for everyone) until email-based reset exists.
- (c) keep it, but the person must confirm by email before the new password works (needs email delivery).

**Answer:** owner, 2026-11-10: decide in the permissions work. Today's behaviour stays in the tests (own cards); flagged in docs/future/permissions.md as a security item to settle early.

---

## OQ-35. The PO hub's money totals add voided orders, and count them as open — not blocking

**Module:** `app/dao/purchase_order.py` (`aggregate_hub_stats`; `GET /purchase-orders/stats/`) — spec `tests/unit/dao/purchase_order.spec.md` OQ-35, rules `aggregate_hub_stats` R2, R3 (written to today's behaviour, *pending owner*).
**Kind:** money (what the hub's total and open values include).
**Facts from the code:**
- The hub tiles show total count, total value, open count, open value, not invoiced. They use the same filters as the list.
- With "show voided" on, the web app sends `exclude_voided=false`; voided orders then add their `total_amount` to total value, and, because they are never "Complete and paid", to open count and open value.
- Verified: orders 100.00 (Complete, paid), 200.00 (Complete, unpaid), 300.00, 400.00 (voided), 1.00, 5.00 → total value 1006.00, open count 5, open value 906.00.
- Elsewhere voided orders count in no money figure (BUG-2500 orders overview, BUG-2521 item summary).

**Suggested answer:** bug — voided orders add nothing to total value, open count or open value; they still count in total count and "not invoiced" when shown, so the count matches the list.
**Alternatives:** (a) intended — the tiles sum exactly what the list shows. (b) leave voided orders out of every tile, count included.

**Answer:** owner, 2026-11-11: suggested answer (voided orders add no money and are not open; they still count in the total count and "not invoiced" when shown). → BUG-2639

---

## OQ-36. The PO hub's "open value" is the full total of every order not both Complete and paid — not blocking

**Module:** `app/dao/purchase_order.py` (`aggregate_hub_stats`, `_purchase_order_is_fully_closed_clause`) — spec `tests/unit/dao/purchase_order.spec.md` OQ-36, rule `aggregate_hub_stats` R3.
**Kind:** money (meaning of "open value").
**Facts from the code:**
- An order is "fully closed" when its stage is `Complete` **and** `paid` is set (mirrors the web app's `isPurchaseOrderFullyClosed`); everything else is open.
- Open value adds each open order's whole `total_amount`: a Complete order with a half-paid invoice adds its full total; a fully paid order still in `Receiving` adds its full total too.
- Example: 10,000.00 PO, all goods received, 9,000.00 paid → open value 10,000.00.

**Suggested answer:** intended — open value is the value of orders not yet closed (received **and** paid), at full order total; what is still owed belongs to the invoice / payables views.
**Alternatives:** (a) bug — open value is the unpaid balance of the linked invoice (order total when no invoice).

**Answer:** owner, 2026-11-11: suggested answer (intended: open value is the full order total). → intended, no bug (applied to `purchase_order.spec.md` `aggregate_hub_stats` R3 ✅)

---

## OQ-37. The PO hub's "outstanding payment" filter includes orders whose invoice is a draft or voided — not blocking

**Module:** `app/dao/purchase_order.py` (`_apply_purchase_order_hub_filters`, `invoice_filter=outstanding_payment`; list and stats) — spec `tests/unit/dao/purchase_order.spec.md` OQ-37, rule `_apply_purchase_order_hub_filters` R9.
**Kind:** money (which orders still owe money).
**Facts from the code:**
- Kept: POs whose linked invoice's `payment_status` is not `paid`. The invoice's own status (`draft` / `confirmed` / `locked` / `voided`) is not looked at.
- `payment_status` is `unpaid` from creation (default) and is only meaningful once the invoice is confirmed; a real invoice void resets `payment_status` to `unpaid` and `paid_amount` to 0.00 (corrected 2026-11-11 from the code; the original note said a voided invoice keeps its last value).
- Verified: a PO with a draft invoice and a PO with a voided invoice were both listed as outstanding.
- The expense hub's "unpaid pipeline" already leaves voided invoices out (it keeps drafts).

**Suggested answer:** bug — outstanding = the invoice is confirmed or locked (not draft, not voided) and `payment_status` is not `paid`.
**Alternatives:** (a) take only voided invoices out, keep drafts (the expense hub's rule). (b) intended.

**Answer:** owner, 2026-11-11: suggested answer (only orders with a confirmed or locked invoice that is not fully paid). → BUG-2640

---

## OQ-38. The PO list's "received" progress ignores refunded quantity — not blocking

**Module:** `app/dao/purchase_order.py` (`PurchaseOrderItemDAO.summarize_by_purchase_order_ids`; hub list rows "x/y received" in `PurchaseOrderListRow.tsx`) — spec `tests/unit/dao/purchase_order.spec.md` OQ-38, rule `summarize_by_purchase_order_ids` R2.
**Kind:** stock (what counts as still to receive).
**Facts from the code:**
- Per order: ordered total = sum of `quantity_ordered`, received total = sum of `quantity_received`. Refunded (`quantity_refunded`) and returned quantities play no part; different items' units are added together.
- A refund-type return settles that quantity: it will never be received, and the order counts as fully received when received + refunded reaches ordered.
- Verified: lines 10 / 7 received / 3 refunded, 5.5 / 0 / 0, 1 / 1 / 0 → 16.50 ordered, 8.00 received.
- The row shows "8/16.5 received" only while the order is in `Receiving`.

**Suggested answer:** bug — the ordered total counts each line as ordered − refunded ("7/7 received" for 10 ordered, 7 received, 3 refunded); received stays the received quantity.
**Alternatives:** (a) intended — raw ordered and received. (b) received total = received + refunded ("10/10").

**Answer:** owner, 2026-11-11: show all three numbers, e.g. "7 received of 10 ordered · 3 refunded", and the line counts as done when received + refunded = ordered. → BUG-2641 (the DAO returns ordered, received and refunded; the wording is the service's / web app's job, spec FU-5)

---

## OQ-39. The transfer hub counts an order with a route but no lines as "Planned", while the order page calls it "Draft" — not blocking

**Module:** `app/dao/transfer_order.py` (`get_pending_highlights_for_hub`; `GET /transfer-orders/stats/`, the hub's "Pending actions" box). Spec `tests/unit/dao/transfer_order.spec.md` OQ-39 (APPROVED; rules `get_pending_highlights_for_hub` R2, R3 written to today's behaviour, *pending OQ-39*). Found 2026-11-10.
**Kind:** order workflow (which stage an open transfer order is in).
**Facts from the code:**
- Transfer orders have no live workflow status (see OQ-40); the stage is worked out from the order.
- The web app's order page (`deriveTransferOrderStage`) says **Draft** until both route ends are set **and** at least one line exists, then **Planned**, then **Completed** once marked complete.
- The hub box counts "In Planned" = open order with a route, lines not looked at; "Awaiting setup" / "Oldest draft" = open order with no route. Each sample is labelled with the fixed text "Planned" / "Draft".
- Verified on `marker_test` (rolled back): three open orders with a route and no lines were all counted and listed as "Planned".
- Such an order cannot be completed ("Add at least one item before completing").

**Suggested answer:** bug — "Planned" needs a route **and** at least one line, as the order page; an open order missing either is "Draft" (awaiting setup, oldest drafts).
**Alternatives:** (a) intended — the hub only tracks whether the route is set. (b) a third hub box "needs lines".

**Answer:** owner, 2026-11-11: suggested answer ("Planned" needs a route and at least one line; otherwise Draft, matching the order page). → BUG-2659

---

## OQ-40. The transfer hub's status filter compares the status stored at creation, which never changes — not blocking

**Module:** `app/dao/transfer_order.py` (`_apply_transfer_order_hub_filters`, `status_ids`; `GET /transfer-orders/`, `GET /transfer-orders/stats/`). Spec `tests/unit/dao/transfer_order.spec.md` OQ-40 (APPROVED; rule `_apply_transfer_order_hub_filters` R4 written to today's behaviour, *pending OQ-40*). Found 2026-11-10.
**Kind:** order workflow (what a transfer order's status means when filtering).
**Facts from the code:**
- `current_status_id` is set once at creation (today the fixed id 1, BUG-1018) and never changes: an edit that sends it is refused ("Status is derived from workflow state — use Mark complete instead"); marking complete sets `completed_at` only.
- The web app's hub status filter offers the workspace's statuses named Draft, Planned and Completed and sends their ids as `status_ids`; the DAO keeps orders whose **stored** status id is in the list.
- So ticking "Planned" empties the list, the total and the KPI tiles, although orders show "Planned" on their pages.
- Which status a new order gets is the owner's boxed question O2 (status DAO spec, 2026-11-02); this question is only about the filter.

**Suggested answer:** bug — the filter matches the order's stage: a ticked status named Draft / Planned / Completed keeps orders in that stage (Draft / Planned as OQ-39; Completed = `completed_at` set); a ticked status of any other name matches nothing. Once O2 is decided and the system keeps `current_status_id` in step with the stage, the filter can compare the stored id again.
**Alternatives:** (a) decide O2 now: the system moves `current_status_id` to the workspace's Draft / Planned / Completed rows as the stage changes, and the filter stays as it is. (b) remove the status filter from the transfer hub.

**Answer:** owner, 2026-11-11: suggested answer (the Draft / Planned / Completed ticks match the order's current stage). → BUG-2660

---

## OQ-41. The account invoice summary adds what we owe and what we are owed into one total — not blocking

**Related:** same root as OQ-30 / OQ-31 (owner, 2026-11-10: split different money flows instead of adding them).

**Module:** `app/dao/account_invoice.py` (`summarize_invoices`; `GET /accounts/{id}/invoice-summary/`) — spec `tests/unit/dao/account_invoice.spec.md` OQ-41 (APPROVED; rule `summarize_invoices` R5 written to today's behaviour, *pending OQ-41*). Found 2026-11-10.
**Kind:** money (what an account's balance totals mean).
**Facts from the code:**
- An account can hold both kinds of invoice: **payable** (we owe them: purchase orders, expenses) and **receivable** (they owe us: sales, and the credit note a purchase return creates against the same supplier, `order_type = purchase_order`, `invoice_type = receivable`).
- With no `invoice_type` filter, `invoiced_total`, `paid_total` and `outstanding_total` are plain sums over both kinds (voided left out; drafts left out after BUG-634).
- The account page's KPI strip "Invoiced / Paid / Outstanding" (`AccountOverviewPanel.tsx`) calls the summary with no type filter.
- Verified on `marker_test` (rolled back): a 1,000.00 unpaid payable and a 200.00 receivable on one account → invoiced 1,200.00, paid 0.00, outstanding 1,200.00.
- The workspace hub already keeps the two apart (`payable` / `receivable` KPIs and per-account rollups).

**Suggested answer:** bug — the summary returns payable and receivable figures separately (`payable_invoiced/paid/outstanding`, `receivable_invoiced/paid/outstanding`; `invoice_count` per kind too); the combined fields go, or stay only when an `invoice_type` filter is given. A net figure, if wanted, is the web app's to show.
**Alternatives:** (a) intended — "invoiced" is volume across both kinds. (b) keep one set of fields but net them (receivable minus payable, signed).

**Answer:** owner, 2026-11-11: suggested answer (payable and receivable figures shown separately, as in OQ-30/31). → BUG-2692

---

## OQ-42. The expense hub's money figures include voided expense orders — not blocking

**Module:** `app/dao/expense_order.py` (`aggregate_hub_stats`, `aggregate_financial_snapshot_filtered`; `GET /expense-orders/hub-stats`) — spec `tests/unit/dao/expense_order.spec.md` OQ-42 (APPROVED; rules `aggregate_hub_stats` R1–R3, `aggregate_financial_snapshot_filtered` R1, R5, R8 written to today's behaviour, *pending OQ-42*). Found 2026-11-10.
**Kind:** money (which orders count in totals).
**Facts from the code:**
- Voiding keeps the row (`voided = true`). Every hub figure takes `exclude_voided`; the API default is `false` and the web app's expense hub always sends `false` (the purchase order hub has a "show voided" toggle, off by default).
- So voided orders count in total value, in open count/value (a voided order is never completed), in "not invoiced", in the category breakdown, in the stage pipeline (as Draft, or Invoiced) and in open-by-account.
- Verified: orders 100.00 and 50.00 plus a voided 30.00 → total 180.00, open 3 / 180.00, Draft 3 / 180.00.

**Suggested answer:** bug — voided orders never count in the hub's money figures (stats, category breakdown, stage pipeline, open by account), whatever the filter; the list and its count still follow `exclude_voided`, and the web app gets a "show voided" toggle like the purchase order hub.
**Alternatives:** (a) intended — the figures follow the list's filter. (b) voided orders left out of the list too by default (web app sends `exclude_voided=true`), figures follow the list.

**Answer:** owner, 2026-11-11: suggested answer (voided orders never count in money figures; the list follows its filter; add a "show voided" toggle like the PO hub). → BUG-2717

---

## OQ-43. The expense hub's "unpaid pipeline" only shows draft invoices, never bills waiting for payment — not blocking

**Module:** `app/dao/expense_order.py` (`aggregate_financial_snapshot_actionable`; `GET /expense-orders/hub-stats`) — spec `tests/unit/dao/expense_order.spec.md` OQ-43 (APPROVED; rules R8, R9 *pending OQ-43*). Found 2026-11-10.
**Kind:** money (what counts as unpaid).
**Facts from the code:**
- The pipeline counts orders not voided and **not completed**, with an invoice not voided and `payment_status` unpaid / partial / overdue; amount = invoice amount − paid.
- Completing an expense order confirms its invoice, and payments can only be recorded on confirmed invoices. A draft invoice is `unpaid` by default with nothing paid.
- So the pipeline lists only draft invoices, at full amount, as "Unpaid"; "Partial" and "Overdue" stay empty. Once the order is completed — when the bill becomes payable — it leaves the pipeline even if nothing is paid. Verified: draft invoice 100.00 → "Unpaid 100.00".
- The web app's empty text reads "No unpaid invoice balances on open expenses."

**Suggested answer:** bug — the pipeline lists not-voided orders, completed or not, whose invoice is **confirmed** and unpaid / partial / overdue, at invoice amount − paid; draft invoices are left out.
**Alternatives:** (a) intended — the pipeline shows bills about to be confirmed (then rename it, e.g. "Awaiting confirmation"). (b) show both draft and confirmed invoices.

**Answer:** owner, 2026-11-11: suggested answer (not-voided orders, completed or not, whose invoice is confirmed and unpaid, partly paid or overdue, at amount minus paid). → BUG-2718

---

## OQ-44. The expense due timeline drops an order once completed, and counts the full total rather than what is still owed — not blocking

**Module:** `app/dao/expense_order.py` (`aggregate_financial_snapshot_actionable`; `GET /expense-orders/hub-stats`) — spec `tests/unit/dao/expense_order.spec.md` OQ-44 (APPROVED; rules R4–R6 *pending OQ-44*). Found 2026-11-10.
**Kind:** money (what is shown as due).
**Facts from the code:**
- Buckets: overdue, due this week (to Sunday), due later this month, no due date; orders due after this month are not shown. "Today" is the UTC date.
- It takes orders not voided and **not completed**, by the order's `due_date`, at the order's `total_amount`. A completed order (bill confirmed, maybe unpaid) is not in it; amounts already paid are not taken off. The invoice's own `due_date` is not used.
- Example: EO-7 for 500.00 was due yesterday, completed, nothing paid → not in "Overdue".

**Suggested answer:** bug — the timeline is "what we still have to pay": not-voided orders not fully paid (no invoice or a draft invoice → the order total; a confirmed invoice → invoice amount − paid, left out at 0), bucketed by the order's `due_date`.
**Alternatives:** (a) intended — the timeline shows open (unfinished) orders; payment follow-up lives in accounting. (b) as suggested, but use the invoice's due date once an invoice is confirmed.

**Answer:** owner, 2026-11-11: suggested answer (not-voided orders not fully paid: order total until the invoice is confirmed, then amount minus paid, grouped by due date). → BUG-2719 Follow-up confirmed by the owner 2026-11-14: an order whose invoice is voided counts at its full order total.

---

## OQ-45. A return's price per unit can be anything the user types — not blocking

**Module:** `app/managers/purchase_order_return_manager.py` and `app/managers/sales_order_return_manager.py` (`validate_and_build_items`; `POST /purchase-orders/{id}/returns/`, `POST /sales-orders/{id}/returns/`) — specs `tests/unit/managers/purchase_order_return_manager.spec.md` / `sales_order_return_manager.spec.md` OQ-45 (APPROVED; rule `validate_and_build_items` R6 written to today's behaviour, *pending OQ-45*). Found 2026-11-14.
**Kind:** money (credit-note amount of a return).
**Facts from the code:**
- Starting a return creates and confirms its credit note at once (purchase: `receivable`, the supplier owes us; sales: `payable`, we owe the customer). Each line = quantity × the return line's unit price.
- The request may send a `unit_price` per line; if not, the order line's price is used. Nothing checks the price sent: not its sign, not against the order line's price.
- Under the 2026-11-14 freeze a credit note cannot be edited afterwards, only voided.
- Verified on `marker_test` (rolled back): `-5`, `0` and `99999` were all accepted as sent.
- Example: PO-0031 bought bearings at 10.00; a return of 1 at 99,999.00 makes the supplier owe us 99,999.00. A price of −5.00 makes a credit line of −5.00.

**Suggested answer:** bug — a return price must be ≥ 0 and ≤ the order line's price (default: the order line's price); otherwise 400, nothing created. 0 stays allowed (goods back, no credit).
**Alternatives:** (a) intended — any agreed credit (restocking fee, goodwill). (b) only refuse negative prices.

**Answer:** owner, 2026-11-17: suggested answer (a return's unit price must be between 0 and the order line's price; otherwise refused). Also confirmed: returnable = received − returned, counted once (BUG-2750 / 2760). → BUG-2785 (purchase), BUG-2786 (sales)

---

## OQ-46. Returning a purchase line that was ordered without a price makes a 0.00 credit line — not blocking

**Module:** `app/managers/purchase_order_return_manager.py` (`validate_and_build_items`; credit note built in `PurchaseOrderService._attach_return_invoice_for_po`) — spec `tests/unit/managers/purchase_order_return_manager.spec.md` OQ-46 (APPROVED; rule `validate_and_build_items` R7, *pending OQ-46*). Found 2026-11-14.
**Kind:** money (credit-note amount of a return).
**Facts from the code:**
- A purchase order line may have no price (`unit_price` nullable). With no price sent in the return, the return line has none and the credit note line is written at 0.00 (`unit_price or 0`).
- Verified: an unpriced line returned with no price → return line `unit_price None`, accepted.
- Sales lines always have a price, so this is purchase only.
- Example: 5 sample rolls ordered unpriced, invoiced separately later; returning 2 with the price empty → the confirmed credit note says the supplier owes us 0.00.

**Suggested answer:** bug — when the order line has no price, the return must send one for that line; otherwise 400 `Enter a return price for line {n} — the order line has no price`, nothing created.
**Alternatives:** (a) intended — 0.00, credit agreed separately. (b) take the price from the order's confirmed invoice line.

**Answer:** owner, 2026-11-17: suggested answer (returning an unpriced purchase line requires a return price). → BUG-2787

---

## OQ-47. Voiding a return's credit note from the invoice page leaves the return as it was — not blocking

**Related:** the 2026-11-14 decision "return credit notes are never editable but can be voided; to correct one, void it and start a new return" (BUG-2733).

**Module:** `app/managers/purchase_order_return_manager.py` / `sales_order_return_manager.py` (`sync_return_paid`), `app/services/account_invoice_service.py` (`void_invoice`) — return manager specs OQ-47 (APPROVED; rule `sync_return_paid` R6 written to today's behaviour, *pending OQ-47*). Found 2026-11-14.
**Kind:** money and stock (a return and its credit note getting out of step).
**Facts from the code:**
- The return page's "Cancel return" voids the credit note **and** marks the return `voided`, which frees the reserved quantity. It works only on a pending return.
- The invoice page's "Void" voids only the invoice; the return is never told. The only link back resets the return's `paid` flag after a payment change.
- So a pending return whose credit note is voided stays pending: its quantity stays reserved (a corrected new return is refused) and it can still be completed, moving the goods with no credit. A completed return whose credit note is voided stays completed: goods gone (or back), nothing owed.
- Example: PR-2026-004 sends 3 motors back for 3,000.00. The accountant voids the credit note to fix the amount, as the owner's rule says; the storekeeper then completes the return: 3 motors leave stock and the supplier owes nothing; the corrected return is refused ("only 0.00 available to return").

**Suggested answer:** bug — voiding a pending return's credit note from the invoice page cancels the return too (→ `voided`, quantity freed), so "void it and start a new return" works. Voiding a **completed** return's credit note is refused (400: the goods have already moved — start a new return or issue a separate credit note).
**Alternatives:** (a) intended — kept apart. (b) only "Cancel return" may void a return credit note (pending returns only).

**Answer:** owner, 2026-11-17: suggested answer (voiding a pending return's credit note also cancels the return; on a completed return the void is refused). → BUG-2788 (check in `AccountInvoiceManager.void_invoice` R3c, as O1)

---

## OQ-48. Starting a return reopens a completed order, which lifts its invoice freeze — not blocking

**Related:** the 2026-11-14 invoice freeze (BUG-2730 … BUG-2732).

**Module:** `app/managers/purchase_order_manager.py` / `app/managers/sales_manager.py` (`reopen_for_return`, called from `start_return`), `app/managers/account_invoice_manager.py` (freeze F2) — noted in the return manager specs OQ-48 / FU-2 (no rule in those managers). Found 2026-11-14.
**Kind:** money (when an order's invoice is frozen).
**Facts from the code:**
- The freeze applies while the linked order is completed.
- Starting a return on a completed order reopens it: a purchase order goes back to `Receiving`; a sales order has `order_completed`, `completed_at`, `completed_by` cleared. It stays open while the return is pending, and after a `replace` return until the goods are re-received / redelivered.
- So once any return is started, the order's own invoice is no longer frozen. For purchase orders the invoice stays protected anyway (revert and void are refused once goods were received, and a return needs received goods); for sales orders it can be voided (cancelling its payments) or reverted and edited.
- Example: SO-2026-018 completed, invoice 12,000.00 frozen. One chair comes back, a return is started, and the 12,000.00 invoice can now be voided.

**Suggested answer:** bug — once an order has been completed, its invoice stays frozen for good, even while a return reopens the order (the freeze reads "was ever completed", not the current stage).
**Alternatives:** (a) a return does not reopen the order at all; returns are tracked on their own. (b) intended — a reopened order's invoice is editable again.

**Answer:** owner, 2026-11-17: suggested answer (a return never reopens a completed order or lifts its invoice freeze). → BUG-2789 (purchase), BUG-2790 (sales) **Refined by the owner 2026-11-17:** while a return is open, a completed order shows a "return in progress" state; the invoice stays frozen and nothing on the order is editable; when the return is completed or cancelled the order goes back to "completed". The order is never reopened to open/editable.

---

## OQ-49. A sales line fulfilled without delivery still adds stock back when returned — not blocking

**Module:** `app/services/sales_service.py` (`complete_return` → `ProductManager.apply_sale_return`) — noted in `tests/unit/managers/sales_order_return_manager.spec.md` OQ-49 / FU-1 (a) (no rule in the return manager). Found 2026-11-14.
**Kind:** stock (what a sales return does to finished-goods stock).
**Facts from the code:**
- A sales line either needs delivery (`requires_delivery = true`: stock leaves when the delivery completes) or is fulfilled directly (`false`: one click, no stock movement).
- Completing a return adds the returned quantity to Product stock for every line with a catalog item, without looking at `requires_delivery`; free-text lines add nothing.
- Example: "Desk lamp × 3" fulfilled directly — 3 lamps leave, stock stays 20. One comes back; completing the return makes stock 21 while 18 are on the shelf.

**Suggested answer:** bug — a return adds stock back only for lines that took stock out (`requires_delivery = true`); a directly fulfilled line's return moves money (credit note) and line quantities only.
**Alternatives:** (a) intended — the goods are physically back, so they are added (and direct fulfilment should start taking stock out). (b) ask the user at completion whether the goods go back to stock.

**Answer:** owner, 2026-11-17: suggested answer (restock only lines that actually took stock out). → BUG-2791

---

## OQ-50. Production adds finished goods with no cost — not blocking

**Module:** `app/managers/product_manager.py` (`apply_production_output`; reached through production batch completion and "post finished goods") — spec `tests/unit/managers/product_manager.spec.md` OQ-50 (APPROVED; rules `apply_production_output` R5–R7 written to today's behaviour, *pending OQ-50*). Found 2026-11-14.
**Kind:** cost (what finished goods are worth).
**Facts from the code:**
- Finished goods carry an average cost (`avg_cost`) that sales deliveries use as cost of goods sold.
- `apply_production_output` can take a unit cost and blend it into the average, but neither caller (`complete_batch`, `post_outputs_to_finished_goods`) passes one, and production batches, batch items and formulas have no cost columns.
- So every batch output adds quantity and leaves the average as it was (empty for a new bucket); the ledger row has no cost. The only way to give finished goods a cost is typing it on the product.
- Example: batch B-17 produces 200 bales of Yarn into an empty bucket → 200 bales at cost "—"; when 50 are delivered, the sale row records no cost.

**Suggested answer:** intended for now — finished goods cost is set by hand until production costing exists; revisit after launch. The unused unit-cost path stays.
**Alternatives:** (a) bug — batch completion values output at the cost of the inputs it consumed (needs input costing on batches). (b) bug — a batch takes a cost per unit when it is completed.

**Answer:** owner, 2026-11-17: intended for now (production output has no cost; cost set by hand); revisit after launch. No bug; rules tagged "revisit after launch".

---

## OQ-51. Finished goods become sellable only by flipping the whole product row — not blocking

**Module:** `app/managers/product_manager.py` (`update_product`, `is_available_for_sale`; `PUT /products/{id}/`) — spec `tests/unit/managers/product_manager.spec.md` OQ-51 (APPROVED; rules `update_product` R9, R10, *pending OQ-51*). Found 2026-11-14.
**Kind:** stock (how finished goods move from storage to sale).
**Facts from the code:**
- Production posts into the **not-for-sale** product row of an item and factory; deliveries take from the **for-sale** row. There is no "move N units to sale" action.
- The product ledger has no for-sale column, so it cannot tell the two rows apart.
- Today, only: (a) tick "for sale" on the not-for-sale row → its whole quantity and cost move at once, no ledger row; if a for-sale row already exists it fails (BUG-2781 makes that a clear 409). (b) Edit both quantities by hand → two unlinked adjustment rows.
- Example: 200 bales produced (not for sale), a for-sale row holds 30. To make 100 sellable the user lowers one row to 100 and raises the other to 130 — two edits; if one fails, stock is wrong.

**Suggested answer:** bug — add a "make sellable" action: move N units from the not-for-sale to the for-sale row of the same item and factory (created if missing), carrying the source's average cost, weighted into the target's; two linked ledger rows (`transfer` out / in). Flipping "for sale" on a row that holds stock is then refused (400, "use Make sellable"); a row at 0 can still be flipped.
**Alternatives:** (a) intended — the flip and hand edits are enough. (b) keep the flip, but flipping onto an existing for-sale row merges into it (quantity added, average weighted) instead of failing.

**Answer:** owner, 2026-11-17: suggested answer (add a "make N units sellable" move with linked ledger rows; refuse flipping a row that holds stock). → BUG-2793

---

## OQ-52. Customer-returned goods come back at today's average cost, or with none — not blocking

**Related:** OQ-49 (whether a sales return adds stock at all).

**Module:** `app/managers/product_manager.py` (`apply_sale_return`; reached through sales return completion) — spec `tests/unit/managers/product_manager.spec.md` OQ-52 (APPROVED; rules `apply_sale_return` R5, R6, *pending OQ-52*). Found 2026-11-14.
**Kind:** cost (value of returned stock).
**Facts from the code:**
- A delivery takes units out of the for-sale row at its average cost at that time (recorded on the `sale` ledger row).
- A completed customer return puts units back at the row's **current** average and leaves the average unchanged; if the row has no average, the return carries no cost; if the row is missing it is created with quantity 0 and no average.
- Example: 10 bales sold at cost 50.00; the row was later emptied, deleted and recreated with no cost; the customer returns 4 → 4 bales at cost "—", and their next sale records no cost although they left at 50.00.

**Suggested answer:** intended while the row has an average (the usual weighted-average shortcut). When it has none, use the unit cost of the latest `sale` ledger row of that item and factory, and set the row's average to it.
**Alternatives:** (a) intended in every case. (b) always value returned units at the cost they left with (that order's delivery `sale` row), weighted into the average.

**Answer:** owner, 2026-11-17: suggested answer (returned goods come back at today's average cost; if none, the latest sale's unit cost). → BUG-2794

---

# Notes for the permissions task

Moved to [`docs/future/permissions.md`](../future/permissions.md) (2026-11-04).

## Answered in chat (no OQ number), 2026-11-04

- **Who may remove a workspace member** (`workspace_manager.spec.md` Q9): owner, 2026-11-04: "Owner + managers now". The owner may remove any non-owner member; a `ground-team-manager` may remove `ground-team` members only; everyone else is refused (403). Fixed now, not deferred to the permissions task. Follow-up, owner, 2026-11-04: "roles will change, put a note down in the permission and flag this for later, for now keep both kinds": `manager` is treated like `ground-team-manager` (may remove `ground-team` members only). Flagged for later in `docs/future/permissions.md`. So the owner removes any non-owner member; `ground-team-manager` and `manager` remove `ground-team` members only; everyone else gets 403. → BUG-1990 (applied 2026-11-04 to `remove_member_from_workspace` R5, R5a)

## Invoice lock after completion (asked in chat, 2026-11-14)

The owner asked whether a finalized invoice on a completed order can still change. Code review found it can (sales, expense, work orders via revert / void; credit notes via revert; POs via `void_purchase_order`). Owner answers, 2026-11-14:
- Once an order is completed (any type), its invoice is **fully frozen**: no revert, void or delete; payments may still be recorded or voided; mistakes are fixed with a credit note / return. → BUG-2730, BUG-2731, BUG-2732
- Return credit notes are **never editable** after creation: to correct one, void it and make a new return. → BUG-2733
- A **completed PO (or one with goods received) cannot be voided**; use a return. → BUG-2734
- Related, decided with the fix: dead `locked` status (BUG-2735), misleading revert advice (BUG-2736). Already logged: BUG-609, 606, 631, 621, 601.
- Follow-up, owner 2026-11-14: the three edits still allowed on a confirmed invoice (due date, allow payments, payment-lock reason) **stay editable** after the order is completed; they don't change the invoice's money.

## Answered in chat, 2026-11-19

- **Replacement goods on a completed purchase order** (`purchase_order_return_manager.spec.md` FU-2): the return gets its own "receive replacements" step that adds the goods to stock; the purchase order stays completed and its invoice frozen. → BUG-2810
- **First ledger cost when production creates a new product record** (`product_manager.spec.md`, PRDM-PO-20 / R8): the ledger shows "before" as empty (no previous cost); "after" is the unit cost. → BUG-2811

## Answered in chat, 2026-11-21 (purchase, transfer and work order managers)

- **OQ-53 (OQ-PO-1, stock): editing a PO line's received quantity.** Answer: receiving happens only through "Receive goods". The line edit can change only the quantity ordered and the price; `quantity_received` is refused there. → `purchase_order_manager.spec.md`
- **OQ-54 (OQ-PO-2, money): deleting a PO whose invoice is finalized.** Answer: a finalized invoice blocks delete, and the PO can only be voided. A draft invoice is removed together with the PO. → `purchase_order_manager.spec.md`
- **OQ-55 (OQ-T1, order workflow): changing required approvals after approving started.** Answer: the change is allowed, but it wipes every approval given so far, and everyone approves again. (The owner chose this over the suggested lock.) → `transfer_order_manager.spec.md`
- **OQ-56 (OQ-W1, money): cost/account edits on a draft work order that has an invoice.** Answer: refused while the order has an invoice that isn't voided ("Delete the draft invoice first"). → `work_order_manager.spec.md`
- **OQ-57 (OQ-W2, stock): removing the machine from a draft with Install/Replace/Borrow parts.** Answer: refused while such parts are on the order. Switching to another machine is still allowed. → `work_order_manager.spec.md`
- **OQ-58 (OQ-W3, order workflow): approvals after work has started.** Answer: frozen once work starts ("Work has started — approvals can no longer change"). → `work_order_manager.spec.md` Confirmed by the owner 2026-11-21: `required_approvals` is frozen too once work starts (BUG-2931).
- **OQ-59 (OQ-W4, stock value): the value of a replaced part in damaged stock.** Answer: zero value, which is today's behaviour. Not a bug. → `work_order_manager.spec.md`

## Answered in chat, 2026-11-21 (money services batch 1)

- **OQ-60 (OQ-AIS-1, money and order workflow): finalizing an expense/work order invoice early from the invoice page.** Answer: refused on the invoice page. These invoices are finalized only by completing the order (which checks approvals). The message names the order: "This invoice is finalized when expense order EXP-2026-009 is completed." → `account_invoice_service.spec.md`
- **OQ-61 (OQ-IP-1, money): the same payment sent twice is recorded twice.** Answer: a one-time code per payment form (a client idempotency key plus a unique index). Sending the same form twice keeps only the first payment; two separate forms are both kept. The same pattern applies to starting a gateway checkout and to the future subscription portal. → `invoice_payment_service.spec.md`, `payment_transaction_service.spec.md`, `docs/future/subscription-payments.md`

## Answered in chat, 2026-11-21 (services batch 2)

- **OQ-62 (OQ-EOS-1, money and order workflow): voiding an expense or work order whose invoice is already finalized.** Answer: the void is refused with "This order's invoice is already finalized. Void the invoice on the invoice page first, then void the order." It covers expense orders and work orders (`work_order_manager.spec.md` FU-1 (b)). → `expense_order_service.spec.md`, `work_order_service` (when described)

## Answered in chat, 2026-11-22 (services batch 3)

- **OQ-63 (OQ-POS-1, money): receiving a `replace` return's replacements and its credit note.** Answer: option (a). Receiving replacements settles the credit note. **It must be fully recorded (owner):**
  - a non-cash payment entry of method "settled by replacement" on the credit note, for qty × return price rounded half up, with its date, the person who received the goods and a link to the receipt;
  - an event on the return and an activity entry on the PO;
  - the stock-in ledger row linked to the return.

  A partial receipt settles only its own share, and the rest stays owed. A settlement entry is never deleted, only voided with a reason, like any payment. → `purchase_order_service.spec.md`
- **OQ-64 (OQ-SS-1, money and order workflow): delivering a `replace` return's replacement and its credit note.** Answer: option (a). The credit note is still created when the return starts. Once every replaced unit is delivered, it is settled. It must be recorded the same way as OQ-63:
  - a "settled by replacement" entry with date, actor and a link to the delivery;
  - a return event;
  - the delivery record.

  If money was already refunded on that credit note, nothing is cancelled automatically: a warning is shown and staff decide. → `sales_service.spec.md`
- **OQ-65 (OQ-WOS-1, money): creating an invoice for a work order with no cost.** Answer: option (a). "Create invoice" is refused until the order has a cost above 0, with "Set the work order's cost before creating an invoice." Free outside work has no account and gets no invoice. → `work_order_service.spec.md`


## Answered in chat, 2026-11-26 (help tickets after the merge of main)

- **OQ-66 (permissions and workflow): who may change a help ticket's status after the new pending → opened → closed workflow.** The merged code (41d5ac1) lets only platform admins change status. Answer: **keep OQ-8**. The workspace owner and ground-team managers may change status too, along with platform admins, following the same transition table (pending→opened, opened→closed, closed→opened). Anyone else (for example a plain member who raised the ticket) is refused with 403. The admin-only rule in the code is a bug. → `help_ticket_manager.spec.md`, `help_ticket_service.spec.md`, the help-ticket endpoints
