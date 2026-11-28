# Contract note: dao-waitlist

**No contract change** (frontend stage skipped).

`GET /waitlist` keeps the same inputs, status codes, error messages and response fields
(`items`, `total`, `skip`, `limit`). Two value-level differences, both corrections the frontend
does not depend on:

- Search text is literal. Example: searching `a_b` used to return `a_b@x.com` and `axb@x.com`;
  now only `a_b@x.com`. Searching `%` used to return every signup; now only emails containing `%`.
  The frontend sends the box text as typed (trimmed) and never used wildcards.
- Signups with the same `created_at` now come back in a fixed order (newest id first), so paging
  never repeats or skips one. The page already shows rows in the order received.
