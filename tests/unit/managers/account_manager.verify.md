# Verification — `app/managers/account_manager.py`

> **Verdict:** PASS
> Tests: 100 passed · 89 xfailed (reproduced ✅) · coverage 100% branch (100 statements, 42 branches)
> Mutation: 186 mutants · 174 killed · 12 survived → score 100% (after excluding 6 equivalent, 1 dead, 5 bug-path)
> Source commit: e48a092 · Cases revision: 2

**Previous round:** NEEDS WORK with 12 findings, all routed to the executor (1 Given without its "deleted" qualifier, 3 missing global audit counts, omitted "in particular" literals in 17 tests, 9 Given rows with a column the card does not name, 1 row-order drift, 2 derived-instead-of-literal values, 1 inaccurate notes line). This round is a full re-verification after fix round 1: every one of the 12 was re-checked in the test file and is fixed (table below), and the whole procedure was repeated from scratch.

> **Note 2026-11-03 — not re-verified.** After this verdict, cases revision 3 (spec Gap log C1, C2: BUG-719 → BUG-1486 on `get_tags_for_account` R5; new `update_account` R13a [BUG-1487]) added ACC-T-09, T-10, U-55, U-56 and changed the markers of ACC-T-06, T-07 (now non-strict BUG-1486). That was done by one agent in one pass — lighter than an independent verification round; this verdict does not cover those six tests. Run by that agent: 101 passed · 92 xfailed, `--runxfail` 92 failed in the designed Then lines, five forced plans unchanged, 100% branch. No mutation run. See `account_manager.notes.md`, Revision history.

## Summary
The suite can be trusted. All 189 tests were read again against their cards, Then line by Then line, and no deviation is left: every Given row is built with the card's columns, qualifiers and order; every numbered Then line has its assertions under its `# Then N` comment, including both halves of two-part lines, every "in particular" literal and "same `id`"; snapshots are all taken before the call; nothing is mocked beyond the two `utcnow` names; no failure is swallowed.
The run reproduces the notes exactly on three runs (no flakiness), and with `--runxfail` all 89 xfail tests fail inside the Then block their card names (checked by script against each card's "Fails today on" line, 0 mismatches).
Mutation testing gives the same result as before the fix round: 174 killed, the same 12 survivors, none of them a test weakness.
**Findings in local-written tests: 0 of 182. Findings in Claude-written tests: 0 of 7.** (Previous round: 31 of 182 and 0 of 7.)
Nothing has to change.

## Findings
None.

### Previous findings — re-check
| # | Was | Now | Status |
|---|---|---|---|
| 1 | ACC-G-06 built a live A9 | `mk_account(name="Zeta Corp", workspace_id=w2.id, deleted=True)`; still fails on the designed `TypeError` | fixed |
| 2 | ACC-U-40 Then 2 without the global audit count | `assert count_rows(db, FinancialAuditLog) == 1` first in Then 2, then audit(A1) and the five standard fields | fixed |
| 3 | ACC-D-06 Then 2, same | same line added | fixed |
| 4 | ACC-A-11 Then 3 without the count; Then 4 description derived from the row | count added (the test now fails on it, `0 == 1`, still inside Then 3 as the card names); `description == "Account 'Acme Ltd' updated"` as a literal | fixed |
| 5 | ACC-U-36 Then 3 without the five numbers | `accounts` 1, `account_tag_assignments` 1, `financial_audit_logs` 0, T1 `usage_count == 1`, T9 `usage_count == 0` all asserted, plus `written(db) == before` | fixed |
| 6 | "in particular" literals missing in 7 pass tests | ACC-U-17, ACC-AT-03, ACC-A-10: `row_x1.id == x1.id`, `assigned_at == T0`, `assigned_by == u1.id`; ACC-D-02, D-19 (A2), D-20: `is_deleted is False`; ACC-D-21: `deleted_at == T0`, `deleted_by == u1.id` | fixed |
| 7 | the same in 10 xfail tests | ACC-U-04 (4 values), U-35 (2), U-38 (1), U-44 (2), U-45 (1), U-49 (3), ACC-D-13 / D-14 / D-16 (5 each), ACC-D-15 (5 + `paid_amount == Decimal("400.00")`, `payment_status == "partial"`) | fixed |
| 8 | `account_code="SUP-001"` on "A1, but deleted" in 8 tests | all eight are `mk_account(deleted=True)` (ACC-U-04, G-04, G-05, D-05, D-21, A-04, UN-05, T-08); the code remains only where the card names it (ACC-C-23, ACC-U-47) | fixed |
| 9 | ACC-U-25 with `updated_by=u2.id` | `mk_account(city="Dhaka")` | fixed |
| 10 | ACC-UN-01 assignment rows in the wrong order | `mk_link(a1, t1)` then `x2 = mk_link(a1, t2)` | fixed |
| 11 | ACC-AT-09 Then 4 compared with a before-value | `assert reread(db, t3).usage_count == 1` | fixed |
| 12 | notes said reasons carry the kind tag | "Notes for maintainers", first bullet now says `BUG-NNN: <title>` and lists the precedent bugs whose title is another module's; checked: all 27 distinct reasons carry the title column of `bugs.md` (backticks dropped), `incomplete-audit-snapshot` occurs 0 times | fixed |

### The executor's own-initiative changes — judged against the cards
| Change | Matches the card? |
|---|---|
| ACC-UN-05: extra unchanged(A1) snapshot removed | Yes. The card has three Then lines (raises; tags(A1); nothing written) and no unchanged(A1); the test now asserts exactly those. |
| `before = written(db)` / `assert written(db) == before` added to ACC-C-12, C-13, C-14, C-15, ACC-A-04, ACC-A-07, ACC-UN-03, ACC-UN-04 | Yes. "nothing written" is defined in the Conventions as "these equal their values before the call", so the pair is the card's own check; the listed numbers are still asserted literally beside it. In all eight the snapshot is taken after the Given rows and before the call. |
| ACC-UN-09: message with the literal `999999999` instead of `{MISSING}` | Yes — the card writes the number. |
| ACC-S-01, ACC-T-01: `isinstance` checks for "a list of Account / AccountTag objects"; ACC-C-29, ACC-U-11: `isinstance(obj, AccountCreate / AccountUpdate)` for "returns: the schema object, no error raised" | Yes — each is the first half of a two-part Then line that had no assertion; the xfail pair still fails on Then 2 as the card names. |
| ACC-C-33, C-34 (`account_code=None` on A2), ACC-U-54 (`name="Acme Ltd"`), ACC-UN-01 (`workspace_id=w1.id`) removed | Yes — defaults the card does not name as a difference. |
| ACC-D-08 keeps `x1`, `x2` and snapshots those | Yes — the card names "row X1" / "row X2". |
| ACC-C-06, C-07, C-18, C-30: card-text comments replaced by `# Then N` | Yes — code unchanged, comments only. |
| Left as they are: `updated_by=None` (ACC-D-13…16), `is_deleted=False` (ACC-G-07, ACC-A-13), `workspace_id=w2.id` on the assignment (ACC-UN-04) | Acceptable — each value stands in the card's own parentheses for that row. |

Checked and **not** findings:
- ACC-S-02 and ACC-UN-12 (Claude-written) carry one extra comment line (`# Fails today here: …`) before the call; it is a comment only and the call is not wrapped.
- ACC-D-20 Then 2 types the open-invoices text; the dash is U+2014 (bytes `E2 80 94`), identical to `OPEN_INVOICES`.
- ACC-C-01 does not request `w2` ("W1 and W2 have no accounts" needs no row).
- Loops over `links(db, …)` in ACC-C-08, ACC-U-28, ACC-AT-02 would assert nothing on an empty list, but the preceding Then line fixes the list (`tags(...) == [...]`).

## Surviving mutants
Same 12 as in the previous round; the source file is unchanged.

| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 26 | 151 | `hasattr(...) and tag_ids is not None` → `or` | dead | The `hasattr` part is the dead code of spec Q11 / "Not specified" (always true); with `or` the branch is always taken and assigns `tag_ids = account_data.tag_ids`, so `None` stays `None`. | — |
| 112 | 75 | `account_input.get('allow_invoices', True)` → `False` | equivalent | `AccountBase.allow_invoices: bool = True`, so `model_dump` always has the key; the `.get` default is never used. | — |
| 124 | 154 | `exclude_unset=True` → `False` | equivalent | Every `AccountUpdate` field defaults to `None` and `exclude_none=True` stays: an unset field is `None` and is dropped either way. | — |
| 125 | 154 | `exclude_none=True` → `False` | bug-path | Dropping explicit `null` is today's behaviour tagged BUG-608 (`update_account` R5); only xfail ACC-U-12 targets it. No pass card sends an explicit `None` for a copied field (ACC-U-16 sends `tag_ids=None`, excluded separately). | — (resolves with BUG-608) |
| 142 | 59 | `exclude={'tag_ids', 'notes'}` → `''` for `'tag_ids'` | equivalent | `account_dict` is built from 15 named keys; an extra `tag_ids` key in `account_input` is never read. | — |
| 143 | 59 | same, `'notes'` → `''` | equivalent | `AccountCreate` has no `notes` field and the dict is built from named keys. | — |
| 148 | 142 | message part `'Account '` → `''` | bug-path | The "does not belong to workspace" text is today's behaviour tagged BUG-440 (`update_account` R2); pass card ACC-U-02 asserts the type only by design, the text is in xfail ACC-U-03. | — (resolves with BUG-440) |
| 149 | 142 | message part `' does not belong to '` → `''` | bug-path | Same as #148. | — (resolves with BUG-440) |
| 150 | 154 | `exclude={'tag_ids', 'notes'}` → `''` for `'tag_ids'` | equivalent | `account_dict` is filled by the loop over 16 named keys; `tag_ids` in `update_input` is never copied. | — |
| 151 | 154 | same, `'notes'` → `''` | equivalent | `AccountUpdate` has no `notes` field; named-key loop as #150. | — |
| 176 | 410 | message part `'Tag '` → `''` | bug-path | The "is not assigned to account" text is today's behaviour tagged BUG-879 (`unassign_tag` R4); pass cards ACC-UN-06 / UN-08 / UN-10 assert the type only by design, the text is in xfail ACC-UN-07 / UN-09. | — (resolves with BUG-879) |
| 177 | 410 | message part `' is not assigned to '` → `''` | bug-path | Same as #176. | — (resolves with BUG-879) |

Score = 174 / (186 − 6 − 1 − 5) = 174 / 174 = 100%. No `test-weakness`, `case-missing` or `spec-gap` survivor. No timeouts.

## Traceability
cases 189 · tests 189 · unmatched: none (every case ID in exactly one test name and docstring; no test without a case ID; every `# [local-coder] <ID>` comment matches its test) · marker mismatches: none (100 `pass` cards without marker; 89 `xfail` cards with `xfail(strict=True)` naming exactly the listed BUG IDs; every BUG ID exists in `docs/testing/bugs.md`). Authors: 182 local-written, 7 Claude-written (ACC-U-01, U-16, U-28, ACC-C-17, ACC-A-14, ACC-S-02, ACC-UN-12).

Checked by script (AST) over all 189 tests: `# Then N` comments are exactly 1..K for a card with K Then lines; no `try` / `except`, no `skip`, no `pytest.raises` with a type other than `ValueError` / `ValidationError` / `IntegrityError` / `TypeError`; the only `patch` calls are the two `utcnow` names of the spec's Externals; no `snap(` / `written(` assignment after the first `M.` call; no unused fixture argument or variable; no fixture used without being requested.

`--runxfail`: 89 failures = the 89 xfail tests, each inside the Then block of its card's "Fails today on" (0 mismatches): 43 on the named assertion, 38 `DID NOT RAISE` (ACC-UN-14 the reverse case, `DID NOT RAISE TypeError`), 8 with the designed `TypeError` on the call line before `# Then 1` (ACC-C-19, U-42, G-05, G-06, S-02, D-12, UN-12, UN-13). No setup, fixture or import error.

## Commands run
- `.venv/Scripts/python.exe -m pytest tests/unit/managers/test_account_manager.py -q -p no:cacheprovider --cov=app.managers.account_manager --cov-branch --cov-report=term-missing`
  → `app\managers\account_manager.py 100 0 42 0 100%` · `100 passed, 89 xfailed, 15 warnings in 16.05s`
- `.venv/Scripts/python.exe -m pytest tests/unit/managers/test_account_manager.py -q -p no:cacheprovider --runxfail -rf --tb=short --junitxml=<scratch>/v2_runx.xml`
  → `89 failed, 100 passed in 7.80s`
- Two more plain runs (flakiness): `100 passed, 89 xfailed in 8.00s` · `100 passed, 89 xfailed in 7.91s`
- `.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/managers/account_manager.py tests/unit/managers/test_account_manager.py --json <scratch>/acc_mut_r2.json`
  → `Mutants: 186 · killed 174 · timeout 0 · survived 12 · score 94%` (raw, before classification). Run on its own, not in parallel with the pytest runs (both use the same test database).

## Local-coder patterns
No recurring mistake is left in the 182 local-written tests after fix round 1 (0 findings). For the record, the patterns of the previous round and whether the fix round's prevention is in place:

| Pattern (previous round) | Count then | Count now | Prevention |
|---|---|---|---|
| "In particular …" / "same `id`" literals after `unchanged(X)` dropped | 17 tests (e.g. ACC-A-10, ACC-D-13) | 0 | Helper-sheet rule added ("values after the dash of `unchanged` get one assert each"). Still worth adding: card wording with one obligation per numbered line, and a runner check that counts the backticked comparisons of such a line. |
| Helper-sheet example copied whole (`deleted=True, account_code="SUP-001"`) | 8 tests (e.g. ACC-G-04, ACC-T-08) | 0 | Sheet now has the plain rows `A1, but deleted` and `A9 (in W2), but deleted`, one change per example row. |
| Compound Then line half implemented (global audit count skipped) | 3 tests (ACC-U-40, D-06, A-11) | 0 | Sheet rule "the global audit count comes first". Runner check still open: "`<table>` has exactly N rows" requires `count_rows(db, <Model>) == N`. |
| Given qualifier lost, value carried over from the neighbouring card, row order | 3 tests (ACC-G-06, U-25, UN-01) | 0 | Runner checks still open: "deleted" / "inactive" / "in W2" in a Given row require the matching builder keyword; builder keywords that occur nowhere in the card are rejected. |
| Literal replaced by a derived value or a name | 3 tests (ACC-A-11, AT-09, U-36) + ACC-UN-09 found by the executor | 0 | Sheet rule "expected values are the card's literals, never read from a row or a before variable". Runner check still open: every quoted string and number of a Then line occurs literally in the test body. |
| First half of a two-part "returns:" line without an assertion (found by the executor's sweep) | 4 tests (ACC-S-01, T-01, C-29, U-11) | 0 | Sheet rule "a line with two parts needs both asserts; schema 'returns' gets an `isinstance` assert". |

The sheet rules are untested until the next local-coder run; the runner checks listed as "still open" are the ones that would have rejected these tests mechanically.
