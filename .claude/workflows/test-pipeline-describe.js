export const meta = {
  name: 'test-pipeline-describe',
  whenToUse: 'Start of a batch: args.files = list of app/ source paths. Returns every new review question with a suggested answer for the human digest.',
  description: 'Stage 1 of the unit-test pipeline: describe a batch of source files in parallel and collect review questions',
  phases: [
    { title: 'Describe', detail: 'one describer agent per source file' },
  ],
}

const FILES = args.files
const ROOT = args.root || 'E:\\Projects\\Makorsh-Corp\\backend'   // pass args.root for a checkout elsewhere

const RESULT = {
  type: 'object',
  properties: {
    file: { type: 'string' },
    spec_path: { type: 'string' },
    status: { type: 'string', description: 'IN REVIEW or APPROVED' },
    callables_specified: { type: 'integer' },
    not_specified: { type: 'integer' },
    house_rule_lines: { type: 'integer', description: 'number of auto-applied house-rule violation lines' },
    precedent_lines: { type: 'integer', description: 'number of precedent-match lines pre-filled' },
    questions: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          qid: { type: 'string', description: 'e.g. Q1' },
          title: { type: 'string' },
          one_line: { type: 'string', description: 'what happens today, one plain sentence' },
          suggested_answer: { type: 'string', description: 'intended | bug — <intended behavior> | remove' },
          severity: { type: 'string', description: 'high (security/money/data loss/crash) | normal' },
        },
        required: ['qid', 'title', 'one_line', 'suggested_answer', 'severity'],
      },
    },
    notes: { type: 'string', description: 'anything the orchestrator must know (e.g. file is constants-only, cross-file bug found)' },
  },
  required: ['file', 'spec_path', 'status', 'callables_specified', 'not_specified', 'house_rule_lines', 'precedent_lines', 'questions', 'notes'],
}

phase('Describe')
const results = await parallel(FILES.map(f => () => agent(
`Working directory: ${ROOT} (FastAPI + SQLAlchemy backend, Windows; Python venv at .venv).

Read the skill file .claude/skills/test-describer/SKILL.md in full and follow it exactly, in mode:

describe ${f}

Batch-mode rules (you are one of many describers running in parallel):
- Read docs/testing/house-rules.md and docs/testing/bugs.md first. House-rule violations and precedent matches are pre-filled, not asked.
- EVERY new review question must end with a line "**Suggested answer:** <intended | bug — <intended behavior> | remove>", chosen by industry best practice (the reviewer delegates to best practice by default). Leave its **Answer:** line as _pending_.
- Do NOT edit docs/testing/bugs.md, house-rules.md, the dead-code checklist, or anything under app/. Write only the spec file.
- If the file is framework glue (middleware, FastAPI dependencies, settings), note in the Overview under "Notes for the test designer" how it can be unit-tested (e.g. call the dependency function directly with a real db session; wrap middleware in a minimal Starlette/FastAPI app and use TestClient). Unit tests may use such a minimal app; they must not start the real app.
- If you find a serious bug outside this file (security, data leak, crash), mention it in your final notes.

Return the structured summary: spec path, status, counts, and every NEW question (qid, title, one plain sentence of what happens today, your suggested answer, severity high for security/money/data-loss/crash else normal).`,
  { label: `describe ${f.replace('app/', '')}`, phase: 'Describe', schema: RESULT }
)))

const ok = results.filter(Boolean)
const failed = FILES.filter((f, i) => !results[i])
if (failed.length) log(`Describer failed for: ${failed.join(', ')}`)
const totalQ = ok.reduce((n, r) => n + r.questions.length, 0)
log(`${ok.length}/${FILES.length} specs written · ${totalQ} new questions · ${ok.filter(r => r.questions.length === 0).length} specs need no review`)
return { results: ok, failed }
