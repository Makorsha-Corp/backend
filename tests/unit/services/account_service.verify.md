# Verification — `app/services/account_service.py`

> **Verdict:** NEEDS WORK. Only the case designer has work, plus one register item for the describer. No test is wrong.
> Tests: 73 passed · 43 xfailed (all strict; reproduced ✅) · coverage 93% branch (128 statements, 7 missed: 92–95, 357, 366–367, all dead per spec Q4 / Q5)
> Mutation: 186 mutants · 154 killed · 32 survived → score 88% (154 / 175, after excluding 1 equivalent, 10 dead, 0 bug-path). The 21 survivors left are all `case-missing`.
> Fidelity: **0 of 116 unfaithful** (all 116 read by eye against their cards)
> Hand variants: 80 · 75 caught by a pass card · 5 others: 3 are the same gap as the mutants (Findings 3), 1 equivalent, 1 out of the card's reach (see "Considered")
> Source commit: e48a092 · Cases revision: 2; spec APPROVED

## Summary
- **The tests can be trusted as written.** Every one of the 116 tests matches its card: Givens (W0 / W2 order, gone columns, explicit invoice ids), commit point, X, each Then line in card order, `committed:` re-reads after `db.rollback()`. There are no `try` blocks, and the only broad `pytest.raises(Exception)` is the one ASV-D-10 prescribes. The only patches are the ones Conventions name.
- **The transaction contract holds under attack.** No commit, commit before the manager, a missing rollback on each of the 8 error paths, commit instead of rollback, a partial write after a failure, refresh or read before commit, and reads that commit, roll back or flush are all caught (48 variants).
- **Error mapping, swallowing and HR-16 hold.** A wrong exception type, a wrong detail, translating every ValueError, a swallowed error, and dropping the workspace filter (get, delete pre-check, tag lookup; W0 and W2 both) are all caught. There is one exception, in `unassign_tag` (see below).
- **Delete blockers (today's pass side).** Over-blocking variants are caught: any invoice, settled, foreign voided (D-29) and another account's draft (D-18). The `other_workspace` entry itself (D-20 … D-23, D-30) is bug-path, BUG-2984. All 9 of those xfails fail on Then 1 ("DID NOT RAISE"), as their cards say.
- **What must change:** 21 surviving mutants and 3 variants fall into three rule gaps with no card:
  1. The tag entries (`TAGKEYS` and their values) of the list, by-tag and hub dicts.
  2. The three default `limit` values.
  3. `unassign_tag`'s 422 branch for any other ValueError.

## Findings
| # | Kind | Case / line | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing | Facts (account dict with tags) via `get_accounts_with_tags` R1, `get_accounts_by_tag_id` R3, `_account_dict_with_tags` R1 / hub R2 | Only `get_account_with_tags` has a card that checks a tag entry's keys and values (G-01 Then 4–5). L-03 and M-01 check tag `id`s only. T-01 and H-01 check the account keys only. | mutants L223–227, L265–269, L421–426 (`'name'`, `'tag_code'`, `'color'`, `'icon'`, `'is_system_tag'`, and `'id'` on L421) → `''`: 16 survive | **case designer** |
| 2 | case-missing | signatures: `get_accounts_with_tags` `limit=100`, `get_accounts_by_tag_id` `limit=100`, `get_accounts_hub_page` `limit=50` | Every list card passes `limit` or has fewer rows than the default, so a different default passes. A default limit is a card (case designer shape 1b, precedent `app_settings_service` R-AS-1). | mutants L167 `100→101`, L378 `100→101`, L292 `50→51` survive | **case designer** |
| 3 | case-missing | `unassign_tag` R2 ("translation as `assign_tag` R2") | There is no pass card for a ValueError without "not found" (→ 422 `BusinessRuleError`, same detail) or for the case-sensitive match. Today the only 422 card is N-04, which is xfail (BUG-879), so the branch is never run by a pass test. `assign_tag` has A-09 / A-10 for the same rule. | mutants L481 `'not found'→''` and L483 `raise→pass`; variants `EM wrong type: unassign other -> 404`, `EM wrong detail: unassign 422 text`, `SW swallow: unassign ValueError` all survive | **case designer** |
| 4 | register | xfail reasons `BUG_124`, `BUG_629` | The cards and the spec cite BUG-124 (account update / delete answers 500) and BUG-629 (inactive tag on create / update) as precedent IDs. Their register rows describe other modules: the attachment allow-list (124) and moving a draft invoice (629). The account-service half of each is not in `bugs.md`. Once those rows are closed for their own modules, 15 strict xfails here would point at a closed bug. Same pattern in `account_manager.spec.md` P1 / P8. | `bugs.md` rows BUG-124 (line 54), BUG-629 (line 139); notes "Notes for maintainers" bullet 2 | **describer** (apply-review: extend the two rows' location column to `account_service.py` / `account_manager.py`, or give the account half its own ID and re-point the cards) |

### Scratch cards that close the gaps
| Ref | Rule | Given | When | Then | Expect | Kills |
|---|---|---|---|---|---|---|
| R-AS-1 | Facts via `get_accounts_with_tags` R1 | A = account; T = tag, but `color "#ff0000"`, `icon "truck"`; link(A, T) | `result = svc.get_accounts_with_tags(db, workspace_id=W1.id)` | 1. `result[0]["account_tags"] == [{"id": T.id, "name": "Supplier", "tag_code": "supplier", "color": "#ff0000", "icon": "truck", "is_system_tag": False}]` | pass | L223–227 |
| R-AS-2 | Facts via `get_accounts_by_tag_id` R3 | as R-AS-1 | `result = svc.get_accounts_by_tag_id(db, tag_id=T.id, workspace_id=W1.id)` | 1. same equality as R-AS-1 | pass | L421–426 |
| R-AS-3 | `_account_dict_with_tags` R1 (hub R2) | as R-AS-1 | `result = svc._account_dict_with_tags(db, account=A, workspace_id=W1.id)` | 1. same equality on `result["account_tags"]` | pass | L265–269 |
| R-AS-4 | `get_accounts_with_tags` default limit | 101 accounts of W1 by `add_all`, `name f"a{k:03d}"` | `svc.get_accounts_with_tags(db, workspace_id=W1.id)` | 1. `len(result) == 100` | pass | L167 |
| R-AS-5 | `get_accounts_by_tag_id` default limit | T = tag; 101 accounts each with link(·, T) | `svc.get_accounts_by_tag_id(db, tag_id=T.id, workspace_id=W1.id)` | 1. `len(result) == 100` | pass | L378 |
| R-AS-6 | `get_accounts_hub_page` default limit | 51 accounts of W1 | `items, total = svc.get_accounts_hub_page(db, workspace_id=W1.id)` | 1. `len(items) == 50`; 2. `total == 51` | pass | L292 |
| R-AS-7 | `unassign_tag` R2 | A = account; T = tag; X; `E = ValueError("bad state")`; **mgr raises E on unassign_tag** | `svc.unassign_tag(db, account_id=A.id, tag_id=T.id, workspace_id=W1.id)` | 1. raises `BusinessRuleError`; 2. `status_code == 422`; 3. `detail == "bad state"`; 4. `x_gone` | pass (Author: claude) | L481, L483; the 3 unassign variants |
| R-AS-8 | `unassign_tag` R2 (case-sensitive) | as R-AS-7, `E = ValueError("Tag 5 Not Found")` | same | 1. raises `BusinessRuleError`; 2. `detail == "Tag 5 Not Found"` | pass (Author: claude) | L481 |

## Surviving mutants
| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 1-#1, #2, #6, #7, #33, #34 | 93–95 | `get_account`: if negate, return None, drop not, raise→pass, two message consts | dead | spec Not specified, Q5: no caller; listed in `dead-code-removal-checklist.md` | — |
| 3-#13, #14, #26, #27 | 357, 367 | `update_account` "manager returned nothing" raise→pass, its `except NotFoundError` raise→pass, two message consts | dead | spec Not specified, Q4: the manager never returns `None` | — |
| 3-#3 | 289 | `section="overview"` → `""` | equivalent | `AccountInvoiceDAO` filters only for `"payable"` / `"receivable"` (`app/dao/account_invoice.py:274–277`); any other value, `""` included, is the overview query | — |
| 1-#11 | 167 | default `limit 100 → 101` | case-missing | Finding 2 | case designer |
| 3-#5 | 292 | default `limit 50 → 51` | case-missing | Finding 2 | case designer |
| 3-#9 | 378 | default `limit 100 → 101` | case-missing | Finding 2 | case designer |
| 2-#67 … #71 | 223–227 | list tag keys `name` … `is_system_tag` → `''` | case-missing | Finding 1 (L-03 checks `id` only) | case designer |
| 2-#56 … #60 | 265–269 | hub / `_account_dict_with_tags` tag keys → `''` | case-missing | Finding 1 (M-01 checks `id` only) | case designer |
| 4-#41 … #46 | 421–426 | by-tag tag keys `id` … `is_system_tag` → `''` | case-missing | Finding 1 (T-01 never looks at `account_tags`) | case designer |
| 4-#38 | 481 | `"not found" in error_msg` → `"" in …` | case-missing | Finding 3 | case designer |
| 4-#8 | 483 | `raise BusinessRuleError` → `pass` | case-missing | Finding 3 | case designer |

(Shard prefix 1 = lines 1–200, 2 = 201–285, 3 = 286–400, 4 = 401–540.)

## Hand variants
Each variant is a one-line edit of a temp copy of the backend (my `variants.py`, `var2.py`). It was run against the 73 pass tests, without `-x`, and every run reached all of them.

| Group | Variants | Pass card | Cards that fail |
|---|---|---|---|
| TC1 no commit (create, update, assign, unassign, delete) | 5 | 5 | C-01, C-02, C-04, C-05, U-01, U-02, A-01, A-12 … A-14, N-01, D-01, D-02, D-06, D-08, D-16 … D-18, D-29 |
| TC2 no refresh (create, update); commit before manager / before pre-check (6 sites) | 8 | 8 | C-01, C-05, U-01, C-03, C-06, U-03, A-03, A-08, A-11, N-02, N-06, D-03, D-07 |
| TC3 no rollback on each error path (8); commit instead of rollback (8) | 16 | 16 | C-03, C-06, U-03, A-03, A-08, A-11, N-02, N-06, D-03, D-07 |
| TC4 partial write after failure (commit then rollback: update, delete) | 2 | 2 | U-03, D-07 |
| TC5 refresh before commit (create); read before commit (assign) | 2 | 2 | C-05, A-12 … A-14 |
| TC6 read commits / rolls back (4 reads each); read flushes (2) | 10 | 10 | G-10, L-08, H-04, T-08 |
| Error mapping: wrong type (7), wrong detail (4), case-insensitive match, translate all ValueErrors (3), wrap other exception | 16 | 14 | G-05 … G-07, T-04 … T-06, D-03 … D-05, A-03, A-06 … A-11, N-02, N-03, C-06, U-03, D-27 |
| Swallowed error (create, update, assign × 2, unassign × 2, delete × 2, get 404, by-tag 404) | 10 | 9 | C-03 … C-06, U-02, U-03, A-08 … A-11, N-02, N-03, N-06, D-03 … D-07, D-27, G-05, T-04 |
| HR-16 no workspace filter (get, delete pre-check, tag lookup); tags read for the account's own workspace | 4 | 3 | G-06, G-07, D-04, D-05, T-05, T-06 |
| Delete blockers: any invoice, settled, foreign voided, another account's draft, row lock (lower-case raw, upper-case raw, ORM `with_for_update`) | 7 | 6 | D-08, D-16, D-17, D-18, D-29 |
| **Total** | **80** | **75** | |

Not caught: `EM wrong type: unassign other -> 404`, `EM wrong detail: unassign 422 text` and `SW swallow: unassign ValueError` (all three are Finding 3), plus the two listed below.

### Considered and not listed
| Variant | Why it is not a finding |
|---|---|
| `HR-16 tags read with account's own workspace` (L124 `workspace_id=account.workspace_id`) | **Equivalent:** the account has just passed `get_account(..., workspace_id)`, so `account.workspace_id == workspace_id` always holds. |
| `BLK delete takes a row lock` with lower-case raw `text('... for update')` | D-08 is faithful to its card (`"FOR UPDATE"`, case-sensitive). An upper-case raw lock and an ORM `with_for_update()` are both caught by D-08 (`var2.py`). The ORM always emits upper case and the service has no raw SQL, so this is not a gap today. Note for the future: if raw SQL ever enters the delete path, the card should match case-insensitively. |
| `other_workspace` blocker entry (R5a, D-20 … D-23, D-30) | **Bug-path** BUG-2984 / BUG-876: no pass card can see blockers until the manager refuses. All 9 xfails fail on Then 1 today, and the reference plugin of the notes passes them. Cross-workspace invoices are invalid data (house rule). The refusal names no foreign id, which matches the "refusals show blockers" rule without leaking another workspace. |

## xfail tests
`--runxfail`: 43 failed, 73 passed. I mapped each failure's last frame in the test file to the `# Then N` block above it (my `thenline.py`): **43 of 43 fail on the card's "Fails today on" line**. 37 fail in that Then block. The 6 TypeError cards (C-13, G-09, L-07, U-13, N-07, D-28) fail at the `# Fails today here` call, which is their card's Then 1 reason. No failure comes from setup or an import. Every reason constant names exactly its card's bug ID, and all those IDs exist in `bugs.md` (see Finding 4 for 124 / 629).

## Reproduced claims
- Notes Result `73 passed · 43 xfailed · 93% branch, misses 92–95, 357, 366–367`: reproduced exactly.
- Three plain runs: 73 / 43 each time. No flaky test.
- `ruff check` and `ruff format --check`: clean.
- Mocks are only what Conventions name: spies, failing commit / refresh, `mgr raises` on `svc.account_manager`, the hub manager in H-01, the instance read in A-12 … A-14, and the D-12 simulation. The session wraps call the real methods, and no DAO is patched. This follows the sibling precedent (`account_tag_service.verify.md`).
- No new bug: BUG-2986 … 2990 are unused.

## Traceability
cases 116 · tests 116 · unmatched: none · duplicates: none · marker mismatches: none. 73 pass cards have no marker. 43 xfail cards are `xfail(strict=True, reason=BUG_n)`, and each constant's text starts with the card's BUG ID.

## Commands run
```
COVERAGE_FILE=…/svc1v/account/.coverage .venv/Scripts/python.exe -m pytest tests/unit/services/test_account_service.py -q -p no:cacheprovider -o addopts="" --cov=app.services.account_service --cov-branch --cov-report=term-missing
  → app\services\account_service.py 128 7 22 1 93%  Missing 92-95, 357, 366-367 · 73 passed, 43 xfailed
.venv/Scripts/python.exe -m pytest tests/unit/services/test_account_service.py -q -p no:cacheprovider -o addopts=""   (×2)
  → 73 passed, 43 xfailed · 73 passed, 43 xfailed
.venv/Scripts/python.exe -m pytest tests/unit/services/test_account_service.py -q -p no:cacheprovider -o addopts="" --runxfail -rf --tb=short
  → 43 failed, 73 passed
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/services/account_service.py tests/unit/services/test_account_service.py --lines <shard> --timeout 180 --json …/mut_<shard>.json
  shard 1-200   → Mutants: 42 · killed 35 · survived 7
  shard 201-285 → Mutants: 71 · killed 61 · survived 10
  shard 286-400 → Mutants: 27 · killed 20 · survived 7
  shard 401-540 → Mutants: 46 · killed 38 · survived 8
.venv/Scripts/python.exe …/svc1v/account/variants.py …/variants.json   → baseline clean · 78 variants · 73 killed · 5 survived
.venv/Scripts/python.exe …/svc1v/account/var2.py …/var2.json           → 2 lock variants · 2 killed (D-08)
.venv/Scripts/python.exe -m ruff check / ruff format --check tests/unit/services/test_account_service.py → clean
```
Scratch: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\svc1v\account\` (`trace.py`, `thenline.py`, `variants.py`, `var2.py`, mutation JSON and logs).

## Fix list
- **Case designer:** add cards R-AS-1 … R-AS-8 (Findings 1–3), then the executor implements them and the verifier re-runs the mutants on L167, L223–227, L265–269, L292, L378, L421–426, L481, L483.
- **Describer (apply-review):** Finding 4. Make BUG-124 and BUG-629 cover the account service / manager in the register, or give that half its own ID.
- **Executor:** nothing until the new cards exist.

## Round 2 — 2026-11-22

> **Verdict: PASS** (cases revision 3 / 3a, narrow round)
> Tests: 81 passed · 43 xfailed (all strict; reproduced ✅) · coverage 93% branch (misses 92–95, 357, 366–367, dead as before) · 3 plain runs identical, no flaky test
> Mutation: the 21 case-missing survivors of round 1 were re-run, and all 21 are killed. Score is now 100% (175 / 175, after excluding 1 equivalent and 10 dead), using round 1's totals with only these 21 re-run.
> Variants: the 5 round-1 survivors were re-run. 4 are killed. 1 is equivalent, as already classified (`HR-16 tags read with account's own workspace`, L124).

**Scope.** I checked the 8 new cards and tests (ASV-L-09, L-10, M-03, H-05, T-09, T-10, N-08, N-09), the changed ASV-D-08, and the citation change BUG-124 → BUG-2986 and BUG-629 → BUG-2987 (revision 3a). Full mutation testing was not run again.

**Fidelity: 0 unfaithful.**
- Each new test asserts its card's Then lines in order. Each tag-entry check is an exact `==` against the six-key dict with its stored values.
- The default-limit cards build 101 / 51 / 101 rows by `add_all` through the new `account_row` / `link_row` helpers, which match the Convention rows unflushed. Each call omits `skip` and `limit`.
- N-08 and N-09 use the Convention `mgr raises` patch. N-08 checks `x_gone`.
- D-08 Then 1 is now `all("FOR UPDATE" not in t.upper() for t in rec.stmts)`, as the card says.

**Traceability.**
- 124 cases and 124 tests. Nothing unmatched, nothing duplicated, no marker mismatch.
- No `BUG_124` or `BUG_629` is left in the test file.
- `BUG_2986` and `BUG_2987` are strict xfail reasons whose text starts with their ID. Both rows exist in `bugs.md` (lines 1090 and 1091), with the account service and manager as their location. **Finding 4 is closed.**

**`--runxfail`.** 43 failed and 81 passed. My `thenline.py` matched 43 of 43 failures to the Then line the card names. There is no new xfail; the 8 new cards are pass cards.

**Targeted re-runs.**
| Item | Killed by |
|---|---|
| L167 `100→101` | ASV-L-10 |
| L292 `50→51` | ASV-H-05 |
| L378 `100→101` | ASV-T-10 |
| L223–227 tag keys | ASV-L-09 |
| L265–269 tag keys | ASV-M-03 |
| L421–426 tag keys | ASV-T-09 |
| L481 `'not found'→''`, L483 `raise→pass` | ASV-N-08 / N-09 |
| variants `unassign other -> 404`, `unassign 422 text`, `swallow unassign ValueError` | ASV-N-08, N-09 |
| variant: row lock in lower-case raw SQL | ASV-D-08 (case-insensitive now) |
| variant: tags read with `account.workspace_id` | survives: equivalent (the account has just passed the workspace check) |

**Commands.**
```
COVERAGE_FILE=…/svc1v/account/.coverage.r2 .venv/Scripts/python.exe -m pytest tests/unit/services/test_account_service.py -q -p no:cacheprovider -o addopts="" --cov=app.services.account_service --cov-branch --cov-report=term-missing
  → 93% (92-95, 357, 366-367) · 81 passed, 43 xfailed   (×3 plain runs: 81 / 43 each)
… --runxfail -rf --tb=short → 43 failed, 81 passed
.venv/Scripts/python.exe …/svc1v/account/remut.py → selected 21 · killed 21 of 21
.venv/Scripts/python.exe …/svc1v/account/var3.py  → 5 variants · 4 killed · 1 equivalent
ruff check tests/unit/services/test_account_service.py → clean
```
No remaining items.
