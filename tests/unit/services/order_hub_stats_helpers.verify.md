# Verification — `app/services/order_hub_stats_helpers.py`

> **Current verdict (Round 2, 2026-11-04):** PASS. Finding 1 is closed (cases revision 2). Hand variants: 74 · 70 caught · 4 equivalent. See `## Round 2 — 2026-11-04` at the end.

> **Verdict (round 1):** NEEDS WORK
> Tests: 19 passed · 0 xfailed (nothing to reproduce) · coverage 100% branch (14 statements, 0 branches counted)
> Mutation: 5 mutants · 5 killed · 0 survived → score 100% (after excluding 0 equivalent, 0 dead, 0 bug-path)
> Fidelity: **0 of 19 unfaithful** (19 / 19 right; read by eye against every card)
> Hand variants: 74 (+1 no-op guard) · 67 caught by a pass card · 7 others: 4 equivalent, 3 case-missing (one finding)
> Source commit: e48a092 · Cases revision: 1; spec APPROVED (revision 2026-11-04, fill-gaps)

## Summary
- **The tests are faithful to their cards**, and they catch nearly every break I tried: every field copied from the wrong source, every missing field, every extra field, and both sides of each `status.name if status else None`.
- **Both sides of the status conditionals are asserted**, although coverage.py does not count them as branches: P-01 `status_name == "Draft"` and P-03 `is None`; T-01 `== "In Transit"` and T-03 `is None`. Hand variants prove it: always `None` fails P-01 / T-01; `''` in place of `None` fails P-03 / T-03; no guard fails P-03 … P-06 / T-03 … T-05.
- **One gap, for the case designer: money scale is never checked.** P-01 and E-01 check `total_amount` with `==` and `isinstance(Decimal)`. `Decimal("1234.5") == Decimal("1234.50")`, so the money can be **rounded to one decimal** or **sent through `float`** and every test still passes. Either change is visible to the client: the JSON shows `"1234.5"` in place of `"1234.50"`. The spec forbids it (Review, HR-15: "passed through as the `Decimal` it is; nothing is rounded"; R1: "the order's own values").
- `mutate.py` makes only 5 mutants here (4 × `return None`, `status_id` 0 → 1), all killed. The hand variants carry the verdict.

Written by Claude (all 19 under `# [claude]`). Findings in local-written tests / local-written tests: 0 / 0. In others: 0 / 19. No `order_hub_stats_helpers.local-run.json` exists, so there is no `## Local-coder patterns` section.

## Findings
| # | Kind | Case / line | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing | OHS-P-01 Then 6, OHS-E-01 Then 5; source L19, L33 | `total_amount` is checked by value only. A mapper that rounds money to 0.1 or passes it through `float` loses the scale (`1234.50` → `1234.5`, also in the JSON) and passes every card. Spec Review HR-15 and R1 say the Decimal is passed through unchanged. | Variants `p_total_quantize1`, `p_total_float`, `e_total_float`: `19 passed`. Check: `OrderHubRecentSummary(..., total_amount=float(Decimal("1234.50"))).total_amount` is `Decimal('1234.5')`; JSON `"total_amount":"1234.5"`. | **case designer**: add to P-01 Then 6 `str(result.total_amount) == "1234.50"`; give E-01 a value ending in 0 (e.g. `Decimal("99.90")`) and add `str(result.total_amount) == "99.90"`. That catches all three variants (rounding to a whole number is already caught). |

## Surviving mutants
None from `mutate.py`. All 5 are killed with a plain `1 failed` (L10, L24, L42, L55 `return None`: P-01, E-01, T-01, H-01; L27 `0 → 1`: E-01).

## Hand variants
`plug\vplug.py` is a pytest plugin that, before each test, swaps in the module built from one edited copy of today's source and rebinds the names the test file imported. `variants.py` holds the edits; `runvars.py` checks each applies exactly once and changes the source, then runs the whole file. The no-op guard `o_nop` gives `19 passed`.

| Group | Variants | Pass card | Cards that fail | Others |
|---|---|---|---|---|
| purchase: field from the wrong source (`id`, `order_number`, `status_id`, `status_name` from `comment`, `created_at` ↔ `updated_at`, `account_id` ↔ `invoice_id`) | 8 | 8 | OHS-P-01 (+P-03, P-05, P-06 for some) | — |
| purchase: `status_name` always `None` / `''` when no status / no guard | 3 | 3 | P-01; P-03; P-03 … P-06 | — |
| purchase: `status_id` from the loaded status row | 1 | 0 | — | equivalent |
| purchase: `total_amount` rounded to a whole number / to 0.1 / via `float` | 3 | 1 | P-01 (whole number only) | 2 × case-missing (#1) |
| purchase: a field missing (`status_name`, `created_at`, `updated_at`, `account_id`, `invoice_id`, `total_amount`) | 6 | 6 | P-01 (+P-02, P-03 for `created_at`) | — |
| purchase: extra field (`due_date`, `source_location_type`); `model_construct` (no validation) | 3 | 3 | P-02; P-04 … P-06 | — |
| expense: wrong source (`id`, `order_number`, `status_id` = id, `status_name` set, dates swapped, `created_at` ↔ `updated_at`, `account_id` ↔ `invoice_id`) | 10 | 10 | OHS-E-01 (+E-02, E-04 for some) | — |
| expense: `total_amount` rounded / via `float` | 2 | 1 | E-01 (rounded) | 1 × case-missing (#1) |
| expense: a field missing (8 fields) | 8 | 8 | E-01 (+E-02 for `created_at`) | — |
| expense: extra location field (source, destination) | 2 | 2 | E-01 | — |
| transfer: wrong source (`id`, `order_number`, `status_id`, `created_at` ↔ `updated_at`, locations swapped or source from destination) | 7 | 7 | OHS-T-01 (+T-03, T-05 for some) | — |
| transfer: `status_name` always `None` / `''` when no status / no guard | 3 | 3 | T-01; T-03; T-03 … T-05 | — |
| transfer: `status_id` from the loaded status row | 1 | 0 | — | equivalent |
| transfer: a field missing (`status_name`, `created_at`, `updated_at`, source, destination) | 5 | 5 | T-01 (+T-02, T-03 for `created_at`) | — |
| transfer: extra field (`total_amount`, `account_id`) | 2 | 2 | T-02 | — |
| highlight: only required keys, `status_name` or `created_at` dropped, strict mode, `status_name` from `order_number` | 5 | 5 | OHS-H-01 (+H-02, H-03) | — |
| highlight: default `id` / `order_number`; `model_construct` | 3 | 3 | H-03; H-04; H-01, H-03, H-04 | — |
| highlight: `data.get(...)` per field; `model_validate(data)` | 2 | 0 | — | 2 × equivalent |
| **Total** | **74** | **67** | | **7** |

### Considered and not listed
| Variant | Why it is not a finding |
|---|---|
| `p_status_id_from_row`, `t_status_id_from_row` | **Equivalent.** `status_id = status.id if status else order.current_status_id`: `current_status` is the row loaded through `current_status_id`, so the two ids are the same on every order the hub reads (assigning the relationship sets the FK on flush). |
| `h_get_defaults` | **Equivalent.** A missing key gives `None`, which the DTO's default also gives; a missing `id` / `order_number` still fails validation; unknown keys are not passed, which the DTO ignores anyway. |
| `h_model_validate` | **Equivalent.** `model_validate(dict)` and `**dict` validate the same fields the same way for a dict with string keys, which is what the order DAOs return. |

## Reproduced claims
- **Result line of the notes holds:** `19 passed` in 4 of 4 default runs (the coverage run among them), and `19 passed` with `--runxfail`. No flaky test.
- **Mocks:** none, as the Conventions say. No test uses the `db` fixture. No `try`, no `if`, no broad `pytest.raises` (every refusal is `pytest.raises(ValidationError)`, as the cards say).
- "none of (fields)" is one `is None` per field, as the Conventions say. Every Given is built with exactly the card's keyword arguments.

## Traceability
cases 19 · tests 19 · unmatched: none · duplicates: none · marker mismatches: none (all `pass`, no markers). Card order equals file order. Each docstring holds its card's ID, title and Rules; `# Then N` numbers match the card. No BUG IDs used. All sit under `# [claude] <ID>`. `ruff check` passes.

## Limits of this round
- **The variants are mine.** They show what these tests catch around them, not every possible break.
- **Which orders reach the mappers** is decided by the order services and DAOs; not judged here (spec Overview).

## Commands run
```
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/services/order_hub_stats_helpers.py tests/unit/services/test_order_hub_stats_helpers.py --timeout 300 --json <scratch>/res/mut_ohs.json
  [1/5] L10:4 return None KILLED · [2/5] L24:4 return None KILLED · [3/5] L42:4 return None KILLED · [4/5] L55:4 return None KILLED · [5/5] L27:18 const 0 -> 1 KILLED
  Mutants: 5 · killed 5 · timeout 0 · survived 0 · score 100%
.venv/Scripts/python.exe -m pytest tests/unit/services/test_order_hub_stats_helpers.py -q -p no:cacheprovider --cov=app.services.order_hub_stats_helpers --cov-branch --cov-report=term-missing
  19 passed · app\services\order_hub_stats_helpers.py 14 0 0 0 100%
.venv/Scripts/python.exe -m pytest tests/unit/services/test_order_hub_stats_helpers.py -q -p no:cacheprovider --runxfail -rf
  19 passed
pytest, default, 2 more runs                                    19 passed each
trace.py (cards vs tests: IDs, order, markers, patches)         clean
runvars.py (hand variants through plug\vplug.py)                as above
python -c (DTO with float(Decimal("1234.50")))                  Decimal('1234.5'), JSON "1234.5"
.venv/Scripts/python.exe -m ruff check tests/unit/services/test_order_hub_stats_helpers.py   All checks passed!
git diff --stat -- app/services                                 (empty)
```
Scratch: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\svc4v\` (private `COVERAGE_FILE`). Only this report was written in the repo. No commit. Nothing was killed.

## Round 2 — 2026-11-04
Narrow re-check of finding 1 after cases **revision 2** and the matching test update. Nothing else in the file is re-judged.

**Fidelity (2 changed tests vs their cards): 0 unfaithful.**
- OHS-P-01: the Given is unchanged (`Decimal("1234.50")`). New `# Then 7`: `assert str(result.total_amount) == "1234.50"`, exactly as card Then 7. Then 1–6 are unchanged.
- OHS-E-01: the Given is now `total_amount=Decimal("99.90")`, as the card says. Then 5 is now `== Decimal("99.90")`. New `# Then 8`: `assert str(result.total_amount) == "99.90"`, exactly as card Then 8. Then 1–7 are unchanged, and the Then numbering matches the card.

**Variants (same plugin and edits as round 1):**
| Variant | Round 1 | Round 2 |
|---|---|---|
| `o_nop` (guard) | 19 passed | 19 passed |
| `p_total_quantize1` | 19 passed | **1 failed** (OHS-P-01) |
| `p_total_float` | 19 passed | **1 failed** (OHS-P-01) |
| `e_total_float` | 19 passed | **1 failed** (OHS-E-01) |
| `p_total_rounded`, `e_total_rounded` (control) | 1 failed | 1 failed (P-01; E-01) |

The 3 case-missing variants now fail a pass card. Hand-variant totals: 74 · 70 caught · 4 equivalent (unchanged: `p_/t_status_id_from_row`, `h_get_defaults`, `h_model_validate`). The finding is **closed**.

**Runs:** 3 plain runs, `19 passed` each; no flaky test. `ruff check` passes. `git diff -- app/services` is empty. `mutate.py` was not run again: the change only adds assertions, and every round 1 mutant was already killed.

**Current verdict: PASS.** Traceability clean, no fidelity findings, the runs reproduce the notes, and every survivor is equivalent.

Commands (round 2):
```
runvars.py o_nop p_total e_total            as the table above
.venv/Scripts/python.exe -m pytest tests/unit/services/test_order_hub_stats_helpers.py -q -p no:cacheprovider   (x3)   19 passed each
.venv/Scripts/python.exe -m ruff check tests/unit/services/test_order_hub_stats_helpers.py                     All checks passed!
```
Only this report was edited. No commit. Nothing was killed.
