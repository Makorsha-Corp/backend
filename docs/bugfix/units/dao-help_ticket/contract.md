# Contract note: dao-help_ticket (round 1, 2026-11-27)

No contract change (no field, status code, message or input changes). Values that now behave differently, and the frontend already handles them:

- **`GET /platform/help/tickets?search=…`**: `%`, `_` and `\` in the search match literally in title, ticket number, description and workspace name (BUG-1443). Example: searching `a_b` used to list tickets titled "a_b" and "axb"; now only "a_b". Searching `50%` no longer finds "50 x". Searching `a\b` finds a title containing a real backslash, not "ab". Empty or spaces-only search still lists everything.
- **Order only:** `GET /help-tickets/` and `GET /platform/help/tickets` list newest first and then highest `id` when creation times tie (BUG-1442), so paging no longer repeats or skips tickets.
- **`POST /help-tickets/` → `ticket_number`**: the year comes from UTC (BUG-1441). Example: a server on Dhaka time, ticket opened 31 Dec 2026 20:00 UTC: `HELP-2026-…` instead of `HELP-2027-…`.

Frontend: `PlatformSupportPage.tsx` sends the trimmed search text unchanged and shows the list in server order; `HelpPage.tsx` sends no search. No change needed, so the frontend stage is skipped.
