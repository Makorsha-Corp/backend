# Spec — `app/core/waitlist_admin.py`

> **Status:** APPROVED
> **Source commit:** e48a092

## Review
> Reviewer: answer each question on its **Answer:** line with one of
> `intended` · `bug` · `bug — <what it should do instead>` · `remove` (unreachable
> code only) · or a question back.
> Then run the describer in `apply-review` mode.

### New questions

### Q1. The email allowlist trusts an email address nobody has verified — 🐞 BUG-540
**Background:** Waitlist signups (the landing-page list of prospective customers: names, emails, IP hashes) can be viewed and have their status changed by a "waitlist admin". A user is a waitlist admin if they are a Makorsha platform admin (`is_platform_admin` flag on their profile) **or** if their account email appears in the server setting `WAITLIST_ADMIN_EMAILS` (a comma-separated list, described in the code as "legacy"). Registration (`POST /auth/register`) does not verify that the registrant owns the email address, and the "email already registered" check and the database unique constraint are exact and case-sensitive on the part before the `@`. The allowlist comparison, however, ignores case and surrounding spaces.
**What happens today:** Any authenticated account whose email, lower-cased and trimmed, equals an allowlisted address gets full waitlist admin access — regardless of whether that person owns the mailbox.
**Example:** `WAITLIST_ADMIN_EMAILS=founder@makorsha.com`. The founder already has an account `founder@makorsha.com`. An outsider registers a new account with `Founder@makorsha.com` (accepted — it is not an exact duplicate, and no verification email is sent), logs in, and calls `GET /waitlist` — they receive the full list of signups and can change their statuses. The same happens with the exact address if the founder has not registered yet.
**Rules affected:** `get_waitlist_admin` R3, R5
**Suggested answer:** bug — only platform admins (`is_platform_admin = True`) are waitlist admins; the unverified-email allowlist no longer grants access (if the allowlist must stay, it may only match an account whose email ownership has been verified).
**Answer:** bug — only platform admins (`is_platform_admin = True`) are waitlist admins; the unverified-email allowlist no longer grants access (if the allowlist must stay, it may only match an account whose email ownership has been verified). (reviewer accepted suggestion)
**Resolution:** the codebase has no email-ownership verification (no verified flag on `Profile`), so the "verified-only allowlist" alternative is not available; the allowlist grants nothing and access depends solely on `is_platform_admin` (best-practice default, delegated by reviewer). The `WAITLIST_ADMIN_EMAILS` setting itself (in `app/core/config.py`) is left for the fix to retire; this spec only requires that it has no effect on access. Rules: `get_waitlist_admin` R3 (tagged); R4, R5 unchanged and still hold under the intended behavior.

### Q2. The "no allowlist configured" 403 exposes server configuration — 🐞 BUG-541
**Background:** When a non-admin user is refused, there are two different refusal messages depending on whether the server has any allowlist configured.
**What happens today:** If `WAITLIST_ADMIN_EMAILS` is empty, any logged-in non-admin gets 403 `"Waitlist admin access requires platform admin or WAITLIST_ADMIN_EMAILS"`; if it is non-empty they get 403 `"Not authorized to view waitlist signups"`. Any user can thereby learn the environment variable name and whether an email allowlist is active.
**Example:** A regular workspace member opens `GET /waitlist` on production (no allowlist set) and sees the message naming `WAITLIST_ADMIN_EMAILS`; on another environment with an allowlist, the message differs — telling them an email-based bypass exists there.
**Rules affected:** `get_waitlist_admin` R2, R4
**Suggested answer:** bug — every refusal returns the same 403 `"Not authorized to view waitlist signups"`; the configuration detail is only logged server-side.
**Answer:** bug — every refusal returns the same 403 `"Not authorized to view waitlist signups"`; the configuration detail is only logged server-side. (reviewer accepted suggestion)
**Resolution:** every refusal is 403 `"Not authorized to view waitlist signups"`, whatever the allowlist contains. Server-side logging of the refusal is optional and not asserted by unit tests (best-practice default, delegated by reviewer) — once BUG-540 is fixed the allowlist no longer affects access, so there is no configuration detail left to log. Rules: `get_waitlist_admin` R2 (tagged); R4 unchanged.

## Overview
A FastAPI dependency that guards the platform-level waitlist admin endpoints (`GET /waitlist` list signups and `PATCH /waitlist/{signup_id}/status` in `app/api/v1/endpoints/waitlist.py`). It receives the authenticated user (from `get_current_active_user`, which today returns the JWT user unchanged — no extra "active" check) and lets them through only if they are a Makorsha platform admin; everyone else gets the same 403. *(Today it also admits users whose email is on the `WAITLIST_ADMIN_EMAILS` server setting — BUG-540 — and uses a second, configuration-revealing refusal message — BUG-541.)* It only reads the user object and settings; no database access, no writes.

**Callables:** 1 specified · 0 not specified
**Externals to mock:** none (settings value is patched, see notes)
**Integration-only behavior:** authentication itself (missing/invalid JWT → 401 from `get_current_user`) and wiring onto the two waitlist endpoints — needs the real dependency chain / HTTP routing.

**Notes for the test designer:**
- Framework glue, but trivially unit-testable: call `get_waitlist_admin(current_user=<Profile>)` directly with a `Profile` (factory-created or an unsaved `Profile(...)` instance). Passing the argument explicitly bypasses the `Depends(get_current_active_user)` default; no app or HTTP client needed.
- The allowlist is read from the `settings` object at call time (`app.core.config.settings.WAITLIST_ADMIN_EMAILS`, a `list[str]`). Patch that attribute (e.g. `monkeypatch.setattr(settings, "WAITLIST_ADMIN_EMAILS", [...])`) per test; it can be set to a list containing raw, unstripped, mixed-case or blank strings. Under the intended behavior the value must make no difference to the outcome, so bug tests should set it to a list that *would* match today, to prove it grants nothing. If the fix removes the setting entirely, use `monkeypatch.setattr(..., raising=False)`.
- `Profile.email` is NOT NULL in the database; the `None` email case (R5) is only reachable with an unsaved in-memory `Profile`.
- `HTTPException` is `fastapi.HTTPException`; assert `.status_code` and `.detail`.

## Not specified
(none)

---

## `get_waitlist_admin(current_user)`
**Shape:** validator
**Persistence:** pure
**Visibility:** public (FastAPI dependency on `GET /waitlist` and `PATCH /waitlist/{signup_id}/status`)

**Purpose:** Allow only platform admins to use the waitlist admin endpoints.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `current_user` | `Profile` | The authenticated user. Only `is_platform_admin` and `email` are read today (intended: only `is_platform_admin` matters). |
| *(setting)* `WAITLIST_ADMIN_EMAILS` | `list[str]` | Legacy allowlist. From env, a comma-separated string is split, entries trimmed, blanks dropped (settings validator). Any list given directly is used as-is; the function trims, lower-cases and drops blank entries itself. Intended: has no effect on access (BUG-540). |

**Returns:** the same `current_user` object (identity, unchanged) when access is granted.

**Rules:**
- **R1.** If the user's `is_platform_admin` is truthy, the user is returned — regardless of email and regardless of the allowlist (even an empty allowlist, even an email not on it). If the user object has no `is_platform_admin` attribute at all, it is treated as `False`.
- **R2.** [BUG-541] If the user is not a platform admin (`is_platform_admin` is `False`, `None` or absent) and the allowlist is empty after normalisation — an empty list, or a list containing only `""` / whitespace-only entries — the call raises 403 with detail `"Not authorized to view waitlist signups"` (the same message as R4). This happens whatever the user's email is. *(Today: detail is `"Waitlist admin access requires platform admin or WAITLIST_ADMIN_EMAILS"`.)*
- **R3.** [BUG-540] A non-admin user whose email matches an allowlist entry is **not** admitted: the call raises 403 with detail `"Not authorized to view waitlist signups"`. This holds for an exact match and for a match that differs only in case or surrounding whitespace (user `Founder@Makorsha.com`, allowlist entry ` founder@makorsha.com `). *(Today: the user is returned when their email, trimmed and lower-cased, equals an allowlist entry trimmed and lower-cased; matching is exact otherwise — `founder@makorsha.com.evil` and `makorsha.com` do not match.)*
- **R4.** A non-admin user whose normalised email is not in a non-empty allowlist gets 403 with detail `"Not authorized to view waitlist signups"`. ✅
- **R5.** A non-admin user with email `None` or an empty/whitespace-only email is refused with the R4 403 when the allowlist is non-empty (the email is treated as `""`, which never matches since blank allowlist entries are dropped). ✅
- **R6.** Nothing is written and the user object is not modified in any outcome.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| Not platform admin (any email, any allowlist content) | `HTTPException` 403 | `Not authorized to view waitlist signups` |

*(Today: empty allowlist → detail `Waitlist admin access requires platform admin or WAITLIST_ADMIN_EMAILS` (BUG-541); allowlisted email → no error, user returned (BUG-540).)*

**Side effects:** none.

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 11 | `is_platform_admin` truthy (getattr default `False`) → return | R1 |
| 14–18 | comprehension over allowlist: entry blank after strip → skipped; else trimmed + lower-cased | R2, R3 |
| 14–18 | loop over empty / one / many entries | R2, R3 |
| 19 | allowlist empty → 403 (config message today) | R2 |
| 25 | `current_user.email or ""` — `None`/`""` → `""` | R5 |
| 26 | normalised email not in allowlist → 403 | R4, R5 |
| 32 | email in allowlist → return user (today; intended 403) | R3 |
| config.py 50–53 | settings validator: string → split on `,`, trim, drop blanks; list passed through | Inputs (setting) |
