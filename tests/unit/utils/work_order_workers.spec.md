# Spec — `app/utils/work_order_workers.py`

> **Status:** APPROVED
> **Source commit:** e48a092

## Review
> Reviewer: answer each question on its **Answer:** line with one of
> `intended` · `bug` · `bug — <what it should do instead>` · `remove` (unreachable
> code only) · or a question back.
> Then run the describer in `apply-review` mode.

### New questions

### Q1. A name shared by two members is silently given to one of them at random — 🐞 BUG-380
**Background:** Work orders let users type worker names as free text ("Rahim, Karim"). Each typed name is matched against the workspace's active members by display name or email, ignoring case and surrounding spaces. The matched members become the work order's assignees (or the recorded completers). Member names are not unique inside a workspace, and the member list is loaded with no sort order.
**What happens today:** When a typed name matches more than one active member (e.g. two members both named "Rahim", or one member's name equals another member's email), the first member in the loaded list wins; which one is first is not defined, so it can differ between calls. The other member is never considered and nothing tells the user the name was ambiguous.
**Example:** Workspace has active members #7 "Rahim" and #12 "rahim". A user assigns a work order to "Rahim". The work order is assigned to #7 or #12 depending on database row order; the user sees "Rahim" in both cases and cannot tell the wrong person got it.
**Rules affected:** `resolve_names_to_members` R4, R5; `load_active_member_lookups` R3
**Suggested answer:** bug — a name that matches more than one active member is treated as unmatched (kept as typed, reported in `unmatched_names`), never assigned to an arbitrary member
**Answer:** bug — a name that matches more than one active member is treated as unmatched (kept as typed, reported in `unmatched_names`), never assigned to an arbitrary member (reviewer accepted suggestion)
**Resolution:** an ambiguous name (matching two or more distinct members) is unmatched: no id, listed in `unmatched_names`, shown as typed. "More than one member" means more than one distinct `user_id`; several candidate entries with the same `user_id` still count as one match (best-practice default, delegated by reviewer). Member load order then no longer affects the result; `load_active_member_lookups` R3 stays a fact, untagged. Rules: `resolve_names_to_members` R5.

### Q2. Repeated names are de-duplicated in the member ids but not in the display text — 🐞 BUG-381
**Background:** Resolution returns the matched member ids and a display string built from the typed names (matched names replaced by the member's stored name).
**What happens today:** If the same member is typed twice (or once by name and once by email), their id appears once in `matched_user_ids`, but their name appears twice in `display_text`. Unmatched names typed twice also appear twice in both `unmatched_names` and the display text. `display_names_for_user_ids` likewise repeats a name when an id is repeated.
**Example:** Text "Rahim, rahim@x.com, rahim" for member #7 "Rahim" (email rahim@x.com) → `matched_user_ids = [7]`, `display_text = "Rahim, Rahim, Rahim"`; the completion record shows Rahim three times while one person is credited.
**Rules affected:** `resolve_names_to_members` R7, R9; `display_names_for_user_ids` R5
**Suggested answer:** bug — display text lists each resolved member once (first occurrence order), and repeated unmatched names (case-insensitive after trimming) appear once in both `unmatched_names` and the display text
**Answer:** bug — display text lists each resolved member once (first occurrence order), and repeated unmatched names (case-insensitive after trimming) appear once in both `unmatched_names` and the display text (best-practice default, delegated by reviewer)
**Resolution:** no Answer line was filled; the suggested answer is adopted as best practice. Each member appears once in the display text at the position of its first occurrence; unmatched names are de-duplicated by trimmed + `casefold` comparison (same normalisation as matching), keeping the first occurrence's typed form and position; `display_names_for_user_ids` likewise shows each id once (best-practice default, delegated by reviewer). `parse_worker_names` R5 (duplicates kept when splitting) is unchanged — de-duplication belongs to resolution. Rules: `resolve_names_to_members` R7a, R9a; `display_names_for_user_ids` R5.

### Q3. A member whose stored name is only spaces disappears from the display text — 🐞 BUG-382
**Background:** When a typed name resolves to a member, the display text shows the member's stored name, or the email when the name is empty. Profile names should never be blank (HR-1), but whitespace-only names can exist in stored data. The same fallback is used when the completion record is built from explicit user ids.
**What happens today:** A stored name of only spaces counts as "present", so it is chosen over the email; it is then trimmed to nothing and dropped when the display string is joined. The member is credited (their id is in the result) but is missing from the displayed text. For explicit ids the same happens: no label at all, not even the email or `User #<id>`.
**Example:** Member #31 has name `"   "` and email `w@x.com`. Typing `"w@x.com, Rahim"` gives ids `[31, 7]` but display text `"Rahim"`; the work order shows only Rahim although two people are credited.
**Rules affected:** `resolve_names_to_members` R8a; `display_names_for_user_ids` R7
**Answer:** bug — a whitespace-only stored name is treated like an empty name: fall back to the email, then (for explicit ids) to `User #<id>` (best-practice default, delegated by reviewer)
**Resolution:** blank-after-trim name → email (trimmed); blank-after-trim email too → `User #<id>` in `display_names_for_user_ids` (in `resolve_names_to_members` such a member can never match, per R4). Every credited member always has a visible display entry (best-practice default, delegated by reviewer). Rules: `resolve_names_to_members` R8a; `display_names_for_user_ids` R7.

## Overview
Turns the free-text "assigned to" / "completed by" worker field of a work order into workspace member ids. Text is split on commas/semicolons, each name is matched case-insensitively against active workspace members' profile name or email, and a normalised display string is produced. Called only by `WorkOrderManager._sync_assignees_from_text` (create/update of a work order, which replaces the assignee rows with `matched_user_ids`) and `WorkOrderManager._resolve_completion_workers` (completion). The stored `assigned_to` text itself is kept as typed; only ids are derived from it.

**Callables:** 6 specified · 3 not specified
**Externals to mock:** none
**Integration-only behavior:** none

**Notes for the test designer:** `parse_worker_names`, `join_worker_names`, `resolve_names_to_members` and `resolve_worker_text_to_members` are pure — build `MemberLookup` values directly, no database. `load_active_member_lookups` and `display_names_for_user_ids` need the real session with `Profile` and `WorkspaceMember` rows (`Profile.name` and `Profile.email` are NOT NULL, email unique; `WorkspaceMember` is unique on `(workspace_id, user_id)`, `status` in `'active'`/`'suspended'`/`'invited'`). Profiles have no soft-delete column. A "missing profile" can be simulated by passing a user id with no profile row to `display_names_for_user_ids`; for `load_active_member_lookups` the FK (`workspace_members.user_id → profiles.id`, `ON DELETE CASCADE`, not deferrable) makes a membership without a profile impossible: inserting one fails at flush, and deleting the profile deletes the membership. `load_active_member_lookups` R5 is therefore a defensive branch with no reachable setup — design no case for it (patching the DAO is not an allowed simulation); its line is expected to stay uncovered.
- The typed-name fallback in `resolve_names_to_members` R8 (member `name` and `email` both empty) is likewise unreachable, because such a member never matches (R4); design no case for it.

## Not specified
- `MemberLookup` — frozen dataclass (`user_id`, `name`, `email`), no logic
- `WorkerNameResolution` — frozen dataclass (`matched_user_ids`, `unmatched_names`, `display_text`), no logic
- `_normalize` — private; behavior stated in `resolve_names_to_members` R4

---

## `parse_worker_names(text)`
**Shape:** helper
**Persistence:** pure
**Visibility:** internal (used by: `resolve_worker_text_to_members`)

**Purpose:** Split a free-text worker field into individual names.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| text | `str \| None` | Free text; any value accepted |

**Returns:** `list[str]` of trimmed, non-empty names in the order they appear.

**Rules:**
- **R1.** `None`, `""` or whitespace-only text returns `[]`.
- **R2.** Names are separated by commas and semicolons; any run of consecutive separators (e.g. `",;,"`) counts as one split. No other character separates names — newlines, `"and"`, `"&"`, `"/"` stay inside a name (`"Rahim\nKarim"` → `["Rahim\nKarim"]`).
- **R3.** Each name has leading/trailing whitespace removed; inner whitespace and case are kept (`"  Abdul  Karim "` → `"Abdul  Karim"`).
- **R4.** Empty or whitespace-only pieces are dropped (`",Rahim,, ;Karim,"` → `["Rahim", "Karim"]`).
- **R5.** Duplicates are kept and order is preserved (`"A, A"` → `["A", "A"]`).

**Errors:** none

**Side effects:** none

---

## `join_worker_names(names)`
**Shape:** helper
**Persistence:** pure
**Visibility:** internal (used by: `resolve_names_to_members`, `display_names_for_user_ids`)

**Purpose:** Build a comma-separated display string from a list of names.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| names | `Sequence[str]` | Names; `None` elements tolerated |

**Returns:** `str`.

**Rules:**
- **R1.** Names are trimmed and joined with `", "` (comma + one space), in input order (`["Rahim", " Karim "]` → `"Rahim, Karim"`).
- **R2.** `None`, `""` and whitespace-only entries are skipped (no empty slot, no doubled separator).
- **R3.** An empty sequence, or one with only skipped entries, returns `""`.
- **R4.** Duplicates are kept.
- **R5.** No escaping: a name that itself contains a comma is joined as-is.

**Errors:** none

**Side effects:** none

---

## `resolve_names_to_members(names, members)`
**Shape:** compute
**Persistence:** pure
**Visibility:** public (used by: `resolve_worker_text_to_members`)

**Purpose:** Match each typed name against a list of members and report matched ids, unmatched names and a display string.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| names | `Iterable[str]` | Typed names; iterated once; elements must be strings (a `None` element raises `AttributeError`) |
| members | `Sequence[MemberLookup]` | Candidates; `name`/`email` may be `None` |

**Returns:** `WorkerNameResolution(matched_user_ids, unmatched_names, display_text)`.

**Rules:**
- **R1.** A name that is empty or whitespace-only is skipped entirely: not matched, not in `unmatched_names`, not in the display text.
- **R2.** Empty `names` (or only blank names) → `matched_user_ids = []`, `unmatched_names = []`, `display_text = ""`.
- **R3.** Empty `members` → every non-blank name is unmatched.
- **R4.** A name matches a member when, after trimming and case-folding both sides (Unicode `casefold`, so `"STRASSE"` matches `"straße"`), it equals the member's `name` or the member's `email`. Inner whitespace must match exactly (`"Abdul  Karim"` does not match `"Abdul Karim"`). No partial / prefix matching. A member whose `name` and `email` are both `None` or blank is never matched.
- **R5.** [BUG-380] When a name matches two or more members with **different** `user_id`s (e.g. two members named "Rahim", or one member's name equal to another member's email), the name is ambiguous and treated as unmatched: no id is added to `matched_user_ids`, the trimmed name goes to `unmatched_names` (per R7/R7a), and the display text shows the typed name (per R9). The result does not depend on the order of `members`. If every matching entry has the same `user_id` (e.g. the same member listed twice), it is a normal match for that member (best-practice default, delegated by reviewer). *(Today: the first matching member in `members` order wins; the others are ignored and nothing reports the ambiguity.)*
- **R6.** Matched member ids are listed in order of first match, each id once, even if typed several times or reached via both name and email.
- **R7.** Each non-blank name that matches no member (or is ambiguous per R5) is added to `unmatched_names` trimmed (inner whitespace and case as typed), in input order.
- **R7a.** [BUG-381] A repeated unmatched name appears in `unmatched_names` only once: names are compared after trimming and `casefold` (same as R4), and the first occurrence's typed form and position are kept (`"Unknown, unknown , UNKNOWN"` → `["Unknown"]`). *(Today: every occurrence is listed — `["Unknown", "unknown", "UNKNOWN"]`.)*
- **R8.** For a matched name, the display text shows the member's `name` (trimmed); if the member's `name` is `None`/`""`, the member's `email` (trimmed). (Typing `"rahim@x.com"` for member "Rahim" displays `"Rahim"`; typing `"rahim"` displays `"Rahim"`.) The code has a third fallback (the typed name when both `name` and `email` are empty), but it is unreachable: such a member never matches (R4). No case.
- **R8a.** [BUG-382] A matched member whose `name` is whitespace-only (e.g. `"   "`) is displayed like one whose name is empty: the member's `email`, trimmed (member #31 `"   "` / `"w@x.com"`, typed `"W@X.COM, Rahim"` with members `[#31, M7]` → display `"w@x.com, Rahim"`, ids `[31, 7]`). The member always has a visible display entry (best-practice default, delegated by reviewer). *(Today: the whitespace name is chosen, trimmed to `""` and dropped by the join — display `"Rahim"`, the member has no entry.)*
- **R9.** For an unmatched name, the display text shows the typed name trimmed. Display entries keep input order and are joined per `join_worker_names` R1–R2.
- **R9a.** [BUG-381] The display text has one entry per resolved member and one per distinct unmatched name (per R7a), each at the position of its first occurrence. A member typed several times — by name, by email, in different case — is displayed once (`"Rahim, rahim@x.com, rahim"` for member #7 "Rahim" → `"Rahim"`; `"Rahim, Unknown, rahim"` → `"Rahim, Unknown"`). Two different members whose stored names are equal each keep their own entry. *(Today: one display entry per non-blank typed name — `"Rahim, Rahim, Rahim"`.)*

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| an element of `names` is `None` / not a string | `AttributeError` | (Python default) |

**Side effects:** none

---

## `resolve_worker_text_to_members(text, members)`
**Shape:** compute
**Persistence:** pure
**Visibility:** public (used by: `WorkOrderManager._sync_assignees_from_text`, `WorkOrderManager._resolve_completion_workers`)

**Purpose:** Resolve a raw free-text worker field against members.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| text | `str \| None` | Raw worker field |
| members | `Sequence[MemberLookup]` | Candidates |

**Returns:** `WorkerNameResolution`.

**Rules:**
- **R1.** Result equals splitting `text` per `parse_worker_names` R1–R5 and resolving the pieces per `resolve_names_to_members` R1–R9 (e.g. `"rahim; Unknown,"` with member #7 "Rahim" → ids `[7]`, unmatched `["Unknown"]`, display `"Rahim, Unknown"`).
- **R2.** `None` / blank text → empty resolution (`[]`, `[]`, `""`).

**Errors:** none

**Side effects:** none

---

## `load_active_member_lookups(session, workspace_id)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `WorkOrderManager._sync_assignees_from_text`, `WorkOrderManager._resolve_completion_workers`)

**Purpose:** Load the active members of a workspace with their profile name and email, as match candidates.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| session | `Session` | Real DB session |
| workspace_id | `int` | Not validated; unknown id → empty list |

**Returns:** `list[MemberLookup]`, one per active membership.

**Rules:**
- **R1.** Only memberships of `workspace_id` with `status == 'active'` are returned; `'suspended'` and `'invited'` members, and members of other workspaces, are excluded.
- **R2.** All active members are returned — no cap / pagination.
- **R3.** No defined order (no `ORDER BY`); order is whatever the database returns; tests must not assert an order. Once BUG-380 is fixed this order has no effect on name resolution (`resolve_names_to_members` R5). ✅
- **R4.** Each entry has `user_id` = the member's user id, `name` and `email` = that user's profile name and email.
- **R5.** If no profile exists for the member's user id, the entry is still returned with `name = None`, `email = None` (such a member can never be matched, per `resolve_names_to_members` R4).
- **R6.** A workspace with no active members (or a non-existent workspace id) → `[]`.

**Errors:** none

**Side effects:** none (read-only; no flush or commit)

---

## `display_names_for_user_ids(session, user_ids)`
**Shape:** mapper
**Persistence:** reads
**Visibility:** public (used by: `WorkOrderManager._resolve_completion_workers`)

**Purpose:** Build a display string for explicit worker user ids.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| session | `Session` | Real DB session |
| user_ids | `Sequence[int]` | Profile ids; not checked against any workspace |

**Returns:** `str` — the per-user labels joined per `join_worker_names` R1–R3.

**Rules:**
- **R1.** For each id, the label is the profile's `name` when non-empty.
- **R2.** If the profile's `name` is `""`, the label is the profile's `email` (when non-empty).
- **R3.** If no profile has that id (or both name and email are empty), the label is `"User #<id>"` (e.g. `"User #42"`).
- **R4.** Labels keep input order; empty `user_ids` → `""`.
- **R5.** [BUG-381] A repeated id produces one label, at the position of its first occurrence (`[7, 9, 7]` with #7 "Rahim", #9 "Karim" → `"Rahim, Karim"`). *(Today: repeated ids produce repeated labels — `"Rahim, Karim, Rahim"`.)*
- **R6.** No workspace scoping or membership check: any existing profile's name is returned regardless of workspace or membership status (the caller checks membership separately).
- **R7.** [BUG-382] A whitespace-only `name` is treated like an empty name: the label is the profile's `email`, trimmed by the join; if the `email` is also empty or whitespace-only, the label is `"User #<id>"` (P22 `"   "` / `"ws@x.com"` → `"ws@x.com"`; `[P7, P22, P9]` → `"Rahim, ws@x.com, Karim"`). Every id always produces a visible label (best-practice default, delegated by reviewer). *(Today: the whitespace name is kept as the label and then dropped by the join — `[P22]` → `""`, `[P7, P22, P9]` → `"Rahim, Karim"`; an empty name with a whitespace-only email is dropped the same way.)*

**Errors:** none

**Side effects:** none (read-only)

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 17 | `not text` (None / "") | `parse_worker_names` R1 |
| 17 | `not text.strip()` (whitespace-only) | `parse_worker_names` R1 |
| 19 | split on `[,;]+` | `parse_worker_names` R2 |
| 19 | `if part.strip()` true / false | `parse_worker_names` R3, R4 |
| 23 | `name and name.strip()` — None / "" / whitespace / real | `join_worker_names` R1, R2, R3 |
| 41 | `value or ""` — None vs string | `resolve_names_to_members` R4 |
| 53 | loop over names: empty / one / many | `resolve_names_to_members` R2, R6, R9 |
| 55 | `if not token: continue` | `resolve_names_to_members` R1 |
| 59 | loop over members: empty / many | `resolve_names_to_members` R3, R5 |
| 60 | name match / email match / neither | `resolve_names_to_members` R4 |
| 62 | `break` on first match (intended: all members scanned, distinct matching ids counted) | `resolve_names_to_members` R5 [BUG-380] |
| 63 | `hit is not None` true / false | `resolve_names_to_members` R6, R7, R7a |
| 66, 68–69 | one display / unmatched entry appended per typed name | `resolve_names_to_members` R7a, R9, R9a [BUG-381] |
| 64 | `hit.user_id not in matched_ids` | `resolve_names_to_members` R6 |
| 66 | `hit.name or hit.email or token` — name / email / typed name (typed-name branch unreachable) | `resolve_names_to_members` R8 |
| 66 | whitespace-only `hit.name` is truthy → trimmed to `""` (intended: fall back to email) | `resolve_names_to_members` R8a [BUG-382] |
| 74 | join display names | `resolve_names_to_members` R9 |
| 82 | parse then resolve | `resolve_worker_text_to_members` R1, R2 |
| 86 (`workspace_member_dao.get_workspace_members` L38–43) | workspace filter; `status is not None` → status filter; no order/limit | `load_active_member_lookups` R1, R2, R3, R6 |
| 88 | loop over rows: empty / many | `load_active_member_lookups` R4, R6 |
| 89 (`BaseDAO.get`) | profile found / not found | `load_active_member_lookups` R4, R5 |
| 93–94 | `if profile else None` (else branch unreachable: FK) | `load_active_member_lookups` R5 |
| 102 | loop over user_ids: empty / many / repeated [BUG-381] | `display_names_for_user_ids` R4, R5 |
| 103 (`BaseDAO.get`) | profile found / not found | `display_names_for_user_ids` R3, R6 |
| 104 | `profile and profile.name` (whitespace-only name truthy) | `display_names_for_user_ids` R1, R7 [BUG-382] |
| 106 | `profile and profile.email` (whitespace-only email truthy) | `display_names_for_user_ids` R2, R7 [BUG-382] |
| 108 | else → `User #id` | `display_names_for_user_ids` R3 |
| 110 | join | `display_names_for_user_ids` R4, R7 |

## Gap log
- G1 (work_order_workers.cases.md gap 1) — Fact — the FK `workspace_members.user_id → profiles.id` is `ON DELETE CASCADE` and not deferrable, so `load_active_member_lookups` R5 is a defensive branch with no reachable setup. Added a note for the test designer (no case, line expected uncovered); Branch map row marked unreachable. Kept as a rule, not dead code (one defensive conditional expression, not a callable).
- G2 (work_order_workers.cases.md gap 2) — Contradiction — confirmed the typed-name fallback in `resolve_names_to_members` R8 is unreachable (R4 prevents the match). R8 now says so; note for the test designer added; Branch map updated.
- G3 (work_order_workers.cases.md gap 3) — Intent, decided by best practice (delegated by reviewer) — a whitespace-only member name is treated like an empty name and falls back to the email. Logged as BUG-382 (Q3, resolved, no pending question). New rule `resolve_names_to_members` R8a. For consistency the same fix applies to `display_names_for_user_ids` R7 (previously an untagged description of today's behaviour; now tagged BUG-382, falling back to `User #<id>` when the email is blank too). Case WOW-D-08 must be regenerated.
