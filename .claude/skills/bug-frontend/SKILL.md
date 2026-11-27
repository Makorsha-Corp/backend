---
name: bug-frontend
description: Bug-fix pipeline stage 5. After a unit's backend fix has PASSED the tester, updates the frontend (../frontend) for the API contract change the systems engineer recorded in docs/bugfix/units/<unit>/contract.md, on a matching branch, and opens a linked frontend PR. Skipped when there is no contract change. Use in the bug-fix pipeline (docs/bugfix/pipeline.md).
---

# Frontend agent

You run only after the tester has passed the backend fix, and only when
`docs/bugfix/units/<unit>/contract.md` lists a contract change. Your input is that
note, not the backend diff. The frontend repo is `../frontend` (React, Vite,
TypeScript), next to this backend checkout.

## Steps

1. Read `contract.md` and the bug rows it refers to in `docs/testing/bugs.md`.
   Read the frontend notes in those rows too. Some bugs say "the frontend part
   goes here as a note", for example showing the blockers a refusal lists.
2. In `../frontend`: `git fetch origin`, then create branch `bugfix/<unit>` from
   `origin/main`. If that repo has uncommitted work, stop and report it; don't
   stash or overwrite it.
3. Find every place that uses the changed endpoint or field:
   `grep -rn "<path or field>" src/`. Update API types, calls, error handling and
   UI copy to match the contract exactly:
   - new status codes get handled, and their messages shown as the backend
     sends them;
   - removed or renamed fields are removed or renamed;
   - blocker lists are shown to the user.
   Keep the change minimal and in the existing style; don't redesign screens.
4. Checks, all must pass:
   ```
   npm run typecheck
   npm run lint
   npm test
   ```
   If a page you changed has e2e coverage (`e2e/`), run `npm run test:e2e` for it.
5. Commit with the message `fix(<area>): follow backend <BUG ids>` and the
   attribution lines the session requires, then push. Open a PR with `gh` if it's
   logged in. Otherwise write `docs/bugfix/units/<unit>/frontend-pr.md` and leave
   the branch for the owner.
   - The PR body links the backend PR or branch and says "merge after the backend PR".
6. Add the frontend PR or branch to the backend `pr.md` and to `docs/bugfix/state.md`.

Never merge. Report: files changed, check results, the PR link or branch.
