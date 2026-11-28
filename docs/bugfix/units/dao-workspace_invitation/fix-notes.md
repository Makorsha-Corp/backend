# Fix notes: dao-workspace_invitation

## Round 1 (2026-11-27)

### Changed
File: `app/dao/workspace_invitation.py` (only file touched).

- **BUG-1401** (lists had no sort order)
  - `get_pending_invitations`: added `.order_by(WorkspaceInvitation.invited_at.desc(), WorkspaceInvitation.id.desc())`.
  - `get_user_invitations`: same `order_by`.
  - `get_all_invitations`: same `order_by`.
- **BUG-1402** ("my invitations" matched the email exactly)
  - `get_user_invitations`: the filter is now
    `func.lower(func.trim(WorkspaceInvitation.email)) == email.strip(" ").lower()`.
  - Added `from sqlalchemy import func`. No other imports changed, and none became unused.
- `get_by_token`, `count_pending_invitations`, the singleton and the signatures are unchanged.

### Why
- HR-6 and the BUG-1210 precedent: newest first by `invited_at`, with `id` descending last so rows with the same `invited_at` always come back in one fixed order. This is the same two-key `order_by` that `help_ticket.py`, `attachment_link.py` and `account_invoice.py` use.
- R2/R2a: both sides are trimmed and lower-cased, then compared with `=`. That keeps it a whole-value equality: no LIKE, so `_` and `%` are ordinary characters and a substring never matches. Postgres `trim(x)` with no character list strips only the space character. So Python uses `strip(" ")`, not a bare `strip()`, and both sides trim exactly the same character (rule for this round).

### Reproduction (throwaway script in the session scratchpad, run against `bf_dao_workspace_invitation_test` with rowkit, now deleted)
Setup: 4 pending invitations in one workspace with `invited_at` t0, t0+1h, t0+1h (a tie), t0+2h. The first row is then updated. Invitation rows stored as `john.doe@example.com`, `John.Doe@Example.com`, ` john.doe@example.com `, plus `john_doe@example.com` and `a@x.com` as decoys.

| Check | Before | After |
|---|---|---|
| `get_pending_invitations` order (expected newest first, tie by id desc) | `[23, 24, 25, 26]` (insertion order), FAIL | `[35, 34, 33, 32]`, PASS |
| `get_all_invitations` order | `[23, 24, 25, 26]`, FAIL | `[35, 34, 33, 32]`, PASS |
| `get_user_invitations("John.Doe@example.com")` (expect all 3 john rows) | `[]`, FAIL | 3 rows, newest first, PASS |
| `get_user_invitations(" john.doe@example.com ")` | only the row stored with spaces, FAIL | 3 rows, PASS |
| `get_user_invitations("john.doe@example.com")` | only the exact lower-case row, FAIL | 3 rows, PASS |
| `get_user_invitations("JOHN.DOE@EXAMPLE.COM")` | `[]`, FAIL | 3 rows, PASS |
| `a@y.com`, `doe@example.com`, `john%doe@example.com` give `[]`; `a@x.com` gives 1 row | PASS | PASS (unchanged) |

The ids differ between the two runs because each run rolls back and the sequences keep counting. The order pattern is what was checked.

The compiled SQL for `get_user_invitations(email=" A@x.com ")` (from `scripts/bugfix/compile_query.py`):
`WHERE lower(trim(workspace_invitations.email)) = 'a@x.com' AND status = 'pending' AND expires_at > ... ORDER BY invited_at DESC, id DESC`.

Other checks: `python -c "import app.main"` imports fine. `ruff check app/dao/workspace_invitation.py` reports "All checks passed!".

### Assumptions
- "Surrounding spaces" means the space character only (Postgres `trim` default). Tabs and newlines around an email are not trimmed on either side. This keeps SQL and Python symmetric.
- The Python side lower-cases with `str.lower()` and Postgres uses `lower()`. For ASCII emails they agree. Non-ASCII local parts could in theory differ under some database collations; I treated that as out of scope.

### Seen, not fixed
- `lower(trim(email))` cannot use a plain index on `email`, and there is no such index today anyway. If "my invitations" ever gets slow, a functional index `lower(trim(email))` would need a migration. Not needed for these bugs.
- `count_pending_invitations` has no order (correct: it is a count), and it is unchanged as the brief requires.

### Risk
- Low. The only behaviour change outside ordering is that `GET /workspaces/me/invitations/` now shows invitations whose stored email differs from the account email only in case or surrounding spaces. Accepting an invitation already compares the two case-insensitively (`WorkspaceManager`, `invitation.email.lower() != user_email.lower()`), but it does not trim. A row stored with surrounding spaces would now be listed, yet accepting it would fail the manager's email check. `create_invitation` lower-cases but does not trim either. Such rows should be rare, but the systems engineer may want to look at whether the manager should trim too (out of scope here).
