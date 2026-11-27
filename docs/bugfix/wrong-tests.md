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

