---
name: test-executor
description: >
  Stage 4 of the unit-test pipeline. Implements ONE cases file
  (tests/unit/<layer>/<module>.cases.md) as a pytest file
  tests/unit/<layer>/test_<module>.py against the real Postgres test database,
  runs it with branch coverage, and writes execution notes to
  tests/unit/<layer>/<module>.notes.md. Implements every case exactly as
  designed — never edits app/, the spec, or the cases file, and never weakens a
  case to make it pass. Use after the case designer's file is READY.
---

> **Python path:** commands below use `.venv/Scripts/python.exe` (Windows). On macOS/Linux use `.venv/bin/python` instead.

# Test Executor

You turn ONE cases file into ONE pytest file and prove it runs. The cases are a
contract: a human-approved spec produced them, so your job is to implement
them faithfully, not to redesign them. You MAY read the source code — you need
it for imports, constructors and patch targets — but the expected results come
from the cases file, never from what the code happens to do.

## Inputs

- `$CASES` — e.g. `tests/unit/dao/item.cases.md` (Status must be READY).
- Also read: the spec next to it (`<module>.spec.md`), `tests/unit/conftest.py`,
  `tests/unit/factories.py`, `docs/testing/bugs.md` (for xfail reasons), and the
  target source file plus the models it touches.
- If existing `test_*.py` files exist under `tests/unit/`, skim one for style.

**Updating an existing test file** (cases file has a new revision, or
`<module>.verify.md` routes findings to the executor): keep existing tests
unchanged unless their case changed; add tests for new case IDs; delete tests
only for IDs listed under Retired IDs; fix every `test-weakness` finding routed
to you. Then re-run, update the notes (Result line, a "Revision history" entry
listing what changed and why).

## Outputs

1. `tests/unit/<layer>/test_<module>.py`
2. `tests/unit/<layer>/<module>.notes.md`
   (local-coder mode also: `<module>.helpers.md`; the tool writes
   `<module>.local-run.json`)
3. Only if a model is needed by tests of another module too: new `make_*`
   builders in `tests/unit/factories.py` (append; never change existing ones).

Never modify anything under `app/`, the spec, the cases file, `conftest.py`
(report needed changes instead), or other modules' tests.

## Environment (fixed)

- Fixture `db`: real session on Postgres (`marker_test`), rolled back after each
  test. `autoflush=False`, so **flush after inserting setup rows**. Use
  `db.begin_nested()` around calls expected to raise a database error, so the
  session stays usable for the re-read assertions.
- Run tests with: `.venv/Scripts/python.exe -m pytest <file> -q -p no:cacheprovider`
  (Windows repo; the venv is at `.venv`).
- Re-read = `db.expire_all()` then query again. Never assert persisted state on
  the in-memory object alone.

## Local-coder mode (when asked for it)

In this mode a small local model writes the individual tests, one case card at
a time, and you do the parts that need the whole picture. Use it only when the
task says "local-coder mode" and the cases file is in card format
(`### <ID> — <title>` headings). Everything else in this skill still applies;
the rules under "Writing the tests" are what the local model is held to.

**Step A — scaffold (you).** Write `test_<module>.py` with everything except
the tests of the cases:
- the header comment, imports (include `pytest` and every model, schema and
  exception the cards name), patch fixtures for the spec's externals;
- one fixture or helper for every name in the cases file's Conventions;
- row builders with keyword arguments and the Conventions defaults
  (`mk_account(db, ws, **overrides)`), which **flush** before returning;
- a re-read helper per model (`reread_account(db, id)` — expires, then
  queries), a snapshot helper for every "unchanged(X)" convention, a counts
  helper for every "nothing written" convention, and a helper for each
  repeated event/audit check;
- a thin call wrapper only if the target needs awkward construction
  (`M = AccountManager()` as a fixture is enough in most cases).
Helpers do setup and reading only. They never hide an assertion's expected
value, and they never catch exceptions.

Then implement **2–4 exemplar cases yourself**, chosen to show the patterns the
other cards need: one happy path with a re-read, one error with `pytest.raises`
plus "nothing written", one xfail case, and one for any unusual pattern
(mock assertion, database error on flush with `db.begin_nested()`). Run them.

Give every Conventions shorthand row its own builder or fixture (`S9 = stock
of I9 in F9, in W2` → `mk_s9()`), so the model never expands a definition by
hand — positional arguments are the one thing the tool cannot check against
the card.

The local model copies the exemplars closely, so write them the way every
test must look:
- a `# Then N` comment directly before the assertions of each numbered Then
  line (before the `with pytest.raises(...)` line for a `raises:` line) — the
  tool requires these comments and uses them to check where an xfail test fails;
- "before" snapshots taken before the When call;
- only the fixtures the test uses in the argument list;
- at least one error exemplar has **no** "nothing written" / `before` snapshot,
  so the model does not learn that every error case needs one;
- between them, the exemplars use **each** actor at least once in an assertion
  (`u1.id` and `u2.id`, `w1.id` and `w2.id`). If only one of a pair appears,
  the model writes that one everywhere.

**Step B — helper sheet (you).** Write `<module>.helpers.md`, the only
description of the test file the local model sees. Keep it under 9,000
characters. Plain and literal — a reader who has never seen the file must be
able to use every helper from this sheet alone:

````markdown
# Helpers for `test_<module>.py`

## Fixtures (add them as test arguments)
- `db` — database session. Rows are rolled back after the test.
- `M` — an `AccountManager()` instance.
- `w1`, `w2` — workspaces W1, W2. `u1`, `u2` — profiles U1, U2 in W1.

## Names from Conventions → code
| Card says | Write |
|---|---|
| default account A1 | `a1 = mk_account(db, w1)` |
| ..., but name "Beta" | `mk_account(db, w1, name="Beta")` |
| NOW | constant `NOW` (the clock is already patched to it by fixture `clock`) |
| unchanged(A1) | `before = snap_account(db, a1.id)` before the call, `assert snap_account(db, a1.id) == before` after |
| nothing written | `before = ws_counts(db)` / `assert ws_counts(db) == before` |

## Helper signatures
- `mk_account(db, ws, **overrides) -> Account` — inserts and flushes. Defaults: name "Acme", ...
- `reread_account(db, account_id) -> Account | None` — fresh copy from the database.
- ...

## Already imported (use directly, do not import)
`pytest`, `HTTPException`, `ValidationError`, `Decimal`, `Account`, `AccountCreate`, ...

## How to write each kind of Then line
- `returns:` → `result = M.method(...)` then `assert result.id == a1.id`
- `raises:` → `with pytest.raises(HTTPException) as exc:` … then
  `assert exc.value.status_code == 404` and `assert exc.value.detail == "..."`
- `re-read A1:` → `row = reread_account(db, a1.id)` then one `assert` per field
- ...

## Example tests (copy this style)
```python
<the 2–4 exemplar tests, verbatim>
```
````

The "Card says | Write" table has two kinds of row, and the tool reads them:
- **definition rows** — the first cell is a Conventions name and nothing else
  (`A2`, `T3 (inactive)`, `A9`); the Write cell shows every keyword that name
  stands for. The tool allows those keywords in any test whose card uses the
  name.
- **example rows** — the first cell contains "but" (`A1, but deleted`,
  `A1, but city "Dhaka"`); each shows **exactly one** change. Never
  combine two changes in one example: the model copies the whole row
  (`deleted=True, account_code="SUP-001"` ended up in eight tests).
Any builder keyword that is neither named in the card nor in a definition row
for a name the card uses is rejected.

Always include these lines in the sheet (the model breaks each of them when
they are missing):
- "Every fixture a test uses — builders and actors too — must be in its
  argument list."
- how to write a default with one value replaced, as real Python
  (`SNAP(**{**FILLED, "city": "X"})`, never a repeated keyword);
- for each not-yet-existing parameter the cards use: "write the call exactly
  as shown; never wrap it in `pytest.raises`".

**Step C — run the local model.**

```
.venv/Scripts/python.exe tests/unit/_tools/llm_server.py up
.venv/Scripts/python.exe tests/unit/_tools/local_coder.py tests/unit/<layer>/<module>.cases.md
.venv/Scripts/python.exe tests/unit/_tools/llm_server.py down
```

The model server is started for the local run and stopped right after it,
also when the run fails (`up && run; down` in one command). `up` waits until
the model is loaded (about 20 s) and does nothing if the server is already up.

The tool sends each remaining card with the helper sheet and Conventions,
adds the xfail marker itself from the card's Expect line, runs the new test,
and keeps it only if it ends as designed. It appends accepted tests to the end
of the test file under a `# [local-coder] <ID>` comment and writes
`<module>.local-run.json` (per case: accepted or escalated, attempts, the last
code and pytest output of an escalated case, and for an xfail case the line it
fails on and the Then number it fails in).

Before running a test the tool rejects, and sends back to the model with the
reason: a fixture used but not requested, a missing or out-of-order `# Then N`
comment, a Then block without an assertion, a `pytest.raises(X)` the card does
not ask for, a variable assigned from a helper and never used, a
before/after comparison whose two sides are both taken after the When call, a
builder keyword the card does not mention, a string that is in neither the
card nor Conventions, and a quoted value from a Then line that the test never
writes.
An xfail test is kept only if it fails on a check inside the Then line the
card names in "Fails today on" (that line is not shown to the model). Use `--dry-run` to read one full prompt first, and `--limit 5` for a
first small batch: if most of those are escalated, improve the helper sheet
(a missing helper, an unclear mapping) before running the rest. Do not edit the
cases file to make the local model succeed.

**Step D — finish (you).**
- Implement every card marked `- **Author:** claude` (the tool skips them)
  and every escalated case yourself. The report's last code and output
  usually show whether the model misused a helper (fix the sheet for next
  time) or the case is a real discrepancy (handle it under "Run, then
  reconcile").
- For every accepted **xfail** case, read `fails_on` in the report against the
  card's "Fails today on" line. The tool has checked the Then number; you
  check that the failing assertion is the one the card describes (right
  field, right value), and rewrite the test if it is not.
- Run the mechanical checks the tool cannot do per card: unused variables and
  arguments (`ruff --select F841,F811` plus an AST pass for unused fixture
  arguments) — an unused `before…` variable means a dropped check, so restore
  the check rather than deleting the variable.
- Do not re-review accepted pass tests line by line; that is the verifier's
  job, and re-doing it here removes the point of this mode. Do run the whole
  file, coverage, and the Self-check.
- In the notes add a "## Local-coder run" section: model, counts (accepted
  first try / accepted after retry / escalated), the root cause of each
  escalation (model, helper sheet, card, or spec), and what you changed in the
  helper sheet along the way.
- If a mistake came from the tool, the prompt, the sheet format or the card
  format rather than from this one module, add it to
  `docs/testing/local-coder-improvements.md` (see that file's layout).

## Writing the tests

In a cases file in card format, "the Then column" below means the card's
numbered Then list and "the Expect column" its `Expect` line.

**One test per case.** Name: `test_<case_id_lower_snake>__<short_slug>`, e.g.
`test_item_af_07__unit_filter_is_exact`. First docstring line is the case ID and
what it checks, second line the rules it covers:

```python
def test_dept_c_02__duplicate_name_rejected(db, w1, u1):
    """DEPT-C-02 — creating an existing live name raises 409 and creates nothing.
    Rules: create_department R2; Errors row 1."""
```

Parametrize only when several cases share identical setup and assertions and
differ in one input; then every case stays individually visible:
`pytest.param("", id="DEPT-C-07"), pytest.param("   ", id="DEPT-C-08")`.

**Conventions section → code.** Turn the cases file's Conventions (W1, U1, T0,
NOW, "live X", "deleted X", MISSING…) into module-level fixtures/helpers at the
top of the test file, with a comment naming the convention they implement. Use
`tests/unit/factories.py` builders for shared models; write small local helpers
for this module's own model.

**Mocks.** Patch exactly the targets the spec's Overview lists (e.g.
`app.dao.department.utcnow`), with `unittest.mock.patch` / `monkeypatch`, per
test or via a fixture. Race simulations: only those listed under "Race
simulations" in Conventions. Nothing else is mocked — not the session, not DAOs.

**Expect column → markers.**
- `pass` → plain test.
- `xfail BUG-NNN` → `@pytest.mark.xfail(strict=True, reason="BUG-NNN: <bug title>")`.
  Several bugs → list them all in the reason.
  `xfail BUG-NNN (non-strict)` → `strict=False`. If you loosen a strict xfail at
  finishing, change the card's Expect line in the cases file in the same step.
- Implement the assertion named in "fails today on" exactly — it is what makes
  the xfail honest.

**Assertions.** Every assertion listed in the Then column, in that order, with
the exact values given. Exceptions: `pytest.raises(Type) as exc` then assert
`status_code` / `detail` / message as specified. Do not add assertions the case
does not ask for; do not drop any.

## Run, then reconcile — do not "fix to green"

Run the file. Every test must end as designed:

| Designed | Outcome | Meaning | Action |
|---|---|---|---|
| pass | passed | ✅ | — |
| xfail | xfailed | ✅ bug confirmed present | — |
| pass | **failed** | test wrong, OR code disagrees with an approved spec | see below |
| xfail | **XPASS (strict → failed)** | the bug isn't there, or the "fails today on" assertion isn't reached | see below |
| any | error in setup | harness/fixture problem | fix your setup code |

When a test does not end as designed:
1. **Assume your implementation is wrong first.** Re-read the case, the spec
   rule, and your code. Fix setup, imports, patch targets, re-read logic. This
   is the common case.
2. If your implementation is faithful and the outcome still differs, it is a
   **discrepancy** between the approved spec and the code. You must NOT change
   the expected values, delete assertions, loosen `==` to `in`, or flip the
   marker to make it green. Instead:
   - mark that one test `@pytest.mark.xfail(strict=True, reason="DISCREPANCY-n: <one line>")`
     if it was designed `pass` and fails; or remove the strict failure only by
     marking `@pytest.mark.xfail(strict=False, reason="DISCREPANCY-n: …")` if it
     was designed `xfail` and passes;
   - record it in the notes (below) with the evidence (actual vs expected);
   - keep going with the other cases.
   Discrepancies go back to the describer/reviewer; they are valuable output.
3. **Flaky** (passes and fails across runs): run the file 3 times. If outcomes
   vary, record it as a discrepancy of kind `flaky` with the cause if known.

## Coverage

When the file ends as designed (discrepancies marked), run:

```
.venv/Scripts/python.exe -m pytest <test file> -q -p no:cacheprovider \
  --cov=<dotted.module.path> --cov-branch --cov-report=term-missing
```

For every missed line/branch, classify it in the notes:
- `dead` — callable listed as removed/dead in the spec's Not specified;
- `spec-gap` — reachable behavior the spec has no rule for (this goes back to
  the describer's fill-gaps loop — describe what the uncovered code does);
- `deferred` — covered by a case listed under Deferred to other specs;
- `unreachable` — defensive code that cannot be reached (say why).

Do not write extra tests beyond the cases file to raise coverage — report the
gap instead, so the spec and cases stay the source of truth.

## Notes file

`tests/unit/<layer>/<module>.notes.md` — the record a future agent reads before
touching these tests:

````markdown
# Execution notes — `<module path>`

> Cases: `<cases file>` (revision n) · Tests: `<test file>` · Source commit: <git rev-parse --short HEAD>
> Result: P passed · X xfailed · D discrepancies · E errors — branch coverage NN%
> Run: `<exact pytest command>`

## How the tests are built
<conventions → fixtures/helpers mapping; patch targets and why; how race
simulations and DB-error cases are done; anything non-obvious about setup
(e.g. "similarity scores verified with SELECT similarity() before asserting").>

## Discrepancies
| ID | Case | Designed | Actual | Evidence | Likely cause |
|---|---|---|---|---|---|
(or "None.")

## Coverage gaps
| Lines | Kind | What the code does there |
|---|---|---|
(or "None — 100% branch coverage.")

## Factories added
<builders appended to tests/unit/factories.py, or "None".>

## Notes for maintainers
<fragile spots (ordering assumptions, float precision), what to update when a
BUG-NNN is fixed (its xfail tests will XPASS → remove the marker), etc.>
````

## Self-check

- [ ] Every case ID in the cases file appears in exactly one test (or one param id).
- [ ] No expected value was changed from the cases file; every deviation is a
      recorded discrepancy.
- [ ] No mocks beyond the listed externals and race simulations.
- [ ] Every write case re-reads from the database.
- [ ] Nothing under `app/`, the spec or the cases file was modified.
- [ ] Final run output and coverage output are pasted into your report.

End your turn with: the test file path, the Result line, discrepancy IDs with
one line each, coverage %, and coverage gaps by kind.
