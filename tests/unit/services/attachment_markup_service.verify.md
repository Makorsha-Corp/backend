# Verification — `app/services/attachment_markup_service.py`

> **Verdict:** NEEDS WORK (case designer only: two small card gaps; nothing for the executor or describer)
> **Current verdict (Round 2):** PASS. Cases Revision 2 closes findings 1 and 2. The tests (28 passed · 11 xfailed, 3 identical runs) are faithful, and every round-1 survivor now fails a card. See Round 2.
> Tests: 23 passed · 11 xfailed (reproduced ✅, 3 identical runs) · coverage 100% branch (40 statements, 0 branches)
> Mutation: 7 mutants · 7 killed · 0 survived → score 100% (after excluding 0 equivalent, 0 dead, 0 bug-path)
> Hand variants: 43 · 35 killed · 8 survived (1 equivalent, 2 delegated to the markup manager, 5 → case designer)
> Source commit: e48a092 · Cases revision: 1

## Summary
The tests are faithful to the cards. Traceability is clean: 34 cards ↔ 34 tests, every marker matches, and every BUG ID exists. Each Then line is asserted in card order with the card's exact values. Nothing is patched beyond the Conventions. With `--runxfail` all 11 strict xfails fail on the card's "Fails today on" line. Three plain runs are identical.

An independent reference written by the verifier passes all 34 tests with `--runxfail`. It reimplements the markup manager as intended (BUG-2115, 2118, 2119, 2120) and keeps today's service.

The service-level defects in the brief are all caught:
- commit then raise, and a commit before the manager runs (unrelated pending rows saved);
- a missing rollback on error;
- a rollback (or no commit) on the D1 reads;
- the caller or the session id not passed down;
- a re-read after the commit;
- per-row profile reads;
- a skipped parent-record check, and a role read from another workspace.

Two kinds of service defect pass:
1. An `AttachmentValidationError` turned into another error passes in `list_events`, `put_own_layer` and `delete_own_layer`. Only `list_layers` has a not-ready card.
2. A service that reorders the manager's list passes. Every list is compared as a set, but R1 says "in its order".

Both go to the case designer.

## Findings
| # | Kind | Case / line | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing | `list_events` R2, `put_own_layer` R3, `delete_own_layer` R2 ("errors … reach the caller unchanged"; Errors list `AttachmentValidationError`) | Only AMSV-LL-05 sends a not-ready attachment. Every other refusal card is `AttachmentNotFoundError`. A service that maps `AttachmentValidationError` to another type (here `AttachmentNotFoundError` with the same message) in these three methods passes. Needed: one card per method, like LL-05 (a pending A2, pending X): `raises: AttachmentValidationError`, `str == UNAV`, session clean, x_gone; for put and delete also "nothing written". | variants `mapval_lv`, `mapval_pl`, `mapval_dl`: 34 passed each (`mapval_ll` killed by LL-05) | case designer |
| 2 | case-missing | `list_layers` R1, `list_events` R1 ("exactly the manager's list, in its order") | Every list card compares sets (Reviewer summary: order is BUG-1435 / BUG-1436). Those bugs cover only ties. With distinct times the manager's order is defined today: events `created_at` newest first, layers `updated_at` oldest first. LV-01 already has E1 at T1 and E2 at T2, so a card `[i.id for i in result.items] == [E2.id, E1.id]` holds today. For layers, two layers with explicit distinct `updated_at` do the same. A service that reverses or sorts the list passes. | variants `order_ll`, `order_lv`: 34 passed each | case designer |

Unfaithful tests: none.

## Surviving mutants
None. All 7 mutants (3× `return None`, 4× `raise` → `pass`) were killed.

## Hand variants
These are my own in-process plugins: `attsvcv/mk/plug/v_amsv.py` and `v_failline.py`, in scratch only. The executor's plugins were not used.

`MV=base` is an independent intended-behaviour reference of the markup manager:
- **BUG-2115:** PR-3 over the attachment's W1 links before the ready / type check. A project is checked with `can_access_project`, a component through its project, and a ticket by the workspace owner or `can_access_ticket` with the active W1 role.
- **BUG-2118:** an equal payload writes no event.
- **BUG-2119:** authors are read in one `IN` query.
- **BUG-2120:** the insert runs in a savepoint; an `IntegrityError` turns it into an update with `markup_updated`.

The service stays today's (re-wrapped). The base passes **34 / 34** with `--runxfail`. Each other variant adds one defect to the base.

| Variant (one defect) | Failing tests | Result |
|---|---|---|
| read does not commit (TC6 style) — `list_layers` / `list_events` | LL-03 / LV-03 | killed |
| read rolls back instead of committing — ll / lv | LL-03 / LV-03 | killed |
| **commit then raise** on error (pending X saved) — ll / lv / pl / dl | 3 / 2 / 1 (PL-06) / 1 (DL-03) | killed |
| commit **before** the manager call (unrelated pending rows saved) — ll / lv / pl / dl | 4 / 3 / 2 / 1 | killed |
| no rollback on error — ll / lv / pl / dl | 3 / 2 / 1 / 1 | killed |
| wrong error mapping: not-found → `ValueError` — ll / lv / pl / dl | 5 / 2 / 3 / 2 | killed |
| wrong error mapping: validation → not-found — ll | 1 (LL-05) | killed |
| **wrong error mapping: validation → not-found — lv / pl / dl** | 0 / 0 / 0 | **survived → Finding 1** |
| caller not passed down (id 0 reaches the manager) — ll / lv / pl / dl | 2 / 1 / 7 / 2 | killed |
| `session_id` not passed down — pl / dl | 2 / 1 | killed |
| **list reversed by the service — ll / lv** | 0 / 0 | **survived → Finding 2** |
| layer re-read after the commit (put) | 2 (PL-05, PL-10) | killed |
| two commits — put | 1 (PL-05) | killed |
| two commits — delete | 0 | equivalent: the second commit has nothing pending, and no rule counts the commits of `delete_own_layer` |
| parent-record check skipped — ll / lv / pl / dl | 3 / 1 / 2 / 1 | killed |
| per-row profile reads (N+1) | 2 (LL-11, LV-06) | killed |
| ticket role read from the caller's newest membership in any workspace | 2 (LL-09, PL-09) | killed |
| ticket role read from the caller's oldest membership in any workspace | 0 | delegated: the oldest row is the W1 one in every Given; the role rule (PR-5) is the manager's and is pinned there |
| parent check **after** the ready / type check (PR-4) | 0 | delegated: no card here combines a hidden record with a not-ready attachment; the markup manager has them (AMUP-GR-43, AMUP-PL-21). The spec asks for one pass-through card per bug here. |

Not applicable to this service: Cloudinary delete before commit (no external call, HR-13 checked in the spec); a missing row lock (no lock rule; BUG-2120 is solved without a lock); one links query per item (BUG-2201 is `attachment_service`'s; here the list is of layers, and the PR-3 link read is once per call in the manager); and a list check on the parent record (BUG-2200 is the attachment list's; here it is BUG-2115, covered by LL-07 … LL-09 and LV-05 with W0 / W2 role rows and explicit ids, all killed above). A link filed under another workspace is invalid data and was not offered as a variant.

## Traceability
- **Counts:** 34 cards, 34 tests. Unmatched: none. Tests without a case ID: none. `# [claude] <ID>` sits above each test, and the ID is in each docstring.
- **Markers:** none mismatched.
  - 23 `pass` cards have no marker.
  - 11 `xfail` cards carry `strict=True`, and each reason names the card's BUG ID: BUG-2115 ×7, BUG-2118 ×1, BUG-2119 ×2, BUG-2120 ×1. All four IDs are in `bugs.md`.
- **Then blocks:** the `# Then N` blocks match each card's Then count.
- **Fails today (`--runxfail`, `v_failline`):**
  - LL-07, LL-08, LL-09, LV-05, PL-08, PL-09, DL-05 fail on Then 1 with `DID NOT RAISE AttachmentNotFoundError`.
  - LL-11 fails on Then 2 (`10 <= 2`) and LV-06 on Then 2 (`5 <= 2`).
  - PL-11 fails on Then 2 (`1 == 0`).
  - PL-10 raises `IntegrityError` (`UniqueViolation`) in the When call. The card names this ("Then 1 (the call raises IntegrityError 23505)").
- **Fidelity:** no weakened, missing or changed assertion. No swallowed failure: every `pytest.raises` names the card's type. No extra mock: only the spies, the failing commit, PL-05's order log and PL-10's race patch, all from the Conventions. The committed lines re-read after `db.rollback()`.

## For the coming features
- **Permissions:** the service adds no check of its own and passes the caller down unchanged (variants `caller_*` killed). BUG-2115 (PR-3 in `_get_ready_attachment`) is the whole permission story. When it is fixed, the seven BUG-2115 cards here XPASS. The shared `can_access_*` helper noted in the attachment and mobile verifications would serve the markup manager too.
- **Notifications:** the markup events (`markup_saved` / `markup_updated` / `markup_cleared`, with `session_id`) are committed here. A notification hook belongs after this service's commit, never inside the manager, so a rolled-back save notifies nobody. Fix BUG-2118 first, or no-op saves would notify.
- **Payments:** nothing here.

## Commands run
```
mutate.py app/services/attachment_markup_service.py tests/unit/services/test_attachment_markup_service.py --json attsvcv/mk/mut.json
  -> Mutants: 7 · killed 7 · timeout 0 · survived 0 · score 100%
pytest <test file> -q -p no:cacheprovider --cov=app.services.attachment_markup_service --cov-branch --cov-report=term-missing
  -> 23 passed, 11 xfailed; attachment_markup_service.py 40 0 0 0 100%
pytest <test file> -q -p no:cacheprovider --runxfail -rf            -> 11 failed, 23 passed (the 11 xfail cards)
pytest <test file> -q -p no:cacheprovider   (runs 2 and 3)          -> 23 passed, 11 xfailed (both)
PYTHONPATH=attsvcv/mk/plug pytest <test file> -q -s --runxfail -p v_failline  -> 11/11 fail on the card's Then line
PYTHONPATH=attsvcv/mk/plug MV=<variant> pytest <test file> -q --runxfail -p v_amsv  -> base 34 passed; variants as tabled (attsvcv/mk/variants.txt)
ruff check <test file>                                               -> All checks passed!
```
Every run used a private `COVERAGE_FILE` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\attsvcv\mk\`. bugs.md unchanged (BUG-2237 … 2242 unused).

## Round 2 — 2026-11-05

> **Verdict (Round 2):** PASS. No findings and nothing routed.
> Tests: 28 passed · 11 xfailed (reproduced ✅, 3 identical runs) · coverage 100% branch (40 statements, 0 branches)
> Mutation: not re-run this round (source unchanged at e48a092; round 1: 7 / 7 killed).
> Hand variants: the five round-1 survivors re-run against the round-1 reference. All 5 are now killed.
> Source commit: e48a092 · Cases revision: 2

### Summary
Cases Revision 2 adds five cards: LV-07, PL-12 and DL-07 (a not-ready attachment) and LL-12, LV-08 (the manager's order with distinct times). Each new test matches its card.
- **Givens are reproduced exactly.**
  - LL-12: the three layers are aged with `older(L1, 2)`, `older(L2, 3)`, `older(L3, 1)`, written as the Conventions' raw `UPDATE … make_interval` and then `expire_all`. The expected order `[U2, U1, UG]` does not follow insertion or id order.
  - LV-08: E1 is at T2, E2 at T1 and E3 at 11:00, so ids do not follow the newest-first order.
  - The pending-A2 cards add pending X after the commit point. DL-07's L is built before the commit point, and its id is copied there.
- **Then lines are asserted in card order with the card's exact values:**
  - `pytest.raises(AttachmentValidationError)`;
  - `str == UNAV`;
  - the three `session: clean` asserts before any re-read;
  - `x_gone`;
  - DL-07's re-read of L `payload == D(P1)`;
  - "nothing written" as `counts(db) == before`;
  - list equality (not sets) on LL-12 and LV-08.
- **Unchanged parts:** the 34 round-1 tests read as in round 1, with no marker change and no new patch.
- **Traceability:** clean.

### Round-1 survivors re-run
| Round-1 survivor | Round 2 | Killed by |
|---|---|---|
| `mapval_lv` (validation error turned into not-found in `list_events`) | killed (1) | LV-07 |
| `mapval_pl` (same, `put_own_layer`) | killed (1) | PL-12 |
| `mapval_dl` (same, `delete_own_layer`) | killed (1) | DL-07 |
| `order_ll` (service reverses the layer list) | killed (1) | LL-12 |
| `order_lv` (service reverses the history list) | killed (1) | LV-08 |

The round-1 reference (`plug/v_amsv.py`, `MV=base`, intended manager behaviour for BUG-2115, 2118, 2119, 2120) still passes **39 / 39** with `--runxfail`. So the new cards also hold against the intended behaviour. The round-1 equivalent and delegated survivors (`dblcommit_dl`, `check_after_ready`, `role_any_ws`) keep their classes.

### Findings
None. Unfaithful tests: none.

### Traceability
- **Counts:** 39 cards, 39 tests, IDs in the same order. Unmatched: none.
- **Markers:** 28 `pass` cards have no marker. 11 strict xfails are unchanged: BUG-2115 ×7, BUG-2118, BUG-2119 ×2, BUG-2120. The counts header (39 · 28 · 11) matches.
- **`--runxfail` (`v_failline`):** all 11 fail on the card's line, exactly as in round 1.
  - Seven BUG-2115 cards fail on Then 1 with `DID NOT RAISE`.
  - LL-11 fails on Then 2 (`10 <= 2`) and LV-06 on Then 2 (`5 <= 2`).
  - PL-11 fails on Then 2 (`1 == 0`).
  - PL-10 raises `IntegrityError` `UniqueViolation` in the When call, as its card names.

### Commands run (Round 2)
```
COVERAGE_FILE=<s>/.cov.p1 pytest <test file> -q -p no:cacheprovider --cov=app.services.attachment_markup_service --cov-branch --cov-report=term-missing
  -> 28 passed, 11 xfailed; attachment_markup_service.py 40 0 0 0 100%
COVERAGE_FILE=<s>/.cov.p{2,3} pytest <test file> -q -p no:cacheprovider          -> 28 passed, 11 xfailed (both)
PYTHONPATH=<mk>/plug pytest <test file> -q -s -p no:cacheprovider --runxfail -p v_failline  -> 11 failed, 28 passed; 11/11 on the card's line
PYTHONPATH=<mk>/plug MV=<variant> pytest <test file> -q -p no:cacheprovider --runxfail -p v_amsv
  -> base 39 passed; mapval_lv 1 failed (LV-07); mapval_pl 1 failed (PL-12); mapval_dl 1 failed (DL-07); order_ll 1 failed (LL-12); order_lv 1 failed (LV-08)
ruff check <test file>                                               -> All checks passed!
```
`<s>` = `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\attsvcv\mk\r2\`, which holds the private `COVERAGE_FILE`s. `<mk>` = its parent folder. mutate.py was not run, as instructed. bugs.md is unchanged (BUG-2237 … 2242 unused).
