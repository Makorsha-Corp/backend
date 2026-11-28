# API contract: dao-account_tag

**No contract change** (no frontend work; the frontend stage is skipped).

Request inputs, status codes, error messages and response fields are unchanged. `GET /account-tags/`
never took `skip` / `limit` query parameters; only the internal DAO method lost them.

Value changes a client can see (none needs frontend work; the frontend shows these lists in server
order and does not re-sort them):

- `GET /account-tags/`: system tags first, then name case-insensitive, then id. Example: system
  `Utility`, `client`, `Bank`; user `bravo`, `Alpha`, `alpha`, `Charlie` →
  `Bank, client, Utility, Alpha, alpha, bravo, Charlie`. All active tags are returned (108 tags →
  108, not 100).
- `GET /account-tags/system/`: an inactive system tag is no longer listed; order name
  case-insensitive, then id. Not used by any frontend component today.
- `usage_count` in tag responses: now correct when two requests tag or untag at once (two users tag
  "Supplier" at 5 → 7, not 6).
