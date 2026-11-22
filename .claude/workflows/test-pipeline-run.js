export const meta = {
  name: 'test-pipeline-run',
  whenToUse: 'After a describe batch has been reviewed (all Answer lines filled). args.items = [{source, spec, block}] with a unique 20-ID bug block per file.',
  description: 'Run stages 2-5 of the unit-test pipeline (apply-review, case design, gap loop, tests, verify + fix round) for a batch of reviewed specs, then merge bug registers',
  phases: [
    { title: 'Apply review', detail: 'turn reviewer answers into rules; stage bugs', model: 'sonnet' },
    { title: 'Design cases', detail: 'black-box case design + gap loop' },
    { title: 'Write tests', detail: 'executor implements and runs tests', model: 'sonnet' },
    { title: 'Verify', detail: 'traceability, fidelity, mutation testing' },
    { title: 'Fix round', detail: 'route verifier findings back and re-verify once' },
    { title: 'Merge', detail: 'merge staged bugs and dead code into shared registers', model: 'sonnet' },
  ],
}

const ITEMS = args.items   // [{source, spec, block}]
const ROOT = args.root || 'E:\\Projects\\Makorsh-Corp\\backend'   // pass args.root for a checkout elsewhere
const ENV = `Working directory: ${ROOT} (FastAPI + SQLAlchemy backend, Windows; Python venv at .venv; run Python as .venv/Scripts/python.exe). The Postgres test harness (tests/unit/conftest.py, database marker_test) already works.`
const BATCH = `Batch-mode rules (many agents run in parallel on other modules):
- Never modify anything under app/.
- Never edit docs/testing/bugs.md, docs/testing/house-rules.md, docs/testing/dead-code-removal-checklist.md, or tests/unit/factories.py — those are shared files merged later by one agent.
- The reviewer has delegated follow-up decisions to industry best practice: never leave a question pending. When a choice is needed, decide by best practice, mark it "(best-practice default, delegated by reviewer)" in the spec/cases, and list it in your structured result under decisions_made.
- Other agents run tests on the same database concurrently; each test is its own rolled-back transaction, so that is fine.`

const stem = it => it.spec.replace(/\.spec\.md$/, '')

const APPLY = { type: 'object', properties: {
  status: { type: 'string' }, bugs_logged: { type: 'array', items: { type: 'string' } },
  dead_code: { type: 'array', items: { type: 'string' } },
  decisions_made: { type: 'array', items: { type: 'string' } } },
  required: ['status', 'bugs_logged', 'dead_code', 'decisions_made'] }
const DESIGN = { type: 'object', properties: {
  counts: { type: 'string' }, gaps: { type: 'integer' }, gap_titles: { type: 'array', items: { type: 'string' } },
  blocking_gaps: { type: 'integer', description: 'how many open gaps prevent a case from being written at all' },
  decisions_made: { type: 'array', items: { type: 'string' } } },
  required: ['counts', 'gaps', 'gap_titles', 'blocking_gaps', 'decisions_made'] }
const EXEC = { type: 'object', properties: {
  test_file: { type: 'string' }, passed: { type: 'integer' }, xfailed: { type: 'integer' },
  discrepancies: { type: 'array', items: { type: 'string' } }, coverage: { type: 'string' },
  coverage_gaps: { type: 'array', items: { type: 'string' } } },
  required: ['test_file', 'passed', 'xfailed', 'discrepancies', 'coverage', 'coverage_gaps'] }
const VERIFY = { type: 'object', properties: {
  verdict: { type: 'string', description: 'PASS or NEEDS WORK' }, mutation: { type: 'string' },
  findings: { type: 'array', items: { type: 'object', properties: {
    fix_by: { type: 'string', description: 'describer | case designer | executor' }, summary: { type: 'string' } },
    required: ['fix_by', 'summary'] } } },
  required: ['verdict', 'mutation', 'findings'] }

const applyReview = it => agent(`${ENV}

Read .claude/skills/test-describer/SKILL.md in full and follow Mode 2, in mode:

apply-review ${it.spec}

The reviewer's answers are on the **Answer:** lines ("(reviewer accepted suggestion)" = the suggested answer is the reviewer's decision). Also read docs/testing/house-rules.md and docs/testing/bugs.md (for precedents and patterns).

${BATCH}

BUG IDs and bug logging for THIS run (overrides the skill's "log in bugs.md" step):
- Use ONLY IDs from your pre-allocated block BUG-${it.block}..BUG-${it.block + 19}, in order. If an answer says "per BUG-NNN precedent" or the bug is an existing one (e.g. BUG-035 statuses leak, BUG-020, BUG-031), reference that existing ID instead of creating a new one.
- Write your new bug rows (same columns as docs/testing/bugs.md) to ${stem(it)}.bugs-staging.md next to the spec, not to bugs.md.
- Code answered "remove" goes to ${stem(it)}.deadcode-staging.md as checklist lines ("- [ ] \`file:line\` — kind \`name\` — reason — confirmed unreachable in spec review"), not to the shared checklist. If a legacy test in tests/ (outside tests/unit/) exercises removed code, mention that on the line.
- Status must end APPROVED (decide any follow-up by best practice as described above).

Return: final status, bug IDs logged or referenced, dead-code entries, decisions made on the reviewer's behalf.`,
  { label: `apply-review ${it.source}`, phase: 'Apply review', schema: APPLY, model: 'sonnet' })

const design = (it, note) => agent(`${ENV}

Read .claude/skills/test-case-designer/SKILL.md in full and follow it exactly, with:

$SPEC = ${it.spec}

${note || 'First run for this module (if a cases file already exists, treat this as a re-run).'}
Do not open, grep, or read anything under app/ (black-box). Write only the cases file.
${BATCH}

Return: the Counts line, the number of spec gaps and their titles, how many of those gaps BLOCK a case from being written (vs. merely weaken one), decisions made.`,
  { label: `design ${it.source}`, phase: 'Design cases', schema: DESIGN })

const fillGaps = (it, source) => agent(`${ENV}

Read .claude/skills/test-describer/SKILL.md in full and follow Mode 3 (fill-gaps) for the spec ${it.spec}, taking the gaps from ${source}${source.endsWith('verify.md') ? ' (handle only findings whose "Fix by" is the describer / spec-gap)' : ''}.
Do NOT add review questions: decide intent gaps by best practice (see batch rules) and keep the spec APPROVED. New bugs: IDs from BUG-${it.block}..BUG-${it.block + 19} continuing after those already in ${stem(it)}.bugs-staging.md, rows appended to that staging file.
${BATCH}

Return: status, bug IDs logged, dead-code entries (none expected), decisions made.`,
  { label: `fill-gaps ${it.source}`, phase: 'Design cases', schema: APPLY })

const execute = (it, update) => agent(`${ENV}

Read .claude/skills/test-executor/SKILL.md in full and follow it exactly, with:

$CASES = ${stem(it)}.cases.md

${update ? `This is an UPDATE of the existing test file: ${update}` : 'For style, look at tests/unit/dao/test_item.py and tests/unit/managers/test_department_manager.py and their notes files.'}
Put shared builders you need as LOCAL helpers/fixtures in the test file (batch mode: tests/unit/factories.py may not be edited); note any builder worth promoting later in the notes file.
${BATCH}

Return: test file path, passed / xfailed counts, discrepancy list (one line each), branch coverage, coverage gaps by kind.`,
  { label: `tests ${it.source}`, phase: update ? 'Fix round' : 'Write tests', schema: EXEC, model: 'sonnet' })

const verify = (it, round) => agent(`${ENV}

Read .claude/skills/test-verifier/SKILL.md in full and follow it, with:

$MODULE = ${it.source}

${round > 1 ? `This is a SCOPED RE-VERIFY after a fix round. The previous report ${stem(it)}.verify.md lists the findings and surviving mutants.
- Traceability (step 1): full, it is cheap.
- Fidelity (step 2): only for cases whose rows changed in the latest cases revision (see its Revision line / Revision history) and tests added or changed since the last verify (see the notes file's Revision history). Unchanged tests were already verified.
- Reproduce (step 3): full test file run, --runxfail run, and one repeat.
- Mutation (step 4): run tests/unit/_tools/mutate.py only with --lines covering each previously surviving mutant's line (one call per contiguous range), plus any lines the fix round changed coverage for. Carry over the classifications of the previous report for everything else.
Overwrite ${stem(it)}.verify.md with the updated verdict (keep previous findings that are resolved, marked resolved).` :
`Run the mutation tool yourself (tests/unit/_tools/mutate.py mutates a temporary COPY of the backend and never touches app/; use --timeout 180 and write its --json into your system temp dir).`}
Write only ${stem(it)}.verify.md.
${BATCH}

Return: verdict, mutation line, and every OPEN finding with the stage that must fix it.`,
  { label: `verify${round > 1 ? '#2' : ''} ${it.source}`, phase: round > 1 ? 'Fix round' : 'Verify', schema: VERIFY })

const results = await pipeline(ITEMS,
  // 1. apply review
  it => applyReview(it),
  // 2. design + gap loop (up to 2 gap rounds)
  async (ap, it) => {
    let d = await design(it)
    const decisions = [...(ap?.decisions_made || []), ...(d?.decisions_made || [])]
    for (let round = 1; d && d.gaps > 0 && (round === 1 || d.blocking_gaps > 0) && round <= 2; round++) {
      const fg = await fillGaps(it, `${stem(it)}.cases.md`)
      decisions.push(...(fg?.decisions_made || []))
      d = await design(it, `Re-run: the spec's Gap log was updated to close your previous gaps. Follow "Re-running on an updated spec".`)
      decisions.push(...(d?.decisions_made || []))
    }
    return { ap, d, decisions }
  },
  // 3. tests
  async (prev, it) => ({ ...prev, ex: await execute(it) }),
  // 4. verify + one fix round
  async (prev, it) => {
    let v = await verify(it, 1)
    const first = v
    if (v && v.verdict !== 'PASS' && v.findings.length) {
      const by = s => v.findings.some(f => f.fix_by.toLowerCase().includes(s))
      if (by('describer')) await fillGaps(it, `${stem(it)}.verify.md`)
      if (by('describer') || by('designer') || by('case')) {
        const d2 = await design(it, `Re-run after verification: read ${stem(it)}.verify.md and follow "Verifier feedback" (and "Re-running on an updated spec" if the spec's Gap log changed).`)
        prev.decisions.push(...(d2?.decisions_made || []))
      }
      await execute(it, `the cases file may have a new revision and ${stem(it)}.verify.md may route test-weakness findings to you. Follow "Updating an existing test file".`)
      v = await verify(it, 2)
    }
    return { source: it.source, status: prev.ap?.status, bugs: prev.ap?.bugs_logged || [], dead: prev.ap?.dead_code || [],
             decisions: prev.decisions, cases: prev.d?.counts, open_gaps: prev.d?.gap_titles || [],
             tests: prev.ex ? `${prev.ex.passed} passed / ${prev.ex.xfailed} xfailed` : 'FAILED',
             coverage: prev.ex?.coverage, discrepancies: prev.ex?.discrepancies || [],
             first_verdict: first?.verdict, verdict: v?.verdict, mutation: v?.mutation,
             open_findings: v?.verdict === 'PASS' ? [] : (v?.findings || []) }
  },
)

const done = results.filter(Boolean)
const dropped = ITEMS.filter((it, i) => !results[i]).map(it => it.source)
if (dropped.length) log(`Pipeline failed for: ${dropped.join(', ')}`)

phase('Merge')
const merge = await agent(`${ENV}

You are the single writer for the shared registers after a parallel batch.
1. Find every tests/unit/**/*.bugs-staging.md. Insert all their rows into docs/testing/bugs.md, in the main bug table (the table ABOVE the "## TODOs" section — never after it), sorted by BUG ID with the existing rows. Skip exact duplicates of existing IDs and report any ID that appears in two staging files with different content. Then delete the staging files.
2. Find every tests/unit/**/*.deadcode-staging.md. Append their lines to docs/testing/dead-code-removal-checklist.md under the right layer heading (create the heading if missing), then delete the staging files.
3. Check that every BUG-NNN referenced in tests/unit/**/*.spec.md, *.cases.md and test_*.py exists in docs/testing/bugs.md; list any that do not.
Do not modify anything else. Return a short plain-text report: rows merged, dead-code lines merged, dangling IDs.`,
  { label: 'merge registers', phase: 'Merge', model: 'sonnet' })

return { results: done, dropped, merge }
