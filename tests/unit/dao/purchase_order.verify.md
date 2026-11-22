# Verification — `app/dao/purchase_order.py`

> **Verdict:** PASS
> Tests: 204 passed · 38 xfailed (reproduced ✅; all 38 fail on their carded Then line under `--runxfail`) · coverage 94% branch (misses 148-157, 330 = dead code only)
> Mutation: 185 mutants · 172 killed · 13 survived → score 100% (172 / 172, after excluding 3 equivalent, 10 dead, 0 bug-path)
> Source commit: e48a092 · Cases revision: 2

## Summary
These tests can be trusted. Every one of the 242 cards has exactly one test (20 of them as `pytest.param` ids), every marker matches its Expect line, and I read each test against its card: no missing, weakened or changed assertion, no wrong setup, no swallowed failure, and no mocks beyond the carded clock and the AL-29 / AL-30 race patch. All 38 xfails fail on the line their card names (checked by machine, 0 bad). Three plain runs and the coverage run give the same result as the notes. Every surviving mutant is in dead code or cannot change behaviour. Nothing needs fixing. AL-20 / AL-21 are still carded to retire when BUG-2630 is fixed, and AL-29 / AL-30 then take over.

## Findings
None.

**Observations (no fix needed, nothing logged):**
- O1 (hand variant, numbering): `allocate_po_number` parses the suffix with Python `int()`. That means `PO-2031-৯৯৯` (Bengali digits) counts as 999 and `PO-2031-1_500` counts as 1500, so the next numbers are `-1000` and `-1501`. Spec R3 only says that "a suffix that is not an integer is ignored". Nobody can reach this today: numbers are made by the system and cannot be set through `PurchaseOrderCreate` / `PurchaseOrderUpdate`. No bug. **Describer**, optional: add one line to R3 on a later spec touch.
- O2 (hand variant, voided scope): with `exclude_voided=False`, a voided Planning PO counts in `pending_planning_count` (PH-16) and also in `missing_invoice_count`. A real void unlinks the invoice, so a voided PO always reads as "missing invoice". This matches spec R1, which says every part follows the filters. Owner answer OQ-35 covers only the money tiles. Not a bug under today's rules. **Describer**: a possible future owner question ("should voided POs ever appear in the needs-attention panel?"). Park it in `docs/testing/owner-questions.md` at the next spec pass. It is not blocking.

## Surviving mutants
| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 25 | 153 | negate `if account_id` | dead | `get_by_workspace` body. Spec Not specified, Q1 (no caller; confirmed below) | — |
| 26 | 155 | negate `if invoice_id is not None` | dead | same | — |
| 27 | 157 | `return None` | dead | same | — |
| 36 | 330 | `return None` | dead | `get_next_number` alias. Spec Not specified, Q1 (no caller) | — |
| 51 | 145 | default `skip` 0 → 1 | dead | `get_by_workspace` signature | — |
| 52 | 146 | default `limit` 100 → 101 | dead | `get_by_workspace` signature | — |
| 53 | 155 | `is not None` → `is None` | dead | `get_by_workspace` | — |
| 81 | 151 | `==` → `!=` (workspace filter) | dead | `get_by_workspace` | — |
| 102 | 154 | `==` → `!=` (account filter) | dead | `get_by_workspace` | — |
| 103 | 156 | `==` → `!=` (invoice filter) | dead | `get_by_workspace` | — |
| 179 | 353 | `rsplit("-", 1)` → `rsplit("-", 2)` | equivalent | `[-1]` of `rsplit` is the text after the last `-` for any maxsplit ≥ 1 | — |
| 184 | 414 | `coalesce(sum(quantity_ordered), 0)` → `…, 1)` | equivalent | each group comes from at least one line (GROUP BY on existing rows) and `quantity_ordered` is NOT NULL, so the sum is never NULL | — |
| 185 | 415 | `coalesce(sum(quantity_received), 0)` → `…, 1)` | equivalent | same: `quantity_received` is NOT NULL | — |

**Dead-code claims confirmed:**
- `PurchaseOrderDAO.get_by_workspace` (148-157): its only caller is `PurchaseOrderManager.list_purchase_orders` (`app/managers/purchase_order_manager.py:930-936`), and nothing in `app/`, `scripts/` or `tests/` calls that. `PurchaseOrderService.list_purchase_orders` goes through `list_purchase_orders_page` → `list_for_hub`.
- `PurchaseOrderDAO.get_next_number` (330): no caller. The `get_next_number` calls in the managers are on `eo_dao`, `to_dao` and `wo_dao`. There is no `getattr` or string lookup of either name.

## Traceability
cards 242 · tests 222 functions (242 test ids, after the parametrized HF-32…34, HF-44/45, AL-02…14, IN-02/03) · unmatched: none · tests without a case ID: none · marker mismatches: none (204 pass with no marker; 30 strict + 8 non-strict xfails, each reason names its bug; BUG-2630…2641 all exist in `docs/testing/bugs.md`). Script: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\bigdaov\po\trace.py`.

**`--runxfail` location check** (own plugin `failson_v.py` + `check_failson.py`, same folder): 38 of 38 fail inside the `# Then N` block their card's "Fails today on" names (`BAD 0 of 38`). Examples: AL-29 `DID NOT RAISE HTTPException` (Then 1), OQ35-01 `1006.00 == 606.00` (Then 3), PH-12 `'purchase_orders.id' in ' purchase_orders.created_at ASC '` (Then 3), OQ38-08…10 `KeyError: 'quantity_refunded_total'`.

**Hand variants tried** (scratch `probe/test_po_probe.py`; nothing committed):
- voided rows in hub money: BUG-2639 cards cover it. A legacy voided PO linked to an unpaid invoice with `outstanding_payment` + show-voided gives `(1, 40.00, 1, 40.00, 0)`, which is the BUG-2639 path.
- open / outstanding scope: OQ36 / OQ37 cover it. With search + `outstanding_payment` + `exclude_complete` together (three joins), list, count and stats agree with no duplicate.
- received vs refunded: OQ38-01…10 cover it.
- numbering: per-workspace (BUG-2630), past 999 / 9999 (AL-04…07), local clock year (BUG-2632), prefix case (AL-12), text vs numeric order (AL-04). Unicode digits and `_` in the suffix: O1.
- `%` / `_` wildcards and deleted supplier search: BUG-2633 / BUG-2634 cover them.
- tie-breaks: LH-02/03, RH-04, PH-04/10/11, GV-07/08 and IN-10/11, with strict statement alarms RH-05, PH-12, GV-09, IN-12.
- locks: every read card checks `"FOR UPDATE" not in` sql.
- W0 / W2 scoping: covered throughout. Asking W2 with a W1 factory id returns `[]`.
- Not applicable here: transfer "Planned" stage filter, payable + receivable combined, expense pipeline / timeline.

## Commands run
```
COVERAGE_FILE=C:\Users\User\AppData\Local\Temp\makorsh-pipeline\bigdaov\po\.cov
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_purchase_order.py -q -p no:cacheprovider -o addopts="" --cov=app.dao.purchase_order --cov-branch --cov-report=term-missing
  app\dao\purchase_order.py  144  7  46  0  94%  148-157, 330
  204 passed, 38 xfailed, 20 warnings in 39.72s
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_purchase_order.py -q -p no:cacheprovider -o addopts="" --runxfail -rf
  38 failed, 204 passed, 20 warnings in 19.02s
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_purchase_order.py -q -p no:cacheprovider -o addopts=""   (x2)
  204 passed, 38 xfailed, 20 warnings in 19.00s
  204 passed, 38 xfailed, 20 warnings in 18.27s
PYTHONPATH=<scratch> FAILSON_OUT=<scratch>\failson.json .venv/Scripts/python.exe -m pytest tests/unit/dao/test_purchase_order.py -q -p no:cacheprovider -o addopts="" --runxfail -p failson_v
  38 failed, 204 passed;  check_failson.py: BAD 0 of 38
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/dao/purchase_order.py tests/unit/dao/test_purchase_order.py --json C:\Users\User\AppData\Local\Temp\makorsh-pipeline\bigdaov\po\mut.json
  Mutants: 185 · killed 172 · timeout 0 · survived 13 · score 93%  (raw; 100% after excluding 10 dead + 3 equivalent)
```
Stability: 4 runs, same outcome every time, no flaky test. The 20 warnings are the known `SAWarning` (subquery coerced into `IN()`) at line 258, already in the notes.
