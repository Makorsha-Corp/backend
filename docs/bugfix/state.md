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
