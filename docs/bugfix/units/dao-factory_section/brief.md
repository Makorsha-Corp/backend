# Fix brief: dao-factory_section

## 1. Unit

| | |
|---|---|
| Slug | `dao-factory_section` |
| Source files | `app/dao/factory_section.py` (the fix) and `app/managers/factory_section_manager.py` (one pass-through change only, see §5) — **two-file unit** |
| Worktree | `E:\Projects\Makorsh-Corp\bugfix-worktrees\dao-factory_section` |
| Branch | `bugfix/dao-factory_section` (from `origin/main`) |
| Risk | `normal` (BUG-903 is a trivial-list pattern; BUG-904 `join-ignores-soft-deleted` and BUG-905 `get-returns-soft-deleted` are not on the list) |

All three bugs are in one method, `DAOFactorySection.get_by_factory`.

**Why the manager is in scope (re-scoped 2026-11-27, decided by Claude under the reviewer's delegation):** `FactorySectionManager.search_factory_sections` has an `include_deleted` option. In its factory branch it calls `get_by_factory` and drops deleted sections itself afterwards, so with `include_deleted=True` it relies on `get_by_factory` still returning soft-deleted sections and sections of a soft-deleted factory. A DAO-only fix of BUG-904 / BUG-905 would break that option (manager rules R6 and R7 below). So `get_by_factory` gets an `include_deleted` keyword and the manager's factory branch passes its flag through.

## 2. Bugs

### BUG-903: Section list of a factory has no sort order
- **Pattern:** `unordered-pagination`
- **Where:** `DAOFactorySection.get_by_factory`; reached through `GET /factory-sections/?factory_id=…` and the section duplicate-name check.
- **Today:** No `ORDER BY`; the order is unspecified and paging with `skip` / `limit` can repeat or skip sections.
- **Intended:** Name case-insensitive ascending, then `id` ascending, before `skip` / `limit` (HR-6).

### BUG-904: Sections of a soft-deleted factory are still returned
- **Pattern:** `join-ignores-soft-deleted`
- **Where:** `DAOFactorySection.get_by_factory`; reached through `GET /factory-sections/?factory_id=…` and the section duplicate-name check.
- **Today:** The lookup never looks at the factory row: the live sections of a factory with `is_deleted = True` are returned.
- **Intended:** A section whose factory has `is_deleted = True` is hidden (not returned), by the factory's state alone; the section row is never deleted or altered, and it is returned again, unchanged, once the factory is no longer deleted; an inactive-but-live factory hides nothing (per the BUG-891 precedent for machines and the "hidden, not cascaded" decision of 2026-10-11; decided by Claude under the reviewer's delegation).
- **Example:** Factory 9 "Old Plant" is deleted while it still has the sections "Cutting" and "Paint". Asking for the sections of factory 9 must give nothing; restoring factory 9 brings both back untouched.

### BUG-905: Section list of a factory returns soft-deleted sections
- **Pattern:** `get-returns-soft-deleted`
- **Where:** `DAOFactorySection.get_by_factory`; reached through `GET /factory-sections/?factory_id=…` and the section duplicate-name check.
- **Today:** `is_deleted` is not looked at: deleted sections are returned like live ones and count toward `skip` / `limit` (100 deleted sections created first + 1 live one → the default call returns 100 rows, at least 99 deleted).
- **Intended:** Soft-deleted sections are never returned and never use up a place in the page (HR-4, scope "module-specific DAO query methods"; reviewer decision 2026-10-10 "soft-deleted things should not show up"; reading kept 2026-10-16, decided by Claude under the reviewer's delegation). The inherited raw lookups stay raw.

## 3. Intended behaviour (spec rules, copied)

### `DAOFactorySection.get_by_factory(db, *, factory_id, workspace_id, skip=0, limit=100, include_deleted=False)`
One page of the live sections of one factory of a workspace. Returns a `list` of `FactorySection` (possibly empty). Every parameter after `db` is keyword-only. `include_deleted` is new (keyword-only, `bool`, default `False`); every rule below describes the default unless it says otherwise.

Used by: `FactorySectionManager.search_factory_sections` when a factory is given, with the caller's `skip` / `limit` (← `GET /factory-sections/?factory_id=…`); `FactorySectionManager._check_name_exists_in_factory` with the defaults (← create / rename of a section).

- **R1.** Only sections with `workspace_id` and `factory_id` equal to the arguments are returned. A section of another factory of the same workspace, and a section of the same factory id asked for with another workspace id, are never returned.
- **R1a.** The workspace filter is on the **section's own** `workspace_id`; the workspace of the factory named by `factory_id` is never compared. Given a live section S of W1 whose `factory_id` is a live factory F9 of W2 (a row only a direct insert can produce; the manager checks the factory before creating), `get_by_factory(factory_id=F9.id, workspace_id=W1.id)` returns S, and `get_by_factory(factory_id=F9.id, workspace_id=W2.id)` returns `[]`. The same holds after the BUG-904 fix: the fix looks at the factory row only for its `is_deleted` (R3a), so S is still listed for W1 while F9 is live (hidden while F9 is soft-deleted) and is never listed for W2.
- **R2.** [BUG-905] (HR-4) Soft-deleted sections (`is_deleted = True`) are never returned and never use up a place in the page: given one live and one deleted section in the factory, only the live one is returned; given 100 deleted sections created first and one live section after them, the default call returns exactly that one. *(Today: `is_deleted` is not looked at.)*
- **R2a.** `is_active` is not consulted: a live section with `is_active = False` is returned.
- **R3.** An unknown factory id, `factory_id=0`, an unknown workspace id, or a factory with no sections returns `[]`.
- **R3a.** [BUG-904] When the factory itself is soft-deleted (`factories.is_deleted = True`), its sections are hidden: `[]` is returned even though it has live sections. They are hidden by the factory's state alone; nothing about the sections themselves says "deleted". *(Today: the factory row is never looked at.)*
- **R3b.** What surrounds R3a and holds today and after the fix: (1) the call changes nothing: the sections of a soft-deleted factory stay in the database exactly as they were (`is_deleted = False`, `is_active`, `deleted_at = None`, every other column unchanged); (2) a factory that is live but inactive (`is_active = False`, `is_deleted = False`) hides nothing: its live sections are returned; (3) once the factory is no longer deleted (`factories.is_deleted` back to `False`), its live sections are returned again, unchanged, with nothing done to the section rows.
- **R4.** The workspace and factory filters (and, after the fix, the deleted-section and deleted-factory filters) are applied before `skip` / `limit` (HR-5): sections of other factories and other workspaces never use up a place in the page. With defaults at most 100 sections are returned: given 101 live sections in the factory, exactly 100; with `limit=101` all 101.
- **R5.** `limit=0` returns `[]`; `skip` at or past the number of matching sections returns `[]`. A negative `limit` or `skip` makes Postgres reject the query: `sqlalchemy.exc.DataError` with pgcode `2201W` (`LIMIT must not be negative`) or `2201X` (`OFFSET must not be negative`).
- **R6.** [BUG-903] (HR-6) Sections are ordered by name case-insensitive ascending, then `id` ascending, before `skip` / `limit`, so consecutive windows (`skip=0, limit=2`, `skip=2, limit=2`, …) partition the factory's live sections with no repeats or gaps. Example: sections "Zulu", "bolt", "apple", "Bolt", "Banana", with "bolt" created before "Bolt", come back "apple", "Banana", "bolt", "Bolt", "Zulu". *(Today: no ordering is requested.)*
- **R7.** Each section appears exactly once, whether or not machines are assigned to it; nothing is written.
- **R8.** (new, for the manager's `include_deleted` option) With `include_deleted=True`, both deleted filters are skipped: soft-deleted sections of the factory **and** sections of a soft-deleted factory are returned along with the live ones. Everything else stays: the workspace and factory filters (R1, R1a), the order (R6: name case-insensitive ascending, then `id` ascending, deleted and live sections ordered together), paging after filtering (R4, R5), one row per section (R7).
- **How the factory's state is read:** the fix looks only at `factories.is_deleted`, never at the factory's `workspace_id` or `is_active` (R1a, R3b). The list is read in a single database query (a join or `EXISTS` on `factories`), not with a second read of the factory row.

### The rest of the file (must not change)
- `soft_delete(db, *, db_obj, deleted_by)`: sets `is_deleted = True`, `deleted_at = utcnow()` (naive UTC), `deleted_by`; leaves `is_active` and every other column alone; touches no machine, assignment row or factory; flushes, does not commit; returns the same instance.
- `restore(db, *, db_obj)`: sets `is_deleted = False`, `deleted_at = None`, `deleted_by = None`; no other column, no clock, no name check, no factory check; flushes, does not commit; returns the same instance. A section restored while its factory is still soft-deleted stays hidden from `get_by_factory` (R3a) until the factory is no longer deleted.
- The inherited generic methods (`get`, `get_by_id_and_workspace`, `get_by_workspace`, `create`, `update`) are not overridden and stay raw: they return soft-deleted sections and sections of soft-deleted factories.

### `FactorySectionManager.search_factory_sections(session, workspace_id, factory_id=None, search=None, skip=0, limit=100, include_deleted=False)` (manager; pass-through change only)
Used by `FactorySectionService.get_factory_sections` ← `GET /factory-sections/`, which passes `factory_id`, `search`, `skip`, `limit` and never `include_deleted`; the endpoint enforces `skip >= 0`, `1 <= limit <= 1000`, any integer `factory_id`. Returns one page of the workspace's sections, optionally of one factory and filtered by a text in the name.

**The only change allowed in this unit:** in the factory branch (`if factory_id:`), pass `include_deleted=include_deleted` to `get_by_factory`. Nothing else in the manager changes: the workspace branch, the Python filtering after the page, the search, `if factory_id:`, and `_check_name_exists_in_factory` (which keeps calling `get_by_factory` with the default, so it sees only live sections of a live factory).

All rules of the method, copied so you can see what must hold and what stays as today. Rules tagged with a bug other than BUG-903 / BUG-904 / BUG-905 are **other units' bugs**: they keep today's behaviour after this unit; do not fix them.
- **R1.** Only sections with the section's own `workspace_id` equal to the argument are returned; an unknown workspace gives `[]`. A section's `is_active` is not consulted.
- **R2.** Given a `factory_id`, only sections of that factory are returned; an unknown factory, a negative id, or a factory of another workspace gives `[]`.
- **R2a.** [BUG-922, not this unit] `factory_id=0` filters like any id and gives `[]`. *(Today: treated as "no factory": the whole workspace is listed.)*
- **R3.** [BUG-917, not this unit] (HR-5) All filters (R2, R5, R7, R8, R9) are applied to the whole scope first; then `skip` matches are skipped and at most `limit` returned. A page is short only when there are no more matches, and a search finds a match wherever it is. *(Today: one page of `limit` rows, deleted rows and non-matching rows included, is loaded first and filtered afterwards. For a list of one factory the deleted part goes away with BUG-905, this unit.)*
- **R4.** [BUG-918 (no factory), not this unit] / [BUG-903 (one factory), this unit] (HR-6) Results are ordered by name case-insensitively ascending, then `id` ascending, before `skip` / `limit`; with `include_deleted=True` deleted and live sections are ordered together. *(Today: no order is requested.)*
- **R5.** [BUG-917] With `include_deleted=False` (default) soft-deleted sections are never returned and never take a place in the page. *(Today: removed only after the page was cut. In the factory branch this holds once BUG-905 is fixed in the DAO.)*
- **R6.** [BUG-920] (HR-4) With `include_deleted=True` soft-deleted sections are returned along with live ones. The manager does so today and must keep doing so after this unit: in the factory branch that is what the pass-through to `get_by_factory(include_deleted=True)` gives (DAO R8). Making the option reachable from `GET /factory-sections/` is the service / endpoint part of BUG-920 and is **not** this unit.
- **R7.** [BUG-924 (no factory), not this unit] / [BUG-904 (one factory), this unit] With `include_deleted=False`, a section whose factory is soft-deleted is not returned and takes no place in the page, with or without a factory filter; with `include_deleted=True` it is returned. The section rows are never changed: once the factory is no longer deleted they are listed again. A live but inactive factory hides nothing. *(Today: listed in both branches.)*
- **R8.** Given a non-blank `search`, a section matches when the text is a case-insensitive substring of its **name** (`"HALL"` finds "Main Hall" and "hidden hall"); the factory's name is not searched. Inner whitespace of the text is significant. (Holds today within the loaded page; the whole-scope part is R3.)
- **R8a.** (HR-8) The text is literal: `"%"` returns only sections whose name contains `%`; `"_"` only names containing `_`. (Holds today.)
- **R9.** [BUG-921, not this unit] `None`, `""` and whitespace-only `search` apply no search filter; otherwise leading / trailing whitespace is removed before matching. *(Today: `None` and `""` apply no filter; the text is used untrimmed.)*
- **R10.** `search` combines with the deleted filter: a matching soft-deleted section is returned only with `include_deleted=True`.
- **R11.** No sections, no match, or `skip` at / past the number of matches → `[]`; `limit=0` → `[]`. Defaults `skip=0`, `limit=100`: given 101 live sections (one factory, or the workspace), exactly 100 are returned. A negative `limit` or `skip` makes Postgres reject the query, on both branches (`sqlalchemy.exc.DataError`: `LIMIT must not be negative` / `OFFSET must not be negative`).

Side effects: none.

Facts: `factories` has `is_deleted` (soft delete) and `is_active` (separate flag). `factory_sections.factory_id` is NOT NULL with a foreign key to `factories.id`, so every section has a factory row. Nothing in the database ties a section's `workspace_id` to its factory's.

## 4. Rules that apply

- **HR-4. Soft-deleted rows are hidden unless asked for.** Lists/searches exclude soft-deleted rows by default. Filters, joins and searches through related rows ignore related rows that are soft-deleted. Scope: enforced in managers and module-specific DAO query methods (like `get_by_factory`); the generic `BaseDAO` methods stay raw and do return soft-deleted rows.
- **HR-5. Filter first, then page.** All filtering (soft-delete, flags) happens in the query before `skip` / `limit`. A page is only short when there are no more results.
- **HR-6. Every paged or top-N result has a stable order.** Default: name case-insensitive ascending, then `id` ascending. Standing decision: no order recipe counts as deterministic unless it ends in `id`.
- **Standing decision ("hidden, not cascaded", 2026-10-11):** things belonging to a soft-deleted factory are hidden by the factory's state, their own rows untouched, so restoring the factory brings them back.
- **HR-16. Nothing links across workspaces.** Not changed by this unit: keep comparing the section's own `workspace_id` (R1a).
- No owner answer (OQ-n) touches these bugs.

## 5. Scope

- May change: `app/dao/factory_section.py` (the fix of BUG-903, BUG-904, BUG-905 and the new `include_deleted` keyword of `get_by_factory`) and `app/managers/factory_section_manager.py`, **limited to** passing `include_deleted=include_deleted` to `get_by_factory` in the factory branch of `search_factory_sections`. No other manager change.
- No migration, no schema or API change. The response shape of the section list does not change; deleted sections and sections of deleted factories just stop appearing in the by-factory list (default `include_deleted=False`). The endpoint still never sends `include_deleted`.

## 6. Out of scope (leave alone)

Open bugs in `app/managers/factory_section_manager.py` that this unit does **not** fix (the manager change is the pass-through only):
- BUG-908 deleting a section erases its machines' assignments; BUG-911 duplicate-name check scans only 100 rows; BUG-912 case-sensitive duplicate check; BUG-913 no unique index; BUG-914 move into a factory where the name is taken; BUG-916 `get_factory_section` returns deleted sections; BUG-917 section list filters after paging; BUG-918 workspace-wide list has no order; BUG-919 `updated_by` on no-op update; BUG-920 section list `include_deleted` flag unreachable from the API (broader than this unit: making it reachable is a service / endpoint change; this unit only keeps the manager option working); BUG-921 search text not trimmed; BUG-922 / BUG-923 `factory_id=0`; BUG-924 workspace-wide list shows sections of a deleted factory; BUG-925 section of a deleted factory opens by id; BUG-926 / BUG-927 writes to a section of a deleted factory; BUG-928 moving a section links machines across factories.
- Known side effect, not a bug of this unit: after BUG-904 the duplicate-name check (`_check_name_exists_in_factory`) sees no sections of a soft-deleted factory. No path reaches it for such a factory except a rename inside one, which is BUG-926 (open, not this unit). Leave it.
- BUG-910 (assigning a machine to a section of a deleted factory): `app/managers/machine_section_assignment_manager.py`.
- BUG-100 (generic `get_by_workspace` has no order): `app/dao/base.py`.
