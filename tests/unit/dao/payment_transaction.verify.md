# Verification — `app/dao/payment_transaction.py`

> **Current verdict: PASS (round 2, 2026-11-10, cases revision 3): findings 1 and 2 are closed. See "Round 2" at the end; the rest of this block is round 1.**
>
> **Verdict:** NEEDS WORK — only the case designer has work: 2 rule gaps, found by hand variants. No test is wrong.
> Tests: 125 passed · 18 xfailed, 12 strict and 6 non-strict (reproduced ✅) · coverage 100% branch (27 statements, 4 branches)
> Mutation: 29 mutants · 26 killed · 3 survived → score 100% (after excluding 3 equivalent, 0 dead, 0 bug-path)
> Fidelity: **0 of 143 unfaithful**
> Hand variants: 96 · 84 killed by a pass card · 9 fix candidates (BUG-029 / BUG-2402 / BUG-2403) judged with `--runxfail` · 3 tie variants bug-path · 1 survived (Finding 2), plus 2 BUG-029 fix candidates that wrongly pass (Finding 1)
> Source commit: e48a092 · Cases revision: 2 (143 cases, READY; spec APPROVED 2026-11-10)

## Summary
- **The tests can be trusted as written.** I read every one of the 143 tests against its card, Then line by Then line. Nothing is mocked or weakened, every write card re-reads from the database, and every `raises` names its exact type and pgcode.
- **Runs:** the runs reproduce the notes exactly, three times with no flakes. Every xfail fails on its card's "Fails today on" line.
- **Mutation:** `mutate.py` kills every mutant that can change behaviour. The 3 survivors only blank the `initiated_by_name` label, and every caller unpacks the pair by position.
- **Hand variants.** This file is the reference for the SSLCommerz portal, so I tried 96 hand variants. They covered case-insensitive and partial lookups, lock forms, the sweep's window, order, tie-break and limit, the local and database clocks, and money rounding and bounds. All were caught except two rule gaps, both for the **case designer**:
  - Finding 1 matters for the portal. A BUG-029 fix that takes `FOR UPDATE OF payment_transactions SKIP LOCKED` or `… NOWAIT` passes all six BUG-029 cards, although HR-10 says the loser waits and gets the normal 400.
  - Finding 2 is minor. A second profile read is hidden by the identity map.

Written by Claude (all 143 under `# [claude]`). Findings in local-written tests / local-written tests: 0 / 0. In others: 0 / 143. No `payment_transaction.local-run.json` exists, so there is no `## Local-coder patterns` section.

## Findings
| # | Kind | Case / rule | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing | `get_by_id_and_workspace_with_initiator` R5 [BUG-029]; PTX-IW-13 | IW-13 checks `"FOR UPDATE OF payment_transactions" in sql` and that `profiles` is not in `lock_part`. It never pins the rest of the lock clause, as PTX-TU-11 T4/T5 and TU-12 T3 do for the callback lock. So a fix that adds `SKIP LOCKED` passes: the second `resolve_risk` gets `None` (404) instead of waiting and getting the normal 400 (HR-10). A fix that adds `NOWAIT` also passes: the loser gets 55P03, a 500. Add to IW-13: `lock_part.strip() == "FOR UPDATE OF payment_transactions"` (or the two `NOWAIT` / `SKIP LOCKED` lines of TU-11). The spec R5 already says "only that row is locked" and HR-10 says the loser waits, so no spec change is needed. | `fix029_skiplocked` and `fix029_nowait` pass IW-01…IW-18 with `--runxfail`. `fix029_ok`, with `with_for_update(of=PaymentTransaction)`, passes too, as it should. Caught: `fix029_plain`, `_ofprofile` and `_both` (0A000, IW-13/14/15/16/18), `_share`, `_keyshare` and `_nolock` (IW-13), `_inner` (IW-03/04/14), and `_always` (IW-11/17). | **case designer** |
| 2 | case-missing | `get_by_id_and_workspace_with_initiator` R4 "One query (no separate profile read)"; same for `…tran_id_and_workspace…` R3 and the list R7; cards PTX-IW-11, TW-15, LW-21 | The initiator's profile is still in the session's identity map from `make_profile`, so a version that reads the transaction and then calls `db.get(Profile, …)` sends no second SELECT, and `len(selects) == 1` holds. Add `db.expire_all()` as the last Given step before the statement recorder starts in IW-11, TW-15 and LW-21. (Expiring does not evict, so `db.expunge_all()` may be needed; the card should say which.) Low weight: no wrong value results, only an extra query per row. | `iw_two_queries` (transaction query + `db.get(Profile, initiated_by)`) passes all 125 pass tests. | **case designer** |

No fidelity finding.

**The no-lock check here is not vacuous.** Other modules of this batch define `lock_part` as the text *after* `FOR UPDATE`, and that is empty for a plain lock. These cards define it as the text *from* the first `FOR UPDATE` to the end, and `StatementRecorder.lock_part` does the same. Checked with `omdv\PT\plug\lockall.py`, which adds a lock to every `PaymentTransaction` query:
- `FOR UPDATE OF …` is caught by TI-17, TW-15, IW-11, LW-21 and SI-21.
- A plain `FOR UPDATE` fails 48 tests.

## Surviving mutants
| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 24 | 38 | `'initiated_by_name'` → `''` | equivalent | Only the label of the second column changes. Its one caller (`PaymentTransactionManager.resolve_risk`, `txn, _ = row`) unpacks by position. The spec's Returns promises a pair that unpacks as two values, not an attribute name. | — |
| 25 | 51 | `'initiated_by_name'` → `''` | equivalent | Same; its one caller (`PaymentTransactionService.get_transaction_by_tran_id`, `txn, initiated_by_name = row`) unpacks by position. | — |
| 29 | 64 | `'initiated_by_name'` → `''` | equivalent | The rows are turned into plain tuples on line 72, so the label never leaves the method. | — |

## Hand variants
Plugin `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\omdv\PT\plug\ptv.py`, in-process (`-p ptv`, env `PTV=<name>`), never on disk. Runner: `run_variants.py`, output in `variants.txt`. Ordinary variants ran on the pass tests (`-m "not xfail"`). Fix candidates ran with `--runxfail` on their method's section.

| Group | Variants | Result |
|---|---|---|
| Lookups: case-insensitive or partial (`ilike`, `lower()`, `contains`, `startswith`, `trim`, `like`, truncation to 27) on `get_by_tran_id`, `…_for_update`, `…_and_workspace_with_initiator` | 13 | all killed (TI-06…16, TU-06/08, TW-10/12/13) |
| Workspace scoping (`…with_initiator` unscoped, `<=` / `>=` workspace, list unscoped, page-then-filter with W0/W2 rows on both sides) | 7 | all killed (IW-05/06/07, TW-04…07, LW-01/02/04/18/22) |
| Joins (inner join, resolver instead of initiator, rows not tuples) | 3 | all killed (IW-01/02/03/04/11, LW-05) |
| Callback lock (`get_by_tran_id_for_update`): none, `NOWAIT`, `SKIP LOCKED`, `FOR SHARE`, `FOR KEY SHARE`, `OF payment_transactions`, lock after a plain read, a commit inside | 8 | all killed (TU-11/12, TU-13/14) |
| Locks where none belong (`get_by_tran_id`, `…tran_id_and_workspace…`, `…id_and_workspace…` today, list, sweep plain and `SKIP LOCKED`) | 6 | all killed (TI-17, TW-15, IW-11, LW-21, SI-21) |
| BUG-029 fix candidates (`for_update`) | 11 | `fix029_ok` passes all 18 IW cards. 8 wrong shapes are caught. `_skiplocked` and `_nowait` pass → **Finding 1** |
| Ledger order and page (id only, `created_at ASC`, `initiated_at`, `updated_at`, unordered, limit ±1, default 99/101, skip ±1) | 11 | all killed (LW-03/05/06/07/08/13/14/15/16/17/18/20/21) |
| Ledger tie-break `created_at DESC, id ASC` | 1 | bug-path: no pass card. Caught by the strict LW-12 T6 with `--runxfail` |
| Ledger fix `created_at DESC, id DESC` | 1 | all 22 LW cards pass with `--runxfail` |
| Sweep window (`<=`, `created_at`, `updated_at`, `func.now()`, a local-clock cutoff, an aware cutoff forced to UTC) | 6 | all killed (SI-02/03/04/22…25 and others) |
| Sweep order (`created_at`, `id`, `DESC`, unordered) | 4 | all killed (SI-01/09/10/15/25) |
| Sweep limit (±1, default 199/201, filter after limit) | 5 | all killed (SI-15/16/18/20, OQ25-06) |
| Sweep status (`ilike`, `like 'INITIATE%'`, `trim`, not-success, `+ EXPIRED`) | 5 | all killed (SI-05/06/07/20, OQ25-01…06) |
| Sweep tie-break `id DESC`; `workspace_id` before `id` | 2 | bug-path: no pass card. Caught by the strict SI-14 T6 / T7 with `--runxfail` |
| Sweep fix `initiated_at ASC, id ASC` | 1 | all 31 SI/OQ25 cards pass with `--runxfail` |
| Times: Python default from the local clock (`datetime.now`, machine on Eastern time); Python default dropped, so the database's `now()` applies | 2 | killed (CR-01; CR-01…22) |
| Money (HR-15, `Numeric(15,2)`): half-even quantize, round down, `float`, clamp at the column's maximum, `abs` | 5 | all killed (CR-04/05/06, CR-23/24, CR-15) |
| `create` commits | 1 | killed (CR-03) |
| One query (`iw_two_queries`) | 1 | survived → **Finding 2** |

## For the portal (future notes)
These are for `docs/future/subscription-payments.md`; I did not edit it.
- Risk resolution's lock must be exactly `FOR UPDATE OF payment_transactions`: no `SKIP LOCKED`, no `NOWAIT` (Finding 1). A plain `FOR UPDATE` fails with 0A000 on the outer join.
- The `…with_initiator` reads return a positional pair. No caller may rely on the `initiated_by_name` attribute, because nothing pins it (mutants 24/25).
- "One query" checks need the identity map cleared first, or a second read is invisible (Finding 2). This applies to every portal DAO card that counts SELECTs.

## Traceability
- 143 cases, 143 tests, one each, in card order, each under `# [claude] <ID>`, and no test without a case ID.
- Marker mismatches: none. 12 strict and 6 non-strict xfails exactly as the cards say. Their reasons come from the constants `R029`, `R2401`, `R2402` and `R2403`, each starting with its BUG ID.
- BUG-029, BUG-2401, BUG-2402 and BUG-2403 are all in `docs/testing/bugs.md` (open).
- Script: `omdv\tools\trace.py`. It reported "missing bug ids" only because the reasons are constants; I checked them by hand.

## Commands run
```
COVERAGE_FILE=…/omdv/PT/.cov .venv/Scripts/python.exe -m pytest tests/unit/dao/test_payment_transaction.py -q -p no:cacheprovider -o addopts="" --cov=app.dao.payment_transaction --cov-branch --cov-report=term-missing
  app\dao\payment_transaction.py  27  0  4  0  100%
  125 passed, 18 xfailed in 8.71s
(same, without coverage, runs 2 and 3)
  125 passed, 18 xfailed in 5.29s
  125 passed, 18 xfailed in 5.30s
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_payment_transaction.py -q -p no:cacheprovider -o addopts="" --runxfail -rf --tb=line
  18 failed, 125 passed in 5.17s
  CR-18/19/20/21 at near_utc (Then 2) · IW-13…18 TypeError 'for_update' in the call (Then 1)
  LW-09/10/11 and SI-11/12/13 at the order list (Then 2) · LW-12 and SI-14 at "payment_transactions.id" in order_part (Then 4)
COVERAGE_FILE=…/omdv/.cov.mut.payment_transaction .venv/Scripts/python.exe tests/unit/_tools/mutate.py app/dao/payment_transaction.py tests/unit/dao/test_payment_transaction.py --json …/omdv/payment_transaction.mut.json
  Mutants: 29 · killed 26 · timeout 0 · survived 3 · score 90%
.venv/Scripts/python.exe …/omdv/PT/run_variants.py   (results above; full list in variants.txt)
```

## Round 2 — 2026-11-10
Narrow re-check of cases revision 3 (patched, not regenerated). **Verdict: PASS.**

**Changed cards:** PTX-IW-13 (new Then 6: `lock_part.strip() == "FOR UPDATE OF payment_transactions"`); PTX-IW-11, TW-15 and LW-21 (new Given step `db.expunge_all()` before the recorder).

**Fidelity:** All four tests match their cards line by line. The Then 6 comment repeats the card's reason, and `db.expunge_all()` is the last Given step, as carded. The ids used in Then come from objects built before the expunge, as the new convention allows. **0 unfaithful.**

**Runs:** 125 passed, 18 xfailed ×3 · coverage 100% branch (27 statements, 4 branches) · `--runxfail` 18 failed, 125 passed. IW-13 still stops in the When with `TypeError`, its card's Then 1. No flaky outcome. Runs (private `COVERAGE_FILE`, `omdv\R2\.cov`): `pytest <file> -q -p no:cacheprovider -o addopts=""` with `--cov=app.dao.<module> --cov-branch` once, plain twice, then `--runxfail` once.

**Variants:**
- F1: `fix029_skiplocked` and `fix029_nowait` (`--runxfail -k ptx_iw`) now **fail IW-13** (Then 6). `fix029_ok` still passes all 18 IW cards.
- F2: `iw_two_queries` (a second profile read) is now **killed by IW-11**.
- Lock on every read, per method, both `FOR UPDATE OF payment_transactions` and plain: all 10 killed (TI-17, IW-11, TW-15, LW-21, SI-21; a plain lock also fails 0A000 on the outer joins).

Variants: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\omdv\PT\plug\r2var.py` (per-method `FOR UPDATE OF <table>` and plain `FOR UPDATE`; create's year hard-coded 2026, bypassing the tests' clock patch; a hidden `db.get` of the parent), driven by `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\omdv\PT\run_r2.py` on the pass tests (`-m "not xfail"`); results in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\omdv\PT\r2.txt`. `mutate.py` was not re-run: Revision 3 only adds assertions and one card, so no mutant killed in round 1 can survive now.

**Open items:** None.
