# Tester pre-check: dao-attachment_markup_event

Date: 2026-11-28 (batch 5). Source `app/dao/attachment_markup_event.py`. Spec
`tests/unit/dao/attachment_markup_event.spec.md` (APPROVED); caller rule `list_events` R3 in
`tests/unit/managers/attachment_markup_manager.spec.md`. Database `bf_dao_attachment_markup_event_test`.

Search: grepped the bare numbers `1436`, `1437` in `tests/**/*.py`. The DAO file uses inline
`pytest.mark.xfail(...)`; the manager file uses the module constants `X1436` (non-strict) and
`X1437` (strict), each used by exactly one test (lines 150–153, used at 2260 and 2282).

Caller test files (grep for `attachment_markup_event_dao`, `list_for_attachment`, `markup_event`):
- `tests\unit\dao\test_attachment_markup_event.py` (unit's own; targets)
- `tests\unit\managers\test_attachment_markup_manager.py` (targets)
- `tests\unit\services\test_attachment_markup_service.py` (no target; no 1436/1437 marker)
- `tests\test_attachment_markup.py` (legacy; mocks `list_for_attachment` with `return_value`, passes no `limit`; no target)
- `tests\unit\dao\test_attachment.py`, `tests\unit\dao\test_attachment_markup.py` only count rows of the table; not affected.

No test, script or `app/` caller passes `limit` to `list_for_attachment` (grep: zero hits), so
removing the parameter breaks nothing.

Run today with `--runxfail`: all 5 targets fail, each on the Then its card names; the 6th selected
test (AME-LA-11, passing companion) passes.

Candidate fix swapped in with a scratch plugin (no `app/` edit): `ORDER BY created_at DESC, id DESC`,
no `limit` parameter, no `.limit()`. Over the 4 files above:

| Candidate | Result |
|---|---|
| none (today) | 160 passed, 119 xfailed |
| candidate fix | 160 passed, 114 xfailed; exactly the 5 targets flip (3 strict XPASS, 2 non-strict XPASS); nothing else changes |

## BUG-1436 (ties in markup history): tests right, go ahead

| Test | File | Marker | Today |
|---|---|---|---|
| `test_ame_la_08__on_a_tie_the_highest_id_comes_first_when_the_lowest_id_was_updated` | `tests/unit/dao/test_attachment_markup_event.py` | non-strict | fails Then 2: `[615, 613, 614, 612]` vs `[615, 614, 613, 612]` (updated lowest id last) |
| `test_ame_la_09__the_query_orders_by_created_at_then_id_both_descending` | same | strict | fails Then 3: order part is `attachment_markup_events.created_at DESC` only |
| `test_amup_lv_04__ties_highest_id_first_after_update` | `tests/unit/managers/test_attachment_markup_manager.py` | `X1436` non-strict | fails Then 1: `[408, 409, 410]` vs `[410, 409, 408]` |

Verdict: **right.** Row: "HR-6: `created_at` newest first, then `id` descending"; spec R3 "then
entries of one time highest `id` first, also after one of them was updated". LA-08 and LV-04 check
exactly that under a forced sequential scan after an update (non-strict, as their cards say:
physical order may happen to match). LA-09 is the strict proof, a SQL-text check: `created_at`
before `.id`, two `DESC`. **Risk for the systems engineer:** a normal ORM
`order_by(created_at.desc(), id.desc())` passes it (verified); a raw `text()` sort without the
table-qualified `.id`, or a third `DESC` anywhere after `ORDER BY`, would fail it. The helper cuts
the order part at `LIMIT`; with the limit removed the order part runs to the end of the statement,
which is fine (verified). Depends on no other bug.

## BUG-1437 (200-entry cap): tests right, go ahead

| Test | File | Marker | Today |
|---|---|---|---|
| `test_ame_la_10__every_entry_is_returned_201_give_201` | `tests/unit/dao/test_attachment_markup_event.py` | strict | fails Then 2: 200 vs 201 |
| `test_amup_lv_06__all_201_entries` | `tests/unit/managers/test_attachment_markup_manager.py` | `X1437` strict | fails Then 1: 200 vs 201 |

Verdict: **right.** Row: "All entries are returned, no cap"; spec R4 "given 201, 201"; manager
`list_events` R3 "no 200 cap". Both check only the count, which a correct fix gives (with or without
the parameter removed). LV-06 puts all 201 at one time, so it does not depend on BUG-1436. The
companion AME-LA-11 (first 200 are the newest 200) passes today and with the fix. No card checks
that the `limit` parameter is gone; that part of the row is checked only by review (the dead-code
checklist entry in `docs/testing/dead-code-removal-checklist.md` names it).

## Wrong tests

None. `wrong-tests.md` not touched.

## Outside this unit

- **BUG-2119** (manager, profile read per history entry) grows with the uncapped history: after this
  fix a 1,000-entry history makes 1,000 profile reads per request. Not a reason to hold this unit
  (the row ties them together already), but worth a note in the PR; BUG-2119 is a natural next unit.
- Same pattern in the neighbouring layer DAO: **BUG-1435** (`app/dao/attachment_markup.py`,
  `updated_at` ascending without `id`), open, its own unit.
- `docs/testing/dead-code-removal-checklist.md` line 214 should be ticked when this unit merges.
