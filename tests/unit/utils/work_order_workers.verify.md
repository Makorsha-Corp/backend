# Verification — `app/utils/work_order_workers.py`

> **Verdict:** PASS
> Tests: 61 passed · 16 xfailed (reproduced ✅) · coverage 100% branch
> Mutation: 35 mutants · 33 killed · 2 survived → score 100% (after excluding 2 equivalent, 0 dead, 0 bug-path)
> Source commit: e48a092 · Cases revision: 3

## Summary
These tests can be trusted. Each of the 77 cases maps to exactly one test or `pytest.param` id, and no test is missing a case ID. Every Then column is asserted with exact equality, nothing is mocked, and the read-only cases check that the session is clean. All 16 xfail tests, including the new WOW-R-33, fail under `--runxfail` on the assertion the case names in its "fails today on" column, not on setup errors. The results match the executor's notes (61 passed, 16 xfailed, 100% branch coverage) and stayed the same over three runs. Mutation testing killed every mutant that changes behavior. The only two survivors switch off `frozen=True` on the two result dataclasses, and no caller can observe that. Non-blocking: the test module's docstring still says "revision 2" (line 3), but the file implements revision 3. That is cosmetic, has no effect on behavior, and is not counted as a finding.

## Findings
None.

## Surviving mutants
| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 17 | 26 | `@dataclass(frozen=True)` → `frozen=False` on `MemberLookup` | equivalent | The spec lists it as "frozen dataclass, no logic". Its only users are this module and `WorkOrderManager._sync_assignees_from_text` / `_resolve_completion_workers` (work_order_manager.py L1093–1136, re-checked). They never assign to a field, hash an instance, or use one as a set member or dict key, so switching off immutability and hashability changes nothing a caller can see. | — |
| 18 | 33 | `@dataclass(frozen=True)` → `frozen=False` on `WorkerNameResolution` | equivalent | Same reasoning. The manager only reads `.matched_user_ids` and `.display_text`, and never mutates or hashes the result. | — |

## Traceability
- Cases: 77. Test functions: 73, and two of them are parametrized (WOW-P-01..03 and WOW-T-02..04, one `pytest.param` id per case), giving 77 test items. A script cross-checked the case IDs from the table rows against the test names and param ids.
- Unmatched case IDs: none. Tests without a case ID: none.
- Marker mismatches: none. None of the 61 `pass` cases has an xfail marker. All 16 `xfail` cases use `xfail(strict=True)`, and each reason names the case's BUG ID: R-21..24 → BUG-380; R-25..28, R-33, D-10, D-11 → BUG-381; R-30, R-32, D-08, D-12, D-13 → BUG-382.
- BUG IDs: BUG-380, BUG-381 and BUG-382 all exist in `docs/testing/bugs.md` (rows 3–5, status open).
- Fidelity: I read every case against its test and found no missing, weakened or changed assertions and no wrong setups. There are no swallowed failures: WOW-R-20 uses `pytest.raises(AttributeError)`, the specific type. There are no extra mocks. L-01 and D-01/D-08 check that the session is clean, and L-01 re-counts the rows after `expire_all()`. The blank emails in D-04 (`""`), D-12 (`"   "`) and D-13 (`"\t "`) are inserted exactly as written, as the Conventions require. The new WOW-R-33 test uses members `[M7]`, resolves `["Zed", "Rahim", " zed "]` and asserts `ids=[7]`, `unmatched=["Zed"]`, `display="Zed, Rahim"`, exactly as the case says.
- xfail honesty (`--runxfail`), with today's value for each: R-21 `[7] == []`, R-22 `[12] == []`, R-23 `[7] == []`, R-24 `[7, 9] == [9]`, R-25 `['Unknown','unknown','UNKNOWN'] == ['Unknown']`, R-26 `['STRASSE','straße'] == ['STRASSE']`, R-27 `'Rahim, Rahim, Rahim'`, R-28 `'Rahim, Unknown, Rahim'`, R-30 `'Rahim'`, R-32 `''`, R-33 `['Zed','zed'] == ['Zed']`, D-08 first call `''`, D-10 `'Rahim, Karim, Rahim'`, D-11 `'User #1000, User #1000'`, D-12 `''`, D-13 `'Rahim'`. Every one matches its case's "fails today on" column.

## Commands run
```
.venv/Scripts/python.exe -m pytest tests/unit/utils/test_work_order_workers.py -q -p no:cacheprovider --cov=app.utils.work_order_workers --cov-branch --cov-report=term-missing
  app\utils\work_order_workers.py      67      0     22      0   100%
  61 passed, 16 xfailed in 6.91s

.venv/Scripts/python.exe -m pytest tests/unit/utils/test_work_order_workers.py -q -p no:cacheprovider --runxfail -rf
  16 failed, 61 passed in 5.11s   (the 16 failures are exactly the 16 xfail cases)

(stability, 2 more runs)
  61 passed, 16 xfailed in 5.22s
  61 passed, 16 xfailed in 5.36s

.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/utils/work_order_workers.py tests/unit/utils/test_work_order_workers.py --timeout 180 --json <scratchpad>/wow_mut.json
  Mutants: 35 · killed 33 · timeout 0 · survived 2 · score 94%
  SURVIVED #17 L26:18 const: True -> False
  SURVIVED #18 L33:18 const: True -> False
```
