# Execution notes — `app/services/expense_order_service.py`

> Cases: `tests/unit/services/expense_order_service.cases.md` (revision 4, 2026-11-22) · Tests: `tests/unit/services/test_expense_order_service.py` · Source commit: e48a092
> Result: 228 of 228 cases implemented · 199 passed · 29 xfailed (29 designed strict xfails) · 0 open discrepancies · 0 errors — branch coverage 100% (284 statements, 46 branches)
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/services/test_expense_order_service.py -q -p no:cacheprovider -o addopts=""`

## How the tests are built
Normal mode, no local model. One test per card in card order. Cards with identical setup and checks that differ in one input are parametrized with the case ID as the param id: K-03/04, K-05/06/07, V-17/18, S-03/04/05, D-06/07/08, R-08/09. Each test has a `# Then N` comment before the checks of its card's Then line N and the card's rules in its docstring. `# [claude]` marks the four `Author: claude` cards (H-03, H-04, C-19, D-12).

- **Standing rows:** fixture `s` (namespace): `W0 < W1 < W2`, `U1…U5` with the cards' names, the five `W1` memberships (U5 inactive), `A0, A1, A2, A9`, `DEP1`, `TAG`.
- **Time:** the autouse fixture `clock` patches `app.services.expense_order_service.utcnow` and `app.managers.expense_order_manager.utcnow` to NOW (naive, like the real helper). `date.today()` (D3) is not mocked, as the spec says.
- **Given rows:** `eo(db, s, n, ws=, waived=, completed=, voided=, **but)`, `eo_many` (add_all and one flush), `line`, `appr(approved=)`, `inv(E or None, ws=, confirmed=, voided_inv=, linked=)`, `link`, `invl`, `pay(voided=)`, `ev`, `tpl(waiving=)`, `tplline`, `acct`. Each one flushes. `ws="0"/"2"` means "of W0 / of W2": that workspace and its account.
- **Named checks:** `commit_point` (= `db.commit()`, then the "nothing written" counts of the ten tables), `snap` (every column, read from the table after `expire_all`), `reread`, `gone`, `x_gone`, `count_where`, `rows_where`, `EV`, `types`, `itypes`, `LINES`, `notes`, `recips`, `loaded`, `approver_of`. Helpers make no assertions. "Session clean" is three asserts inline.
- **`committed:` lines:** `db.rollback()` once before the first one. Ids are saved before the call so nothing reads a deleted or expired object.
- **Spies / failing variants:** the Conventions wraps exactly. `failing notify` / `failing section notify` / `failing approver notify` patch the three names imported into the service (spec G2).
- **Lock cards (C-21, V-24, I-15):** class `Recorder` (an `after_cursor_execute` listener on the session's connection). It provides `first_read_lock`, `lock_clause` (one-table FROM, no JOIN, regex `FOR UPDATE( OF T)?\s*$`) and `locks_before`. Each card runs `db.expunge_all()` after the commit point, with ids taken before.
- **Helper cards with `db.begin_nested()`:** D-06…D-10, R-08…R-10 wrap the call in `with db.begin_nested():` inside the `pytest.raises` block.
- **X-02 (BUG-1193):** the call raises `TypeError` today. It sits directly under `# Then 1` (as in `test_expense_order_manager.py`), so the xfail fails on Then 1 as the card says.

## Fails-today check (`--runxfail`)
`C:\Users\User\AppData\Local\Temp\makorsh-pipeline\svc2e\expense_order_service\check_runxfail.py` maps each failure's last line inside the test function to the nearest `# Then N` comment and compares it with the card's "Fails today on". All 29 designed xfails match:
- Then 1: U-07, R-08, R-09 (BUG-629), U-11, U-12, X-02, X-06, C-05, C-09, C-15, C-22, V-08 (IntegrityError inside the Then 1 raises), V-13, V-17, V-18, V-19, I-05, AS-04.
- Then 2: C-06, C-21, V-24, I-15, I-06, I-08, D-11 (today's real date ≠ 2026-09-27), D-12.
- Then 3: V-15, RA-02.
- Then 4: V-03 (BUG-3070).

## Reference run
`ref_plugin.py` in the scratch folder applies the spec's intended behaviour in-process, never in `app/`. It covers BUG-3062 (locked read), 3063, 3064 (validator on a replacement `ExpenseOrderVoidRequest`), 3065, 3066, 3067, 3068, 3069, 3070, 627, 628, 629, 639, 742, 755 and 1193. Command: `PYTHONPATH=<scratch> … -p ref_plugin --runxfail` → **228 passed**.

Plain runs: 3 × `199 passed, 29 xfailed`, identical. `ruff check` clean, LF line endings.

## Discrepancies
| ID | Case | Designed | Actual | Evidence | Likely cause |
|---|---|---|---|---|---|
| DISCREPANCY-1 | EOS-U-07, EOS-R-08, EOS-R-09 | — | — | **Resolved in Revision 3**: the cards are now `xfail BUG-629` (R4b), failing on Then 1. | — |
| DISCREPANCY-2 | 14 read cards (G-01 … N-02) | — | — | **Resolved in Revision 3**: the cards now say `X in db`; the per-line comments were removed. | — |
| DISCREPANCY-3 | EOS-V-03 | — | — | **Resolved in Revision 3a**: the card is now strict xfail BUG-3070, Fails today on Then 4 (the `invoice_voided` metadata is `{"invoice_id": null}`; the id is read after the draft's delete has nulled it). The bug is logged as BUG-3070 (below). | — |

## New bugs
| ID | Pattern | Module | Title | Today | Intended | Spec | Status |
|---|---|---|---|---|---|---|---|
| BUG-3070 | `audit-value-read-after-mutation` | `app/services/expense_order_service.py` (`void_expense_order`) | Voiding an expense order with a draft invoice logs the unlink event without the invoice id | `delete_invoice` is called before `old_invoice_id = eo.invoice_id` is read; flushing the delete nulls the order's `invoice_id` through the `invoice` relationship, so the `invoice_voided` event's metadata is `{"invoice_id": null}` (verified, EOS-V-03). With a voided or other-workspace invoice (not deleted) the id is kept. | Read the old invoice id before the draft is deleted; the `invoice_voided` event always carries `{"invoice_id": <old id>}` (spec V7) | [spec V7](../../tests/unit/services/expense_order_service.spec.md) | open |

Severity: low. Audit trail only, no money or state is wrong. But it is the only record of which draft was deleted. BUG-3071 and BUG-3072 are not used.

## Coverage gaps
None — 100% branch coverage of `app.services.expense_order_service` (COVERAGE_FILE in the scratch folder).

## Factories added
None. Every builder is local to the test file.

## Notes for maintainers
- When a bug is fixed its strict xfails will XPASS and fail; remove their markers. BUG-3062: C-21, V-24, I-15. BUG-3065: C-05, C-06, C-22, I-05, I-06, I-08. BUG-3064: V-17, V-18, V-19. BUG-3068: U-11, U-12. BUG-629: U-07, R-08, R-09. BUG-3070: V-03. The others have one card each: 3063 D-11, 3066 RA-02, 3067 V-15, 3069 V-13, 627 D-12, 628 C-15, 639 V-08, 742 X-06, 755 C-09 / AS-04, 1193 X-02.
- The BUG-755 fix changes which orders auto-draft: an order with no approvers and no requirement no longer counts as met. UI-03's order F silently gets a draft today; no card checks that, and the reference run stays green.
- D-11 depends on the real clock: it would XPASS on 2026-09-27 (UTC and local date both that day).
- `notes()` / "nothing written" count all workspaces. That is safe on the shared database because other runs never commit.
- The 422 deprecation warnings come from `status.HTTP_422_UNPROCESSABLE_ENTITY` in the service (Starlette rename), not from the tests.

## Revision history
- **Revision 3 (2026-11-22).** U-07, R-08, R-09: markers changed from DISCREPANCY-1 to `xfail(629)` (BUG-629 title), docstrings cite R4b. New test U-14 (deleted new account → 400 `Cannot assign invoice to deleted account`, whole edit undone); passes today and under the reference plugin. The 14 read cards' `# card: X in db.new (DISCREPANCY-2)` comments removed (assertions were already `X in db`). V-03 marker reason now names BUG-3070's title. `_BUGS` gained 629 and 3070. Re-checked: `--runxfail` (28 on their named Then line, V-03 on Then 4), reference plugin 226 passed, 3 plain runs `197 passed, 29 xfailed`, branch coverage 100%, ruff clean, LF.
- **Revision 3a (2026-11-22).** V-03's card became strict xfail BUG-3070 (Fails today on Then 4); the test's marker is now plain `xfail(3070)` and its docstring cites V7 [BUG-3070]. DISCREPANCY-3 resolved. Re-checked: `--runxfail` 29 failures, 0 mismatches against the cards; reference plugin 226 passed; 3 plain runs `197 passed, 29 xfailed`; branch coverage 100%; ruff clean; LF.
- **Verifier fixes (2026-11-22).** Module docstring now names revision 3a; the stale "(DISCREPANCY-1)" tag was removed from the maintainers' BUG-629 line. V-03's marker (`xfail(3070)`, bugs.md title) and the resolved DISCREPANCY-3 row were already current. Re-checked: 3 plain runs `197 passed, 29 xfailed`, ruff clean, LF.
- **Revision 4 (2026-11-22)**, from verifier findings 1–4.
  - (1) The 42 write-method cards with X now bind `x` from `mk_x` and assert `x not in db` at the card's Then position, right after the raise; the later Then numbers shifted.
  - The 14 named error cards (E-02, U-08, X-03, C-07, V-06, AI-05, UI-05, RI-03, I-02, AA-05, RA-04, AP-04, UA-02, T-04) now run the call inside `with spies(db) as (_cm, rb):`, nested inside the `pytest.raises`, and assert `rb.call_count >= 1` next. U-13 and AA-08 already had their rb check.
  - (2) V-10 gains Then 6–10: the reset text, the `invoice_voided` and `eo_voided` descriptions, the `void_note` metadata and the performers.
  - (3) New P-09 (no filter lists completed and voided orders) and H-08 (no filter counts a voided order; its figures differ from the `exclude_voided=True` figures).
  - (4) V-13's invoice now carries `paid_amount 10.00` and `payment_status "partial"`. V-14 is unchanged.
  - The edits were made by script (`rev4.py`, `rev4_manual.py` in the scratch folder). Every card's Then count now equals its test's `# Then` count (`cardmap.py`: 228 cards, 0 mismatches).
  - Re-checked: `--runxfail` gives 29 failures, 0 mismatches against "Fails today on"; the reference plugin gives 228 passed; 3 plain runs gave `199 passed, 29 xfailed`; branch coverage 100%; ruff clean; LF.
  - **Mutation check:** `norollback_plugin.py` (scratch) makes `ExpenseOrderService._rollback_transaction` a no-op, giving 33 failed / 166 passed / 29 xfailed.
    - 32 of the 42 X tests fail on `assert x not in db`, and all 14 spies tests fail.
    - V-09 also fails, but on its next line, the re-read (`PendingRollbackError`). Its refusal is a NOT NULL violation during the flush, which already expunged X, so its X line holds without the service's rollback.
    - The other 9 X tests (U-07, U-11, X-06, C-05, C-15, C-22, V-13, I-05, I-08) are strict xfails that fail on their bug line before reaching the X line, so they still xfail.
