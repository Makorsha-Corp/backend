# Verification — `app/services/payment_transaction_service.py`

> **Verdict:** NEEDS WORK (minor: no unfaithful test; 2 `case-missing` and 1 `spec-gap` from the hand variants)
> Tests: 68 passed · 62 xfailed + 1 xpassed (non-strict D-14), reproduced ✅ · coverage 100% branch (63 stmts, 2 branches)
> Mutation (`mutate.py`): 19 mutants · 19 killed · 0 survived → score 100% (0 equivalent, 0 dead, 0 bug-path)
> Hand variants, today's code: 72 · 69 killed · 3 survived (2 equivalent, 1 case-missing) → 69/70 = 99%
> Hand variants against a scratch reference fix of BUG-3023 + BUG-019 (+ BUG-022): 46 · 44 killed · 2 survived (1 case-missing, 1 spec-gap) → 44/45 = 98%
> Source commit: e48a092 · Cases revision: 2b

## Summary
You can trust these tests. All 131 cards are implemented faithfully. Traceability is clean. Every xfail fails on the line its card names. The runs match the notes, with the one allowed non-strict xpass. `mutate.py` kills all 19 of its mutants.

`mutate.py` has few operators for this 108-line service, so I also wrote hand variants for everything the brief listed:
- TC1–TC6 on each write and read;
- error mapping;
- partial writes;
- the order of gateway calls and the commit;
- `duplicate_ignored`;
- the callback lock clause;
- workspace scope.

To test the not-yet-written idempotency code (BUG-3023) and the `INIT_FAILED` save (BUG-019), I built a small reference fix on a temp copy. With it, all 48 of those cards and the 68 pass cards pass, including IK-36's literal hash. I then broke that fix 46 ways: another member reusing a key, a fingerprint that ignores any one field, unsorted keys, each normalisation, a replay that commits, no workspace scope, the key checked after the gateway call, and the race paths. The cards caught 44 of them.

Three small gaps remain:
- A duplicate callback that re-stamps `validated_at` is not caught (case designer).
- A race handler that treats any `IntegrityError` as a key race is not caught (case designer).
- R7c1's "500.001 is a different body" cannot be reached once BUG-021 lands (describer).

## Findings
| # | Kind | Case / line | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing | GC-03, GC-04, TW-05 (`handle_gateway_callback` R2, `handle_terminal_without_validation` R2) | A duplicate callback is not checked for leaving `validated_at` alone. The Given stamps `validated_at` through `paid`/`held` with the patched `utcnow` = NOW, and the duplicate would stamp NOW again, so a re-stamp cannot be seen. | Hand variant "DUP duplicate path re-stamps validated_at (callback)" (`txn.validated_at = utcnow()` before the duplicate's flush) survived, 68 passed. | **case designer**: in one duplicate card, patch `utcnow` to a later time during the When (or set `validated_at` to a time other than NOW in the Given) and assert `validated_at` unchanged, or assert unchanged(T) apart from `updated_at`. |
| 2 | case-missing | IK-42 / IK-43 (`initiate_payment` R7e2, "IntegrityError on another constraint … re-raised unchanged") | IK-42's foreign-key error happens in a workspace with no keyed row. A handler that treats **any** `IntegrityError` as a key race rolls back, re-reads, misses, and re-raises the same error, so its answer is the same. No card has a non-key `IntegrityError` while a matching keyed row exists. | Reference variant "V13 any IntegrityError treated as the race" survived, 116 passed. | **case designer**: add a card where a keyed winner row exists and the loser's insert fails on another constraint (for example, the race simulation plus a `token_hex` patch that collides on `tran_id`). Expect that `IntegrityError` re-raised, not a replay. If no single-session setup can raise the other constraint first, mark it integration-only in "Deferred". |
| 3 | spec-gap (contradiction) | spec R7c1 "500.001 is a different body. It is not rounded." | Approved BUG-021 (manager spec Q3 / R9a) rejects amounts with more than 2 decimals at the schema. R7c1's 500.001 example can then never reach the fingerprint, and no card can test it. | Reference variant "V04 amount rounded to 2dp" survived, 116 passed. No card sends more than 2 decimals. | **describer** (fill-gaps): say the 500.001 example is unreachable after BUG-021, or replace it with a reachable one (`500.5` vs `500.50` is already IK-45). |

No unfaithful tests: no missing, weakened or changed assertion, no wrong setup, no in-memory-only check, no swallowed failure, no extra mock, and no dishonest xfail.

## Surviving mutants
`mutate.py`: none (19/19 killed, `mut_service.json`).

Hand variants:

| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| H1 | service :36 (initiate) | a failed `db.refresh` is followed by `db.rollback()` | equivalent | The refresh runs after the commit, so the extra rollback has nothing pending to undo. TC5 holds either way. | — |
| H2 | DAO `get_by_tran_id_for_update` | `.with_for_update()` → `.with_for_update(of=PaymentTransaction)` | equivalent | On this one-table SELECT, Postgres `FOR UPDATE OF payment_transactions` locks the same row in the same mode as plain `FOR UPDATE`. The spec makes only the clause's presence a unit case. FOR SHARE, FOR NO KEY UPDATE, SKIP LOCKED, NOWAIT, no lock, and locking after `validate` are all killed. | — |
| H3 | manager `finalize_from_gateway` duplicate path | re-stamps `validated_at` | case-missing | Finding 1 | case designer |
| R1 | reference fix, service race handler | any `IntegrityError` treated as the race | case-missing | Finding 2 | case designer |
| R2 | reference fix, fingerprint | amount quantized to 2 dp | spec-gap | Finding 3 | describer |

### Variant results by area (what the brief asked for)
- **Transaction contract.** All killed. Each of the 4 writes was tried with: no commit; refresh dropped; refresh before commit; rollback removed; commit instead of rollback; failing commit swallowed. Also killed: a commit before the manager call (initiate, callback); a commit after the "received" event and before `validate`; a commit before `init_session`; a commit between the row and its event; reads that commit, roll back on 404, flush, or take `FOR UPDATE` (detail and list).
- **Error mapping.** Killed: errors wrapped as 500, and errors swallowed (returns `None`), in all 4 writes; the detail 404 changed to 400; the callback 404 changed to 400; the 409 changed to 400 or given another message.
- **Callbacks.**
  - `duplicate_ignored`: killed when it is missing (both methods), doubled, when the duplicate overwrites `val_id`, and when it sets the status.
  - `validate`: killed when it is called twice, or before the duplicate check.
  - `init_session` called twice: killed.
  - Re-stamping `validated_at` survived (H3).
- **Lock clauses.** Callbacks: everything except the equivalent `OF payment_transactions` is killed (H2). Resolve: `FOR UPDATE OF payment_transactions` is BUG-029 (RR-08, strict xfail; it fails on Then 2 with `0 == 1` today).
- **Gateway call vs commit.**
  - GC-16 checks that `validate` runs with 0 commits so far.
  - I-10 and GC-09 check one gateway call when the commit fails.
  - Moving the commit before either gateway call is killed.
- **BUG-3023 (reference fix):**
  - Another member reusing the key (no `profile_id`): killed by IK-15.
  - The fingerprint ignoring any one of the 9 request fields or `amount`: each killed by IK-06/07–14 plus the hash cards.
  - Unsorted keys or default separators: killed by IK-01, IK-02, IK-36, IK-44, IK-45.
  - Normalisation (no trim, blank not null, amount not normalised, case-folded text, fingerprint taken after the profile defaults): all killed.
  - Replay that commits, has no rollback, or rolls back twice: killed by IK-03 (and IK-28).
  - Replay that writes an event or touches the row: killed by IK-30.
  - No workspace scope: killed by IK-16 to IK-19.
  - Key checked after the gateway call: killed by IK-03 to IK-15. Key checked after tran_id generation: killed by IK-30 and IK-31.
  - Lookup with `FOR UPDATE` or a join: killed by IK-31.
  - Key lower-cased, trimmed, or matched with LIKE: killed by IK-21 to IK-24 and IK-40.
  - Race (unhandled; 500 on a re-read miss; no fingerprint check; no rollback before the re-read): killed by IK-28, IK-29, IK-43. Any `IntegrityError` treated as the race survived (R1).
- **BUG-019 `INIT_FAILED` (reference fix).** Killed: not saved (rolled back); `failed_reason` missing from the response or not stored; no `"unknown error"` default; saved and then 502 raised; no `initiation_failed` event; key not stored; gateway URL kept.

## Traceability
- 131 cards, 131 tests or params. IK-07…14 and D-05…09 are parametrize groups with `id="PTS-…"`. No card is missing and no test lacks a card ID.
- Markers: 68 `pass` cards have no marker. 63 xfail cards use `xbug(...)` = `pytest.mark.xfail(strict=True)`, and D-14 and L-11 use `strict=False`, as the cards say. Each reason names the card's BUG ID, and all 10 BUG IDs used exist in `docs/testing/bugs.md`. There are no marker mismatches.
- `--runxfail` (scratch plugin mapping each failing test-file line to its `# Then N`):
  - All 63 xfail cards fail as designed.
  - 21 fail on the named Then line itself:
    - D-11 to D-14, D-17, L-10, L-11, L-13, RR-08, RR-11, TR-04, TW-03, TW-04 on Then 2;
    - GC-13, GC-14, IK-25, IK-41, IK-42 and I-05 on Then 1;
    - I-05 inside its `raises` block, with HTTPException 502.
  - The When raises before the first `# Then` comment, as the card says:
    - IK-01, IK-02, IK-31, IK-36, IK-40 and IK-45: `TypeError` on `idempotency_key`;
    - I-03 and I-04: HTTPException 502.
  - 34 fail in the Given helper:
    - IK-03 to IK-24, IK-28 to IK-30, IK-32 to IK-35, IK-37 to IK-39, IK-43 and IK-44 in `first()`, with the same `TypeError`;
    - IK-26 and IK-27 when building the row, with `invalid keyword argument`.
    - Conventions ("xfail cards") names this as the expected failure.
  - No failure is a setup or import error, and no failure is unrelated.
- The non-strict D-14 xpassed in all 3 plain runs and in 1 of 2 `--runxfail` runs. L-11 failed every time. This is the allowed tie-card behaviour, not a finding (see Notes).

## Commands run
All runs from `E:\Projects\Makorsh-Corp\backend`, each with a private `COVERAGE_FILE` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\svc1v2\payment_transaction\`.

```
.venv/Scripts/python.exe -m pytest tests/unit/services/test_payment_transaction_service.py -q -p no:cacheprovider -o addopts="" --cov=app.services.payment_transaction_service --cov-branch --cov-report=term-missing -rxX   (x3)
  run 1: 68 passed, 62 xfailed, 1 xpassed (D-14) · app\services\payment_transaction_service.py 63 0 2 0 100%
  run 2: 68 passed, 62 xfailed, 1 xpassed (D-14) · 100%
  run 3: 68 passed, 62 xfailed, 1 xpassed (D-14) · 100%
.venv/Scripts/python.exe -m pytest … -o addopts="" --runxfail -rf                         → 62 failed, 69 passed (D-14 passed)
.venv/Scripts/python.exe -m pytest … -o addopts="" --runxfail -p failline_plugin         → 63 failed, 68 passed (line map above)
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/services/payment_transaction_service.py tests/unit/services/test_payment_transaction_service.py --json …/mut_service.json
  → Mutants: 19 · killed 19 · timeout 0 · survived 0 · score 100%
.venv/Scripts/python.exe …/handmut.py    (temp copy, -m "not xfail")  → baseline 68 passed; 72 variants, 69 killed, 3 survived
.venv/Scripts/python.exe …/refimpl.py    (temp copy + reference fix + refplug DDL inside each test's outer transaction, --runxfail minus 15 unrelated bug cards)
  → baseline 116 passed, 15 deselected; 46 variants, 44 killed, 2 survived
.venv/Scripts/python.exe -m ruff check / ruff format --check <test file> → All checks passed / already formatted
```
Results and scripts: `hand_mutants.log/.json`, `ref_variants.log`, `ref_variants.final.json`, `mut_service.json`, `faillines.json`, `refimpl.py`, `refplug.py`, `handmut.py` in the scratch folder above. I wrote all of these scripts.

**First attempt discarded:** the hand run started while the reference run was going. The reference run's `ALTER TABLE` locks made the hand baseline show 5 failed. I stopped that hand run, waited for the reference run to finish, and ran the hand run again alone. Only the clean results are reported.

## Notes for future work
- **D-14 / L-11 tie cards.** Which plan Postgres picks decides the result. With the shared table's current statistics, D-14 xpassed 4 times in 5 runs today (the notes recorded 1 in 9), so it rarely shows the bug. D-13 (strict, `ORDER BY` text) carries BUG-1190 and L-10 carries BUG-2402, so no outcome hangs on the tie cards. When BUG-1190 and BUG-2402 are fixed, remove both non-strict markers, as the notes say.
- **Dependency on a second bug.** IK-02 and IK-04 also need BUG-019, IK-38 also needs BUG-022, and RR-11 also needs BUG-026, but each marker names only its main bug. That is harmless while they stay strict-xfail. Whoever fixes BUG-3023 should expect these four to stay red until the other fix lands.
- **Implementing BUG-3023 / BUG-019.** A reference fix that passes all 116 cards needs these changes, a useful starting point for the portal:
  - **columns:** `failed_reason`, `idempotency_key` and `idempotency_fingerprint`, plus the partial unique index with exactly the IK-25 `indexdef`;
  - **DAO:** `get_by_workspace_and_idempotency_key(db, *, workspace_id, idempotency_key)`, a one-table read with no lock;
  - **manager:** the lookup runs first and returns `(txn, replay)`;
  - **service:**
    - catch `IntegrityError` and check that it names the key index;
    - roll back, re-read, then replay or answer 409;
    - build a replay's response before its single rollback;
    - fill `failed_reason` in both responses.
  - The scratch `refimpl.py` holds the code.
- **Portal reference (spec Q4).** The service maps no gateway errors. A typed gateway error still needs to exist before 502/503 mapping can be tested (portal note in the spec).
- No new code bug found, so no rows were added to `docs/testing/bugs.md` (BUG-3034…3041 unused).

## Round 2 — 2026-11-22

> **Verdict:** PASS
> Tests: 68 passed · 64 xfailed (run 1: 63 xfailed + 1 xpassed, non-strict D-14), reproduced ✅ · coverage 100% branch
> Re-run variants: 14 targeted · 13 killed · 1 survived (equivalent once BUG-021 lands) · Cases revision: 3 (132 cards)

**Fidelity of the new and changed tests.** All faithful.
- **GC-03, GC-04, TW-05, TW-06:** the first outcome is built `at(V0)`. The tests assert `validated_at == V0` on the Then line the card names: GC-03 Then 6, GC-04 Then 3, TW-05 Then 2, TW-06 Then 2. The other Then lines are unchanged.
- **IK-46:**
  - The Given clears the winner's key, flushes it and commits.
  - `ik46_side_effect` follows the Conventions: first answer `None`, second answer restore + commit + real lookup.
  - `GHOST` is built in memory only.
  - Then 1–7 are asserted in card order: `IntegrityError`, `23503`, `lk.call_count == 1`, one `init_session`, 0 rows by `MISSING`, key still `None`, session usable.
- **Multi-bug markers:** they now match the Expect lines. That is IK-02 and IK-04 (`BUG_3023 + BUG_019`), IK-38 (`+ BUG_022`), and RR-11, D-17 and L-13 (`BUG_3022 + BUG_019 + BUG_026`).
- **Traceability:** 132 cards ↔ 132 tests or params. My script flagged these six concatenated reasons as mismatches; that was its own parsing limit, and I checked the six by hand. ruff is clean.

**`--runxfail`:** 64 failed, 68 passed. Every xfail fails as before, on its named Then line or in the Given helper as the Conventions allow. IK-46 fails in `first()` with the `idempotency_key` TypeError, as its card says.

**Targeted re-runs.** Each was run alone, the reference run first and the hand run after it.
| Variant | Before | Now | Killed by |
|---|---|---|---|
| H3 duplicate re-stamps `validated_at` (callback) | survived | **KILLED** | GC-03, GC-04 |
| new: duplicate re-stamps `validated_at` (terminal) | — | **KILLED** | TW-05, TW-06 |
| DUP: no event (callback, terminal), two events, overwrites `val_id`, sets status (terminal); `validate` before the duplicate check | killed | killed | GC-01/03/04/08/09, TW-05/06 |
| R1 any `IntegrityError` treated as the race (reference fix) | survived | **KILLED** | IK-46 |
| Other V13 race variants (not handled, re-read miss → 500, no fingerprint check, no rollback before re-read) | killed | killed | IK-28, IK-29, IK-43 |
| R2 amount quantized to 2 dp (reference fix) | survived | survived → **equivalent** | Once BUG-021 lands, the schema rejects amounts with more than 2 decimals, so quantizing to 2 dp changes nothing. Spec G9 replaced the unreachable 500.001 example, and no card change is needed. |

Reference-fix baseline: 117 passed, 15 deselected. IK-46 passes against a correct fix.

**Runs.** These used a private `COVERAGE_FILE` (`.cov_r2`) in the scratch folder: `r2_run1..3.log`, `ref_variants.r2.log`, `hand_mutants.r2.log`, `faillines.r2.json`.
- Run 1: 68 passed, 63 xfailed, 1 xpassed (D-14).
- Runs 2 and 3: 68 passed, 64 xfailed.
- All runs: 100% branch.

The results match the coordinator's 68 passed / 64 xfail, apart from D-14's allowed non-strict xpass.

**Open:** none. D-14 and L-11 stay non-strict until BUG-1190 and BUG-2402 are fixed (notes item, not a finding).
