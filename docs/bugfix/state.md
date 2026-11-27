# Bug-fix pipeline: batch state

See `docs/bugfix/pipeline.md`. One row per fix unit.

| Unit | File | Bugs | Risk | Status | Date |
|---|---|---|---|---|---|
| dao-order_template | `app/dao/order_template.py` | BUG-1210, BUG-1211 | trivial | merged (PR #5, 2026-11-27) | 2026-11-27 |
| dao-attachment_link | `app/dao/attachment_link.py` | BUG-1432, BUG-1433, BUG-1434 | normal | merged (PR #7, 2026-11-27) | 2026-11-27 |
| dao-work_order_template | `app/dao/work_order_template.py` | BUG-2330, BUG-2331, BUG-2332 | normal | merged (PR #8, 2026-11-27) | 2026-11-27 |
| dao-factory_section | `app/dao/factory_section.py`, `app/managers/factory_section_manager.py` (two-file unit) | BUG-903, BUG-904, BUG-905 | normal | prechecked (batch 2; no wrong tests; re-scoped 2026-11-27 to a two-file unit: DAO fix plus `include_deleted` pass-through in the manager factory branch of `search_factory_sections`, per tester-precheck.md option 1; brief updated, firewall clean) | 2026-11-27 |
| dao-item_tag | `app/dao/item_tag.py` | BUG-929, BUG-930, BUG-931 | normal | prechecked (batch 2; BUG-931 needs the ITG-INC-11/DEC-13 relative-UPDATE diff in wrong-tests.md on main before the baseline, else skip BUG-931) | 2026-11-27 |
| dao-machine_maintenance_log | `app/dao/machine_maintenance_log.py` | BUG-1100, BUG-1101, BUG-1102 | normal | prechecked (batch 2; BUG-1101 needs the MMLM-G-21/G-22 marker diff in wrong-tests.md on main before the baseline) | 2026-11-27 |
