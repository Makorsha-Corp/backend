# Verification — `app/managers/workspace_manager.py`

> **Current verdict (Round 2, 2026-11-04, cases revision 3): PASS.** Both round-1 items are closed. Tests: 221 passed and 84 strict xfail in each of 3 runs; traceability is clean at 305/305. The round-1 mutation result still stands because `app/` is unchanged. See "Round 2" at the end.

> **Verdict:** NEEDS WORK (one case-designer item; the tests themselves have no finding)
> Tests: 218 passed · 84 xfailed (reproduced ✅, `--runxfail` 84 failed, each where its card says) · coverage 100% branch (156 stmts, 58 branches)
> Mutation: 162 mutants · 160 killed · 2 survived → score 100% (after excluding 0 equivalent, 0 dead, 2 bug-path)
> Hand variants: 59 faulty implementations run in-process (my own plugin), 58 caught · 1 not caught (`case-missing`, below)
> Source commit: e48a092 · Cases revision: 2

## Summary
You can trust these tests. All 302 cards are implemented faithfully, and the executor's results reproduce exactly: three plain runs, one `--runxfail` run and the coverage run, with no flakiness. Every mutant the tool generated is killed, apart from the two that sit on BUG paths.

I also ran 59 faulty implementations of my own against the plans, seats, limits, duplicate-invitation, accept-supersede and BUG-1990 removal rules. The cards catch 58 of them. The one they miss is a BUG-1874 fix that writes the superseded invitation's email lower-cased in its audit row. AI-18 builds exactly that row but checks only its status, so the case designer should add a Then line.

The P16 and P17 sections are isolated. No other card depends on them, and changing either decision breaks only its own cards (and, for P16, the R2 refusal cards that test the same `if subscription_plan_id` branch).

## Findings
| # | Kind | Case / line | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing | WSMG-AI-18 (spec `accept_invitation` R5) | R5 says each superseded row's audit metadata is `{"invitation_id", "email": <its email>, "reason": "superseded"}`. AI-18 is the only card whose superseded invitation is stored in mixed case (`Ann.{TAG}@Acme.com`), and it checks only `status == "cancelled"`. In AI-16 and AI-27 the stored email is already lower-case, so a fix that logs `email.lower()` passes every card. | Variant `acc_lower_email_audit` (reference BUG-1874 fix with `'email': _o.email.lower()`): with `--runxfail`, 80 failed, the same set as the correct reference. | **case designer**: add to AI-18 an audit Then line asserting the superseded `invitation_cancelled` row's `metadata_json == {"invitation_id": K.id, "email": f"Ann.{TAG}@Acme.com", "reason": "superseded"}`. |
| 2 | notes accuracy (minor) | `workspace_manager.notes.md:127` | It says "RM-60…66 and XI-23/24 give the caller an owner or manager grant in W0 or W2". RM-60 has no row in another workspace (self-removal), and RM-63's grant is `ground-team-manager`. The test code is correct. | Cards RM-60 and RM-63, Given lists | **executor**: reword the note, e.g. "RM-61…66 give the caller another grant in W0 or W2". |

Not findings (checked and accepted):
- **`patch.object(db, "commit", wraps=db.commit)`** in CW-33, AM-39, RM-81, CI-59, AI-24 and XI-25. This is the spy that the cases Conventions prescribe for "rolled back" cards. It wraps the real commit, so it is not a mocked session.
- **Markers without `raises=ValueError`:** BUG-1872 (AM-33/34, AI-14) and BUG-1982 (AM-19/21, AI-15). The cards do not ask for `raises`. My `--runxfail` failure map shows that each of these fails today with the exact ValueError text the card's "Fails today on" names. Pinning `raises=ValueError` would be a harmless hardening; it is optional.
- **XI-09 and XI-11 do not check the message.** Their cards say the message is checked in the BUG-1981 cards, XI-08 and XI-10.

## Surviving mutants
| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 60 | L431 `if invitation.expires_at < utcnow()` | `<` → `<=` | bug-path | This mutation is the BUG-1987 fix itself, where expired means `expires_at <= now`. Only VI-08, a strict xfail, pins that boundary, and mutate.py excludes xfail tests. VI-08 will kill it once the marker is removed. | — |
| 130 | L537 `"Invitation does not belong to this workspace"` | → `""` | bug-path | BUG-1981 replaces this message with "Invitation not found". XI-08 and XI-10, both xfail, check the intended text. XI-09 and XI-11 are pass cards that check only "nothing changed", as their cards say. | — |

## Hand variants (owner's focus: plans, seats, limits; BUG-1990)
I wrote the plugin `wsmv_variants.py` (scratch). It applies text edits to the real source, execs the result in the module's own namespace (so the clock patch still applies) and rebinds the singleton's methods. Nothing under `app/` is written.

- **Today's behaviour (plain runs):** a variant is caught when a passing card fails.
- **Bug-rule variants:** I first wrote a correct reference fix and checked it with `--runxfail`. Each reference flips exactly its own cards and breaks none:
  - negative limits, `neg_fix`: 5 cards;
  - duplicate invitations, `dup_ref`: 5 cards;
  - accept supersedes the others, `acc_ref`: 4 cards;
  - removal permissions, `rm_ref`: 34 cards.

  Each faulty variant is then compared with its reference. "Caught by" lists the cards that newly fail.

**Seats and limits**

| Variant | Caught by |
|---|---|
| invite seat check `>` instead of `>=` | CI-39, 40, 41, 42, 45, 47, 54 |
| add seat check `>` instead of `>=` | AM-23, 24, 27, AI-12 |
| pending invitations not counted on invite | CI-39, 41, 42, 47, 54 |
| expired pending counted (no `expires_at` filter) | CI-46 |
| pending counted at `expires_at >= now` | CI-46 |
| pending of every workspace counted (W0, W2) | CI-52, 53 |
| accepted or cancelled invitations counted (no status filter) | CI-48, 49 |
| `status != 'cancelled'` counted | CI-48 |
| suspended members counted, add / invite | AM-29 / CI-50 |
| every member row counted (inactive too), add / invite | AM-29, 30 / CI-50, 51 |
| active members of every workspace counted, add / invite | AM-31, 32 / CI-52, 53 |
| add (and accept) also counts pending invitations | AM-28, AI-13 |
| owner not counted, add / invite | AM-23, 24, 27, AI-12 / CI-39…42, 45, 47, 54 |
| inactive plan's limit skipped, add / invite | AM-23 / CI-39 |
| negative limit: only `-1` taken as unlimited | AM-34, CI-56 (limit `-5`) |

**0 handling (OQ-17 / BUG-1989, pending)**
- I ran three variants that treat `0` as a real limit (`is not None`): add only, invite only, and both. They fail P17-01, 02 and 05 (add), P17-03 and 04 (invite), and all five P17 cards (both). No other card fails.
- So whatever the plans design decides, only section P17 changes.

**P16 isolation (OQ-16, pending)**
- "Refuse a non-default plan at creation" (the spec's suggested answer) fails P16-01, 02 and 04 and nothing else. P16-03 uses the default plan's own id and still passes, as it should.
- "Ignore `subscription_plan_id`" fails P16-01, 02 and 04, plus CW-07, 08 and 09. Those three are the R2 refusal cards (unknown or inactive plan id). They stand whatever the portal decides, and they break here because this variant removes R2 itself, not because they depend on P16.
- The fidelity pass also confirmed:
  - outside P16, no card passes a truthy active plan id to the manager, and outside P17 none uses limit 0;
  - no fixture or helper exists only for those sections;
  - every fixture is function-scoped, and the per-test rollback keeps them from sharing state.

**Duplicate invitations (BUG-1873, against the reference fix)**

| Variant | Caught by |
|---|---|
| case-sensitive compare (raw input vs stored) | CI-28, 29 |
| input lower-cased, stored compared exactly | CI-29 |
| no trim | CI-29 |
| ignores expiry | CI-31 |
| `expires_at >= now` | CI-31 |
| any workspace | CI-34, 35 |
| any status | CI-32, 33 |

**Accept supersedes the others (BUG-1874, against the reference fix)**
- Accept cancels nothing else, which is today's code: AI-16, 17, 18 and 27 stay failing, so the bug shows as open.

| Variant | Caught by |
|---|---|
| cancels other workspaces' invitations | AI-19, 20 |
| cancels other emails' invitations | AI-13, 21 |
| case-sensitive email match | AI-18 |
| unexpired only | AI-17 |
| any status (re-cancels accepted / cancelled) | AI-22 |
| superseded audit rows in descending id order | AI-27 |
| superseded audit email lower-cased | **not caught** (finding 1) |

**Member removal (BUG-1990, against the reference fix)**

| Variant | Caught by |
|---|---|
| role read from the remover's first membership anywhere | RM-61, 63, 66 |
| role compared case-insensitively | RM-43 (`Owner`), RM-44 (`Manager`) |
| role stripped of spaces | RM-45 (`"ground-team-manager "`) |
| owner-target check moved after the role check | RM-49, 50, 51 |
| `manager` may remove anyone | RM-14…18 |
| only `ground-team-manager` limited (`manager` refused) | RM-13…18 |

Note for later, not a finding: the owner-first order is pinned for ground-team, ground-team-manager and member removers (RM-49…51). No card has a manager, viewer, finance or odd-case remover targeting the owner. My reorder variant is caught anyway.

## Traceability
- **Cards and tests:** 302 cards, 302 tests and params (246 `# [claude]` tags, 63 param ids). Unmatched: none. Duplicates: none. No test lacks an id.
- **Markers:** 84 xfail cards against 84 strict markers. Each reason names every listed BUG id, and AI-28's names both 1404 and 1874. Marker mismatches: none.
- **bugs.md:** all 18 BUG ids exist there.
- **`--runxfail` failure map** (my plugin `failmap.py`): all 84 fail inside the card's "Fails today on" block.
  - 69 fail at that Then line.
  - 15 fail at the When call, where the card's Then 1 says "the call raises". The exception text matches the card every time: a TypeError on `ip_address` (×7), a ValueError "already a member" (×3), and "…limit (-1)…" / "(-5)" (×5).
  - None fails on a setup or import error.

## For the coming features
**Payment portal (plans, seats, limits).** Every line below is pinned by a passing card that a wrong implementation fails, as the variant tables above show.
- **Seats when inviting:**
  - Counted: active members of this workspace, the owner included, plus invitations with status exactly `pending` and `expires_at > now`.
  - Refused at count == limit (CI-40); allowed at limit − 1 (CI-43).
  - An invitation expiring exactly now frees its seat (CI-46). One microsecond before, it still holds it (CI-47).
- **Seats when adding or accepting:** active members only. Pending invitations do not count (AM-28, AI-13).
- **What never takes a seat:** suspended and inactive members; accepted and cancelled invitations; anything in another workspace.
- **Plan status:** an inactive plan's limit is still enforced (AM-23, CI-39).
- **Negative limits:** any negative value is meant as unlimited. `-5` is pinned too (AM-34, CI-56), so a portal that tests `== -1` would be caught.
- **`0` (P17, BUG-1989 pending):** today `0` means no limit. Deciding it touches only P17-01…05.
- **Creation (P16, OQ-16 pending):** today any active plan id is taken unpaid, enterprise included. Deciding it touches only P16-01, 02 and 04.
- **Locking:** the seat check takes no lock (spec FU-4). No card covers concurrent invites or a limit lowered below the current count; the portal's downgrade path must decide that.
- **Duplicate invitations (BUG-1873):** the intended check is per workspace, lower-cased and trimmed, pending and unexpired only. The variants above show that each of those conditions is pinned.

**Permissions (BUG-1990).**
- `owner` may remove any non-owner. `ground-team-manager` and `manager` may remove only `ground-team`. Every other role is refused.
- Role names match exactly: `Owner`, `Manager`, `"ground-team-manager "` and `""` are refused.
- The target-is-owner refusal comes before any role check.
- The role must be the caller's role in this workspace: a grant held in W0 or W2 must not leak (RM-61, 63, 66).
- Cancelling an invitation is owner-only, and the role is checked first (BUG-1986).

**Notifications.** Nothing is sent today.
- Hooks: the `invitation_sent` audit row keeps the email as typed, while the stored invitation email is lower-cased. The `member_added` and `invitation_accepted` audit rows are written on accept. Once BUG-1874 is fixed, superseded `invitation_cancelled` rows follow with `reason: "superseded"`; the email in those rows is not yet pinned by any card (finding 1).
- On removal, `approver_removed`, `member_removed` and `assignee_removed` events are written once BUG-1201, BUG-1280 and BUG-1883 are fixed.

## Commands run
All runs used a private `COVERAGE_FILE` under `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\wsmv\`.

**Tests and coverage**
```
.venv/Scripts/python.exe -m pytest tests/unit/managers/test_workspace_manager.py -q -p no:cacheprovider --cov=app.managers.workspace_manager --cov-branch --cov-report=term-missing
  app\managers\workspace_manager.py  156  0  58  0  100%
  218 passed, 84 xfailed, 23 warnings in 29.45s
```

**`--runxfail` with the failure map**
```
.venv/Scripts/python.exe -m pytest tests/unit/managers/test_workspace_manager.py -q -p no:cacheprovider --runxfail -rf -p failmap   (PYTHONPATH=wsmv)
  84 failed, 218 passed
```

**Two repeat runs**
```
  218 passed, 84 xfailed   (both runs)
```

**Lint**
```
.venv/Scripts/python.exe -m ruff check tests/unit/managers/test_workspace_manager.py
  All checks passed!
```

**Mutation**
```
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/managers/workspace_manager.py tests/unit/managers/test_workspace_manager.py --timeout 300 --json <wsmv>/mutate.json
  Mutants: 162 · killed 160 · timeout 0 · survived 2 · score 99%
  SURVIVED #60 L431:11 cmp: Lt -> LtE
  SURVIVED #130 L537:29 const: 'Invitation does not ' -> ''
```

**Hand variants and traceability**
```
bash <wsmv>/run_variants.sh plain|runxfail <variant>...      (VARIANT=<name>, -p wsmv_variants)
  none: 218 passed, 84 xfailed
  references, --runxfail: neg_fix 79 failed · dup_ref 79 · acc_ref 80 · rm_ref 50   (= 84 minus each fix's own cards)
.venv/Scripts/python.exe <wsmv>/trace.py
  cards 302 · tests mapped 302 · missing [] · extra [] · marker mismatches [] · bug ids missing in bugs.md []
```

Fidelity was read card by card for all 302 cards, split by section (CW 34, AM 40, RM 82, CI 60, VI/AI/XI/P16/P17 86). Fidelity findings: none.

## Round 2 — 2026-11-04
> **Verdict:** PASS · cases revision 3 · source e48a092 (`app/managers/workspace_manager.py` unchanged: `git diff e48a092` is empty)
> Tests: 221 passed · 84 xfailed in all 3 runs (no flakiness) · traceability 305 cards ↔ 305 tests, 84/84 strict markers, 0 mismatches

Scope: the revision-3 changes only.

| Item | Check | Result |
|---|---|---|
| Finding 1: WSMG-AI-18, Then 3–4 | Test at lines 5224–5245, read against the card. Then 3: `audit(db, w1, "invitation_cancelled")` has exactly 1 row. Then 4: `user_id == ua.id` and the exact `metadata_json == {"invitation_id": k.id, "email": f"Ann.{t.TAG}@Acme.com", "reason": "superseded"}`. The strict BUG-1874 marker stays, and with no fix the card still fails on Then 2. | ✅ faithful |
| Finding 1: does the variant now die? | Each variant runs the full file with `--runxfail`. The reference `acc_ref` gives 80 failed, and AI-18 passes. `acc_lower_email_audit` gives 81 failed: the one new failure is **AI-18**, on Then 4 (`Differing items` in the metadata). | ✅ caught |
| New WSMG-RM-83/84/85 | Tests at lines 3348–3417, read against the cards. R is the remover's member row with role `manager` / `viewer` / `finance`. Snapshots are taken after the last Given line. Then 1–2 check `pytest.raises(ValueError)` and the exact owner message. Then 3–5 check `unchanged(MO)`, `unchanged(R)` and "nothing written". No marker, as the cards say (pass). | ✅ faithful |
| RM-83/84/85 against the reorder | The variant `rm_owner_after_role` (owner-target check after the role check, on top of the BUG-1990 reference) now fails RM-49, 50, 51, **83, 84 and 85**. In the plain run, the three new cards fail as well, because today's code needs the owner check first. The round-1 note about the uncovered `manager`/`viewer`/`finance` removers is closed. | ✅ caught |
| Finding 2: notes line 127 | It now reads "RM-61…66 and XI-23/24 give the caller a grant in W0 or W2…". RM-60 is described separately (self-removal, no row in another workspace), and the grants are listed by card: owner for RM-61/62/65/66, `ground-team-manager` for RM-63, `manager` for RM-64. I checked the list against the cards' Given lines. It is correct. | ✅ fixed |

New findings: none.

Commands run in round 2 (scratch in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\wsmv\`, with a private `COVERAGE_FILE`):

```
.venv/Scripts/python.exe <wsmv>/trace.py
  cards 305 · tests mapped 305 · missing [] · extra [] · marker mismatches [] · bug ids missing in bugs.md []
.venv/Scripts/python.exe -m pytest tests/unit/managers/test_workspace_manager.py -q -p no:cacheprovider   (x3)
  221 passed, 84 xfailed   (each run)
bash <wsmv>/r2/run_variants.sh runxfail acc_ref acc_lower_email_audit rm_ref rm_owner_after_role
  acc_ref 80 failed · acc_lower_email_audit 81 failed (new: AI-18) · rm_ref 50 failed · rm_owner_after_role 56 failed (new: RM-49, 50, 51, 83, 84, 85)
bash <wsmv>/r2/run_variants.sh plain rm_owner_after_role
  40 failed, 215 passed, 50 xfailed
```
