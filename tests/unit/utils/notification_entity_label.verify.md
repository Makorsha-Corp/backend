# Verification — `app/utils/notification_entity_label.py`

> **Verdict:** PASS
> Tests: 54 passed · 28 xfailed (reproduced ✅) · coverage 100% branch
> Mutation: 25 mutants · 16 killed · 9 survived → score 100% (after excluding 0 equivalent, 0 dead, 9 bug-path)
> Source commit: e48a092 · Cases revision: 2

## Summary
The tests can be trusted. All 23 cases in cases revision 2 are implemented with the exact assertions the cases file asks for, and nothing is mocked. The pass and xfail counts in the notes reproduce exactly and stay the same over three runs. With `--runxfail`, each of the 28 xfail tests fails on its exact `"<type name> #<id>"` equality, and each failure shows today's `"<type>-<id>"` value. So the BUG-200 markers are honest. Every mutant the passing tests can reach is killed. The 9 survivors are friendly type names in `_ENTITY_TYPE_LABEL` that only the BUG-200 fix will use, and today only the xfail tests check them. No stage has work to do.

## Findings
None.

Note (not a finding, batch mode): BUG-200 is not yet in `docs/testing/bugs.md`. It is recorded in `tests/unit/utils/notification_entity_label.bugs-staging.md`, and one agent will merge that file into the shared register later. The staging title matches the xfail reason text word for word ("Notification fallback label uses raw `type-id` for most entity types"). I treated that as meeting "BUG ID exists in bugs.md" for this batch (best-practice default, delegated by reviewer).

## Surviving mutants
| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 12 | L10:22 | `'purchase order'` → `''` | bug-path | This `_ENTITY_TYPE_LABEL` value is read only on the `ValueError` path. `purchase_order` is a valid `AttachmentEntityTypeEnum`, so today it never gets there. Only R3a [BUG-200] uses the name, and it is checked by the xfail tests NEL-R-08 and NEL-R-10, which the mutation run leaves out. | — |
| 13 | L11:22 | `'transfer order'` → `''` | bug-path | Same as #12 (R3a; NEL-R-08/10). | — |
| 14 | L12:21 | `'expense order'` → `''` | bug-path | Same as #12. | — |
| 15 | L13:18 | `'work order'` → `''` | bug-path | Same as #12. | — |
| 16 | L14:19 | `'sales order'` → `''` | bug-path | Same as #12. | — |
| 17 | L15:15 | `'project'` → `''` | bug-path | Same as #12. Also used by R4a (NEL-R-12-e). | — |
| 18 | L16:25 | `'project component'` → `''` | bug-path | Same as #12. | — |
| 19 | L17:15 | `'machine'` → `''` | bug-path | Same as #12. | — |
| 21 | L19:12 | `'item'` → `''` | bug-path | Same as #12. Also used by R4a (NEL-R-12-c/d). | — |

Notable killed mutants:
- `'inventory'` value (#20): killed by NEL-R-16, NEL-R-17 and NEL-R-23.
- All dict-key mutants (#2–#11): killed, because a `''` key changes the output of NEL-R-20's empty-type call.
- Both `return None` mutants (#1, #22): killed.
- `' #'` (#23), `'_'` (#24) and `' '` (#25): killed.

## Traceability
Cases: 23. Test functions: 22, because NEL-R-05 and NEL-R-06 share one function and each has its own `pytest.param(id=…)`. Collected items: 82.
- **Unmatched cases:** none. The IDs NEL-R-01 to NEL-R-23 each belong to exactly one test, found by grep over test names, docstrings and param ids. Parametrized sets use `NEL-R-NN-<type|letter>` ids.
- **Tests without a case ID:** none.
- **Marker mismatches:** none.
  - `pass` cases (01–07, 09, 11, 13, 14, 16–23) have no xfail marker.
  - `xfail BUG-200` cases (08, 10, 12, 15) use `xfail(strict=True, reason=BUG_200)`, and the reason names BUG-200.
- **Fidelity:** I read every test against its Given/When/Then.
  - No assertion is missing, weakened or changed, and no failure is swallowed. There are no `try/except` blocks and no `pytest.raises`.
  - No mocks or patches, which matches the spec (no externals) and the cases file (no race simulations).
  - NEL-R-09 asserts "not the standard label" and, for item, also "not Hex Bolt", plus a non-empty result ending with the id, as the case says.
  - NEL-R-23 re-reads from the DB with `count(*)`, `expire_all()` and `db.get`, and checks `db.new`, `db.dirty` and `db.deleted`.
  - NEL-R-17 matches revision 2: any valid inventory, with the exact id-form assertion.
  - The `call()` helper asserts `isinstance(result, str)` on every call, as the Conventions require.

## Commands run
```
.venv/Scripts/python.exe -m pytest tests/unit/utils/test_notification_entity_label.py -q -p no:cacheprovider --cov=app.utils.notification_entity_label --cov-branch --cov-report=term-missing
  app\utils\notification_entity_label.py  13  0  0  0  100%
  54 passed, 28 xfailed in 8.89s

.venv/Scripts/python.exe -m pytest tests/unit/utils/test_notification_entity_label.py -q -p no:cacheprovider --runxfail -rf
  28 failed, 54 passed in 5.50s
  (all 28 = NEL-R-08 x11, NEL-R-10 x11, NEL-R-12 x5, NEL-R-15; every one is an AssertionError on the exact
   equality, e.g. assert 'purchase_order-2000000000' == 'purchase order #2000000000', assert 'scratch-5' == 'scratch #5')

.venv/Scripts/python.exe -m pytest tests/unit/utils/test_notification_entity_label.py -q -p no:cacheprovider   (x2, flakiness)
  54 passed, 28 xfailed in 5.58s
  54 passed, 28 xfailed in 5.89s

.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/utils/notification_entity_label.py tests/unit/utils/test_notification_entity_label.py --timeout 180 --json C:/Users/User/AppData/Local/Temp/nel_mut.json
  Mutants: 25 · killed 16 · timeout 0 · survived 9 · score 64% (raw; 100% after excluding 9 bug-path)
```
