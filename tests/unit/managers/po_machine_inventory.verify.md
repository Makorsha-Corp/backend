# Verification — `app/managers/po_machine_inventory.py`

> **Verdict:** PASS
> Tests: 0 passed · 0 xfailed (reproduced ✅: nothing to run, matches notes) · coverage N/A (module is dead code, no specified callables)
> Mutation: 0 mutants run (no unit test file exists by design, so `mutate.py` refused: "Unmutated test run does not pass cleanly"). Every mutable line (10–76) is `dead`, so the score is N/A (after excluding 0 equivalent, all dead, 0 bug-path)
> Source commit: e48a092 · Cases revision: 2

## Summary
This is a re-verification (2026-10-02, fourth pass) against cases revision 2.
I re-ran every check below; nothing has changed since the previous PASS
(spec APPROVED, cases READY rev 2 with 0 cases, HEAD still e48a092, module
unmodified, still no importers, mutate.py still refuses with no test file). The spec (APPROVED) specifies 0 callables. The reviewer
marked the whole module (`PO_MACHINE_SOURCE_TYPE`, `_quantity_to_int`,
`_weighted_avg_price`, `_ensure_machine_item`, `_ledger_exists_for_source`) as
dead code to remove (spec Q1). The cases file (READY) issues 0 cases, and the
executor correctly wrote no `test_po_machine_inventory.py`.

I checked the dead-code claim again on my own. No `.py` file under `app/`,
`tests/`, `alembic/` or `scripts/` imports the module or uses any of its names.
The only places that mention `po_machine` are documentation and generator data
(`docs/testing/*`, `po_storage_inventory.spec.md`). Every possible mutant would
land in `dead` code, so the test pipeline has nothing to fix. The only remaining
work is the removal, which is already logged in
`po_machine_inventory.deadcode-staging.md`.

## Findings
None.

## Surviving mutants
None were classified one by one, because the mutation tool cannot run without a
test file, and that file is absent by design. Every mutable line falls under the
spec's "Not specified — dead code, to be removed (Q1)".

| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| — | 10–76 (whole module) | any | dead | Its sole caller `post_purchase_order_to_machine` was deleted in `7be54d5`. A grep found no importer in any `.py` file in the repo | — |

## Traceability
cases 0 · tests 0 · unmatched: none · marker mismatches: none · BUG IDs used: none
(`docs/testing/bugs.md` has no entry for this module, which is expected: Q1 is dead code, not a bug).

## Commands run
```
ls tests/unit/managers/ | grep po_machine
  -> cases.md, deadcode-staging.md, notes.md, spec.md, verify.md  (no test_po_machine_inventory.py: matches notes "Tests: none (by design)")

git rev-parse --short HEAD
  -> e48a092  (matches spec/cases/notes source commit)

grep -rn --include=*.py -E "po_machine_inventory|PO_MACHINE_SOURCE_TYPE|_ensure_machine_item|_ledger_exists_for_source" app tests alembic scripts   (excluding the module itself)
  -> (no matches)

grep -rln "po_machine" . (excluding .venv/.git/__pycache__ and this module's pipeline files)
  -> docs-only: docs/testing/unit-test-checklist-by-{domain,layer}.md, docs/testing/_generators/{deadcode,inventory}.json, gen.py, tests/unit/managers/po_storage_inventory.spec.md, .ruff_cache

.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/managers/po_machine_inventory.py tests/unit/managers/test_po_machine_inventory.py --timeout 180 --json %TEMP%/pmi_mut.json
  -> "Unmutated test run does not pass cleanly — fix the tests first."  (the test file does not exist)
```
I skipped the pytest coverage run, the `--runxfail` run and the flakiness
re-runs because there is no test file to run. This matches the notes' Result
line ("0 passed · 0 xfailed · Run: none").

Decision: I treat the missing test file plus the mutation tool's refusal as
"all mutants dead" instead of a failure (best-practice default, delegated by
reviewer). This follows the `app/utils/work_order_calendar.py` precedent.
