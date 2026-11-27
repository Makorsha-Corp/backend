# Execution notes — `app/services/item_service.py`

> Cases: `tests/unit/services/item_service.cases.md` (revision 2) · Tests: `tests/unit/services/test_item_service.py` · Source commit: e48a092
> Result: 71 of 71 cases implemented · 36 passed · 35 xfail as designed (33 strict, all xfailed; 2 non-strict, P-17 and S-06, xfailed in every run) · 0 errors · 0 discrepancies — branch coverage 94% (all misses dead code)
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/services/test_item_service.py -q -p no:cacheprovider` (about 4 s)

## How the tests are built
Same form as `department_service.notes.md` / `machine_item_service.notes.md`.
- **Standing rows:** W1, W2, U1, U2 only (Conventions: "They exist in every test"): chained fixtures `w1`, `w2`, `u1`, `u2`, autouse `standing_rows`. Every other row is a Given row of its card.
- **Given rows:** `mk_item(name, name_normalized, **but)` with the Conventions defaults (`created_by` U1); `mk_i1`, `mk_i2`, `mk_ix`, `mk_i9` (`workspace_id` W2); `mk_tag(name, tag_code, **but)`, `mk_t1`, `mk_td`; `mk_link(item, tag)` (`assigned_by` U1); `mk_f1()`; `mk_stock(item, factory, qty)`. Each flushes, so ids rise in card order.
- **Commit point:** `commit_point(db)` = `db.commit()` (releases the savepoint). Rows "after the commit point" are built after it and stay uncommitted; `before` snapshots are taken at the commit point, before those rows.
- **Reading helpers:** `reread` / `reread_item_id`, `snap_before` / `snap` (every column of the row's table), `count_rows(table, **filters)`, `written` (`items`, `item_tags`, `item_tag_assignments`), `stored_count` (the card's raw SQL), `tag_ids_of`, `ids`, `unloaded`, `usable`. `committed:` lines are preceded by one `db.rollback()`.
- **Patches:** only the failing commit / failing refresh wraps, the manager patches of the translation cards (`patch.object(svc.item_manager, …, side_effect=ValueError(…))`) and the D-02 spy (`wraps=` the real `delete_item`). Nothing else.
- **Spec-gap assumptions, real names:** `SimilarItemMatch` (`app/schemas/item_similar.py`) has `id`, `name`, `unit`, `sku`, `similarity_score`, `match_type` — the fields S-01, S-03, S-05, S-06 use exist as assumed. "stock of I" = `app.models.inventory.Inventory` (table `inventory`), `inventory_type=InventoryTypeEnum.STORAGE`.
- ITS-P-09's two `[r for r in … ][0]` expressions are the card's and carry `# noqa: RUF015`.

## Fails-today check
`--runxfail`, failing line mapped to its `# Then N`, value read; every card fails where its "Fails today on" says:
- Then 1, the `ValueError` escapes the `raises` wrap: C-05 (`Item tag 999999999 not found`), C-06, C-07, U-03, U-04 (`Item 999999999 not found`), U-05 (`… does not belong to workspace …`), D-04 (`Item <id> is already deleted`), D-05, D-06, D-07 (the two-arg `ValueError`).
- Then 1 `DID NOT RAISE`: C-08, C-09, C-10, G-04, U-06, D-08.
- When raises (the card's "the call raises"): G-05 `TypeError` (no `include_deleted`); P-12 `ValueError: invalid literal for int()` on `²`. G-06: the `TypeError` inside Then 1's wrap.
- C-12 Then 2 `'  Steel  Rod 22 m '`; P-11 Then 2 `'physical'`; P-13 Then 1 both items; P-14, P-15 Then 1 one item instead of `[]`; P-16 Then 2 `['Zulu', 'Mike', 'alpha']`; N-02 Then 1 `['kg', 'Kg', 'KG']`; S-05 Then 1 `0 == 1`; U-08 Then 2 `updated_by` = U2; U-09 Then 3 a new link id; U-10 Then 2 `[T1]`; U-11 Then 2 `'Zinc plated'`; U-12 Then 3 `False`; D-11 Then 2 `9`.
- Non-strict: P-17 Then 2 (`alpha` before `Alpha`), S-06 Then 2 (`['delta', 'Bravo', 'alpha']`), in every run.

## Reference run
`refplug.py` (scratch `…/makorsh-pipeline/svc2x/item/`) patched in what each bug names:
- DAO: ASCII-only digit shortcut (012), `LIKE` escaping (013), deleted tags neither filter (014) nor match (015), unit filter and unit list trimmed / lower case (017), list ordered by `lower(name), id` (033), score rounded to 4 places before the 0.35 threshold (034), ties by `lower(name), id` (018), tag chips by `lower(name), id` (933);
- manager: unknown / foreign tag and deleted tag refused (944, 943), SKU unique among live items (946), name trimmed (936); update refuses deleted / foreign items (938, 941), `exclude_unset` without `exclude_none` (942), `is_active` ignored (947), stamp only on a change (939), kept links stay and links to deleted tags survive (934, 935); delete refused by stock with `[{"type": "factory_stock", "id": …}]` (948) and lowers deleted tags too (945);
- service: D1 translations (944, 943, 946, 940 with the service's text, 948 with `errors`), `include_deleted` and the deleted-item 404 on get and delete (937), `item_type` on the page (1573).
With `--runxfail` all 70 tests passed; without it all 33 strict cards XPASSed (strict, so failed) and both non-strict cards XPASSed.

## Stability
5 plain runs, plus `enable_seqscan=off` and `enable_indexscan/bitmapscan/indexonlyscan=off` (scratch `forceplan.py`, set and committed on each new connection, checked with `SHOW`): 35 passed, 35 xfailed in all 7; no test moved. Ruff passes (repo config); `F841`/`F811` and an AST pass find no unused variable or argument. LF line endings.

## Discrepancies
None.

## Coverage gaps
| Lines | Kind | What the code does there |
|---|---|---|
| 115 | dead | `get_items` → `search_items` (spec Not specified; dead-code checklist) |
| 254→255, 255 | dead | `update_item`'s `if not item: raise NotFoundError` — the manager never returns `None` (spec D3, `remove`) |
| 264–265 | dead | `update_item`'s `except NotFoundError` clause, reachable only through line 255 (D3) |

## Factories added
None.

## Notes for maintainers
- The task brief mentioned a 101-create card C-15; this cases file has no ITS-C-15 (C-01 … C-12) and no bulk card — nothing to time.
- When BUG-937 is fixed, `get_item` gains `include_deleted`; G-05 and G-06 then run their Then lines (the reference run shows they hold).
- D-07 / D-08 expect `ValidationError.errors` to be the blocker list as the manager gives it (D2: no display fields).
- P-17 and S-06 are non-strict: their order depends on the database collation / storage order; they xfailed in every run here.
- Plain runs are warning-free; the coverage run shows 15 SQLAlchemy `SAWarning`s ("GenericFunction … already registered") from the dialect being imported twice under `--cov`, unrelated to this module.

## Revision 2 (2026-11-04)
Cases revision 2 (spec R1a for `get_similar_items`; verifier Findings 1–3). Only these tests changed:
- **ITS-P-10** (changed) — I1 built with `updated_by=u2.id`, `updated_at=datetime(2026, 2, 3, 4, 5, 6)`; Then 5 `updated_by == U2.id`, Then 7 `updated_at.replace(tzinfo=None) == datetime(2026, 2, 3, 4, 5, 6)`; Then lines renumbered 1–8 as on the card. Passes.
- **ITS-D-09** (changed) — "Extra" item added after the commit point (uncommitted); Then 3 `count_rows("items", name="Extra") == 0` right after the call, before any test-level rollback; Then 4 unchanged(I1); Then 5 session usable. Renamed to the card title; Rules gain TC3. Passes.
- **ITS-S-08** (new) — six items `Bolt A` … `Bolt F`, all `name_normalized "bolt"`; default call returns 5 distinct ids, all from the six. Passes.

Counts: 71 tests · 36 passed · 35 xfailed · 0 xpassed · 0 errors · 0 discrepancies. Branch coverage `app.services.item_service` 94% — misses unchanged (115, 254→255, 255, 264–265; all dead, see Coverage gaps). 3 runs identical. Ruff clean (two inline `noqa: DTZ001` for the card's naive stamp); LF endings.
