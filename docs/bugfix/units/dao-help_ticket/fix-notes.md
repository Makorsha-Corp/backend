# Fix notes: dao-help_ticket

## Round 1 (2026-11-27)

Only file changed: `app/dao/help_ticket.py` (worktree `E:\Projects\Makorsh-Corp\bugfix-worktrees\dao-help_ticket`).

### Changed

- **BUG-1441** `DAOHelpTicket.create_with_user`: `datetime.now().year` became `utcnow().year`. Added `from app.utils.time import utcnow` at module level and removed `from datetime import datetime`, which nothing else used.
- **BUG-1442** `DAOHelpTicket.list_by_workspace` and `DAOHelpTicket.list_platform`: `order_by(HelpTicket.created_at.desc())` became `order_by(HelpTicket.created_at.desc(), HelpTicket.id.desc())`. It still runs before `offset` / `limit`.
- **BUG-1443** `DAOHelpTicket.list_platform`:
  - Added the class attribute `_ILIKE_ESCAPE = "\\"` and a static helper `_escape_ilike(value: str) -> str`. Both copy `AccountInvoiceDAO` exactly: the helper escapes `\` first, then `%` and `_`.
  - The trimmed search text is now escaped before it is wrapped in `%…%`.
  - All four `ilike` calls (title, ticket number, description, workspace name) now pass `escape=self._ILIKE_ESCAPE`.

### Why

- **BUG-1441:** `utcnow()` is naive UTC. The year therefore matches the UTC `created_at`, whatever time zone the server is set to.
- **BUG-1442:** `id` is unique, so tickets with the same `created_at` now always come back in the same order. Pages no longer repeat or skip tickets (HR-6).
- **BUG-1443:** Postgres treats an escaped `%`, `_` or `\` as a plain character when `ESCAPE '\'` is given, so search text matches literally in all four fields (HR-8).
- Empty search and spaces-only search are unchanged. `if search:` still skips the filter for `None` / `""`, and spaces-only trims to `%%`, which matches everything (R3, R4).

### Reproduction (throwaway checks against marker_test with rowkit, rolled back; plus compile_query)

| Bug | Before | After |
|---|---|---|
| BUG-1441: local clock faked to 2027-01-01 02:00 (Dhaka), UTC 2026-12-31 20:00 | `HELP-2027-001` | `HELP-2026-001` |
| BUG-1442: compiled SQL of both list methods | `ORDER BY help_tickets.created_at DESC` | `ORDER BY help_tickets.created_at DESC, help_tickets.id DESC` |
| BUG-1443: search `a_b` | `a\b`, `a_b`, `axb` | `a_b` |
| BUG-1443: search `50%` | `50 x`, `50%` | `50%` |
| BUG-1443: search `a\b` | `ab` (the backslash escaped `b`) | `a\b` |
| BUG-1443: search `_` / `%` | every ticket | only rows that really contain `_` / `%` |

- For the `_` search, the "after" result also includes one seed row. Rowkit gave it the ticket number `ticket_number-<n>`, which really contains `_`, so that match is correct.
- For BUG-1442, the database run happened to return tied rows in id order. Tie order without a tiebreak depends on chance and the plan, so I checked this bug by the SQL shape, as the agent rules allow for ordering bugs.

Other checks: `python -c "import app.main"` succeeds, and `ruff check app/dao/help_ticket.py` passes. `.scratch/` has been deleted.

### Assumptions

- I copied the escape helper from `AccountInvoiceDAO` into this class rather than moving it into a shared module. That keeps the change inside the brief's scope (this file only).
- The escaping is applied after trimming, so leading and trailing spaces are still removed as before.

### Seen, not fixed

- `generate_ticket_number` builds its own `LIKE` with `f"{prefix}%"` and no escaping. `year` is an int, so this is harmless. The race in the numbering is BUG-1440 and is out of scope.

### Risk

- Low. A search containing `\` now matches a literal backslash. Before the fix the backslash acted as an escape, so `a\b` used to find `ab`. This is the intended behaviour under HR-8.
