# Bug-fix pipeline: batch state

See `docs/bugfix/pipeline.md`. One row per fix unit.

| Unit | File | Bugs | Risk | Status | Date |
|---|---|---|---|---|---|
| dao-order_template | `app/dao/order_template.py` | BUG-1210, BUG-1211 | trivial | merged (PR #5, 2026-11-27) | 2026-11-27 |
| dao-attachment_link | `app/dao/attachment_link.py` | BUG-1432, BUG-1433, BUG-1434 | normal | merged (PR #7, 2026-11-27) | 2026-11-27 |
| dao-work_order_template | `app/dao/work_order_template.py` | BUG-2330, BUG-2331, BUG-2332 | normal | merged (PR #8, 2026-11-27) | 2026-11-27 |
| dao-factory_section | `app/dao/factory_section.py`, `app/managers/factory_section_manager.py` (two-file unit) | BUG-903, BUG-904, BUG-905 | normal | branch-pushed (batch 2, baseline f27d6ca; two-file unit; impact-1 APPROVE, no contract change; flip check CLEAN 16/16; commit cab794a; pr.md written, gh not logged in; not auto-merge: normal risk) | 2026-11-27 |
| dao-item_tag | `app/dao/item_tag.py` | BUG-929, BUG-930, BUG-931 | normal | branch-pushed (batch 2; flip check CLEAN, 11 flipped; `10ac8de` on bugfix/dao-item_tag; pr.md written, PR not opened; not trivial) | 2026-11-27 |
| dao-machine_maintenance_log | `app/dao/machine_maintenance_log.py` | BUG-1100, BUG-1101, BUG-1102 | normal | branch-pushed (flip check CLEAN vs f27d6ca, 46 flipped, G-21/22 still xfailed for BUG-1150; commit 5966805; pr.md ready, PR not opened; not auto-merge) | 2026-11-27 |
| dao-account_tag | `app/dao/account_tag.py` | BUG-1482, BUG-1483, BUG-1484, BUG-1485 | normal | prechecked (batch 3; 14 targets; BUG-1484 conditional keep: wrong-tests.md relative-UPDATE diff must be on origin/main before the batch-3 baseline, else drop it (11 targets); worktree not created) | 2026-11-27 |
| dao-machine | `app/dao/machine.py` | BUG-886, BUG-887, BUG-888, BUG-889, BUG-890, BUG-891, BUG-892 | normal | prechecked (batch 3; 60 targets; BUG-886 conditional keep: wrong-tests.md enum-input diff for 3 caller tests must be on origin/main before the baseline, else drop it (35 targets); BUG-342/343 out of scope; worktree not created) | 2026-11-27 |
| dao-help_ticket | `app/dao/help_ticket.py` | BUG-1441, BUG-1442, BUG-1443 | normal | prechecked (batch 3; 13 targets; BUG-1440 skipped (no test; "retry" conflicts with spec R4, needs lock-vs-retry decision and a race test); BUG-1441 conditional keep: wrong-tests.md `create=True` patch diff must be on origin/main before the baseline, else drop it; worktree not created) | 2026-11-27 |
