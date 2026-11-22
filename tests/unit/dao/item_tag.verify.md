# Verification — `app/dao/item_tag.py`

> **Verdict:** PASS
> Tests: 81 passed · 11 xfail-marked (6 strict, 5 non-strict; printed as `11 xfailed`, or `8 xfailed, 3 xpassed` when the plan is an index scan) (reproduced ✅) · coverage 100% branch (24 statements, 4 branches)
> Mutation: 22 mutants · 22 killed · 0 survived → score 100% (after excluding 0 equivalent, 0 dead, 0 bug-path)
> Source commit: e48a092 · Cases revision: none stated (READY, 92 cases; spec APPROVED 2026-10-17)

## Summary
These tests can be trusted. I read all 92 tests against their cards line by line, with no sampling: every Given row and column, the When call and each argument, and every numbered Then line with every check it lists. As a second, independent check, a script (`itgv/audit.py`) rebuilt the expected body of all 76 vocabulary cards (70 local and 6 exemplars) from the card text and the helper sheet. It compared each body statement by statement, including the `# Then N` comments and the argument set: **0 functional differences**. The script also reported **32 of 32 planted mistakes** (`itgv/selftest.py`). The plants included a swapped "alpha"/"Alpha" name, a system tag built as a normal tag, T1/T2 rows swapped, W1/W2 swapped in the When, one of three values of a re-read line dropped, a `sorted()` dropped, a membership check turned into `==`, a snapshot moved after the call, and a pending rename dropped or flushed.

- **Local-model tests (70): functional findings in 0 / 70, so 70 of 70 (100%) are right as delivered.** Cosmetic findings in 9 / 70: the tool cut 8 names, DEC-11 takes its two snapshots in the opposite order, and INH-11 has a blank line after the docstring; INH-11 is also one of the 8 cut names.
- **Claude-written tests (22 = 6 exemplars + 16 `# [claude]`): functional findings in 0 / 22.** Cosmetic findings in 6 / 22, all names cut at the same length as the tool cuts them (exemplars ACT-01, INC-01; claude ACT-11, ACT-13, INC-13, DEC-15).
- **"Byte-identical, only moved into card order" is confirmed.** Against `test_itg.asdelivered.py`, all 70 local tests and all 6 exemplars match line for line. The 16 tests missing from the copy are exactly the 16 `# [claude]` ones. The scaffold differs only by the `patch`, `event`, `insert` and `text` imports, plus `bulk_tags`, `StatementRecorder` and `order_part_of`. The tests now follow card order. The 6 exemplars match the helper sheet verbatim.
- **Stability:** I ran the whole file 6 times on the default plan, once with coverage, once with `--runxfail`, twice with a forced sequential scan and twice with a forced index scan. No run was red, and all 81 pass cards passed every time. Only the three non-strict "moved row" cards move: SYS-09, ACT-12 and INH-18 XPASS under an index scan and xfail under a sequential scan. No strict xfail and no pass card rests on row order or collation (see Stability).
- **Then lines that never run today** (SYS-10 Then 3–4, ACT-13 Then 5, INC-11 / DEC-13 / DEC-14 Then 3, INH-19 Then 3): read against their cards, they are right. Against a scratch reference with all four fixes, the full file passes **92 / 92 under `--runxfail`** on the default, sequential and index plans.
- **Mutation:** 22 / 22 killed. I also ran 28 hand variants (pass mode, like `mutate.py`) and 6 reference-fix runs. Every requested variant is caught. Every variant that breaks a pass rule turns a pass card red. The only two not caught are an equivalent variant and a bug-path variant.

## Findings
None functional. Cosmetic only — none blocks PASS, all optional:

| # | Kind | Case / line | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | Naming (local) — COSMETIC | ITG-SYS-01, SYS-06, DEC-01, DEC-12, INH-11, INH-12, INH-13, INH-17 (8 tests) | The test name is cut at the tool's length limit, so it does not carry the whole title. The docstring carries the full ID, title and rules in all 92 tests. The tool made this cut, not the model. | `test_itg_inh_13__update_with_an_itemtagupdate_changes_the_name_and_keeps_a_colour_sent` | optional — tool (`tests/unit/_tools/local_coder.py`) |
| 2 | Snapshot order (local) — COSMETIC | ITG-DEC-11 lines 1318–1319 | `before_t2 = snap(db, t2)` comes before `before = written(db)`. The sheet and the twin card INC-09 have the other order. Both snapshots are taken after the last Given line and before the call, so the test checks exactly the same thing. | audit: "snapshot order differs from the sheet's: ['ITG-DEC-11']" | optional — executor |
| 3 | Layout (local) — COSMETIC | ITG-INH-11 line 1559 | There is a blank line right after the docstring (the card has "No tag exists.", so there is no Given code). | audit: "blank line right after the docstring: ['ITG-INH-11']" | optional — executor |
| 4 | Naming (exemplar / claude) — COSMETIC | ITG-ACT-01, INC-01 (exemplars); ACT-11, ACT-13, INC-13, DEC-15 (claude) | Names are cut at the same length as the tool's cut. | `test_itg_act_13__the_active_tag_query_asks_for_system_first_then_name_case_insensitive` | optional — executor |

Checked for and **not** found in any of the 70 local tests, both by reading and by the rebuild script:
- **Given rows:** no missing, extra or reordered row, and no row swapped with another of the same kind.
  - Names and codes are exact. This covers the deliberate same-code pairs: CODE-17 has `"Bolt Small"` and `"Bolt Large"`, both `bolt_part`; INH-12 adds a second `"Spare Part"` / `spare_part`.
  - ACT-10 keeps `"delta"`, `"alpha"` (user tags), then `"yarn"`, `"bolt"` (system tags), all lower-case as the card writes them.
  - ACT-09 inserts Anchor and Bracket first, then the system tags **Zinc Plate** and **Yarn Spool**.
- **System tag or normal tag:** `mk_system_tag` is used on exactly the rows the card calls "system tag":
  - CODE-16; SYS-01 S1, S2 (T3 normal); SYS-02 S1, SD; SYS-03, SYS-04 S1, S9; SYS-05; SYS-06 SD (T1 normal); ACT-03 SD; ACT-09 and ACT-10 S1, S2; INC-07; DEC-10.
  - No row passes `is_system_tag`.
- **Extra keywords:**
  - `workspace_id=w2.id` is on exactly the rows whose card says "but `workspace_id W2.id`": CODE-02, SYS-03, SYS-04, ACT-04, ACT-05, ACT-07, INC-04, INC-05, DEC-07, DEC-08, INH-17, INH-21, INH-23.
  - `is_active=False` is on exactly the TD / SD rows.
  - `usage_count` values are exact: 2, 5, −2, 4, 3, 1.
  - INC-09 and DEC-11 carry `color="#AA3300", icon="bolt", description="M8 bolts"`.
  - INH-13 and INH-16 carry `color="#AA3300"`.
  - No row has a keyword its card does not list.
- **Code lines in the Given:**
  - `t1.name = "Lock Nut"` is unflushed, at the card's place (INC-10, DEC-12).
  - `t1_id = t1.id` is after the rows (INH-24).
- **When call:** no changed, dropped or added argument.
  - `workspace_id=w2.id` in CODE-03-like isolation calls (SYS-04, ACT-05, INC-05, DEC-08); `workspace_id=w1.id` with a W2 tag in INC-04, DEC-07, INH-23; `workspace_id=MISSING` in CODE-04, SYS-05, ACT-06; `tag_id=MISSING` in INC-03, DEC-06.
  - `tag_code` values `"Raw_Material"`, `"RAW_MATERIAL"`, `" raw_material"`, `"raw_material "`, `"raw"`, `"raw_material_"`, `"raw%"`, `""` and `None`.
  - Every `create` dict and the `ItemTagCreate` / `ItemTagUpdate` arguments; `dao.get(db, td.id)` / `dao.get(db, t9.id)`; `dao.remove(db, id=t1_id)`.
- **Then lines:**
  - None is skipped, and no assertion sits under the wrong `# Then N`.
  - **Every multi-value re-read line has one assert per value.** This covers INC-09 and DEC-11 Then 3, 4 and 5 (3 values each) and INH-14 Then 3.
  - No check is weaker than its card. `sorted(...)`, `in {…}` and `len` occur only where the card writes them. `ids(result) == [x]`, `result == []` and `names(result) == [...]` stay exact. `stored_count(db, …)` is used exactly where the card says stored_count, and it is never replaced by the object's value.
  - The raises lines keep the card's type (`IntegrityError` / `DataError`), the `.orig` class, the `column "<name>"` texts, the constraint names and pgcode `"22001"`.
- **Write cards:**
  - Every re-read goes through `reread(db, …)` of the row the line names, or `reread(db, result)` for "the returned row".
  - Every `unchanged` / `nothing written` snapshot is taken after the last Given line and before the call, on the row the Then line names. No test takes a snapshot its card does not ask for.
  - "nothing written" is `written(db) == before`, never `== 0`.
- **Swallowed failures and extra mocks:** none. `pytest.raises` appears only on the 6 local `raises:` cards (INH-02, 03, 04, 06, 07, 09), each with the card's type, `# Then 1` directly above it, and the call inside `db.begin_nested()`. No local test has a `try`, patches anything, or has an unused fixture argument.

I read the 22 Claude-written tests the same way and found no functional finding:
- **Bulk rows (SYS-07, ACT-08).**
  - Each Given is one multi-row Core insert of 101 rows, `f"Seed {k:03d}"` / `f"seed_{k:03d}"` (system) and `f"Crate {k:03d}"` / `f"crate_{k:03d}"` (normal).
  - Each row has the Conventions "tag" columns, and `created_at` comes from the model's default.
  - Then 2 compares with `sorted(n_ids)`, which is "the 101 ids, ascending".
- **Order cards (SYS-08, SYS-09, ACT-11, ACT-12, INH-18).**
  - The names and codes are exact, including the deliberate pairs: SYS-09 has S1 `"Alpha"`/`alpha_upper` and S2 `"alpha"`/`alpha_lower`; ACT-11 has T2 `"Alpha"`, T3 `"alpha"`, then T1 `"bravo"` and T4 `"Charlie"`.
  - The "moved" Given (`description = "moved"`, then `db.flush()`) is on S1 / T1 after the second row.
  - The expected lists are exactly the cards': `["Bolt", "consumable", "Tool"]`, `[t2, t3, t1, t4]`, `[t1, t2]`.
- **Recorder cards (SYS-10, ACT-13, INH-19).**
  - The recorder surrounds the When only, and `[sql] = recorder.selects()` fails loudly unless exactly one SELECT was sent.
  - Every `statement:` line is one assert with the card's exact text: `"ORDER BY" in sql`, `"lower(item_tags.name)"`, `"item_tags.is_system_tag DESC"`, `"item_tags.id"` in `order_part`.
- **Stale object (INC-11, INC-12, DEC-13, DEC-14).**
  - The raw `UPDATE` runs on the same session after the flush, with the card's stored value (10, 10, 10, 0).
  - INC-12 alone calls `db.expire(t1)`.
  - Then 2 reads `result.usage_count` before any re-read, and Then 3 uses `stored_count`.
- **Rollback cards (INC-13, DEC-15).**
  - `sp = db.begin_nested()` is directly before the call. Then 1–2 run inside the savepoint, and then `sp.rollback()`.
  - Then 3 is a re-read (2 / 3), and Then 4 is `commit_spy.call_count == 0` on a `wraps=` spy, so nothing is replaced.
- **Markers:** 6 are `strict=True` and 5 are `strict=False`, exactly the cards marked "(non-strict)". Each reason names the card's bug and its `bugs.md` title.

### xfail tests
All 11 xfail cards are `Author: claude`; the local model got none.

| Card | Strict | Fails on (`--runxfail`) | Actual | Then lines never executed today | Against the scratch fix |
|---|---|---|---|---|---|
| SYS-08 | no | Then 2, line 683 | `['Tool', 'consumable', 'Bolt']` | — | passes (fix929) |
| SYS-09 | no | Then 2, line 705 (when it fails) | `[S2.id, S1.id]` | — | passes |
| SYS-10 | yes | Then 2, line 723 | no `ORDER BY` | Then 3–4 (725–727) | passes: `lower(item_tags.name), item_tags.id` |
| ACT-11 | no | Then 2, line 879 | `[T3, T2, T1, T4]` ("alpha" < "Alpha" under `English_United States.1252`) | — | passes (fix930) |
| ACT-12 | no | Then 2, line 901 (when it fails) | `[T2, T1]` | — | passes |
| ACT-13 | yes | Then 4, line 924 | `order_part` = ` item_tags.is_system_tag DESC, item_tags.name` (Then 2–3 pass) | Then 5 (926) | passes |
| INC-11 | yes | Then 2, line 1111 | 4, not 11 | Then 3 (1113) | passes (fix931) |
| DEC-13 | yes | Then 2, line 1377 | 2, not 9 | Then 3 (1379) | passes |
| DEC-14 | yes | Then 2, line 1395 | 2, not 0 | Then 3 (1397) | passes |
| INH-18 | no | Then 2, line 1692 (when it fails) | `[T2, T1]` | — | passes (fix100) |
| INH-19 | yes | Then 2, line 1710 | no `ORDER BY` (`… LIMIT … OFFSET …`) | Then 3 (1712) | passes |

Every xfail fails on its card's "Fails today on" line, with the value the card predicts. None fails on a setup or import error. With all four fixes together (`fix929+fix930+fix100+fix931`), `--runxfail` gives **92 passed** on the default plan, under forced sequential scans and under forced index scans. With markers on, each fix alone flips exactly its own cards:

| Scratch fix | Strict alarms (XPASS strict → red) | Non-strict that xpass | Pass cards |
|---|---|---|---|
| fix929 (`ORDER BY lower(name), id` in the system list) | SYS-10 | SYS-08, SYS-09 | 81 / 81 |
| fix930 (`is_system_tag DESC, lower(name), id`) | ACT-13 | ACT-11, ACT-12 (+ INH-18 by plan) | 81 / 81 |
| fix100 (`ORDER BY id` in `get_by_workspace`) | INH-19 | INH-18 (+ SYS-09, ACT-12 by plan) | 81 / 81 |
| fix931 (one `UPDATE … SET usage_count = usage_count + 1`; decrement `usage_count - 1 WHERE usage_count > 0`; flush when written; refresh `usage_count`) | INC-11, DEC-13, DEC-14 | — | 81 / 81 (INC-12 control holds) |

**Note on the BUG-931 reference form.** The brief's form `greatest(usage_count - 1, 0)` (`fix931g`) fails pass card **DEC-05**: a stored −2 becomes 0. Spec R3 requires −2 to stay −2, and `bugs.md` BUG-931 asks for "`usage_count - 1` only where `usage_count > 0`". The test is right. Whoever fixes BUG-931 must use the `WHERE usage_count > 0` form, not `greatest`. A version that flushes unconditionally also breaks **DEC-04** (spec R2: nothing is flushed at 0). The cards guard both points.

### Stability
| Run | Plan | Result | XPASS |
|---|---|---|---|
| 1 | default | 81 passed, 9 xfailed, 2 xpassed | ACT-12, INH-18 |
| 2–6 | default | 81 passed, 8 xfailed, 3 xpassed | SYS-09, ACT-12, INH-18 |
| coverage | default | 81 passed, 11 xfailed | — |
| seq 1–2 | `PGOPTIONS` enable_indexscan / bitmapscan / indexonlyscan off | 81 passed, 11 xfailed | — |
| index 1–2 | `PGOPTIONS` enable_seqscan / bitmapscan off | 81 passed, 8 xfailed, 3 xpassed | SYS-09, ACT-12, INH-18 |

`PGOPTIONS` reaches the connection (`SHOW enable_seqscan` → `off`). No run was red. No pass card and no strict xfail changed outcome.

**Order and collation, card by card:**
- **No pass card rests on row order or collation.**
  - The list cards with one element (SYS-02/03/04, ACT-02/03/04/05, plus `result == []` cards) cannot depend on order.
  - SYS-01, ACT-01, SYS-07, ACT-08 and INH-17 compare `sorted(...)`, and CODE-17 uses membership.
  - ACT-09 compares only the `is_system_tag` flags plus a sorted pair, and that order comes from `ORDER BY is_system_tag DESC`.
  - ACT-10 uses single-word all-lower-case ASCII names, which every collation, `C` included, orders alike.
- **No strict xfail rests on order or collation.**
  - SYS-10, ACT-13 and INH-19 inspect the SQL text. ACT-13 Then 1 (`[S1, T1]`) holds through `is_system_tag DESC`.
  - INC-11, DEC-13 and DEC-14 are deterministic (stale object in one transaction).
- **The five non-strict cards are right to be non-strict.**
  - SYS-09, ACT-12 and INH-18 depend on the plan: a HOT update leaves the index pointing at the old tuple chain.
  - ACT-11 depends on the server's collation.
  - SYS-08 failed in every run, but it relies only on the physical row order, so non-strict is consistent.
- **Absolute count lines.** INH-01 … INH-09 count `item_tags` across all workspaces (`count: … exactly 0 / 1 row`), so they assume no committed tag rows in `marker_test`. I checked: 0 committed rows. Because the `db` fixture rolls back, only a test that really commits could break these lines.

## Surviving mutants
None from `mutate.py` (22 / 22 killed: `return None` on every method, the `if tag` and `if tag and usage_count > 0` negations, `And → Or`, `> → >=`, `0 → 1`, `+1 → +2`, `-1 → -2`, every `== → !=` in the filters and `True → False` on `is_system_tag` / `is_active`).

Hand-made variants (`itgv/plug/ref_itg.py`, patched in-process; `app/` untouched), run like `mutate.py` (`-m "not xfail"`):

| Variant | Result | Caught by |
|---|---|---|
| `db.commit()` in `increment_usage_count` | killed | INC-13 (commit spy) |
| `db.commit()` in `decrement_usage_count` | killed | DEC-15 (commit spy) |
| decrement without the floor at 0 | killed | DEC-03, DEC-04, DEC-05 |
| floor `>= 0` instead of `> 0` | killed | DEC-03, DEC-04 |
| decrement flushes even at 0 | killed | DEC-04 |
| negative clamped to 0 | killed | DEC-05 |
| increment reading the stored value (BUG-931 fix, increment only) | 81 / 81 pass cards green; with markers INC-11 → XPASS(strict) → red | — (the intended fix) |
| decrement reading the stored value (BUG-931 fix, decrement only) | 81 / 81 pass cards green; DEC-13, DEC-14 → XPASS(strict) → red | — (the intended fix) |
| active list without `is_active` | killed | ACT-02, ACT-03 |
| code lookup without the workspace | killed | CODE-02, CODE-03, CODE-04 |
| code lookup hides deleted tags | killed | CODE-15 |
| code lookup with `ILIKE` | killed | CODE-05, 06, 11, 14 |
| code lookup trims the code | killed | CODE-07, CODE-08 |
| system list without `is_active` | killed | SYS-02, SYS-06 |
| system list without `is_system_tag` | killed | SYS-01, SYS-06 |
| active list without the workspace | killed | ACT-04 … ACT-07 |
| active list ordered by name only / system last / no order | killed | ACT-09, ACT-10 |
| active list name descending | killed | ACT-10 |
| counters without the workspace (`db.get`) | killed | INC-04, DEC-07 |
| counters skip deleted tags | killed | INC-06, DEC-09 |
| increment without flush | killed | INC-01, 02, 05 … 10, 12, 13 |
| decrement without flush | killed | DEC-01, 02, 08 … 12, 15 |
| system / active list capped at 100 | killed | SYS-07 / ACT-08 |
| increment returns a re-selected row (`populate_existing`) | survived | **equivalent**: the identity map returns the same instance, so `result is t1` still holds and the values are the same |
| system list `ORDER BY name` (collation, no `lower`, no `id`) | survived | **bug-path** (BUG-929): only SYS-08/09/10 target the order; with markers on, SYS-10 stays xfailed (no `lower`) — correct, the variant is not the fix |

## Spec coverage
Every rule of the spec has at least one card and test:
- `get_by_code_in_workspace` R1–R5
- `get_system_tags_in_workspace` R1–R4
- `get_active_tags_in_workspace` R1–R5
- `increment_usage_count` R1–R6 and Side effects
- `decrement_usage_count` R1–R7 and Side effects
- inherited R1–R7 and Errors rows 1–3

Checked by script against each card's `Rules:` line; the counts match the cases file's coverage matrix.

Deliberately not covered, as recorded in the cases file:
- inherited R7, the cascade to `item_tag_assignments` (Spec gap 4). ITG-INH-24 checks only the tag row; the cascade is deferred to the base / assignment DAO cases.
- The "keyword-only parameters" note (Spec gap 3), which is not a rule.

**Rules without a card: none.**

## Traceability
- cases 92 · tests 92 (70 `# [local-coder]`, 16 `# [claude]`, 6 exemplars) · unmatched: none · marker mismatches: none.
- Every docstring is `<ID> — <title>.` plus `Rules: <card Rules line>`, exactly.
- `# Then N` comments run 1 … N in all 92 tests and match the card's Then count.
- The 16 `Author: claude` cards are exactly the 16 `# [claude]` tests, and no vocabulary card sits under `# [claude]`.
- BUG-929, BUG-930, BUG-931 and BUG-100 exist in `bugs.md`, and each marker reason carries the bug's title.

## Commands run
```
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_item_tag.py -q -p no:cacheprovider --cov=app.dao.item_tag --cov-branch --cov-report=term-missing -rX
  app\dao\item_tag.py  24  0  4  0  100%
  81 passed, 11 xfailed, 1 warning
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_item_tag.py -q -p no:cacheprovider --runxfail -rf --tb=line
  11 failed, 81 passed (lines 683, 705, 723, 879, 901, 924, 1111, 1377, 1395, 1692, 1710)
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_item_tag.py -q -p no:cacheprovider -rX     (x6)
  81 passed, 9 xfailed, 2 xpassed  (run 1)
  81 passed, 8 xfailed, 3 xpassed  (runs 2-6)
PGOPTIONS="-c enable_indexscan=off -c enable_bitmapscan=off -c enable_indexonlyscan=off" … (x2)
  81 passed, 11 xfailed
PGOPTIONS="-c enable_seqscan=off -c enable_bitmapscan=off" … (x2)
  81 passed, 8 xfailed, 3 xpassed
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/dao/item_tag.py tests/unit/dao/test_item_tag.py --json <scratch>/itgv/mut.json
  Mutants: 22 · killed 22 · timeout 0 · survived 0 · score 100%
<scratch>/itgv/audit.py          cards 92 · tests 92 · rebuilt 76 · problems 0
<scratch>/itgv/selftest.py       32 of 32 planted mistakes reported
<scratch>/itgv/delivered.py      identical: 70 local + 6 exemplars; missing from copy = the 16 [claude] tests
<scratch>/itgv/drive.py runx fix929+fix930+fix100+fix931            92 passed (default, PGO=seq, PGO=index)
<scratch>/itgv/drive.py plain fix929 | fix930 | fix100 | fix931 | fix931g   (table above)
<scratch>/itgv/drive.py pass <28 hand variants>                      (table above)
```
`<scratch>` = `C:\Users\User\AppData\Local\Temp\claude\E--Projects-Makorsh-Corp-backend\5dcda696-13dd-4b73-983c-11d3c05a8ed9\scratchpad`. Nothing under `app/`, the tests, cases, spec or notes was edited. The model server was not touched.

## Local-coder patterns
I found no functional mistake in the 70 delivered tests. The patterns below come from the cosmetic findings and from the retries the runner rejected (`item_tag.local-run.json`: 62 first try, 7 on attempt 2, 1 on attempt 3, 0 handed back).

| Pattern | Count | Examples | What would prevent it |
|---|---|---|---|
| `w1` used in a `dao.create` dict but not requested as an argument (rejected by the runner, fixed on retry) | 6 retries | INH-03, INH-04, INH-06, INH-07, INH-09, INH-11 | The batch-2 sheet line did not stop it. Better: show a second create exemplar with `(db, w1)` next to INH-05 `(db)`, or have the tool add any fixture name the body uses to the argument list before checking. |
| Unused `before` snapshot copied from an exemplar (rejected) | 2 retries | INH-07, INH-10 | The tool's existing unused-variable check catches it. A sheet line could add: "`before` only with a `nothing written` line". |
| `# Then 1` placed after the `pytest.raises` block (rejected) | 1 | INH-07 (batch 1) | Already fixed by the `raises:` sheet bullet; it did not recur. |
| "nothing written" written as `== 0` (rejected) | 1 | INC-09 (attempt 3) | Already fixed by the "never `== 0`" sheet line. |
| Snapshot lines in a different order from the sheet (delivered, cosmetic) | 1 | DEC-11 | Not worth a check. Optionally: "`before = written(db)` first, then the `before_x` lines". |
| Blank line after the docstring when the card has no Given code (delivered, cosmetic) | 1 | INH-11 | The tool could strip a blank line directly after the docstring. |
| Name cut by the tool at its length limit (cosmetic, tool) | 8 | SYS-01, INH-13 | The tool's name rule; the docstring carries the full title. |
