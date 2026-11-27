# Tester pre-check: dao-item_tag

Date: 2026-11-27. Source `app/dao/item_tag.py`. Specs and cases: `tests/unit/dao/item_tag.*`,
`tests/unit/services/item_tag_service.*`.

Search: I grepped the bare numbers `929`, `930` and `931` in `tests/**/*.py`. All the markers are
inline `pytest.mark.xfail(..., reason="BUG-93x: ...")`, with no helper constants. Callers of
`item_tag_dao`: `ItemTagService` (both list methods) and `ItemManager` (both counters). In
`test_item_manager.py`, `test_item_service.py`, `test_item_summary_service.py`,
`test_item_tag_assignment.py` and `test_workspace_manager.py` no marker names these bugs (the
`usage_count` hits in `test_account_manager.py` are account tags, a different DAO). So there are
11 target tests in 2 files.

Run today with `--runxfail`, DB `bf_dao_item_tag_test`: 8 failed, 3 passed (ITG-SYS-09, ACT-12,
ITS-T-08, all non-strict ties or collation-dependent, as their cards say). Every strict test fails
on the Then its card names.

I also patched candidate fixes in through a scratch pytest plugin (no `app/` edit) and ran the
unit's file plus the five caller files: the sort fix plus a correct counter fix makes exactly the
11 target tests pass, nothing else changes (plus the already-loose non-strict ties elsewhere,
BUG-100 ITG-INH-18, which is a non-strict tie that the ORDER BY id now happens to satisfy).

## BUG-929: system tag list has no order

| File | Tests | Strict |
|---|---|---|
| DAO | ITG-SYS-08, SYS-09 | no |
| DAO | ITG-SYS-10 (SQL text) | yes; fails on Then 2 (no `ORDER BY`) |
| service | ITS-Y-04 | no (its `ids` helper sorts, so Then 1 is a set check) |

Verdict: **right**, all 4. SYS-08 and ITS-Y-04 check "Tool", "consumable", "Bolt" →
"Bolt", "consumable", "Tool" (R3's own example); SYS-09 checks the `id` tie-break on two names
differing only in case. SYS-10 wants `lower(item_tags.name)` and `item_tags.id` after `ORDER BY`.
`order_by(func.lower(ItemTag.name), ItemTag.id)` passes. It does not check the key order; SYS-08/09
do. Risk for the systems engineer: a raw `text()` sort, `func.upper`, or a `collate(...)` sort would
fail SYS-10 although it may sort correctly.

## BUG-930: active tag list sorted by collation, no tie-break

| File | Tests | Strict |
|---|---|---|
| DAO | ITG-ACT-11, ACT-12 | no (ACT-11 depends on the server's collation) |
| DAO | ITG-ACT-13 (SQL text) | yes; fails on Then 4 (`lower(item_tags.name)` missing) |
| service | ITS-T-08 | no (passes today under this collation) |

Verdict: **right**, all 4. ACT-11 is R4's own example ("Alpha" (1), "alpha" (2), "bravo",
"Charlie"); ACT-12 the same-name tie. ACT-13 wants `item_tags.is_system_tag DESC`,
`lower(item_tags.name)` and `item_tags.id`; it doesn't check their order, but the passing test
ITG-ACT-09 (system tags first) would catch a fix that moved the name key in front. Same SQL-text
risk as BUG-929.

## BUG-931: usage counter can lose concurrent changes

| File | Tests | Strict |
|---|---|---|
| DAO | ITG-INC-11 | yes; fails on Then 2 (4, not 11) |
| DAO | ITG-DEC-13 | yes; fails on Then 2 (2, not 9) |
| DAO | ITG-DEC-14 | yes; fails on Then 2 (2, not 0) |

Pass controls that constrain the fix: ITG-INC-12 (expired object → 11), INC-10 / DEC-12 (the
flush also saves a pending rename), **DEC-04 (at 0 nothing is flushed: a pending rename stays
unsaved)**, INC-13 / DEC-15 (flushed, not committed).

Verdict: **right but incomplete** → entry in `docs/bugfix/wrong-tests.md`. The tests use the
spec's stale-object recipe in one session (no commits, so no real second transaction). Candidates
run against them:

| Candidate | Stored | Returned | INC-11 / DEC-13 / DEC-14 | Fixes the race? |
|---|---|---|---|---|
| Core `update(...).values(usage_count=usage_count ± 1).returning(...)`, decrement guarded `usage_count > 0`, `set_committed_value` on the tag, flush only when a row changed | right | right | pass | yes |
| ORM `query.update(..., synchronize_session=False)` + `db.refresh(tag, ["usage_count"])` | right | right | pass | yes |
| ORM `query.update(...)` with the default sync, or `synchronize_session="fetch"` | right | **stale (4 / 2)** | fail | yes, but R5/R6 "returned tag shows the stored result" is broken |
| shortcut: `db.refresh(tag, ["usage_count"])`, then the old `+= 1` / `-= 1` | right | right | **pass** | **no** (still read-then-write) |

So a correct fix passes, and the naive ORM update is rightly rejected, but the refresh-then-write
shortcut also passes while two concurrent requests still both write 6 (the bug's example). The
proposed correction adds one SQL-text Then to INC-11 and DEC-13: an UPDATE whose SET computes
`usage_count` from the stored column (and, for the decrease, whose WHERE tests `usage_count >`).
Checked: both correct candidates pass it, the shortcut fails INC-11 and DEC-13, today's code
still fails on Then 2. **Condition:** the diff in `wrong-tests.md` must be on `origin/main` before
the batch-2 baseline. If it isn't, BUG-931 is skipped this round (remove it from `brief.md`,
re-run the firewall).

Notes for the systems engineer, whichever way it goes:
- Reject any fix that re-reads and then writes an absolute value, or that locks the row
  (`with_for_update`; HR-10 says no lock).
- The ORM's default synchronisation evaluates `usage_count + 1` against the stale in-memory value,
  so the returned tag must be set from the database (RETURNING or a refresh of `usage_count`).
- DEC-04 requires that a decrement at stored 0 flushes nothing. The test session has
  `autoflush=False` (as the app's `SessionLocal`), so an ORM-enabled UPDATE doesn't autoflush
  there; a fix that calls `db.flush()` unconditionally before the UPDATE breaks DEC-04.

## Outside this unit

- `ItemManager` calls the counters once per tag; BUG-934 / BUG-935 / BUG-945 (out of scope) are
  where item saves recreate or miss counter changes. No test there names BUG-931.
- The same read-then-write counter is in `app/dao/account_tag.py` (lines 100, 120), logged as
  **BUG-1484** ("per BUG-931"). Its tests very likely share the gap above (a stale-object check
  that a refresh-then-write shortcut passes); its pre-check should apply the same SQL-text check.
