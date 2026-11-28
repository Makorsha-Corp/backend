# Tester pre-check: dao-item_tag-2

Date: 2026-11-27 (batch 4). Source `app/dao/item_tag.py` (follow-up unit; BUG-929/930/931 fixed in
`dao-item_tag`). Spec and cases: `tests/unit/dao/item_tag.spec.md`, `tests/unit/dao/item_tag.cases.md`.

**Search.** Grepped the bare number `3302` in `tests/**/*.py`: no test existed (the bug row says
"no test yet: add one in the follow-up unit"). Caller test files of the counters
(`tests/unit/managers/test_item_manager.py`, `tests/unit/services/test_item_service.py`,
`tests/unit/services/test_item_tag_service.py`) carry no marker for this bug.

## Test added (main checkout, not committed)

- Card **ITG-DEC-16** in `E:\Projects\Makorsh-Corp\backend\tests\unit\dao\item_tag.cases.md`
  ("after a savepoint rollback, the tag object shows the stored count again"; rule
  `decrement_usage_count` R7 [BUG-3302]; strict; fails today on Then 4). Header counts, the
  rule-coverage row for R7 and the bug-coverage table were updated (93 cases, 12 expected-to-fail).
- Test `test_itg_dec_16__after_a_savepoint_rollback_the_tag_object_shows_the_stored_count_again` in
  `E:\Projects\Makorsh-Corp\backend\tests\unit\dao\test_item_tag.py`, right after ITG-DEC-15, in the
  file's style (`mk_tag`, `stored_count`, `# Then n` comments), marked
  `xfail(strict=True, reason="BUG-3302: ...")`.
  Steps: tag stored with 5; `sp = db.begin_nested()`; decrement; `result is t1`; `t1.usage_count == 4`
  (loads the value inside the savepoint); `sp.rollback()`; `stored_count == 5`; `t1.usage_count == 5`.

## BUG-3302: decremented tag keeps the rolled-back count in memory

| Test | Strict | Verdict |
|---|---|---|
| ITG-DEC-16 (DAO) | yes | **right** |

**Run today** (`--runxfail -rf`, DB `bf_dao_item_tag_2_test`): fails on Then 4, `assert 4 == 5`
(the object still holds the rolled-back 4; Then 1-3 pass, so it is not a setup error). Normal run:
XFAIL with reason BUG-3302.

**Judgement against the row and rule.** The row's Intended is "after a savepoint rollback the
in-memory `usage_count` equals the stored value, as for the increment"; the test checks exactly that
(Then 4), plus that the stored value is restored (Then 3, spec R7) and that the value inside the
savepoint is 4 (Then 2, R1). It checks nothing the spec does not require; it does not depend on how
the fix is done (no SQL-text check). It depends on no other open bug.

**A correct fix makes it pass.** Scratch pytest plugin (in the scratchpad, swapping
`ItemTagDAO.decrement_usage_count` in memory; no `app/` edit) using the same guarded relative UPDATE
with `synchronize_session="fetch"` + expire of `usage_count`:
- `test_item_tag.py`: ITG-DEC-16 becomes a strict XPASS (reported FAILED, i.e. the marker must go);
  everything else identical (90 passed, INH-19 xfail, INH-18 non-strict xpass as in the baseline).
  With `--runxfail -k itg_dec`: all 16 decrement tests pass, including R2 (no flush at 0) and the
  BUG-931 statement-recorder check (one guarded relative UPDATE).
- Caller files `test_item_manager.py` + `test_item_service.py` (179 passed, 167 xfailed) and
  `test_item_tag_service.py` (40 passed, 28 xfailed): identical with and without the patch.

**Baseline of the file after adding the test:** 90 passed, 2 xfailed (DEC-16, INH-19), 1 xpassed
(INH-18, non-strict, pre-existing). Nothing else changed.

**Increment check (brief claim):** a throwaway probe confirmed that today, after a savepoint
rollback around `increment_usage_count`, the tag object shows the old value again (5 → 6 → rollback
→ 5). So the brief's "the increment already behaves as intended" holds. Probe deleted.

## Outside this unit

- The spec `tests/unit/dao/item_tag.spec.md` R7 does not yet state the in-memory part; the brief
  states it as "R7, extended by BUG-3302" from the bug row. The spec could get one sentence added
  to R7 in a later describer pass (not done here: test-pipeline scope).
- Cards ITG-INC-11, DEC-13, DEC-14 still say "Expect: xfail BUG-931" although BUG-931 is fixed and
  their markers were removed; cosmetic, for the next cases-file touch.

Verdict: **all tests right; BUG-3302 goes ahead.** `wrong-tests.md` untouched.
