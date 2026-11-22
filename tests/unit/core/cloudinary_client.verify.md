# Verification — `app/core/cloudinary_client.py`

> **Verdict:** PASS
> Tests: 52 passed · 0 xfailed (reproduced ✅; `--runxfail` gives 52 passed, as expected with no xfail markers) · coverage 100% branch (43 stmts, 10 branches)
> Mutation: 46 mutants · 45 killed · 1 survived → score 100% (after excluding 1 equivalent, 0 dead, 0 bug-path)
> Source commit: e48a092 · Cases revision: 3

## Summary
This is an independent re-verify against cases revision 3. Revision 3 changed no cases, and the test file is the same one that passed at revision 2. These tests can be trusted:
- All 52 cases are implemented faithfully.
- The runs reproduce the notes' Result line (52 passed, 100% branch), and three runs gave the same outcome, so nothing is flaky.
- Mutation testing killed every mutant that could change behavior. The one survivor (`"secure"` option key) is equivalent, as in the previous rounds.

Nothing has to change.

## Findings
None.

Fidelity was checked for all 52 cases against their Given / When / Then:
- URLs, signatures and the bound SDK arguments are compared with exact `==` (via `inspect.signature(...).bind` on the original SDK function), so extra keys would fail.
- Returned responses and propagated exceptions are checked with `is`.
- "Config unchanged" is compared against `PREV` (including `secure=False`), and "config set" asserts `secure is True`.
- The only mocks are the four SDK externals the spec lists (`api.resource`, `api.update`, `uploader.destroy`, `uploader.rename`). The default fakes raise when called. `api_sign_request` and `cloudinary_url` are real.
- There is no `try/except`, and every `pytest.raises` names the specific exception type from the case.
- No database is involved, and no write case needs a DB re-read. This matches the spec Overview.

Cosmetic, not a finding: the test module docstring still says "cases.md (revision 2)". Cases revision 3 made no case changes, so the tests are still correct.

## Surviving mutants
| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 34 | L72 | `"secure": True` key → `"": True` in `options` | equivalent | `_ensure_configured()` always runs first (L65) and sets the SDK global `secure=True`; the L27 `True -> False` mutant is killed, which proves the global is observed. Without the option, `cloudinary_url` falls back to `config().secure`, so the URL is still `https://`. The stray `""` option does not change the URL either, because every exact-URL assertion still passed. No non-secure global config can appear between the two statements. | — |

## Traceability
- Cases: 52 (52 unique IDs). Test items: 52 (48 test functions; CLD-ENS-02..06 are one parametrized test with `pytest.param(id=…)`).
- Unmatched: none. An AST scan (function body plus decorators) found every case ID in exactly one test and no test function without a case ID.
- Marker mismatches: none. All 52 cases are `pass`, and the file has no xfail markers. No BUG IDs are used, so there is nothing to check in `bugs.md`.

## Commands run
```
.venv/Scripts/python.exe -m pytest tests/unit/core/test_cloudinary_client.py -q -p no:cacheprovider --cov=app.core.cloudinary_client --cov-branch --cov-report=term-missing
  app\core\cloudinary_client.py      43      0     10      0   100%
  52 passed in 0.80s
.venv/Scripts/python.exe -m pytest tests/unit/core/test_cloudinary_client.py -q -p no:cacheprovider --runxfail -rf
  52 passed in 0.35s
.venv/Scripts/python.exe -m pytest tests/unit/core/test_cloudinary_client.py -q -p no:cacheprovider   (x2)
  52 passed in 0.33s
  52 passed in 0.31s
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/core/cloudinary_client.py tests/unit/core/test_cloudinary_client.py --timeout 180 --json <system temp>/verify_cloud/mut.json
  Mutants: 46 · killed 45 · timeout 0 · survived 1 · score 98%
  SURVIVED #34 L72:8 const: 'secure' -> ''
```
