# Bug-fix pipeline: batch state

See `docs/bugfix/pipeline.md`. One row per fix unit.

| Unit | File | Bugs | Risk | Status | Date |
|---|---|---|---|---|---|
| dao-order_template | `app/dao/order_template.py` | BUG-1210, BUG-1211 | trivial | merged (PR #5, 2026-11-27) | 2026-11-27 |
| dao-attachment_link | `app/dao/attachment_link.py` | BUG-1432, BUG-1433, BUG-1434 | normal | pr-open (branch pushed, commit 11db000; flip check CLEAN, 12 flipped; gh not logged in: owner opens PR from pr.md; no frontend change) | 2026-11-27 |
| dao-work_order_template | `app/dao/work_order_template.py` | BUG-2330, BUG-2331, BUG-2332 | normal | pr-open (branch pushed bugfix/dao-work_order_template @ 23cb9e5; gh not logged in, owner opens PR from docs/bugfix/units/dao-work_order_template/pr.md; flip check CLEAN, 9 flipped; follow-up: log manager section-fallback bug, see impact-1.md) | 2026-11-27 |
