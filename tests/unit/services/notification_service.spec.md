# Spec — `app/services/notification_service.py`

> **Status:** APPROVED (2026-11-03; nothing open). Stays APPROVED after fill-gaps (Gap log at the end; decided by Claude under the reviewer's delegation (2026-11-03)).
> **Source commit:** e48a092

> **Form.** As `tests/unit/services/department_service.spec.md`. This service has **no manager** and does **not** inherit `BaseService`. It reads and writes through `notification_dao` and `workspace_member_dao`, and reads `profiles` directly for previews. Below it: `tests/unit/dao/notification.spec.md`, `tests/unit/dao/workspace_member.spec.md` (APPROVED).

> **Routed here:** notification DAO FU-1: `mark_read` leaves loaded rows stale, and nothing reads them after the service's commit (`mark_read` R3; no rule change); the per-row label lookup of `GET /me/notifications/` is the endpoint's, not this service's (FU-2).
>
> **Review round 2026-11-03.** **Decided by Claude under the reviewer's delegation (2026-11-03):** P1 and Q1. Neither is the owner's own answer. Who may receive a notification is not widened by either: both only remove recipients or text. House-rule line: BUG-1534. New bugs: BUG-1534, BUG-1535, BUG-1536.
>
> **Verified by running** (`h.py`, `v4_notif.py`, `v6_digits.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\svc1\`, one outer transaction rolled back against `marker_test`, session as the `db` fixture; nothing persisted): every "Today:" note below. Previews: a member's name, an outsider's name (a profile whose only membership is in another workspace), `@User 999999999` for an unknown id, plain text, a token cut at 200 characters (`…@[5`), a token that just fits, `max_len=5`, `""`, a suspended member's name, malformed tokens left alone, one id twice, Arabic-Indic and Bengali digits resolved to the profile, a superscript digit left alone. Fan-out: actor, an active member, the same member twice, an outsider, a suspended member, an unknown id → two notifications (the actor and the member), with every field; an empty list → none; rows visible in the session before any commit. `list_for_user` counts; `mark_read` of all → 1, kept after a test-level rollback (committed), a second call → 0. **Not run:** the live stream (`pg_notify` delivery happens only on a real commit); the intended behavior of BUG-1534 … BUG-1536.

## Review
> All answered; nothing pending.

### Quick list — all answered
| # | What the code does today, in plain words | Answer | Decided by |
|---|---|---|---|
| HR-16 | A mention preview shows the name of anyone on the platform | bug (BUG-1534) | house rule |
| P1 | `@[١٢]` written with non-ASCII digits counts as a mention of profile 12 | bug (BUG-1536) | Claude, delegated |
| Q1 | Mentioning yourself sends you a notification | bug (BUG-1535) | Claude, delegated |

### House-rule violations — applied automatically

- **HR-16** `humanize_mention_preview` R5 — the preview looks profiles up by id over the whole platform, so `@[<id>]` of a person outside the workspace shows that person's name to the recipients (verified: "Secret Outsider"). Ids are small sequential numbers, so a member can list the names behind them by mentioning himself (Q1) with a run of ids. Intended: only profiles with a membership in the workspace are named; any other id reads `@User <id>`, exactly like an unknown id. *(requires new parameter `workspace_id`; the discussion service passes its own.)*
**Answer:** bug — per HR-16 (house rule)
**Resolution:** 🐞 BUG-1534 (pattern `missing-workspace-scope`). Rules: `humanize_mention_preview` R5.

Reached through the DAO and cited: BUG-1412 (order), BUG-1413 (`read_at`), BUG-1414 (`ids: []`), one pass-through case each.

Checked and **not** violated: **HR-4, HR-9** — no soft delete, no audit column. **HR-5, HR-6, HR-7** — the DAO's (`GET /me/notifications/` enforces `1 <= limit <= 200`, `skip >= 0`). **HR-8** — no `LIKE`. **HR-10** — `mark_read` is one conditional update; a mention fan-out runs once per new message. **HR-16** on recipients — `fan_out_mentions` notifies only active members of the workspace; on lists and marks — the DAO filters by workspace and recipient.

**Permission checks:** a person reads and marks only their own notifications in the current workspace (the DAO's filter by recipient and workspace); a mention reaches only active members. Nothing else.

### Precedent matches — all accepted (decided by Claude under the reviewer's delegation (2026-11-03))

### P1. Non-ASCII digits make a mention — 🐞 BUG-1536
**Background:** A mention is written `@[<profile id>]` in a discussion message. The pattern uses `\d`, which matches every Unicode decimal digit, and Python's `int` reads them. BUG-162 ruled the same for date-times: only ASCII `0-9` count (as HR-8 for digit shortcuts). The discussion service extracts the ids to notify with the same pattern (FU-1).
**What happens today:** `@[১২]` (Bengali digits) and `@[١٢]` (Arabic-Indic) both show as `@Bob` when Bob is profile 12 (verified).
**Example:** A message quoting "item [১২]" after an `@` names someone, and that person is notified.
**Rules affected:** `humanize_mention_preview` R7
**Answer:** bug — per BUG-162 precedent: only ASCII `0-9` inside `@[…]` make a mention; any other digit leaves the text as typed
**Resolution:** 🐞 BUG-1536 (pattern `unicode-digit-regex-match`) — decided by Claude under the reviewer's delegation (2026-11-03). Rules: `humanize_mention_preview` R7. The extractor in the discussion service must change with it (FU-1).

### New questions

### Q1. Mentioning yourself sends you a notification — 🐞 BUG-1535
**Background:** When a discussion message mentions people, each mentioned active member gets a "mention" notification. The author is not left out.
**What happens today:** Ann writes "@[Ann] please check tomorrow" as a note to herself: her bell shows "Ann mentioned you" (verified: the actor received a notification).
**Example:** Ann copies a message that mentions the whole team, herself included, and gets her own mention in her unread count.
**Rules affected:** `fan_out_mentions` R4
**Suggested answer:** `bug — the author is never notified of a mention in their own message; everyone else as today.` It also closes the easy way to read a preview built from one's own ids (HR-16 line). Alternative: `intended` — self-mentions work as reminders.
**Answer:** as suggested — decided by Claude under the reviewer's delegation (2026-11-03).
**Resolution:** 🐞 BUG-1535 (pattern `actor-notified-of-own-action`). Rules: `fan_out_mentions` R4.

## Overview
`NotificationService` serves a person's inbox (`/me/notifications/`: list, mark read) and creates mention notifications when a discussion message names people. `humanize_mention_preview` turns `@[<id>]` tokens into `@<name>` for the stored preview. Mentions are written inside the discussion service's transaction, which commits; `mark_read` commits itself; the list reads only.

**Callables:** 5 specified · 1 not specified
**Externals to mock:** none. `pg_notify` is sent by the DAO inside the transaction and delivered only on a real commit: nothing to mock under the `db` fixture.
**Integration-only behavior:** `GET /me/notifications/` shaping (`entity_label`, `actor`) and its paging bounds; `POST /me/notifications/read/` returning `{"marked_read": n}`; the live stream.

**Facts for the test designer**
- Import: `from app.services.notification_service import NotificationService, notification_service, humanize_mention_preview, _active_workspace_member_ids`. Parameters are positional-or-keyword. The endpoint calls `list_for_user` and `mark_read` positionally; the discussion service calls `fan_out_mentions` by keyword and `humanize_mention_preview(db, message)`.
- `MarkReadRequest(ids: list[int] | None = None)` from `app.schemas.notification`.
- Profiles and workspaces from `tests/unit/factories.py`; a membership is `WorkspaceMember(workspace_id, user_id, role, status)` from `app.models.workspace_member` (`role` NOT NULL, any string; `status` default `"active"`).
- `notifications` table: notification DAO spec, Model facts.

**Notes for the test designer**
- Session and commits: as the Notes of `department_service.spec.md`. `mark_read`'s commit is a savepoint release under the `db` fixture; assert "committed" with a test-level `db.rollback()` and a re-read (`db.expire_all()` first: the DAO update does not refresh loaded rows).
- **`fan_out_mentions` order:** recipients are visited in set order; never assert the order of the created rows or their ids, only the set of `(recipient_user_id, …)`.
- **BUG-1534:** the new `workspace_id` parameter does not exist today (`TypeError`) → strict xfail. It is required with no default, so the 13 preview cards that pass today get `workspace_id=W1.id` added when the fix lands (one edit each, no rule change); give the outsider a membership in **another** workspace, and one profile with no membership at all.
- **BUG-1535, BUG-1536:** deterministic today → strict xfail. Build non-ASCII digits from the id: `"".join(chr(0x09E6 + int(c)) for c in str(pid))`.

## Not specified
- `notification_service` — module-level singleton, no logic. (`_MENTION_RE` is the pattern; its behavior is in `humanize_mention_preview`'s rules.)

---

## `humanize_mention_preview(db, message, max_len=200)` → [BUG-1534] `humanize_mention_preview(db, message, workspace_id, max_len=200)`
**Shape:** mapper · **Persistence:** reads · **Visibility:** public (used by: `DiscussionService.create`, for the `preview` of each mention notification)

**Purpose:** The short text a mention notification shows, with `@[id]` tokens turned into names.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `message` | str | the discussion message as typed |
| `workspace_id` | int | [BUG-1534] new, **required, no default** (a default would leave the unscoped lookup reachable); passed by keyword. Every preview case calls with `workspace_id=` after the fix, so the cases that pass today change with it |
| `max_len` | int, default `200` | the message is cut to this many characters **before** tokens are replaced |

**Returns:** a `str`.

**Rules:**
- **R1.** The text is the first `max_len` characters of the message; tokens are replaced afterwards, so the result can be longer than `max_len` (names are longer than tokens) or shorter. A token cut by the limit stays as cut: 197 × `x` + `@[5]` gives `…xxx@[5`; a token that fits whole is replaced. `""` gives `""`; `max_len=5` on `"abcdefgh"` gives `"abcde"`.
- **R2.** A text without a token is returned unchanged, and no profile is read.
- **R3.** A token is `@[` + digits + `]`. Each token of a known profile becomes `@<profile name>`; the same id twice is replaced twice. Leading zeros are read as the number (`@[007]` is profile 7).
- **R4.** An id with no profile becomes `@User <id>` (`@User 999999999`).
- **R5.** [BUG-1534] (HR-16) An id whose profile has no membership in the workspace (in any status) becomes `@User <id>`, exactly as R4: no name of anyone outside the workspace appears. A member in any status (`active`, `suspended`, …) is named. *(Today: any profile on the platform is named. Verified.)*
- **R6.** Text that only looks like a token is left as typed: `@[abc]`, `@[]`, `@[ 1]`, `@[-1]`.
- **R7.** [BUG-1536] (P1) Only ASCII `0-9` make a token: `@[১২]` and `@[١٢]` are left as typed. *(Today: read as the number and replaced by that profile's name. Verified.)* A digit that is not a decimal digit (`²`) is left as typed today too.
- **R8.** Nothing is written.

**Errors:** none. **Side effects:** none

---

## `_active_workspace_member_ids(db, workspace_id)`
**Shape:** helper · **Persistence:** reads · **Visibility:** internal (used by: `fan_out_mentions`)

**Rules:**
- **R1.** The set of `user_id`s of the workspace's memberships whose `status` is exactly `"active"` (workspace member DAO `get_workspace_members` R1–R3: no cap, other workspaces never included). Its order does not matter: it is a set.

**Errors:** none. **Side effects:** none

---

## `NotificationService.list_for_user(db, workspace_id, user_id, unread_only=False, skip=0, limit=50)`
**Shape:** list · **Persistence:** reads · **Visibility:** public (used by: `GET /me/notifications/`)

**Returns:** the tuple `(items, total, unread_count)`.

**Rules:**
- **R1.** The answer is the notification DAO's `get_for_user` for these arguments, unchanged (DAO R1–R6, with BUG-1412). Defaults: `unread_only=False`, `skip=0`, `limit=50`.
- **R2.** Nothing is written, committed or rolled back.

**Errors:** as the DAO (negative paging → `DataError`). **Side effects:** none

---

## `NotificationService.mark_read(db, workspace_id, user_id, data)`
**Shape:** update · **Persistence:** writes · **Visibility:** public (used by: `POST /me/notifications/read/`)

**Returns:** `int`, the number of notifications marked.

**Rules:**
- **R1.** The user's unread notifications in the workspace named by `data.ids` (all of them for `None` or an omitted `ids`) are marked read as the DAO's `mark_read` does (DAO R1–R4, with BUG-1413, BUG-1414); the number is returned.
- **R2.** The change is committed: it survives a later rollback of the session (verified).
- **R3.** Rows of the session loaded before the call are expired by the service's commit, so their next attribute read reloads and shows `is_read = True` (verified through the service, `v7_gaps.py`). The DAO's own stale-row behavior (DAO R4) is not observable through this service.
- **R4.** If the update or the commit raises (in a test: `patch.object(notification_dao, "mark_read", side_effect=...)` from `app.dao.notification`, or a patched `db.commit`), the exception reaches the caller unchanged, nothing is saved, and the service does **not** roll back: the session is left for the caller (the request's session is discarded by the API).

**Errors:** database errors, unchanged. **Side effects:** notifications marked read, committed.

---

## `NotificationService.fan_out_mentions(db, workspace_id, actor_user_id, mentioned_user_ids, entity_type, entity_id, source_id, preview=None)`
**Shape:** create · **Persistence:** writes · **Visibility:** public (used by: `DiscussionService.create`, only when the message has at least one mention; it commits afterwards)

**Purpose:** Put a "mention" notification in the inbox of each mentioned active member.

**Returns:** `None`.

**Rules:**
- **R1.** Each distinct id in `mentioned_user_ids` that is an active member of the workspace (`_active_workspace_member_ids` R1) gets exactly one notification: `workspace_id`, `recipient_user_id` = the id, `actor_user_id`, `notification_type = "mention"`, `entity_type`, `entity_id`, `source_type = "discussion"`, `source_id`, `preview` as given (`None` by default), unread (notification DAO `create` R1, R2).
- **R2.** An id that is not an active member is skipped without error: a suspended or invited member, a member of another workspace only, an unknown id.
- **R3.** An id listed twice gets one notification.
- **R4.** [BUG-1535] (Q1) The actor is never notified, even when mentioned and an active member. *(Today: notified. Verified.)*
- **R5.** An empty list creates nothing.
- **R6.** Nothing is committed or rolled back here: the rows are flushed into the caller's transaction (visible in the session at once), and the caller's commit saves them with the message. A database error reaches the caller unchanged.
- **R7.** The order in which recipients are written is not specified.

**Errors:** database errors from the DAO, unchanged (notification DAO `create` R4).

**Side effects:** notification rows flushed, one `pg_notify` each (delivered when the caller commits); no commit.

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 14 | `\d+` matches any Unicode decimal digit (BUG-1536) | `humanize_mention_preview` R3, R6, R7 |
| 19 | cut to `max_len` before replacing | `humanize_mention_preview` R1 |
| 20–22 | no token → return text, no read | `humanize_mention_preview` R2 |
| 24–25 | profiles by id, any workspace (BUG-1534) | `humanize_mention_preview` R3, R5, R8 |
| 27–29 | name found / `User <id>` fallback | `humanize_mention_preview` R3, R4 |
| 31 | replace every token | `humanize_mention_preview` R3 |
| 35–38 | active members of the workspace → set of user ids | `_active_workspace_member_ids` R1 |
| 51–53 | DAO `get_for_user`, positional | `list_for_user` R1, R2 |
| 62–64 | DAO `mark_read`, commit, count; no try / rollback | `mark_read` R1–R4 |
| 78 | recipients allowed: active members | `fan_out_mentions` R1, R2 |
| 80 | loop over the set of ids (dedupe, any order; empty → nothing) | `fan_out_mentions` R3, R5, R7 |
| 81–82 | not allowed → skip; the actor is not excluded (BUG-1535) | `fan_out_mentions` R2, R4 |
| 83–94 | DAO `create` with the fixed fields; no commit | `fan_out_mentions` R1, R6 |
| 97 | module singleton | Not specified |

## Follow-ups for other reviews
> Nothing below is a rule of this service.

| # | Where it must be looked at | What | Came from |
|---|---|---|---|
| FU-1 | **Discussion service** (`app/services/discussion_service.py`, not yet described) | (a) BUG-1536: `_extract_mentions` uses the same `\d` pattern; it must take ASCII digits only, together with this fix, or notifications and previews disagree. (b) BUG-1534: pass the workspace to `humanize_mention_preview`. (c) The preview is cut at 200 characters before names are filled in (R1), so a token at the cut shows as `@[5`. Cosmetic; cut after replacing if it matters. | P1, HR-16 |
| FU-2 | **Notification endpoint** (`app/api/v1/endpoints/notifications.py`) | Notification DAO FU-1: one label lookup per row, up to 200 per page. A performance note, no rule. | DAO FU-1 |

## Gap log
G1 (notification_service.cases.md gap 1) — Intent, delegated — BUG-1534's `workspace_id` is required, no default; the passing preview cards change with the fix. Inputs table, Notes; BUG-1534 row.
G2 (gap 2) — Test mechanics — how to make the update fail: patch `notification_dao.mark_read`. `mark_read` R4.
G3 (gap 3) — Fact, verified by running (`v7_gaps.py`) — the commit expires loaded rows; they read `True` afterwards. `mark_read` R3 restated.
