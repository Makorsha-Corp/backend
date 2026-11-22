# Spec — `app/managers/machine_maintenance_log_manager.py`

> **Status:** APPROVED (2026-10-31; nothing open)
> **Source commit:** e48a092

> **Review round 2026-10-31.** **The owner's own answers (2026-10-31, relayed by the main session):** Q1, bug, `ge=0` on Create and Update only; Q2, bug, a third decimal is refused with 400 (BUG-708) and the activity entry records the stored form; Q6, maintenance logging is live and gets full depth, and the missing add and edit UI is a frontend bug note. **Delegated:** P1–P7, Q3, Q4, Q5 accepted as suggested, decided by Claude under the reviewer's delegation (2026-10-31). None of these is the owner's own answer. The house-rule lines stand. New bugs: BUG-1150 … BUG-1159. **Two IDs cover two questions each, to stay inside the range given:** BUG-1156 (P5, P6, one field) and BUG-1157 (P7, Q2, one field).

> **Routed here and handled:** machine maintenance log DAO FU-1 (a) BUG-1150; (b) P1; (c) P4, P5, P6; (d) Q1 **OWNER**, P7; (e) BUG-1151; (f) P2; (g) Q2 **OWNER**; (h) P3, Q3, Q4; (i) BUG-1101 rules below; (j) Q5. DAO FU-4: Q6. DAO FU-5: FU-3 here.
>
> **Standing decisions applied here (not asked again):**
> 1. A maintenance log is history (DAO Q1): logs of a soft-deleted machine, or of a machine in a soft-deleted factory, stay listed and readable. The log's own soft delete still hides it.
> 2. A missing `ORDER BY` is a bug (BUG-1100, at the DAO).
> 3. HR-15: money rounds half up. HR-16: cross-workspace rows are refused and leak nothing (BUG-1101, at the DAO).
>
> **Verified by running** (scripts `mmlm_h.py`, `p1.py` … `p5.py` in `C:\Users\User\AppData\Local\Temp\claude\E--Projects-Makorsh-Corp-backend\5dcda696-13dd-4b73-983c-11d3c05a8ed9\scratchpad\mmlm\`, each transaction rolled back against `marker_test`; no row left behind, checked): every "Today:" note below, and through the manager: create with own / other / unknown / `0` / negative machine, deleted, inactive, in a deleted and an inactive factory; `summary` empty, blank, padded, 100 000 characters; `performed_by` empty, blank, padded, 255, 256; `cost` `-5`, `0`, `0.125`, `5.001`, `-1.005`, the column's limit and past it, `1e20`; dates 1900 and 2099; unknown user on all three writes, with its constraint; savepoint roll-back on all three; every event field; the four `metadata.status` values; `model_construct`. Update with each field alone, all five, `{}`, all `null`, same values by the same and another user, `updated_at` in each; `cost` as `5.001`, `5`, `5.0`, `7`, `7.1`, `0.125`, `1E+3`, `1E-7`. Every path of `list_logs`, with `0`, `-1`, unknown, another workspace, type as member, string, `""`, `BOGUS`, paging, 101 rows, negative values. Deleted, inactive and BUG-1101 rows through get, update, list, delete. **Over HTTP** (`TestClient`, overridden dependencies, rolled back): 201 for blank `summary` and `-5`; 500 for `1e20` on `POST` and `PUT`, and for 256 characters; 400 for a schema error (BUG-461), for `limit=0`, `limit=1001`, `skip=-1`; 200 with nothing changed for `{}` and `null`; `machine_id=0` returns the whole workspace, with `maintenance_type` the matching rows; second delete 400; `GET` after delete 200. `git log` in `frontend/` for Q6. The limits of the intended `cost` field were tried on a throwaway schema (`p6.py`), which is where `5.000` and `-0` below come from. **Not run:** two concurrent transactions; the intended behavior of any other bug rule; production data, so how many logs exist is unknown.

## Review
> Reviewer: answer each question on its **Answer:** line with one of
> `intended` · `bug` · `bug — <what it should do instead>` · `remove` (unreachable
> code only) · or a question back.
> Then run the describer in `apply-review` mode.

### Quick list — all answered
| # | What the code does today, in plain words | Answer | Decided by |
|---|---|---|---|
| Q1 | A negative `cost` is stored | bug — `ge=0` on Create and Update only (BUG-1158) | **owner** |
| Q2 | The activity entry records `cost` as typed, not as stored | bug — a third decimal is refused, the entry shows the stored form (BUG-1157) | **owner** |
| Q6 | Nothing in the application creates a log any more | the feature is live, full depth; the missing UI is a frontend bug (BUG-1159) | **owner** |
| Q3 | A log of a deleted machine can be edited | intended | Claude, delegated |
| Q4 | A log of a deleted machine can be removed | intended | Claude, delegated |
| Q5 | `maintenance_date` has no bound, so a future date is stored | intended | Claude, delegated |
| P1 | `machine_id=0` lists the whole workspace | bug (BUG-1152) | Claude, delegated |
| P2 | `cost` and `performed_by` cannot be cleared | bug (BUG-1153) | Claude, delegated |
| P3 | A log can be added to a machine of a deleted factory | bug (BUG-1154) | Claude, delegated |
| P4 | A blank `summary` is stored | bug (BUG-1155) | Claude, delegated |
| P5 | `performed_by` is stored untrimmed, and blank counts as a value | bug (BUG-1156) | Claude, delegated |
| P6 | A `performed_by` of 256 characters crashes | bug (BUG-1156) | Claude, delegated |
| P7 | A `cost` beyond the column crashes | bug (BUG-1157) | Claude, delegated |

### House-rule violations — applied automatically

- **HR-4** `get_log` R3, R3a — a soft-deleted log is returned with 200 although every list hides it. Intended: 404 by default; a new `include_deleted=True` returns it, reachable from the API. A log of a deleted machine is **not** hidden: standing decision 1.
**Answer:** bug — per HR-4 (house rule)
**Resolution:** BUG-1150 (pattern `get-returns-soft-deleted`; DAO P1, BUG-955 precedent). The service and `GET /machine-maintenance-logs/{id}/` must pass it (FU-1).
- **HR-9** `update_log` R8a — `updated_by` is written on every call that finds the log, so `{}`, all `null` or the same values by another user stamp `updated_by` and `updated_at`, with no activity entry. Intended: written only when a field's stored value changes. A `cost` that rounds to the stored value would change nothing; Q2 refuses it before it gets this far.
**Answer:** bug — per HR-9 (house rule)
**Resolution:** BUG-1151 (pattern `audit-stamp-on-noop`; BUG-959 precedent).

Existing bugs written as rules here, no new ID: **BUG-1100** `list_logs` R10; **BUG-1101** `update_log` R3, `get_log` R6, `list_logs` R12, `delete_log` R3; **BUG-1102** `delete_log` R6a. The fixes are at the DAO; each gets one pass-through case.

Checked and **not** violated: **HR-1** — `summary` is required text, not a name; the void-reason precedent decides it (P4). **HR-2, HR-3** — nothing is unique, `performed_by` is not grouped or filtered. **HR-5** — every filter is in the DAO's query. **HR-6** — BUG-1100 only. **HR-7** — `GET /machine-maintenance-logs/` enforces `1 <= limit <= 1000`, `skip >= 0` (verified). **HR-8** — no `LIKE`. **HR-10** — `delete_log` and `update_log` are a plain soft delete and a plain edit, as `delete_machine` (machine manager spec): no lock. Two deletes at once can write two `maintenance_removed` entries; no money or stock moves and nothing reads `cost`. **HR-11 … HR-14** — no external system, no batch. **HR-15** — nothing rounds in Python; the `Numeric(15, 2)` column rounds half up (verified: `0.125` → `0.13`, `-1.005` → `-1.01`). **HR-16** on the write path — `create_log` refuses another workspace's machine exactly as a missing one, and `MachineMaintenanceLogUpdate` has no `machine_id`.

`summary` has no length limit (DAO FU-1 (c)): not a question. The column is `Text`, 100 000 characters are stored and copied into the activity entry with no error, and `machines.note` is the same (BUG-967 leaves it as typed).

`metadata.status` on `maintenance_logged` holds the **maintenance type** (`REPAIR`), not a machine status (RUNNING, IDLE, OFF, MAINTENANCE). Checked and harmless: `get_latest_status`, `get_latest_status_map` read only `status_updated` events, and the frontend reads `metadata.status` only for those. Stated as `create_log` R15.

### Precedent matches — all accepted (decided by Claude under the reviewer's delegation (2026-10-31))

### P1. `machine_id=0` lists the whole workspace — 🐞 BUG-1152
**Background:** `GET /machine-maintenance-logs/` takes an optional `machine_id`. The code tests it for truthiness, so `0` means "no filter". Same root cause as BUG-885, BUG-1074.
**What happens today:** `machine_id=0` returns every log of the workspace, and with a `maintenance_type` every log of that type (verified over HTTP). The DAO itself returns `[]` for `0`.
**Example:** A client with an unset machine id sends `0` and believes it sees one machine's history; it sees all of them.
**Rules affected:** `list_logs` R5
**Answer:** bug — per BUG-1074 precedent: only `None` means "no filter"; `machine_id=0` returns `[]`, with or without a type
**Resolution:** 🐞 BUG-1152 (pattern `falsy-zero-treated-as-missing`) — decided by Claude under the reviewer's delegation (2026-10-31): the suggested precedent answer is accepted. Rules: `list_logs` R5.

### P2. `cost` and `performed_by` cannot be cleared — 🐞 BUG-1153
**Background:** `update_log` drops every field sent as `null`. Same root cause as BUG-962, BUG-1075.
**What happens today:** `PUT` with `cost: null` answers 200 and the old value stays, and `updated_by` is stamped (verified over HTTP). `summary`, `maintenance_type`, `maintenance_date: null` do the same, silently.
**Example:** A cost of 4 000 was entered on the wrong log. A client sends `cost: null`: 200, and it still says 4 000.
**Rules affected:** `update_log` R7
**Answer:** bug — per BUG-1075 precedent: explicit `null` clears `cost` and `performed_by`, and `maintenance_updated` records `to_value: null`; `null` for `maintenance_type`, `maintenance_date` or `summary`, whose columns are NOT NULL, is rejected by `MachineMaintenanceLogUpdate`; omitted fields stay unchanged
**Resolution:** 🐞 BUG-1153 (pattern `exclude-none-blocks-clear`) — decided by Claude under the reviewer's delegation (2026-10-31): the suggested precedent answer is accepted. Rules: `update_log` R7, R7a, R8.

### P3. A log can be added to a machine of a deleted factory — 🐞 BUG-1154
**Background:** `create_log` refuses a soft-deleted machine, but reads only the machine's own flag. A machine of a soft-deleted factory is hidden everywhere (BUG-890, BUG-979). Same root cause as BUG-1076. Standing decision 1 is about logs already written, not about new ones.
**What happens today:** 201, with an activity entry (verified), on a machine nobody can see.
**Example:** "Old Plant" was deleted. A stale form logs a repair on its "Press 4": 201.
**Rules affected:** `create_log` R3
**Answer:** bug — per BUG-1076 precedent: refused like a deleted machine, 400 `Cannot create maintenance log for a deleted machine`, right after the machine's own flag, nothing written; an inactive-but-live machine or factory is not refused
**Resolution:** 🐞 BUG-1154 (pattern `write-to-soft-deleted-related-row`) — decided by Claude under the reviewer's delegation (2026-10-31): the suggested precedent answer is accepted. Rules: `create_log` R3.

### P4. A blank `summary` is stored — 🐞 BUG-1155
**Background:** `summary` is the required text of a log: what was done. It is free text, not a name, so HR-1 does not bind it by its wording, but void reasons were ruled the same way (BUG-605, BUG-626). The removed web form (Q6) required it and trimmed it.
**What happens today:** `""` and `"   "` are stored on create and update, and the activity entry reads `Maintenance logged: ` (verified over HTTP); `"  pad  "` keeps its spaces.
**Example:** A log with an empty summary shows in the machine's history as "Maintenance logged:" and nothing else.
**Rules affected:** `create_log` R8, `update_log` R13
**Answer:** bug — per BUG-605 precedent: `summary` is stripped by `MachineMaintenanceLogCreate` / `Update`; empty or whitespace-only is rejected, nothing written; stored trimmed, inner whitespace kept
**Resolution:** 🐞 BUG-1155 (pattern `blank-name-accepted`) — decided by Claude under the reviewer's delegation (2026-10-31): the suggested precedent answer is accepted. Rules: `create_log` R8, `update_log` R13.

### P5. `performed_by` is stored untrimmed, and blank counts as a value — 🐞 BUG-1156
**Background:** `performed_by` is an optional free-text name of who did the work, not a link to a profile. Same root cause as BUG-967.
**What happens today:** `"  Rahim  "` keeps its spaces, and `""` and `"   "` are stored as values (verified).
**Example:** A log shows "Performed by" as empty, yet the row holds three spaces, and the change log says `None → "  "`.
**Rules affected:** `create_log` R8, `update_log` R13
**Answer:** bug — per BUG-967 precedent: stored trimmed; empty or whitespace-only stored as `NULL`, on create and update
**Resolution:** 🐞 BUG-1156 (pattern `blank-optional-text-stored`; shared with P6) — decided by Claude under the reviewer's delegation (2026-10-31): the suggested precedent answer is accepted. Rules: `create_log` R8a, `update_log` R13a.

### P6. A `performed_by` of 256 characters crashes — 🐞 BUG-1156
**Background:** The column is `String(255)`; the schemas set no limit. Same root cause as BUG-972.
**What happens today:** `DataError` (`StringDataRightTruncation`, pgcode `22001`) at the flush: a 500 on `POST` (verified over HTTP) and `PUT`. 255 characters are stored.
**Example:** A long pasted name gives "An unexpected error occurred" instead of a validation message.
**Rules affected:** `create_log` R9, `update_log` R14
**Answer:** bug — per BUG-972 precedent: `max_length=255` on `performed_by` of `MachineMaintenanceLogCreate` / `Update`, on the trimmed value, rejected by the schema, nothing written
**Resolution:** 🐞 BUG-1156, shared with P5: one field, one schema line. The other uses of this root cause carry the pattern `unchecked-column-length`, and the register row names it. decided by Claude under the reviewer's delegation (2026-10-31): the suggested precedent answer is accepted. Rules: `create_log` R9a, `update_log` R14.

### P7. A `cost` beyond the column crashes — 🐞 BUG-1157
**Background:** `cost` is `Numeric(15, 2)`: 13 digits before the point. The schemas set no limit, and `DataError` has no handler. Same root cause as BUG-708. This question is the integer digits only; a third decimal is Q2.
**What happens today:** `10000000000000` and `1e20` raise `DataError` (`NumericValueOutOfRange`, pgcode `22003`) at the flush: a 500 on `POST` and `PUT` (verified over HTTP). `9999999999999.99` is stored.
**Example:** A typing slip of fourteen digits gives "An unexpected error occurred".
**Rules affected:** `create_log` R10, `update_log` R14
**Answer:** bug — per BUG-708 precedent: `cost` with more than 13 integer digits is rejected by `MachineMaintenanceLogCreate` / `Update`, nothing written; `9999999999999.99` is accepted
**Resolution:** 🐞 BUG-1157 (pattern `unbounded-decimal-input`; shared with Q2, as BUG-708 holds digits and decimals in one) — decided by Claude under the reviewer's delegation (2026-10-31): the suggested precedent answer is accepted. Rules: `create_log` R10a, `update_log` R14.

### New questions — answered

### Q1. A negative `cost` is stored — 🐞 BUG-1158 (owner's answer)
**Background:** `cost` is the optional money figure on a log. The input schemas have no minimum and the table no check. For stock and prices you ruled negatives out at the input schemas (BUG-711, BUG-1079). The facts on whether a negative could mean a credit or a refund, all checked in the code:
- The four types are `PREVENTIVE`, `REPAIR`, `EMERGENCY`, `INSPECTION`. None is a credit, and no field says what a negative means.
- A log links to no invoice, purchase order, account or payment, so a refund could not be traced to what it refunds.
- Nothing uses `cost`: no code in `app/` and no frontend page adds it up or passes it on. It appears only on the log itself and in a change entry, so a negative moves no figure today.
- The removed web form (`AddMachineMaintenanceLogDialog.tsx`) had `min="0" step="0.01"`, so the product never offered a negative. The API has allowed one all along, and the form has been gone since 2026-07-07 (Q6).

**What happens today:** `cost: -5` answers 201 and stores `-5.00`; `PUT` does the same, and the entry says `5.00 → -5` (verified over HTTP). `0` is stored. `-1.005` is stored as `-1.01`.
**Example:** A supplier refunds 500 taka for a bearing. Someone logs `-500`. It is stored as `-500.00`, with no sign of what it refunds, and any future total of maintenance cost would silently net it off the machine's real spending.
**Rules affected:** `create_log` R11, `update_log` R13
**Suggested answer:** `bug — ge=0 on cost of MachineMaintenanceLogCreate and MachineMaintenanceLogUpdate, as BUG-1079, not on MachineMaintenanceLogResponse; 0 and null accepted; rejected by the schema, nothing written.` Nothing in the code gives a negative a meaning, and the only form that ever existed refused it; a refund belongs where it can be traced. Rows already negative stay readable, because the response schema stays open, and can be edited to `0` or more. Alternative: `intended — a negative cost is a credit or refund`; then the rule to write is that any future total nets them, and a way to mark them should follow.
**Answer:** bug — `ge=0` on Create and Update only. **The owner's own answer (2026-10-31).**
**Resolution:** 🐞 BUG-1158 (pattern `unvalidated-numeric-range`; per BUG-1079). `MachineMaintenanceLogResponse` stays open, so a row already negative stays readable and can be edited to `0` or more. `0` and `null` are accepted; `-0` passes `ge=0` and is stored as `0.00`. Rules: `create_log` R11, R11a, `update_log` R13b.

### Q2. The activity entry records `cost` as typed, not as stored — 🐞 BUG-1157 (owner's answer)
**Background:** The column keeps two decimals and rounds half up (HR-15). The update compares the typed value with the stored one *before* the write, and the entry is built from the typed value. The same comparison serves every field; `cost` is the only one that changes on its way into the column. On a third decimal your earlier rulings were "refuse it" (BUG-021, BUG-604, BUG-708), all before HR-15, which says how money rounds, not whether a third decimal is accepted. The removed web form had `step="0.01"`.
**What happens today (verified):**
| Log at | Sent | Stored | Entry says | `updated_by` |
|---|---|---|---|---|
| `5.00` | `5.001` | `5.00` | `5.00 → 5.001` | stamped, though nothing changed |
| `7.10` | `0.125` | `0.13` | `7.10 → 0.125` | stamped |
| `1000.00` | `1E-7` | `0.00` | `1000.00 → 1E-7` | stamped |
| `0.13` | `"1e3"` | `1000.00` | `0.13 → 1E+3` | stamped |
| `5.00` | `7` | `7.00` | `5.00 → 7` | stamped; value right, form differs |
| `5.00` | `5`, `5.0`, `5.00` | `5.00` | no entry | see HR-9 |

Sending `5.001` again in a later request writes the same false entry again, each time. `POST` has no such entry, as `maintenance_logged` does not carry `cost`, but it rounds silently: `5.001` answers 201 with `5.00`. A cost just under the limit is the one rounding case that can still crash after P7: `9999999999999.995` rounds past the column, a 500.
**Example:** A log stands at 5.00. Someone sends 5.001. The panel now says the cost changed from 5.00 to 5.001, a figure no record holds, and the log itself still says 5.00.
**Rules affected:** `update_log` R12a, `create_log` R12
**Suggested answer:** `bug — per BUG-708: cost with more than 2 decimal places is rejected by MachineMaintenanceLogCreate / Update, nothing written; and the entry records the stored form, always two decimals (5.00 → 7.00).` Refusing is what you ruled each time this came up, and it ends all the rows above at once, the `.995` crash included (tried on a test schema: `max_digits=15, decimal_places=2` refuses `5.001`, `9999999999999.995` and `1e20`, and accepts `5.00`, `5`, `0.1`). The form part is needed either way: `7` stays a valid input. Alternatives: (b) `accept a third decimal, round half up before the comparison`, so `5.001` on `5.00` is no change and the entry shows the rounded value; this keeps the API lenient and departs from BUG-708. (c) `intended`, leaving the entry as typed: the log itself stays right and the entry is only noise. This is the least work, and the entry can then disagree with the record it describes.
**Answer:** bug — a third decimal is refused with 400 (BUG-708), and the activity entry records the stored form. **The owner's own answer (2026-10-31).**
**Resolution:** 🐞 BUG-1157, shared with P7. `max_digits=15, decimal_places=2` on `cost` of `MachineMaintenanceLogCreate` / `Update`; the entry's `to_value` is the two-decimal form. 400 is what every schema refusal answers today; BUG-461, still open, would make all of them 422, this one included, so the rule is written against the schema and the 400 is integration-only. Pydantic ignores trailing zeros: `5.000` is accepted as `5.00`. With the refusal in place the `9999999999999.995` crash goes too. Rules: `create_log` R12, `update_log` R12a, R14.

### Q3. A log of a deleted machine can be edited — ✅ intended
**Background:** `create_log` refuses a soft-deleted machine; `update_log` does not look at the machine. For stock on a deleted machine you ruled "refuse" (BUG-1083), because a change made while a thing is hidden means a restore does not bring back what was hidden. A log is different: it stays visible (standing decision 1), so nothing is hidden when it is edited, and an edit moves no stock. "Restore machine" is not built, so a refusal has no way out.
**What happens today:** `PUT` answers 200, for a soft-deleted machine and for a machine of a soft-deleted factory, and writes `maintenance_updated` to that machine's activity log (verified).
**Example:** "Press 4" was deleted in June. In July someone sees its March repair is 400 taka off and corrects it: 200, and the correction is recorded.
**Rules affected:** `update_log` R5
**Suggested answer:** `intended — a log is history, and correcting it with a recorded change keeps it right; it is still listed, so a refusal would only leave a known mistake in place.` Alternative: `bug — 400 Cannot update a maintenance log of a deleted machine, as BUG-1083`, if history should freeze with the machine.
**Answer:** intended — a log is history, and correcting it with a recorded change keeps it right; it is still listed, so a refusal would only leave a known mistake in place
**Resolution:** decided by Claude under the reviewer's delegation (2026-10-31): rule unchanged. Rules: `update_log` R5 ✅.

### Q4. A log of a deleted machine can be removed — ✅ intended
**Background:** As Q3. `delete_log` does not look at the machine. For stock you ruled "refuse" (BUG-1084), because removing it is a hard delete that cannot come back with the machine. Removing a log is a soft delete: the row and its `maintenance_logged` entry stay, and `maintenance_removed` records who did it. The history ruling stops a *parent's* delete from hiding entries; it does not stop a user removing one entry, which works on a live machine too. No list shows a deleted log and no restore exists (DAO FU-2), so in practice a removal is permanent.
**What happens today:** 200, with `maintenance_removed` on that machine's activity log, for a soft-deleted machine and a machine of a soft-deleted factory (verified).
**Example:** A duplicate log of deleted "Press 4" is removed: it leaves `GET /machine-maintenance-logs/`, and the row stays in the table.
**Rules affected:** `delete_log` R5
**Suggested answer:** `intended — the same as on a live machine: soft, recorded, and the row stays`. This is the closer call of the two. Alternative: `bug — 400 Cannot remove a maintenance log of a deleted machine, as BUG-1084`, if a deleted machine's history should be frozen, which leaves Q3 needing the same answer.
**Answer:** intended — the same as on a live machine: soft, recorded, and the row stays
**Resolution:** decided by Claude under the reviewer's delegation (2026-10-31): rule unchanged. Rules: `delete_log` R5 ✅.

### Q5. `maintenance_date` has no bound — ✅ intended
**Background:** The model says a log records "work done", so a future date looks wrong. But nothing computes on the date except the sort order, planning lives on work orders (`planned_date`), and a log has no status. The API has no time zone, so "today" would be a UTC day: at 01:00 on 5 March in Dhaka it is still 4 March UTC, so a job dated today would be refused. The removed form defaulted to today and set no bound. No schema or manager in the application refuses a future date.
**What happens today:** `2099-01-01` and `1900-01-01` are stored on create and update (verified).
**Example:** A typing slip stores a job as 2062. It sorts at the top of the machine's history until someone edits it.
**Rules affected:** `create_log` R13, `update_log` R13
**Suggested answer:** `intended — no bound.` The harm is a sort position, the fix is one edit, and a check would need a time-zone decision first (FU-3 of the DAO spec is open on that). Alternative: `bug — a date after today in UTC is refused, allowing one day's grace`.
**Answer:** intended — no bound
**Resolution:** decided by Claude under the reviewer's delegation (2026-10-31): rules unchanged. Rules: `create_log` R13 ✅, `update_log` R13c ✅.

### Q6. Nothing in the application creates a log any more — 🐞 BUG-1159 (owner's answer)
**Background:** All five endpoints are live behind normal login, and nothing else in the backend writes a log: no work order, script or job. In the frontend only the delete mutation is called, from a machine's activity list. `frontend` history: the update hook was only ever used on `ApiTestPage.tsx`, removed in `b999396` (2026-06-21), so no product page ever edited a log; `623a01f` (2026-07-07, "single guided Maintenance flow") deleted `AddMachineMaintenanceLogDialog.tsx` and the "Add Maintenance Log" button from the machine dialog. So this looks **deliberately replaced**, not unfinished: maintenance is now a machine's status and work orders (that commit's wizard file is no longer in `src/` either), and the list, get, create and update hooks stayed behind as unused exports.
**What happens today:** A new log can come only from a direct API call. The delete button appears only on a `maintenance_logged` activity entry, so it reaches rows written before 2026-07-07 or by such a call.
**Example:** A user opens a machine's activity list. An entry from May offers "Delete maintenance log". There is no way to add one, see the list of logs, or edit one.
**Rules affected:** none. The rules hold whatever is decided.
**Suggested answer:** `keep — specify and test as written, with the lighter case target for simple modules; decide removal separately.` The endpoints are public API and the rows are history, so nothing here is `remove`-able as dead code. This query tells whether the rows exist at all: `SELECT count(*), max(created_at) FROM machine_maintenance_logs WHERE NOT is_deleted`. If it says none, removing the feature is a one-line decision, and Q1 and Q2 lose their weight. Alternative: `remove the endpoints, service and manager`; that is a product decision, the delete button then goes too, and old `maintenance_logged` entries stay as text.
**Answer:** maintenance logging is live and gets full depth, so the case designer does not use the lighter target; the missing add and edit UI is a frontend bug note, since the add dialog was removed on 2026-07-07 and the feature is live. **The owner's own answer (2026-10-31).**
**Resolution:** 🐞 BUG-1159 (pattern `live-feature-without-ui`), frontend note: no rule here and no test case. This answer overrides the reading in Background that the feature was replaced, and the suggested lighter target. **Every rule of this spec gets full-depth cases.** Nothing goes on the dead-code list.

## Follow-ups for other reviews
> Nothing below is a rule of this manager. Whoever describes the named module must read this list first.

| # | Where it must be looked at | What | Came from |
|---|---|---|---|
| FU-1 | **Service and endpoint** (`app/services/machine_maintenance_log_service.py`, `app/api/v1/endpoints/machine_maintenance_logs.py`) | (a) BUG-1150: `get_log` and `GET /machine-maintenance-logs/{id}/` must pass `include_deleted`. (b) `DataError` has no handler: a 500 (BUG-1156, BUG-1157 remove the two paths here). `IntegrityError` has one, a generic 409; an unknown user is not reachable over HTTP. (c) Schema errors are 400 today (BUG-461). (d) `DELETE` answers 200 with the row, where machine and machine item deletes answer 204. Harmless: the frontend types it `void`. | HR-4 |
| FU-2 | **Schemas** (`app/schemas/machine_maintenance_log.py`) | Every schema-side fix goes on `MachineMaintenanceLogCreate` and `Update`, not on `MachineMaintenanceLogResponse`: rows already blank, negative or padded must stay readable. P2 needs `null` told apart from omitted, as BUG-1075: `model_dump(exclude_unset=True)` keeps `cost: None`, verified. | P2, Q1, Q2 |
| FU-3 | **Frontend** (`frontend/src/components/newcomponents/customui/MachineActivityEventLogRow.tsx`, `MachineDetailBody.tsx`, `frontend/src/types/machineMaintenanceLog.ts`) | (a) DAO FU-5: the delete button stays on an entry whose log is already deleted; a second press gets the 400 as a toast. (b) The activity filter's "Maintenance" option sends only `maintenance_logged`, so `maintenance_updated` and `maintenance_removed` are not under it. (c) The confirm says "Delete this event?", though it deletes the log and the event stays. (d) `UpdateMachineMaintenanceLogRequest` has `cost?: number`: it cannot send `null` even after BUG-1153. (e) BUG-1159: the add and edit forms, which should carry the schema's limits (`cost` `min="0"`, `step="0.01"`; `summary` required). | DAO FU-5, Q6 |
| FU-4 | **Machine activity manager** (`app/managers/machine_activity_manager.py`, not yet specified) | `collect_field_changes` compares and records values as given. Harmless for integers and strings; `cost` is the only field it sees that a column rounds (Q2). BUG-1157's stored-form formatting can live here or in this manager. `log_event` does not look at the machine's state (Q3, Q4), and BUG-1091 stands for its workspace. | Q2 |

## Overview
`MachineMaintenanceLogManager` is the business layer for the record of maintenance work done on machines: it creates, edits, reads, lists and soft-deletes logs, and writes each change into the machine's activity log. It is called only by `MachineMaintenanceLogService` behind `/machine-maintenance-logs/`, and today the web application uses only its delete; the feature is live and the missing add and edit UI is BUG-1159 (Q6). It is meant to protect workspace isolation and to keep new logs off deleted machines. It validates no values itself (the limits belong on the input schemas, FU-2) and never commits; DAOs and the activity manager flush. Every refusal is an `HTTPException`.

**Callables:** 5 specified · 2 not specified
**Externals to mock:** none in this module. BUG-1102's pass-through case patches the DAO's clock (Notes). `MachineActivityEvent.created_at` is a Python column default bound at import: assert set / not set.
**Integration-only behavior:** the HTTP status of the refusals; schema validation at the API (400 today, BUG-461; 422 intended); `skip >= 0`, `1 <= limit <= 1000` and the enum check on `GET`; the 500 for `DataError`; the service's commit, rollback and `db.refresh`. Two real concurrent transactions.

**Facts for the test designer**
- Import: `from app.managers.machine_maintenance_log_manager import MachineMaintenanceLogManager, MAINTENANCE_LOG_FIELDS, machine_maintenance_log_manager`. Parameters are positional-or-keyword; the service passes `session=`, `log_data=`, `log_id=`, `workspace_id=`, `user_id=` by keyword, and calls `get_log` positionally.
- Schemas: `from app.schemas.machine_maintenance_log import MachineMaintenanceLogCreate, MachineMaintenanceLogUpdate`. Enum: `app.models.enums.MaintenanceTypeEnum`.
- `HTTPException` is `fastapi.HTTPException`: assert `.status_code` and `.detail` (a plain string). Database errors are `sqlalchemy.exc.IntegrityError` / `DataError` with `.orig` a `psycopg2` error class. Schema errors are `pydantic.ValidationError`.
- Table, columns, foreign keys, schemas: maintenance log DAO spec, **Model facts**. Collaborator rules cited, not repeated: same spec. Machine soft delete: `is_deleted = True`, `is_active = False`. Factory: `is_deleted = True`, `is_active` unchanged.
- **Two different "performed by":** `performed_by` on the log is free text, who did the work; `performed_by` on the activity entry is the acting user's profile id. `created_by`, `updated_by`, `deleted_by` are profile ids.
- `machine_activity_events`: `workspace_id`, `machine_id`, `event_type`, `description`, `metadata_json` (column `metadata`, JSON), `performed_by`, `created_at`. `log_event` adds one row and flushes.
- `MAINTENANCE_LOG_FIELDS`, in order: `maintenance_type` "Maintenance type", `maintenance_date` "Maintenance date", `summary` "Summary", `cost` "Cost", `performed_by` "Performed by". A `changes` entry is `{"field", "label", "from_value", "to_value"}`.

**Notes for the test designer**
- Workspaces and profiles from `tests/unit/factories.py`. Build `Factory`, `Machine`, `MachineMaintenanceLog` directly, as the DAO spec's Notes. `autoflush=False`: flush before calling the manager.
- **`cost` on a row built directly:** `db.refresh(row)` after building, or the instance keeps the value as given and `from_value` is not the stored form (`5.00`).
- **A value set twice in one session:** the instance keeps the typed `cost` until a refresh, so a second identical `update_log` in one test compares with the typed value and writes no entry (verified); between real requests it does. `db.refresh` between calls for that case.
- **Reading rows:** assert activity rows with a fresh `SELECT` filtered by `machine_id`, ordered by `id`. Compare `metadata_json` as a whole dict, order of `changes` included. Compare `Decimal` by value.
- **`updated_at` (HR-9):** build the log with `updated_by=None`; `updated_at` is `None` until an UPDATE is issued. Today `{}` stamps both (verified) → strict xfail. Keep "no activity entry" in a separate plain pass case (R8).
- **Hidden parents:** as DAO Notes. Soft-deleted machine = `is_deleted=True, is_active=False`, soft-deleted factory = `is_deleted=True` with a live machine in it; soft-delete the parent after building the log, because `create_log` refuses a deleted machine.
- **BUG-1101 rows:** `workspace_id` = A, `machine_id` = a machine of B, built directly. `create_log` cannot make one. Today get, update, delete and the lists reach it → strict xfail. Assert with `exc.value.status_code`, and that B's machine gets no new activity row.
- **BUG-1100:** order by date alone holds today and is a plain pass case. Ties are not deterministic: **non-strict** xfail, as DAO Notes. Every case not about order compares **sets** of ids.
- **BUG-1102 pass-through:** `patch("app.dao.machine_maintenance_log.utcnow", create=True, return_value=NOW)`, `NOW` a fixed naive datetime far from today → strict xfail. Keep the other `soft_delete` columns in a plain pass case.
- **BUG-1150:** today `get_log` has no `include_deleted`, so a call with it raises `TypeError` → strict xfail. Strict too: the 404 of R3.
- **The `str()` fallback of `create_log` R15:** only `MachineMaintenanceLogCreate.model_construct(...)` with a plain string reaches it: Pydantic warns while dumping, so filter that warning in the case. Every normal input is a member.
- **Refusals after a flush:** none: all refusals come before the first write. **Database errors** abort the transaction: `with db.begin_nested():` inside `pytest.raises(...)`, and `db.refresh(row)` afterwards. **Not committed:** `sp = db.begin_nested()`, call, `sp.rollback()`, re-read.
- **Depth (Q6, owner):** the feature is live: full depth, not the lighter case target for simple modules.
- **Schema rules (BUG-1153, BUG-1155, BUG-1156, BUG-1157, BUG-1158):** build the schema inside `pytest.raises(pydantic.ValidationError)`, on both `MachineMaintenanceLogCreate` and `MachineMaintenanceLogUpdate`. Today the schema accepts these values, so the raises fails deterministically. Assert `MachineMaintenanceLogResponse` still reads a row with a negative `cost` (plain pass case). A refusal is `ValidationError` here, not a status code: the 400 is integration-only.
- **BUG-1157 entry form:** build the log at `5.00` and refresh; send `7`; intended `"to_value": "7.00"`. Today `"7"`.
- **BUG-1154:** build the log's machine live in a factory with `is_deleted=True`; assert the 400 and no new row.
- Strict xfail, outcome deterministic today: BUG-1150, BUG-1151, BUG-1152, BUG-1153, BUG-1154, BUG-1155, BUG-1156, BUG-1157, BUG-1158, BUG-1101, BUG-1102. Non-strict: BUG-1100. BUG-1159 is frontend: no case here.
- No legacy test calls this manager.

## Not specified
- `MachineMaintenanceLogManager.__init__` — stores the model and the DAOs, no logic
- `machine_maintenance_log_manager` — module-level singleton, no logic

The checklist (`docs/testing/unit-test-checklist-by-layer.md`) marks nothing of this file as possibly unused. `BaseManager` adds only `self.model`.

---

## `MachineMaintenanceLogManager.create_log(session, log_data, workspace_id, user_id)`
**Shape:** create
**Persistence:** writes
**Visibility:** public (used by: `MachineMaintenanceLogService.create_log` ← `POST /machine-maintenance-logs/`; no frontend caller, Q6)

**Purpose:** Record maintenance work on a machine of the workspace, and say so in the machine's activity log.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `session` | `Session` | open session; not committed here |
| `log_data` | `MachineMaintenanceLogCreate` | `machine_id`, `maintenance_type`, `maintenance_date`, `summary` required; `cost`, `performed_by` default `None`. `summary` stripped, not blank [BUG-1155]. `performed_by` stripped, blank becomes `None`, at most 255 [BUG-1156]. `cost` at least 0 [BUG-1158], at most 2 decimals and 13 integer digits [BUG-1157]. `NaN`, `Infinity`, a wrong type name and unknown keys never get here: the schema rejects the first three and drops the last |
| `workspace_id` | int | caller's workspace; not taken from the body |
| `user_id` | int | `created_by` on the log, `performed_by` on the entry |

**Returns:** the new `MachineMaintenanceLog`, flushed, not committed.

**Rules:**
- **R1.** A machine that is missing, of another workspace, `0` or negative → 404 `Machine with ID <machine_id> not found`, where `<machine_id>` is the id sent, so another workspace's machine cannot be told from a missing one (HR-16); nothing written.
- **R2.** A soft-deleted machine → 400 `Cannot create maintenance log for a deleted machine`, whatever its `is_active`; nothing written.
- **R3.** [BUG-1154] (P3) A live machine in a soft-deleted factory is refused like a deleted machine: 400 `Cannot create maintenance log for a deleted machine`, right after R2; nothing written. *(Today: accepted, with its activity entry.)*
- **R4.** A machine with `is_active = False`, `is_deleted = False`, or in a factory with `is_active = False`, `is_deleted = False`, is accepted.
- **R5.** One row is created with the input's six fields, `workspace_id` = the argument, `created_by = user_id`; `is_active = True`, `is_deleted = False`; `updated_at`, `updated_by`, `deleted_at`, `deleted_by` empty; `created_at` set. `cost` and `performed_by` omitted are `NULL`.
- **R6.** Any number of logs may share a machine, date and type: no duplicate check.
- **R7.** The returned object keeps `cost` as given until a refresh (DAO inherited R4); after one it is the stored value.
- **R8.** [BUG-1155] (P4) `MachineMaintenanceLogCreate` strips `summary`: `"  pad  "` is stored, and repeated in the entry, as `pad`, inner whitespace kept; `""` and `"   "` are rejected (`ValidationError`); nothing written. *(Today: all stored as given, and the entry repeats them.)*
- **R8a.** [BUG-1156] (P5) `MachineMaintenanceLogCreate` strips `performed_by`: `"  Rahim  "` is stored as `Rahim`; `""` and `"   "` are stored as `NULL`. *(Today: stored as given.)*
- **R8b.** A `summary` of 100 000 characters is stored and copied into the entry.
- **R9.** `performed_by` of 255 characters is stored.
- **R9a.** [BUG-1156] (P6) `performed_by` of 256 characters after trimming is rejected by `MachineMaintenanceLogCreate`; nothing written. 255 characters with surrounding spaces are accepted. *(Today: `DataError`, `.orig.pgcode == "22001"`, at the flush; a 500.)*
- **R10.** `cost` `9999999999999.99` is stored.
- **R10a.** [BUG-1157] (P7) A `cost` of more than 13 integer digits is rejected by `MachineMaintenanceLogCreate`: `10000000000000`, `1E+13`, `1e20`; nothing written. *(Today: `DataError`, `.orig.pgcode == "22003"`, at the flush; a 500.)*
- **R11.** `cost` `0` is stored as `0.00`, and so is `-0`.
- **R11a.** [BUG-1158] (Q1, owner) A negative `cost` is rejected by `MachineMaintenanceLogCreate`: `-5`, `-0.01`; nothing written. `MachineMaintenanceLogResponse` has no minimum. *(Today: stored, `-5` as `-5.00`, `-1.005` as `-1.01`.)*
- **R12.** [BUG-1157] (Q2, owner) A `cost` of more than 2 decimal places is rejected by `MachineMaintenanceLogCreate`: `5.001`, `0.125`, `1E-7`, `9999999999999.995`; nothing written. `5`, `5.1`, `5.00` are accepted, and so is `5.000`, because trailing zeros do not count. *(Today: the column rounds with no notice, `5.001` to `5.00`, `0.125` to `0.13`, and `9999999999999.995` raises `DataError`.)*
- **R13.** ✅ (Q5) `maintenance_date` has no bound: 1900 and 2099 are stored.
- **R14.** One activity entry: `event_type = "maintenance_logged"`, `description = "Maintenance logged: <summary>"`, `performed_by = user_id`, `workspace_id` = the argument, `machine_id` = the log's, `metadata_json = {"maintenance_log_id": <id>, "status": <type>}`. Neither `cost` nor `performed_by` is recorded in it.
- **R15.** `"status"` holds the maintenance type's value for each of the four types: `"PREVENTIVE"`, `"REPAIR"`, `"EMERGENCY"`, `"INSPECTION"`. A plain string, which only `model_construct` can bring, gives the same text. It is not a machine status and does not change the machine's status: `get_latest_status` reads only `status_updated` events.
- **R16.** Unknown `user_id` → `IntegrityError` (`ForeignKeyViolation`, `machine_maintenance_logs_created_by_fkey`); no log and no entry saved.
- **R17.** Flushed, not committed: rolling back a savepoint around the call removes the log and the entry.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| machine missing / other workspace / `0` / negative | `HTTPException` 404 | `Machine with ID <machine_id> not found` |
| machine soft-deleted; [BUG-1154] its factory soft-deleted | `HTTPException` 400 | `Cannot create maintenance log for a deleted machine` |
| [BUG-1155] blank `summary`; [BUG-1156] `performed_by` over 255; [BUG-1157] `cost` over 2 decimals or 13 integer digits; [BUG-1158] negative `cost` | `pydantic.ValidationError` building `MachineMaintenanceLogCreate` | not asserted |
| unknown `user_id` | `IntegrityError` / `ForeignKeyViolation` | — |

**Side effects:** one `machine_maintenance_logs` row; one `machine_activity_events` row; both flushed. No commit. The machine is not touched.

---

## `MachineMaintenanceLogManager.update_log(session, log_id, log_data, workspace_id, user_id)`
**Shape:** update
**Persistence:** writes
**Visibility:** public (used by: `MachineMaintenanceLogService.update_log` ← `PUT /machine-maintenance-logs/{id}/`; no frontend caller, Q6)

**Purpose:** Correct a log, recording what changed in the machine's activity log.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `session` | `Session` | open session; not committed here |
| `log_id` | int | primary key |
| `log_data` | `MachineMaintenanceLogUpdate` | `maintenance_type`, `maintenance_date`, `summary`, `cost`, `performed_by`, all optional, with the limits of `create_log`; `null` rejected on the first three [BUG-1153]. The log's machine cannot be changed: `machine_id`, `updated_by` or any other key in the body is dropped by the schema |
| `workspace_id` | int | caller's workspace |
| `user_id` | int | `updated_by` on the log, `performed_by` on the entry |

**Returns:** the same `MachineMaintenanceLog` instance, flushed, not committed.

**Rules:**
- **R1.** A log of another workspace, an unknown id or `0` → 404 `Maintenance log with ID <log_id> not found`, the answers identical; nothing written.
- **R2.** A soft-deleted log → 400 `Cannot update a deleted maintenance log`; nothing written, no entry.
- **R3.** [BUG-1101] (HR-16) A log whose machine belongs to another workspace → 404 as R1; nothing written, and that machine gets no entry. *(Today: updated, and `maintenance_updated` is written with the caller's `workspace_id` on the other workspace's machine.)*
- **R4.** A log with `is_active = False`, `is_deleted = False` is updated like any other; `is_active` stays `False`.
- **R5.** ✅ (Q3) A log of a soft-deleted machine, or of a machine in a soft-deleted factory, is updated like any other, and the entry is written to that machine.
- **R6.** Each of the five fields sent with a value is written; a field omitted stays as it was. `cost` `0` is a value and is applied.
- **R7.** [BUG-1153] (P2) An explicit `null` clears `cost` or `performed_by`, and the entry records `"to_value": None`. *(Today: ignored, the old value stays, 200.)*
- **R7a.** [BUG-1153] (P2) `null` for `maintenance_type`, `maintenance_date` or `summary` is rejected by `MachineMaintenanceLogUpdate` (`ValidationError`); nothing written. *(Today: ignored, 200.)*
- **R8.** When no field changes value (`{}`, the same values, or `null` on a field already empty), no activity entry is written.
- **R8a.** [BUG-1151] (HR-9) When no field changes value, nothing is written: `updated_by` and `updated_at` keep their values, and an unknown `user_id` raises nothing. The row is returned. *(Today: `updated_by` becomes `user_id` on every call, and `updated_at` is set whenever that is a different value; by the user already in `updated_by`, no UPDATE is issued. An unknown `user_id` raises as R15.)*
- **R9.** Values are compared by value: `cost` `5`, `5.0`, `5.00`, `5.000` on a log at `5.00` is no change.
- **R10.** When at least one field changes value, `updated_by = user_id`, `updated_at` is set, and one activity entry is written.
- **R11.** The entry: `event_type = "maintenance_updated"`, `description = "Maintenance log updated: <summary>"` with the **new** `summary`, `performed_by = user_id`, `workspace_id` = the argument, `machine_id` = the log's, `metadata_json = {"maintenance_log_id": <id>, "changes": [...]}`.
- **R12.** `changes` lists only fields whose value changed, in the order of `MAINTENANCE_LOG_FIELDS`, with `from_value` and `to_value` as strings: a type by its value (`"REPAIR"`), a date as `YYYY-MM-DD`, an empty old or new value as `None`.
- **R12a.** [BUG-1157] (Q2, owner) `cost` in `changes` is in the stored form, always two decimals, on both sides: `7` on `5.00` gives `"from_value": "5.00", "to_value": "7.00"`; `7.1` gives `"7.10"`; `1E+3` gives `"1000.00"`. A third decimal never gets here (R14). *(Today: `to_value` is as typed, `"7"`, `"7.1"`, `"1E+3"`; and `5.001` on `5.00` stores `5.00`, stamps the log and writes `"to_value": "5.001"`.)*
- **R13.** [BUG-1155] (P4) `summary` follows `create_log` R8 on `MachineMaintenanceLogUpdate`: stored trimmed, blank rejected, and the entry's `to_value` and `description` carry the trimmed text. *(Today: stored as given.)*
- **R13a.** [BUG-1156] (P5) `performed_by` follows `create_log` R8a on `MachineMaintenanceLogUpdate`; `""` or `"   "` clears it, as R7. *(Today: stored as given, and `"  "` is listed as a new value.)*
- **R13b.** [BUG-1158] (Q1, owner) A negative `cost` is rejected by `MachineMaintenanceLogUpdate`; nothing written. A log already negative is edited to `0` or more like any other change. *(Today: stored, `-5` as `-5.00`, and listed in `changes`.)*
- **R13c.** ✅ (Q5) `maintenance_date` has no bound: any date is stored and listed in `changes`.
- **R14.** [BUG-1156] [BUG-1157] (P6, P7, Q2) `performed_by` over 255 after trimming, and a `cost` outside `create_log` R10a, R12, are rejected by `MachineMaintenanceLogUpdate`; the log keeps its values and no entry is written. *(Today: `DataError` at the flush, a 500, for the first two kinds; a third decimal is rounded by the column.)*
- **R15.** Unknown `user_id` with a change → `IntegrityError` (`ForeignKeyViolation`, `machine_maintenance_logs_updated_by_fkey`); the log keeps its values and no entry is written.
- **R16.** The returned object is the very instance read, and keeps `cost` as given until a refresh.
- **R17.** Flushed, not committed: rolling back a savepoint around the call restores the log and removes the entry.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| log missing / other workspace / `0`; [BUG-1101] its machine in another workspace | `HTTPException` 404 | `Maintenance log with ID <log_id> not found` |
| log soft-deleted | `HTTPException` 400 | `Cannot update a deleted maintenance log` |
| [BUG-1153] `null` on a required field; [BUG-1155] blank `summary`; [BUG-1156] `performed_by` over 255; [BUG-1157] `cost` over 2 decimals or 13 integer digits; [BUG-1158] negative `cost` | `pydantic.ValidationError` building `MachineMaintenanceLogUpdate` | not asserted |
| unknown `user_id` | `IntegrityError` / `ForeignKeyViolation` | — |

**Side effects:** the log's changed fields, `updated_by`, `updated_at`; at most one `machine_activity_events` row; all flushed. No commit. `maintenance_date` changing does not touch the machine.

---

## `MachineMaintenanceLogManager.get_log(session, log_id, workspace_id, include_deleted=False)`
**Shape:** get-or-404
**Persistence:** reads
**Visibility:** public (used by: `MachineMaintenanceLogService.get_log` ← `GET /machine-maintenance-logs/{id}/`; no frontend caller, Q6)

**Purpose:** One log by id, inside a workspace.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `session` | `Session` | open session |
| `log_id` | int | primary key |
| `workspace_id` | int | caller's workspace |
| `include_deleted` | bool, default `False` | [BUG-1150] new parameter, reachable from the API |

**Returns:** the `MachineMaintenanceLog` the session holds.

**Rules:**
- **R1.** A live log of that workspace is returned.
- **R2.** A log of another workspace, an unknown id, `0` or a negative id → 404 `Maintenance log with ID <log_id> not found`, the answers identical.
- **R3.** [BUG-1150] (HR-4) A soft-deleted log → 404 as R2. *(Today: returned, 200.)*
- **R3a.** [BUG-1150] With `include_deleted=True` a soft-deleted log is returned. *(Today: the parameter does not exist.)*
- **R4.** A log with `is_active = False`, `is_deleted = False` is returned.
- **R5.** A log of a soft-deleted machine, or of a machine in a soft-deleted factory, is returned, with the default too (standing decision 1).
- **R6.** [BUG-1101] (HR-16) A log whose machine belongs to another workspace → 404 as R2, also with `include_deleted=True`. *(Today: returned to the log's workspace. Asked from the machine's workspace it is 404 today too.)*
- **R7.** The call writes nothing.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| log missing / other workspace; [BUG-1150] soft-deleted; [BUG-1101] its machine in another workspace | `HTTPException` 404 | `Maintenance log with ID <log_id> not found` |

**Side effects:** none

---

## `MachineMaintenanceLogManager.list_logs(session, workspace_id, machine_id=None, maintenance_type=None, skip=0, limit=100)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `MachineMaintenanceLogService.list_logs` ← `GET /machine-maintenance-logs/`, always with `skip`, `limit`; no frontend caller, Q6)

**Purpose:** A workspace's logs, optionally of one machine, of one type, or both, one page at a time.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `session` | `Session` | open session |
| `workspace_id` | int | caller's workspace |
| `machine_id` | int \| `None` | optional filter; only `None` means "no filter" [BUG-1152]; existence not checked |
| `maintenance_type` | `MaintenanceTypeEnum` \| `None` | optional filter; the endpoint lets only members through |
| `skip`, `limit` | int | defaults `0`, `100`; not validated here |

**Returns:** a `list` of `MachineMaintenanceLog` (possibly empty).

**Rules:**
- **R1.** Neither filter: the workspace's live logs, as DAO `get_by_workspace` R1, R2, R5, R6.
- **R2.** `machine_id` alone: that machine's live logs in the workspace, as DAO `get_by_machine` R1–R3. Another machine's logs never appear.
- **R3.** `maintenance_type` alone: the workspace's live logs of that type, as DAO `get_by_type` R1.
- **R4.** Both: logs matching machine, type and workspace, as DAO `get_by_machine_and_type` R1.
- **R5.** [BUG-1152] (P1) `machine_id=0` filters like any integer and returns `[]`, with or without a type. *(Today: `0` means "no filter": alone it behaves as R1, with a type as R3.)*
- **R6.** An unknown machine id, a negative one, or a machine of another workspace returns `[]` with or without a type: no 404 and no sign that the machine exists. A type no log has returns `[]`. An unknown or empty workspace returns `[]`.
- **R7.** `maintenance_type` forms, at this level only: `"REPAIR"` works like the member; `""` is falsy and means "no filter", with or without a machine; `"BOGUS"` raises `DataError`, `.orig.pgcode == "22P02"`.
- **R8.** `skip` and `limit` reach all four paths: `limit=1`, `skip=1` page each of them. Defaults give at most 100: of 101 logs, exactly 100 on each path, and 101 with `limit=1000`. `limit=0` or `skip` at or past the end gives `[]`.
- **R9.** A negative `limit` or `skip` raises `DataError` on all four paths (`2201W`, `2201X`), as DAO `get_by_workspace` R7.
- **R10.** Different dates come back latest `maintenance_date` first on all four paths. [BUG-1100] (HR-6) Logs on one date come back highest `id` first, before `skip` / `limit`. *(Today: no tie-break, DAO `get_by_workspace` R4a.)*
- **R11.** A soft-deleted log is never returned and takes no place in the page. A log with `is_active = False` is returned. A log of a soft-deleted machine, or of a machine in a soft-deleted factory, is returned on every path, also when that machine is asked for by id (standing decision 1).
- **R12.** [BUG-1101] (HR-16) A log whose machine belongs to another workspace is not returned, on any path, and takes no place in the page. *(Today: returned, showing that machine's id, with no filter and with that `machine_id`.)*
- **R13.** The call writes nothing.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| negative `limit` | `DataError`; `.orig.pgcode == "2201W"` | `LIMIT must not be negative` |
| negative `skip` | `DataError`; `.orig.pgcode == "2201X"` | `OFFSET must not be negative` |
| a string that is no member's value | `DataError`; `.orig.pgcode == "22P02"` | — |

**Side effects:** none

---

## `MachineMaintenanceLogManager.delete_log(session, log_id, workspace_id, user_id)`
**Shape:** soft-delete
**Persistence:** writes
**Visibility:** public (used by: `MachineMaintenanceLogService.delete_log` ← `DELETE /machine-maintenance-logs/{id}/`, called by the frontend from a machine's activity list)

**Purpose:** Remove a log from view, keeping the row, and say so in the machine's activity log.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `session` | `Session` | open session; not committed here |
| `log_id` | int | primary key |
| `workspace_id` | int | caller's workspace |
| `user_id` | int | `deleted_by` on the log, `performed_by` on the entry |

**Returns:** the same `MachineMaintenanceLog` instance, soft-deleted, flushed, not committed.

**Rules:**
- **R1.** A log of another workspace, an unknown id or `0` → 404 `Maintenance log with ID <log_id> not found`, the answers identical; nothing written.
- **R2.** An already soft-deleted log → 400 `Maintenance log is already deleted`; the first delete's `deleted_by` and `deleted_at` stay, and no entry is written.
- **R3.** [BUG-1101] (HR-16) A log whose machine belongs to another workspace → 404 as R1; nothing written. *(Today: soft-deleted, and `maintenance_removed` is written on the other workspace's machine.)*
- **R4.** A log with `is_active = False`, `is_deleted = False` is deleted like any other.
- **R5.** ✅ (Q4) A log of a soft-deleted machine, or of a machine in a soft-deleted factory, is deleted like any other, and the entry is written to that machine.
- **R6.** After the call: DAO `soft_delete` R1, R2: `is_deleted = True`, `is_active = False`, `deleted_by = user_id`, `deleted_at` set; `updated_by` is not stamped; `cost`, `summary` and the other columns keep their values.
- **R6a.** [BUG-1102] `deleted_at` is `utcnow()`, naive UTC, as DAO `soft_delete` R1a. *(Today: the database's `now()`.)*
- **R7.** One activity entry: `event_type = "maintenance_removed"`, `description = "Maintenance log removed: <summary>"`, `performed_by = user_id`, `workspace_id` = the argument, `machine_id` = the log's, `metadata_json = {"maintenance_log_id": <id>}`. The earlier `maintenance_logged` entry stays.
- **R8.** Only that log changes: other logs of the machine and the machine itself stay as they were.
- **R9.** Afterwards in the same session: the log is in no list; `update_log` answers 400 (R2 there); a second `delete_log` answers 400 (R2); `get_log` follows its R3.
- **R10.** Unknown `user_id` → `IntegrityError` (`ForeignKeyViolation`, `machine_maintenance_logs_deleted_by_fkey`); the log stays live and no entry is written.
- **R11.** The returned object is the very instance read. Flushed, not committed: rolling back a savepoint around the call makes the log live again with an empty stamp and removes the entry.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| log missing / other workspace / `0`; [BUG-1101] its machine in another workspace | `HTTPException` 404 | `Maintenance log with ID <log_id> not found` |
| log already soft-deleted | `HTTPException` 400 | `Maintenance log is already deleted` |
| unknown `user_id` | `IntegrityError` / `ForeignKeyViolation` | — |

**Side effects:** one `machine_maintenance_logs` row updated (`is_deleted`, `is_active`, `deleted_at`, `deleted_by`; `updated_at` by the ORM); one `machine_activity_events` row; both flushed. No commit.

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 20–26 | fields tracked, and their order | `update_log` R12 |
| 45–47 | raw machine lookup inside the workspace; factory (BUG-1154) and `is_active` not read | `create_log` R1, R3, R4 |
| 48–52 | machine found / not found | `create_log` R1 |
| 53–57 | machine soft-deleted | `create_log` R2 |
| 59–61 | all six fields, `workspace_id`, `created_by` | `create_log` R5 |
| 63 | create: flush; FK, range and length errors; no value check on the schema (BUG-1155 … BUG-1158) | `create_log` R5–R13, R16 |
| 64–75 | `maintenance_logged`, always | `create_log` R14, R17 |
| 73 | `hasattr(..., "value")`: member / plain string | `create_log` R15 |
| 87–89 | raw lookup; machine not read (BUG-1101, Q3) | `update_log` R3, R4, R5 |
| 90–94 | log found / not found | `update_log` R1 |
| 95–99 | log soft-deleted | `update_log` R2 |
| 101 | `exclude_unset`: omitted skipped; `exclude_none`: `null` dropped (BUG-1153) | `update_log` R6, R7, R7a |
| 102 | `updated_by` always set (BUG-1151) | `update_log` R8a, R10 |
| 104–106 | changes computed before the write, from the typed values (BUG-1157) | `update_log` R9, R12, R12a |
| `machine_activity_manager.py` 57–59 | `field not in update_dict` | `update_log` R6, R12 |
| `machine_activity_manager.py` 62–63 | same value skipped; compared by value | `update_log` R8, R9, R12a |
| `machine_activity_manager.py` 40–48 | `format_field_value`: `None`, enum, date, `Decimal` and `str` by `str()`; the `datetime` branch is not reached by these fields | `update_log` R12, R12a |
| 107 | update: flush; no UPDATE if nothing differs; FK, range, length errors | `update_log` R8a, R10, R13–R13c, R14, R15, R16 |
| 108 | `if changes:` | `update_log` R8, R10, R11 |
| 124–126 | raw lookup; `is_deleted` not read (BUG-1150); machine not read (BUG-1101) | `get_log` R1, R3, R3a, R4, R5, R6 |
| 127–131 | log found / not found | `get_log` R2 |
| 141 | defaults `skip=0`, `limit=100` | `list_logs` R8 |
| 144 | `machine_id and maintenance_type` truthy; `0` falsy (BUG-1152) | `list_logs` R4, R5, R7 |
| 149 | `machine_id` truthy; `0` falsy (BUG-1152) | `list_logs` R2, R5, R6 |
| 154 | `maintenance_type` truthy; `""` falsy | `list_logs` R3, R5, R7 |
| 159–161 | no filter | `list_logs` R1, R5 |
| DAO lists | filters, order, paging, negative values (BUG-1100, BUG-1101) | `list_logs` R6, R8–R13 |
| 171–173 | raw lookup; machine not read (BUG-1101, Q4) | `delete_log` R3, R4, R5 |
| 174–178 | log found / not found | `delete_log` R1 |
| 179–183 | log soft-deleted | `delete_log` R2, R9 |
| 185 | `soft_delete`: flush; FK on `deleted_by`; BUG-1102 | `delete_log` R6, R6a, R10 |
| 186–194 | `maintenance_removed`, always | `delete_log` R7, R8 |
| 195 | returns the row | `delete_log` R11 |
