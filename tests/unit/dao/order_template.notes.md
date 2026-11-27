# Execution notes — `app/dao/order_template.py`

> Cases: `tests/unit/dao/order_template.cases.md` (Revision 1, READY, 74 cases) · Tests: `tests/unit/dao/test_order_template.py` · Source commit: e48a092
> Result: **74 tests for 74 cases — 67 passed · 7 xfail · 0 discrepancies · 0 errors** — branch coverage 100% line and branch (23 statements, 4 branches). The five non-strict cards may XPASS without turning the run red: `67 passed, 6 xfailed, 1 xpassed` (default) or `67 passed, 5 xfailed, 2 xpassed`.
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/dao/test_order_template.py -q -p no:cacheprovider`

## Who wrote what
Normal mode, no local model: every test sits below a `# [claude] <ID>` comment. The card bodies were transcribed by a throwaway parser of the cases file (not kept in the repo; `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\refx\gen.py`), so values are the card's own text. The fixtures and helpers were written by hand from the Conventions. A separate audit script (`check.py`) checked: each ID exactly once and in card order, title and rules in the docstring, `# Then 1..N` matching the card's Then count, every quoted literal of the Given, When and Then lines present, marker and bug matching the Expect line, no unused argument, no fixture used without being an argument. LF only.

## How the tests are built
- **Nothing is patched.**
- **Constants:** `dao`, `idao`, `MISSING`, `T9` to `T12`.
- **Standing rows:** `w1`, `w2`, through the autouse `standing_rows`.
- **Builders:** `mk_template(created_at=, **columns)` = "template"; `mk_line(template, line_number=, **columns)` = "line on T"; `mk_many_templates(count)` returns `newest`, `mk_many_lines(template, count)` returns `in_order`, both built with `add_all`.
- **`ids(result)`**; `stored_count(db)` is the pair of table counts, "nothing written".
- `recorder.sql()` is the one SELECT sent; `order_part_of(sql)` is the text after the first `ORDER BY` and before any `LIMIT`.
- **Database-error cards:** `with pytest.raises(...)` around `with db.begin_nested():`; that block is Then 1, and `as exc` is there only when a later line reads it.
- **Statement recorder:** `StatementRecorder(db)`, a `before_cursor_execute` listener on the session's connection, around the When only; `recorder.written()` is the card's `written`.
- **Row letters** of the cards are lower case in the code (`A` becomes `a`, `P` becomes `p`). A Given row no later line names is built without a variable (F841). Lines such as "W1 has no status" add no code.
- **Reading helpers (no expected values inside):** `snap(db, row)` is every column by a Core select, for "unchanged"; `reread(db, row)` is `db.expire_all()` then SELECT by id.

## xfail location (`--runxfail`, reading the failing value)
| Card | Strict | Fails on | Actual |
|---|---|---|---|
| OTP-GW-17 | no | Then 2, all 10 matrix runs | `assert [2701, 2702, 2700] == [2702, 2701, 2700]` |
| OTP-GW-18 | no | Then 2, all 10 matrix runs | `assert [2703, 2704, 2705] == [2705, 2704, 2703]`: physical order is the reverse of the intended one |
| OTP-GW-19 | no | Then 2, all 10 matrix runs | `assert [2707, 2707, 2709, 2710, 2706] == [2710, 2709, 2708, 2707, 2706]`: one row twice, one never, as the card says |
| OTP-GW-20 | yes | Then 4, every run | `assert '.id' in ' order_templates.created_at DESC \n '` |
| OTP-GT-08 | no | Then 2, default runs and plans 4, 5; XPASS on plans 1, 2, 3 | `assert [559, 560, 558] == [558, 559, 560]` |
| OTP-GT-09 | no | Then 2, only under the plugin below | XPASSED in every plain run, which the card's Fails line expects |
| OTP-GT-10 | yes | Then 4, every run | `assert '.id' in ' order_template_items.line_number'` |

**Proof of the lines past the failure point.** Plugin `refx_plug.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\refx` (`-p refx_plug`), which replaces the two list methods in-process; nothing in `app/`. The recorder sees the rewritten text here, so GW-20 and GT-10 move to the Then the wrong order breaks.

**Explicit wrong orders, `--runxfail`:**

| `get_by_workspace` order | `get_by_template` order | Cards that fail | Pass cards that fail |
|---|---|---|---|
| `created_at DESC, id` | `line_number, id DESC` | GW-17, 18, 19, GT-08, GT-09 on Then 2 (`assert [2453, 2452, 2451] == [2451, 2452, 2453]` for GT-09); GW-20, GT-10 on Then 6 | none |
| `created_at DESC, template_name` | `line_number, quantity` | the same five on Then 2; GW-20, GT-10 on Then 4 | none |
| `created_at DESC, is_active` | `line_number, unit_price` | GW-17, 18, 19, GT-09 on Then 2; GW-20, GT-10 on Then 4 | none |
| `created_at DESC, expense_category` | `line_number, quantity DESC` | GW-17, 18, 19, GT-09 on Then 2; GW-20, GT-10 on Then 4 | none |
| `created_at DESC, template_name DESC, id DESC` | `line_number, quantity, id` | the same five on Then 2; GW-20 on Then 6, GT-10 on Then 7 | none |

So every non-strict card can fail on its Then 2, and no pass card depends on the order among ties. With the markers on the first, second and last give `55 passed, 7 xfailed`; the two others `55 passed, 6 xfailed, 1 xpassed`.

**The intended order** (`REFX_MODE=fix`: `created_at DESC, id DESC` and `line_number, id`): with `--runxfail`, all 62 pass, so Then 5 to 7 of GW-20 and GT-10 hold. With the markers on, GW-20 and GT-10 are `XPASS(strict)` and the five non-strict cards XPASS.


## Discrepancies
None. No card was changed, no marker loosened, no test is marked DISCREPANCY.

Prose only, no test affected: GT-09 never failed without a plugin, in any of the 11 runs and 20 repeats, which its `Fails today on` line expects.


## Spec gaps of the cases file, checked
All assumed columns held: `description` on a line; `requires_approval`, `auto_approve` on a template; the line's module is `app.models.order_template_item`.

## Coverage gaps
None — 100% line and branch coverage.

Run with a private `COVERAGE_FILE`. Inherited `BaseDAO` methods live in `app/dao/base.py` and are measured by `tests/unit/dao/test_base.py`.

## Factories added
None.

## Stability
5 default runs and 5 forced plans, each `55 passed, 6 xfailed, 1 xpassed` (plans 1, 2, 3 of `enable_seqscan=off`, its join variant and `enable_hashjoin=off`: `55 passed, 5 xfailed, 2 xpassed`); the coverage run the same. All pass cards passed and every strict card xfailed in each. 20 more repeats of every test, in one process: nothing red. `PGOPTIONS` carried five forced plans: `enable_seqscan=off`; that plus hash join and nested loop off; `enable_hashjoin=off`; index, bitmap and index-only scans off; that plus hash and merge join off. `ruff check`: all checks passed.

## Revision history
- **Revision 1 of the cases (order_template.verify.md, case-missing findings):** added OTP-GW-34 ... GW-40, GI-08, GI-09, GT-16, II-08, II-09. The new tests were transcribed from the cards by the same parser and inserted at their card's place; no existing test changed. The audit script passed on every card of the file.
- **Rerun of the final text:** 3 default runs and 5 forced plans, as above, each `67 passed, 6 xfailed, 1 xpassed (plans 1, 2, 3 and the coverage run: 67 passed, 5 xfailed, 2 xpassed)`; coverage with a private `COVERAGE_FILE` as in the Result line; `ruff check` passed. 20 repeats of every test in one process: nothing red. `REFX_MODE=fix` over the nine files: 252 passed with `--runxfail`; with the markers on, 14 strict `XPASS(strict)`, 233 passed, 5 xpassed.

**The verifier's named variants, rebuilt here** (`refx_var.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\refx`, `-p refx_var`, `REFX_VAR=<name>`, in-process, nothing in `app/`; not the verifier's own files). The compare variants keep `==` for an empty or `None` argument, so the old cards do not catch them by accident. Each run on the default plan, markers on:

| Variant | Pass cards that fail |
|---|---|
| `gw_r3_lower_arg` | OTP-GW-34 |
| `gw_r3_lstrip` | OTP-GW-35 |
| `gw_r3_contains_auto` | OTP-GW-36, GW-37, GW-39 |
| `gw_r3_startswith` | OTP-GW-36 |
| `gw_r3_endswith` | OTP-GW-37, GW-39 |
| `gw_r3_like_esc_pct` | OTP-GW-38 |
| `gw_r3_trim_col` | OTP-GW-39 |
| `gi_r2_id_ge` | OTP-GI-08 |
| `ii_r2_id_ge` | OTP-II-08 |
| `gw_w_dirty_hit`, `gw_w_expire` | OTP-GW-40 |
| `gi_w_dirty_hit`, `gi_w_expire` | OTP-GI-09 |
| `gt_w_dirty_hit`, `gt_w_expire` | OTP-GT-16 |
| `ii_w_dirty_hit`, `ii_w_expire` | OTP-II-09 |

## Notes for maintainers
- When BUG-1210 and BUG-1211 are fixed, GW-20 and GT-10 turn the run red: remove the seven markers.
- Never read a GT-08 or GT-09 XPASS as the bug being gone: GW-20 and GT-10 are the proof.
- The file carries `FURB157` in its `ruff: noqa`: the Conventions prescribe `Decimal("1")`.
