# Handoff: testing the production revamp

Everything in `app/` except production is tested and verified (215 modules,
2026-11-22). This guide is for testing the **production revamp** with the same
pipeline, and then for splitting the bug fixing.

## 1. Set up (once)

1. Merge this branch (`getabidallabib/mak-107-test-checklists`) into your
   production branch, or rebase your branch on it.
2. Install the requirements into `.venv`: `pip install -r requirements.txt`. Python 3.12.
3. Start Postgres 16. For example:
   `docker run -d --name marker-pg -e POSTGRES_PASSWORD=postgres -p 5432:5432 postgres:16`
4. If your Postgres uses other credentials, set
   `TEST_DATABASE_URL=postgresql://<user>:<pw>@localhost:5432/marker_test`.
   The database name must end in `_test`. The tests create and migrate it
   themselves.
5. Your normal `.env` must be present, because the app reads its settings on
   import.

## 2. Baseline run: did the revamp break anything else?

```
python -m pytest tests/unit -o addopts=""
```

This takes about 16 minutes. Add `-n 4` to run on 4 workers, which is faster; CI does this on every PR. Before the revamp the result was **17,994 passed,
5,902 xfailed, 75 xpassed, 1 skipped, 0 failed**.

- **`failed`:** your change altered behaviour that another module's test
  pins. Read the test's card in the matching `.cases.md`. Either your code
  is wrong, or the old rule changed on purpose. If the change was on
  purpose, re-run the pipeline for that module (describer apply-review →
  designer → executor → verifier) instead of editing the test by hand.
- **`XPASS(strict)`:** your change fixed a logged bug. Remove the xfail
  marker and mark the bug fixed in `docs/testing/bugs.md`.
- **Failures in `tests/unit/dao/test_production_*.py`:** expected if you
  changed the production tables. Those DAOs get redone in step 3.

## 3. Test production with the pipeline

Open Claude Code in this repo. It reads `CLAUDE.md`, which holds the rules and
your bug id range (**BUG-5000…5999**).

1. **Settle the design questions first.** `docs/future/production-revamp.md`
   lists BQ1–BQ6, OQ-F1 and O1, plus findings against the old code. Go
   through them with the owner, since they are stock questions, and record
   the answers in `docs/testing/owner-questions.md`. Drop any that the
   revamp made moot.
2. **Production DAOs**, if their code changed: `production_batch`,
   `production_batch_item`, `production_batch_stage_log`,
   `production_formula`, `production_formula_item`,
   `production_formula_stage`, `production_line`. These already PASS
   against the old code. Re-describe only the ones you changed, by running
   the describer in apply-review mode on the existing spec, or describing
   from scratch for a big rewrite.
3. **Managers:** `production_batch_manager`, `production_formula_manager`,
   `production_line_manager`. Their specs in `tests/unit/managers/` were
   drafted on the old code and are PAUSED. **Describe them from scratch.**
   Use the old spec and the revamp notes only as a checklist.
4. **Services:** `production_batch_service`, `production_formula_service`,
   `production_line_service`. These have never been described.
5. Any new production files from the revamp go through the same steps.

Example prompts for Claude:

- One module: "Run the test pipeline on `app/managers/production_line_manager.py`:
  describe, then I'll review, then cases, tests, verify. Bug ids BUG-5000…5049."
- Batch: "use a workflow: run test-pipeline-describe with
  files [...] and root <path to this checkout>". After review, run
  "test-pipeline-run" with one item per spec, each with its own bug block.

A module is done when its `.verify.md` says **PASS**. Finish with a full
suite run, which should show 0 failed.

## 4. Then: final check and bug fixing

1. The owner does a final check of both branches merged together.
2. Split `docs/testing/bugs.md` between the two of you, for example by area
   (each takes whole modules, so two people never fix the same file).
3. For each bug: fix `app/`, remove its xfail marker, run that module's test
   file plus the full suite, and mark the bug fixed in `bugs.md`.
