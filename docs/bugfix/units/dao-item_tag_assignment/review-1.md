# Code review 1: dao-item_tag_assignment (2026-11-28)
Verdict: PASS   (blockers: 0, majors: 0, minors: 0, nits: 1)
Diff reviewed: 092776b..ec2b64c, files: app/dao/item_tag_assignment.py (no alembic changes)

## 1. What a correct fix must do (written before reading the diff)

- **BUG-932 `get_tags_for_item`:** add an SQL `ORDER BY lower(name) ASC, id ASC`,
  in the same form as `app/dao/item_tag.py` (`func.lower(ItemTag.name).asc(),
  ItemTag.id.asc()`). No `is_system_tag` key. Filters (link `item_id`, link
  `workspace_id`, `ItemTag.is_active`) unchanged; no limit; return type `list`.
- **BUG-933 `get_tags_for_items`:** within each item, the same two keys after the
  `item_id` grouping key (or with no item key at all, since the Python grouping
  preserves row order per item). The dict must still be seeded from `item_ids` in
  first-appearance order with duplicates collapsed and unknown ids mapping to `[]`;
  empty/None input still returns `{}` without a query.
- Both methods must give the same order for the same item (spec R3 of
  `get_tags_for_item`).
- Must not change: signatures (keyword-only), the other three methods, inherited
  methods, the workspace and active-tag filters, the counter-lowering callers in
  `ItemManager.update_item` / `delete_item` (order of decrements is irrelevant to
  them). Join cannot duplicate rows (one link per item+tag, `uq_item_tag`).

## 2. Findings

No blockers, majors or minors.

Checked:
- **Correctness.** Throwaway check (rowkit, `bf_dao_item_tag_assignment_test`,
  collation `English_United States.1252`, rolled back) with tags bravo, Alpha,
  alpha, Charlie (system), Bolt, Bolt, bolt, Älpha and a deleted tag:
  `get_tags_for_item` → Alpha(148), alpha(149), Älpha, Bolt(151), Bolt(152),
  bolt(153), bravo(147), Charlie(150): brief example 2, 3, 1, 4 holds, equal
  names by lower id, system tag not grouped first, deleted tag absent.
  `get_tags_for_items([it2, it, it2, 999999])` → keys `[it2, it, 999999]`,
  999999 → `[]`, each item's list in the same order, and the list for `it` is
  identical to `get_tags_for_item`. Other workspace → `[]`; `[]` → `{}`.
- **Root cause.** Ordering done in SQL, both sibling list methods fixed; the
  other methods return no ordered list (count dict, bool, int) so there is no
  sibling left broken.
- **Convention.** Identical expression to `app/dao/item_tag.py:58` and `:83-84`
  (minus the system-first key, as the brief requires). `func` was already
  imported.
- **Scope/cleanliness.** Only the two `order_by` clauses and their docstrings
  changed; docstrings are accurate. `ruff check app/dao/item_tag_assignment.py`:
  all checks passed. No migration, no API/shape change.
- **Workspace (HR-16).** Filters on the link's `workspace_id` untouched.
- **Performance.** Per-item tag lists are tiny and already filtered by
  `item_id`; the sort adds no index need.

Nit (style only, no action needed):
- N1. `get_tags_for_items` keeps `ItemTagAssignment.item_id` as the first sort key
  without `.asc()` while the two new keys spell `.asc()`; harmless and
  pre-existing.

## 3. Questions (unproven)

- None on the fix. Observation only: `lower()` still sorts under the database
  collation (e.g. "Älpha" falls among the a's on this database); this matches the
  established `item_tag.py` convention and HR-6's "case-insensitive", so it is not
  a finding.

## 4. What is good

Minimal, exactly mirrors the BUG-930 convention, fixes both sibling methods in
SQL so they agree with each other, and leaves grouping, key order and filters
untouched.
