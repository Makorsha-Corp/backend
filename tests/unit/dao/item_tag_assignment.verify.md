# Verification — `app/dao/item_tag_assignment.py`

> **Verdict:** PASS
> Tests: 80 passed · 8 xfail-marked (3 strict, 5 non-strict; printed as `8 xfailed`, `7 xfailed, 1 xpassed` or `6 xfailed, 2 xpassed` depending on the plan) (reproduced ✅) · coverage 100% branch (28 statements, 4 branches)
> Mutation: 27 mutants · 27 killed · 0 survived → score 100% (after excluding 0 equivalent, 0 dead, 0 bug-path); 19 hand variants + 6 reference-fix runs on top
> Source commit: e48a092 (`app/dao/item_tag_assignment.py` unchanged in the working tree) · Cases revision: none stated (READY, 88 cases; spec APPROVED 2026-10-17)

## Summary
These tests can be trusted. I read all 88 tests against their cards line by line, with no sampling: every Given row and every keyword, the When call and each argument, and every numbered Then line with every check it lists. As a second, independent check, a script (`itav/audit.py`) rebuilt the expected body of all 75 vocabulary cards (68 local and 7 exemplars) from the card text and the helper sheet. It compared each body statement by statement, including the `# Then N` comments and the argument set: **0 functional differences**. The script also reported **43 of 43 planted mistakes** (`itav/selftest.py`), including the trial slip itself: an extra `workspace_id=w2.id` on the L9 link of ITA-INH-13.

- **Local-model tests (68): functional findings in 0 / 68, so 68 of 68 (100%) are right as delivered.** Cosmetic findings in 18 / 68 in the file as it stands: the tool cut 17 names, and RM-06 names its re-read variable `row_k1`. As delivered, 4 more had a blank line after the docstring (INH-08, INH-09, INH-11, INH-12; INH-01 also had one and is a cut name). The executor has already removed those 5 blank lines.
- **Claude-written tests (20 = 7 exemplars + 13 `# [claude]`): functional findings in 0 / 20.** Cosmetic findings in 7 / 20: names cut at the same length as the tool cuts them (exemplars TFS-16, CNT-01, INH-04; claude TFS-17, TFI-12, RM-09, RM-14).
- **"Local tests unchanged except 5 blank lines and the reorder" is confirmed** (`itav/delivered_cmp.py`). Against `test_ita.asdelivered.py`, 70 tests (63 local + 7 exemplars) are byte-identical. The other 5 local tests (INH-01, 08, 09, 11, 12) differ only by the one blank line right after the docstring. The 13 tests missing from the copy are exactly the 13 `# [claude]` ones, and every `# [local-coder] <ID>` comment is unchanged. The scaffold differs only as the notes say: the `patch` import, the dropped `# noqa: F401` comments, the claude helper header, and `order_part` renamed to `order_part_of`.
- **ITA-INH-13, the re-run trial card, is faithful as delivered:** `mk_link(of=i9, to=t9)` with no keyword, and no variable because nothing uses L9. Then 1 is `sorted(ids(result)) == [l1.id, l2.id]` and Then 2 is `len(result) == 2`.
- **Stability:** I ran the whole file 6 times on the default plan, once with coverage, once with `--runxfail`, twice with forced sequential scans and twice with forced index scans. No run was red, and all 80 pass cards passed every time. Only the three non-strict physical-order cards move (TFS-18, TFI-13, INH-14). **No strict xfail and no pass card rests on row order or collation.**
- **Then lines that never run today** (TFS-19 Then 5, TFI-14 Then 3–4, INH-15 Then 3): I read them against their cards, and they are right. With the three intended `ORDER BY`s patched in-process, the full file gives **88 / 88 under `--runxfail`** on the default, sequential and index plans.
- **Mutation:** 27 / 27 killed. Every requested hand variant is caught, and so are 13 more.

## Findings
None functional. Cosmetic only — none blocks PASS, all optional:

| # | Kind | Case / line | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | Naming (local) — COSMETIC | ITA-TFS-01, TFS-09, TFS-11, TFS-13, TFS-14, TFI-01, TFI-06, TFI-10, TFI-11, EX-06, CNT-02, RM-02, RM-10, RM-11, INH-01, INH-03, INH-05 (17 tests) | The test name is cut at the tool's length limit, so it does not carry the whole title. The docstring carries the full ID, title and Rules line in all 88 tests. The tool made this cut, not the model. | `test_ita_tfs_09__a_deleted_tag_is_never_listed_an_item_with_only_a_deleted_tag_maps_to` | optional — tool (`local_coder.py`) |
| 2 | Variable name (local) — COSMETIC | ITA-RM-06 lines 1331–1332 | Then 2 ("re-read K1: `usage_count == 4`") is written `row_k1 = reread(db, k1)` / `assert row_k1.usage_count == 4`. The sheet says `row = reread(db, …)`. The re-read is the same row, the check is the same, and nothing else in the test uses `row`. | audit: "re-read variable named other than `row`: ['ITA-RM-06']" | optional — executor |
| 3 | Layout (local, as delivered) — COSMETIC, already fixed | ITA-INH-01, INH-08, INH-09, INH-11, INH-12 | As delivered, each had a blank line after the docstring. These cards' Given is "No link exists.", so they have no Given code. The executor removed the blank lines at finishing. | `audit.py ../test_ita.asdelivered.py`: "blank line right after the docstring: ['ITA-INH-01', 'ITA-INH-08', 'ITA-INH-09', 'ITA-INH-11', 'ITA-INH-12']" | — (done) |
| 4 | Naming (exemplar / claude) — COSMETIC | ITA-TFS-16, CNT-01, INH-04 (exemplars); TFS-17, TFI-12, RM-09, RM-14 (claude) | Names are cut at the same length as the tool's cut. | `test_ita_tfs_17__names_that_differ_only_in_case_come_back_in_id_order_then_the_other` | optional — executor |

I checked for each of the following, both by reading and with the rebuild script, and found none in the 68 local tests.

- **Given rows.** No row is missing, extra or out of order, and no row is swapped with another of the same kind.
  - Items: I1 / I2 / IX / I9 are exactly the card's. Examples: TFS-08 and TFI-02 link I2, not I1. TFS-12, TFI-09, EX-08, RM-03 and CNT-02 link IX. TFS-14, TFI-11, CNT-04, CNT-05 and CNT-08 link I9. CNT-11's pending P1 is on I2.
  - Tags: T1 / T2 / TS / TD / T9 are exactly the card's. Examples: TFS-01 is I1→T1, I1→TS, I2→T2. TFI-01 is T1, T2, TS, then I2→T1. TFS-09 has TD on both I1 and I2. CNT-09 has TD on I1 and I2. RM-01 links T1, T2, TS.
  - Further rows: RM-06 builds K1 `"Gasket"` / `"gasket"` with `usage_count=4`.
- **Keywords.**
  - `workspace_id=w2.id` is on exactly the rows whose card says "but `workspace_id W2.id`": TFS-10, TFS-11, TFI-05, TFI-06, EX-05, EX-06 (and exemplar RM-05).
  - `workspace_id=w1.id` is on exactly the I9 rows whose card says "but `workspace_id W1.id`": TFS-14, TFI-11, CNT-08.
  - The links to T9 (TFS-13, TFI-10, EX-09, CNT-10) and the W2 link I9→T9 (CNT-04, CNT-05, INH-13) carry **no** `workspace_id`. This is the trial slip, and it did not recur in the delivered file.
  - No row has a keyword its card does not list.
- **Code lines in the Given.**
  - `p1 = ItemTagAssignment(...)` and `db.add(p1)` are unflushed and use the card's values: TFS-20 has I1 / T2, EX-10 has I1 / T1, CNT-11 has I2 / T1, RM-10 has I1 / T2.
  - RM-12 has `_loaded = len(i1.tag_assignments)`, as the sheet prescribes.
  - INH-16 has `l1_id = l1.id` after both rows.
- **When call.** No argument is changed, dropped or added.
  - The `item_ids` lists are the card's: `[i2.id, i1.id]` in TFS-05, `[i1.id, i2.id, i1.id]` in TFS-06, `[i1.id, MISSING]` in TFS-07, `[]`, `None`.
  - `workspace_id=w2.id` is in TFS-11, TFI-04, TFI-06, EX-06, CNT-05 and CNT-07, and `workspace_id=MISSING` is in CNT-06.
  - `item_id=MISSING` is in TFI-03 and RM-08. EX-04 passes `item_id=MISSING, tag_id=MISSING`.
  - Every `create` dict matches the card. INH-02 passes `"assigned_by": u2.id`, INH-09 passes `"assigned_by": MISSING`, and INH-05 passes `"workspace_id": w2.id`. INH-03 passes `ItemTagAssignmentCreate(item_id=i1.id, tag_id=t1.id)`, and INH-16 calls `dao.remove(db, id=l1_id)`.
- **Then lines.**
  - No line is skipped, and no assertion sits under the wrong `# Then N`.
  - Every multi-value re-read line has one assert per value: INH-01 Then 2 and INH-12 Then 2 have 3 values each.
  - Checks keep the card's form:
    - `sorted(...)` appears only where the card writes it (TFS-01, TFI-01, TFI-09, INH-13).
    - `ids(...) == [x]`, `result == []`, `result == {i1.id: []}` and the dict equalities of CNT-01 … CNT-11 are exact.
    - `is True` / `is False`, `is` (TFS-15), `not in` (CNT-02, CNT-03), `l1 not in db` / `l3 in db` (RM-11) and `isinstance` stay as the card writes them.
    - `count:` lines use the card's numbers: 0, 1, 2, 4, 6. RM-06's 4 items and 6 tags were not computed from `before`.
  - The raises lines keep `IntegrityError`, the `.orig` class (`NotNullViolation`, `UniqueViolation`, `ForeignKeyViolation`) and the exact text: `"workspace_id"`, `"uq_item_tag"` and the four `item_tag_assignments_*_fkey` names.
- **Write cards.**
  - "re-read the returned row" is `reread(db, result)`, and "re-read links_of(I1)[0]" is `links_of(db, i1)[0]` (RM-10).
  - Every `unchanged` and `nothing written` snapshot is taken after the last Given line and before the call, on the row the Then line names. RM-04 snapshots L2 and L3, RM-06 snapshots K1 and I1, and RM-07 takes `before` and then L2.
  - "nothing written" is always `written(db) == before`, never `== 0`.
- **Swallowed failures and extra mocks: none.**
  - `pytest.raises` appears only on the 6 local `raises:` cards (INH-03, 05, 06, 07, 08, 09). Each has the card's type, `# Then 1` directly above it, and the call inside `db.begin_nested()`.
  - No local test has a `try`, patches anything, or has an unused fixture argument (`ruff check`: clean).

I read the 20 Claude-written tests the same way and found no functional finding:
- **Exemplars (7).** All match their cards, and they match the helper sheet's copies verbatim.
  - TFS-16 has the names `"delta"`, `"alpha"`, `"charlie"` and system `"zulu"`, with links I1→K1, K4, K2 and I2→K3, K2.
  - INH-17 takes `at_before` after L1 and checks the three values in Then 4.
- **Recorder cards (TFS-04, TFS-19, TFI-14, INH-15).**
  - The recorder surrounds the When only. `recorder.sql()` fails loudly unless exactly one SELECT was sent.
  - Every `statement:` line is one assert with the card's exact text:
    - TFS-04: `statements == []`.
    - TFS-19, TFI-14: `"ORDER BY" in sql`, `"lower(item_tags.name)"` / `"item_tags.id"` in `order_part`.
    - INH-15: `"item_tag_assignments.id"` in `order_part`.
  - TFS-04 can see a query: with `tfs_query_on_empty` it turns red.
- **Order cards (TFS-17, TFS-18, TFI-12, TFI-13, INH-14).**
  - The names and codes are exact: `"bravo"`, `"Alpha"`/`alpha_upper`, `"alpha"`/`alpha_lower`, system `"Charlie"`; two `"Bolt"` (`bolt_a`, `bolt_b`).
  - In TFS-18 and TFI-13, K2 is linked before K1.
  - In INH-14, `l1.assigned_by = u2.id` and `db.flush()` come after L2.
  - Then 2 is exactly the card's list.
- **RM-09 (rolled back).**
  - The spy is `patch.object(db, "commit", wraps=db.commit)`, and `sp = db.begin_nested()` is directly before the call.
  - Then 1–2 run inside the savepoint, then `sp.rollback()`, then Then 3 (2 rows), Then 4 (`tag_id`, `assigned_by` of L1) and Then 5 (`call_count == 0`).
- **RM-13, RM-14, INH-18.**
  - In RM-13, the edit and flush of I1 sit under `# Then 2`, before its assertion.
  - In RM-14, `new = dao.create(...)` sits under `# Then 2`.
  - In INH-18, the When is the card's direct `DELETE`, and Then 3 counts by `k1_id`, taken before the When.
- **Markers.**
  - 3 markers are `strict=True` and 5 are `strict=False`, exactly the cards marked "(non-strict)".
  - Each reason names the card's bug and its `bugs.md` title: BUG-933 "Item list tag chips sorted by collation name with no tie-break", BUG-932 "An item's tags on its summary have no sort order", BUG-100 "BaseDAO list methods have no sort order".

### xfail tests
All 8 xfail cards are `Author: claude`; the local model got none.

| Card | Strict | Fails on (`--runxfail`) | Actual | Then lines never executed today | Against the scratch fix |
|---|---|---|---|---|---|
| TFS-17 | no | Then 2, line 692 | `[K3, K2, K1, K4]` ("alpha" < "Alpha" under `English_United States.1252`), as the card predicts | — | passes (fix933) |
| TFS-18 | no | Then 2, line 715 (when it fails) | `[K2, K1]` | — | passes |
| TFS-19 | yes | Then 4, line 737 | `order_part` = ` item_tag_assignments.item_id, item_tags.name` (Then 1–3 pass) | Then 5 (739) | passes |
| TFI-12 | no | Then 2, line 934 | `[K1, K2, K3, K4]` (insert order) | — | passes (fix932) |
| TFI-13 | no | Then 2, line 956 (when it fails) | `[K2, K1]` | — | passes |
| TFI-14 | yes | Then 2, line 974 | no `ORDER BY` | Then 3–4 (976, 978) | passes |
| INH-14 | no | Then 2, line 1745 (when it fails) | `[L2, L1]` | — | passes (fix100) |
| INH-15 | yes | Then 2, line 1763 | no `ORDER BY` (`… LIMIT … OFFSET …`) | Then 3 (1765) | passes |

Every xfail fails on its card's "Fails today on" line, with the value the card predicts. None fails on a setup or import error.

The scratch reference (`itav/plug/ref_ita.py`) is a pytest plugin that patches `ItemTagAssignmentDAO` in-process; `app/` is untouched. Its `same` variant re-types today's code and reproduces today's results. It has three fixes:
- fix933: `ORDER BY item_id, lower(name), id`
- fix932: `ORDER BY lower(name), id`
- fix100: `ORDER BY id` in `get_by_workspace`

With all three together, `--runxfail` gives **88 passed** on the default plan, under forced sequential scans and under forced index scans. With markers on, it gives 80 passed, 5 xpassed (non-strict), and 3 failed (TFS-19, TFI-14, INH-15: XPASS(strict), the intended alarm).

Under `--runxfail`, each fix alone turns green exactly its own cards:
- fix933 alone: TFS-17, 18, 19 pass.
- fix932 alone: TFI-12, 13, 14 pass.
- fix100 alone: INH-14 and INH-15 pass.

### Stability
| Run | Plan | Result | XPASS |
|---|---|---|---|
| 1–2 | default | 80 passed, 6 xfailed, 2 xpassed | TFS-18, TFI-13 |
| 3–4 | default | 80 passed, 8 xfailed | — |
| 5–6 | default | 80 passed, 7 xfailed, 1 xpassed | INH-14 |
| coverage | default | 80 passed, 6 xfailed, 2 xpassed | TFS-18, TFI-13 |
| seq 1–2 | `PGOPTIONS` enable_indexscan / bitmapscan / indexonlyscan off | 80 passed, 6 xfailed, 2 xpassed | TFS-18, TFI-13 |
| index 1–2 | `PGOPTIONS` enable_seqscan off | 80 passed, 7 xfailed, 1 xpassed | INH-14 |
| runxfail seq 1–2 | as above | 6 failed (TFS-17, 19, TFI-12, 14, INH-14, 15), 82 passed | — |
| runxfail index 1–2 | as above | 7 failed (TFS-17, 18, 19, TFI-12, 13, 14, INH-15), 82 passed | — |

`PGOPTIONS` reaches the connection (`SHOW enable_seqscan` → `off`). No run was red. No pass card and no strict xfail changed outcome. The outcomes match the notes' Stability section.

**Order and collation, card by card:**
- **No pass card rests on row order or collation.**
  - Every list check with more than one element uses `sorted(...)`, except TFS-16. TFS-16 uses single-word, all-lower-case ASCII names, which every collation, `C` included, orders alike.
  - All other list checks have one element (`ids(...) == [x]`, `links_of(...)[0]` when exactly one row exists, `result[i1.id][0]` with one tag), or are `[]` or a dict equality.
- **No strict xfail rests on order or collation.** TFS-19, TFI-14 and INH-15 inspect the SQL text only. Their Then 1–2 lines check one-element results.
- **The five non-strict cards are right to be non-strict.**
  - TFS-18, TFI-13 and INH-14 flip with the plan.
  - TFS-17 depends on the server's collation.
  - TFI-12 failed in every run, but it relies on physical row order, so non-strict is consistent.
- **Absolute count lines.** RM-01, RM-13, INH-01 and INH-03 count `item_tag_assignments`, and RM-06 counts `items` and `item_tags`, across all workspaces. These lines assume no committed rows in `marker_test`. I checked: 0 committed rows in all three tables. Because the `db` fixture rolls back, only a test that really commits could break these lines.

## Surviving mutants
None from `mutate.py`: 27 / 27 killed. The mutants were:
- `return None` on all 5 methods and on the empty-list early return
- the `if not item_ids` negation and the dropped `not`
- `is not → is`
- every `== → !=` in the joins and filters
- `True → False` on both `ItemTag.is_active` and on `Item.is_active`

The run used the file alone from my side. The `same` re-typed variant was 80 / 80 green in every run, so no kill came from a disturbed database.

Hand-made variants (`itav/plug/ref_ita.py`, patched in-process; `app/` untouched), run like `mutate.py` (`-m "not xfail"`). Every one is killed:

| Variant | Result | Caught by |
|---|---|---|
| `db.commit()` in `remove_all_tags_from_item` (requested) | killed | RM-09: the commit closes the savepoint, so `sp.rollback()` raises `ResourceClosedError` before Then 3–5. RM-12 also catches it: the commit expires the collection, giving 0 instead of 2. |
| `get_tags_for_item` without `is_active` (requested) | killed | TFI-07, TFI-08 |
| `get_tags_for_items` without `is_active` (requested) | killed | TFS-09 |
| count without `Item.is_active` (requested) | killed | CNT-02 |
| `assignment_exists` without the workspace (requested) | killed | EX-05 |
| `get_tags_for_items`: each key gets the next requested item's list (requested) | killed | TFS-16, TFS-01, TFS-05, TFS-06, TFS-07, TFS-09 |
| `get_tags_for_items`: keys in ascending id order, not the request's order | killed | TFS-05 |
| `get_tags_for_items` runs a query for `[]` | killed | TFS-04 |
| `get_tags_for_items` / `get_tags_for_item` without the link workspace | killed | TFS-10 / TFI-04, TFI-05 |
| count without the link workspace | killed | CNT-04 … CNT-07 |
| remove without the workspace | killed | RM-05 |
| remove without `db.flush()` | killed | RM-10 |
| remove with `synchronize_session=False` | killed | RM-11 |
| remove followed by `expire_all()` | killed | RM-12 |
| `assignment_exists` hides deleted tags | killed | EX-07 |
| count hides deleted tags | killed | CNT-09 |

## Spec coverage
Every rule of the spec has at least one card and test. I checked this by script (`itav/rules.py`), matching the spec's rules against each card's `Rules:` line:
- `get_tags_for_items` R1–R7
- `get_tags_for_item` R1–R5
- `assignment_exists` R1–R5
- `count_active_items_per_tag` R1–R6
- `remove_all_tags_from_item` R1–R6
- inherited R1–R5

That is 34 rules. Errors rows 1–3 are also covered (INH-03 … INH-09), and so is the model-facts cascade (INH-18). Deliberately not covered, as recorded in the cases file:
- `get_tags_for_item` R3's last sentence ("same tags as `get_tags_for_items`"). Every situation has a card for both methods with the same Given, so it is covered indirectly.
- The keyword-only note, which is not a rule (Spec gap 2).
- BUG-934 and BUG-935, which are deferred to the item manager.

**Rules without a card: none.**

## Traceability
- cases 88 · tests 88 (68 `# [local-coder]`, 13 `# [claude]`, 7 exemplars) · unmatched: none · marker mismatches: none.
- Every docstring is `<ID> — <title>.` plus `Rules: <card Rules line>`, exactly.
- The `# Then N` comments run 1 … N in all 88 tests and match each card's Then count.
- The 13 `Author: claude` cards are exactly the 13 `# [claude]` tests, and no vocabulary card sits under `# [claude]`.
- The non-exemplar tests are in card order.
- BUG-932, BUG-933 and BUG-100 exist in `bugs.md`.

## Commands run
```
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_item_tag_assignment.py -q -p no:cacheprovider --cov=app.dao.item_tag_assignment --cov-branch --cov-report=term-missing -rX
  app\dao\item_tag_assignment.py  28  0  4  0  100%
  80 passed, 6 xfailed, 2 xpassed, 1 warning
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_item_tag_assignment.py -q -p no:cacheprovider --runxfail -rf --tb=line
  8 failed, 80 passed (lines 692, 715, 737, 934, 956, 974, 1745, 1763)
<scratch>/itav/drive.py none real   (x6 default, x2 PGO=seq, x2 PGO=index)     (Stability table)
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/dao/item_tag_assignment.py tests/unit/dao/test_item_tag_assignment.py --json <scratch>/itav/mut.json
  Mutants: 27 · killed 27 · timeout 0 · survived 0 · score 100%
<scratch>/itav/audit.py                     cards 88 · tests 88 · rebuilt 75 · problems 0
<scratch>/itav/audit.py ../test_ita.asdelivered.py   problems = only the 13 missing [claude] tests; blank line after docstring: INH-01, 08, 09, 11, 12
<scratch>/itav/selftest.py                  43 of 43 planted mistakes reported
<scratch>/itav/delivered_cmp.py             identical 70; whitespace-only 5 (one blank line each); real differences: none
<scratch>/itav/rules.py                     34 rules, rules without a card: none; cards without a test: none
<scratch>/itav/drive.py runx fix933+fix932+fix100                88 passed (default, PGO=seq, PGO=index)
<scratch>/itav/drive.py runx same | fix933 | fix932 | fix100     (xfail table)
<scratch>/itav/drive.py plain same | fix933+fix932+fix100
<scratch>/itav/drive.py pass <19 hand variants>                 (variant table)
ruff check tests/unit/dao/test_item_tag_assignment.py            All checks passed
```
`<scratch>` = `C:\Users\User\AppData\Local\Temp\claude\E--Projects-Makorsh-Corp-backend\5dcda696-13dd-4b73-983c-11d3c05a8ed9\scratchpad`. Nothing under `app/`, the tests, cases, spec, notes or runner was edited. The model server was not touched.

## Local-coder patterns
I found no functional mistake in the 68 delivered tests. The patterns below come from the cosmetic findings and from the retries the runner rejected (`item_tag_assignment.local-run.json`: 58 first try, 8 on attempt 2, 2 on attempt 3, 0 handed back). The trial's unfaithful ITA-INH-13 was deleted and re-run before delivery.

| Pattern | Count | Examples | What would prevent it |
|---|---|---|---|
| Extra `workspace_id=` on a link that already takes its item's workspace (rejected; one accepted in the trial) | 4 retries + 1 trial acceptance | TFS-13, TFI-10, EX-09, CNT-10 (`workspace_id=w1.id` on a link to T9); trial INH-13 (`workspace_id=w2.id` on L9) | Runner fix P23 (builder keywords only from the card's Given rows) and the sheet's L9 row. `audit.py` now also catches the planted INH-13 slip. Keep P23. |
| Fixture used but missing from the argument list (rejected) | 2 retries | TFS-09 (`t1`), CNT-11 (`u1`) | Runner fix P24 (`tidy_args`) adds it automatically. |
| Unused `before` / `before_items` snapshot copied from an exemplar (rejected) | 4 retries | INH-02, INH-10, CNT-04, RM-06 | The tool's unused-variable check catches it. A sheet line could say "`before` only with a `nothing written` line" (also seen in item_tag). |
| `count:` numbers asserted against `before` values instead of the card's number (rejected) | 1 (3 attempts) | RM-06 | Already rejected by the runner. The sheet's `count:` bullet could add: "the card's number, never `before[...]`". |
| `# Then 1` missing (rejected) | 1 | CNT-04 | Already rejected by the runner. |
| Re-read variable named after the row (`row_k1`), not `row` (delivered, cosmetic) | 1 | RM-06 | Optional. A sheet line: "always `row = reread(db, x)`, even when there are other rows". |
| Blank line after the docstring when the card has no Given code (delivered, cosmetic) | 5 | INH-01, INH-08, INH-09, INH-11, INH-12 | Recurs from item_tag (INH-11). The tool could strip a blank line directly after the docstring. |
| Name cut by the tool at its length limit (cosmetic, tool) | 17 | TFS-09, INH-05 | The tool's name rule; the docstring carries the full title. |
