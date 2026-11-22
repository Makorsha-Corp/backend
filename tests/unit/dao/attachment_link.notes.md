# Execution notes — `app/dao/attachment_link.py`

> Cases: `tests/unit/dao/attachment_link.cases.md` (Revision 1, READY, 78 cases) · Tests: `tests/unit/dao/test_attachment_link.py` · Source commit: e48a092
> Result: **78 tests for 78 cases — 70 passed · 8 xfail (7 xfailed, 1 xpassed) · 0 discrepancies · 0 errors** — branch coverage 96% (24 statements, 0 branches; the one miss is the dead `get_by_entity`). Non-strict cards may XPASS without turning the run red: default `70 passed, 7 xfailed, 1 xpassed` (ALK-GL-12); plans 1 and 2 also ALK-GL-07: `70 passed, 6 xfailed, 2 xpassed`.
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/dao/test_attachment_link.py -q -p no:cacheprovider`

## Who wrote what
Normal mode, no local model: every test sits below a `# [claude] <ID>` comment, written by hand from the cards. The audit scripts `check.py` and `lits.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\attx\A` (throwaway, not in the repo) checked: each ID exactly once and in card order, the docstring starting with the ID, `# Then 1..N` matching the card's Then count, marker, strictness and bug matching the Expect line, no unused argument, every double-quoted card literal present in its test (the three `f"f{k}.png"` ones sit in the `mk_many_linked` builder). LF only.

## How the tests are built
- **Nothing is patched.**
- **Constants:** `dao`, `Schema`, `MISSING`.
- **Standing rows:** `w1`, `w2`, `u1` (ids rise in Conventions order), through the autouse `standing_rows`.
- **Builders:** `mk_attachment(**columns)` = "attachment"; `mk_deleted_attachment(**columns)` = "deleted" (`is_deleted True`, `deleted_by U1.id`); `mk_link(attachment, **columns)` = "link on X"; `mk_many_linked(count)` = the 101 attachments and 101 links built with `add_all` (returns `all_ids`). ALK-GL-02 builds its 101 links inline with `add_all`.
- **Given steps:** `age(db, row, n)`, `bump(db, row)`, `bump_l(db, row)`, `seqscan(db)` are the Conventions' SQL verbatim (each `UPDATE` followed by `db.expire_all()`).
- **Reading helpers:** `ids(result)`; `reread(db, row)`; `links_of(db, row)`; `stored_count(db)` = (all `attachments`, all `attachment_links`), "nothing written".
- **Database-error cards:** `with pytest.raises(...) as exc:` around `with db.begin_nested():`. Where the card's first Then is `raises: E` (GA-24, GA-25) the `# Then 1` comment sits on the `with`; where the first Then reads `exc.value` (CR-04, 05, 07, 09, 10) the `with` block is the When.
- **rolled back (CR-12):** `commit_spy(db)` wraps `db.commit`; `sp = db.begin_nested()` directly before the call.
- **Statement recorder:** `StatementRecorder(db)` around the When only; `recorder.sql()` is the one SELECT; `order_part_of(sql)` the text after the first `ORDER BY` and before any `LIMIT`.

## xfail location (`--runxfail`, reading the failing value)
| Card | Strict | Fails on | Actual |
|---|---|---|---|
| ALK-GA-28 | no | Then 2, every plain run and plan | `assert [316473, 316474, 316472, 316475] == [316474, 316473, 316472, 316475]`: B, C, A, D for C, B, A, D (A = 316472) |
| ALK-GA-29 | no | Then 2, every plain run and plan | `assert [316477, 316478, 316479, 316476] == [316479, 316478, 316477, 316476]`: pages B, C, D, A for D, C, B, A |
| ALK-GA-30 | yes | Then 3, every run | `assert '.id' in ' attachments.uploaded_at DESC \n '` |
| ALK-CN-01 | yes | Then 2, every run | `assert 3 == 2`: the failed one counts |
| ALK-GL-07 | no | Then 2 on the default plan and plans 3–5; **XPASS** on plans 1 and 2 (`enable_seqscan=off` reads by the `attachment_id` index, in id order) | `assert [661, 662, 660] == [660, 661, 662]` |
| ALK-GL-08 | yes | Then 2, every run | `assert 'ORDER BY' in 'SELECT attachment_links.id … WHERE …'` |
| ALK-CR-02 | yes | Then 3, every run | `assert timedelta(seconds=21600) < timedelta(seconds=300)`: Dhaka local time, 6 h after UTC |

**Proof plugin** `attx_plug.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\attx\A` (`-p attx_plug`, `ATTX_MODE=…`), replacing the DAO methods in-process; nothing in `app/`.

**Explicit wrong orders, `--runxfail`:**

| `get_attachments_for_entity` order | `get_links_for_attachment` order | Cards that fail | Pass cards that fail |
|---|---|---|---|
| `uploaded_at DESC, id` | `id DESC` | GA-28, GA-29, GL-07 on Then 2; GA-30 on Then 5; GL-08 on Then 4 | none |
| `uploaded_at DESC, file_name` | `entity_id DESC` | GA-28, GA-29, GL-07 on Then 2; GA-30, GL-08 on Then 3 | none |
| `uploaded_at DESC, note DESC` | `entity_type, linked_by` | GA-28, GA-29, GL-07 on Then 2; GA-30, GL-08 on Then 3 | none |
| `uploaded_at DESC, file_name DESC, id` | `entity_id DESC, id` | GA-28, GA-29, GL-07 on Then 2; GL-08 on Then 4; **GA-30 passes** | none |

(CN-01 and CR-02 fail as today in every row; the plugin leaves them alone.) So every non-strict card can fail on its Then 2, and no pass card depends on the order among ties.

**The intended behaviour** (`ATTX_MODE=fix`: `uploaded_at DESC, id DESC`; `id`; count leaves out `failed`; `linked_at` stamped with naive `utcnow()` by a `before_insert` listener): with `--runxfail` all 70 pass, so Then 4 and 5 of GA-30 and Then 3 and 4 of GL-08 hold. With the markers on, the four strict cards here are `XPASS(strict)` and the three non-strict ones XPASS.

## Discrepancies
None. No card was changed, no marker loosened, no test is marked DISCREPANCY.

Prose only, no test affected: ALK-GA-30's checks (`.id` after `uploaded_at`, two `DESC`) also accept `uploaded_at DESC, file_name DESC, id`, a wrong order (row 4 above); GA-28 and GA-29 catch it. A tighter check would be the case designer's call.

## Spec gaps of the cases file, checked
Gap 1: `linked_at` compared within 5 minutes; holds (`UTC` card 3000 repeats green). Gaps 2, 3 need no executor action.

## Coverage gaps
| Lines | Kind | What the code does there |
|---|---|---|
| 52 | dead | `get_by_entity` — no caller; to be removed (spec P3; Deferred table). |

Run with a private `COVERAGE_FILE` (`...\attx\A\.coverage`). The inherited `create` lives in `app/dao/base.py` (measured by `tests/unit/dao/test_base.py`).

## Factories added
None.

## Stability
5 default runs `63 passed, 7 xfailed`; 5 forced plans and 2 database time zones the same, except plans 1 and 2 (`enable_seqscan=off`, and that with hash join and nested loop off): `63 passed, 6 xfailed, 1 xpassed` (GL-07). Plans and zones as in `attachment.notes.md`; the database default zone is `America/New_York`. ALK-CR-02 and CR-03 compare real-clock stamps: 3000 repeats of each in one process (`attx_rep.py`, `-p attx_rep`, `ATTX_REP=3000`): 3000 passed, 3000 xfailed. `ruff check`: all checks passed.

## Notes for maintainers
- When BUG-1432 is fixed, GA-30 turns the run red: remove the markers of GA-28, 29, 30. BUG-1433: GL-07, GL-08. BUG-1434: CN-01. BUG-1431: CR-02.
- Never read a GA-28, GA-29 or GL-07 XPASS as the bug being gone: GA-30 and GL-08 are the proof.
- The `ALK-SC` cards take no fixture argument, but the autouse standing rows still build W1, W2, U1 (Conventions: they exist in every test).

## Revision history
- **Revision 1 of the cases (attachment_link.verify.md, case-missing findings):** added ALK-CN-12 … CN-17, GL-11 (pass) and GL-12 (xfail BUG-1433, non-strict); ALK-GL-10 gained Then 7 (`"FOR UPDATE" not in sql.upper()`, through `recorder.sql()`), its `nothing written` check is now Then 8. GL-12 XPASSES on today's code in every run (physical order equals id order, which its card allows: "can match by accident"); the variant `gl_ord_entity` (`entity_id, id`) makes it fail on Then 2 (`assert [97061, 97062, 97060] == [97060, 97061, 97062]`), and GL-08 stays the strict proof of BUG-1433. Patched in place, no other test changed. 3 default runs, 5 forced plans (as above) and the database time zones `UTC` and `Asia/Dhaka`, `ruff check` passed, coverage with a private `COVERAGE_FILE`, LF only. Card audit (my own `audit.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\attx\R`): every ID once, in card order, `# Then 1..N` per card, markers as the Expect lines. Reference plugin `attxr_plug.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\attx\R` (`-p attxr_plug`, `ATTXR_MODE=ref`, in-process, nothing in `app/`; covers the seven revised modules): with `--runxfail` all 371 tests of the seven files pass, so the lines past every failure point hold. The verifier's named variants, rebuilt in the same plugin (`ATTXR_MODE=<variant>`, the reference with one change, `--runxfail`, default plan; each asserted applied): `cn_txt_like` → CN-12; `cn_txt_contains` → CN-12, 13, 14, 16; `cn_txt_startswith` → CN-12, 13; `cn_txt_endswith` → CN-12, 14, 16; `cn_txt_strip` → CN-15; `cn_txt_trimcol` → CN-16; `cn_ws_le` → CN-17; `gl_ws_le` → GL-11; `gl_ord_entity` → GL-12 Then 2; `gl_w_forupdate` → GL-10 Then 7. No other test failed under any of them.
