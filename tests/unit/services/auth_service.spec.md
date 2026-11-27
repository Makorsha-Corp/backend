# Spec — `app/services/auth_service.py`

> **Status:** APPROVED (2026-11-10). One owner question is parked as **OQ-34** (not blocking): `reset_password_by_admin` R7 is written to today's behaviour and marked *pending OQ-34*. Everything else is a house rule, an owner answer already given (OQ-1, OQ-11, OQ-12; OQ-7 and OQ-9 boxed), or was decided by Claude under the reviewer's delegation (2026-11-10).
> **Source commit:** e48a092
> **Fill-gaps 2026-11-10** (case designer, `auth_service.cases.md` gaps 1–7): facts added, plus two delegated decisions: `refresh_access_token` R2a and `login_user` R3. Status unchanged. See the Gap log.

> **Below (approved, not restated):** `tests/unit/dao/profile.spec.md` (`get_by_email`, `create`, `authenticate`, inherited `get`), `tests/unit/dao/refresh_token.spec.md` (`create`, `get_by_hash`, `revoke`, `revoke_family`, `revoke_all_for_user`, `touch_last_used`), `tests/unit/dao/workspace_member.spec.md` (`get_by_workspace_and_user`), `tests/unit/dao/workspace_invitation.spec.md` (`get_by_token`), `tests/unit/dao/workspace.spec.md` / `base.spec.md` (`get`), `tests/unit/managers/workspace_manager.spec.md` (`create_workspace_with_owner`, `validate_invitation_for_user`, `accept_invitation`), `tests/unit/services/workspace_service.spec.md`, `tests/unit/managers/profile_stamp_manager.spec.md` (`validate_saved_stamp_payload`, `destroy_saved_stamp_image`), `tests/unit/core/security.spec.md` (`create_access_token`, `create_refresh_token`, `hash_refresh_token`, `get_password_hash`), `tests/unit/core/limiter.spec.md` (rate limits of the auth routes). **Transaction contract:** TC1–TC6 of `tests/unit/services/base_service.spec.md`; each method below says which apply and where it departs.
>
> **Above:** `app/api/v1/endpoints/auth.py` only. It maps a `ValueError` to 400 (register, reset-password, validate-invitation, `PATCH /me/`, logout), 401 (login, refresh) or 403 (switch-workspace, admin reset); `NotImplementedError` to 501; anything else to 500 with the exception text (BUG-037). `GET /auth/me/` and `POST /auth/me/stamp-image/sign` do not use this service.
>
> **Verified by running** (`v_auth.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\auth\`, one outer transaction on `marker_test` rolled back, session with `join_transaction_mode="create_savepoint"`, private `COVERAGE_FILE`; nothing persisted, no Cloudinary or email call): registration with a new workspace, a second registration with the same workspace name, Bengali / `!!!` / 150-character / `Plant²` workspace names, account-only registration, a case-variant email; an owner's reset of a member who is a platform admin and owns another workspace, then login and switch into that other workspace as the member; an owner resetting their own password; `update_current_user` image → vector, `name: null`, `name: "   "`, `timezone: null`; `logout_session(all_devices=True, user_id=None)`. **Read, not run:** the refresh rotation and reuse paths, the invitation registration path, `validate_invitation_token`, everything over HTTP.

## Review
> All answered; OQ-34 parked for the owner (not blocking).

### Quick list
| # | What the code does today, in plain words | Answer | Decided by |
|---|---|---|---|
| H1 | Two refreshes with one token at the same moment both succeed and leave two live sessions | bug — HR-10 (BUG-2560) | house rule |
| H2 | A blank name can be saved on `PATCH /auth/me/` | bug — HR-1, existing BUG-1406 | house rule |
| P1 | The invitation preview accepts an invitation at the exact instant it expires | bug — per BUG-1987 (BUG-2561) | precedent, Claude |
| P2 | Removing or replacing a stamp deletes the old picture before the change is saved | bug — per BUG-2202 (BUG-2562) | precedent, Claude |
| P3 | Registration's workspace and invitation audit rows never carry the client's IP and browser | bug — per BUG-1404 (BUG-2563) | precedent, Claude |
| P4 | Two registrations of one email at once: the second gets a 500 with database text | bug — per BUG-1440 (BUG-2564) | precedent, Claude |
| P5 | Session rows store the client address from a raw `X-Forwarded-For` header | bug — per BUG-140 decision (BUG-2565) | precedent, Claude |
| D1 | A workspace name whose derived slug breaks the slug rules (Bengali, symbols only, over 100 characters) makes registration fail with a raw validation text | bug (BUG-2566) | Claude, delegated |
| D2 | A second company with the same workspace name cannot register | bug (BUG-2567) | Claude, delegated |
| D3 | Replacing an image stamp with a drawn stamp leaves the old picture in Cloudinary | bug (BUG-2568) | Claude, delegated |
| D4 | An owner's reset of a member's password leaves no audit row | bug (BUG-2569) | Claude, delegated |
| D5 | "Log out all devices" uses a revoked or expired token to find the user, and an unknown token gives 400 though the endpoint's comment says 200 | bug (BUG-2570) | Claude, delegated |
| D6 | Registration with both a workspace name and an invitation token: the token wins; with neither, an account without a workspace is made | intended | Claude, delegated |
| D7 | Registration says "An account with this email already exists", though the comment says the error is generic | intended | Claude, delegated |
| D8 | `RegisterRequest.position` is accepted and never used | intended | Claude, delegated |
| D9 | Forgot-password stores nothing and sends nothing; reset-password always answers 501 | intended for now; routed to notifications | Claude, delegated |
| D10 | Switching workspace does not revoke the old refresh token | intended | Claude, delegated |
| D11 | A refreshed access token keeps the old `workspace_id` claim after the member was removed | intended | Claude, delegated |
| D12 | "Revoked N active session(s)" counts expired rows too | intended | Claude, delegated |
| Q1 | **OWNER (OQ-34)** — A workspace owner can reset the password of any member's account, which is global: they can then log in as that person in every other workspace, platform admins included | pending OQ-34 (suggested: bug) | owner |

**Already decided elsewhere and applied here (no question):**
- **OQ-1** (owner, 2026-11-04): an email identifies one account whatever its capitals. BUG-1860 (lookup), BUG-1861 (stored lower-cased), BUG-1862 (unique on `lower(email)`). Rules `register_user` R1, R1a, `login_user` R1, `request_password_reset` R1. No new ID: the bug rows already name these paths.
- **OQ-11 / OQ-12** (owner, 2026-11-04): a stamp is accepted, and its old picture deleted, only in the exact minted form `…profiles/<user id>/stamp-<32 lowercase hex>`, and the server builds the picture's `url`. BUG-1864, BUG-1865, BUG-1866. Per `profile_stamp_manager` FU-1 (a), `update_current_user` must pass the current user's id. Rules `update_current_user` R6a, R7a, R8.
- **BUG-1885** (only an *active* membership's role counts): `switch_workspace` and `reset_password_by_admin` already count only an `active` membership. Rules `switch_workspace` R1 and `reset_password_by_admin` R1, R2 follow that rule ✅, and no bug is logged.
- **OQ-7, OQ-9** (owner: boxed, 2026-11-04): the rate limits and the way the client address is read in production are a deployment matter, not rules here. The limits are in the limiter spec: register 5, login 10, forgot-password 5, validate-invitation 20 per minute. Refresh, reset-password, logout, switch-workspace, admin reset and `/me/` have none.
- **BUG-037** (`internal-error-leak`): every auth endpoint, not only login, answers unexpected errors with `"<Action> failed: <exception text>"`. The bug row already says "and possibly other auth endpoints". No new ID.
- **BUG-038, BUG-500** (login timing and over-long password): these are rules of `authenticate` (profile DAO spec). `login_user` R1 points there.
- **BUG-1406** (HR-1, a person's name): its row already names `ProfileMeUpdate` and `PATCH /auth/me/`. Rule `update_current_user` R3a.
- **BUG-1407** (over-long user agent or address fails the login): refresh token DAO `create` R4. Every token-issuing method here reaches it.

Checked and **not** a line here: **HR-2**: email uniqueness is a database index (profile DAO), and its case is OQ-1. Workspace slugs are unique in the database (D2). **HR-3 … HR-8**: no grouping, list, paging or `LIKE`. **HR-9**: profiles have no audit columns. **HR-11 … HR-14**: Cloudinary deletes start no business process; there is no batch. **HR-15**: no money. **HR-16**: `switch_workspace` and `reset_password_by_admin` look memberships up by workspace and user together, the invitation decides its own workspace (workspace manager FU-3), and a refresh row keeps the workspace it was issued for.

### House-rule violations — applied automatically

- **HR-10** `refresh_access_token` R7 — the presented row is read without a lock, checked "not revoked", then a successor is issued and the row revoked. Two refreshes with one token at the same moment both pass: two live successors exist in the family, and the second `revoke` replaces `replaced_by_id`, so the first successor is left live and unlinked (refresh token DAO FU-1 (a), `revoke` R2). Intended: the row is read `FOR UPDATE`; the loser waits, then sees it revoked with a successor, which is the reuse case (R3).
**Answer:** bug — per HR-10 (house rule)
**Resolution:** 🐞 BUG-2560 (pattern `hr-10-unlocked-state-transition`). Rules: `refresh_access_token` R7. Frontend note in the bug row: the web app's refresh mutex is per tab, so two tabs sharing one refresh token can still race; after the fix, the loser's tab is logged out together with the whole family. The app should share one refresh across tabs (e.g. a `BroadcastChannel` or a storage lock).

- **HR-1** `update_current_user` R3a — `ProfileMeUpdate.name` is a bare optional `str`: `"   "` is saved as typed (verified).
**Answer:** bug — per HR-1 (house rule)
**Resolution:** existing 🐞 BUG-1406 (its row already lists `ProfileMeUpdate`). No new ID. Rules: `update_current_user` R3a.

### Precedent matches — all accepted (decided by Claude under the reviewer's delegation, 2026-11-10)

### P1. The invitation preview accepts an invitation at the exact instant it expires — 🐞 BUG-2561
**Background:** BUG-1987 settled that an invitation is expired once `expires_at <= now`, everywhere: the lists, the seat count and the accept check. `POST /auth/validate-invitation/` (the page shown before registering) has its own copy of the check.
**What happens today:** It refuses only when `expires_at < now`. At exactly `expires_at` the preview says the invitation is valid.
**Example:** An invitation expires at 10:00:00.000000. A preview at exactly that instant shows "Valid invitation to join 'Acme'", and the registration that follows is refused as expired (after BUG-1987).
**Rules affected:** `validate_invitation_token` R2
**Answer:** bug — per BUG-1987 precedent: expired means `expires_at <= utcnow()` (precedent — confirmed under delegation)
**Resolution:** 🐞 BUG-2561 (pattern `inconsistent-sibling-guard`). Low. Rules: `validate_invitation_token` R2.

### P2. Removing or replacing a stamp deletes the old picture before the change is saved — 🐞 BUG-2562
**Background:** BUG-2202 (attachments) and BUG-2205 (QR uploads) settled that a Cloudinary delete runs only after the commit has succeeded. It runs right after the commit, before the re-read, and its failure is logged and swallowed.
**What happens today:** `PATCH /auth/me/` with `saved_stamp: null`, or with a new image stamp, asks Cloudinary to delete the old picture first and commits afterwards. If the commit fails, the profile still names the picture, which is gone.
**Example:** Ann replaces her stamp. The database is briefly unavailable when the change is committed, so she gets a 500 and keeps her old stamp. That stamp's picture was already deleted, so every markup showing her stamp shows a broken image.
**Rules affected:** `update_current_user` R10
**Answer:** bug — per BUG-2202 precedent (precedent — confirmed under delegation)
**Resolution:** 🐞 BUG-2562 (pattern `external-delete-before-commit`). Rules: `update_current_user` R10.

### P3. Registration's audit rows never carry the client's IP and browser — 🐞 BUG-2563
**Background:** BUG-1404 (workspace audit log) settled that every workspace audit row carries the request's client IP and user agent. The workspace manager gets new optional `ip_address` / `user_agent` parameters (workspace manager spec A2). Its FU-2 covered only the workspace service.
**What happens today:** `register_user` receives `ip_address` and `user_agent` and stores them on the refresh token row. It passes neither to `create_workspace_with_owner` or `accept_invitation`, so the `workspace_created`, `member_added` and `invitation_accepted` rows written at registration have both NULL.
**Example:** The audit log of a new workspace shows who created it and when, but not from where, although the same request's session row records the address.
**Rules affected:** `_register_with_new_workspace` R5, `_register_with_invitation` R4
**Answer:** bug — per BUG-1404 precedent (precedent — confirmed under delegation)
**Resolution:** 🐞 BUG-2563 (pattern `flag-unreachable-from-api`). The value passed is the one BUG-2565 makes trustworthy. Rules: `_register_with_new_workspace` R5, `_register_with_invitation` R4.

### P4. Two registrations of one email at once: the second gets a 500 — 🐞 BUG-2564
**Background:** The "already registered" check is a Python read followed by an insert, with no lock. The database's unique index on the email (on `lower(email)` after BUG-1862) stops the second insert. BUG-1440 and BUG-2120 settled the same shape: the loser gets the normal refusal, never a 500.
**What happens today:** Both requests pass the check. The second insert raises `IntegrityError` at the flush, and the endpoint answers 500 `"Registration failed: (psycopg2.errors.UniqueViolation) duplicate key value violates unique constraint "profiles_email_key" …"`, showing the SQL.
**Example:** Ann double-clicks "Create account". One tab gets her workspace, the other a 500 page full of SQL.
**Rules affected:** `register_user` R1b
**Answer:** bug — per BUG-1440 precedent: the unique violation on the email answers the same `ValueError` as R1 (400), and nothing is written (precedent — confirmed under delegation)
**Resolution:** 🐞 BUG-2564 (pattern `count-then-insert-race`). Rules: `register_user` R1b.

### P5. Session rows store the client address from a raw `X-Forwarded-For` header — 🐞 BUG-2565
**Background:** The audit-logger review settled that "the client address" is the one the server's trusted-proxy handling gives, never a raw `X-Forwarded-For` header (BUG-140). The limiter follows that rule (limiter spec P1). The auth endpoint's `_client_context` builds the address it hands to this service from the first entry of `X-Forwarded-For` whenever the header is present.
**What happens today:** Any client can write any text as its address on its refresh token rows (and, after BUG-2563, on the audit rows). After BUG-1407 that text is cut to 64 characters.
**Example:** A client sends `X-Forwarded-For: 10.0.0.1`. A future "active sessions" page would show 10.0.0.1 for a login made from anywhere.
**Rules affected:** none of this service (integration-only, the endpoint): the service stores what it is given (`_issue_token_pair` R4).
**Answer:** bug — per BUG-140 decision: the endpoint uses `request.client.host` (the trusted-proxy result) and ignores the raw header (precedent — confirmed under delegation)
**Resolution:** 🐞 BUG-2565 (pattern `raw-forwarded-header-trusted`). Low: diagnostics only, no access decision uses it. Not unit-testable here.

### New questions

### D1. A workspace name whose derived slug breaks the slug rules makes registration fail — 🐞 BUG-2566
**Background:** At registration the workspace slug is derived from the name: lower-cased, spaces and `_` turned into `-`, every character dropped that is not `isalnum()` or `-`, runs of `-` collapsed, outer `-` removed. `WorkspaceCreate.slug` then requires 1–100 characters matching `^[a-z0-9]+(?:-[a-z0-9]+)*$`. Python's `isalnum()` keeps any Unicode letter or digit. The same root cause was settled for tag codes (BUG-1532, BUG-1690: a derived value always satisfies its own rules).
**What happens today (verified):** `কারখানা` derives `কখন` (Bengali letters, with the vowel signs dropped), `Plant² …` keeps `²`, `!!!` derives `""` and a 150-character name derives 150 characters. Each raises Pydantic `ValidationError` (a `ValueError`). The endpoint answers 400 with Pydantic's raw text (`1 validation error for WorkspaceCreate\nslug\n  String should match pattern …`), and nothing is written.
**Example:** A Dhaka factory owner types her company's name in Bangla and cannot create an account at all. The message talks about a "slug" she never typed.
**Rules affected:** `_register_with_new_workspace` R2, R2a
**Answer:** bug — the derived slug always satisfies the slug rules: only ASCII `a-z` and `0-9` are kept (other characters act as separators), runs of `-` collapse and outer `-` are removed, it is cut to at most 100 characters with no trailing `-`, and an empty result becomes `workspace`. The workspace name itself is stored as typed (BUG-1980 trims it). Decided by Claude under the reviewer's delegation (2026-11-10), per BUG-1532.
**Resolution:** 🐞 BUG-2566 (pattern `derived-value-violates-schema`). Rules: `_register_with_new_workspace` R2a.

### D2. A second company with the same workspace name cannot register — 🐞 BUG-2567
**Background:** Slugs are unique across all workspaces (workspace manager R5). The registration form asks only for a workspace name, never a slug. The same root cause was settled for tag codes: a taken derived code becomes the first free `<code>_2`, `<code>_3` (BUG-1533, BUG-1691).
**What happens today (verified):** When the derived slug is taken, registration fails with 400 "Workspace slug 'acme' is already taken. Please choose a different name.", and the account is not created (rolled back).
**Example:** "Rahman Textiles" exists. A second, unrelated "Rahman Textiles" in another city cannot register under its real name.
**Rules affected:** `_register_with_new_workspace` R3, R3a
**Answer:** bug — a derived slug that is taken becomes the first free `<slug>-2`, `<slug>-3`, …, staying within 100 characters (the base is cut so that the suffix fits). Registration never fails because of the slug. If two registrations race for the same free slug, the database's unique index still refuses the second (`IntegrityError`). That remains possible and is not specified further. Decided by Claude under the reviewer's delegation (2026-11-10), per BUG-1533.
**Resolution:** 🐞 BUG-2567 (pattern `derived-key-collision-refused`). Rules: `_register_with_new_workspace` R3a. `POST /workspaces/`, where the user types the slug, keeps its 400 (workspace manager R5).

### D3. Replacing an image stamp with a drawn stamp leaves the old picture in Cloudinary — 🐞 BUG-2568
**Background:** A saved stamp is either a vector drawing or an uploaded picture. The old picture is deleted only when the stamp is removed, or replaced by another picture with a different `public_id`.
**What happens today (verified, Cloudinary mocked):** image → vector saves the vector, and the delete is not called (0 calls). The picture stays in Cloudinary with nothing naming it.
**Example:** Ann uploads a scanned stamp, then decides to draw one instead. Her scan stays in the company's Cloudinary account for ever.
**Rules affected:** `update_current_user` R7b
**Answer:** bug — replacing an image stamp with a vector stamp deletes the old picture, under the same rules as removal: the exact minted form only (BUG-1865), after the commit (BUG-2562), failure logged and swallowed (BUG-1713). Decided by Claude under the reviewer's delegation (2026-11-10), per BUG-2099.
**Resolution:** 🐞 BUG-2568 (pattern `orphaned-external-file`). Rules: `update_current_user` R7b.

### D4. An owner's reset of a member's password leaves no audit row — 🐞 BUG-2569
**Background:** Workspace security events (member added or removed, invitations, and after BUG-2253 role changes) are written to `workspace_audit_logs` through `log_action`. Setting another person's password is at least as sensitive.
**What happens today:** `reset_password_by_admin` changes the hash and revokes the sessions, and nothing records who did it.
**Example:** A member finds they cannot log in and their sessions are gone. Nothing shows that the owner reset their password, or when.
**Rules affected:** `reset_password_by_admin` R9
**Answer:** bug — a successful reset writes one workspace audit row: `workspace_id` = the workspace, `user_id` = the owner, `action = 'member_password_reset'`, `metadata = {"target_user_id": <id>, "sessions_revoked": <count>}`. The password and its hash never appear. Decided by Claude under the reviewer's delegation (2026-11-10), per BUG-2253.
**Resolution:** 🐞 BUG-2569 (pattern `missing-audit-row`). Rules: `reset_password_by_admin` R9.

### D5. "Log out all devices" trusts a dead token and contradicts its own comment — 🐞 BUG-2570
**Background:** `POST /auth/logout/` needs no access token. For `all_devices: true` the endpoint finds the user from the presented refresh token's row (`get_by_hash` finds revoked and expired rows too), then calls `logout_session(all_devices=True, user_id=<that user or None>)`. Its comment says "If the row is unknown we still 200".
**What happens today:** (a) A revoked or expired refresh token, for example an old one from a backup or a log, signs its owner out of every device. (b) An unknown token passes `user_id=None`, and the service raises `ValueError("Cannot logout all devices without an authenticated user")` (verified), so the answer is 400, not 200.
**Example:** (a) A refresh token leaked in last month's crash report is long revoked, but anyone holding it can still sign the user out everywhere, over and over. (b) A client whose token was already cleaned up gets a 400 for "log out everywhere".
**Rules affected:** `logout_session` R2 (the service rule is unchanged). The fix is in the endpoint (integration-only).
**Answer:** bug — only a live token (not revoked, not expired) identifies the user for an all-devices logout. With an unknown or dead token the endpoint answers 200 with the info message "No active session found; nothing to revoke." and revokes nothing. The service keeps refusing `user_id=None` (R2). Decided by Claude under the reviewer's delegation (2026-11-10), refresh token DAO FU-1 (d).
**Resolution:** 🐞 BUG-2570 (pattern `dead-credential-accepted`). Low. Not unit-testable here.

### D6. Registration paths: the token wins, and neither gives an account only — ✅ intended
**Background:** The docstring says "Either workspace_name OR invitation_token required (not both)".
**What happens today:** A non-empty `invitation_token` takes the invitation path and ignores `workspace_name`. Otherwise a non-empty `workspace_name` creates a workspace. With neither, an account with no workspace is made ("PATH 3", which the web app uses before the workspace picker).
**Example:** A user sends a name and a token: they join the inviting workspace, and no "Acme" workspace is created.
**Rules affected:** `register_user` R2, R3, R4
**Answer:** intended. The account-only path is deliberate (code comment "workspace created later"), and the docstring is stale. Decided by Claude under the reviewer's delegation (2026-11-10).

### D7. Registration tells the user the email is taken — ✅ intended
**Background:** The comment says "Generic error — don't reveal whether the email exists". The message is "An account with this email already exists. Try logging in instead.", which does reveal it.
**What happens today:** Anyone can learn whether an email has an account, 5 tries a minute per address (limiter).
**Example:** Trying `rahim@acme.com` at registration answers "already exists".
**Rules affected:** `register_user` R1
**Answer:** intended. A sign-up form has to tell a person their address is taken, and the rate limit bounds probing. The comment is stale. The alternative (always "check your email", with a mail to the existing account) needs email delivery and is noted in `docs/future/notifications.md`. Decided by Claude under the reviewer's delegation (2026-11-10).

### D8. `RegisterRequest.position` is accepted and never used — ✅ intended
**What happens today:** `position` (default `"User"`, at most 100 characters) is validated and dropped. The owner's member row gets `position = NULL`, and an invited member gets the invitation's position.
**Example:** Registering with `position: "CEO"` stores no position anywhere.
**Rules affected:** `_register_with_new_workspace` R4
**Answer:** intended. The field is left over from an earlier form; dropping it from the schema is a clean-up, not a behaviour change. Decided by Claude under the reviewer's delegation (2026-11-10).

### D9. Forgot-password stores and sends nothing; reset-password always answers 501 — ✅ intended for now
**Background:** No password reset token table exists. The web app has forgot- and reset-password pages.
**What happens today:** `request_password_reset` makes a random token that nobody stores, and the endpoint throws it away and answers "If an account with that email exists, a password reset link has been sent." No email is sent. `reset_password` always raises `NotImplementedError` (501). The only way back into a forgotten account is an owner's reset (`reset_password_by_admin`, see OQ-34).
**Example:** Rahim forgets his password, asks for a link, is told it was sent, and never gets one.
**Rules affected:** `request_password_reset` R1–R4, `reset_password` R1
**Answer:** intended for now. The feature needs email delivery, which comes with the notifications work. The page's promise and the 501 are recorded in `docs/future/notifications.md`. Decided by Claude under the reviewer's delegation (2026-11-10).

### D10. Switching workspace does not revoke the old refresh token — ✅ intended
**What happens today:** Every switch makes a new session family. The previous refresh token stays valid until it expires (14 days) or is used.
**Example:** A user who switches workspaces five times in a day holds six live refresh tokens.
**Rules affected:** `switch_workspace` R5
**Answer:** intended, as the docstring explains: the request does not carry the old token. Decided by Claude under the reviewer's delegation (2026-11-10).

### D11. A refreshed access token keeps its `workspace_id` claim after the member was removed — ✅ intended
**Background:** No access decision reads the claim. `get_current_workspace` uses the `X-Workspace-ID` header and re-checks the active membership on every request (deps spec).
**What happens today:** Refreshing a session issued for workspace 7 gives a token claiming `workspace_id = 7`, even after the user was removed from workspace 7.
**Example:** Removed from workspace 7, Rahim's refreshed token still claims 7, and every request to workspace 7 is still refused by the membership check.
**Rules affected:** `refresh_access_token` R6
**Answer:** intended; the claim is informational. Noted in `docs/future/permissions.md`. Decided by Claude under the reviewer's delegation (2026-11-10).

### D12. "Revoked N active session(s)" counts expired rows too — ✅ intended
**Background:** The refresh token DAO's Q1 kept stamping expired rows (intended) and handed the wording to this spec (FU-1 (c)).
**What happens today:** A user with one live and four expired sessions reads "Revoked 5 active session(s)."
**Example:** As above.
**Rules affected:** `logout_session` R3, `reset_password_by_admin` R8
**Answer:** intended; the count is informational and the endpoints do not show it as a figure. Decided by Claude under the reviewer's delegation (2026-11-10).

### Q1. OWNER — A workspace owner can take over a member's whole account by resetting its password — ⏸ pending OQ-34 (not blocking)
**Background:** An account (profile) is global: one email and password for every workspace the person belongs to, and for the platform admin role (`is_platform_admin`). Anyone can register and become the owner of a new workspace, and can invite any email. `POST /auth/admin/reset-password/` lets the owner of the current workspace set a new password for any **active** member of that workspace. No old password, no email and no consent are needed. The web app has no screen for it; it is API-only.
**What happens today (verified):** The owner of workspace A reset the password of a member of A who is a platform admin and the owner of workspace B. The owner then logged in with the new password as that member and switched into workspace B. All of the member's sessions were revoked, so the real person is locked out.
**Example:** A stranger registers "Acme Test", invites `rahim@bigfactory.com` ("join our pilot"), and Rahim accepts. The stranger resets Rahim's password and now owns Rahim's account in BigFactory, with BigFactory's orders, money and members. Rahim cannot log in, and forgot-password does not work (D9).
**Rules affected:** `reset_password_by_admin` R7
**Suggested answer and alternatives:** in OQ-34.
**Answer:** _pending OQ-34 (owner)_. The rule describes today's behaviour and is marked *pending OQ-34*. The spec is not blocked.

## Follow-ups for other reviews
> Nothing below is a rule of this service, and no bug is logged for it here.

| # | Where it must be looked at | What | Came from |
|---|---|---|---|
| FU-1 | **Endpoint** `app/api/v1/endpoints/auth.py` | (a) `register`'s docstring promises 409 for a taken email; it is 400. (b) `forgot_password` swallows every exception into the same 200, which is right for enumeration but hides real failures from the logs (nothing is logged). (c) BUG-2565 and BUG-2570 are endpoint fixes. | D5, P5 |
| FU-2 | **Profile DAO / fix of BUG-1861** | The access token's `email` claim is the stored email. After BUG-1861 it is lower-case for new accounts only; old rows keep their capitals until the listing script's manual merge. | OQ-1 |

## Overview
`AuthService` runs the account side of signing in: registration (a new workspace, an invitation, or an account alone), login, workspace switch, refresh-token rotation with reuse detection, logout, the placeholder password-reset flow, an owner's reset of a member's password, the invitation preview, and self-service profile changes (name, time zone, saved stamp). It turns DAO and manager calls into one transaction per request and issues the access and refresh token pair. It is meant to protect who can get a session, keep each refresh token usable exactly once, and save only well-formed stamps.

**Callables:** 13 specified · 3 not specified
**Externals to mock:** Cloudinary through `profile_stamp_manager` (patch `app.managers.profile_stamp_manager.destroy_resource`). The clock: `app.services.auth_service.utcnow` (refresh expiry, reset expiry, invitation preview expiry, refresh row `expires_at`), plus `app.core.security.utcnow` (access token `exp`), `app.dao.refresh_token.utcnow` (revocations) and `app.managers.workspace_manager.utcnow` (registration paths) where those values are asserted. `secrets.token_urlsafe` (`app.services.auth_service.secrets.token_urlsafe`) only where a fixed reset token is wanted. No email or notification is sent anywhere in this module.
**Integration-only behavior:** the endpoint's status mapping and response bodies; the rate limits; BUG-2565, BUG-2570; the row lock of BUG-2560 itself (one connection cannot observe a lock. The test checks the outcome of the sequential replay, R3, and may assert the `FOR UPDATE` in the captured SQL).

**Facts for the test designer**
- Import: `from app.services.auth_service import auth_service, AuthService, TokenPair`. `AuthService()` takes no arguments. Every method takes `db` first; the public ones are called by keyword in the endpoint.
- Settings: `ACCESS_TOKEN_EXPIRE_MINUTES = 15`, `REFRESH_TOKEN_EXPIRE_DAYS = 14` (defaults; read at call time from `app.core.config.settings`). The raw refresh token is `secrets.token_urlsafe(64)`; the stored hash is its SHA-256 hex (security spec).
- The access token decodes (security `decode_token`) to `sub` = `str(user.id)`, `email`, `exp`, and `workspace_id` only when one was given.
- Registration with a new workspace needs exactly one active default plan in the test (`make_subscription_plan(db, is_default=True, is_active=True)`), and seeds 13 statuses, a workflow, 5 departments and 11 tags (workspace manager R9). Registration commits; under the `db` fixture a commit releases a savepoint (base service notes).
- Membership rows: `WorkspaceMember(workspace_id, user_id, role, status)`; `status` is free text, and only `active` counts.
- bcrypt runs for real (about 0.25 s per hash). Use one password per test.
- Passwords reach this service already checked by the request schemas (8–72 characters, at most 72 UTF-8 bytes) except through direct calls. `get_password_hash` raises `ValueError` above 72 bytes (security spec).
- Errors are plain `ValueError` unless stated; compare messages exactly.
- **`TokenPair`** (G1): a dataclass (`app.services.auth_service.TokenPair`) with exactly four fields, in this order: `access_token: str`, `refresh_token: str`, `expires_in: int`, `refresh_expires_in: int`.
- **`ProfileMeUpdate`** (G2): `from app.schemas.profile import ProfileMeUpdate`.
- **Messages** (G3): every `messages` list holds `app.schemas.response.ActionMessage` objects. Their fields are `type` (a `MessageType`, a `str` enum with values `"success"`, `"info"`, `"warning"`, `"error"`; this service uses only `success` and `info`), `message` (the text), `timestamp` (set at creation) and `details` (`None` throughout this service). Compare `(m.type.value, m.message)`, or `m.type == "success"`, which also holds because the enum is a `str`.
- **Audit and seed tables** (G7): workspace audit rows are in `workspace_audit_logs` (model `app.models.workspace_audit_log.WorkspaceAuditLog`), with columns `ip_address` VARCHAR(45) and `user_agent` TEXT, both nullable (workspace audit log DAO spec). The seeded departments are in the `departments` table (`app.models.department.Department`).

## Not specified
- `TokenPair` — a dataclass of four fields, no logic.
- `AuthService.__init__` — wires the DAOs and the workspace manager. `self.subscription_dao` is never used.
- `auth_service` — module-level singleton.

---

## `AuthService._issue_token_pair(db, *, user, workspace_id, family_id=None, user_agent=None, ip_address=None)`
**Shape:** create
**Persistence:** writes
**Visibility:** internal (used by: `_register_user_only`, `_register_with_invitation`, `_register_with_new_workspace`, `login_user`, `switch_workspace`, `refresh_access_token`)

**Purpose:** Mint an access token and a refresh token, and store the refresh token's hash.

**Returns:** a `TokenPair`. The refresh row is flushed, not committed.

**Rules:**
- **R1.** The access token's claims are `sub` = the user's id as a string and `email` = the user's stored email, plus `exp` (now + 15 minutes, security spec). `workspace_id` is present when `workspace_id` is not `None` (`0` is present), and absent when it is `None`.
- **R1a.** (G4) `refresh_tokens.workspace_id` is a nullable foreign key to `workspaces.id` (ON DELETE CASCADE). So `workspace_id=0`, or any id with no workspace, makes the refresh row's flush raise `IntegrityError` (pgcode `23503`), and no pair is returned. The `0 is present` boundary of R1 can be observed only with the row write replaced: `monkeypatch.setattr(auth_service, "refresh_token_dao", fake)`, where `fake.create` accepts the keywords and returns `None`. With that fake, `workspace_id=0` gives a claim `workspace_id: 0`. No caller passes `0`: the ids come from rows.
- **R2.** One `refresh_tokens` row is created for the user: `token_hash` = SHA-256 of the returned `refresh_token`, `workspace_id` as given (`None` allowed), `expires_at` = `utcnow()` + 14 days, `user_agent` and `ip_address` as given, not revoked, no successor (refresh token DAO `create`).
- **R3.** `family_id` given → the row joins that family. `None` or `""` → a new family: a 32-character lowercase hex value, different on each call.
- **R4.** `expires_in` = 900 (15 × 60) and `refresh_expires_in` = 1 209 600 (14 × 86 400), from the settings at call time. Two calls give two different refresh tokens and two rows.
- **R5.** The raw refresh token is not stored anywhere: no column holds it.

**Errors:** those of the refresh token DAO's `create` (BUG-1407 for over-long diagnostics).

**Side effects:** one refresh token row, flushed.

---

## `AuthService.register_user(db, name, email, password, workspace_name=None, invitation_token=None, timezone=None, user_agent=None, ip_address=None)`
**Shape:** create
**Persistence:** writes
**Visibility:** public (used by: `POST /auth/register/`, which passes every argument from `RegisterRequest` except `position`)

**Purpose:** Create an account, and either a new workspace or the membership an invitation offers, then sign the person in.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `name` | str | `RegisterRequest`: 1–255 characters (BUG-1406) |
| `email` | str | `EmailStr` at the API, domain lowered (BUG-1861) |
| `password` | str | 8–72 characters and ≤ 72 UTF-8 bytes at the API; not checked here |
| `workspace_name` | str \| None | 1–255 characters at the API |
| `invitation_token` | str \| None | any string |
| `timezone` | str \| None | trimmed; blank → `None`; must be an IANA zone (schemas) |

**Returns:** `(user, workspace or None, TokenPair, messages)`, committed. `user` and `workspace` are re-read after the commit.

**Rules:**
- **R1.** When an account already has this email (`get_by_email`), `ValueError("An account with this email already exists. Try logging in instead.")` is raised. Nothing is written, and the session is rolled back. ✅ (D7)
- **R1a.** [BUG-1860] (OQ-1, owner) "Already has this email" ignores capitals and outer spaces: with `Ann.Lee@example.com` registered, `ann.lee@example.com` gets R1's error. *(Today: verified, a second account is created.)* The new account's email is stored lower-cased [BUG-1861], and a case variant that slips past the check is refused by the database [BUG-1862] (profile DAO `create` R4a, R4b).
- **R1b.** [BUG-2564] (P4) When the insert itself hits the unique email index (two registrations at once), the same `ValueError` as R1 is raised and nothing is saved. *(Today: the `IntegrityError` reaches the caller, and the endpoint answers 500 with the SQL text. Test: patch `profile_dao.get_by_email` to return `None` for an email that exists.)*
- **R2.** ✅ (D6) A truthy `invitation_token` takes the invitation path (`_register_with_invitation`); `workspace_name` is then ignored, whatever it holds.
- **R3.** ✅ (D6) Otherwise a truthy `workspace_name` takes the new-workspace path (`_register_with_new_workspace`).
- **R4.** ✅ (D6) Otherwise (`None` or `""` for both) the account-only path runs (`_register_user_only`), and `workspace` is `None`.
- **R5.** On success the chosen path's messages come first, then one success message `"Welcome <name>! Your account has been created successfully."` with the name as passed.
- **R6.** On success everything the path wrote (account, workspace and its seeded data, membership, invitation update, audit rows, refresh row) is committed (TC1). The returned user and workspace are re-read after the commit (TC2).
- **R7.** Any exception from the check or a path (`ValueError`, Pydantic `ValidationError`, `IntegrityError`, anything) rolls the session back and reaches the caller as the same object. No account, workspace or token row stays, and other pending changes in the session are discarded (TC3). A failing commit: TC4. A failing re-read after the commit: TC5 (the account stays).

**Errors:** R1; and those of each path.

**Side effects:** as the chosen path, committed.

---

## `AuthService._register_user_only(db, name, email, password, timezone=None, user_agent=None, ip_address=None)`
**Shape:** create
**Persistence:** writes
**Visibility:** internal (used by: `register_user`)

**Purpose:** Make an account with no workspace and sign it in.

**Returns:** `(user, None, TokenPair, [success "User profile created"])`, flushed.

**Rules:**
- **R1.** One profile is created from `ProfileCreate(name, email, password, timezone)` (profile DAO `create`: hashed password, `user_id` = email, BUG-1406 for the name). An invalid `timezone` raises Pydantic `ValidationError` before anything is written.
- **R2.** A token pair is issued with no workspace (`_issue_token_pair` with `workspace_id=None`, a new family, the given user agent and address). The access token has no `workspace_id` claim.
- **R3.** No workspace, membership or audit row is written.

**Errors:** those of `ProfileCreate` and profile DAO `create`.

**Side effects:** 1 profile, 1 refresh row; flushed.

---

## `AuthService._register_with_invitation(db, name, email, password, invitation_token, timezone=None, user_agent=None, ip_address=None)`
**Shape:** create
**Persistence:** writes
**Visibility:** internal (used by: `register_user`)

**Purpose:** Make an account and accept the invitation behind the token.

**Returns:** `(user, workspace, TokenPair, messages)`, flushed.

**Rules:**
- **R1.** The invitation is checked before anything is written, as `validate_invitation_for_user` with the email being registered (workspace manager R1–R6: unknown token, expired at `expires_at <= now` (BUG-1987), not pending, another email ignoring capitals). Its `ValueError` reaches the caller and nothing is written.
- **R2.** Messages, in order: info `"Valid invitation found for workspace: <workspace name>"`, success `"User profile created"`, success `"You've been added to workspace '<workspace name>' with role '<invitation role>'"`.
- **R3.** The profile is created as `_register_user_only` R1. The invitation is accepted as `accept_invitation` does (workspace manager R1–R6a): a member row with the invitation's role and position, the invitation `accepted`, other pending invitations to that email cancelled (BUG-1874), and audit rows.
- **R4.** [BUG-2563] (P3) The audit rows written by the accept carry this call's `ip_address` and `user_agent` (workspace manager A2). *(Today: both NULL; requires BUG-1404's new manager parameters.)*
- **R5.** The token pair is issued for the invitation's workspace (`workspace_id` claim and refresh row = that workspace), as a new family.
- **R6.** A refusal by the accept (seat limit, BUG-1871 for unlimited plans) raises its `ValueError`; the caller's rollback removes the profile.

**Errors:** those of R1 and R6.

**Side effects:** 1 profile, 1 member row, invitation(s) updated, audit rows, 1 refresh row; flushed.

---

## `AuthService._register_with_new_workspace(db, name, email, password, workspace_name, timezone=None, user_agent=None, ip_address=None)`
**Shape:** create
**Persistence:** writes
**Visibility:** internal (used by: `register_user`)

**Purpose:** Make an account and a new workspace it owns.

**Returns:** `(user, workspace, TokenPair, messages)`, flushed.

**Rules:**
- **R1.** The profile is created as `_register_user_only` R1. Messages, in order: success `"User profile created"`, success `"Workspace '<workspace_name>' created successfully with 14-day trial"` (the name as passed).
- **R2.** The slug is derived from `workspace_name`: lower-cased; spaces and `_` become `-`; characters that are neither `isalnum()` nor `-` are dropped; runs of `-` become one; outer `-` are removed. `"Acme Steel_Works"` → `acme-steel-works`, `"  A -- B  "` → `a-b`, `"R&D Ltd."` → `rd-ltd`.
- **R2a.** [BUG-2566] (D1) The derived slug always satisfies `WorkspaceCreate.slug`: only ASCII `a-z` and `0-9` are kept, and any other character is a separator (so `Plant² Two` → `plant-two`, `কারখানা 2` → `2`). It is cut to at most 100 characters with no trailing `-`, and an empty result (`"!!!"`, an all-Bengali name) becomes `workspace`. Registration never fails because of the derived slug's form. *(Today: verified, Unicode letters and digits are kept and there is no length cut; Bengali, `²`, `!!!` and a 150-character name raise Pydantic `ValidationError` and the endpoint answers 400 with Pydantic's text.)*
- **R3.** When no workspace has the derived slug, the workspace is created with it.
- **R3a.** [BUG-2567] (D2) When the derived slug is taken, the first free one of `<slug>-2`, `<slug>-3`, … is used, within 100 characters (the base is cut so that the suffix fits). *(Today: verified, `ValueError("Workspace slug '<slug>' is already taken. Please choose a different name.")` is raised and the caller rolls back the account.)*
- **R4.** The workspace is created as `create_workspace_with_owner` does with no plan id and no owner position (workspace manager R3, R5–R12): the default plan, a 14-day trial, `billing_email` = the email as passed, the user as owner and first `active` member with `position` NULL ✅ (D8), the seeded data, and one `workspace_created` audit row. No active default plan → `ValueError("No default subscription plan found")`.
- **R5.** [BUG-2563] (P3) The `workspace_created` audit row carries this call's `ip_address` and `user_agent`. *(Today: both NULL.)*
- **R6.** The token pair is issued for the new workspace, as a new family.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| derived slug invalid (today, BUG-2566) | `pydantic.ValidationError` | Pydantic's |
| derived slug taken (today, BUG-2567) | `ValueError` | `Workspace slug '<slug>' is already taken. Please choose a different name.` |
| no default plan | `ValueError` | `No default subscription plan found` |

**Side effects:** 1 profile, 1 workspace with its seeded data, 1 member row, 1 audit row, 1 refresh row; flushed.

---

## `AuthService.login_user(db, email, password, user_agent=None, ip_address=None)`
**Shape:** create (a session)
**Persistence:** writes
**Visibility:** public (used by: `POST /auth/login/`)

**Purpose:** Check an email and password and start a new session with no workspace chosen.

**Returns:** `(user, TokenPair, [success "Welcome back, <user name>!"])`, committed.

**Rules:**
- **R1.** The account is found and the password checked as `authenticate` does (profile DAO R1–R5: [BUG-1860] other capitals find it; [BUG-038] the timing; [BUG-500] an over-long password). When it gives `None` (unknown email, wrong password, empty or malformed stored hash), `ValueError("Invalid email or password")` is raised, the same text for every reason. Nothing is written, and no rollback is made.
- **R2.** On success a token pair is issued with no workspace, as a new family (no `workspace_id` claim), and committed (TC1). Earlier sessions of the user are not touched.
- **R3.** An exception while issuing or committing rolls back and reaches the caller unchanged (TC3, TC4). An exception from `authenticate` itself reaches the caller without a rollback, and pending changes in the session stay pending. (G6, decided by Claude under the reviewer's delegation (2026-11-10).) This second sentence is **reached only through BUG-500** (an over-long password for a known email). Once BUG-500 is fixed, `authenticate` raises nothing, and the sentence describes no reachable path. It gets no case: a passing card would pin the bug path, and BUG-500 is tested in the profile DAO spec.

**Errors:** `ValueError("Invalid email or password")`; today BUG-500's `ValueError`.

**Side effects:** 1 refresh row, committed.

---

## `AuthService.switch_workspace(db, user_id, workspace_id, user_agent=None, ip_address=None)`
**Shape:** create (a session)
**Persistence:** writes
**Visibility:** public (used by: `POST /auth/switch-workspace/`, with the signed-in user)

**Purpose:** Start a session for one of the user's workspaces.

**Returns:** `(workspace, TokenPair, [success "Switched to workspace: <workspace name>"])`, committed.

**Rules:**
- **R1.** ✅ (BUG-1885 rule) The user must have a membership in that workspace whose `status` is exactly `active`. No row, or any other status (`inactive`, `suspended`, `invited`, `Active`), raises `ValueError("You are not a member of this workspace")`. The same message is given for a workspace id that does not exist and for a workspace the user does not belong to (HR-16: nothing about it is revealed). Nothing is written.
- **R2.** A membership whose workspace no longer exists raises `ValueError("Workspace not found")`. This is unreachable: the membership's foreign key cascades on workspace delete.
- **R3.** The token pair is issued for that workspace (claim and refresh row), as a new family, and committed (TC1).
- **R4.** The membership's role is not checked: every active role may switch.
- **R5.** ✅ (D10) Earlier refresh tokens of the user are not revoked.
- **R6.** Refusals in R1–R2 make no rollback. An exception while issuing or committing rolls back and reaches the caller unchanged (TC3, TC4).

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| no active membership | `ValueError` | `You are not a member of this workspace` |
| workspace missing (unreachable) | `ValueError` | `Workspace not found` |

**Side effects:** 1 refresh row, committed.

---

## `AuthService.refresh_access_token(db, raw_refresh_token, user_agent=None, ip_address=None)`
**Shape:** state-transition
**Persistence:** writes
**Visibility:** public (used by: `POST /auth/refresh/`, which answers 401 with the message for every `ValueError`)

**Purpose:** Exchange a refresh token, once, for a new pair in the same family, and treat a replayed token as theft.

**Returns:** `(TokenPair, [])`, committed.

**Rules:**
- **R1.** The row is found by the SHA-256 of the raw token (exact; refresh token DAO `get_by_hash`). No row (any unknown string, `""`) → `ValueError("Invalid refresh token")`, and nothing is written.
- **R2.** A row that is revoked **and** has a successor (`replaced_by_id` set) means the token was already rotated and is presented again. Every not-yet-revoked row of its family is revoked (`revoke_family`), **that revocation is committed**, and then `ValueError("Refresh token reuse detected; all sessions for this login have been revoked")` is raised. The family's revocation survives the rollback that follows. Other families of the same user are not touched. No new row is created.
- **R2a.** (G5) The commit in R2 commits the session as it stands: any other change pending in the session (e.g. a row added and flushed before the call) is committed with the family's revocation and survives the rollback that follows. This is today's behaviour, and it is **intended** (decided by Claude under the reviewer's delegation (2026-11-10)): the revocation must be recorded even though the call fails, as HR-13 records an attempt elsewhere, and a service commit always commits the whole session (TC1). In the endpoint, the request's session holds nothing else at that point.
- **R3.** Reuse is checked before expiry: a rotated token that has also expired still triggers R2.
- **R4.** A row that is revoked with no successor (a logout, a revoke-all, a family revocation) → `ValueError("Refresh token has been revoked")`. A row whose `expires_at` is at or before `utcnow()` → `ValueError("Refresh token has expired")`; one microsecond later than now still passes. Neither writes anything; the session is rolled back.
- **R5.** A row whose user no longer exists → `ValueError("User no longer exists")`. This is unreachable: the row's foreign key cascades on profile delete.
- **R6.** Otherwise a new pair is issued in the **same family**, for the row's `workspace_id` (`None` stays `None`: no claim), with this call's user agent and address. ✅ (D11) Membership is not re-checked. The old row then gets `revoked_at` = now, `replaced_by_id` = the new row's id, and `last_used_at` = now. Everything is committed (TC1). The old token presented again afterwards falls under R2.
- **R7.** [BUG-2560] (HR-10) The presented row is read with a row lock (`SELECT … FOR UPDATE`). When two refreshes present the same live token at once, exactly one issues a successor; the other, after the first commits, sees the row revoked with a successor and is handled by R2. *(Today: no lock. Both pass the check and both issue a successor; the second `revoke` replaces `replaced_by_id`, so the first successor is left live and unlinked (refresh token DAO FU-1 (a)). Read, not run. Unit test: the sequential replay is R2; the lock itself is integration-only, or asserted on the captured SQL.)*
- **R8.** Every `ValueError` and every other exception rolls the session back and reaches the caller unchanged (TC3). A failing commit: TC4.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| unknown token | `ValueError` | `Invalid refresh token` |
| rotated token replayed | `ValueError` | `Refresh token reuse detected; all sessions for this login have been revoked` |
| revoked | `ValueError` | `Refresh token has been revoked` |
| expired | `ValueError` | `Refresh token has expired` |
| user gone (unreachable) | `ValueError` | `User no longer exists` |

**Side effects:** success: 1 new row and the old row revoked, linked and touched, committed. Reuse: the family's live rows revoked, committed.

---

## `AuthService.logout_session(db, raw_refresh_token, user_id=None, all_devices=False)`
**Shape:** state-transition
**Persistence:** writes
**Visibility:** public (used by: `POST /auth/logout/`, which finds `user_id` from the token's row for `all_devices`, BUG-2570)

**Purpose:** End this session, or every session of the user.

**Returns:** a list of one message; the session is committed in every successful branch.

**Rules:**
- **R1.** `all_devices` true takes precedence over the token: the token is not looked at.
- **R2.** `all_devices` true with `user_id` `None` → `ValueError("Cannot logout all devices without an authenticated user")` (verified), rolled back, and nothing changed.
- **R3.** `all_devices` true with a user: every not-yet-revoked row of that user is revoked, in every family and workspace, expired rows included (`revoke_all_for_user`). The message is success `"Revoked <n> active session(s)."`, where `n` is the number of rows stamped (0 allowed) ✅ (D12). Rows of other users are untouched.
- **R4.** Otherwise, with a non-empty token: if its row exists and is not revoked, it is revoked (no successor, `last_used_at` unchanged). The rest of its family is not touched. An unknown, already-revoked or expired-but-unrevoked token is no error. An expired, unrevoked row is revoked. The message is success `"Logged out."` either way.
- **R5.** Otherwise (`None` or `""`): info `"No refresh token provided; nothing to revoke."`, and nothing changed.
- **R6.** Every branch that does not raise commits (TC1), the R5 branch included: other pending changes in the session are committed with it. Any exception rolls back and reaches the caller unchanged (TC3, TC4).

**Errors:** R2.

**Side effects:** rows revoked as above, committed.

---

## `AuthService.request_password_reset(db, email)`
**Shape:** compute
**Persistence:** reads
**Visibility:** public (used by: `POST /auth/forgot-password/`, which discards the token and always answers the same message)

**Purpose:** Placeholder: make a password reset token for an account, revealing nothing about whether the account exists. ✅ (D9, intended for now)

**Returns:** `(token, expires_at, messages)`.

**Rules:**
- **R1.** The account is found as `get_by_email` ([BUG-1860]: other capitals find it, OQ-1).
- **R2.** No account: the token is a fresh `secrets.token_urlsafe(32)` value (43 URL-safe characters), `expires_at` = `utcnow()` + 1 hour, and the messages are exactly one info `"If an account with that email exists, a password reset link has been sent."`.
- **R3.** An account: a token of the same form and `expires_at` = `utcnow()` + 1 hour. Messages: success `"Password reset token generated for <email as passed>. Token expires in 1 hour."`, then info `"NOTE: Token storage not yet implemented. Store this token securely and validate on reset."`.
- **R4.** Nothing is stored, sent, committed or rolled back in either case (TC6). The token cannot be used: `reset_password` always refuses.

**Errors:** none of its own.

**Side effects:** none.

---

## `AuthService.reset_password(db, reset_token, new_password)`
**Shape:** update (placeholder)
**Persistence:** pure
**Visibility:** public (used by: `POST /auth/reset-password/`, which answers 501)

**Purpose:** Placeholder for setting a new password from a reset token. ✅ (D9, intended for now)

**Rules:**
- **R1.** Any input raises `NotImplementedError("Password reset requires a password_reset_tokens table. Please implement password_reset model, DAO, and schema first.")`. No password changes, and nothing is committed or rolled back.

**Errors:** R1.

**Side effects:** none.

---

## `AuthService.reset_password_by_admin(db, admin_user_id, target_user_id, new_password, workspace_id)`
**Shape:** update
**Persistence:** writes
**Visibility:** public (used by: `POST /auth/admin/reset-password/`, with the signed-in user and the `X-Workspace-ID` workspace; not used by the web app)

**Purpose:** Let a workspace owner set a new password for a member and sign that member out everywhere.

**Returns:** `(target_user, messages)`, committed.

**Rules:**
- **R1.** ✅ (BUG-1885 rule) The caller must have an `active` membership in the workspace. Otherwise `ValueError("Admin is not a member of this workspace")`.
- **R2.** The caller's role must be exactly `owner`; every other role (`manager`, `ground-team-manager`, `finance`, …) → `ValueError("Only workspace owners can reset user passwords")`. The workspace's `owner_user_id` column is not consulted, only the membership role. Platform admins get no exception.
- **R3.** The target must have an `active` membership in **the same workspace**. Otherwise `ValueError("Target user is not a member of this workspace")`, whether they are absent, removed, suspended, or a member of another workspace only (HR-16).
- **R4.** A target membership whose profile no longer exists → `ValueError("Target user not found")`. This is unreachable: the membership cascades on profile delete.
- **R5.** Checks run in the order R1, R2, R3, R4; nothing is written before all pass, and every refusal rolls back (TC3).
- **R6.** The target's `hashed_password` becomes a bcrypt hash of `new_password` (an over-72-byte password raises `get_password_hash`'s `ValueError`, rolled back). The old password no longer logs in, and the new one does.
- **R7.** *(pending OQ-34 (owner): today's behaviour, kept in its own rule)* The target may be any active member: another owner-role member, the caller themself (verified: an owner may reset their own password without the old one), a platform admin, or a member who owns or belongs to other workspaces (verified). The new password is the account's password everywhere.
- **R8.** Every not-yet-revoked refresh row of the target is revoked (`revoke_all_for_user`), in every workspace. Access tokens already issued stay valid until they expire (at most 15 minutes).
- **R9.** [BUG-2569] (D4) One workspace audit row is written: `workspace_id`, `user_id` = the caller, `action = 'member_password_reset'`, `metadata = {"target_user_id": <id>, "sessions_revoked": <count>}`. No password or hash appears in it. *(Today: no audit row.)*
- **R10.** Committed (TC1; TC4 for a failing commit). Messages, in order: success `"Password reset successfully for user: <target email>"`; info `"Revoked <n> active session(s); user must log in again."` only when `n` > 0 ✅ (D12); info `"User should be notified of password change via email."` (nothing is sent; notifications note). The returned user is not re-read; its attributes reload on access.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| caller not active here | `ValueError` | `Admin is not a member of this workspace` |
| caller not `owner` | `ValueError` | `Only workspace owners can reset user passwords` |
| target not active here | `ValueError` | `Target user is not a member of this workspace` |
| target profile gone (unreachable) | `ValueError` | `Target user not found` |
| password over 72 bytes | `ValueError` | `Password exceeds bcrypt's 72-byte limit` |

**Side effects:** the target's password hash, their refresh rows revoked, (BUG-2569) one audit row; committed.

---

## `AuthService.validate_invitation_token(db, invitation_token)`
**Shape:** get
**Persistence:** reads
**Visibility:** public (used by: `POST /auth/validate-invitation/`, public, 20 a minute)

**Purpose:** Show what an invitation offers before the person registers.

**Returns:** `(details, [success "Valid invitation to join '<workspace name>' as <role>"])`.

**Rules:**
- **R1.** An unknown token (exact match, any workspace; invitation DAO `get_by_token`) → `ValueError("Invalid invitation token")`.
- **R2.** [BUG-2561] (P1) An invitation whose `expires_at` is at or before `utcnow()` → `ValueError("Invitation has expired. Please request a new invitation.")`; one microsecond after now passes. *(Today: refused only when strictly before; at exactly `expires_at` it passes.)*
- **R3.** Expiry is checked before status: an accepted or cancelled invitation that has also expired gets the expiry message.
- **R4.** An unexpired invitation whose `status` is not exactly `pending` → `ValueError("Invitation has already been <status>")`.
- **R5.** Otherwise `details` is exactly `{"invitation_id", "email", "role", "position", "workspace_id", "workspace_name", "expires_at"}`, with `expires_at` as `isoformat()` of the stored naive value (no offset). `email` is the invited email as stored (lower-case), and `position` may be `None`. No email is checked: anyone holding the token sees this.
- **R6.** Nothing is written, committed or rolled back (TC6).

**Errors:** R1, R2, R4.

**Side effects:** none.

---

## `AuthService.update_current_user(db, *, user, update)`
**Shape:** update
**Persistence:** writes (and Cloudinary)
**Visibility:** public (used by: `PATCH /auth/me/`, with the signed-in user)

**Purpose:** Save the signed-in user's own name, time zone and saved stamp.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `user` | `Profile` | the signed-in user, attached to `db` |
| `update` | `ProfileMeUpdate` | `name: str \| None` (BUG-1406); `timezone`: trimmed, blank → `None`, IANA zone; `saved_stamp: dict \| None`. Only the fields the client sent count (`exclude_unset`). |

**Returns:** the same `Profile`, committed and re-read.

**Rules:**
- **R1.** An update with no field sent (`{}`) returns the user unchanged. Nothing is committed, rolled back, or sent to Cloudinary (TC6-like: pending changes stay pending).
- **R2.** Fields not sent are left as they are.
- **R3.** `name` sent with a string sets it. `name: null` leaves the name unchanged (verified): the name cannot be cleared.
- **R3a.** [BUG-1406] (HR-1) The name is stored trimmed, and a blank or whitespace-only name is refused by `ProfileMeUpdate` (Pydantic `ValidationError`, 422 at the API) before this method runs. *(Today: verified, `"   "` is saved.)*
- **R4.** `timezone` sent sets it; `null`, `""` or `"   "` clears it to `None` (verified).
- **R5.** `saved_stamp: null` clears the stamp to `None`, and the old stamp's picture is deleted as `destroy_saved_stamp_image` does (nothing for a vector or no stamp; R10 for when).
- **R6.** A non-null `saved_stamp` is checked as `validate_saved_stamp_payload` does (stamp manager R1–R6), and the cleaned form is what is stored. An invalid one raises `ValueError` (or Pydantic `ValidationError`): rolled back, nothing saved, **including name and time zone changes sent with it**, and no Cloudinary call. 400 at the endpoint.
- **R6a.** [BUG-1864] (OQ-11, owner) The current user's id is passed to the check (`user_id=user.id`, profile stamp manager FU-1 (a)): an image stamp is accepted only in that user's exact minted form (`<env prefix>profiles/<user.id>/stamp-<32 lowercase hex>`). Another user's stamp id, an attachment's id or any other text raises `ValueError("saved_stamp.public_id is not a stamp of this user")`, and nothing is saved. *(Today: any 1–512-character `public_id` is stored.)*
- **R7.** Replacing an image stamp with an image stamp whose `public_id` differs deletes the old picture (R10 for when). The same `public_id` again deletes nothing.
- **R7a.** [BUG-1865] (OQ-11, owner) Every delete in R5, R7 and R7b passes the user's id (`user_id=user.id`). An old stamp whose `public_id` is not that user's exact minted form (stored before the fix) is not deleted from Cloudinary, and the profile change still succeeds. *(Today: whatever `public_id` the old stamp names is deleted.)*
- **R7b.** [BUG-2568] (D3) Replacing an image stamp with a vector stamp deletes the old picture too, under R7a and R10. *(Today: verified, no delete; the picture is orphaned.)*
- **R8.** [BUG-1866] (OQ-12, owner) A stored image stamp's `url` is the one the server builds from the accepted `public_id` (authenticated Cloudinary delivery address of our cloud). The client's `url` never appears in the saved stamp or the response (stamp manager R4b). *(Today: the client's `url` is stored.)*
- **R9.** A successful change is committed and the user re-read (TC1, TC2). Any exception rolls back and reaches the caller unchanged (TC3, TC4; TC5 for a failing re-read).
- **R10.** [BUG-2562] (P2) The Cloudinary delete of R5, R7 or R7b runs only after the commit has succeeded, before the re-read. A failed commit deletes nothing, and the old stamp and its picture stay. A delete failure is logged and swallowed (BUG-1713) and never fails the request. *(Today: the delete runs before the commit; a failing commit leaves the profile naming a deleted picture.)*

**Errors:** R6, R6a; those of TC3–TC5.

**Side effects:** the profile's `name`, `timezone`, `saved_stamp`; at most one Cloudinary delete; committed.

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 102–103 | `workspace_id is not None` → claim | `_issue_token_pair` R1 |
| 112–121 | refresh row; `family_id or uuid4().hex` | `_issue_token_pair` R2, R3, R5 |
| 123–128 | lifetimes from settings | `_issue_token_pair` R4 |
| 182–184 | email already registered | `register_user` R1, R1a, R1b |
| 187 | `invitation_token` truthy | `register_user` R2 |
| 201 | `workspace_name` truthy | `register_user` R3 |
| 215 | else: account only | `register_user` R4 |
| 228–235 | commit; refresh user; `if workspace` refresh; welcome message | `register_user` R5, R6 |
| 239–241 | any exception → rollback, re-raise | `register_user` R7 |
| 256–273 | profile; token with no workspace | `_register_user_only` R1–R3 |
| 303–311 | validate invitation; info message | `_register_with_invitation` R1, R2 |
| 314–330 | profile; accept | `_register_with_invitation` R3, R4, R6 |
| 333–347 | workspace; message; token | `_register_with_invitation` R2, R5 |
| 375–385 | profile; message | `_register_with_new_workspace` R1 |
| 388–394 | slug derivation (`isalnum`, `while '--'`, strip) | `_register_with_new_workspace` R2, R2a |
| 397–409 | `WorkspaceCreate` (slug schema); create with owner (slug taken, default plan) | `_register_with_new_workspace` R2a, R3, R3a, R4, R5 |
| 411–422 | message; token | `_register_with_new_workspace` R1, R6 |
| 447–449 | `authenticate` falsy → invalid | `login_user` R1 |
| 453–465 | issue, commit / rollback | `login_user` R2, R3 |
| 493–497 | no membership or not `active` | `switch_workspace` R1, R4 |
| 499–501 | workspace missing | `switch_workspace` R2 |
| 505–516 | issue, commit / rollback | `switch_workspace` R3, R5, R6 |
| 552–553 | lookup by hash (no lock, BUG-2560) | `refresh_access_token` R1, R7 |
| 556–557 | row `None` | `refresh_access_token` R1 |
| 560–567 | revoked and successor → revoke family, commit, raise | `refresh_access_token` R2, R3 |
| 570–571 | revoked | `refresh_access_token` R4 |
| 572–573 | `expires_at <= utcnow()` | `refresh_access_token` R4 |
| 576–578 | user missing | `refresh_access_token` R5 |
| 580–600 | issue same family; find new row; revoke with successor (`if new_row`); touch; commit | `refresh_access_token` R6 |
| 602–607 | `ValueError` / other → rollback, re-raise | `refresh_access_token` R8 |
| 627–637 | `all_devices`; `user_id is None`; revoke all | `logout_session` R1, R2, R3 |
| 638–644 | token truthy; `row and revoked_at is None` | `logout_session` R4 |
| 645–646 | no token | `logout_session` R5 |
| 648–652 | commit; exception → rollback | `logout_session` R6 |
| 692–702 | no account → fake token | `request_password_reset` R1, R2, R4 |
| 705–726 | account → token, messages | `request_password_reset` R3, R4 |
| 769 | always `NotImplementedError` | `reset_password` R1 |
| 819–823 | caller membership missing / not active | `reset_password_by_admin` R1 |
| 826–827 | role not `owner` | `reset_password_by_admin` R2, R7 |
| 830–834 | target membership missing / not active | `reset_password_by_admin` R3, R7 |
| 837–839 | target profile missing | `reset_password_by_admin` R4 |
| 842–849 | hash; flush; revoke all | `reset_password_by_admin` R6, R8, R9 |
| 852–865 | commit; messages; `if revoked` | `reset_password_by_admin` R10 |
| 867–869 | exception → rollback | `reset_password_by_admin` R5 |
| 901–904 | unknown token | `validate_invitation_token` R1 |
| 907–908 | `expires_at < utcnow()` (BUG-2561) | `validate_invitation_token` R2, R3 |
| 911–912 | status not `pending` | `validate_invitation_token` R4 |
| 915–931 | details; message | `validate_invitation_token` R5, R6 |
| 942–944 | nothing sent → return | `update_current_user` R1 |
| 946–947 | `name` sent and not `None` | `update_current_user` R2, R3, R3a |
| 948–949 | `timezone` sent | `update_current_user` R4 |
| 950–957 | `saved_stamp` sent; `None` → destroy, clear | `update_current_user` R5, R7a, R10 |
| 958 | validate | `update_current_user` R6, R6a, R8 |
| 959–966 | old and new both image with different `public_id` → destroy (vector new: none, BUG-2568) | `update_current_user` R7, R7a, R7b, R10 |
| 969–975 | add, commit, refresh; exception → rollback | `update_current_user` R9 |

## Gap log
- G1 (auth_service.cases.md gap 1) — Fact — `TokenPair`'s four fields named, in order, under Facts for the test designer.
- G2 (gap 2) — Fact — `ProfileMeUpdate` is imported from `app.schemas.profile` (Facts).
- G3 (gap 3) — Fact — messages are `ActionMessage` (`type`: `MessageType` str enum, `message`, `timestamp`, `details`) (Facts).
- G4 (gap 4) — Fact + test mechanics — `refresh_tokens.workspace_id` is a nullable FK to `workspaces` (CASCADE): `0` fails at the flush (23503). The claim boundary is observable with a fake `refresh_token_dao`. New rule `_issue_token_pair` R1a.
- G5 (gap 5) — Intent, decided under delegation (2026-11-10) — the reuse branch's commit commits every pending change with the revocation; this is today's behaviour, intended. New rule `refresh_access_token` R2a.
- G6 (gap 6) — Intent, decided under delegation (2026-11-10) — `login_user` R3's second sentence is reached only through BUG-500 and gets no case.
- G7 (gap 7) — Fact — `workspace_audit_logs.ip_address` / `user_agent` and the `departments` table named (Facts).
