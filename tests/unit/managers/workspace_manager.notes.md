# Execution notes — `app/managers/workspace_manager.py`

> Cases: `tests/unit/managers/workspace_manager.cases.md` (revision 3) · Tests: `tests/unit/managers/test_workspace_manager.py` · Source commit: e48a092
> Result: 221 passed · 84 xfailed · 0 discrepancies · 0 errors — branch coverage 100%
> Run: `COVERAGE_FILE=<private> .venv/Scripts/python.exe -m pytest tests/unit/managers/test_workspace_manager.py -q -p no:cacheprovider --cov=app.managers.workspace_manager --cov-branch --cov-report=term-missing`

## How the tests are built
- **One test per card, in card order.** Sections: CW, AM, RM, CI, VI, AI, XI. The two pending sections come last and stand apart, so a product decision changes only them:
  - **P16:** OQ-16, any active plan at creation.
  - **P17:** OQ-17 / BUG-1989, `max_members = 0`.
- **Naming.** Every test sits below a `# [claude] <ID>` comment. Its docstring's first line is the ID and title, the second its rules. `# Then N` marks the checks of the card's Then line N.
- **Parametrized cards.** Each card stays visible as its own param id. These groups share the same setup and checks and differ in one input:
  - RM-01…06, RM-07/13, RM-08…18 and RM-19…47: remover role × target role. The banner over them holds the table of who may remove whom.
  - CI-08…12: refused invite roles.
  - CI-23…25: invite blocked by a row that is not `inactive`.
  - XI-12…19: non-owner callers.
- **Conventions → code** (all in the file's header):
  - **Constants:** `M`, `MISSING`, `NOW`, `US`, `DAY`, `T1`, `T2`.
  - **TAG-based names:** on fixture `t` (`t.SL`, `t.EA` …), computed once per test.
  - **Standing rows:** fixtures `pl0`→`pl2`, `w0`→`w2`, `uo`→`uc`, `mo`. Each depends on the one before, so ids rise in Conventions order. The autouse `standing_rows` builds them in every test.
  - **Given builders, each flushing:**
    - `mk_member(user, **but)` for "member(U)";
    - `mk_invitation("J", email, **but)` for "invitation J to e", with token `tok-J-<TAG>`;
    - `set_limit(n)` for "limit n" (W1's plan);
    - `mk_plan("PD"|"PX"|"PE"|"PI")`;
    - `make_profile(db)` for Pk.
  - **Named checks:**
    - `reread`;
    - `snap_before` / `snap` for "unchanged(X)", plus `without(cols, *names)` for "unchanged(X) except c";
    - `count_rows`;
    - `written` for "nothing written" and `seeded` for "nothing seeded";
    - `audit(db, ws, action=None)`, `members`, `invitations`.
  - Helpers only read. None of them holds an expected value.
- **Clean-up rows (RM-68…80, BUG-1201 / BUG-1280 / BUG-1883):**
  - Fixture `mk_order` (`OrderBuilder`) builds the rows: `eo`, `po`, `so`, `to`, `wo`, `inv` (`ws=w2` for W2), plus `approver(order, user, **but)`, `project`, `project_member`, `assignee` and `completer`.
  - Each order's parents (factory, account, work order type, a `Draft` status) are built once per workspace on first use.
  - `n_rows` / `rows_of` count and read on a fresh SELECT.
- **Patched:**
  - In every test, the autouse `clock` fixture patches `app.managers.workspace_manager.utcnow` and `app.dao.workspace_invitation.utcnow` to NOW (Conventions, Externals).
  - WSMG-CW-12 alone patches `M.workspace_dao.get_by_slug` (Race simulations).
  - WSMG-CI-04 wraps `app.managers.workspace_manager.secrets.token_urlsafe` with a spy (`token_spy()`) that calls the real function, around the When call only.
  - Nothing else is mocked.
- **Database errors:**
  - CW-12 (23505) and CW-28 (23503) run the call in `with db.begin_nested()` inside `pytest.raises(IntegrityError)`.
  - "Rolled back" cards (CW-33, AM-39, RM-81, CI-59, AI-24 …) use `sp = db.begin_nested()`, a `patch.object(db, "commit", wraps=db.commit)` spy, then `sp.rollback()`.
- **xfail markers:**
  - The `BUG_*` constants carry the bug's title from `docs/testing/bugs.md`. All are strict.
  - `BUG_1404` adds `raises=TypeError`: today the When call fails on the new `ip_address` keyword. The marker pins that cause, so a setup error cannot hide as an xfail.
  - AI-28 uses `BUG_1404_AND_1874`. It needs both fixes to pass.
- **How it was built:** six parallel forks, one per section, each in its own scratch folder (`C:\Users\User\AppData\Local\Temp\makorsh-pipeline\wsme\<section>\`). `merge.py` merged them under one shared header. Parts were run in scratch with `-p tests.unit.conftest`.

## Verification runs
- 3 plain runs and 1 run with `PGOPTIONS=-c enable_seqscan=off`: 218 passed and 84 xfailed every time, with no flakiness.
- **`--runxfail` with the scratch plugin `thenmap.py`:** the plugin maps each failure to the `# Then N` block it happens in and compares that with the card's "Fails today on". All 84 failures map with 0 mismatches:
  - 47 fail with `DID NOT RAISE` at Then 1.
  - 22 fail on an assertion at Then 2.
  - 8 fail with a `ValueError` at the When call. The card says "Then 1, the call raises": AM-19/21, AM-33/34, AI-14/15, CI-55/56.
  - 7 fail with a `TypeError` at the When call (BUG-1404: CW-34, AM-40, RM-82, CI-60, AI-25, AI-28, XI-26).
- **Reference plugin** (scratch `…\wsme\ref\wsme_ref_fix.py`, loaded in-process with `-p`, never in `app/`):
  - It replaces all seven `WorkspaceManager` methods with the spec's intended behaviour for every bug.
  - It swaps `WorkspaceCreate` for a subclass that trims the name and refuses a blank one (BUG-1980).
  - **All fixes with `--runxfail`:** 305 passed, so every check after each failure point runs and holds.
  - **All fixes without `--runxfail`:** the 84 strict cards XPASS. Strict mode reports them as failures.
  - **Each fix alone (`REF_FIX=<n>`)** flips exactly its own cards and breaks no other card:

    | Fix | Cards it flips |
    |---|---|
    | 1201 | RM-70…74 |
    | 1280 | RM-76 |
    | 1404 | 6 of its 7 cards; AI-28 also needs 1874 |
    | 1860 | CI-20…22 |
    | 1871 | CI-55/56 |
    | 1872 | AM-33/34, AI-14 |
    | 1873 | CI-27…30, CI-37 |
    | 1874 | AI-16…18, AI-27 |
    | 1883 | RM-78/79 |
    | 1980 | CW-29/30 |
    | 1981 | XI-08/10 |
    | 1982 | AM-19…21, AI-15 |
    | 1983 | CI-23…25 |
    | 1984 | RM-56 |
    | 1985 | AM-35, AI-10 |
    | 1986 | XI-20…22 |
    | 1987 | VI-08 |
    | 1990 | 34 cards |

  - **Faulty-fix check (`REF_1990_VARIANT=role_by_user`):** this variant reads the remover's role from their first membership row in any workspace. It fails RM-61, RM-63 and RM-66, the grants held in W0. The correct reference passes all 302.
- **Mechanical checks:**
  - `ruff check` (and `--select F841,F811`) is clean.
  - An AST pass finds no unused test argument.
  - All 305 case IDs appear exactly once.
  - The 84 xfail IDs equal the cards' xfail set.
  - The file is LF only (0 CRLF in 222,308 bytes).
- **Warnings:** 8 `DeprecationWarning`s for `datetime.utcnow()` come from the model defaults `SalesOrderApprover.assigned_at` and `SalesOrderEvent.created_at`. They are hit by RM-72 and RM-75. This is not a behaviour bug, so no bug was logged.

## Discrepancies
None.

## Coverage gaps
None — 100% branch coverage (156 statements, 58 branches).

## Factories added
None. The order and clean-up builders are local to this file (`OrderBuilder`), because only these cards need them in this form.

## Notes for maintainers
- **When a BUG-n is fixed,** its cards XPASS, and strict mode turns that into a failure. Remove the marker from those cards, and check that each card still fails today where its card says.
  - BUG-1404 fixes the `ip_address` / `user_agent` keywords on all seven methods.
  - AI-28 needs BUG-1874 as well.
  - BUG-1871 and BUG-1872 are separate paths: invite and add.
- **When OQ-16 or OQ-17 is decided,** only the P16 or P17 section changes. No other card passes an active plan id at creation or uses a limit of 0.
- **Timestamps:** the datetime columns are naive UTC and are compared with NOW. `invited_at`, `created_at` and `last_usage_reset_at` come from model defaults on the real clock and are checked only as `is not None`. `workspace_audit_logs.created_at` (timestamptz, BUG-1403) is never compared.
- **CW-26** gives a workspace an explicit high id, `990000000 + TAG % 9000000`. If the `workspaces` sequence ever gets that high, pick a new range.
- **Refusal cards** take their "before" snapshots after the last Given line, as Conventions say. A new Given row added after the snapshot would make "nothing written" fail.

## For the coming features (from these cards)
- **Payment portal (plans, seats, limits):**
  - **Seats when inviting:** active members (the owner included) + pending invitations with `expires_at > now`, for this workspace only.
  - **Seats when adding or accepting:** active members only. Pending invitations do not count (AI-13).
  - **What takes no seat:** suspended and removed members; accepted, cancelled and expired invitations. An invitation expiring exactly now frees its seat; one microsecond later it still holds it.
  - **Two pending invitations to one email hold two seats** until BUG-1873 is fixed (CI-54).
  - **An inactive plan's limit is still enforced** (AM-23, CI-39).
  - **Negative limits are meant as unlimited** (BUG-1871 / BUG-1872), but today they refuse everything. `0` currently means no limit (P17, BUG-1989 pending).
  - **At creation:** today any active plan id is taken unpaid, even with no default plan (P16). Every plan starts a 14-day `trial`, enterprise included. The owner gets no seat check, even on a `-1` plan (CW-19).
  - **The seat check has no lock** (spec FU-4). The portal's upgrade and downgrade path should decide how a limit lowered below the current count behaves. No card covers that today.
- **Permissions:**
  - **Removing members** (BUG-1990, owner's answer): `owner` may remove any non-owner; `ground-team-manager` and `manager` may remove `ground-team` only; everyone else gets 403. Roles match exactly: `Owner`, `Manager`, `"ground-team-manager "` and `""` are refused.
  - **The role comes from the caller's W1 role.** RM-61…66 and XI-23/24 give the caller a grant in W0 or W2 but pass their W1 role: owner (RM-61, RM-62, RM-65, RM-66), `ground-team-manager` (RM-63) or `manager` (RM-64). RM-60 has no other-workspace row; it checks that a member cannot remove themselves. A fix that reads the role by user id alone fails some of these cards, as the faulty-fix check above shows (RM-61, RM-63, RM-66).
  - **Cancelling an invitation** is owner-only and should be checked first (BUG-1986). The role lists for invitations (`manager, member, viewer, ground-team`) and members are routed to the permissions feature (Q10).
- **Notifications:** nothing is sent today.
  - `create_invitation` stores the email lower-cased. Its audit row keeps it as typed (CI-02, CI-57).
  - Accepting writes only the `member_added` audit row (actor = the inviter, or none) and the `invitation_accepted` audit row. After BUG-1874, it also writes the superseded `invitation_cancelled` rows, in that order (AI-26/27).
  - Removal writes `approver_removed`, `member_removed` and `assignee_removed` events once BUG-1201, BUG-1280 and BUG-1883 are fixed. These are the natural hooks for member notices.

## Revision history
- Revision 2 of the cases, first execution (2026-11-04): all 302 cards implemented, no discrepancy, no new bug (BUG-2050…2069 unused).
- Revision 3 of the cases (2026-11-04), from the verifier:
  - **WSMG-AI-18:** added Then 3–4. There is exactly one superseded `invitation_cancelled` audit row, its actor is UA, and its email is logged exactly as stored (`Ann.<TAG>@Acme.com`). The card is still xfail BUG-1874 and still fails today on Then 2 (`'pending' == 'cancelled'`, checked with `thenmap`).
  - **New WSMG-RM-83, RM-84, RM-85 (pass):** a `manager`, `viewer` or `finance` remover asking to remove the owner gets the owner message. MO, the remover's row and the counts are unchanged.
  - **Reference plugin:** the superseded row logs the stored email, so all 305 pass with `--runxfail`. `REF_1874_VARIANT=lower` is a wrong BUG-1874 fix that lower-cases that email; it fails AI-18 only, on Then 4 (1 failed, 304 passed). `REF_FIX=1874` alone still flips AI-16, AI-17, AI-18 and AI-27.
  - **Markers:** `BUG_1872` now has `raises=ValueError` (AM-33, AM-34 and AI-14 fail on the add's own `ValueError`). `BUG_1982` stays without `raises=`, because AM-20 fails on an assertion at Then 2, not on a raise.
  - **Notes fix:** "For the coming features → Permissions" now names the other-workspace cards correctly (RM-61…66; RM-60 has no other-workspace row; RM-63's grant is `ground-team-manager`).
  - **Runs:** 3 plain runs and 1 with seqscan off each gave 221 passed, 84 xfailed. `--runxfail` gave 84 failures with 0 Then mismatches. Coverage 100%, ruff clean, LF only.
