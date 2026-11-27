# Future work: notifications

Notes for the coming notifications feature, collected during the unit-testing sweep (as of 2026-11-04, source commit `e48a092`).
Written for the owner and for the developer who builds the feature. Every claim cites its source; "(guess)" marks a guess and "Suggestion:" marks an idea nobody has decided.

## Today

**What a notification is**
- One row per person per event in the `notifications` table, inside one workspace: recipient, optional actor, kind, the record it is about (`entity_type` + `entity_id`), what produced it (`source_type` + `source_id`), a short `preview`, read flag and read time (`app/models/notification.py:18-51`).
- The record it points at has no foreign key; a notification about a deleted record stays listed, by design ("logs are history") (`tests/unit/dao/notification.spec.md` Q2).
- Kinds and sources are fixed strings in `app/core/notification_types.py`: `approval_assigned`, `approval_pending`, `section_confirm`, `invoice_action`, `mention`; sources `approver`, `order`, `section`, `invoice`, `discussion` (`tests/unit/core/notification_types.spec.md` R1, R4).
- The web app also knows `low_stock`, `project_update`, `maintenance`, `system`; the backend never produces them (`notification_types.spec.md` Notes; grep of `app/` for producers below).
- In-app only: there is no email, SMS or mobile push sending anywhere in `app/` (grep for smtp / send_email / fcm / firebase found nothing).

**What creates notifications (the only two producers)**
- Discussion mentions: a message containing `@[<profile id>]` notifies each mentioned active member (`app/services/discussion_service.py:76-91` → `app/services/notification_service.py:66-94`).
- Order approvals, through `app/services/approval_notification_service.py` (no spec yet), for purchase, transfer, expense and work orders only (`ORDER_PREFIX`, lines 22-27; summaries lines 81-104):
  - approver added → `approval_assigned` to that approver; then either `approval_pending` to the other pending approvers or `section_confirm` to the order's creator (`handle_add_approver`, lines 360-400);
  - order edited → `section_confirm` to the creator when approvals were reset or the order stopped being ready; `approval_pending` when it became ready (`handle_order_update_notifications`, lines 403-447);
  - invoice drafted / confirmed → `invoice_action` to all approvers, pending approvers and the creator (`notify_invoice_action`, lines 289-357).
- Callers: `purchase_order_service.py` (lines 294, 340, 408, 1341), `transfer_order_service.py` (53, 248, 307), `expense_order_service.py` (64, 299, 536, 559, 596), `work_order_service.py` (178, 413, 461, 564, 595), `account_invoice_service.py` (462, 478).
- Sales orders send nothing (BUG-1205, below).
- Every producer writes only to **active** members of the workspace; anyone else is silently skipped (`notification_service.py:78-82`; `approval_notification_service.py:57-59`).

**The inbox API** (`/me/notifications`, `app/api/v1/router.py:155`)
- `GET /me/notifications/`: your notifications in the current workspace, newest first, with `total` and `unread_count`; `limit` 1–200 (`app/api/v1/endpoints/notifications.py:53-69`).
- Each row gets a label for its record (order number, project name, …) by one lookup per row (`notifications.py:37-42`; `app/utils/notification_entity_label.py`).
- `POST /me/notifications/read/` with `{"ids": [...]}` or no ids (= all) marks them read and commits (`notifications.py:88-96`; `notification_service.py:55-64`).
- You only ever see and mark your own rows in your current workspace (`notification_service.spec.md`, "Permission checks").

**Live updates (the stream)**
- Writing a notification also sends `pg_notify('user_notifications', {recipient, workspace, id})`, delivered when the transaction commits (`app/dao/notification.py:73-83`).
- `GET /me/notifications/stream` is a Server-Sent-Events stream; each open stream holds its own Postgres connection that `LISTEN`s on that one platform-wide channel and forwards only the id of notifications for this user and workspace (`app/services/notification_stream.py:16-49`; `notifications.py:72-85`).
- The browser then fetches the notification through the normal list (`notification_stream.spec.md` Overview).
- A keep-alive `: ping` is sent when no message at all arrived for 30 s (`notification_stream.py:26-29`).

**Mention details**
- The preview is the first 200 characters of the message with `@[id]` turned into `@Name` (`notification_service.py:17-31`).
- Mentions are written in the same transaction as the message and committed with it (`discussion_service.spec.md` D1).

## Decided already

- **Mention preview leaks names (BUG-1534, HR-16):** a preview names only people with a membership in the workspace; any other id reads `@User <id>` (`notification_service.spec.md` `humanize_mention_preview` R5).
- **Self-mention (BUG-1535):** the author is never notified of a mention in their own message (`notification_service.spec.md` Q1, `fan_out_mentions` R4).
- **Non-ASCII digits (BUG-1536):** only ASCII `0-9` inside `@[…]` make a mention, in the preview and the extractor alike (`notification_service.spec.md` P1; `discussion_service.spec.md` `_extract_mentions` R2).
- **Mentions on private records (R9a, BUG-1879; consequence of OQ-5):** on a private project, its component, or a help ticket, a mentioned person who may not open the record gets no notification and no preview; the message is still stored (`discussion_service.spec.md` `create` R9a).
- **Private threads (OQ-5, BUG-1867, BUG-1868):** posting on such a thread is refused (404) for people who may not open the record, so no notification is sent either (`discussion_service.spec.md` `create` R11, R11a, R11b).
- **Stream bugs (decided by Claude under delegation, 2026-11-04):**
  - BUG-1802: a message that is JSON but not an object is skipped; today it ends every open stream on the platform.
  - BUG-1803: a failure while starting to listen closes the connection.
  - BUG-1804: a ping whenever 30 s pass without a frame to *this* client, measured with `time.monotonic()` (`notification_stream.spec.md` R5, R5a).
- **Inbox bugs (decided by Claude under delegation, 2026-11-03):**
  - BUG-1412: ties ordered by `id` descending.
  - BUG-1413: `read_at` is the true UTC moment.
  - BUG-1414: `{"ids": []}` marks nothing (`tests/unit/dao/notification.spec.md` R4, R3, R2).
- **Fallback labels (BUG-200):** a record that cannot be found shows `"<type name> #<id>"` (e.g. `purchase order #5`), never `purchase_order-5` (`notification_entity_label.spec.md` R3a).
- **Sales order approvals (BUG-1205, owner 2026-11-01):** sales order approvers are notified like the other four order types (`tests/unit/dao/sales_order_approver.spec.md` Q2, FU-3).
- **Notifications about deleted records stay listed** (decided by Claude under delegation; `notification.spec.md` Q2).
- **Member removal (OQ-6, BUG-1883):** removing a member takes them off open work orders' planned workers and writes one event per order (e.g. `assignee_removed`).
  - The precedents BUG-1201 (approvers) and BUG-1280 (project members) also remove the person on leaving.
  - These are order or project events, not notifications; whether anyone is notified is open (below).
- **Constants tidy-up (not a bug):** the mention code should use `MENTION` / `SOURCE_DISCUSSION` instead of literal strings (`notification_types.spec.md` FU-1).

## Known bugs and gaps that touch it

- Open bugs, all with tests written to the intended behaviour (strict or non-strict xfail): BUG-200, BUG-1205, BUG-1412, BUG-1413, BUG-1414, BUG-1534, BUG-1535, BUG-1536, BUG-1802, BUG-1803, BUG-1804, BUG-1867, BUG-1868, BUG-1879 (`docs/testing/bugs.md`).
- BUG-1883, BUG-1201, BUG-1280: workspace manager removal rules, no spec yet. A removal can change who is a pending approver, so it touches approval notifications (guess).
- BUG-740: saving an expense order without changes resets approvals, and the approvers are then asked to approve again (`expense_order_manager.spec.md` Q14).
- `approval_notification_service.py` has **no spec**. Things read in the code, not run:
  - the actor is not left out of `invoice_action` recipients (lines 340-357);
  - self-assignment is not excluded in `approval_assigned` (lines 200-230);
  - the preview's order reference uses the database id (`PO-12`), not the order number (lines 30-34), while the list label shows the business number (`notification_entity_label.spec.md` R1).
- The order services that call it (purchase, transfer, expense, work order, account invoice services) have no service spec yet. Which events notify is therefore not pinned by any test.
- The notifications endpoint (`app/api/v1/endpoints/notifications.py`) is integration-only. It makes one label query per row, up to 200 per page (`notification.spec.md` FU-1; `notification_service.spec.md` FU-2).
- Capacity: each open stream holds one worker thread and one database connection outside the pool, and filters every workspace's messages in Python (`notification_stream.spec.md` FU-1).
- A member removed from the workspace keeps an open stream until it disconnects; membership is checked only when the stream opens (`notification_stream.spec.md` FU-2, "Permission checks").
- A notification created while a browser is reconnecting is not pushed (it shows on the next list fetch) (`notification_stream.spec.md` P1 and Q2 examples).
- The preview is cut at 200 characters *before* names are filled in, so a token at the cut shows as `@[5` (cosmetic) (`notification_service.spec.md` FU-1 (c)).
- `notification_entity_label.spec.md` Overview says discussion mentions are the only producer; the approval service also writes notifications (`approval_notification_service.py:60`). It is a doc slip in the spec, and the rules there are unaffected.
- The model declares `read_at` / `created_at` as plain `DateTime` while the database columns are `timestamptz` (`notification.spec.md` "Verified by running"). Same root cause as BUG-1413.

## Open questions for the feature

- Which events should notify beyond approvals and mentions? The web app already knows `low_stock`, `project_update`, `maintenance`, `system`, and the backend produces none of them (`notification_types.spec.md` Notes).
- Should removing a member (OQ-6 / BUG-1883, BUG-1201, BUG-1280) notify anyone: the person removed, the order's creator, the remaining approvers when an order becomes ready?
- Should an actor ever be notified of their own action (self-assigned approver, own invoice action)? BUG-1535 settled this only for mentions.
- Email, push or digest delivery: is any channel besides the in-app bell wanted? None exists today (grep of `app/`).
- Per-user preferences (mute a kind, mute a record): nothing exists today.
- Retention: notifications are never deleted. Should old read ones expire? Nobody has decided.
- Who may receive a notification once the permissions feature lands? R9a filters mentions by record visibility. Approval notifications follow assignment, not visibility; is that enough? See `docs/future/permissions.md`.
- Should a notification about a record the person can no longer open still be listed? Q2 keeps notifications about deleted records; access lost is a different case.
- Should the order reference in approval previews show the business number (`PO-2026-015`) rather than `PO-<id>`?
- Cross-workspace: a person in several workspaces sees only the current workspace's bell. Is an "all workspaces" unread count wanted? (guess at a need; nothing in the code or specs asks for it)

## What the tests already pin down

Each module below has an APPROVED spec, a cases file and a PASS verdict; read the spec for intended behaviour and the cases for concrete examples.
- `tests/unit/dao/notification.spec.md` + `.cases.md`: storage, `pg_notify` payload and key order, list order and counts, mark-read rules (R1–R4).
- `tests/unit/services/notification_service.spec.md` + `.cases.md`: mention fan-out (who gets one, dedupe, actor excluded), preview text rules R1–R8, mark-read commit.
- `tests/unit/services/notification_stream.spec.md` + `.cases.md`: exact SSE frames, matching rule (user **and** workspace), skip rules, keep-alive clock, cleanup (R1–R10). Unit tests use fakes; real delivery is integration-only.
- `tests/unit/services/discussion_service.spec.md` + `.cases.md`: mention extraction and when mentions are sent (`create` R9, R9a, R10, R11–R11c).
- `tests/unit/core/notification_types.spec.md` + `.cases.md`: the kind and source strings (R1–R5).
- `tests/unit/core/notification_channels.spec.md` + `.cases.md`: the channel name and that it is a valid unquoted identifier (R1–R3).
- `tests/unit/utils/notification_entity_label.spec.md` + `.cases.md`: the label shown for each record type and its fallback (R1–R9).
- `tests/unit/dao/sales_order_approver.spec.md` Q2 / FU-3: the intended sales-order approval notifications (BUG-1205).
- `tests/unit/dao/workspace_member.spec.md`: the "active members" read that both producers use to pick recipients.
- **No spec yet:** `app/services/approval_notification_service.py`; the order services that call it; `app/managers/workspace_manager.py` (member removal); the notifications endpoint. When reached, their specs should become the reference for which events notify whom.

## Ideas for later

- Suggestion: one place that decides "may this person see this record", used both to filter recipients and to filter the list. The permissions notes already ask for this shared rule (`docs/testing/owner-questions.md`, notes for the permissions task).
- Suggestion: put the record's label (and the business order number) in the notification when it is created, instead of one lookup per row on every list call (`notification.spec.md` FU-1).
- Suggestion: on (re)connect, the stream sends a "since" marker, or the browser refetches unread, so notifications created during a reconnect are not missed (`notification_stream.spec.md` Q2 example).
- Suggestion: a stream that ends itself when the member is removed, or re-checks membership periodically (`notification_stream.spec.md` FU-2).
- Suggestion: for scale, a per-workspace or per-user channel, or a single shared listener that fans out in-process, instead of one database connection per open browser tab (`notification_stream.spec.md` FU-1).
- Suggestion: cut the mention preview after names are filled in (`notification_service.spec.md` FU-1 (c)).
- Suggestion: use the constants from `notification_types.py` everywhere, and add the four kinds the web app already knows once they have producers (`notification_types.spec.md` FU-1).

## Added during the sweep

- 2026-11-04, discussion service tests (Revision 4), read in code:
  - Only active workspace members get mention notifications. A platform admin, who can open any help ticket, is never notified; neither is a workspace owner with no membership row.
  - Replies notify nobody unless someone is mentioned: the parent's author and the thread get nothing. *Suggestion:* notify the parent's author and thread participants.
  - Access is checked only when a notification is created. Someone who later loses access keeps the preview and a link to a record they can't open. *Suggestion:* check access again when a notification is read or opened.
  - Previews are the first 200 characters with names filled in, and those names can be from other workspaces (BUG-1534, open). Mentioning yourself notifies yourself (BUG-1535, open).
- 2026-11-04, help ticket / stamp tests:
  - Help tickets send nothing today. *Suggestion:* notify platform support on create, and the creator when someone else closes or reopens (`closed_by`, `closed_at` exist). Send after commit; a failed send must not undo the change. Close times depend on the database time zone until BUG-1577 is fixed.
  - Stamps: after BUG-1713 a failed delete of an old stamp image logs a WARNING naming the file; a natural hook for an admin alert about orphaned Cloudinary files.
- 2026-11-04, notification stream: the BUG-1804 keep-alive fix must read the clock through the module's `time.monotonic` (tests patch `ns.time`), recording the time at each yield; importing `monotonic` by name bypasses the tests.
- 2026-11-04, discussion round 3 verifier: mention previews are built before the access filter, so email/push must filter first; nothing says what happens to notifications already sent when a project later becomes private.
- 2026-11-04, profile / help ticket / stamp verifier:
  - Ticket close / reopen as triggers: closing an already-closed ticket must not fire (BUG-1576); `closed_at` is off by the database time zone until BUG-1577.
  - Delivery and lookup by email should use `lower(trim(email))` (BUG-1860, BUG-1861); invitations already store lower case.
  - Anything that embeds stamps (e.g. in a notification) must use the server-built url (BUG-1866); rows saved before the fix keep the client url and maybe a foreign `public_id`, so run a repair job before notifications show stamps.
- 2026-11-04, `workspace_manager` spec (`tests/unit/managers/workspace_manager.spec.md`; read, not run):
  - Invitations are never sent. `create_invitation` writes the row and an audit entry, and the web app shows the token with "Share this token with <email>" (`frontend/src/pages/newpages/ManagementPage.tsx:472`). **Suggestion:** an invitation email (or an in-app notice when the email already has an account) carrying the accept link; send after commit, and do not undo the invitation if sending fails.
  - Nobody is told when an invitation is accepted, cancelled or superseded (BUG-1874 cancels the other pending invitations to that email), or when a member is removed. **Suggestion:** notify the inviter / owner on accept; notify the removed person (in-app notices are workspace-scoped and they lose access, so this needs email); notify the owner on removal by someone else.
  - Removing a member (BUG-1201, BUG-1280, BUG-1883) deletes their pending approvals, project memberships and open work order assignments, with one order / project event each (`approver_removed`, `member_removed`, `assignee_removed`). These are timeline events, not notifications. **Suggestion:** tell each affected order's creator that an approver left, because the order can no longer pass until a new approver is added (BUG-755 and siblings).
  - The workspace audit log (`workspace_created`, `member_added`, `member_removed`, `invitation_sent`, `invitation_accepted`, `invitation_cancelled`) has no reader (workspace audit log spec Q1, intended). It is the natural source for an "activity" feed of membership changes.
- 2026-11-04, `project_manager` spec (read): adding someone to a project, removing them, and making a project private notify nobody. Only the project's activity log records it (`member_added`, `member_removed`, `visibility_updated`). **Suggestion:** notify the person added or removed. When a project becomes private, notifications already sent about it (mentions, previews) stay with people who can no longer open it (see the discussion note above).
- 2026-11-04, project / help ticket manager tests:
  - Projects: every state change already writes an activity row via `log_event` (created, updated, status_updated, visibility_updated, member_added, member_removed, deleted); member events carry user id and name, visibility events old and new values. Natural hook, but `log_event` accepts another workspace's project id (BUG-1192), so don't trust it until fixed.
  - Help tickets: hooks would be `create_ticket` and the status branch of `update_ticket`; notify only on a real state change (after BUG-1576) and after the service's commit.
- 2026-11-04, workspace_manager tests: nothing is sent today. Accept writes audit rows `member_added`, `invitation_accepted` (then superseded `invitation_cancelled` after BUG-1874). After BUG-1201 / 1280 / 1883, removal writes `approver_removed`, `member_removed`, `assignee_removed` events: natural hooks for member notices. Invitations store the email lower-cased; the audit row keeps it as typed.

- 2026-11-04, `attachment_manager` spec: becoming ready writes `attachment_added` ("Attached <file>") and deleting writes `attachment_removed` on the parent's activity log (orders, projects, components, machines, invoices; not items, tickets or scratch). Natural hooks; fire only after BUG-2093 / BUG-2098 so retries and never-ready uploads are right, and only to people who may open the record (BUG-1870, BUG-1950, BUG-2091).
- 2026-11-04, `attachment_markup_manager` spec: marking a document notifies nobody; the markup history (`markup_saved`, `markup_updated`, `markup_cleared`, with pages and `session_id`) is the natural hook, e.g. tell the uploader when someone else marks their file. Notify only on a real change (after BUG-2118) and only people who may open the record (BUG-2115).
- 2026-11-04, same spec: the desktop learns that the phone finished only by polling `GET /mobile-upload/sessions/{id}`. *Suggestion:* a per-user stream event "phone upload ready" (session id) on `confirm_staging_upload`, sent after commit; polling stays as fallback.
- 2026-11-04, attachment family tests: "Attached" / "Removed" lines go through each record type's `log_event`; items, help tickets and scratch uploads have no activity log, and the mobile flow emits nothing of its own. Fix BUG-2093 and BUG-2098 first so these lines match real attach/remove one to one, and BUG-2118 so an unchanged markup save doesn't notify.

- 2026-11-04, `workspace_service` spec: changing a member's role (or position) notifies nobody, the member included; BUG-2253 adds an audit row `member_role_changed`, which is the natural hook (send after commit, only on a real change).
- 2026-11-04, `project_component_{task,note,item}_service` specs: completing or reopening a component task, adding a note, and planning or removing component items write project events but notify nobody; tasks have no assignee.
- 2026-11-04, `project_service` / component specs: `GET /projects/{id}/events/` validates event metadata with `ProjectEventMetadata` (`changes`, `user_id`, `user_name` only), so `component_id`, `component_name`, `task_id`, `note_id`, `item_id`, `qty` stored by component, task, note and item events are dropped from the response (the rows keep them). Any notification or activity view built on these events needs them exposed.
- 2026-11-05, attachment / markup service tests: markup events (`markup_saved` / `markup_updated` / `markup_cleared`, with `session_id`) and the "Attached" / "Removed" activity entries are committed by the service, so a notification belongs after the service's commit, never inside the manager. Fix BUG-2118 first (unchanged markup saves write `markup_updated`). Once BUG-2095 is fixed a failed confirm also commits its failure record, which could carry an "upload failed" notice; the mobile QR flow emits nothing of its own.
- 2026-11-05, attachment / mobile service tests: after a delete commits, the order is Cloudinary delete, then re-read, then response; a notification hook there must not be able to stop the delete. Failed deletes after commit log a WARNING naming the `public_id`; an admin alert can key on that.

- 2026-11-06, work order template specs: nothing is sent when someone is made a template's default approver, nor when drafts are generated from templates (the work orders get `created_from_template` and `approver_added` events through `WorkOrderManager`). Natural hooks: notify each approver once per generated order (after the service's commit), and fix BUG-2343 first so a double run cannot notify twice. Approvers skipped because they are no longer active members are skipped silently (manager FU-1).
- 2026-11-06, financial audit log specs: every change to an account, invoice or payment already writes one `financial_audit_logs` row in the same transaction (`log_financial_audit`, with `entity_type`, `action_type`, `related_entity`, before/after `changes`). It is the natural feed for money notifications (payment recorded / voided, invoice status changed). Send after the service's commit; order by `performed_at`, then `id` (BUG-2370); read times as UTC (BUG-2371, BUG-2372).
- 2026-11-09, template tests: drafts log a `created_from_template` event (hook for a "drafts planned" notice). After BUG-2344, templates skipped by Plan day are only logged as a WARNING, so an alert would need a record of them. Order templates write no events.
- 2026-11-09, `work_order_template_manager` verifier: an approver silently dropped when a generated work order copies the template's approvers (no longer an active member) is an alert candidate (tell the template's creator or the owner that the order has fewer approvers than the template), once work order template manager FU-1 (a) is settled.

- 2026-11-10, approval notification service spec (`tests/unit/services/approval_notification_service.spec.md`, APPROVED; the spec now pins today's behaviour, replacing the "no spec yet" notes above). Verified on `marker_test`:
  - Nobody is left out for being the actor: a self-assigned approver gets `approval_assigned`; the creator gets `section_confirm` for their own edit or approver add; a pending approver who makes the order ready gets `approval_pending`; the actor gets their own `invoice_action`. *Suggestion:* leave the actor out everywhere (as BUG-1535 did for mentions).
  - References are `PO-<database id>`, not the order number (still open above).
  - Wrong or vague gap texts: a transfer order with source = destination is told "Add at least one item before approvals can proceed" even when it has items; an expense order not ready only because a line has a blank description or quantity 0 gets the generic "Complete remaining details…". *Suggestion:* say "Source and destination cannot be the same" / "Every expense line needs a description and a quantity above 0", the texts the order managers already use when refusing approval.
  - Repeats: every approver added to a ready order re-sends `approval_pending` to all other pending approvers; every approver added to a not-ready order re-sends `section_confirm` to the creator. *Suggestion:* send `approval_pending` once per "became ready", and `section_confirm` only on a change of readiness.
  - "Invoice confirmed on PO-… — order locked" is also the text for expense and work orders, and for any action other than `"draft"`.
  - Invoice notices go to all approvers only when the order requires approvals (`required` > 0); with `required_approvals = 0` (or negative, which the schemas accept) approvers who already approved hear nothing. *Suggestion:* the same recipients in both cases.
  - Order state is not looked at: adding an approver to a completed or voided order still sends "ready for your approval".
  - All of this runs inside the order's transaction: a failure here undoes the order change. *Suggestion (as for help tickets):* write notifications after the service's commit, so a failed notice cannot undo the business change.
  - Once BUG-755 / BUG-1202 / BUG-1203 are fixed, an order with no approvers shows "0 of 1 approval(s) collected" and counts as needing approval, but there is nobody to notify; consider telling the creator "add an approver".
  - BUG-1205 (sales orders) is applied in the spec; readiness for sales was chosen by analogy with purchase orders (`order_info_confirmed` and `items_confirmed`), and the gap text "Confirm Order info, Order items before approvals can proceed" (decided under the reviewer's delegation; owner did not object, 2026-11-10).
  - Two concurrent order edits that both make an order ready each send `approval_pending` (no row lock; spec FU-1, for the purchase / transfer order services).
- 2026-11-10, item summary service spec: the summary computes a per-machine "low stock" flag (`qty < req_qty`) and the item's outstanding purchase quantity, but nothing alerts on either. Natural hooks: a low-stock notice when a stock movement takes a machine below its wanted quantity (send after the movement's commit, once per crossing, not on every read), and a "purchase overdue" notice keyed on open lines (wait for OQ-32: which lines count as open; voided ones never, BUG-2521).
- 2026-11-10, auth service spec (D9): **password reset email.** `POST /auth/forgot-password/` answers "If an account with that email exists, a password reset link has been sent." but stores no token and sends nothing; `POST /auth/reset-password/` always answers 501. The web app has both pages. Needed: a `password_reset_tokens` table (user, token hash, expires_at = 1 hour, used), the email with the link, one-time use, and on success revoke all refresh tokens (as the owner's reset does). Look the account up with `lower(trim(email))` (BUG-1860). Keep the same answer whether or not the account exists, and the 5-per-minute limit.
- 2026-11-10, auth service spec: **password changed by the owner.** `reset_password_by_admin` returns the message "User should be notified of password change via email." and sends nothing. The member only finds out when their sessions stop working. Notify the member (email, and an in-app notice at next login) naming who reset it and when (the audit row of BUG-2569 has both). See OQ-34 first: the suggested answer limits who can be reset.
- 2026-11-10, auth service spec: **welcome / account emails.** Registration sends nothing (only the in-response message "Welcome <name>! …"). Ideas: a welcome email with the workspace and its 14-day trial end; and, if the sign-up form should stop revealing that an email is registered (D7, kept intended today), "someone tried to register with your address" mailed to the existing account instead of the on-screen error.
- 2026-11-10, money DAO tests: DAOs emit no events and never commit; "order created" / "delivery created" notices must hook in at the manager or service, after commit.
- 2026-11-10, auth tests: forgot-password stores and mails nothing and `reset_password` always answers 501 (D9); needs a stored, single-use, 1-hour token sent by email (rewrite AUTH-FP-02 and RP-01 then). The admin reset says the user "should be notified via email" but nothing is sent; after BUG-2569 its audit row is the natural trigger. No welcome / "you joined" mail on registration or invitation accept.
- 2026-11-10, approval notification tests: once BUG-1202/1203/755 are fixed, orders with no approvers will send creators section-confirm notices that no approver can act on; decide whether that notice is wanted. A real BUG-1205 fix should reuse `SalesManager.approval_summary`.
- 2026-11-21, `purchase_order_manager` spec (read in code):
  - The approver-added notice ("ready for your approval") is still sent for completed or voided POs (approval notification spec FU-3); it stops once BUG-2881 / BUG-2882 refuse those changes.
  - The draft-invoice and section-reset notices come from `PurchaseOrderService._sync_draft_invoice_for_po`, not this manager; BUG-2888 (draft invoice deleted with its PO) should not send an "invoice changed" notice for the deleted draft.
- 2026-11-21, `transfer_order_manager` spec (read in code):
  - Changing "Required approvals" notifies nobody. `handle_order_update_notifications` reacts only to a change in readiness (route + lines), and the transfer service reads no `_approvals_reset` marker (the expense and work order services do). Once BUG-2903 (OQ-55) wipes approvals on such a change, approvers are not told to approve again. *Suggestion:* on an `approvals_reset` the service sends the "approvals were reset — re-approve" notice, as expense and work orders do.
  - Nothing is sent when an approver is removed, an approval is withdrawn, or the order is completed. *Suggestion:* tell the creator and approvers on completion; tell the remaining approvers when a withdrawal makes approvals no longer met.
  - Approval notices go out via `handle_order_update_notifications` and `handle_add_approver` (service). BUG-2897 stops "approver added" notices on completed orders, because the add is refused.
- 2026-11-21, `work_order_manager` spec (`tests/unit/managers/work_order_manager.spec.md`):
  - Once BUG-2915 is fixed, the service's "approvals were reset — re-approve" notice (sent when `_approvals_reset` is true) stops firing on edits that change nothing. Today sending a details field with its current value resets approvals and notifies the approvers.
  - `create_work_order` always logs `auto_approved` first, then `approval_revoked` as soon as approvers are added. Any event-driven notification would send a false "approved" then "revoked" pair for every new order with approvers. *Suggestion:* notify from the final approval state after the create transaction, not per event.
  - After BUG-2931, approvers can't change once work has started, so no approver notices are needed for in-progress orders.

- 2026-11-21, account invoice service describe ([spec](../../tests/unit/services/account_invoice_service.spec.md)):
  - Finalizing from the invoice page notifies the people on a PO, and after BUG-2965 a sales order's approvers and creator. Nobody is notified on an invoice void (any order type), a revert to draft, a resync or a draft delete. Candidate: notify the order's people when its invoice is voided (BUG-2966 releases the order at that moment).
  - One PO finalize from the invoice page writes two `invoice_confirmed` PO log entries ("Draft invoice confirmed after invoice finalized" and "Invoice #<id> confirmed — order locked"); the sales side avoids this. Event-driven notifications would show it twice; clean up with the log redesign.
  - After BUG-2969 ([OQ-60](../testing/owner-questions.md)) the invoice page's expense-order "invoice confirmed" notification can no longer fire (dead-code checklist); expense orders notify on completion in `expense_order_service` only. Today the expense order notified is the newest one linked to the invoice, voided ones included.
- 2026-11-21, account service describe ([spec](../../tests/unit/services/account_service.spec.md)): nothing in the account module notifies anyone. Candidate: alert the owner when a supplier's bank details change (fraud guard against "please pay our new account" scams), after the commit, naming who changed it, old and new values masked (audit snapshot BUG-872).
- 2026-11-21, invoice payment service review ([spec](../../tests/unit/services/invoice_payment_service.spec.md)): recording or voiding a payment notifies nobody. Candidates: tell finance or the invoice's creator when a payment is voided, and when an invoice becomes fully paid. Sent after the commit, never again when a repeated key returns the first payment (BUG-3002 R9b, [OQ-61](../testing/owner-questions.md)).
- 2026-11-21, payment transaction service review ([spec](../../tests/unit/services/payment_transaction_service.spec.md)): no notification is sent today. Candidates: a payment reaching a final status (`VALIDATED_SUCCESS`, `VALIDATED_FAILED`); a `RISK_HOLD` waiting for the owner; a refused start (`INIT_FAILED`, BUG-019). Each after the commit, once per change, never on `duplicate_ignored` or a repeated `Idempotency-Key` (BUG-3023, [OQ-61](../testing/owner-questions.md)); a send failure is logged and ignored.
- 2026-11-21, expense order service describe ([spec](../../tests/unit/services/expense_order_service.spec.md)):
  - An edit to order details that wipes approvals tells only the creator, never the approvers whose approval was wiped. A line add / edit / remove that wipes approvals sends no notice at all (same kind of gap as transfer OQ-55).
  - Voiding (approvals cleared, draft invoice deleted), withdrawing an approval and removing an approver notify nobody.
  - When approvals are met but the order has no account, no draft invoice is made and only a log entry records it; nobody is told. *Suggestion:* tell the creator "set an account to create the invoice".
  - The completion text "Invoice confirmed on EXP-<id> — order locked" shows the database id, not the expense number.
  - An order created from a template does not notify the template's default approver.
- 2026-11-21, transfer order service describe ([spec](../../tests/unit/services/transfer_order_service.spec.md), verified on `marker_test`):
  - Nothing is sent on create, completion, approve / withdraw, approver removal, or line edit / removal. After the last line is removed, approvers already told "approval pending" are not told it is off (D1).
  - A change to "Required approvals", including the OQ-55 wipe, sends no "approve again" notice (already noted above).
  - The notification is sent inside the order's transaction, so a notification failure rolls back the order change. Two edits at once can each send "approval pending" until BUG-3142 (lock before the readiness check) is fixed.
- 2026-11-21, inventory service describe ([spec](../../tests/unit/services/inventory_service.spec.md)): clearing stock and manual quantity / average-price changes are not announced. Optional candidate for a stock-change alert.
- 2026-11-22, purchase order service spec ([spec](../../tests/unit/services/purchase_order_service.spec.md)):
  - "Create invoice" sends no "draft" notice, while auto-drafting through a section confirm does.
  - Approving, withdrawing an approval or removing an approver sends nothing, even when that makes the approvals met.
  - Voiding a PO, starting, completing or cancelling a return, receiving goods and receiving replacements notify no one. A settlement by replacement (BUG-3176) changes money without telling the accountant.
  - Adding an approver to a ready order notifies every other pending approver again (AA2).
- 2026-11-22, sales service spec ([spec](../../tests/unit/services/sales_service.spec.md)):
  - Once BUG-1205 is fixed, the sales "draft invoice" notice reuses the text "Linked payable invoice", but a sales order's invoice is receivable; the wording must follow `invoice_type`.
  - Sales returns and their credit notes notify nobody: start, complete and cancel send nothing, and neither will the BUG-3217 "settled by replacement" step or its "already refunded — settle by hand" warning (today it appears only in the delivery's response messages). Decide who hears about a warning that needs staff to act.
  - The last approval needed sends no "ready to finalize" notice to the order's creator.
- 2026-11-22, work order service spec ([spec](../../tests/unit/services/work_order_service.spec.md)):
  - Start, completion, void and delete send nothing. The one exception is the invoice "confirmed" notice at completion.
  - Nothing is sent when an approval makes the order ready to start, or when an approver is removed.
  - Approvers copied from a template or named in a sheet entry are not told.
  - Item edits that clear approvals send nothing, while a header edit notifies the creator.
  - The "confirmed" invoice notice says `Invoice confirmed on WO-<database id>` instead of the work order number.
  - After OQ-65, a refused "Create invoice" (no cost) sends nothing. If a reminder to the creator to enter the cost is ever wanted, it belongs here.
- 2026-11-22, purchase order service fill-gaps: the new return event log (`purchase_order_return_events`) is a natural source if return activity ever needs notices.
