# Verification — `app/services/invoice_payment_service.py`

> **Verdict:** NEEDS WORK
> Tests: 65 passed · 53 xfailed (reproduced ✅, every xfail fails on its card's "Fails today on" line) · coverage 97% branch (line 50 missing, as the notes say)
> Mutation: 27 mutants · 25 killed · 2 survived → score 100% (after excluding 0 equivalent, 1 dead, 1 bug-path)
> Service-level variants: 42 on today's code: 39 killed, 3 survived (1 case-missing, 2 equivalent). 42 on a reference BUG-3002 implementation: 42 killed (both baselines pass all 46 K cards).
> Source commit: e48a092 · Cases revision: 2

## Summary
These tests can be trusted. All 118 cards are implemented faithfully, in card order, with exact values. Nothing is mocked beyond the Conventions. Every xfail fails for its stated cause. Three runs agree. mutate.py leaves no real survivor.

The hand-written transaction-contract, error-mapping and HR-16 variants are all caught, except one: **`get_payment` committing on its success path goes unnoticed**. The spec says the read never commits or rolls back (`get_payment` R3, TC6), but the only TC6 card (G-07) covers the 404 path. That is one missing card, for the case designer. It is the only reason this report is NEEDS WORK.

Idempotency (BUG-3002): I wrote my own reference fix in a temp copy. All 46 K cards pass against it. Each of the 42 wrong versions I tried is caught, and caught by the card meant for it. The card set is a sound template for the payment portal (see "Idempotency reference").

## Findings
| # | Kind | Case / line | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing | `get_payment` R3 (TC6), lines 81–90 | Only the 404 path is checked for "neither commits nor rolls back" (G-07). A `db.commit()` on the found path passes every test. Add a card: payment found, X pending, **spies** → `cm.call_count == 0`, `rb.call_count == 0`, X still there (count 1). `list_payments_by_invoice` already has this card (L-10). | variant "TC6 get commits" (`db.commit()` before line 90's return) → 65 passed | **case designer** |

No fidelity findings. Tests checked: 118 (all `# [claude]`, no local-coder tests; no `local-run.json`).

## Surviving mutants
| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 8 | 50 | `return to_payment_response(payment, None)` → `return None` | dead | `_payment_response` R2: the re-read fallback cannot be reached through the public methods. Spec Q1 decided "intended, kept, no case". This is the notes' one coverage gap. | — |
| 16 | 154 | `return to_payment_response(payment_before, …)` → `return None` | bug-path | `delete_payment` R3 [BUG-609]: once the bug is fixed, no response is ever built. Only xfail cards D-04…D-06 target a successful delete, and mutate.py leaves them out of the run. | — (goes away with BUG-609) |

## Service-level variants (hand-written, temp copy, today's code, `-m "not xfail"`)
| Variant | Result | Killed by |
|---|---|---|
| TC1 no commit / `flush()` instead of commit — create | killed | C-01 C-02 C-03 C-10 C-11 C-13 C-16 K-23 K-25 |
| same — update | killed | U-01 U-10 U-11 U-12 |
| same — delete | killed | D-07 |
| same — void | killed | V-01 V-02 V-03 V-09 V-10 V-13 |
| commit before the manager call (commit before the error) — create / update / delete / void | killed ×4 | C-04 C-07 C-08 C-09 C-13 C-17 / U-02 U-05 U-10 / D-01 / V-04 V-07 |
| TC3 missing rollback in `except` — create / update / delete / void | killed ×4 | C-04 C-07 C-08 C-09 C-17 / U-02 U-05 / D-01 / V-04 V-07 (x_gone) |
| partial write after a failure (`commit()` in `except`) — each of the four | killed ×4 | same cards |
| TC5 refresh before commit (create, update, void) | killed | C-11 U-12 V-10 |
| TC2 response built before commit (create) | killed | C-11 |
| commit twice on success (create) | killed | C-13 |
| TC6 get commits on 404 / rolls back on 404 | killed ×2 | G-07 |
| **TC6 get commits on success** | **survived** | — → Finding 1 |
| TC6 list commits / rolls back | killed ×2 | L-10 |
| error map: get 404 → 400 | killed | G-04 G-05 G-06 G-07 |
| error map: delete 404 → 403 | killed | D-01 D-02 D-03 |
| error map: every exception → 500 | killed | 26 cards |
| error map: manager HTTPException re-wrapped as 400 | killed | 14 cards (all 404/403 passes) |
| swallowed error: create / void return `None` on error | killed ×2 | C-04…C-11 C-17 K-24 / V-04…V-10 |
| HR-16: DAO payment lookup without workspace filter | killed | G-05 (W2), G-06 (W0) |
| HR-16: workspace `>=` (only W2 leaks) / `<=` (only W0 leaks) | killed ×2 | G-05 / G-06 — both sides matter, as HR-16 asks |
| HR-16: manager invoice lock without workspace filter | killed | C-05 (W2), C-06 (W0) |
| HR-16: service passes the wrong workspace to the re-read | killed | C-01 PR-01 PR-02 U-01 V-01 |
| HR-16: `get_payment` reads with the payment's own workspace | killed | G-05 G-06 |
| HR-16: `delete_payment` pre-read with the payment's own workspace | survived — equivalent | The manager's own workspace-filtered lookup raises the same 404 (spec Q2: the redundant read is harmless). D-02/D-03 still get 404. |
| `delete_payment` pre-read dropped | survived — equivalent | Same reason (Q2). A successful delete would build from `None`, but that path is BUG-609 (bug-path). |

## Idempotency reference (BUG-3002 R9–R9i) — for the future payment portal
Method: in a temp copy only, I wrote my own reference fix:
- the model columns;
- the column + partial unique index, added by `ALTER TABLE` / `CREATE INDEX` inside each test's own transaction (a scratch pytest plugin, rolled back);
- the manager lookup after the plain invoice `FOR UPDATE` and before the checks;
- the spec R9f fingerprint;
- in the service: replay → response, then rollback; on `IntegrityError` on the index → rollback, re-read, replay or 409.

I ran the 46 K cards with `--runxfail`. **Baseline: 46 passed.** Then each wrong version below, one at a time:

| Wrong version (what a fix could get wrong) | Caught by |
|---|---|
| **Another member reusing a key** — the comparison ignores the caller (`profile_id`) | K-05 |
| Comparison ignores `invoice_id` / `payment_amount` / `payment_date` / `payment_method` / `payment_reference` / `bank_name` / `transaction_id` / `notes` | K-10 / K-09 / K-11 / K-12 / K-13 / K-14 / K-15 / K-16 — exactly one card each |
| Stored fingerprint recipe drops any one field (hash differs from R9f) | K-36 (literal SHA-256) + every replay card (K-01 K-04 K-06 K-07 K-08 K-28 K-34 K-35 K-38 K-39 K-43) |
| **Normalisation `400` vs `400.00`**: raw `str(amount)` in the comparison | K-34; in the stored recipe also K-36 and the replays |
| Over-normalisation: amount rounded to whole units (`400.01` = `400`) | K-09, K-29 |
| Text not trimmed / blank not null | K-35 |
| Text case-folded (`"Cash"` = `"cash"`) | K-36 + replays (and K-12 in a comparison-based fix) |
| Fingerprint not stored | K-01 K-36 K-38 |
| **Replay that commits** | K-04 K-06 K-07 K-08 K-34 K-35 K-39 K-43 (commit spy) |
| Replay neither commits nor rolls back (pending work survives) | K-04 K-06 K-07 K-08 K-43 (x_gone) |
| Race-path replay commits | K-28 |
| 409 without rollback | K-05 K-09 (x_gone) |
| 409 → 400; 409 detail leaks the first payment's id | K-05 K-09…K-16 |
| **Scope with no workspace filter** on the lookup | K-21 (W0), K-22 (W2) |
| Unique index on the key alone (no `workspace_id`) | K-21 K-22 K-32 K-33 |
| Index not partial | K-33 |
| Lookup skips voided payments | K-08 |
| Key trimmed / lower-cased | K-17 K-18 |
| `""` treated as "no key" | K-38 K-39 |
| Lookup before the invoice lock | K-27 K-44 K-45 |
| Lookup after the status / lock / amount checks | K-06 K-07 K-43 |
| Lookup takes its own `FOR UPDATE` | K-27 |
| `IntegrityError` on the index not handled (500) | K-28 K-29 |
| Every `IntegrityError` translated (not just the index) | K-46 |

What the portal (BUG-3023 / subscription checkout) should copy from these cards:
- **One 409 card per fingerprint field, the caller included.** A fix that compares field by field cannot drop a field silently.
- **A literal-hash card (K-36).** It pins the recipe itself.
- **A commit spy plus a pending row on every replay.** This catches a replay that commits, or one that never ends its transaction.
- **W0 and W2 key twins.** A lookup or index without `workspace_id` cannot pass.
- **An index race simulated by patching the manager to insert the twin row.** This covers both outcomes: replay and 409.
- **Lookup-order cards: replay on a paid / locked / no-longer-confirmed invoice, and 404 before 409.**

Not covered at unit level, by design (Deferred): the real two-connection race; the header's 422 for an empty or 101-character key.

## Traceability
Cards 118 · tests 118 (109 functions; K-11…K-16 and K-18…K-20 as `pytest.param(id=…)`) · unmatched: none · duplicate IDs: none.

Marker mismatches: none. 65 `pass` cards have no marker. 53 `xfail` cards carry `xfail(strict=True)` with a reason naming exactly the card's bug: BUG-600, 601, 603, 606, 607, 608, 609, 611, 2400, 3002, all present in `docs/testing/bugs.md`. The TypeError cards also carry `raises=TypeError` (C-14, V-12, U-09, 38 K cards).

`--runxfail`: 53 failed, each on its card's "Fails today on" line:
- TypeError at the call: the C-14 / V-12 / U-09 / K cards.
- Then 2 assertion: C-15, L-02, V-11, U-08, and K-37 (AttributeError in `col`).
- Then 3 assertion: U-06.
- `DID NOT RAISE` at Then 1: K-30, U-07, D-04, D-05, D-06.
- Then 1 `len(defs)`: K-33.

None fails on setup or import.

## Notes for future work
- **When BUG-3002 lands:**
  - The reference run shows all 46 K cards are satisfiable together; K-31 / K-32 keep passing.
  - K-36 uses fixed ids (profile 910001, invoice 920001). Once it passes, two concurrent runs of this file (parallel mutation shards, other agents) will wait on each other's uncommitted insert. They block; they do not fail.
- **BUG-609:**
  - Mutant #16 and the "pre-read dropped" variant go away.
  - After the fix, the service's own pre-read (R1) becomes the only workspace guard in front of the manager's blanket 400, if the manager refuses before it looks the payment up. Keep D-02 / D-03 when fixing.
- **No cross-workspace links:** V-08 builds a W1 payment on a W2 invoice. The card names it invalid data, used only to reach the manager's "invoice missing" 404. That matches the rule that such links are invalid data.
- **PR-01:** the identity map returns the same object to the re-read, so "the passed-in object" and "the re-read row" cannot be told apart here (`autoflush=False`, no `populate_existing`). This is harmless, so it is not a finding.

## Commands run
```
.venv/Scripts/python.exe -m pytest tests/unit/services/test_invoice_payment_service.py -q -p no:cacheprovider -o addopts="" --cov=app.services.invoice_payment_service --cov-branch --cov-report=term-missing
  app\services\invoice_payment_service.py  69  1  6  1  97%  50
  65 passed, 53 xfailed, 19 warnings in 18.90s
.venv/Scripts/python.exe -m pytest tests/unit/services/test_invoice_payment_service.py -q -p no:cacheprovider -o addopts="" --runxfail -rf
  53 failed, 65 passed, 4 warnings in 9.77s
  (again with a scratch plugin mapping each failure to its `# Then N` block: 53 failed, 65 passed in 11.04s)
.venv/Scripts/python.exe -m pytest tests/unit/services/test_invoice_payment_service.py -q -p no:cacheprovider -o addopts=""   # run 2
  65 passed, 53 xfailed, 4 warnings in 9.45s
.venv/Scripts/python.exe -m pytest tests/unit/services/test_invoice_payment_service.py -q -p no:cacheprovider -o addopts=""   # run 3
  65 passed, 53 xfailed, 4 warnings in 12.01s
.venv/Scripts/python.exe -m pytest … --collect-only -p markplug   # traceability (scratch plugin)
  118 tests collected
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/services/invoice_payment_service.py tests/unit/services/test_invoice_payment_service.py --timeout 300 --json <scratch>/mutate.json
  Mutants: 27 · killed 25 · timeout 0 · survived 2 · score 93%   (raw; 100% after classification)
<scratch>/variants.py orig | ref, <scratch>/variants2.py   # verifier-written variant runners, temp copy of app/tests/alembic
  orig: 42 variants, 39 killed · ref: baseline 46 passed, 31 variants killed · ref2: control 46 passed, 11 variants killed
ruff check / ruff format --check on the test file: clean
```
Scratch (COVERAGE_FILE and every artifact): `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\svc1v\invoice_payment\`.

## Round 2 — 2026-11-22

> **Verdict:** PASS
> Tests: 66 passed · 53 xfailed (reproduced ✅, 3 runs identical) · coverage 97% branch (line 50 only) · Cases revision: 3 · Source commit: e48a092
> Re-run variants: 3 · killed 1 · equivalent 2 (no full mutation re-run, as asked; round-1 mutation score 100% stands)

**Scope:** cases revision 3 adds IPS-G-08, which closes Finding 1. No other card changed.

**Fidelity of G-08:**
- G-08 is faithful to its card.
- The Given rows are reproduced exactly: P = TW(I1) is committed; after the commit point, Y is added and not flushed, and A1 is renamed in memory only.
- The When runs inside the **spies**.
- All five Then lines are asserted in card order, with exact values: `result.id`, `created_by_name == U2.name`, `cm.call_count == 0`, `rb.call_count == 0`, `Y in db.new`, `A1 in db.dirty`.
- There is no marker, which is right for a `pass` card. No extra mocks.
- The file grew only by this test (about 0.8 KB).
- The `--runxfail` failure map matches round 1 exactly (53 failures, same test, same Then line, same exception type), so no other test changed behaviour.

**Traceability:** cards 119 · tests 119 · unmatched: none · marker mismatches: none.

**Re-run of the round-1 survivors** (same runner, temp copy, `-m "not xfail"`):

| Variant | Result | Class |
|---|---|---|
| TC6 `get_payment` commits on the found path | **killed** by G-08 | — (Finding 1 closed) |
| HR-16: `delete_payment` pre-read uses the payment's own workspace | survived (66 passed) | equivalent — the manager's own workspace-filtered lookup raises the identical 404 (spec Q2); D-02 / D-03 still get 404 |
| `delete_payment` pre-read dropped | survived (66 passed) | equivalent (Q2); the successful-delete path it would break is BUG-609 (bug-path) |

**Open items:** none for any stage. The future-work note in round 1 still applies: after BUG-609, keep D-02 and D-03, because the service's pre-read may become the only workspace guard.

**Commands run:**
```
pytest … --collect-only -p markplug + trace2.py      → 119 tests collected · tests 119 cards 119 · extra set()
pytest … --cov=app.services.invoice_payment_service --cov-branch (×3)
  → 66 passed, 53 xfailed in 17.43s / 19.10s / 19.43s · 97%, missing 50
pytest … --runxfail -p failplug                      → 53 failed, 66 passed in 9.63s · same failure map as round 1: True
<scratch>/variants_r2.py                             → TC6 get commits: 1 failed (G-08) · the 2 delete pre-read variants: 66 passed
```
Scratch and COVERAGE_FILE: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\svc1v\invoice_payment\`.
