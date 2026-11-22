# Spec — `app/managers/factory_section_manager.py`

> **Status:** APPROVED (2026-10-16)
> **Source commit:** e48a092

> **Review round 2026-10-16.** The reviewer delegated every open decision of this spec to Claude. Decided by Claude under the reviewer's delegation (2026-10-16): every suggested answer is accepted — P1–P5 (bug: BUG-921 … BUG-925), Q1–Q3 (bug: BUG-926, BUG-927, BUG-928) and every house-rule / reused-bug line (BUG-911 … BUG-920; BUG-903, BUG-908 cited, no new ID). None of these is the reviewer's own answer. The "(pilot default — awaiting reviewer)" markers were removed; no rule changed. BUG-911 … BUG-928 are logged in `docs/testing/bugs.md` with the delegation wording.

> **Pilot convention:** every question below carried a suggested answer, applied to the rules as a provisional default. All were accepted on 2026-10-16 (decided by Claude under the reviewer's delegation); nothing is provisional any more.
>
> **Standing reviewer decisions applied here (not asked again):**
> 1. Soft-deleted rows are kept but must not show up in lists or be counted (inventory DAO Q2, 2026-10-10).
> 2. Things of a soft-deleted factory or section are **hidden by the parent's state, their own rows untouched** ("hidden, not cascaded" — machine DAO P1 / P2; confirmed 2026-10-11). Here: a section of a soft-deleted factory is hidden (BUG-904, and P4 / P5 below), and the machine assignments of a soft-deleted section are kept (BUG-908).
> 3. **BUG-908** (accepted 2026-10-16, assignment DAO spec P3): `delete_factory_section` must not erase the section's machine assignments. Tagged here with BUG-908 — no new ID. Today the delete also brings BUG-906 (no order) and BUG-907 (10 000 cap) with it; after the fix those, the import of the assignment manager (`factory_section_manager.py:13-15`) and the refresh of loaded machines go away (dead-code list entry already present).
> 4. **BUG-910** (accepted 2026-10-16): a machine may not be put into a section of a soft-deleted factory. By the same reasoning, writes into a soft-deleted factory are refused here: create and "move into" already are (holds today, `create_factory_section` R4, `update_factory_section` R8); renaming / editing a section that sits in a soft-deleted factory is not — Q1 (assignment manager FU-1 (c)).
> 5. A `restore` method with no caller is kept; "restore section" is a feature to build (section DAO FU-1). This manager has no restore method; nothing here is dead code because of it.
> 6. "Whitespace" means what Python's `str.strip()` removes (machine DAO P3).
> 7. The physical row order of the test database is **not** deterministic. No order recipe in this spec is called verified or deterministic; every case that depends on which rows land in a page is a **non-strict** xfail.
>
> **Sibling precedent:** `FactoryManager` (`tests/unit/managers/factory_manager.spec.md`, APPROVED) has the same code shape. Its decisions on trimming, blank names, case-insensitive uniqueness, the 100-row duplicate scan, page-before-filter, search trimming and the unreachable `include_deleted` are applied here; each gets its own new bug ID (this file's code), citing the factory manager's ID as precedent.
>
> **Verified by running** (two throwaway scripts against the test database, rolled back; nothing created or dropped): every "Today:" note below; every status code and detail message; the table's indexes (primary key and plain indexes on `id`, `workspace_id` — no unique index); create into a missing / other-workspace / `0` / soft-deleted / inactive factory; exact, case and whitespace duplicates; `""` and `"   "` names on create and update; reuse of a soft-deleted section's name; the 100-row scan (100 soft-deleted sections created first, then "Late": the check returned `False` and a second "Late" was created — an observation, order-dependent); `exclude_id`; update of a missing / other-workspace / soft-deleted section; rename collisions (exact → 409, case variant → accepted); `{}`, same values and `name=None` stamping `updated_by`; moving into a factory that already has the name (accepted, two live "Cut"), with and without a new name; moving into a missing / other-workspace / `-1` / soft-deleted / inactive factory; `factory_id=0` on update (foreign-key error); moving a section with an assigned machine (assignment kept, machine of the old factory now in a section of the new one); rename / same-factory update / move-out / delete / get of a section of a soft-deleted factory (all succeed); get of a soft-deleted section; the list with and without a factory, `include_deleted`, sections of a soft-deleted factory, `factory_id=0` and `-1`, search case / untrimmed / whitespace-only / `""` / `%` / `_`, `limit=0`, negative `limit` / `skip`, the 100-row default (101 live → 100) on both branches, and 100 soft-deleted then one live (default page `[]`, `skip=100` shows it — observation, order-dependent); delete of a missing / other-workspace / already-deleted section, the foreign-key error on `deleted_by`, the columns written, assignment rows of the section erased (other sections' kept), a loaded machine reading `None` afterwards, and delete → section DAO `restore` giving an empty section. **Not run:** anything at the HTTP level; the race behind BUG-913 (argued from the missing index, which was verified); the *intended* behavior of the bug rules.

## Review
> Reviewer: answer each question on its **Answer:** line with one of
> `intended` · `bug` · `bug — <what it should do instead>` · `remove` (unreachable
> code only) · or a question back.
> Then run the describer in `apply-review` mode.

### Quick list — all accepted (decided by Claude under the reviewer's delegation, 2026-10-16)
| # | What the code does today, in plain words | Answer (accepted) |
|---|---|---|
| P1 | The section search does not trim the text: `" hall "` finds nothing | bug — trim; a search of only spaces means "no search" (same as factories, BUG-902) — BUG-921 |
| P2 | Asking for the sections of "factory 0" returns the sections of every factory | bug — `0` is a factory id like any other and matches nothing (same as stock, BUG-880) — BUG-922 |
| P3 | Editing a section with "factory 0" crashes with a database error (500) instead of "factory not found" | bug — answer 404 `Factory with ID 0 not found` like any unknown factory — BUG-923 |
| P4 | The section list without a factory filter still shows sections of a deleted factory | bug — hide them, as the list of one factory will (BUG-904) — BUG-924 |
| P5 | Opening one section by id still works when its factory is deleted | bug — 404 like a deleted section (BUG-904 / BUG-916) — BUG-925 |
| Q1 | A section inside a deleted factory can still be renamed, or moved out of it | bug — refuse with 400 like a deleted section (same reasoning as BUG-910) — BUG-926 |
| Q2 | A section inside a deleted factory can still be deleted | bug — refuse with 400 "Cannot delete a section of a deleted factory" — BUG-927 |
| Q3 | Moving a section to another factory takes its machines along: machines of factory A end up "in" a section of factory B, a link the machine screen itself refuses | bug — refuse the move with 400 while machines are assigned to the section — BUG-928 |

Nothing here needs the owner (no money, no order workflow).

Already decided by house rules / existing bugs (kept as applied — decided by Claude under the reviewer's delegation, 2026-10-16):
- the duplicate-name check looks at only the first 100 sections of the factory → BUG-911 (HR-2; as BUG-893 for factories);
- "Paint", "paint" and " Paint " count as three different names → BUG-912 (HR-2; as BUG-894);
- the database does not stop two sections with the same name → BUG-913 (HR-2; as BUG-895);
- moving a section into a factory where its name is already used is not checked at all → BUG-914 (HR-2, new);
- blank names are accepted, names are stored with their spaces → BUG-915 (HR-1; as BUG-896);
- opening a deleted section by id still works → BUG-916 (HR-4; as BUG-897);
- the list drops deleted sections and applies the search only after cutting the page → BUG-917 (HR-5; as BUG-898);
- the list without a factory filter has no sort order → BUG-918 (HR-6; as BUG-899) — the list of one factory is BUG-903 (section DAO, cited);
- saving a section without changing anything still records "last changed by" → BUG-919 (HR-9; as BUG-900);
- the "include deleted" switch of the list cannot be reached from the API → BUG-920 (HR-4; as BUG-901);
- deleting a section erases its machines' assignments → BUG-908 (cited; with it BUG-906 and BUG-907).

### House-rule violations — applied automatically
> All kept as applied — decided by Claude under the reviewer's delegation (2026-10-16).

- **HR-2** `_check_name_exists_in_factory` R5 — the duplicate check loads at most 100 sections of the factory (soft-deleted ones included, in no order) and looks only at those; a live duplicate outside them is missed. Intended: every live section of the factory is checked. (The BUG-905 fix in the section DAO stops deleted rows from taking places; the 100-row cap on live sections stays — this fix is in the manager, e.g. a dedicated existence query.)
**Answer:** bug — per HR-2 (house rule)
**Resolution:** 🐞 BUG-911 (pattern `capped-uniqueness-scan`; precedent BUG-893). Rules: `_check_name_exists_in_factory` R5. Kept as applied — decided by Claude under the reviewer's delegation (2026-10-16).
- **HR-2** `_check_name_exists_in_factory` R4 — names are compared with exact equality: "Paint", "paint" and " Paint " are three different names (verified: all three created in one factory). Intended: compared case-insensitively after trimming.
**Answer:** bug — per HR-2 (house rule)
**Resolution:** 🐞 BUG-912 (pattern `unnormalised-uniqueness-compare`; precedent BUG-894). Rules: `_check_name_exists_in_factory` R4. Kept as applied — decided by Claude under the reviewer's delegation (2026-10-16).
- **HR-2** `create_factory_section` R9, `update_factory_section` R15 — `factory_sections` has no unique index (verified); two requests at the same moment both pass the Python check. Intended: a partial unique index on live rows, per factory, on the normalised name (lower-case of the trimmed name); a violation surfaces as 409, never 500. (Noted as open in section DAO P4 / FU-2 (e).)
**Answer:** bug — per HR-2 (house rule)
**Resolution:** 🐞 BUG-913 (pattern `python-only-uniqueness`; precedent BUG-895). Rules: `create_factory_section` R9, `update_factory_section` R15. Kept as applied — decided by Claude under the reviewer's delegation (2026-10-16).
- **HR-2** `update_factory_section` R9 — moving a section to another factory checks the name in the target factory only when a *different* name is sent at the same time. A move alone (or a move re-sending the current name) is never checked: "Cut" of factory A moved into factory B, which already has a live "Cut", is saved — B then has two live "Cut" (verified). Intended: whenever the section's factory or name changes, the resulting name is checked against the live sections of the resulting factory (409 on a clash).
**Answer:** bug — per HR-2 (house rule)
**Resolution:** 🐞 BUG-914 (pattern `uniqueness-unchecked-on-move`, new). Rules: `update_factory_section` R9. Kept as applied — decided by Claude under the reviewer's delegation (2026-10-16).
- **HR-1** `create_factory_section` R8, `update_factory_section` R12 — names are stored exactly as typed (`"  Paint "` keeps its spaces); `""` and `"   "` are accepted on create and on update (`""` on update even skips the duplicate check). Intended: stored trimmed; blank / whitespace-only rejected by `FactorySectionCreate` / `FactorySectionUpdate` (422), nothing written. Fix in `app/schemas/factory_section.py` on the create / update schemas, not on `FactorySectionBase`, which `FactorySectionResponse` inherits.
**Answer:** bug — per HR-1 (house rule)
**Resolution:** 🐞 BUG-915 (pattern `blank-name-accepted`; precedent BUG-896). Rules: `create_factory_section` R8, `update_factory_section` R12. Kept as applied — decided by Claude under the reviewer's delegation (2026-10-16).
- **HR-4** `get_factory_section` R3, R4 — a soft-deleted section is returned by id (`GET /factory-sections/{id}/` answers 200), although the list hides it and update answers 400. Intended: 404 by default; a new `include_deleted=True` parameter returns it.
**Answer:** bug — per HR-4 (house rule)
**Resolution:** 🐞 BUG-916 (pattern `get-returns-soft-deleted`; precedent BUG-897). Rules: `get_factory_section` R3, R4. Kept as applied — decided by Claude under the reviewer's delegation (2026-10-16).
- **HR-5** `search_factory_sections` R3, R5 — one page of `limit` rows is loaded first (deleted sections included), and only then are deleted rows dropped and the search applied, in Python. Pages come back short or empty although more sections exist, and the search only looks inside the loaded page. Intended: filter first, then page. For a list of one factory the deleted part is also removed by the section DAO's BUG-905; the search part, and the whole of the list without a factory, are this bug.
**Answer:** bug — per HR-5 (house rule)
**Resolution:** 🐞 BUG-917 (pattern `paginate-before-filter`; precedent BUG-898 — one ID, one fix: move the filters into the query). Rules: `search_factory_sections` R3, R5. Kept as applied — decided by Claude under the reviewer's delegation (2026-10-16).
- **HR-6** `search_factory_sections` R4 — no sort order. Intended: name case-insensitive ascending, then `id` ascending, before `skip` / `limit`. With a factory given, the order comes from the section DAO's `get_by_factory` — already BUG-903 (cited, no new ID). Without a factory, the list reads the generic `get_by_workspace`, which after BUG-100 only guarantees `id` order; the display order is this manager's job (HR-6) — new ID.
**Answer:** bug — per HR-6 (house rule)
**Resolution:** 🐞 BUG-918 (pattern `unordered-pagination`; precedent BUG-899) for the list without a factory; BUG-903 (existing) for the list of one factory. Rules: `search_factory_sections` R4. Kept as applied — decided by Claude under the reviewer's delegation (2026-10-16).
- **HR-9** `update_factory_section` R13 — `updated_by` is written on every successful update, including `{}`, `null` fields and unchanged values (verified: `{}` sets `updated_by` and `updated_at`). Intended: only when the name or the factory actually changes.
**Answer:** bug — per HR-9 (house rule)
**Resolution:** 🐞 BUG-919 (pattern `audit-stamp-on-noop`; precedent BUG-900). Rules: `update_factory_section` R13. Kept as applied — decided by Claude under the reviewer's delegation (2026-10-16).
- **HR-4** (second bullet) `search_factory_sections` R6 — the list has an `include_deleted` option that `FactorySectionService.get_factory_sections` and `GET /factory-sections/` never pass. Intended: reachable from the API. The manager behaves correctly today; the fix is in the service and the endpoint — and, once BUG-905 hides deleted sections in the DAO, the manager needs a lookup that can still return them.
**Answer:** bug — per HR-4 (house rule)
**Resolution:** 🐞 BUG-920 (pattern `flag-unreachable-from-api`; precedent BUG-901). Rules: `search_factory_sections` R6. Integration note: `FactorySectionResponse` has no `is_deleted`, so a listed deleted section cannot be told from a live one. Kept as applied — decided by Claude under the reviewer's delegation (2026-10-16).
- **HR-8** `search_factory_sections` R8a — search text must be literal. Holds today (Python substring test; verified `%` finds only "50% zone", `_` finds nothing). The BUG-917 fix moves the search into SQL, where the text must be escaped. Same fix as BUG-917 — no new ID; the cases are regression guards, not expected-to-fail.
**Answer:** bug — per HR-8 (house rule)
**Resolution:** logged against BUG-917. Kept as applied — decided by Claude under the reviewer's delegation (2026-10-16).

Checked and **not** violated: **HR-7** — `GET /factory-sections/` enforces `limit >= 1` (and `skip >= 0`, `limit <= 1000`). **HR-10** — rename, move and soft delete are plain state changes; no lock. **HR-3** — no categorical free text.

### Precedent matches — all accepted (decided by Claude under the reviewer's delegation, 2026-10-16)

### P1. The section search does not trim the text — 🐞 BUG-921
**Background:** `GET /factory-sections/?search=…` looks for the text inside the section name, ignoring case. The text is used exactly as typed. For machines and factories the reviewer ruled (BUG-892, BUG-902): trim; a whitespace-only search means "no search".
**What happens today:** `" hall "` does not find "Main Hall"; a search of three spaces returns only sections whose name contains three spaces in a row (verified: `[]`).
**Example:** A user pastes "Main Hall " (trailing space) into the section search and gets an empty list.
**Rules affected:** `search_factory_sections` R9
**Answer:** bug — per BUG-902 precedent: leading / trailing whitespace (`str.strip()`) is removed before matching; a whitespace-only search applies no search filter
**Resolution:** 🐞 BUG-921 (pattern `whitespace-search-empties-results`; precedent BUG-902) — decided by Claude under the reviewer's delegation (2026-10-16): the suggested precedent answer is accepted. Rules: `search_factory_sections` R9.

### P2. "Factory 0" lists the sections of every factory — 🐞 BUG-922
**Background:** The section list takes an optional `factory_id`. The code asks `if factory_id:`, so the value `0` is treated like "no factory given". The endpoint accepts any integer, `0` included. For stock and the inventory ledger the reviewer ruled that only "not given" means "no filter" (BUG-880, BUG-885).
**What happens today:** `factory_id=0` returns the sections of the whole workspace (verified), while `factory_id=-1` or an unknown id returns `[]`.
**Example:** A client that sends `factory_id=0` for "no factory picked yet" shows every section of every factory under an empty factory heading.
**Rules affected:** `search_factory_sections` R2a
**Answer:** bug — per BUG-880 precedent (`falsy-zero-treated-as-missing`): only `None` means "no factory filter"; `factory_id=0` filters like any other id and returns `[]`
**Resolution:** 🐞 BUG-922 (pattern `falsy-zero-treated-as-missing`; precedent BUG-880) — decided by Claude under the reviewer's delegation (2026-10-16): the suggested precedent answer is accepted. Rules: `search_factory_sections` R2a.

### P3. Editing a section with "factory 0" crashes — 🐞 BUG-923
**Background:** On update, a new `factory_id` is checked (exists in the workspace, not deleted) only `if section_data.factory_id and …` — `0` skips the check. The value is still written, and no factory has id 0.
**What happens today:** `PUT /factory-sections/{id}/` with `{"factory_id": 0}` fails at the database with a foreign-key error (`factory_sections_factory_id_fkey`) — a 500, nothing saved (verified). `-1` correctly answers 404 `Factory with ID -1 not found`.
**Example:** A buggy client sends `factory_id: 0`; the user sees "Internal server error" instead of "Factory with ID 0 not found".
**Rules affected:** `update_factory_section` R8a
**Answer:** bug — per BUG-880 precedent (`falsy-zero-treated-as-missing`): only `None` (not sent) means "keep the factory"; `factory_id=0` is checked like any other id → 404 `Factory with ID 0 not found`, nothing written
**Resolution:** 🐞 BUG-923 (pattern `falsy-zero-treated-as-missing`; precedent BUG-880) — decided by Claude under the reviewer's delegation (2026-10-16): the suggested precedent answer is accepted. Rules: `update_factory_section` R8a.

### P4. The list without a factory filter shows sections of a deleted factory — 🐞 BUG-924
**Background:** Standing decision 2: a section whose factory is soft-deleted is hidden by the factory's state, its own row untouched. For the list of one factory this is BUG-904 (section DAO, accepted). The list *without* a factory filter reads the generic workspace lookup, which never looks at the factory (section DAO FU-2 (c)).
**What happens today:** `GET /factory-sections/` lists the live sections of soft-deleted factories along with the rest (verified: "hidden hall" of a deleted factory is listed, and found by a search for "hall").
**Example:** "Old Plant" was deleted with its sections "Cutting" and "Paint". The workspace-wide section list still shows both, under a factory that no longer exists in the UI.
**Rules affected:** `search_factory_sections` R7
**Answer:** bug — per BUG-904 precedent (`join-ignores-soft-deleted`): with or without a factory filter, a section whose factory has `is_deleted = True` is not returned and takes no place in the page; its row is untouched and it is listed again once the factory is no longer deleted; an inactive-but-live factory hides nothing. With `include_deleted=True` such sections are returned too (the switch means "show what deletion hides")
**Resolution:** 🐞 BUG-924 (pattern `join-ignores-soft-deleted`; precedent BUG-904) — decided by Claude under the reviewer's delegation (2026-10-16): the suggested precedent answer is accepted. Rules: `search_factory_sections` R7.

### P5. Opening a section of a deleted factory by id still works — 🐞 BUG-925
**Background:** As P4. `get_factory_section` checks only that the section exists in the workspace; neither its own deleted flag (BUG-916) nor its factory's is looked at.
**What happens today:** `GET /factory-sections/{id}/` answers 200 with a live section of a soft-deleted factory (verified).
**Example:** A bookmarked link to "Paint" of the deleted "Old Plant" still opens the section page although "Paint" is in no list.
**Rules affected:** `get_factory_section` R5
**Answer:** bug — per BUG-904 / BUG-916 precedent: a section whose factory has `is_deleted = True` → 404 `Factory section with ID <id> not found` by default; `include_deleted=True` returns it; an inactive-but-live factory hides nothing
**Resolution:** 🐞 BUG-925 (pattern `join-ignores-soft-deleted`; precedent BUG-904 / BUG-916) — decided by Claude under the reviewer's delegation (2026-10-16): the suggested precedent answer is accepted. Rules: `get_factory_section` R5.

### New questions

### Q1. A section inside a deleted factory can still be renamed or moved out — 🐞 BUG-926
**Background:** Creating a section in a deleted factory is refused (400 `Cannot create section for deleted factory`), and so is moving a section *into* one (400 `Cannot move section to deleted factory`). A section already inside a factory that is then deleted keeps its own row live (standing decision 2) and is hidden (BUG-904, P4, P5). For machines the same situation was decided on 2026-10-16: a section of a deleted factory is refused like a deleted section (BUG-910). Update refuses a *deleted section* with 400 `Cannot update deleted factory section`.
**What happens today:** `update_factory_section` never looks at the section's current factory. A section of a deleted factory can be renamed, re-saved with the same factory id, or moved to a live factory (all verified). The duplicate check still works today; after BUG-904 it would see no sections of that factory at all.
**Example:** "Old Plant" is deleted. Someone with a stale screen renames its section "Paint" to "Spray" (200). When "Old Plant" is restored, "Paint" has silently become "Spray". Or the section is moved to "New Plant" — it leaves the deleted factory, and a restore of "Old Plant" no longer brings it back.
**Rules affected:** `update_factory_section` R3a
**Answer:** bug — a section whose factory has `is_deleted = True` is refused like a deleted section: 400 `Cannot update deleted factory section`, nothing written, whatever the request (rename, same factory, move out); checked right after the section's own deleted flag. An inactive-but-live factory is not refused. (Alternative offered and not taken: `intended`, if moving a section out of a deleted factory should be the way to rescue it.)
**Resolution:** 🐞 BUG-926 (pattern `write-to-soft-deleted-related-row`; same reasoning as BUG-910) — decided by Claude under the reviewer's delegation (2026-10-16): the suggested answer is accepted. Rules: `update_factory_section` R3a.

### Q2. A section inside a deleted factory can still be deleted — 🐞 BUG-927
**Background:** As Q1. `delete_factory_section` refuses a missing section (404) and an already-deleted one (400 `Factory section is already deleted`), but never looks at the factory. The section is hidden (P4, P5), so only a client holding its id can reach it.
**What happens today:** The section is soft-deleted normally (verified) — and today its machine assignments are erased with it (BUG-908). When the factory is restored, that section stays deleted.
**Example:** "Old Plant" is deleted. A stale screen still shows its section "Paint"; the user deletes it (200). Support restores "Old Plant": every section is back except "Paint".
**Rules affected:** `delete_factory_section` R10
**Answer:** bug — a section whose factory has `is_deleted = True` cannot be deleted: 400 `Cannot delete a section of a deleted factory`, nothing written; checked after the "already deleted" check. An inactive-but-live factory is not refused. (Alternatives offered and not taken: `intended`, if deleting a hidden section is acceptable; `bug — 404 Factory section with ID <id> not found`, if a hidden section should look absent.)
**Resolution:** 🐞 BUG-927 (pattern `write-to-soft-deleted-related-row`) — decided by Claude under the reviewer's delegation (2026-10-16): the suggested answer is accepted. Rules: `delete_factory_section` R10.

### Q3. Moving a section takes its machines into another factory — 🐞 BUG-928
**Background:** A machine belongs to one factory and may be put into one section; the machine screen refuses a section of another factory (400 `Factory section does not belong to this machine's factory`, assignment manager `set_assignment` R8). The link is its own row (machine → section). `update_factory_section` can change a section's factory and never looks at those links.
**What happens today:** Moving section "Paint" (with machine "Sprayer 1" of factory A assigned) to factory B succeeds; the link is kept, so "Sprayer 1" — still a machine of A — is now "in" a section of B (verified). Editing "Sprayer 1" and re-sending its section then answers 400.
**Example:** A user moves "Paint" from "Plant A" to "Plant B" to reorganise. The machine list of Plant A still shows "Sprayer 1 — section Paint", and the section filter of Plant B's machine list finds a machine of Plant A.
**Rules affected:** `update_factory_section` R10
**Answer:** bug — a section that has machine assignments cannot be moved to another factory: 400 `Cannot move a section that has machines assigned`, nothing written. Any assignment row of the section in the workspace counts (also of a soft-deleted machine, since it comes back when the machine is restored). Renaming without a move is not affected. (Alternatives offered and not taken: `intended`, a move carrying the machines along; `bug — the move unassigns those machines`, a cascade conflicting with standing decision 2.)
**Resolution:** 🐞 BUG-928 (pattern `move-ignores-dependents`, new) — decided by Claude under the reviewer's delegation (2026-10-16): the suggested answer is accepted. Rules: `update_factory_section` R10.

## Follow-ups for other reviews
> Nothing below is a rule of this manager and no bug is logged for it here except where an ID is given. Whoever describes the named module must read this list first.

| # | Where it must be looked at | What | Came from |
|---|---|---|---|
| FU-1 | **Factory section DAO** (`app/dao/factory_section.py`, APPROVED) — at the time of the fixes | BUG-917, BUG-918, BUG-920, BUG-924 need queries the DAO does not have: a workspace-wide list that filters deleted sections and sections of deleted factories, searches (escaped, HR-8) and orders (name case-insensitive, `id`) **before** paging; and, after BUG-905, a way for the manager's `include_deleted=True` to still get deleted sections (section DAO FU-2 (g)). BUG-911 needs an existence check over all live sections of a factory (not a capped list). Each new DAO method gets its own rules then. | HR lines, P4 |
| FU-2 | **"Restore section" feature** (section DAO FU-1) | The future manager method must also: compare the name the BUG-912 way (normalised) when refusing a taken name; respect Q1 / Q2 (a section of a deleted factory); and, after BUG-908, rely on the kept assignment rows (no re-assigning). | BUG-908, BUG-912, Q1 |
| FU-3 | **Factory section service / endpoint** (`app/services/factory_section_service.py`, `app/api/v1/endpoints/factory_sections.py`, `FactorySectionResponse`) | Exposing `include_deleted` on the list and on get-by-id (BUG-920, BUG-916); `FactorySectionResponse` has only `id`, `name`, `factory_id` — no `is_deleted`. The service's commit / rollback and its `db.refresh` after each write. | HR-4 lines |
| FU-4 | **Machine manager** (`app/managers/machine_manager.py`) | After BUG-908 a machine of a deleted section keeps its link; machine edit then re-sends a deleted section id → 400 from the assignment manager (`set_assignment` R7). Whether the machine form must show / clear it is to be looked at there. After the BUG-928 fix (Q3, accepted) no cross-factory link can be created by a section move. | BUG-908, Q3 |
| FU-5 | **Dead-code list** | No new entry. The existing entry for `MachineSectionAssignmentManager.clear_for_section` already says to drop the import `factory_section_manager.py:13-15` with the BUG-908 fix. | BUG-908 |

## Overview
`FactorySectionManager` owns factory sections — the named areas of a factory ("Cutting", "Paint") that machines can optionally be put into. It is called only by `FactorySectionService` (which commits / rolls back and refreshes the row) behind `/factory-sections/`. It is meant to protect: workspace isolation (a section, and the factory it is put in, must belong to the caller's workspace); one live section per name in a factory; no section written into a soft-deleted factory; and soft-delete semantics (a deleted section cannot be edited or deleted again and is hidden from the list). The manager never commits; the DAOs flush. It has no restore method. Today its delete also erases the section's machine assignments through `MachineSectionAssignmentManager.clear_for_section` (BUG-908 — to go).

**Callables:** 6 specified · 2 not specified
**Externals to mock:** `utcnow` (patch `app.dao.factory_section.utcnow`; used for `deleted_at` only)
**Integration-only behavior:** the bounds on `GET /factory-sections/` (`skip >= 0`, `1 <= limit <= 1000`); exposing `include_deleted` through the service and endpoint (BUG-920, BUG-916 — FU-3); the 422 a schema `ValidationError` becomes at the API; the service's commit / rollback.

**Facts for the test designer**
- Import: `from app.managers.factory_section_manager import FactorySectionManager, factory_section_manager`. `FactorySectionManager()` takes no arguments; the module instance holds no per-call state. All parameters are positional-or-keyword (none keyword-only); the service calls `get_factory_section(db, section_id, workspace_id)` positionally and the others by keyword.
- `HTTPException` is `fastapi.HTTPException`; assert `.status_code` and `.detail` (a plain string).
- Table `factory_sections` (class `app.models.factory_section.FactorySection`): columns, defaults and constraint names in the section DAO spec, **Model facts** (`tests/unit/dao/factory_section.spec.md`). No unique index (verified again). Soft delete = `is_deleted = True` + `deleted_at` + `deleted_by`; `is_active` is never written by this manager.
- Schemas (`app/schemas/factory_section.py`): `FactorySectionCreate` = `name: str`, `factory_id: int` (both required); `FactorySectionUpdate` = `name: str | None = None`, `factory_id: int | None = None`. No validators today; unknown fields (e.g. `workspace_id`) are ignored.
- The section is read with the generic `factory_section_dao.get_by_id_and_workspace` (id **and** workspace; soft-deleted sections **are** returned). The factory is read with `factory_dao.get_by_id_and_workspace` (same; soft-deleted factories returned — factory DAO spec).
- `Factory` needs `workspace_id`, `name`, `abbreviation`; `Machine` needs `workspace_id`, `name`, `factory_id`; `MachineSectionAssignment` needs `workspace_id`, `machine_id`, `factory_section_id` (unique per machine).

**Notes for the test designer**
- Workspaces and profiles from `tests/unit/factories.py` (`make_workspace`, `make_profile`). Build `Factory`, `FactorySection`, `Machine`, `MachineSectionAssignment` rows directly (add + flush). `autoflush=False`: flush before calling the manager. For 100+ rows use a bulk `insert(FactorySection)` with `is_active=True, is_deleted=…` set explicitly.
- After a write, `db.refresh(section)` before asserting database-set columns. For "nothing written" cases (HR-9, BUG-919) `db.refresh(section)` after building it, so `updated_at` starts loaded as `None`.
- `updated_at`: assert `None` → not `None` (or unchanged), never "later than". `deleted_at` is compared with the mocked `utcnow` value (a naive `datetime`).
- **Refusals (404 / 400 / 409)** happen before anything is written: no savepoint needed. **Database errors** (foreign key, negative `limit` / `skip`, the intended unique index) abort the transaction: wrap the call in `with db.begin_nested():` inside `pytest.raises(...)`.
- **Database-level 409 (BUG-913, `create_factory_section` R9, `update_factory_section` R15):** simulate a concurrent request by patching `FactorySectionManager._check_name_exists_in_factory` to return `False`; wrap the call in `db.begin_nested()` inside `pytest.raises(HTTPException)`. A direct duplicate insert that violates the intended index raises `IntegrityError` on flush.
- **At most one live row per normalised name per factory** once BUG-913 is fixed: setups needing two such rows make all but one soft-deleted, or put them in different factories. Cases not about duplicates use distinct names.
- **Row order is not deterministic (standing decision 7).** Order cases (BUG-918 / BUG-903) are written to the intended order and marked **non-strict** xfail. Every other list case compares **sets** of ids or counts.
- **Cap and page cases (BUG-911, BUG-917) depend on which rows the database puts first** → **non-strict** xfail. Recipe: 100 soft-deleted sections of the factory inserted first, then one live "Late" (observed today: the check answers `False`, a second "Late" is created; the default list and `search="late"` give `[]`, `skip=100` shows it). For the factory list and the check this recipe also passes once BUG-905 alone is fixed — add a second case with 101 *live* sections ("s000"…"s099", then "Late") for the cap of BUG-911. The workspace-wide list (no factory) is not touched by BUG-905.
- **Strict xfail** (outcome does not depend on row order, as long as fewer than 100 rows are involved): BUG-912, BUG-914, BUG-915, BUG-916, BUG-919, BUG-921, BUG-922, BUG-923, BUG-924, BUG-925, BUG-926, BUG-927, BUG-928, BUG-908 (assignment rows still there after the delete).
- **Schema rejections (BUG-915):** assert `pydantic.ValidationError` when constructing `FactorySectionCreate` / `FactorySectionUpdate`; the manager is never reached.
- **Soft-deleted factory fixtures:** `is_deleted=True, deleted_at=<fixed naive datetime>, deleted_by=<existing profile id>`, `is_active=True`; the section inside is live. An "inactive but live" factory is `is_active=False, is_deleted=False`.
- **BUG-908:** assert on a fresh `SELECT` of `machine_section_assignments` rows of the section, not on `machine.section_assignment` (cached). For R5b read `machine.factory_section_id` once before the call.
- HR-10 does not apply: no lock rule, no lock case.

## Not specified
- `FactorySectionManager.__init__` — stores the model and the two DAOs, no logic
- `factory_section_manager` — module-level singleton, no logic

The checklist (`docs/testing/unit-test-checklist-by-layer.md`) marks nothing of this file as possibly unused; every method has a caller in `FactorySectionService`. No legacy test outside `tests/unit/` calls this manager. No new dead-code entry (FU-5).

---

## `FactorySectionManager.create_factory_section(session, section_data, workspace_id, user_id)`
**Shape:** create
**Persistence:** writes
**Visibility:** public (used by: `FactorySectionService.create_factory_section` ← `POST /factory-sections/`)

**Purpose:** Create a section in a live factory of the workspace, refusing a name already used by a live section of that factory.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `session` | `Session` | open session; not committed here |
| `section_data` | `FactorySectionCreate` | `name` (intended: trimmed, at least 1 character — BUG-915; today anything), `factory_id` (must be a factory of the workspace) |
| `workspace_id` | int | caller's workspace; the factory must belong to it |
| `user_id` | int | creator; stored as `created_by` (FK `profiles.id`) |

**Returns:** the new `FactorySection`, flushed (has an `id`), not committed.

**Rules:**
- **R1.** Given a live factory of the workspace and a name not used by a live section of that factory, one section is created with `name`, `factory_id` as received, `workspace_id` = the argument and `created_by = user_id`.
- **R2.** The new row has `is_active = True`, `is_deleted = False`, `created_at` set by the database, and `updated_at`, `updated_by`, `deleted_at`, `deleted_by` all `None`.
- **R3.** No factory with `factory_id` (also `0` and negative ids), or a factory of another workspace → 404 `Factory with ID <factory_id> not found`; nothing created. (An unknown `workspace_id` therefore also ends here — the factory is never found.)
- **R4.** The factory is soft-deleted → 400 `Cannot create section for deleted factory`; nothing created. Checked before the name: a taken name in a deleted factory still gets this 400.
- **R5.** A factory that is live but `is_active = False` is accepted like an active one.
- **R6.** A live section of the same factory already has the name → 409 `Section with name '<name>' already exists in this factory` (`<name>` = the submitted value as received by the manager, i.e. trimmed once BUG-915 is fixed); nothing created. Detection follows `_check_name_exists_in_factory` R1–R7.
- **R7.** The same name in another factory (same workspace), in a soft-deleted section of the same factory, or in another workspace does not block the create.
- **R8.** [BUG-915] [HR-1] The name is stored with leading / trailing whitespace removed (`"  Paint "` → `"Paint"`; inner whitespace and case kept); a blank or whitespace-only name (`""`, `"   "`, `"\t"`) is rejected by `FactorySectionCreate` itself — `ValidationError` (422 at the API); nothing created. *(Today: stored as typed; `""` and `"   "` are created.)*
- **R9.** [BUG-913] [HR-2] The database refuses a second live section with the same normalised name (lower-case of the trimmed name) in one factory: a direct insert fails with `IntegrityError`, while a soft-deleted row or a row of another factory with that name is accepted. When such a duplicate reaches the insert through the manager (the Python check passed, e.g. a concurrent request), 409 `Section with name '<name>' already exists in this factory` is raised — not a database error — and nothing is created. *(Today: no index; the duplicate is saved.)*
- **R10.** A `user_id` that is not an existing profile → the flush fails with `IntegrityError` (`ForeignKeyViolation`, `factory_sections_created_by_fkey`); nothing saved.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| factory missing / other workspace | `HTTPException` 404 | `Factory with ID <factory_id> not found` |
| factory soft-deleted | `HTTPException` 400 | `Cannot create section for deleted factory` |
| name used by a live section of the factory | `HTTPException` 409 | `Section with name '<name>' already exists in this factory` — also for the database-level violation [BUG-913] |
| blank name [BUG-915] | Pydantic `ValidationError` building `FactorySectionCreate` | not asserted |
| unknown `user_id` | `sqlalchemy.exc.IntegrityError` / `ForeignKeyViolation` | — |

**Side effects:** one `factory_sections` row inserted and flushed. No commit. Nothing on any error.

---

## `FactorySectionManager.update_factory_section(session, section_id, section_data, workspace_id, user_id)`
**Shape:** update
**Persistence:** writes
**Visibility:** public (used by: `FactorySectionService.update_factory_section` ← `PUT /factory-sections/{id}/`)

**Purpose:** Rename a live section and / or move it to another live factory of the workspace, and record who edited it.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `session` | `Session` | open session; not committed here |
| `section_id` | int | section to change |
| `section_data` | `FactorySectionUpdate` | `name`, `factory_id`: optional, `None` by default; `None` / omitted = keep |
| `workspace_id` | int | caller's workspace; section and target factory must belong to it |
| `user_id` | int | editor; stored as `updated_by` (FK `profiles.id`) |

**Returns:** the same `FactorySection` instance, modified and flushed, not committed.

**Rules:**
- **R1.** No section with that id → 404 `Factory section with ID <section_id> not found`.
- **R2.** A section of another workspace → the same 404; it is not changed.
- **R3.** The section is soft-deleted → 400 `Cannot update deleted factory section`, whatever the request (also when the name is taken or the target factory is deleted — this 400 comes first); nothing changes.
- **R3a.** [BUG-926] (Q1) The section's current factory is soft-deleted → 400 `Cannot update deleted factory section`, whatever the request (rename, the same `factory_id`, a move to a live factory); nothing changes. Checked right after R3. A live but inactive factory is not refused. *(Today: not checked — the rename, the same-factory update and the move out all succeed.)*
- **R4.** Given a `name` that differs from the current one and is not used by another live section of the resulting factory, the name is changed. A field not sent (or `null`) keeps its value (R11).
- **R5.** Given a `name` equal to the current name and no move, no duplicate check is made. Changing only the case of the section's own name (`"Polish"` → `"POLISH"`) succeeds — the section never conflicts with itself, today and after BUG-912.
- **R6.** Given a different `name` used by another live section of the resulting factory (the target when moving, else the current one) → 409 `Section with name '<name>' already exists in this factory` (submitted value); nothing changes — a `factory_id` sent in the same call is not applied. Detection follows `_check_name_exists_in_factory` R1–R7 with the section itself excluded. A name used only in the section's *old* factory does not block a move with that new name.
- **R7.** Given a `factory_id` different from the current one, the target factory is checked: missing (also negative ids) or of another workspace → 404 `Factory with ID <factory_id> not found`; nothing changes. A live but inactive target factory is accepted.
- **R8.** The target factory is soft-deleted → 400 `Cannot move section to deleted factory` (before the name check; also when the name is taken there); nothing changes.
- **R8a.** [BUG-923] (P3) `factory_id=0` is checked like any other id → 404 `Factory with ID 0 not found`; nothing changes. *(Today: `0` skips the check and is written; the flush fails with `IntegrityError` / `ForeignKeyViolation` `factory_sections_factory_id_fkey` — a 500 at the API.)*
- **R9.** [BUG-914] [HR-2] Whenever the section moves to another factory, its resulting name (the new one if sent, else the current one) is checked against the live sections of the target factory: moving "Cut" into a factory that has a live "Cut" → 409 `Section with name 'Cut' already exists in this factory`, nothing changes — both when no `name` is sent and when the current name is re-sent. *(Today: a move without a *different* name is never checked; the target ends with two live "Cut".)*
- **R10.** [BUG-928] (Q3) A move to another factory is refused while any machine-assignment row of the workspace points at the section → 400 `Cannot move a section that has machines assigned`; nothing changes. Checked after R7 / R8, before R9. A rename without a move is not affected; a section without assignments moves normally. *(Today: the move succeeds and the assignment rows are kept, so a machine of the old factory is linked to a section of the new one.)*
- **R11.** `name` / `factory_id` omitted or `null` are left unchanged (both columns are mandatory: `null` never clears). A `factory_id` equal to the current one is not checked and changes nothing.
- **R12.** [BUG-915] [HR-1] A sent name is stored trimmed (`" Cut "` → `"Cut"`; `" Cut "` sent to a section named `"Cut"` is "equal to the current name", R5); a blank or whitespace-only name is rejected by `FactorySectionUpdate` itself (`ValidationError`), nothing changes. *(Today: stored as typed; `""` skips the duplicate check and is written.)*
- **R13.** [BUG-919] [HR-9] `updated_by` is set to `user_id` only when the call actually changes the name or the factory. Given `{}`, only `null` fields, or values equal to the current ones, the call succeeds, returns the section, and `updated_by` / `updated_at` keep their values (including `None`). *(Today: `updated_by` is set on every successful call, and `updated_at` with it.)*
- **R14.** On a real change the database sets `updated_at`. Nothing else is modified: `workspace_id`, `created_by`, `created_at`, `is_active`, `is_deleted`, `deleted_at`, `deleted_by` keep their values; other sections, the factories and the machine-assignment rows are not written.
- **R15.** [BUG-913] [HR-2] A rename or move that would create a second live section with the same normalised name in a factory and reaches the flush (Python check passed, e.g. concurrently) → 409 `Section with name '<name>' already exists in this factory` (for a move without a new name, `<name>` is the current name), not a database error; nothing changes. *(Today: no index; saved.)*
- **R16.** The name of a soft-deleted section, of a section of another factory (without moving there), or of another workspace can be taken by a rename.
- **R17.** A `user_id` that is not an existing profile (with a change that stamps it) → `IntegrityError` (`ForeignKeyViolation`, `factory_sections_updated_by_fkey`); nothing saved.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| section missing / other workspace | `HTTPException` 404 | `Factory section with ID <section_id> not found` |
| section soft-deleted; [BUG-926] its factory soft-deleted | `HTTPException` 400 | `Cannot update deleted factory section` |
| target factory missing / other workspace / [BUG-923] `0` | `HTTPException` 404 | `Factory with ID <factory_id> not found` |
| target factory soft-deleted | `HTTPException` 400 | `Cannot move section to deleted factory` |
| [BUG-928] move of a section with assignments | `HTTPException` 400 | `Cannot move a section that has machines assigned` |
| resulting name used in the resulting factory ([BUG-914] also on a plain move; [BUG-913] database level) | `HTTPException` 409 | `Section with name '<name>' already exists in this factory` |
| blank name [BUG-915] | `ValidationError` building `FactorySectionUpdate` | not asserted |
| unknown `user_id` | `IntegrityError` / `ForeignKeyViolation` | — |

**Side effects:** on a real change: `name` and / or `factory_id`, `updated_by` (and `updated_at` by the database), flushed. On a no-op: nothing (intended, BUG-919). No commit. Nothing on any error.

---

## `FactorySectionManager.get_factory_section(session, section_id, workspace_id, include_deleted=False)`
**Shape:** get-or-404
**Persistence:** reads
**Visibility:** public (used by: `FactorySectionService.get_factory_section` ← `GET /factory-sections/{id}/`)

**Purpose:** Fetch one visible section of the caller's workspace by id.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `session` | `Session` | open session |
| `section_id` | int | section to fetch |
| `workspace_id` | int | caller's workspace |
| `include_deleted` | bool, default `False` | *(requires new parameter — BUG-916)* `True` also returns a soft-deleted section and a section of a soft-deleted factory. Today the parameter does not exist (`TypeError`). |

**Returns:** the `FactorySection`.

**Rules:**
- **R1.** A live section of the workspace in a live factory is returned; `is_active` (of the section or the factory) is not consulted.
- **R2.** No section with that id, or a section of another workspace → 404 `Factory section with ID <section_id> not found`.
- **R3.** [BUG-916] [HR-4] A soft-deleted section → 404 with the same message by default. *(Today: returned.)*
- **R4.** [BUG-916] With `include_deleted=True` a soft-deleted section of the workspace is returned; another workspace still gives 404. *(Requires the new parameter.)*
- **R5.** [BUG-925] (P5) A live section whose factory is soft-deleted → 404 with the same message by default; returned with `include_deleted=True`. A live but inactive factory hides nothing. *(Today: returned.)*

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| missing / other workspace / hidden (R3, R5) without `include_deleted` | `HTTPException` 404 | `Factory section with ID <section_id> not found` |

**Side effects:** none

---

## `FactorySectionManager.search_factory_sections(session, workspace_id, factory_id=None, search=None, skip=0, limit=100, include_deleted=False)`
**Shape:** search
**Persistence:** reads
**Visibility:** public (used by: `FactorySectionService.get_factory_sections` ← `GET /factory-sections/`, which passes `factory_id`, `search`, `skip`, `limit` and never `include_deleted`; the endpoint enforces `skip >= 0`, `1 <= limit <= 1000`, any integer `factory_id`)

**Purpose:** One page of the workspace's sections, optionally of one factory and filtered by a text in the name.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `session` | `Session` | open session |
| `workspace_id` | int | workspace to list |
| `factory_id` | int or `None` | `None` = all factories; otherwise only that factory (today `0` also means "all" — R2a) |
| `search` | str or `None` | text looked for in the name; `None` / `""` = no filter |
| `skip`, `limit` | int, defaults `0`, `100` | paging; not validated here |
| `include_deleted` | bool, default `False` | `True` keeps what deletion hides; never passed by the API (R6) |

**Returns:** a `list` of `FactorySection` (possibly empty).

**Rules:**
- **R1.** Only sections with the section's own `workspace_id` equal to the argument are returned; an unknown workspace gives `[]`. A section's `is_active` is not consulted.
- **R2.** Given a `factory_id`, only sections of that factory are returned; an unknown factory, a negative id, or a factory of another workspace gives `[]`.
- **R2a.** [BUG-922] (P2) `factory_id=0` filters like any id and gives `[]`. *(Today: treated as "no factory" — the whole workspace is listed.)*
- **R3.** [BUG-917] [HR-5] All filters (R2, R5, R7, R8, R9) are applied to the whole scope first; then `skip` matches are skipped and at most `limit` returned. A page is short only when there are no more matches, and a search finds a match wherever it is. *(Today: one page of `limit` rows — deleted rows and non-matching rows included — is loaded first and filtered afterwards. Observed with 100 soft-deleted sections created first and one live "Late": the default list and `search="late"` gave `[]`, `skip=100` gave it — order-dependent. For a list of one factory the deleted part also goes away with BUG-905.)*
- **R4.** [BUG-918] (no factory) / [BUG-903] (one factory) [HR-6] Results are ordered by name case-insensitively ascending, then `id` ascending, before `skip` / `limit`; with `include_deleted=True` deleted and live sections are ordered together. *(Today: no order is requested; not specified.)*
- **R5.** [BUG-917] With `include_deleted=False` (default) soft-deleted sections are never returned and never take a place in the page. *(Today: removed only after the page was cut.)*
- **R6.** [BUG-920] [HR-4] With `include_deleted=True` soft-deleted sections are returned along with live ones — the manager does so today; the option must become reachable from `GET /factory-sections/` (service / endpoint fix — integration-only). After BUG-905 the factory branch needs a DAO lookup that still returns them (FU-1). *(Today: never passed by the API.)*
- **R7.** [BUG-924] (no factory) / [BUG-904] (one factory) (P4, standing decision 2) With `include_deleted=False`, a section whose factory is soft-deleted is not returned and takes no place in the page, with or without a factory filter; with `include_deleted=True` it is returned. The section rows are never changed: once the factory is no longer deleted they are listed again. A live but inactive factory hides nothing. *(Today: listed in both branches.)*
- **R8.** Given a non-blank `search`, a section matches when the text is a case-insensitive substring of its **name** (`"HALL"` finds "Main Hall" and "hidden hall"); the factory's name is not searched. Inner whitespace of the text is significant. (Holds today within the loaded page — the whole-scope part is R3.)
- **R8a.** (HR-8) The text is literal: `"%"` returns only sections whose name contains `%`; `"_"` only names containing `_`. *(Holds today; must keep holding when BUG-917 moves the search into SQL.)*
- **R9.** [BUG-921] (P1) `None`, `""` and whitespace-only `search` apply no search filter; otherwise leading / trailing whitespace (`str.strip()`) is removed before matching: `" hall "` finds "Main Hall". *(Today: `None` and `""` apply no filter; the text is used untrimmed — `" hall "` and `"   "` return `[]` when no name contains them.)*
- **R10.** `search` combines with the deleted filter: a matching soft-deleted section is returned only with `include_deleted=True`.
- **R11.** No sections, no match, or `skip` at / past the number of matches → `[]`; `limit=0` → `[]`. Defaults `skip=0`, `limit=100`: given 101 live sections (one factory, or the workspace), exactly 100 are returned. A negative `limit` or `skip` makes Postgres reject the query, on both branches (see Errors).

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| negative `limit` | `sqlalchemy.exc.DataError`; `.orig` is `psycopg2.errors.InvalidRowCountInLimitClause` | `LIMIT must not be negative` |
| negative `skip` | `sqlalchemy.exc.DataError`; `.orig` is `psycopg2.errors.InvalidRowCountInResultOffsetClause` | `OFFSET must not be negative` |

**Side effects:** none

---

## `FactorySectionManager.delete_factory_section(session, section_id, workspace_id, user_id)`
**Shape:** soft-delete
**Persistence:** writes
**Visibility:** public (used by: `FactorySectionService.delete_factory_section` ← `DELETE /factory-sections/{id}/`, which answers 200 with the section)

**Purpose:** Soft-delete a live section of the workspace, leaving its machine assignments in place (hidden with it).

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `session` | `Session` | open session; not committed here |
| `section_id` | int | section to delete |
| `workspace_id` | int | caller's workspace |
| `user_id` | int | deleter; stored as `deleted_by` (FK `profiles.id`) |

**Returns:** the same `FactorySection` instance, soft-deleted and flushed, not committed.

**Rules:**
- **R1.** No section with that id, or a section of another workspace → 404 `Factory section with ID <section_id> not found`; nothing changes.
- **R2.** Already soft-deleted → 400 `Factory section is already deleted`; its `deleted_at` / `deleted_by` stay as they were.
- **R3.** Given a live section, it gets `is_deleted = True`, `deleted_at = utcnow()` (naive UTC) and `deleted_by = user_id`; the returned object is the instance read.
- **R4.** Nothing else on the row changes: `name`, `factory_id`, `workspace_id`, `created_by`, `created_at`, `updated_by` keep their values and `is_active` stays as it was. `updated_at` becomes non-null (database).
- **R5.** [BUG-908] (standing decision 3) The section's machine-assignment rows are kept: after the delete every assignment row that pointed at the section still exists, unchanged (same `id`, `machine_id`, `created_by`), however many there are. Machines, their factory and other sections are not written. *(Today: every assignment row of the section in the workspace is deleted — at most 10 000 (BUG-907), in no defined order (BUG-906); verified: a section's two assignments gone, another section's kept.)*
- **R5a.** [BUG-908] After the delete the machines that were in the section are hidden as its members (machine DAO `get_by_section` R4, BUG-889) and are in it again, unchanged, once the section is restored (section DAO `restore` R7). *(Today: the section DAO's `restore` brings back an empty section — verified.)*
- **R5b.** [BUG-908] A machine whose section was read before the call is not touched in memory: its `factory_section_id` still gives the section's id after the delete (its link still exists). *(Today: the manager refreshes it and it reads `None`, because its link was deleted.)*
- **R6.** Nothing that belongs to the section blocks the delete: a section with assigned machines is deleted like an empty one.
- **R7.** After the delete, in the same session: the section is not listed by `search_factory_sections` by default (R5 there — BUG-917 for the paging part), is listed with `include_deleted=True`; its name can be used by a new section of the factory (`create_factory_section` R7); `update_factory_section` answers 400 (R3 there); a second delete answers 400 (R2); `get_factory_section` follows its R3 / R4.
- **R8.** The change is flushed, not committed: rolling back a savepoint around the call makes the section live again (and today brings the erased assignment rows back).
- **R9.** A `user_id` that is not an existing profile → `IntegrityError` (`ForeignKeyViolation`, `factory_sections_deleted_by_fkey`); the section stays live with an empty deletion stamp.
- **R10.** [BUG-927] (Q2) A live section whose factory is soft-deleted → 400 `Cannot delete a section of a deleted factory`; nothing written. Checked after R2. A live but inactive factory is not refused. *(Today: deleted normally.)*

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| missing / other workspace | `HTTPException` 404 | `Factory section with ID <section_id> not found` |
| already soft-deleted | `HTTPException` 400 | `Factory section is already deleted` |
| [BUG-927] its factory soft-deleted | `HTTPException` 400 | `Cannot delete a section of a deleted factory` |
| unknown `user_id` | `IntegrityError` / `ForeignKeyViolation` | — |

**Side effects:** one `factory_sections` row updated (`is_deleted`, `deleted_at`, `deleted_by`; `updated_at` by the database), flushed. Intended: no other table written (BUG-908). Today: also up to 10 000 `machine_section_assignments` rows deleted and the affected machines' `section_assignment` expired. No commit.

---

## `FactorySectionManager._check_name_exists_in_factory(session, workspace_id, factory_id, name, exclude_id=None)`
**Shape:** validator
**Persistence:** reads
**Visibility:** internal (used by: `create_factory_section` without `exclude_id`; `update_factory_section` with `exclude_id` = the section being edited)

**Purpose:** Tell whether a live section of a factory already uses a name.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `session` | `Session` | open session |
| `workspace_id` | int | equality on the sections' own `workspace_id` |
| `factory_id` | int | factory to look in |
| `name` | str | name to look for |
| `exclude_id` | int or `None` | section id to ignore; `None` = none |

**Returns:** `True` if a matching live section exists, else `False`. Never raises.

**Rules:**
- **R1.** A live section of the factory (and workspace) whose name equals `name` in the sense of R4 → `True`.
- **R2.** Sections of another factory, or of another workspace, are not considered → `False`.
- **R3.** A soft-deleted section with that name is ignored → `False` (unless a live one matches too).
- **R4.** [BUG-912] [HR-2] Names match regardless of case and of leading / trailing whitespace (`str.strip()`): with a live "Paint", each of `"paint"`, `"PAINT"`, `" Paint "`, `"Paint\n"` → `True`; `"Pa int"`, `"Paint 2"` → `False`. *(Today: exact comparison — only `"Paint"` → `True`.)*
- **R5.** [BUG-911] [HR-2] Every live section of the factory is examined, however many sections (live or deleted) it has. *(Today: only the first 100 sections of the factory — deleted ones included, in no defined order — are examined; a match outside them → `False`. See Notes for the test designer.)*
- **R6.** Given `exclude_id`, the section with that id is ignored even when its name matches (→ `False` if it is the only match); any other matching live section still gives `True`. `exclude_id=None` ignores nothing.
- **R7.** A factory with no sections → `False`.

(Callers never reach it for a soft-deleted factory: create refuses one (R4 there), update refuses a move into one (R8) and — per Q1 — an update of a section inside one (R3a). Its answer for a soft-deleted factory is not specified and not tested; after BUG-904 the DAO lookup it uses returns nothing for such a factory.)

**Errors:** none

**Side effects:** none

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 13–15, 298–300 | import / call of the assignment manager (BUG-908; removed with the fix — FU-5) | `delete_factory_section` R5, R5a, R5b |
| 28–31 | `__init__` | Not specified |
| 56–58 / `dao/factory.py` 56–63 | factory lookup by id AND workspace; no `is_deleted` filter | `create_factory_section` R3, R4 |
| 59–63 | factory not found (missing / other workspace / `0` / unknown workspace) → 404 | `create_factory_section` R3 |
| 66–70 | factory deleted → 400 (before name check); `is_active` not checked | `create_factory_section` R4, R5 |
| 73–83 | name exists → 409 / free → continue | `create_factory_section` R6, R7 |
| 86–91 / `dao/base.py` 76–84 | dump (`name`, `factory_id`) + `workspace_id`, `created_by`; no trim; insert, flush; no unique index | `create_factory_section` R1, R2, R8, R9, R10 |
| 118–125 / `dao/base.py` 187–195 | section lookup (raw) → 404 | `update_factory_section` R1, R2 |
| 128–132 | section deleted → 400 (first) | `update_factory_section` R3 |
| — (no check) | section's current factory deleted | `update_factory_section` R3a |
| 135 | `factory_id` truthy and different → validate / `None`, `0`, same → skip | `update_factory_section` R7, R8a, R11 |
| 136–143 | target factory not found → 404 | `update_factory_section` R7 |
| 145–149 | target factory deleted → 400; `is_active` not checked | `update_factory_section` R8, R7 |
| — (no check) | assignments of a moved section | `update_factory_section` R10 |
| 152 | target = sent `factory_id` if truthy, else current | `update_factory_section` R6, R9 |
| 153 | `name` truthy and different → check / else skip (`None`, `""`, same name — also on a move) | `update_factory_section` R4, R5, R9, R11, R12 |
| 154–165 | name exists in target (self excluded) → 409 | `update_factory_section` R6 |
| 168 | `exclude_unset` + `exclude_none`: omitted / `null` dropped; `""` and `0` kept | `update_factory_section` R8a, R11, R12 |
| 169 | `updated_by` always set | `update_factory_section` R13 |
| 171 / `dao/base.py` 108–119 | dict update, add, flush (FK errors) | `update_factory_section` R4, R14, R15, R16, R17 |
| 194–204 | raw lookup → 404 / found → returned (deleted, factory deleted included) | `get_factory_section` R1–R5 |
| 210–214 | defaults `factory_id=None`, `search=None`, `skip=0`, `limit=100`, `include_deleted=False` | `search_factory_sections` R5, R9, R11 |
| 231 | `factory_id` truthy → by factory / `None`, `0` → workspace | `search_factory_sections` R2, R2a |
| 233–235 / `dao/factory_section.py` 36–43 | by factory: workspace + factory filter, page, no order (BUG-903), deleted and deleted-factory rows included (BUG-905, BUG-904); negative values | `search_factory_sections` R2, R3, R4, R5, R7, R11, Errors |
| 238–240 / `dao/base.py` 161–167 | workspace: filter, page, no order (BUG-100 / BUG-918), no deleted / factory filter | `search_factory_sections` R1, R3, R4, R5, R7, R11, Errors |
| 243–244 | `include_deleted` false → drop deleted after paging / true → keep | `search_factory_sections` R3, R5, R6, R10 |
| 247–252 | `search` truthy → lower-cased substring of name, untrimmed, literal / `None`, `""` → none | `search_factory_sections` R8, R8a, R9, R10 |
| 244, 249 | comprehensions over empty / one / many | `search_factory_sections` R11 |
| 278–286 | section lookup (raw) → 404 | `delete_factory_section` R1 |
| 289–293 | already deleted → 400 | `delete_factory_section` R2 |
| — (no check) | section's factory deleted | `delete_factory_section` R10 |
| 297 / `dao/factory_section.py` 60–65 | three fields set, `utcnow()`, flush (FK), same instance, `is_active` untouched | `delete_factory_section` R3, R4, R7, R8, R9 |
| 298–300 / assignment manager 57–64 / assignment DAO 64–69 | assignment rows deleted (cap 10 000, no order), loaded machines expired | `delete_factory_section` R5, R5a, R5b, R6 |
| 301 | return the section | `delete_factory_section` R3 |
| 326–328 / `dao/factory_section.py` 20–43 | `get_by_factory` with defaults: first 100 rows, deleted included, unordered | `_check_name_exists_in_factory` R2, R5 |
| 329 | loop over empty / one / many | `_check_name_exists_in_factory` R1, R7 |
| 331–332 | deleted → `continue` | `_check_name_exists_in_factory` R3 |
| 333 | exact `==`; `exclude_id is None` / `section.id != exclude_id` | `_check_name_exists_in_factory` R1, R4, R6 |
| 334–335 | `True` on first match / `False` after loop | `_check_name_exists_in_factory` R1, R7 |
| 339 | module singleton | Not specified |
