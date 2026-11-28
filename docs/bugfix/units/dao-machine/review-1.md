# Code review 1: dao-machine (2026-11-27)
Verdict: PASS   (blockers: 0, majors: 0, minors: 0, nits: 3)
Diff reviewed: 614bbce..83f4adf, files: app/dao/machine.py (no alembic changes)

## 1. What a correct fix must do (written before reading the diff)

- **BUG-886** (`search_advanced`, `latest_event_type`): build without `.astext`
  (generic `JSON` needs `.as_string()` → Postgres `->>`). Pick exactly one
  "latest" `status_updated` row per machine, ordered `created_at DESC, id DESC`,
  in the caller's workspace only; filter on that row's status. Must not fall back
  to an older row when the latest has no `status` key or `metadata` is null
  (JSON `null` or SQL NULL); other event types ignored even if newer; a machine
  with no status change never matches; no duplicate rows on same-status ties;
  combines with every other filter, sort and paging in SQL.
- **BUG-887**: name sort `lower(name)` in the requested direction, then
  `id ASC` in both directions; `created_at` sort and unknown `sort_by` /
  `sort_dir` handling unchanged.
- **BUG-888**: escape `\` first, then `%` and `_`, and declare the escape
  character on all three `ILIKE`s (name, model number, manufacturer).
- **BUG-892**: `str.strip()` the search; empty after strip = no filter; inner
  whitespace kept; escaping applied to the stripped text.
- **BUG-889**: `get_by_section` and the `search_advanced` section filter must
  require the section to be live (`factory_sections.is_deleted = false`);
  inactive sections unaffected; assignment rows untouched; without a section
  filter a machine with a left-over assignment to a deleted section still lists.
- **BUG-890 / BUG-891**: `get_by_factory`, `get_by_section`, `search_advanced`
  hide machines whose factory is soft-deleted, via a read of the factory row
  only (no write); inactive-but-live factory hides nothing; restoring the factory
  brings the machine back unchanged; hidden machines must not use page slots
  (filter in SQL before LIMIT/OFFSET). The join must be 1:1 (factory PK, FK NOT
  NULL) so it can neither duplicate nor drop live rows.
- **Must not change:** signatures and paging defaults; no `ORDER BY` added to
  `get_by_factory` / `get_by_section`; inherited `BaseDAO` lookups stay raw;
  `soft_delete` / `restore` untouched; `get_active_by_workspace` and the
  `include_deleted` parameter left alone; no new N+1 (eager load kept).

## 2. Findings

No blockers, majors or minors. Everything in §1 was checked against the code
and with a rolled-back rowkit script on `marker_test`
(scratch: `rev_machine/check.py`). Results:

| Check | Input | Result |
|---|---|---|
| R3a (search) | Factory A live "Lathe", Factory B deleted "Press" | no filter: "Press" absent; `factory_id=B` → `[]`; `sort_dir=desc, limit=1` → a live machine, not "Press" |
| R3a/R3b (get_by_factory) | deleted factory / inactive-live factory | `[]` / machine returned |
| R3c / restore | Factory B `is_deleted=False` again | "Press" back in `search_advanced(factory_id=B)` and in `get_by_section` |
| BUG-889 | section deleted, assignment kept | `get_by_section` → `[]`; `search_advanced(factory_section_id=…)` → `[]`; unfiltered list still contains the machine |
| BUG-888 | `%`, `_`, `a\b` | only "pct" (model "50%"), only "x_y", only `a\b` (not "ab") |
| BUG-892 | `" bolt "`, `" \n\t"` | Bolt/bolt/BOLT; whitespace-only → all 9 machines (no filter) |
| BUG-887 | "Bolt", "bolt", "BOLT" | id ascending in both `asc` and `desc` |
| BUG-886 | RUNNING 10:00 → IDLE 11:00 | IDLE only |
| BUG-886 | RUNNING then OFF, same `created_at` | OFF only |
| BUG-886 | latest status row has no `status` key | matches nothing (older RUNNING not used) |
| BUG-886 | latest status row has `metadata` JSON `null` | matches nothing |
| BUG-886 | two RUNNING rows at the same newest time | listed once |
| BUG-886 | newer `updated` event with `{"status": "IDLE"}` | ignored; still RUNNING |
| BUG-886 + search | `RUNNING` + `search="bolt"` | ANDed correctly |

SQL (compile_query): factory join is `JOIN factories ON factories.id =
machines.factory_id` (PK, `machines.factory_id` NOT NULL → 1:1); all filters
precede `ORDER BY lower(machines.name) …, machines.id ASC LIMIT … OFFSET …`;
the eager load stays two aliased LEFT OUTER JOINs on a `uselist=False`
relationship (app/models/machine.py:44), so LIMIT is not wrapped and no N+1.
The status subquery is bounded by `machine_activity_events.workspace_id`
(HR-16). `ruff check app/dao/machine.py`: all checks passed. No unrelated edits
in `app/`; `get_by_factory` / `get_by_section` got no `ORDER BY`.

### Nits
- **N1.** Factory hiding uses an inner `JOIN factories`, while the sibling DAO
  that solved the same problem (BUG-904) uses `exists()`
  (app/dao/factory_section.py:49-53). Both are correct here (1:1 join on a PK);
  just two styles for one rule.
- **N2.** `_escape_ilike` / `_ILIKE_ESCAPE` duplicate
  app/dao/account_invoice.py:24-28. That is the second copy now. A shared
  helper would be a separate change (scope here is one file).
- **N3.** app/dao/machine.py:216 builds `func.lower(Machine.name)` a second time
  as the `.get` default instead of reusing `sort_field_map["name"]`.

## 3. Questions (unproven)

- **Q1.** `get_by_factory` / `get_by_section` hide machines of a deleted factory
  even when `include_deleted=True`, whereas `factory_section.py:44` applies its
  factory check only when `include_deleted` is false. No caller passes
  `include_deleted` (it is dead and out of scope per brief §6), so this has no
  effect today. Flagged so whoever removes the parameter knows.
- **Q2.** Brief §6 asks that the new joins not change the order of the two
  unordered lookups other than by hiding rows. Neither query has an `ORDER BY`
  (before or after), so row order was never guaranteed. An extra join can still
  change the plan Postgres picks, and with it the physical order. I can't prove
  any change, and BUG-343 owns the ordering.
- **Q3.** Performance: the `row_number()` subquery ranks every `status_updated`
  event in the workspace. It is the same scan size as the old `GROUP BY`
  version, and there is no `(workspace_id, event_type)` or
  `(machine_id, created_at)` index on `machine_activity_events`. Not a
  regression. Worth an index if the activity log grows large.

## 4. What is good

- The window function settles the BUG-886 tie-break (`created_at DESC, id
  DESC`) in one subquery, and it cannot fall back to an older row or duplicate a
  machine. This is simpler than the old max-then-rejoin version.
- The escape order is right (backslash first), and `ESCAPE` is declared on all
  three columns, matching the existing account_invoice convention.
- All hiding is in SQL before paging, so hidden machines never use a page slot.
  The `include_deleted` parameter, the paging defaults and the unordered lookups
  are left exactly as the brief requires.
