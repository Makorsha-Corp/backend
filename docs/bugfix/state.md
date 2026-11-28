# Bug-fix pipeline: batch state

See `docs/bugfix/pipeline.md`. One row per fix unit.

| Unit | File | Bugs | Risk | Status | Date |
|---|---|---|---|---|---|
| dao-order_template | `app/dao/order_template.py` | BUG-1210, BUG-1211 | trivial | merged (PR #5, 2026-11-27) | 2026-11-27 |
| dao-attachment_link | `app/dao/attachment_link.py` | BUG-1432, BUG-1433, BUG-1434 | normal | merged (PR #7, 2026-11-27) | 2026-11-27 |
| dao-work_order_template | `app/dao/work_order_template.py` | BUG-2330, BUG-2331, BUG-2332 | normal | merged (PR #8, 2026-11-27) | 2026-11-27 |
| dao-factory_section | `app/dao/factory_section.py`, `app/managers/factory_section_manager.py` (two-file unit) | BUG-903, BUG-904, BUG-905 | normal | merged (batch 2, baseline f27d6ca; two-file unit; impact-1 APPROVE, no contract change; flip check CLEAN 16/16; commit cab794a; pr.md written, gh not logged in; not auto-merge: normal risk) | 2026-11-27 |
| dao-item_tag | `app/dao/item_tag.py` | BUG-929, BUG-930, BUG-931 | normal | merged (batch 2; flip check CLEAN, 11 flipped; `10ac8de` on bugfix/dao-item_tag; pr.md written, PR not opened; not trivial) | 2026-11-27 |
| dao-machine_maintenance_log | `app/dao/machine_maintenance_log.py` | BUG-1100, BUG-1101, BUG-1102 | normal | merged (flip check CLEAN vs f27d6ca, 46 flipped, G-21/22 still xfailed for BUG-1150; commit 5966805; pr.md ready, PR not opened; not auto-merge) | 2026-11-27 |
| dao-account_tag | `app/dao/account_tag.py` | BUG-1482, BUG-1483, BUG-1484, BUG-1485 | normal | merged (PR #17; batch 3; flip check CLEAN 14/14 vs 614bbce; code review PASS 0/0/2 minors; commit 1846be7; pr.md ready) | 2026-11-27 |
| dao-machine | `app/dao/machine.py` | BUG-886, BUG-887, BUG-888, BUG-889, BUG-890, BUG-891, BUG-892 | normal | merged (PR #19; batch 3; flip check CLEAN 60/60 vs 614bbce; code review PASS 0/0/0, 3 nits; commit 83f4adf; pr.md ready) | 2026-11-27 |
| dao-help_ticket | `app/dao/help_ticket.py` | BUG-1441, BUG-1442, BUG-1443 | normal | merged (PR #16; batch 3; flip check CLEAN 13/13 vs 614bbce; code review PASS 0/0/1 minor; commit 7a24870; pr.md ready) | 2026-11-27 |
| dao-item_tag-2 | `app/dao/item_tag.py` | BUG-3302 | normal | branch-pushed (code review PASS 0/0/1 minor fixed in 24c6843) tested CLEAN (batch 4; new test ITG-DEC-16 is the target and passes, every other test unchanged, 34 non-strict ties ignored; `8502901` on bugfix/dao-item_tag-2, not pushed; pr.md written; awaiting code review) | 2026-11-27 |
| dao-machine_section_assignment | `app/dao/machine_section_assignment.py` | BUG-906, BUG-909 | normal | branch-pushed (code review PASS 0/0/1 minor, 2 nits) tested CLEAN (batch 4; flip check CLEAN vs 092776b, 8 flipped, 30 non-strict ties ignored; BUG-907 and BUG-971 tests still xfailed; commit 881a95c on bugfix/dao-machine_section_assignment, not pushed; pr.md written, code review pending) | 2026-11-27 |
| dao-machine_item | `app/dao/machine_item.py` | BUG-976, BUG-977, BUG-979, BUG-980, BUG-981, BUG-982 | normal | branch-pushed (code review PASS 0/0/0, 2 nits; batch 4; impact-1 APPROVE, no contract change; flip check CLEAN 36/36 vs 092776b; commit 253484f on bugfix/dao-machine_item, not pushed; pr.md written, code review pending; not auto-merge: normal risk) | 2026-11-27 |
| dao-workspace_invitation | `app/dao/workspace_invitation.py` | BUG-1401, BUG-1402 | normal | branch-pushed (code review PASS 0/0/1 minor) tested CLEAN (batch 4; flip check CLEAN vs 092776b, 13 flipped, 31 non-strict ties ignored; commit c6b9a87 on bugfix/dao-workspace_invitation, not pushed; pr.md written, code review pending) | 2026-11-27 |
| dao-waitlist | `app/dao/waitlist.py` | BUG-1410, BUG-1411 | normal | branch-pushed (code review PASS 0/0/0; batch 4; flip check CLEAN vs 092776b, 7 flipped; commit db3bb3f on bugfix/dao-waitlist, not pushed; pr.md written, code review pending) | 2026-11-27 |
