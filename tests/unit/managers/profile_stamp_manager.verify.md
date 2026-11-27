# Verification — `app/managers/profile_stamp_manager.py`

> **Current verdict (round 3, 2026-11-04):** PASS — 59 passed · 44 xfailed · 100% branch · mutation 57/57 · every hand variant caught
> **Round 2 verdict:** NEEDS WORK (minor) — one minted-form variant (`$` accepting a trailing newline) survived
> **Round 1 verdict:** NEEDS WORK
> Tests: 59 passed · 25 xfailed (reproduced ✅, all strict, each on its card's line) · coverage 100% branch
> Mutation: 57 mutants · 57 killed · 0 survived → score 100% (after excluding 0 equivalent, 0 dead, 0 bug-path)
> Hand variants (BUG-1864/1865/1866 fix shapes, in memory): 18 run · 15 caught · 3 survive (1 finding, 1 minor finding, 1 allowed by the spec)
> Source commit: e48a092 · Cases revision: 1

## Summary
The tests are faithful. All 84 cards are implemented, 17 of them as `pytest.param` ids. Assertions are
exact. Only the spec's named targets are patched: `destroy_resource`, `generate_upload_signature` (SG-01,
SG-02, SG-06), `time.time` and `uuid.uuid4` at `app.managers.profile_stamp_manager.*`, plus settings
through `monkeypatch`. Runs match the notes, and every mutant is killed.

The prefix cards (OQ-11) catch every loose check that was tried:
- `startswith` on a shorter prefix (`…/profiles/5` lets in 55)
- folder only, without `stamp-`
- case-insensitive compare
- prefix found in the middle
- stripping spaces first
- the production form everywhere
- `ENVIRONMENT` read instead of `CLOUDINARY_UPLOAD_ENV`
- deleting before validating
- a delete check placed after the call

The url rule (OQ-12) has one gap. A fix that keeps the client's `url` whenever it "looks like Cloudinary"
passes VS-35, because VS-35 only tries a non-Cloudinary tracker url. One more card is needed (case designer).

## Findings
| # | Kind | Case / line | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing (security, OQ-12) | `validate_saved_stamp_payload` R4b; next to PSM-VS-35 | VS-35 sends only `https://tracker.example/p.png`. A fix that keeps a client `url` starting with `https://res.cloudinary.com/` (any cloud, any file) passes every card. The owner's answer is that the client `url` is always ignored. Another cloud's url leaks viewers' IP addresses just as the tracker does, and a url in our own cloud can point at a different file than the `public_id`. | Variant `client_url_if_cloudinary`: 60 passed (same as the reference fix) | case designer: a VS-35 sibling with client `url` `"https://res.cloudinary.com/other-cloud/image/upload/x.png"`, and one with `"https://res.cloudinary.com/demo-cloud/image/upload/ws-12/9f2c.png"`. Then: the result's url starts with `https://res.cloudinary.com/demo-cloud/image/authenticated/`, contains OWN5, and does not contain `other-cloud` / `ws-12`. |
| 2 | case-missing (minor) | `destroy_saved_stamp_image` R4a | VS-31 (`stamp` without the dash) has no DS twin. A delete check written with the prefix `…/profiles/5/stamp` (no dash) is caught only on the validate side. The DS cards cover every other VS shape. | Variant `no_dash`: only VS-31 failed; no DS card did | case designer: DS card `IMG("development/profiles/5/stamp" + TOKEN), user_id=5` → `dr.call_count == 0` |
| 3 | spec-gap (open, raised by the case designer) | `validate_saved_stamp_payload` R4a, cases gap 3 | The spec does not say whether a `public_id` equal to the bare prefix, or with a non-hex or over-long suffix, is accepted. A stricter fix (`fullmatch(prefix + [0-9a-f]{32})`) and the plain `startswith` both pass. Recommendation for the describer: require the exact minted form `prefix + 32 lowercase hex`. It costs nothing, since the server mints every id, and it closes any suffix tricks (`…/stamp-x/../…`, the empty token). | Variant `endswith_token`: 60 passed; reference `startswith`: 60 passed | describer (fill-gaps, gap 3); then case designer |

No fidelity findings. Checked against every card:
- Every refusal asserts the exact type (`type(exc.value) is ValueError`), the message, and that the payload is unchanged.
- VS-22 and VS-27 also assert `dr.call_count == 0`.
- DS-17 … DS-24 assert `result is None` and `dr.call_count == 0`.
- DS-13 asserts one WARNING carrying the `public_id` and the error text.
- The xfail cards pass `user_id=` as the spec says, and `raises` is not narrowed.
- The patches live for the whole test rather than around the When only. This is equivalent here, because the When is the only call of each patched function.

## Surviving mutants
None (57/57 killed).

### Hand variants of the fixes (scratch plugin `psm_variants.py`, BUG-1713 logging included in each; run with `--runxfail -k "ds_ or vs_"`)
| Variant | Caught by |
|---|---|
| reference (`startswith(<env>/profiles/<id>/stamp-)`, url built from `public_id`, foreign delete skipped) | — (60 passed) |
| prefix `…/profiles/<id>` without the slash (`profiles/5` matches `profiles/55`) | DS-17, DS-24, VS-22, VS-24, VS-31 |
| prefix `…/profiles/<id>/` (any file of the folder) | DS-24, VS-24, VS-31 |
| prefix `…/stamp` without the dash | VS-31 only (finding 2) |
| production form in every environment | DS-16, DS-20, VS-21, VS-25, VS-34, VS-35 |
| `ENVIRONMENT` instead of the upload environment | VS-32, VS-33 |
| case-insensitive compare | DS-21, VS-28 |
| prefix anywhere (`in`) | DS-22, DS-23, VS-29, VS-30, VS-33 |
| `strip()` before the compare | DS-22, VS-29 |
| stricter: whole id = prefix + 32 hex | **passes** (finding 3, spec gap) |
| client `url` returned as sent | VS-35 |
| client `url` kept when it starts with `https://res.cloudinary.com/` | **survives** (finding 1) |
| url built with delivery type `upload` | VS-35 |
| url built without the `public_id` | VS-35 |
| validate deletes the file before checking | VS-22, VS-27 |
| validate never checks the prefix | VS-22 … VS-31, VS-33 |
| destroy raises on a foreign id instead of skipping | DS-17 … DS-24 |
| destroy deletes first, ignores the prefix | DS-17 … DS-24 |

## Traceability
cases 84 · tests 84: 67 single-case functions plus 2 parametrized groups of 17 params (69 functions) (DS-17 … 24; VS-23 … 26, 28 … 31, 33). Every case
ID appears exactly once, as a `# [claude]` comment and docstring or `pytest.param(id=…)`. Unmatched: none.
Marker mismatches: none. 25 strict xfails: BUG-1864 ×14, BUG-1865 ×9, BUG-1866, BUG-1713. Each reason
names its BUG ID, and all of them exist in `bugs.md`.

## Commands run
```
.venv/Scripts/python.exe -m pytest tests/unit/managers/test_profile_stamp_manager.py -q -p no:cacheprovider --cov=app.managers.profile_stamp_manager --cov-branch --cov-report=term-missing
  app\managers\profile_stamp_manager.py  55 stmts  0 miss  16 branch  0 brpart  100%
  59 passed, 25 xfailed, 15 warnings (SAWarnings from the coverage re-import)
  repeat runs: 59 passed, 25 xfailed ×2 — stable

.venv/Scripts/python.exe -m pytest tests/unit/managers/test_profile_stamp_manager.py -q -p no:cacheprovider --runxfail -rf --tb=line
  25 failed, 59 passed. DS-13 on Then 2 (`assert 0 == 1`, nothing logged). The 24 others on Then 1 with
  TypeError "unexpected keyword argument 'user_id'" (lines 679, 713 ×8, 1012, 1027, 1071 ×9, 1089, 1107, 1119, 1134)

.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/managers/profile_stamp_manager.py tests/unit/managers/test_profile_stamp_manager.py --json <scratch>/stamp_mut.json
  Mutants: 57 · killed 57 · timeout 0 · survived 0 · score 100%

PYTHONPATH=<scratch> PSM_VARIANT=<v> .venv/Scripts/python.exe -m pytest tests/unit/managers/test_profile_stamp_manager.py -q -p no:cacheprovider -p psm_variants --runxfail -k "ds_ or vs_"
  (scratch = C:\Users\User\AppData\Local\Temp\makorsh-pipeline\oqv; results in the table above)
```

## Round 2 — 2026-11-04
Cases revision 2 (101 cards: 59 pass, 42 xfail). The spec now requires the minted form: the prefix plus exactly 32 lowercase hex characters, and nothing after.

### Fidelity
VS-06 and VS-07 now build `SavedStampImage` directly, as their cards say. The manager is not called, and VS-07 asserts `PydanticValidationError`.

VS-36 and VS-37 assert all four Then lines: the authenticated `demo-cloud` start, `OWN5` in the url, the client's host or file absent, and the result not equal to the client's url.

DS-25 … DS-32 are one parametrized group: `user_id=5`, `result is None`, `dr.call_count == 0`. VS-38 … VS-44 are another: exact `ValueError` type and message, and the payload unchanged. Both groups carry `strict=True` with the right BUG ID. The token constants match the Conventions: TOKEN31, TOKEN33, TOKENU, TOKENG, PRE5.

Traceability: 101 cards, 101 tests (32 of them `pytest.param` ids), no mismatches.

### Variants (scratch `psm_variants.py`, `--runxfail -k "ds_ or vs_"`)
Every result is measured against the reference: `re.fullmatch(re.escape(prefix) + "[0-9a-f]{32}")` → 77 passed.

| Variant | Caught by |
|---|---|
| client url kept when it starts with `https://res.cloudinary.com/` (routed, round-1 finding 1) | VS-36, VS-37 |
| `stamp` without the dash on both sides (routed, round-1 finding 2) | DS-25, VS-31 (plus others) |
| round-1 reference, plain `startswith(prefix)` | DS-26 … DS-32, VS-38 … VS-44 |
| token `{31,33}` | DS-27, DS-28, VS-39, VS-40 |
| token `[0-9a-fA-F]{32}` (upper case allowed) | DS-29, VS-41 |
| token `\w{32}` | DS-29, DS-30, VS-41, VS-42 |
| `startswith(prefix)` plus total length only | DS-29, DS-30, VS-41, VS-42 |
| `fullmatch` with `re.I` | DS-21, DS-29, VS-28, VS-41 |
| `re.match` (no end anchor; suffix allowed) | DS-28, DS-31, DS-32, VS-40, VS-43, VS-44 |
| `re.search` (no anchors) | DS-22, DS-23, DS-28, DS-31, DS-32, VS-29, VS-30, VS-33, VS-40, VS-43, VS-44 |
| **`re.match(prefix + "[0-9a-f]{32}$")`** | **survives**: `$` also matches before a final `\n`, so `OWN5 + "\n"` is accepted and deleted |

### Runs
59 passed, 42 xfailed ×3 (stable). Branch coverage 100%.

`--runxfail`: 42 failed, 59 passed. DS-13 fails on Then 2 (`0 == 1`). The other 41 fail on Then 1 with `TypeError` (unexpected `user_id`), including the new groups at lines 755 (DS-25 … 32) and 1258 (VS-38 … 44) and the VS-36 and VS-37 calls.

Mutation was not re-run, because the source is unchanged (round 1: 57/57).

### Findings
| # | Kind | Case / line | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| R2-1 | case-missing (minor, security) | `validate_saved_stamp_payload` R4a / `destroy_saved_stamp_image` R4a ("nothing after the token") | No card has a trailing newline. A fix written as `re.match(...$)`, a common idiom, accepts `OWN5 + "\n"` and would save or delete that id. The spec already forbids anything after the token, so only cards are missing. | Variant `m_dollar`: 77 passed (same as the reference) | case designer: VS and DS cards with `OWN5 + "\n"` → `ValueError(FOREIGN_MSG)` / `dr.call_count == 0` |
| R2-2 | spec wording (cosmetic) | spec `validate_saved_stamp_payload` R4 (line 178) and `destroy_saved_stamp_image` R4 (line 153) | Both still say "under the user's own stamp prefix", while R4a now requires the exact minted form. The rules agree in substance, but the text does not. | spec text | describer |

Round-1 findings 1, 2 and 3 are closed. Cases gap 2 (is the client `url` still required after BUG-1866?) is still open but does not block. **Verdict: NEEDS WORK (minor):** R2-1 for the case designer, R2-2 for the describer.

## Round 3 — 2026-11-04
Cases revision 3 (103 cards: 59 pass, 44 xfail). The spec wording (R2-2) and cases gap 2 are settled: the client `url` stays required and is ignored.

- **Fidelity:** PSM-DS-33 and PSM-VS-45 (`OWN5 + "\n"`) are new `pytest.param` ids in the existing DS-25 … 33 and VS-38 … 45 groups. Their bodies match the cards:
  - DS-33: `user_id=5`, `result is None`, `dr.call_count == 0`.
  - VS-45: exact `ValueError` type and `FOREIGN_MSG`, payload unchanged.
  - Both are strict xfails for BUG-1865 and BUG-1864.
  - Traceability: 103 cards, 103 tests (34 param ids), no mismatches.
- **Variant:** `re.match(prefix + "[0-9a-f]{32}$")` (`m_dollar`) is now caught by DS-33 and VS-45. The `fullmatch` reference passes 79 of 79 DS and VS tests.
- **Runs:** 59 passed, 44 xfailed ×3 (stable). Under `--runxfail` the two new tests fail on Then 1 with `TypeError` (unexpected `user_id`), at lines 757 and 1262.
- **Mutation:** not re-run, because the source is unchanged (57/57).
- **Findings:** none. R2-1 and R2-2 are closed. **Verdict: PASS.**
