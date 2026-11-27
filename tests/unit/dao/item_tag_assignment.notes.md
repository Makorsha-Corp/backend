# Execution notes — `app/dao/item_tag_assignment.py`

> Cases: `tests/unit/dao/item_tag_assignment.cases.md` (88 cards, READY) · Tests: `tests/unit/dao/test_item_tag_assignment.py` · Source commit: e48a092
> Result: 88 tests — 80 passed · 8 xfail (3 strict, 5 non-strict; the non-strict ones XPASS on some runs, see Stability) · 0 discrepancies · 0 errors — branch coverage 100%
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/dao/test_item_tag_assignment.py -q -p no:cacheprovider`

## Who wrote what
| Author | Tests | Cards |
|---|---|---|
| Claude, exemplars (scaffold step) | 7 | ITA-TFS-16, TFI-15, EX-01, CNT-01, RM-05, INH-04, INH-17 |
| Local model (`# [local-coder] <ID>`) | 68 | every other card not marked `Author: claude` |
| Claude, finishing (`# [claude] <ID>`) | 13 | ITA-TFS-04, TFS-17, TFS-18, TFS-19, TFI-12, TFI-13, TFI-14, RM-09, RM-13, RM-14, INH-14, INH-15, INH-18 |

The file is in card order, one section per callable (same headers as the cases file); the
exemplars stay together in their own section near the top.

## How the tests are built
- Local-coder mode. Scaffold and exemplars hand-written; the helper sheet
  `item_tag_assignment.helpers.md` (~10.5k characters) is the model's only view of the file.
- Standing rows (Conventions): fixtures `w1`, `w2`, `u1`, `u2`, then items `i1`, `i2`, `ix`
  (inactive), `i9` (W2), then tags `t1`, `t2`, `ts` (system), `td` (inactive), `t9` (W2). Each
  fixture depends on the one before it, so ids rise in the Conventions order; an autouse
  `standing_rows` fixture creates all of them in every test.
- Builders (fixtures, keyword-only, flush before returning): `mk_link(of=item, to=tag, **cols)`
  (workspace of the item, `assigned_by` U1, `assigned_at` model default), `mk_tag` /
  `mk_system_tag(name=, tag_code=, **cols)`, `mk_item(name=, name_normalized=, **cols)`.
- Reading helpers: `reread`, `snap` (all columns from the table), `links_of(db, item)` (expires,
  then SELECT by item_id ordered by id), `count_rows(db, table, **filter)`, `written(db)` (counts of
  item_tag_assignments, items, item_tags), `ids`, `names`, `close_to_now`.
- Nothing is patched.
- `Author: claude` cards (helpers not in the sheet):
  - **Statement recorder** (TFS-04, TFS-19, TFI-14, INH-15): `StatementRecorder(db)` listens to
    `before_cursor_execute` on the session's connection during the When; `.statements` is the
    card's `statements`, `.sql()` its `sql` (the one SELECT; fails loudly if there is not exactly
    one), `order_part_of(sql)` its `order_part`. The function was renamed from `order_part` to
    `order_part_of` at finishing so the card's variable name `order_part` can be used in the tests
    (same names as `test_item_tag.py`); no local test used it.
  - **Rolled back** (RM-09): `patch.object(db, "commit", wraps=db.commit)` as the spy,
    `sp = db.begin_nested()` directly before the call, Then 1–2 inside the savepoint,
    `sp.rollback()`, then Then 3–5.
  - RM-13: the edit of I1 (`i1.name = "Bolt M8 Long"`, `db.flush()`) sits under `# Then 2`, before
    its assertion, as the card's Then line says. The Given step `loaded = len(i1.tag_assignments)`
    is kept as written with `# noqa: F841`.
  - RM-14: `new = dao.create(...)` under `# Then 2`, before its assertion.
  - INH-18: the When is the card's direct `db.execute(text("delete from item_tags …"))`. `k1_id =
    k1.id` is taken after the Given rows and before the When: after the DELETE and the expire in
    `links_of`, reading `k1.id` raises `ObjectDeletedError`. Then 3 counts by `k1_id`.
  - Non-strict xfails (TFS-17, TFS-18, TFI-12, TFI-13, INH-14): `strict=False` with the bug title
    and the reason it is non-strict (collation or physical row order); the assertions are the
    card's, unweakened.

## xfail location (`--runxfail -rf`)
All 8 xfail tests are Claude's; the 68 local tests are all pass cards. Each fails on the
card's "Fails today on" line:

| Case | Strict | Fails on | Actual |
|---|---|---|---|
| ITA-TFS-17 | no | Then 2 | `[K3, K2, K1, K4]` ("alpha" before "Alpha"), as the card predicts |
| ITA-TFS-18 | no | Then 2 when it fails | `[K2, K1]`; passes on some runs (see Stability) |
| ITA-TFS-19 | yes | Then 4 | order part ` item_tag_assignments.item_id, item_tags.name` (no `lower(...)`) |
| ITA-TFI-12 | no | Then 2 | insert order `[K1, K2, K3, K4]` |
| ITA-TFI-13 | no | Then 2 when it fails | `[K2, K1]`; passes on some runs |
| ITA-TFI-14 | yes | Then 2 | no `ORDER BY` in the SELECT |
| ITA-INH-14 | no | Then 2 when it fails | `[L2, L1]`; passes on some runs |
| ITA-INH-15 | yes | Then 2 | no `ORDER BY` (only `LIMIT … OFFSET …`) |

## Discrepancies
None.

## Coverage gaps
None — 100% line and branch coverage (28 statements, 4 branches):
`--cov=app.dao.item_tag_assignment --cov-branch --cov-report=term-missing`.

## Stability
- 10 whole-file runs with the default planner: never red; every pass card passed and every strict
  xfail xfailed in every run. Non-strict outcomes varied between runs: runs 1–2 TFS-18 and TFI-13
  XPASS; runs 3–4 all 8 xfailed; runs 5–10 INH-14 XPASS. (The plan for these tiny tables changes
  with table statistics, which other test files running against the same database also move.)
- `PGOPTIONS="-c enable_indexscan=off -c enable_bitmapscan=off -c enable_indexonlyscan=off"`
  (sequential scans): 80 passed, 6 xfailed, 2 xpassed (TFS-18, TFI-13). INH-14 xfails here
  (`[L2, L1]`: the updated L1 row moves behind L2).
- `PGOPTIONS="-c enable_seqscan=off"` (index scans): 80 passed, 7 xfailed, 1 xpassed (INH-14).
- Checked that `PGOPTIONS` reaches the test connection (`SHOW enable_seqscan` → `off`).
- So TFS-18, TFI-13 and INH-14 flip with the plan, as their cards predict; this is why they are
  non-strict. No strict xfail and no pass card flipped under any setting. TFS-17 and TFI-12 failed
  in every run (collation / insert order).

## Local-coder run
Model Qwen3.6-35B-A3B (Q4_K_M), llama-server, n_ctx 16,384, thinking off. The server was started
and stopped around each batch in one command (`llm_server.py up && local_coder … ; llm_server.py
down`).

- 68 cases sent (the 18 trial cards plus 50 in the full run): **58 accepted first try, 10 accepted
  after retries, 0 escalated (handed back)**.
- Retries, all caught by the runner before running the test:
  - fixture used but not in the argument list: TFS-09 (`t1`), CNT-11 (`u1`);
  - an extra `workspace_id=w1.id` on a link that already takes it from its item: TFS-13, TFI-10,
    EX-09, CNT-10;
  - an unused `before` variable: INH-02, INH-10; CNT-04 (plus a missing `# Then 1`);
  - `count:` lines asserted against `before` values instead of the card's numbers: RM-06 (3 tries).
- Trial (18 cards): ITA-INH-13 was accepted but **unfaithful**: "L9 = link of I9 to T9" was built
  with an extra `workspace_id=w2.id` (the default value, so the check was still right, but the row
  was not built as written). Cause: the runner's keyword check looked for `workspace_id` anywhere
  in the card, and the remark "(A link of W2.)" invited it. Fix: a helper-sheet definition row for
  L9; the test was deleted and re-run, accepted first try and faithful (`mk_link(of=i9, to=t9)`).
  Runner fix **P23** (`docs/testing/local-coder-improvements.md`) now accepts builder keywords only
  from the card's Given rows, so that slip is rejected. Runner fix **P24** adds a forgotten
  fixture to the argument list itself (`tidy_args`), which removes the "fixture not requested"
  retry seen above.
- Root causes: all model slips (caught by the runner) plus one helper-sheet gap (L9 row) found in
  the trial; no card or spec problems.

## Finishing (Step D)
- Wrote the 13 `Author: claude` tests.
- Cosmetic only in local tests: removed a blank line after the docstring in ITA-INH-01, INH-08,
  INH-09, INH-11, INH-12; moved all tests into card order under section headers. A whitespace-
  insensitive comparison with the as-delivered file shows all 75 earlier tests unchanged.
- Scaffold: imported `patch`; dropped the `# noqa: F401` import comments (every name is now used);
  renamed `order_part` → `order_part_of` (see above).
- `ruff check`: clean. `ruff --select F841,F811` and an AST pass for unused test arguments: clean.
- No local test errored or had a wrong xfail location (there were no local xfail tests).

## Factories added
None.

## Notes for maintainers
- When BUG-933 is fixed: TFS-19 XPASSes (strict → fails): remove its marker and those of TFS-17,
  TFS-18. BUG-932: same for TFI-14 / TFI-12 / TFI-13. BUG-100: INH-15 / INH-14.
- If the fix spells the case-insensitive key differently from `lower(item_tags.name)` (Spec gap 3),
  the recorder cards' Then lines change with it.
- TFS-18, TFI-13, INH-14 depend on physical row order and the plan; they XPASS on some runs today.
- When BUG-934 is fixed, ITA-RM-01 … RM-14 are deleted with `remove_all_tags_from_item`.
