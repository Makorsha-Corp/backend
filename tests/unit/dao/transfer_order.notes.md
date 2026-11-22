# Execution notes — `app/dao/transfer_order.py`

> Cases: `tests/unit/dao/transfer_order.cases.md` (revision 3) · Tests: `tests/unit/dao/test_transfer_order.py` · Source commit: e48a092
> Result: **267 tests for 267 cases — 210 passed · 57 xfailed (49 strict, 8 non-strict) · 0 discrepancies · 0 errors** — branch coverage 99% (115 statements, 20 branches; 2 lines missed, both dead)
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/dao/test_transfer_order.py -q -p no:cacheprovider -o addopts=""`
> Coverage: the same with `--cov=app.dao.transfer_order --cov-branch --cov-report=term-missing` and `COVERAGE_FILE=C:/Users/User/AppData/Local/Temp/makorsh-pipeline/bigdaoe/to/.coverage`

## How the tests are built
- Written in normal mode (no local model); every test sits below a `# [claude] <ID>` comment, in card order, with a `# Then N` comment before each numbered Then line. Parametrized only where cards share setup and assertions and differ in one input (HF-12…15, HF-23/24, NN-03…07/11/18/19, NN-30/31, HF-55/56, HF-57/58, HF-59/60, IO-03/04, IT-05/06, II-02/03, OQ39-04…07, OQ39-08/09, OQ40-09/10, OQ40-11…13); each case keeps its own param id.
- **Standing rows** → fixture `s` (SimpleNamespace `s.W0 … s.I2`), built in the Conventions' order and flushed one by one. Machine and component ids are `XID(k)`, so they never equal a factory id and never clash with another process.
- **Given rows** → `order(db, s, n, ws=0|1|2, completed=, draft=, planned=, flush=, add=, **cols)`: "order n", "of W0 / W2", the "but" columns, and the conventions **completed** (`completed_at DONE`), **draft** (`destination_location_id 0`) and **planned** (line(T, 1) inserted right after). `flush=False` = "added and not flushed"; `add=False` = "built but not added". `num(db, s, ws, number, created_at=…)` = num(W, s) (exact number, no GN). `line(db, s, T, k, **cols)`, `deleted(db, s, row)` (factory / machine / project; machine also `is_active False`), `numlock`, `seqscan`, `bump`, `bump_l`, `dhaka`.
- **GN(s)** puts the process id on every number outside the NN cards, so parallel runs never insert the same `transfer_number` (the index is global, BUG-2650). Every NN card starts with **numlock** (`pg_advisory_xact_lock(2650)`), released at the rollback.
- **Clock**: `clock(L, U)` patches the stdlib attribute `datetime.datetime` with a subclass whose `now()` returns L (the DAO imports `datetime` inside the function, so it picks up the patch), plus `app.dao.transfer_order.utcnow` (`create=True`) and `app.utils.time.utcnow`. `_next()` wraps every NN call in clock(NOW31, NOW31); NN-23 … 25 give their own clock; NN-26 uses `utconly` only. No other patch, nothing else mocked.
- **Statement recorder**: a `before_cursor_execute` listener on the session's connection. `sql` = the one SELECT whose text contains `FROM <table>` (`transfer_orders`, or `transfer_order_items` for IO / IT); `order_part` = text after the first `ORDER BY`, before `LIMIT`.
- **Database errors**: NN-29 wraps the flush in `pytest.raises(IntegrityError)` + `db.begin_nested()` and keeps using `db`. NN-27 / 28 flush inside `db.begin_nested()` with no `raises`; today the flush raises (23505) in the When, which is what the cards' "Fails today on" lines describe.
- **Tie cards** (non-strict, `Author: claude`): seqscan, then a raw `UPDATE` of the lowest id moves its tuple to the end of the heap, so an unordered tie comes back with that id last. Ids are read into locals before the bump (the bump expires the session).

### `--runxfail` (every xfail must fail on its card's Then line)
Own plugin `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\bigdaoe\to\failson_to.py` (`-p failson_to`, output `runxfail.json`): **57 failed, 210 passed** (Revision 3). Each of the 57 fails at the card's named Then line with the card's "today" value, e.g. HF-46 `[B, A] == [A]`, FF-22 `1 == 2`, RC-05 `[A, B]`, PH-08 / PH-09 at Then 2, TL-09 / IB-11 / IO-09 / IT-09 / PH-12 at Then 2, NN-08 / 09 `TR-2031-1000`, NN-10 `-001`, NN-24 `TR-2031-008`, NN-25 `TR-2030-005`, NN-26 `TR-2026-001` (the real local year), NN-32 `TR-2031-006`, OQ39-02 `0 == 1`, OQ39-13 `2 == 1`, OQ39-14 at Then 2 `0 == 1`, OQ40-20 `[B] == [A]`, OQ40-08 `(1, 1, 0)`. Exceptions: **NN-27 and NN-28** fail in the When with `IntegrityError` 23505 on `ix_transfer_orders_transfer_number`, before Then 1 — exactly what their "Fails today on" lines say ("the call raises IntegrityError").

### Reference plugin
`C:\Users\User\AppData\Local\Temp\makorsh-pipeline\bigdaoe\to\ref_to.py` (`PYTHONPATH=<that folder>`, `-p ref_to`), with `--runxfail`: **267 / 267 passed** (Revision 3; the plugin needed no change: its stage rule already requires a line of the order's own workspace, which OQ39-14 / OQ40-20 check). It replaces in-process: the hub filters (LIKE escaping for BUG-2654; status ticks by stage, names trimmed and case-insensitive, for BUG-2660), the factory filter (either end, BUG-2658), the recent / highlight / touching / inbound orderings (`COALESCE(updated_at, created_at) DESC, id DESC`; oldest drafts `created_at ASC, id ASC`; BUG-2655 / 2656), the highlight stage rule (route + a line of the order's workspace, BUG-2659), `get_next_number` (UTC year, numerically highest all-digit suffix, one SELECT; BUG-2651 / 2653) and the item line order (`line_number, id`, BUG-2657). For NN-27 … 29 an autouse fixture drops `ix_transfer_orders_transfer_number` and creates a unique `(workspace_id, transfer_number)` index inside the test's own transaction (BUG-2650); NN-29 still gets 23505. Nothing in `app/` changes.

## Discrepancies
None.

## Coverage gaps
| Lines | Kind | What the code does there |
|---|---|---|
| 197–202 | dead | `TransferOrderDAO.get_by_workspace` — no caller (spec Q3 "remove", Deferred FU-2); no card by design |

The `IndexError` half of `except (ValueError, IndexError)` is unreachable (`str.split('-')` always gives at least one element); the `ValueError` path is covered by NN-11.

## Factories added
None (all builders are local).

## Stability
| Run | Passed | xfailed | xpassed (non-strict) | Not as designed |
|---|---|---|---|---|
| plain 1 | 210 | 57 | 0 | 0 |
| plain 2 | 210 | 57 | 0 | 0 |
| plain 3 | 210 | 57 | 0 | 0 |
| coverage run | 210 | 57 | 0 | 0 |
| `--runxfail` | 210 | — (57 failed, all on their Then lines) | — | 0 |
| `--runxfail` with the reference plugin | 267 of 267 | — | — | 0 |

Runs were made while the purchase_order, work_order, account_invoice and expense_order executors used the same database (no clash seen); the combined parallel run is the orchestrator's. `ruff check`: all checks passed; `ruff format`: formatted. Line endings: LF.

## Notes for maintainers
- When a bug is fixed its strict cards XPASS and fail: remove the markers. BUG-2650 (migration: per-workspace unique index) → NN-27, NN-28. BUG-2651 → NN-08, 09, 10, 32. BUG-2653 → NN-24, 25, 26. BUG-2654 → HF-46, 48, 49, 51. BUG-2655 → RC-05, RC-06, PH-08, PH-09. BUG-2656 → RC-09, PH-12, TL-09, IB-11 (strict) and remove the non-strict markers of RC-07, RC-08, PH-10, PH-11, TL-08, IB-10. BUG-2657 → IO-09, IT-09 (strict), IO-08, IT-08 (non-strict). BUG-2658 → FF-17 … FF-22. BUG-2659 → OQ39-02, 12, 13, 14. BUG-2660 → OQ40-01, 02, 05 … 15, 18, 19, 20.
- After BUG-2650 is fixed, GN suffixes are no longer needed for parallel safety, but keep them: they cost nothing.
- `clock()` patches the stdlib `datetime.datetime` for the When only; build every value before entering it.
- `count_machine_involved_for_hub` and `aggregate_hub_stats` raise an SAWarning (subquery coerced into `IN`); harmless, from the code under test.
- HF-38 … 40, FF-12, FF-13, OQ39-14 and OQ40-20 (a line of W2 on a W1 order, helper `_foreign_line`) build invalid cross-workspace rows on purpose (HR-16 leak checks, spec review note); do not copy that pattern elsewhere.

## Revision history
- **Revision 2 (2026-11-14):** first execution of this cases file (no earlier test file existed).
- **Revision 3 (2026-11-14):** patched, not regenerated (cases Revision 3 = `transfer_order.verify.md` findings 1–8, all `case-missing`; no ID retired, no existing card changed, so every Revision 2 test is unchanged). Added, each in its section: HF-55 … HF-63 (search by the middle / end / start of factory, machine and component names; component at a project source; factory at a damaged source and at a storage destination — HF-55/56, 57/58, 59/60 parametrized in pairs); no-lock cards CH-06, RC-11, MI-08, AS-09 (Then: the result, `written == []`, no `FOR UPDATE` in any recorded SELECT) and PH-14 (four Thens); strict xfail OQ39-14 (BUG-2659, fails at Then 2: `awaiting_setup_count` 0) and OQ40-20 (BUG-2660, fails at Then 1: only B kept). Re-run: 3 plain runs 210 passed / 57 xfailed each; `--runxfail` 57 failed, the 55 earlier ones on the same Thens as Revision 2 and the two new ones on their named Thens; reference plugin `ref_to.py` unchanged, with `--runxfail` 267 / 267; coverage unchanged (99%, lines 197–202 dead); ruff check and format clean; LF. Discrepancies: none.
