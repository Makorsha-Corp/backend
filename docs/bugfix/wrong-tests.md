# Bug-fix pipeline: wrong tests

See `docs/bugfix/pipeline.md` §5. One entry per test the tester's pre-check judged
wrong: the bug id, test id and test file; why it is wrong (quoting the bug row and
spec rule); a proposed correction as a diff. That bug is skipped until the test is
fixed through the test pipeline.

## BUG-1101: MMLM-G-21 and MMLM-G-22 (marker names one bug, the test needs two)

**Status: applied 2026-11-27 by the orchestrator** (marker reason only; lands in main before the batch-2 baseline). BUG-1101 stays in unit dao-machine_maintenance_log.

- **Unit:** `dao-machine_maintenance_log` (pre-check 2026-11-27).
- **Tests:** `test_mmlm_g_21__the_same_row_gets_the_404_with_include_deleted_true_too`,
  `test_mmlm_g_22__a_soft_deleted_log_on_another_workspace_s_machine_gets_the_404_with_in`,
  in `tests/unit/managers/test_machine_maintenance_log_manager.py`.
- **Why it's wrong:** what the tests check is right. Spec `get_log` R6: "[BUG-1101] (HR-16)
  A log whose machine belongs to another workspace → 404 as R2, also with
  `include_deleted=True`." But `include_deleted` does not exist yet. It is BUG-1150's
  intended change ("new `include_deleted=True` returns it", `app/managers/machine_maintenance_log_manager.py`,
  out of scope for this unit). Both cards say "Fails today on: Then 1 (the call raises
  TypeError: the parameter does not exist)". A correct BUG-1101 fix (DAO only) leaves
  them failing with the same TypeError. The strict marker names only BUG-1101, so stage C
  would remove it and the tests would fail, and the flip check would reject them as
  "target test still xfailed".
- **Scope of the skip:** only these two tests, not BUG-1101. The other 20 BUG-1101 tests
  are right, and the correction changes the label, not the check. The flip check already
  allows a test that names a second bug to stay xfailed ("also needs [...]; still
  xfailed"), and stage C keeps a marker that names a bug outside the unit. **Condition:**
  the diff below must be on `origin/main` before the batch baseline is recorded. If it
  isn't, BUG-1101 must be skipped for this round.
- **Proposed correction** (marker reason only; precedent: `test_account_invoice_manager.py`,
  "BUG-625, BUG-631: needs both fixes"):

```diff
--- a/tests/unit/managers/test_machine_maintenance_log_manager.py
+++ b/tests/unit/managers/test_machine_maintenance_log_manager.py
@@ -4378,3 +4378,3 @@
 # [claude] MMLM-G-21
-@pytest.mark.xfail(strict=True, reason="BUG-1101: A stored maintenance log linked to another workspace's machine shows that machine's id")
+@pytest.mark.xfail(strict=True, reason="BUG-1101, BUG-1150: needs both fixes. BUG-1150 adds include_deleted to get_log; BUG-1101 hides a log on another workspace's machine")
 def test_mmlm_g_21__the_same_row_gets_the_404_with_include_deleted_true_too(db, w1, m9, mk_log):
@@ -4398,3 +4398,3 @@
 # [claude] MMLM-G-22
-@pytest.mark.xfail(strict=True, reason="BUG-1101: A stored maintenance log linked to another workspace's machine shows that machine's id")
+@pytest.mark.xfail(strict=True, reason="BUG-1101, BUG-1150: needs both fixes. BUG-1150 adds include_deleted to get_log; BUG-1101 hides a log on another workspace's machine")
 def test_mmlm_g_22__a_soft_deleted_log_on_another_workspace_s_machine_gets_the_404_with_in(db, w1, m9, mk_log):
```

  Matching cases change in `tests/unit/managers/machine_maintenance_log_manager.cases.md`:
  MMLM-G-21 and MMLM-G-22 `Expect: xfail BUG-1101` becomes `Expect: xfail BUG-1101, BUG-1150`.

## BUG-931: ITG-INC-11 and ITG-DEC-13 (right check, but a racy shortcut passes them)

**Status: proposed 2026-11-27 by the tester's pre-check** (adds one check to two strict tests;
today's outcome is unchanged). BUG-931 stays in unit dao-item_tag **only if** this diff is on
`origin/main` before the batch-2 baseline is recorded; otherwise BUG-931 is skipped this round.

- **Unit:** `dao-item_tag` (pre-check 2026-11-27).
- **Tests:** `test_itg_inc_11__the_increase_is_applied_to_the_stored_value_not_to_the_loaded_one`,
  `test_itg_dec_13__the_decrease_is_applied_to_the_stored_value_not_to_the_loaded_one`
  (and, unchanged, `test_itg_dec_14__the_not_below_0_check_uses_the_stored_value_stored_0_stays_0`),
  in `tests/unit/dao/test_item_tag.py`.
- **Why it's incomplete:** the bug row's Intended is "The change is applied in the database
  relative to the stored value (`usage_count = usage_count + 1`; `usage_count - 1` only where
  `usage_count > 0`) ... no row lock needed (HR-10 does not apply)", and HR-10 in the brief says
  "The fix is a single relative update in the database, not a lock". The tests check spec
  `increment_usage_count` R5 / `decrement_usage_count` R6 with a stale object in one session
  (loaded 3, stored 10 → 11 / 9). That is right and a correct fix passes it, but a shortcut
  that re-reads the counter and then writes an absolute value
  (`db.refresh(tag, ["usage_count"]); tag.usage_count += 1; db.flush()`) passes all three tests
  and the rest of the file, while two concurrent requests still both read 5 and write 6 (the
  bug's own example). Measured on `bf_dao_item_tag_test` with the candidate patched in (no
  `app/` edit): the shortcut makes INC-11, DEC-13 and DEC-14 pass. A true two-transaction
  test is out (nothing is ever committed), so the missing part is a SQL-text check on the
  UPDATE the call sends, the same kind as ITG-SYS-10 / ACT-13.
- **Proposed correction** (one new Then per test; the relative-UPDATE pattern accepts ORM
  `query.update(...)`, Core `update(...)` and raw `text()` forms, and does not require the
  UPDATE to be the only statement, so a fix that also re-writes the value inside the same
  transaction still passes). Checked against four candidate fixes: Core `update().returning()`
  with `set_committed_value` and ORM `update(synchronize_session=False)` + `refresh` both pass
  all three tests; the refresh-then-write shortcut now fails INC-11 and DEC-13; today's code
  still fails on Then 2 as the cards say.

```diff
--- a/tests/unit/dao/test_item_tag.py
+++ b/tests/unit/dao/test_item_tag.py
@@ -11,6 +11,7 @@
 finishing.
 """
 # ruff: noqa: SIM117  (Conventions prescribe `with pytest.raises(...)` around `with db.begin_nested()`)
+import re
 from datetime import datetime, timedelta, timezone
 from unittest.mock import patch
 
@@ -204,6 +205,17 @@
     def selects(self):
         return [s for s in self.statements if s.lstrip().upper().startswith("SELECT")]
 
+    def updates(self):
+        return [s for s in self.statements if s.lstrip().upper().startswith("UPDATE")]
+
+
+# Convention "relative update" (BUG-931, ITG-INC-11, DEC-13): an UPDATE of item_tags whose
+# SET computes the counter from the stored column (`usage_count = usage_count + / - ...`);
+# for the decrease, the same statement's WHERE also tests the stored column (`usage_count >`).
+_REL_INC = re.compile(r"SET\s+usage_count\s*=\s*\(?\s*(?:item_tags\.)?usage_count\s*\+", re.IGNORECASE)
+_REL_DEC = re.compile(r"SET\s+usage_count\s*=\s*\(?\s*(?:item_tags\.)?usage_count\s*-", re.IGNORECASE)
+_DEC_GUARD = re.compile(r"WHERE.*usage_count\s*>", re.IGNORECASE | re.DOTALL)
+
 
 # Convention "order_part": the text of `sql` after `ORDER BY` ("" when there is none)
 def order_part_of(sql):
@@ -1103,7 +1115,8 @@
     t1 = mk_tag(name="Hex Bolt", tag_code="hex_bolt", usage_count=3)
     db.execute(text("update item_tags set usage_count = 10 where id = :i"), {"i": t1.id})
 
-    result = dao.increment_usage_count(db, tag_id=t1.id, workspace_id=w1.id)
+    with StatementRecorder(db) as recorder:
+        result = dao.increment_usage_count(db, tag_id=t1.id, workspace_id=w1.id)
 
     # Then 1
     assert result is t1
@@ -1111,6 +1124,8 @@
     assert result.usage_count == 11
     # Then 3
     assert stored_count(db, t1) == 11
+    # Then 4
+    assert any(_REL_INC.search(s) for s in recorder.updates())
 
 
 # [claude] ITG-INC-12
@@ -1369,7 +1384,8 @@
     t1 = mk_tag(name="Hex Bolt", tag_code="hex_bolt", usage_count=3)
     db.execute(text("update item_tags set usage_count = 10 where id = :i"), {"i": t1.id})
 
-    result = dao.decrement_usage_count(db, tag_id=t1.id, workspace_id=w1.id)
+    with StatementRecorder(db) as recorder:
+        result = dao.decrement_usage_count(db, tag_id=t1.id, workspace_id=w1.id)
 
     # Then 1
     assert result is t1
@@ -1377,6 +1393,8 @@
     assert result.usage_count == 9
     # Then 3
     assert stored_count(db, t1) == 9
+    # Then 4
+    assert any(_REL_DEC.search(s) and _DEC_GUARD.search(s) for s in recorder.updates())
 
 
 # [claude] ITG-DEC-14
```

  Matching cases change in `tests/unit/dao/item_tag.cases.md`: ITG-INC-11 and ITG-DEC-13 get
  the When wrapped in the statement recorder and a Then 4 — "statement recorder: one UPDATE of
  `item_tags` sets `usage_count` from the stored column (`usage_count + ...`)" and, for DEC-13,
  "(`usage_count - ...`) and its WHERE tests `usage_count >`". Add "relative update" to the
  Conventions next to "Statement recorder". The diff applies cleanly to the current file
  (`git apply --check`); the file is CRLF, so apply with `--ignore-whitespace`.

