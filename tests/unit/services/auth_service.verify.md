# Verification — `app/services/auth_service.py`

> **Current verdict (Round 2, 2026-11-10): PASS** — Finding 1 closed by cases revision 4 (AUTH-LI-12); 181 passed · 37 strict xfail · mutation score 100%. Round 1 below is kept as written.

> **Verdict:** NEEDS WORK
> Tests: 180 passed · 37 xfailed (all strict, reproduced ✅) · coverage 98% branch (501, 578, 839: confirmed unreachable)
> Mutation: 216 mutants · 207 killed + 2 timeout · 7 survived → score 100% (after excluding 6 equivalent, 0 dead, 1 bug-path)
> Hand variants: 31 · 28 killed · 3 survived (1 case-missing, 1 out of module and covered by the profile DAO tests, 1 bug-fix shape that should survive)
> Source commit: e48a092 (target file clean in the working tree) · Cases revision: 3

## Summary
These tests are strong, and on the security paths they can be trusted.
- **Mutation:** every mutant that can change behaviour is killed.
- **Fidelity:** all 217 cards were read against their tests, with no findings.
- **Xfail honesty:** each of the 37 strict xfails fails on the Then line its card names.
- **Hand variants:** the security-critical ones are all killed. That covers password hashing skipped or plain, the reuse branch not revoking the family, revoked or expired (`<` vs `<=`) tokens accepted, suspended or removed members allowed to switch or reset, the workspace taken from somewhere other than the membership, audit rows missing, and stamp mix-ups.

One gap remains. `login_user` R2 ("no workspace claim") is tested only with a user who has no membership, so a login that put the user's first workspace in the claim passes every test. That is a case-designer fix: one new card.

## Findings
| # | Kind | Case / line | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing | `login_user` R2 (AUTH-LI-01 … LI-05, lines 455-461) | R2 says a login session has no workspace and no `workspace_id` claim. Every LI card logs in UA or UB, and neither has a membership (the standing owner rows are U0, UO, U2). So a login that takes the claim from the user's first membership is not caught. | Variant V29 (`workspace_id=next(m.workspace_id for m in get_by_user(user.id))`): 180 passed. | **case designer**: add a card where a user with an active membership (e.g. UO, owner of W1) logs in. Then: `"workspace_id" not in claims(pair.access_token)`, and on re-read `row_of(pair).workspace_id is None`. |

Not findings (checked):
- The `rb.call_count >= 1` lines in RG-22, LI-11, SW-13, RF-16, LO-12, AR-27 and ME-31 are what cases revision 3 prescribes (DISCREPANCY-2, double rollback). They are faithful to the cards.
- The only `pytest.raises(Exception)` is in AUTH-RG-12, and the card prescribes it.
- **Patches:** only the clocks, the spies, the failing commit / refresh, RACE-EMAIL (RG-11 … 13), the fake `refresh_token_dao` (TP-13), and the `dr` fixture (`destroy_resource`, the spec's external). No session or DAO is mocked. No Cloudinary or email call can be made.
- **P34 (owner reset, OQ-34), isolation only, behaviour not judged:** no card outside AR / P34 calls `reset_password_by_admin`. Every AR target is a plain W1 member (UB, UC or MISSING). The three P34 tests are tagged "pending OQ-34". An OQ-34 answer changes only P34-01 … 03.

## Unreachable lines (executor's claim confirmed)
`dao.get` has no filter (`app/dao/base.py:43`), and the test database has these validated foreign keys:
- `workspace_members.workspace_id → workspaces` CASCADE
- `workspace_members.user_id → profiles` CASCADE
- `refresh_tokens.user_id → profiles` CASCADE

So a membership row or refresh row that was just found always has its workspace or profile:
- **501:** `switch_workspace` "Workspace not found".
- **578:** `refresh_access_token` "User no longer exists".
- **839:** `reset_password_by_admin` "Target user not found".

The only way to reach them would be a concurrent delete committed between the two SELECTs (READ COMMITTED), and even then the outcome is a refusal. They cannot be reached in a unit test. No spec rule asks for them.

## Surviving mutants
| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 1 | L501:12 | `raise` → `pass` | equivalent | Unreachable (FK cascade, see above) | — |
| 2 | L501:29 | `'Workspace not found'` → `''` | equivalent | Same line, unreachable | — |
| 3 | L578:16 | `raise` → `pass` | equivalent | Unreachable (refresh row cascades with the profile) | — |
| 4 | L578:33 | `'User no longer exists'` → `''` | equivalent | Same line, unreachable | — |
| 5 | L839:16 | `raise` → `pass` | equivalent | Unreachable (membership cascades with the profile) | — |
| 6 | L839:33 | `'Target user not found'` → `''` | equivalent | Same line, unreachable | — |
| 7 | L907:11 | `<` → `<=` | bug-path | This is the BUG-2561 fix (`validate_invitation_token` R2). AUTH-VI-07 is strict xfail and is excluded from the run. VI-08 and VI-09 pin both neighbours. | — |

Timeouts (counted as killed): L392:14 `in` → `not in` and L392:14 `'--'` → `''`. Both turn the slug loop into an infinite loop.

## Hand variants (security scrutiny)
Each variant was applied to a private copy of the backend, then `-m "not xfail"` was run (180 tests).

| # | Variant | Result | Killed by |
|---|---|---|---|
| V01 | email matched as a part (`ilike '%x%'`) in `profile_dao.get_by_email` | survived | Out of module: this is a profile DAO behaviour, covered there by PRF-GE-08 / GE-09 / GE-14 / GE-15. The auth spec delegates to it (`login_user` R1). Not a finding. |
| V32 | email case-insensitive and trimmed (the BUG-1860 fix shape) | survived, as it should | With `--runxfail` it gives 32 failed instead of 37: exactly RG-05, RG-06, RG-07, LI-10 and FP-03 flip. No passing test pins the bug. Case-sensitive and untrimmed matching are the bug path (BUG-1860 / 1861 / 1862). |
| V02 | login ignores the password | killed | LI-07, LI-08, LI-09 |
| V03 | password stored in plain text on registration | killed | RU-01 |
| V04 | owner reset stores the plain password | killed | AR-01, AR-04, AR-24, AR-25, P34-01 … 03 |
| V05 | reuse revokes only the presented row, not the family | killed | RF-09, RF-10, RF-14, RF-17 |
| V06 | reuse revokes the family but never commits | killed | RF-09, RF-10, RF-14, RF-17 |
| V07 | refresh starts a new family | killed | RF-01, RF-14 |
| V08 | refresh drops the session's workspace claim | killed | RF-01, RF-05, RF-06 |
| V09 | rotated row not linked to its successor | killed | RF-02, RF-14 |
| V10 | rotated row left live | killed | RF-02, RF-04, RF-06, RF-13, RF-14 |
| V11 | `last_used_at` not touched | killed | RF-02 |
| V12 | revoked token accepted | killed | RF-11 |
| V13 | expired with `<` instead of `<=` | killed | RF-12 |
| V14 | raw refresh token stored instead of its hash | killed | 67 tests (TP-01 …) |
| V15 | switch: membership taken from any workspace | killed | SW-08, SW-09 |
| V16 | switch: suspended / inactive / invited member allowed | killed | SW-04 … SW-07 |
| V17 | switch: membership checked on another workspace than the claimed one | killed | SW-08, SW-09 |
| V18 | reset: inactive / suspended owner allowed | killed | AR-06, AR-07 |
| V19 | reset: inactive / suspended target allowed | killed | AR-17, AR-18 |
| V20 | reset: owner of any workspace accepted | killed | AR-08 … AR-15, AR-23 |
| V21 | reset: target in any workspace accepted | killed | AR-19, AR-20 |
| V22 | reset: sessions not revoked | killed | AR-02 |
| V23 | reset: the caller's sessions revoked instead of the target's | killed | AR-02 |
| V24 | logout of one token revokes every session | killed | LO-01 |
| V25 | audit rows never written (`log_action` no-op) | killed | RI-04, RW-02. The owner reset's missing audit row is BUG-2569 (AR-26 xfail). |
| V26 | replacing an image deletes the new picture instead of the old one | killed | ME-24 |
| V27 | removing a stamp never deletes its picture | killed | ME-11, ME-34 |
| V28 | removing a stamp keeps the stamp | killed | ME-11, ME-12, ME-28, ME-34 |
| V29 | login puts the user's first workspace in the claim | **survived** | Finding 1 |
| V30 | preview skips the status check | killed | VI-11, VI-12, VI-13 |

Bug-path items from the brief, confirmed as strict xfail failing on their named Then line:
- A stamp `public_id` outside the minted form is accepted: BUG-1864 (ME-19 … 23, Then 1 "DID NOT RAISE").
- Refresh without a lock: BUG-2560 (RF-15 recorder, Then 2, no `FOR UPDATE`).
- The old stamp is deleted before the commit: BUG-2562 (ME-32 Then 3, ME-33 Then 2 `['destroy', 'commit']`).
- The owner reset leaves no audit row: BUG-2569 (AR-26 Then 2).
- A foreign stamp's picture is deleted: BUG-1865 (ME-29, ME-30 Then 2).

## Traceability
cards 217 · tests 214 functions / 217 items (SW-04 … 07 are `pytest.param` ids) · unmatched: none · marker mismatches: none. 180 pass cards have no marker. 37 xfail cards have `xfail(strict=True)` with a reason that names the card's BUG ID. Every ID exists in `docs/testing/bugs.md`: 1406, 1860, 1861, 1862, 1864, 1865, 1866, 1874, 1987, 2560, 2561, 2562, 2563, 2564, 2566, 2567, 2568, 2569.

## Routed items
- **Case designer:** Finding 1 (the login card for a user with a membership).
- **Executor, describer:** nothing.
- **New bugs:** none. No `bugs.md` entry was added; BUG-2571 … 2609 are unused.
- **Future notes:** already present, nothing new.
  - `docs/future/notifications.md`: the password-reset email (D9), the "password changed by the owner" notice, and no welcome mail.
  - `docs/future/permissions.md`: who may reset another member's password, and the OQ-34 security hole.

## Commands run
```
.venv/Scripts/python.exe -m pytest tests/unit/services/test_auth_service.py -q -p no:cacheprovider -o addopts="" --cov=app.services.auth_service --cov-branch --cov-report=term-missing
  app\services\auth_service.py  270  3  66  3  98%  501, 578, 839
  180 passed, 37 xfailed
(plain, twice more)   180 passed, 37 xfailed · 180 passed, 37 xfailed
.venv/Scripts/python.exe -m pytest tests/unit/services/test_auth_service.py -q -p no:cacheprovider -o addopts="" --runxfail -rf
  37 failed, 180 passed   (the 37 are exactly the xfail-marked items; each on its card's "Fails today on" Then line)
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/services/auth_service.py tests/unit/services/test_auth_service.py --lines <range> --timeout 240 --json <scratch>/mut_auth_<n>.json
  1-387    Mutants: 35 · killed 35 · survived 0
  388-540  Mutants: 37 · killed 33 · timeout 2 · survived 2
  541-640  Mutants: 34 · killed 32 · survived 2
  641-832  Mutants: 35 · killed 35 · survived 0
  833-927  Mutants: 38 · killed 35 · survived 3
  928-999  Mutants: 37 · killed 37 · survived 0
<scratch>/variants.py   (own script: 31 text variants, each on a temp copy, -m "not xfail"; V32 also with --runxfail)
```
Scratch: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\authv\`. It holds the private `COVERAGE_FILE`s, `trace.py`, `variants.py`, `variants_main.json`, and the `mut_*.json` and `mut_*.log` files.

## Round 2 — 2026-11-10
Scope: Finding 1 only (cases revision 4 adds AUTH-LI-12). Narrow round: no new mutation run. LI-12 adds a test, not source changes; `app/services/auth_service.py` is unchanged at e48a092.

- **Fidelity, AUTH-LI-12:** faithful.
  - Given: `UO.hashed_password = get_password_hash(PW)` (HPW per the Conventions), `db.flush()`, then the commit point. UO's standing owner row MO in W1 is active.
  - When: `login_user(db, email=S.EO, password=PW)`, under the clock.
  - Then: the three lines in card order, with exact checks:
    1. `user.id == S.UO.id`
    2. `"workspace_id" not in claims(pair.access_token)`
    3. `row_of(db, pair).workspace_id is None`
  - No marker (Expect pass), and the `# [claude] AUTH-LI-12` tag appears once.
- **Variant V29** (login puts the user's first membership's workspace in the claim) is now **killed**: 1 failed (`test_auth_li_12__active_member_gets_no_workspace`), 180 passed.
- **Runs:** 3 plain runs gave 181 passed, 37 xfailed each time. This matches the executor's counts, and no test was flaky.
- **Finding 1:** closed.
- **Verdict:** PASS. Every survivor from Round 1 is equivalent (unreachable lines 501, 578, 839) or bug-path (L907, BUG-2561), and every hand variant is killed or belongs outside this module.

Commands:
```
ONLY=V29 <scratch>/variants.py      → V29 KILLED | 1 failed, 180 passed, 37 deselected
.venv/Scripts/python.exe -m pytest tests/unit/services/test_auth_service.py -q -p no:cacheprovider -o addopts=""   ×3
  181 passed, 37 xfailed · 181 passed, 37 xfailed · 181 passed, 37 xfailed
```
