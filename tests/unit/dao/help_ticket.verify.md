# Verification — `app/dao/help_ticket.py`

## Round 2 (2026-11-26) — cases Revision 3, narrow

> **Verdict:** PASS
> Tests: 112 passed · 10 xfailed, 6 strict + 4 non-strict (reproduced ✅) · coverage 100% branch (55 statements, 16 branches)
> Mutation: not re-run. `app/dao/help_ticket.py` is unchanged since the round above (41d5ac1, clean in `git status`), and that run killed all 51 mutants with fewer tests. Adding tests cannot let a killed mutant survive.
> Hand variants: the 7 survivors of the round above were re-run. 6 are now killed, and 1 is equivalent under the new R1d. 2 new R1d variants: 1 killed, 1 equivalent.
> Source commit: 41d5ac1 · Cases revision: 3 · Spec: Gap log G1 (new `create_with_user` R1d)

### Summary
- The findings of the round above are closed.
  - Finding 1 is closed by HLP-LW-38 and LW-39.
  - Finding 2 is closed by HLP-LP-33 … LP-36.
  - Finding 3 is closed by spec R1d plus HLP-CW-14 and CW-15.
- I read all 8 new cards against their tests. Each test builds the card's Given exactly, including `WithStatus` as the Conventions define it, and asserts every Then line in order with the card's values. 0 fidelity findings.
- Each new card kills the variant it was written for, and no other test changed outcome.
- Findings in local-written tests / local-written tests: 0 / 0. In others: 0 / 8 new (122 in all, every test under `# [claude]`).

### Findings
None.

### Hand variants
Same plugin, `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\help_ticket_dao\plug\htv_plug.py`, default run.

| Variant | Round above | Now |
|---|---|---|
| `lw_type_like` (L106 `.like`) | survived | killed by LW-38 |
| `lw_type_strip` (L106 `.strip()`) | survived | killed by LW-39 |
| `lp_type_like` (L136) | survived | killed by LP-34 |
| `lp_type_strip` (L136) | survived | killed by LP-35 |
| `lp_type_lower` (L136) | survived | killed by LP-33 |
| `lp_type_trimcol` (L136) | survived | killed by LP-36 |
| `cw_status_from_input` (L53 `getattr(obj_in, "status", None) or PENDING`) | survived (spec-gap) | **equivalent** under R1d: see below |
| `cw_status_drop` (new: `data.pop("status", None)`, so a caller's status is silently overridden) | — | killed by CW-14 (`DID NOT RAISE TypeError`) |
| `cw_status_keep` (new: `status=data.pop("status", PENDING)`) | — | **equivalent**: see below |

Why the two R1d variants are equivalent:
- **`cw_status_from_input`:** `**data` still carries the key, so any input whose dump has `status` raises the same `TypeError`. For `HelpTicketCreate.model_construct(status=…)`, the attribute is not set, so `getattr` returns `None` and the ticket is pending (CW-15 passes under it). Only an object with a `status` attribute that is missing from `model_dump()` would behave differently. No rule or caller describes such an input.
- **`cw_status_keep`:** `**data` is unpacked before the later keyword value is evaluated, so the `status` key is still passed twice and the call raises the same `TypeError`.

### Reproduced claims
- **Coverage:** `112 passed, 10 xfailed, 4 warnings` — 100% (55 statements, 16 branches, 0 missing). The 4th warning is CW-15's `model_construct` serialization warning, which the Conventions call harmless.
- **`--runxfail`:** `10 failed, 112 passed`. Each test fails on the Then line its card names: CW-03 Then 2, LW-17 Then 2, LW-18 Then 3, LW-27 Then 1, LP-11 Then 2, LP-12 Then 2, LP-13 Then 1, LP-20 Then 2, LP-21 Then 3, LP-26 Then 1.
- **Repeats:** 3 more default runs with `-rX`. Two gave `112 passed, 10 xfailed`. One gave `112 passed, 9 xfailed, 1 xpassed`, and the XPASS was **HLP-LW-17**. This is the same XPASS as in the round above, now identified, and it also appeared in 2 of the variant runs.
  - It is not a finding. LW-17 is non-strict by the spec's Notes because the order of tied rows is not fixed under BUG-1442. The run stays green, and the strict cards LW-18 and LP-21 carry the proof.
  - It does show that the notes' "xfailed in every run" is not true for LW-17. That is notes wording only; the executor may correct it, but nothing is required.

### Traceability
- Cases 122, tests 122. Unmatched IDs: none. Marker mismatches: none.
- The `# Then N` count equals the card's Then count for all 122 tests.
- The 8 new cards are all `Expect: pass`, and none of their tests has a marker.

### Commands run
```
.venv/Scripts/python.exe trace.py tests/unit/dao/help_ticket.cases.md tests/unit/dao/test_help_ticket.py docs/testing/bugs.md
  → cards 122 tests 122 (no mismatch lines)
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_help_ticket.py -q -p no:cacheprovider --cov=app.dao.help_ticket --cov-branch --cov-report=term-missing
  → 112 passed, 10 xfailed, 4 warnings · app\dao\help_ticket.py 55 0 16 0 100%
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_help_ticket.py -q -p no:cacheprovider --runxfail --tb=line
  → 10 failed, 112 passed, 4 warnings
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_help_ticket.py -q -p no:cacheprovider -rX   (x3)
  → 2 x 112 passed, 10 xfailed · 1 x 112 passed, 9 xfailed, 1 xpassed (XPASS HLP-LW-17)
HTV=<variant> PYTHONPATH=...\plug .venv/Scripts/python.exe -m pytest tests/unit/dao/test_help_ticket.py -q -p no:cacheprovider -p htv_plug   (9 variants, table above)
```

### Fix list
None.

---


## Round (2026-11-26) — cases Revision 2, spec revision 2026-11-26

> **Verdict:** NEEDS WORK — the case designer has two small card additions and the describer one spec line. No test is wrong.
> Tests: 104 passed · 10 xfailed, 6 strict + 4 non-strict (reproduced ✅) · coverage 100% branch (55 statements, 16 branches)
> Mutation: 51 mutants · 51 killed · 0 survived → score 100% (after excluding 0 equivalent, 0 dead, 0 bug-path)
> Hand variants on the new `type` / `ticket_type` code: 11 · 4 caught by a pass card · 7 survive (Findings 1–3)
> Fidelity: 0 of 114 unfaithful (all 26 new / revised cards read line by line against their tests; `git diff` of the test file removes only the old CW-01, LW-05, LW-19, LP-22 lines, so the other 88 tests are the ones round 2 checked)
> Source commit: 41d5ac1 · Cases revision: 2

### Summary
- **The tests can be trusted as written.** Each of the 114 cards has exactly one test. The 22 new cards (GN-12, CW-09 … CW-13, LW-28 … LW-37, LP-27 … LP-32) and the 4 revised ones (CW-01, LW-05, LW-19, LP-22) assert every Then line in order, with the card's exact values and Givens (types, statuses, workspaces, `newer` order). The tool killed all 51 mutants, including every mutant on the new lines 44–47, 105–106 and 135–136.
- **Why NEEDS WORK:** hand variants on the new exact-compare lines survive. On `list_by_workspace` the type cards copy the status shapes `""`, capitals, a part and a stored space. They leave out the two that round 1 asked for on status (`_`, a leading space in the parameter: LW-23 / LW-24), so `.like()` and `.strip()` pass. On `list_platform` only `ticket_type=""` is carded, so `.like()`, `.strip()`, `lower()` or `trim(column)` on line 136 all pass. Separately, the spec says status is `pending` "whatever the input". The code does not do that for an input that carries a `status` field: it raises `TypeError`. The cases file already lists this as Spec gap 5.
- Written by Claude (all 114 under `# [claude]`). Findings in local-written tests / local-written tests: 0 / 0. In others: 0 test-side / 114. There is no `help_ticket.local-run.json`, so there is no `## Local-coder patterns` section.

### Findings
| # | Kind | Case / line | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing | `list_by_workspace` R2a ("exactly that type", by reference to R2: no wildcard, no trimming), line 106 | LW-31 … LW-34 cover `""`, `"Feedback"`, `"feed"` and a stored `" feedback"`. No card puts `_` in the parameter and none puts a leading or trailing space in the parameter. Those are the LW-23 / LW-24 shapes that exist for status. | Variants `lw_type_like` (`HelpTicket.type.like(ticket_type)`) and `lw_type_strip` (`== ticket_type.strip()`) pass all 104 pass cards. Recipe R-7. | **case designer** |
| 2 | case-missing | `list_platform` R2a ("keeps exactly that type, as `list_by_workspace` R2a"), line 136 | Only LP-29 (`""`) checks the exact compare. Line 136 is its own expression, so the LW cards do not reach it. The Reviewer summary chose to card the shapes on LW only, and that leaves the platform line unchecked. | Variants `lp_type_like`, `lp_type_strip`, `lp_type_lower` (`func.lower(col) == func.lower(arg)`) and `lp_type_trimcol` (`func.trim(col) == arg`) each pass all 104 pass cards. Recipe R-8. | **case designer** |
| 3 | spec-gap | `create_with_user` R1 ("`status = 'pending'` (always, whatever the input)"); cases Spec gap 5 | The rule does not say what happens when the input carries a `status` field (or a `workspace_id`, `ticket_number` or `created_by` field). Today such an input raises `TypeError` before any SQL runs, because `HelpTicket(**data, status=…)` gets the keyword twice. It cannot happen through `HelpTicketCreate`: `model_construct(status="closed")` drops the extra field, so it is not in `model_dump()`. | Probe `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\help_ticket_dao\probe_status.py` (no DB write): `TypeError app.models.help_ticket.HelpTicket() got multiple values for keyword argument 'status'`; `model_construct keeps status in dump: False`. Variant `cw_status_from_input` (take `obj_in.status` if present) passes all 104 pass cards. | **describer** (fill-gaps). Either narrow R1 to "`HelpTicketCreate` has no `status`; the status is always `pending`", or state the `TypeError`. Then the case designer closes Spec gap 5 if a rule results. |

No fidelity finding.

**Recipes (for the case designer; the wording is theirs):**
- **R-7** (`list_by_workspace`, like LW-23 / LW-24): F = ticket, `type "feedback"`, `ticket_type="feed_ack"` → `result == []` (kills `.like`). F = ticket, `type "feedback"`, `ticket_type=" feedback"` → `result == []` (kills `.strip()`).
- **R-8** (`list_platform`, `search=TAG`, `own(...)`): F = ticket, `type "feedback"`, then each of `ticket_type="Feedback"`, `"feed_ack"` and `" feedback"` → `own(result) == []`. Also F = ticket, `type " feedback"`, `ticket_type="feedback"` → `own(result) == []`. `list_platform`'s `status` (line 134) is missing the same shapes: it has only LP-25 (`""`) and LP-27 (`"open"`), which round 2 accepted. Whether to cover both in the same cards is the designer's choice.

### Surviving mutants
None: all 51 were killed. The mutants on the new code were L45 `'type'`→`''` and `'support'`→`''`, L46 negate `if` and `'value'`→`''`, L105 / L135 negate `if` and `IsNot`→`Is`, and L106 / L136 `Eq`→`NotEq`. All were killed.

### Hand variants (2026-11-26, new code only)
The variants run through the plugin `htv_plug.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\help_ticket_dao\plug\` (`-p htv_plug`, `HTV=<variant>`). The plugin rewrites the DAO class's methods in-process from the source text with one change and asserts that the change applied; nothing in `app/` is touched. Default run, xfail markers on.

| Variant | Change | Result |
|---|---|---|
| `lw_type_lower` | L106 `func.lower(col) == func.lower(arg)` | killed by LW-32 |
| `lp_type_truthy` | L135 `if ticket_type:` | killed by LP-29 |
| `cw_type_str` | L47 `str(ticket_type)` instead of `.value` | killed by CW-01, 02, 04 … 09 (enum repr, 22001 on `HelpTicketTypeEnum.SUPPORT`) |
| `gn_type_support` | L26 also `HelpTicket.type == 'support'` | killed by GN-12 (`HELP-2026-003` ≠ `-005`) |
| `lw_type_like`, `lw_type_strip` | L106 | **survive** → Finding 1 |
| `lp_type_like`, `lp_type_strip`, `lp_type_lower`, `lp_type_trimcol` | L136 | **survive** → Finding 2 |
| `cw_status_from_input` | L53 `getattr(obj_in, "status", None) or PENDING` | **survives** → Finding 3 |

Considered and not listed:
- An `OR` with a status that no row has: equivalent by construction.
- `data.get` instead of `pop`: raises `TypeError` on every create, so every CW pass card catches it.

### Reproduced claims
- Coverage run: `104 passed, 10 xfailed, 3 warnings` — 100% (55 statements, 16 branches, 0 missing). The 3 warnings are the pydantic serialization warnings of CW-10, 12 and 13, which the Conventions call harmless.
- `--runxfail -rf`: `10 failed, 104 passed`. Each fails on the Then line its card names, mapped by the `# Then N` comment above the failing line:
  - CW-03 Then 2 (`'HELP-2027-001' == 'HELP-2026-001'`)
  - LW-17 Then 2, LW-18 Then 3 (`'.id' in ' help_tickets.created_at DESC \n '`), LW-27 Then 1
  - LP-11 Then 2 (decoy returned), LP-12 Then 2, LP-13 Then 1 (`[…88] == […87]`)
  - LP-20 Then 2, LP-21 Then 3, LP-26 Then 1

  This matches the notes' table. No test failed on a setup or import error.
- Repeats: 12 more default runs. 11 gave `104 passed, 10 xfailed`. **1 gave `104 passed, 9 xfailed, 1 xpassed`.** That was the second run, while the mutation run was using the database. It did not happen again in the next 10 runs with `-rX`, so the card is not known; it is one of the non-strict tie cards LW-17, LW-27, LP-20 or LP-26. This is not a finding. The spec's Notes make those cards non-strict precisely because the tie order is not fixed under BUG-1442. The run stays green, and the strict SQL cards LW-18 / LP-21 carry the proof. The notes' "xfailed in every run" should not be read as a guarantee (executor, notes wording only, optional).

### Traceability
- Cases 114, tests 114. Unmatched: none. Tests without an ID: none.
- Marker mismatches: none. There are 10 xfail markers, each as strict as its Expect line says. Their reasons come from `BUG_1441` / `BUG_1442` / `BUG_1443`, and all three IDs are in `docs/testing/bugs.md`.
- For all 114 tests the `# Then N` count equals the card's Then count.
- Script: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\help_ticket_dao\trace.py`.

### Commands run
```
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/dao/help_ticket.py tests/unit/dao/test_help_ticket.py --json C:/Users/User/AppData/Local/Temp/makorsh-pipeline/help_ticket_dao/mutants-2026-11-26.json
  → Mutants: 51 · killed 51 · timeout 0 · survived 0 · score 100%
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_help_ticket.py -q -p no:cacheprovider --cov=app.dao.help_ticket --cov-branch --cov-report=term-missing   (COVERAGE_FILE in scratch)
  → 104 passed, 10 xfailed, 3 warnings · app\dao\help_ticket.py 55 0 16 0 100%
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_help_ticket.py -q -p no:cacheprovider --runxfail -rf
  → 10 failed, 104 passed, 3 warnings
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_help_ticket.py -q -p no:cacheprovider   (x12, ten with -rX)
  → 11 x 104 passed, 10 xfailed · 1 x 104 passed, 9 xfailed, 1 xpassed
HTV=<variant> PYTHONPATH=...\plug .venv/Scripts/python.exe -m pytest tests/unit/dao/test_help_ticket.py -q -p no:cacheprovider -p htv_plug   (11 variants, table above)
.venv/Scripts/python.exe trace.py tests/unit/dao/help_ticket.cases.md tests/unit/dao/test_help_ticket.py docs/testing/bugs.md
  → cards 114 tests 114 (no mismatch lines)
```

### Fix list
- **case designer:** R-7 (Finding 1) and R-8 (Finding 2). Both are new pass cards; no new bug.
- **describer (fill-gaps):** Finding 3. Settle what `create_with_user` R1 means by "whatever the input" (cases Spec gap 5).
- **executor:** nothing required now. Once the new cards exist, implement them and re-run.

---

# Earlier rounds (kept as written)


> **Current verdict: PASS** (round 2, 2026-11-03, revision 1). See "Round 2" at the end. The rest of this block is round 1.
>
> **Verdict:** NEEDS WORK — only the case designer has work. No test is wrong.
> Tests: 75 passed · 8 xfail, 6 strict, 2 non-strict (reproduced ✅) · coverage 100% branch (46 statements, 10 branches)
> Mutation: 42 mutants · 42 killed · 0 survived → score 100% (after excluding 0 equivalent, 0 dead, 0 bug-path)
> Fidelity: **0 of 83 unfaithful** (83 / 83 right)
> Hand variants: 88 · 70 caught by a pass card · 18 others: rule gaps in Findings, the rest under "Considered and not listed"
> Source commit: e48a092 · Cases revision: none; spec APPROVED

## Summary
- **The tests can be trusted as written.** I read all 83 against their cards; all match, and the script agrees. The shared-table cards (TAG-named workspaces, `own(result)`, `limit=1000` for the unfiltered searches) are built as the Conventions say. They held in 3 default runs and in every reference, variant and mutant run, beside other agents' runs.
- **Why NEEDS WORK:** 6 rule gaps for the case designer. Three matter most: the `status` exact compare, `list_platform`'s `status=""`, and the tie cards whose tickets all share one title. The rest are shape cards: W2-asked reads, unflushed edits, a ticket with no creator in `get_by_id`.

Written by Claude (all 83 under `# [claude]`). Findings in local-written tests / local-written tests: 0 / 0. In others: 0 test-side / 83. No `help_ticket.local-run.json` exists, so there is no `## Local-coder patterns` section.

## Findings
| # | Kind | Rule | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing | `list_by_workspace` R2 ("exactly that status") | LW-04 (`""`) and LW-05 (`"OPEN"`) only. No `_`, no leading space on either side (skill step 1b). | `lws_txt_like`, `lws_txt_strip`, `lws_txt_trimcol` pass all 83. Recipe R-1. | **case designer** |
| 2 | case-missing | `list_platform` R2 ("status given (not `None`)") | No `status=""` card for the platform list (LW-04 covers only the workspace list), so `if status:` passes. | `lp_status_truthy` passes all 83. Recipe R-2. | **case designer** |
| 3 | case-missing | `generate_ticket_number` R2, `list_by_workspace` R1 (another workspace) | Their isolation cards ask for W1 with the other tickets in W2, the later id. A `<=` on `workspace_id` leaks the earlier workspace's tickets. | `gn_ws_le`, `lw_ws_le` pass all 83. Recipe R-3. | **case designer** |
| 4 | case-missing | `generate_ticket_number`, `get_platform_by_id` Side effects: none | GN-10 and GP-06 have a pending row but no unflushed edit, so a read that expires the session passes. | `gn_w_expire`, `gp_w_expire` pass all 83. Recipe R-4. | **case designer** |
| 5 | case-missing | `get_by_id` R1 ("Returns the ticket with that id", creator loaded) | No `get_by_id` card has a ticket without a creator (GW-07 covers only `get_by_id_and_workspace`), so an inner join to `profiles` passes. | `gb_inner_join` passes all 83. Recipe R-5. | **case designer** |
| 6 | case-missing | `list_by_workspace` R5, `list_platform` R5 [BUG-1442] ("then `id` descending") | LW-17 and LP-20 give the four tied tickets one title, "Printer jam". So a text key slipped in before the tail is invisible, and LW-18 and LP-21 only count `DESC` words (skill step 1b, sort keys). This holds after the fix too, once the markers come off. | Extra variants `lw_ord_title_asc`, `lp_ord_title_asc` (`created_at DESC, title, id DESC`, not in the table) pass all 83, with `--runxfail` too. Recipe R-6. | **case designer** |

No fidelity finding.

### Scratch cards that close the gaps
In `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\attv\prop\prop_help_ticket.py`, not in the repo, run by `propdrive.py` in a temporary copy of the backend. Each passes on today's code (the xfail ones xfail or xpass, as non-strict allows) and on my reference with `--runxfail`. Each named variant fails its recipe.

| Recipe | Where | Given and When | Then | Expect | Fails on |
|---|---|---|---|---|---|
| R-1 | three new cards HLP-LW-23 … LW-25, R2 | LW-23: A = ticket, `ticket_number "HELP-2026-001"`, but `status "closed"`; When `list_by_workspace(db, workspace_id=W1.id, status="clos_d")`. LW-24: the same A; When `status=" closed"`. LW-25: A = ticket, `ticket_number "HELP-2026-001"`, but `status " closed"`; When `status="closed"` | `result == []` | pass | LW-23 `lws_txt_like`; LW-24 `lws_txt_strip`; LW-25 `lws_txt_trimcol` |
| R-2 | new card HLP-LP-25, R2 | A = ticket, `ticket_number "HELP-2026-001"`; When `list_platform(db, status="", search=TAG)` | `own(result) == []` | pass | `lp_status_truthy` |
| R-3 | two new cards HLP-GN-11, HLP-LW-26 | GN-11: A = ticket, `ticket_number "HELP-2026-001"`; When `generate_ticket_number(db, workspace_id=W2.id, year=2026)`. LW-26: A = ticket, `ticket_number "HELP-2026-001"`; Z = ticket, `ticket_number "HELP-2026-001"`, but `workspace_id W2.id`; When `list_by_workspace(db, workspace_id=W2.id)` | GN-11: `result == "HELP-2026-001"`. LW-26: `ids(result) == [Z.id]` | pass | GN-11 `gn_ws_le`; LW-26 `lw_ws_le` |
| R-4 | HLP-GN-10 and HLP-GP-06, more Given and Then lines | GN-10: before P, B = ticket, `ticket_number "HELP-2025-001"` (another year, so the count stays 0); `B.title = "Edited"` (not flushed). GP-06: after A, B = ticket, `ticket_number "HELP-2026-003"`; `B.title = "Edited"` (not flushed) | pending: `B in db.dirty`; pending: `len(db.dirty) == 1` (ahead of `nothing written:`) | pass | GN-10 `gn_w_expire`; GP-06 `gp_w_expire` |
| R-5 | new card HLP-GB-06, R1 | A = ticket, `ticket_number "HELP-2026-001"`, but `created_by None`; When `get_by_id(db, ticket_id=A.id)` | 1. `result.id == A.id`. 2. `result.creator is None` | pass | `gb_inner_join` |
| R-6 | two new cards HLP-LW-27, HLP-LP-26, R5 [BUG-1442] | A = ticket, `ticket_number "HELP-2026-001"`, but `title "Alpha"`; B = …`-002`, `title "Bravo"`; C = …`-003`, `title "Charlie"`; D = …`-004`, `title "Delta"`; newer(D, 1); seqscan; bumpT(A); When `list_by_workspace(db, workspace_id=W1.id)` / `list_platform(db, search=TAG)` | LW-27: `ids(result) == [D.id, C.id, B.id, A.id]`. LP-26: `tids(result) == [D.id, C.id, B.id, A.id]` | xfail BUG-1442 (non-strict); Fails today on: Then 1 when the physical order differs | `lw_ord_title_asc`, `lp_ord_title_asc` |

## Surviving mutants
None. Every kill ends in a plain `N failed`.

**Guard.** My own driver (`drive.py muts`) re-ran every mutant of mutate.py's own list with no `-x`. Every run reached every pass test, with no collection or setup error, and each kill or survival matched mutate.py's.

## Hand variants
My reference fix and the variants are a pytest plugin, `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\attv\plug\attvref.py` (`-p attvref`). It replaces the DAO's methods in-process with the spec's intended behaviour, bug rules included; nothing is written to `app/`. Runs used `--runxfail` on the default plan. Every variant was asserted to be applied, and every run reached all 83 tests. Group = the method's tag.

| Group | Variants | Pass card | Cards that fail | Others |
|---|---|---|---|---|
| gn | 11 | 9 | HLP-CW-01, HLP-CW-02, HLP-CW-04, HLP-CW-05, HLP-CW-06, HLP-CW-07 … | `gn_ws_le`, `gn_w_expire` |
| cw | 6 | 5 | HLP-CW-01, HLP-CW-02, HLP-CW-05, HLP-CW-07, HLP-CW-08 | `cw_local` |
| gb | 7 | 6 | HLP-GB-01, HLP-GB-02, HLP-GB-03, HLP-GB-04, HLP-GB-05 | `gb_inner_join` |
| gw | 10 | 10 | HLP-GW-01, HLP-GW-02, HLP-GW-03, HLP-GW-04, HLP-GW-05, HLP-GW-06 … | — |
| lw | 17 | 14 | HLP-LW-01, HLP-LW-02, HLP-LW-03, HLP-LW-04, HLP-LW-05, HLP-LW-06 … | `lw_ws_le`, `lw_ord_id_asc`, `lw_ord_title` |
| lws | 8 | 5 | HLP-LW-04, HLP-LW-05 | `lws_txt_like`, `lws_txt_strip`, `lws_txt_trimcol` |
| lp | 21 | 15 | HLP-LP-01, HLP-LP-02, HLP-LP-03, HLP-LP-04, HLP-LP-05, HLP-LP-06 … | `lp_status_truthy`, `lp_noescape`, `lp_blank_nofilter`, `lp_no_join`, `lp_ord_id_asc`, `lp_ord_title` |
| gp | 8 | 6 | HLP-GP-01, HLP-GP-02, HLP-GP-03, HLP-GP-04, HLP-GP-05, HLP-GP-06 | `gp_no_join`, `gp_w_expire` |
| **Total** | **88** | **70** |  | **18** |

### Considered and not listed
| Variants | Why it is not a finding |
|---|---|
| `lp_blank_nofilter` | **Equivalent:** a search of only spaces with no filter returns every ticket, exactly as R4's `ILIKE '%%'` does; the four searched columns are NOT NULL. |
| `lp_no_join`, `gp_no_join` | Dropping the creator's `joinedload` on the platform reads. No rule of `list_platform` or `get_platform_by_id` names it: the creator's name comes in the tuple. Not a rule gap. |
| `cw_local`, `lp_noescape` | **Bug path** (BUG-1441, BUG-1443). CW-03 Then 2, LP-11 and LP-12 Then 2, LP-13 Then 1. |
| `lw_ord_id_asc`, `lw_ord_title`, `lp_ord_id_asc`, `lp_ord_title` | **Bug path** (BUG-1442). `*_ord_id_asc` fails LW-17 and LW-18 (LP-20 and LP-21); `*_ord_title` (`created_at DESC, title DESC, id DESC`) fails LW-18 and LP-21 on their `DESC` count. With `title` ascending it passes everything: Finding 6. |

## xfail tests against the reference
With `--runxfail` on the reference: 83 passed. **The alarm works:** with the markers on, every strict card is `XPASS(strict)`.

| Cards | Marker | Fails today on (`--runxfail`, my script mapping the failing line to its `# Then N`) |
|---|---|---|
| HLP-CW-03 | strict | Then 2 |
| HLP-LW-17, LP-20 | non-strict | Then 2 |
| HLP-LW-18, LP-21 | strict | Then 3 |
| HLP-LP-11, LP-12 | strict | Then 2 |
| HLP-LP-13 | strict | Then 1 |

Each fails on the line its card's "Fails today on" names.

## Reproduced claims
- **Result line of the notes holds:** `75 passed, 8 xfailed` in 3 of 3 default runs, the coverage run among them, and again in the mutation and variant bases. No flaky test.
- **Mocks:** only those the Conventions name (the commit spy, the clock). No `try`, no broad `pytest.raises`. `ruff check` passes.

## Traceability
cases 83 · tests 83 · unmatched: none · duplicates: none · marker mismatches: none. Card order equals file order. Each docstring equals its card's ID, title and Rules (several end with a period the card lacks; cosmetic). `# Then N` numbers match the card. Every BUG ID is in `docs/testing/bugs.md`. All tests sit under `# [claude] <ID>`.

My own script (`C:\Users\User\AppData\Local\Temp\makorsh-pipeline\attv\tools\rebuild.py`) compares each test with its card by AST and by text: name, docstring, marker, the When call's arguments, each Given line in order, each Then line's expression, operators and literals. Over the 433 cards of this batch it leaves no unexplained report; each report it gave was read by eye. Eye-read here: the whole file, against every card, the shared-table platform cards included. Selftest: 1306 of 1334 planted mistakes of 22 kinds reported. The 28 it misses are values inside pending-row code lines and re-read lines that go through a helper; those lines were read by eye in every module.

## Limits of this round
- **The reference and the variants are mine.** They show what these tests catch around them, not every possible break.
- **Runs were not isolated.** Other agents may have been live on the shared test database. Each kill is a plain `N failed`.
- **Variants ran on the default plan only**, not under forced plans; the order cards' plan sensitivity is the executor's notes'.
- **Not exercised:** manager, service or HTTP level; a real race.

## Commands run
```
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/dao/help_ticket.py tests/unit/dao/test_help_ticket.py --timeout 300 --json <scratch>/res/mut_help_ticket.json   (through runmut.sh)
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_help_ticket.py -q -p no:cacheprovider --cov=app.dao.help_ticket --cov-branch --cov-report=term-missing   (private COVERAGE_FILE)
  75 passed, 8 xfailed; then 2 more default runs and one --runxfail run
drive.py bases | muts | vars <module>; xfline.py; propdrive.py; rebuild.py; rebuild.py --selftest 8
.venv/Scripts/python.exe -m ruff check <the ten test files>     All checks passed!
git diff --stat -- app/dao                                   (empty)
```
Scratch: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\attv\`. Only this report was written in the repo. No commit. Nothing was stopped or killed.

## Fix list
1. **Case designer:** add the recipes above; the Givens and Thens are written out.
2. **Executor,** after 1: implement them and send back for re-verification.

## Round 2 — 2026-11-03 (revision 1, narrow)

> **Verdict:** PASS
> Tests: 82 passed, 10 xfailed (reproduced ✅) · coverage 100% branch
> Mutation: not re-run; round 1 stands
> Fidelity: **0 of 92 unfaithful** (the new and changed tests read by eye; all 92 compared by script)
> Source commit: e48a092 · Cases revision: 1; spec APPROVED, unchanged

Every finding of round 1 is closed. No new rule gap. No test or card edited in this round, no commit.

- **New cards:** HLP-GN-11, GB-06, LW-23 … LW-27, LP-25, LP-26. **Changed:** HLP-GN-10 and HLP-GP-06 (an unflushed edit B and its two `pending:` lines; later Then lines renumbered). Each new or changed test was read against its card and matches it, its recipe included.
- **xfail:** HLP-LW-27, LP-26: non-strict, each fails today on Then 1, as its card says.

### Gap variants against the new cards
Each round 1 gap variant ran on my reference with `--runxfail` on three plans: default; `enable_seqscan=off`; index, bitmap and index-only scans off. "Fails" means the named card failed in all three runs. Every run reached all tests.

| Variant | Card that must fail | Plans where it failed |
|---|---|---|
| `gn_ws_le` | HLP-GN-11 | default, seqoff, idxoff (3 of 3) |
| `lw_ws_le` | HLP-LW-26 | default, seqoff, idxoff (3 of 3) |
| `gn_w_expire` | HLP-GN-10 | default, seqoff, idxoff (3 of 3) |
| `gp_w_expire` | HLP-GP-06 | default, seqoff, idxoff (3 of 3) |
| `gb_inner_join` | HLP-GB-06 | default, seqoff, idxoff (3 of 3) |
| `lws_txt_like` | HLP-LW-23 | default, seqoff, idxoff (3 of 3) |
| `lws_txt_strip` | HLP-LW-24 | default, seqoff, idxoff (3 of 3) |
| `lws_txt_trimcol` | HLP-LW-25 | default, seqoff, idxoff (3 of 3) |
| `lp_status_truthy` | HLP-LP-25 | default, seqoff, idxoff (3 of 3) |
| `lw_ord_title_asc` | HLP-LW-27 | default, seqoff, idxoff (3 of 3) |
| `lp_ord_title_asc` | HLP-LP-26 | default, seqoff, idxoff (3 of 3) |

**Reference bases, `--runxfail`:** default: 92 of 92 passed, seqoff: 92 of 92 passed, idxoff: 92 of 92 passed.

### Reproduced
- `82 passed, 10 xfailed` in the coverage run. The ten files together gave `411 passed, 50 xfailed, 1 xpassed` in 2 of 2 runs, matching the coordinator's line. No flaky test.
- `ruff check` passes. `rebuild.py` over the ten files reports nothing beyond round 1's known alias noise. `git diff --stat -- app/dao` is empty.

### Commands run
```
rebuild.py <ten modules>; show.py <module> <new and changed ids>     read against the cards
round2.py                                                          gap variants and bases, 3 plans
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_help_ticket.py -q -p no:cacheprovider --cov=app.dao.help_ticket --cov-branch   (private COVERAGE_FILE)
.venv/Scripts/python.exe -m pytest <the ten test files> -q -p no:cacheprovider     x2
xfline.py; .venv/Scripts/python.exe -m ruff check <the seven test files>
```
Scratch: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\attv\`. Only this report was edited in the repo. Nothing was stopped or killed.
