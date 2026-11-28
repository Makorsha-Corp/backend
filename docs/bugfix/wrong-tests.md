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

## BUG-1441: the help ticket clock helpers break when the fix drops the unused `datetime` import

**Applied 2026-11-27 on getabidallabib/mak-107-test-checklists (test files and cases text); outcomes of the 6 changed files unchanged (825 passed, 300 xfailed, 1 xpassed before and after). Needs to be on origin/main before the batch-3 baseline.** **Status: proposed 2026-11-27 by the tester's pre-check (batch 3); conditional keep: BUG-1441 stays
in unit dao-help_ticket only if the diff lands on `origin/main` before the batch-3 baseline.**
Otherwise BUG-1441 is skipped this round. The correction changes no check and no outcome today.

- **Unit:** `dao-help_ticket`.
- **Tests:** every test that runs under the `clock` helper of three files: in
  `tests/unit/dao/test_help_ticket.py` all CW cards (HLP-CW-01 … CW-15, target CW-03); in
  `tests/unit/services/test_help_ticket_service.py` the C cards (HTS-C-01 … C-04, C-10, C-11, target
  C-05); in `tests/unit/managers/test_help_ticket_manager.py` HTM-C-01 … C-07.
- **Why it's wrong:** the checks are right. Bug row BUG-1441 Intended: "The year comes from
  `utcnow()`"; spec `create_with_user` R2: "The year is the current year in UTC (`utcnow().year`)".
  The helpers patch `app.dao.help_ticket.utcnow` with `create=True` (right: the module does not
  import it today), but patch `app.dao.help_ticket.datetime` **without** `create=True`. Today
  `datetime` is used only on the line BUG-1441 replaces, so the clean fix
  (`from app.utils.time import utcnow`, the unused `from datetime import datetime` removed) makes
  `mock.patch` raise `AttributeError: ... does not have the attribute 'datetime'` in every clock test.
  Measured with a scratch plugin swapping the candidate in (no `app/` edit), on
  `bf_dao_help_ticket_test`, the 3 files plus `tests/test_help_tickets.py` and
  `tests/test_help_platform.py`: the clean fix gives 33 failed (25 passing tests break, plus the
  targets); the same fix that keeps the unused import gives exactly the 13 targets flipping.
  The spec does not ask the module to keep a `datetime` name; the test constrains how the fix is
  written, not what it does.
- **Proposed correction** (one argument in each helper; checked: today 440 passed / 78 xfailed,
  unchanged; with the clean fix and with the keep-import fix, exactly the 13 BUG-1441/1442/1443 tests
  flip and nothing else changes; `git apply --check` OK):

```diff
--- a/tests/unit/dao/test_help_ticket.py
+++ b/tests/unit/dao/test_help_ticket.py
@@ -143,7 +143,7 @@ def clock(local, utc):
         def now(cls, tz=None):
             return local
 
-    with mock.patch("app.dao.help_ticket.datetime", _Clock), \
+    with mock.patch("app.dao.help_ticket.datetime", _Clock, create=True), \
             mock.patch("app.dao.help_ticket.utcnow", create=True, return_value=utc), \
             mock.patch("app.utils.time.utcnow", return_value=utc):
         yield
--- a/tests/unit/managers/test_help_ticket_manager.py
+++ b/tests/unit/managers/test_help_ticket_manager.py
@@ -243,7 +243,7 @@ def _fixed_datetime(now_value):
 @contextmanager
 def clock():
     with (
-        patch("app.dao.help_ticket.datetime", _fixed_datetime(FIXED)),
+        patch("app.dao.help_ticket.datetime", _fixed_datetime(FIXED), create=True),
         patch("app.dao.help_ticket.utcnow", create=True, return_value=FIXED),
         patch("app.utils.time.utcnow", return_value=FIXED),
     ):
--- a/tests/unit/services/test_help_ticket_service.py
+++ b/tests/unit/services/test_help_ticket_service.py
@@ -260,7 +260,7 @@ def _fixed_datetime(now_value):
 @contextmanager
 def clock(now=FIXED, utc=FIXED):
     with (
-        patch("app.dao.help_ticket.datetime", _fixed_datetime(now)),
+        patch("app.dao.help_ticket.datetime", _fixed_datetime(now), create=True),
         patch("app.dao.help_ticket.utcnow", create=True, return_value=utc),
         patch("app.utils.time.utcnow", return_value=utc),
     ):
```

  Matching cases text: in `tests/unit/dao/help_ticket.cases.md` (Externals, clock(L, U)),
  `tests/unit/services/help_ticket_service.cases.md` (clock convention and HTS-C-05 step 2) and
  `tests/unit/managers/help_ticket_manager.cases.md` (clock convention), "patch
  `app.dao.help_ticket.datetime` with a subclass" becomes "patch `app.dao.help_ticket.datetime`
  (`create=True`) with a subclass". Lesson for the test designer: when a clock bug's fix replaces
  the patched name, patch both the old and the new name with `create=True`.

## BUG-1484: ATG-INC-06 and ATG-DEC-08 (right check, but a racy shortcut passes them; same gap as BUG-931)

**Applied 2026-11-27 on getabidallabib/mak-107-test-checklists (test files and cases text); outcomes of the 6 changed files unchanged (825 passed, 300 xfailed, 1 xpassed before and after). Needs to be on origin/main before the batch-3 baseline.** **Status: proposed 2026-11-27 by the tester's pre-check (batch 3); conditional keep:** BUG-1484 stays in
unit dao-account_tag **only if** this diff is on `origin/main` before the batch-3 baseline is recorded;
otherwise BUG-1484 is skipped this round (remove it from `brief.md`, re-run the firewall). The diff only
adds a check; today's outcome is unchanged.

- **Unit:** `dao-account_tag` (pre-check 2026-11-27).
- **Tests:** `test_atg_inc_06__the_increase_applies_to_the_stored_value_not_the_loaded_one`,
  `test_atg_dec_08__the_decrease_applies_to_the_stored_value_not_the_loaded_one`
  (and, unchanged, `test_atg_dec_09__the_not_below_0_check_uses_the_stored_value_stored_0_stays_0`),
  in `tests/unit/dao/test_account_tag.py`.
- **Why it's incomplete:** the bug row's Intended is "Applied in the database relative to the stored
  value (`usage_count + 1`; `- 1` only where above 0), returned tag shows the stored result; no row lock
  (per BUG-931 ...)", and spec P3 says "changed in the database in one step". The tests check spec
  `increment_usage_count` R5 / `decrement_usage_count` R6 with a stale object in one session (loaded 3,
  stored 10 → 11 / 9; stored 0 → 0). That is right and a correct fix passes it, but the
  refresh-then-write shortcut (`db.refresh(tag, ["usage_count"]); tag.usage_count += 1; db.flush()`)
  passes all three tests and the rest of the unit's and callers' files, while two concurrent requests
  still both read 5 and write 6 (spec P3's example). Measured on `bf_dao_account_tag_test` with the
  candidates patched in by a scratch plugin (no `app/` edit): over the DAO file, the service file and
  every caller file, the shortcut's outcomes are identical to a correct fix's.
- **Proposed correction** (mirrors the applied BUG-931 correction; one new Then per test, a SQL-text check
  on the UPDATE the call sends; accepts ORM `query.update(...)`, Core `update(...)` and raw `text()`
  forms, and does not require the UPDATE to be the only statement). Checked with the patched file on
  `bf_dao_account_tag_test`, all 20 counter tests: Core `update().returning()` + `set_committed_value`
  → 20 pass; ORM `query.update(..., synchronize_session=False)` + `refresh` → 20 pass; the
  refresh-then-write shortcut → INC-06 and DEC-08 fail on Then 4; today's code → INC-06, DEC-08,
  DEC-09 still fail on Then 2, as the cards say. `git apply --check` is clean (the file is LF).

```diff
--- a/tests/unit/dao/test_account_tag.py
+++ b/tests/unit/dao/test_account_tag.py
@@ -8,6 +8,7 @@ Built in normal mode (no local model): every test sits below a `# [claude] <ID>`
 comment.
 """
 # ruff: noqa: SIM117  (Conventions prescribe `with pytest.raises(...)` around `with db.begin_nested():`)
+import re
 from unittest.mock import patch
 
 import pytest
@@ -186,6 +187,9 @@ class StatementRecorder:
     def written(self):
         return [s for s in self.statements if s.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE"))]
 
+    def updates(self):
+        return [s for s in self.statements if s.lstrip().upper().startswith("UPDATE")]
+
     def sql(self):
         """The one SELECT from `account_tags`; fails loudly unless there is exactly one."""
         [statement] = [
@@ -194,6 +198,14 @@ class StatementRecorder:
         return statement
 
 
+# Convention "relative update" (BUG-1484, ATG-INC-06, DEC-08): an UPDATE of account_tags whose
+# SET computes the counter from the stored column (`usage_count = usage_count + / - ...`);
+# for the decrease, the same statement's WHERE also tests the stored column (`usage_count >`).
+_REL_INC = re.compile(r"SET\s+usage_count\s*=\s*\(?\s*(?:account_tags\.)?usage_count\s*\+", re.IGNORECASE)
+_REL_DEC = re.compile(r"SET\s+usage_count\s*=\s*\(?\s*(?:account_tags\.)?usage_count\s*-", re.IGNORECASE)
+_DEC_GUARD = re.compile(r"WHERE.*usage_count\s*>", re.IGNORECASE | re.DOTALL)
+
+
 # Convention "order_part": the text of `sql` after ORDER BY ("" when there is none)
 def order_part_of(sql):
     return sql.split("ORDER BY", 1)[1] if "ORDER BY" in sql else ""
@@ -835,7 +847,8 @@ def test_atg_inc_06__the_increase_applies_to_the_stored_value_not_the_loaded_one
     t1 = mk_tag(name="Supplier", tag_code="supplier", usage_count=3)
     db.execute(text("UPDATE account_tags SET usage_count = 10 WHERE id = :i"), {"i": t1.id})
 
-    result = dao.increment_usage_count(db, tag_id=t1.id, workspace_id=w1.id)
+    with StatementRecorder(db) as recorder:
+        result = dao.increment_usage_count(db, tag_id=t1.id, workspace_id=w1.id)
 
     # Then 1
     assert result is t1
@@ -843,6 +856,8 @@ def test_atg_inc_06__the_increase_applies_to_the_stored_value_not_the_loaded_one
     assert result.usage_count == 11
     # Then 3
     assert stored_count(db, t1) == 11
+    # Then 4
+    assert any(_REL_INC.search(s) for s in recorder.updates())
 
 
 # [claude] ATG-INC-07
@@ -1030,7 +1045,8 @@ def test_atg_dec_08__the_decrease_applies_to_the_stored_value_not_the_loaded_one
     t1 = mk_tag(name="Supplier", tag_code="supplier", usage_count=3)
     db.execute(text("UPDATE account_tags SET usage_count = 10 WHERE id = :i"), {"i": t1.id})
 
-    result = dao.decrement_usage_count(db, tag_id=t1.id, workspace_id=w1.id)
+    with StatementRecorder(db) as recorder:
+        result = dao.decrement_usage_count(db, tag_id=t1.id, workspace_id=w1.id)
 
     # Then 1
     assert result is t1
@@ -1038,6 +1054,8 @@ def test_atg_dec_08__the_decrease_applies_to_the_stored_value_not_the_loaded_one
     assert result.usage_count == 9
     # Then 3
     assert stored_count(db, t1) == 9
+    # Then 4
+    assert any(_REL_DEC.search(s) and _DEC_GUARD.search(s) for s in recorder.updates())
 
 
 # [claude] ATG-DEC-09
```

  Matching cases change in `tests/unit/dao/account_tag.cases.md`: ATG-INC-06 and ATG-DEC-08 get the
  When wrapped in the statement recorder and a Then 4 — "statement recorder: one UPDATE of
  `account_tags` sets `usage_count` from the stored column (`usage_count + ...`)" and, for DEC-08,
  "(`usage_count - ...`) and its WHERE tests `usage_count >`". Add "relative update" to the
  Conventions next to "Statement recorder".

## BUG-886: MCM-S-12, MCM-S-39 and MCS-L-12 (right check, but the input is a plain string, not the enum)

**Applied 2026-11-27 on getabidallabib/mak-107-test-checklists (test files and cases text); outcomes of the 6 changed files unchanged (825 passed, 300 xfailed, 1 xpassed before and after). Needs to be on origin/main before the batch-3 baseline.** **Status: proposed 2026-11-27 by the tester's pre-check (batch 3)** (changes one argument in three
strict tests; today's outcome is unchanged). BUG-886 stays in unit dao-machine **only if** this diff
is on `origin/main` before the batch-3 baseline is recorded; otherwise these three tests would stay
red after a correct fix, so BUG-886 must be skipped this round.

- **Unit:** `dao-machine` (pre-check 2026-11-27).
- **Tests:** `test_mcm_s_12__latest_event_type_is_handed_to_the_list`,
  `test_mcm_s_39__latest_event_type_works_on_the_maintenance_path`
  (`tests/unit/managers/test_machine_manager.py`) and
  `test_mcs_l_12__pass_through_bug_886_latest_event_type_filters_the_list`
  (`tests/unit/services/test_machine_service.py`).
- **Why it's wrong:** the bug row's Intended is "The filter returns the machines whose latest
  `status_updated` activity row has that status". The DAO spec types the input as
  `latest_event_type: MachineEventTypeEnum | None`; the manager spec (`search_machines` inputs:
  "as machine DAO `search_advanced` … handed to it unchanged") and the service spec (`get_machines`
  signature, `MachineEventTypeEnum | None`) say the same, and `GET /machines/` parses the query value
  into that enum. These three tests pass the plain string `"IDLE"` instead. A correct DAO fix that
  keeps today's `latest_event_type.value` (the obvious minimal change: replace `.astext` with
  `.as_string()` and add the `id` tie-break) then fails all three with
  `AttributeError: 'str' object has no attribute 'value'`, while every one of the 22 DAO tests (which
  pass the enum) and the rest of the manager and service files pass. So they test an input outside
  the contract, and the fixer cannot see why. The other BUG-886 checks in the same files are right.
  The cards also say "Fails today on: Then 1 (the call raises AttributeError: the query cannot be
  built)", which still holds after the correction (`.astext`).
- **Checked** on `bf_dao_machine_test` (correction applied temporarily, then reverted; no `app/`
  edit): today's code → 3 xfailed (AttributeError on `.astext`, as the cards say); a correct
  candidate fix through a scratch plugin → all 3 pass. `test_mcm_s_…` line 5775
  (`include_deleted=True` with `latest_event_type="IDLE"`) is a BUG-957 test whose path ignores
  the filter; it is not changed here.
- **Proposed correction** (both files already import the enum and define `IDLE = MachineEventTypeEnum.IDLE`):

```diff
--- a/tests/unit/managers/test_machine_manager.py
+++ b/tests/unit/managers/test_machine_manager.py
@@ -4576,7 +4576,7 @@ def test_mcm_s_12__latest_event_type_is_handed_to_the_list(db, w1, mk_machine, m
     mz = mk_machine("MZ")
     mk_status_row(ma, T1, "IDLE")
     mk_status_row(mz, T1, "RUNNING")
-    result = M.search_machines(db, workspace_id=w1.id, latest_event_type="IDLE")
+    result = M.search_machines(db, workspace_id=w1.id, latest_event_type=IDLE)
 
     # Then 1
     assert names(result) == ["Alpha"]
@@ -4924,7 +4924,7 @@ def test_mcm_s_39__latest_event_type_works_on_the_maintenance_path(db, w1, mk_ma
     mz = mk_machine("MZ")
     mk_status_row(ma, T1, "IDLE")
     mk_status_row(mz, T1, "RUNNING")
-    result = M.search_machines(db, workspace_id=w1.id, latest_event_type="IDLE", maintenance_window="bogus")
+    result = M.search_machines(db, workspace_id=w1.id, latest_event_type=IDLE, maintenance_window="bogus")
 
     # Then 1
     assert names(result) == ["Alpha"]
--- a/tests/unit/services/test_machine_service.py
+++ b/tests/unit/services/test_machine_service.py
@@ -1252,7 +1252,7 @@ def test_mcs_l_12__pass_through_bug_886_latest_event_type_filters_the_list(db, w
     mk_status(ma, T1, "IDLE")
     mk_status(mz, T1, "RUNNING")
     commit_point(db)
-    result = svc.get_machines(db, workspace_id=w1.id, latest_event_type="IDLE")
+    result = svc.get_machines(db, workspace_id=w1.id, latest_event_type=IDLE)
 
     # Then 1
     assert names(result) == ["Alpha"]
```

  Matching cases change: in `tests/unit/managers/machine_manager.cases.md` MCM-S-12 and MCM-S-39,
  and in `tests/unit/services/machine_service.cases.md` MCS-L-12, the When's
  `latest_event_type="IDLE"` becomes `latest_event_type=IDLE` (the enum member, per the
  conventions' `IDLE = MachineEventTypeEnum.IDLE`). Both test files are LF.

## BUG-655: LED-RINV-06 (setup does not match its card) and LED-RINV-12 (marker names one bug, the test needs three)

**Status: proposed 2026-11-28 by the tester's pre-check** (one setup line and one marker reason;
today's outcome is unchanged, both still fail on the `AttributeError`). BUG-655 stays in unit
dao-inventory_ledger **only if** this diff is on `origin/main` before the batch-5 baseline is
recorded; otherwise BUG-655 is skipped this round (BUG-885 goes ahead either way).

- **Unit:** `dao-inventory_ledger` (pre-check 2026-11-28).
- **Tests:** `test_led_rinv_06__no_snapshot_nonzero_ledger_error`,
  `test_led_rinv_12__adjusted_with_history`, in `tests/unit/managers/test_ledger_manager.py`.
  The other 19 BUG-655 tests (8 DAO, 5 manager, 2 service single-tagged; 4 dual-tagged that keep their markers) are right.
- **LED-RINV-06, why it's wrong:** the card's Given is "RI-hist **without S**" and the check is
  spec `reconcile_inventory` R5 ("No live snapshot and ledger quantity ≠ 0 → same error dict ...;
  no snapshot created or restored") reached through R1 [BUG-655]. The test uses the `ri_hist`
  setup as it is, which **creates** the live snapshot S (qty 10 @ 2.00), and never removes it. With
  a correct BUG-655 fix patched in (no `app/` edit) the call returns
  `{"status": "adjusted", "ledger_qty": 15, "snapshot_qty": 10, "discrepancy": 5, ...}` and the
  "no `inventory` row" check fails too, so stage C would remove the marker and the test would fail.
  With S deleted first, the same test fails today on the `AttributeError` and passes with the fix
  (measured on `bf_dao_inventory_ledger_test`).
- **LED-RINV-12, why it's wrong:** what it checks is right (spec `reconcile_inventory` R3, R9,
  R9a, R9b, R10, R1; its card's Rules column says "[BUG-655, BUG-651, BUG-652]"), but its strict
  marker names only BUG-655 (card: "xfail BUG-655"). R9a / R9b are BUG-651 ("quantity = 0;
  qty_before = the ledger quantity"; notes end with the avg-price sentence) and R10's `updated_by`
  is BUG-652, both in `app/managers/ledger_manager.py`, out of this unit. With a correct BUG-655 fix
  patched in, the test gets past the balance and fails on `updated_by == U2` (BUG-652), then would
  fail on `quantity == 0` (BUG-651). Same shape as the BUG-1101 entry above.
- **Proposed correction:**

```diff
--- a/tests/unit/managers/test_ledger_manager.py
+++ b/tests/unit/managers/test_ledger_manager.py
@@ -1626,6 +1626,8 @@
 def test_led_rinv_06__no_snapshot_nonzero_ledger_error(db, M, ri_hist, f1, i1, w1, u2):
     """LED-RINV-06 — ledger history without a snapshot should report the error dict.
     Rules: reconcile_inventory R5, R1 [BUG-655]."""
+    db.delete(ri_hist["snap"])  # card Given: "RI-hist without S"
+    db.flush()
     result = rinv(db, M, f1, i1, STORAGE, w1, u2)
     assert result == {
         "status": "error", "ledger_qty": 15, "snapshot_qty": 0, "discrepancy": 15,
@@ -1727,7 +1729,7 @@
     assert row.total_cost == Decimal("0.00")
 
 
-@pytest.mark.xfail(strict=True, reason=BUG_655)
+@pytest.mark.xfail(strict=True, reason=f"{BUG_655.split(':')[0]}, {BUG_651.split(':')[0]}, {BUG_652.split(':')[0]}: needs all three fixes")
 def test_led_rinv_12__adjusted_with_history(db, M, ri_hist, f1, i1, w1, u1, u2):
     """LED-RINV-12 — a full correction with ledger history (qty + avg_price + notes).
     Rules: reconcile_inventory R3, R9, R9a, R9b, R10, R1 [BUG-655, BUG-651, BUG-652]."""
```

  Matching cases change in `tests/unit/managers/ledger_manager.cases.md`: LED-RINV-06 unchanged
  (the card is right); LED-RINV-12 `xfail BUG-655 — fails today on: raises AttributeError` becomes
  `xfail BUG-655, BUG-651, BUG-652 — fails today on: raises AttributeError (after BUG-655:
  updated_by == U1, quantity == 5)`. The test file is LF.

## BUG-664: INVM-SO-18 and INVM-SI-15 (the "new ledger row" is picked by id, but the tie setup gives a seeded row a higher id)

**Status: proposed 2026-11-28 by the tester's pre-check (round 2 of unit dao-inventory_ledger,
scope widened with the inventory half of BUG-641 / BUG-664 / BUG-803).** Two lines per test; today's
outcome is unchanged (both still fail strict, on the sync line their cards name), so a baseline
recorded before or after the diff gives the same outcome for them. BUG-664 stays in the unit
**only if** this diff is on `origin/main` and in `bugfix/dao-inventory_ledger` before the tester's
stage C; otherwise these two tests keep their markers and are reported as expected leftovers
(the flip check will list them as rejections, see the unit's `tester-precheck.md`, round 2).

- **Unit:** `dao-inventory_ledger` (pre-check round 2, 2026-11-28).
- **Tests:** `test_invm_so_18__tied_ledger_rows_sync_from_wrong_row`,
  `test_invm_si_15__tied_ledger_rows_sync_from_wrong_row`, in
  `tests/unit/managers/test_inventory_movements.py`. The other BUG-664 / BUG-803 inventory tests
  (INV-SY-17, LED-LE-06, PRI-P-47) are right.
- **Why it's wrong:** what the cards check is right. Spec `_storage_out` R3a [BUG-664]: "The bucket
  row's `qty` and `avg_price` are then set from the newest ledger row for that bucket ... 'newest' =
  greatest `performed_at`, ties broken by greatest `id`"; bug row BUG-664 intended: "'Latest' ordered by
  `performed_at` descending, then `id` descending". The cards (SO-18, SI-15) expect "new ledger row
  `qty_before 10` ...". But the test reads the new row as `ledger_rows(...)[-1]`, and `ledger_rows`
  orders by `id` ascending. The tie setup gives row C an explicit id of `nextval + 1_000_000`, so the
  row the movement writes (next sequence value) has a **smaller** id than C, and `[-1]` is C (seeded with
  `qty_before 0`). With a correct fix simulated (scratch plugin that patches `InventoryLedgerDAO`
  with `ORDER BY performed_at DESC, id DESC`; no `app/` edit), the result and the bucket checks pass and
  both tests fail on `assert 0 == 10` (`new.qty_before`). No correct fix can make them pass.
- **Proposed correction** (pick the row the movement wrote as the one that was not there before;
  `git apply --check` clean on 092776b. Patched copy measured on `bf_dao_inventory_ledger_test`:
  today both still fail on the card's line (`Decimal('4.50') == Decimal('5.00')`, bucket `22 == 20`,
  i.e. synced from row B), with the simulated fix both pass, and no other test in the file changes):

```diff
--- a/tests/unit/managers/test_inventory_movements.py
+++ b/tests/unit/managers/test_inventory_movements.py
@@ -1031,12 +1031,13 @@
                   row_id=c_id)
     mk_inv_ledger(db, workspace_id=w1.id, factory_id=f1.id, item_id=i1.id, inv_type=STORAGE,
                   qty_after=15, avg_after=Decimal("4.00"), performed_by_id=u2.id, performed_at=T0)
+    seeded = {row.id for row in ledger_rows(db, w1.id, f1.id, i1.id, STORAGE)}
     result = _storage_out(db, factory_id=f1.id, item_id=i1.id, qty=5, **so_kwargs(w1, u1))
     assert result == Decimal("5.00")
     r = reread_inventory(db, bucket.id)
     assert r.qty == 5
     assert r.avg_price == Decimal("5.00")
-    new = ledger_rows(db, w1.id, f1.id, i1.id, STORAGE)[-1]
+    [new] = [row for row in ledger_rows(db, w1.id, f1.id, i1.id, STORAGE) if row.id not in seeded]
     assert new.qty_before == 10
     assert new.qty_after == 5
     assert new.unit_cost == Decimal("5.00")
@@ -1377,13 +1378,14 @@
                   row_id=c_id)
     mk_inv_ledger(db, workspace_id=w1.id, factory_id=f1.id, item_id=i1.id, inv_type=STORAGE,
                   qty_after=15, avg_after=Decimal("4.00"), performed_by_id=u2.id, performed_at=T0)
+    seeded = {row.id for row in ledger_rows(db, w1.id, f1.id, i1.id, STORAGE)}
     result = _storage_in(db, factory_id=f1.id, item_id=i1.id, qty=10, unit_cost=Decimal("7.00"),
                           **si_kwargs(w1, u1))
     assert result is None
     r = reread_inventory(db, bucket.id)
     assert r.qty == 20
     assert r.avg_price == Decimal("6.00")
-    new = ledger_rows(db, w1.id, f1.id, i1.id, STORAGE)[-1]
+    [new] = [row for row in ledger_rows(db, w1.id, f1.id, i1.id, STORAGE) if row.id not in seeded]
     assert new.qty_before == 10
     assert new.avg_price_before == Decimal("5.00")
     assert new.avg_price_after == Decimal("6.00")
```

  The cards in `tests/unit/managers/inventory_movements.cases.md` are right and stay unchanged; the
  executor notes could add one line: "with an explicit high id in the setup, the new row is the one not
  seeded, not the last by id". The test file is LF, ASCII.
