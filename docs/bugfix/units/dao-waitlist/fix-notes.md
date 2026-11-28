# Fix notes: dao-waitlist

## Round 1 (2026-11-27)

Worktree: `E:\Projects\Makorsh-Corp\bugfix-worktrees\dao-waitlist` (branch `bugfix/dao-waitlist`). Not committed.

### Changed

Only `app/dao/waitlist.py`.

- **BUG-1410**, `WaitlistDAO`:
  - Added the class attribute `_ILIKE_ESCAPE = "\\"` and a private staticmethod `_escape_ilike(value: str) -> str`. They copy `app/dao/help_ticket.py`: the backslash is doubled first, then `%` and `_` each get a backslash in front.
  - `list_signups`: the search term is now `f"%{self._escape_ilike(search.strip().lower())}%"` and the filter is `email.ilike(term, escape=self._ILIKE_ESCAPE)`.
- **BUG-1411**, `WaitlistDAO.list_signups`: the order is now `created_at.desc(), id.desc()`, set before `offset` / `limit`.

No imports added or removed. Signatures and return types are the same.

### Why

- **BUG-1410:** escaping the backslash first, and giving Postgres `ESCAPE '\'`, makes `%`, `_` and `\` in the search text match literally (HR-8, R2). The trim and lower-casing happen before escaping, as before. So the R2a cases are unchanged: `""` still applies no filter, and `"   "` becomes `"%%"` and matches every row.
- **BUG-1411:** `id` is unique, so `created_at DESC, id DESC` is a fixed order even when signups share one `now()`. Paging can no longer repeat or skip a row (HR-6, BUG-1210 precedent).

### Reproduction (throwaway check in the session scratchpad, now deleted)

Run with rowkit against `bf_dao_waitlist_test`. It inserted six signups in one transaction, so they all share one `created_at`: `zzqa_b@x.com`, `zzqaxb@x.com`, `zzqp%q@x.com`, `zzqpzzq@x.com`, `zzqc\d@x.com`, `zzqcd@x.com`.

| Check | Before | After |
|---|---|---|
| search `a_b` | `a_b`, `axb` (FAIL) | `a_b` only (OK) |
| search `p%q` | `p%q`, `pzzq` (FAIL) | `p%q` only (OK) |
| search `c\d` | `cd` only; the real `c\d` row was missed (FAIL) | `c\d` only (OK) |
| search `%` | all six (FAIL) | `p%q` only (OK) |
| order with one shared `created_at` | ids `649..654` ascending (FAIL) | ids `666..661` descending (OK) |
| pages of 2 walked with skip 0/2/4 | `650, 649, 651, 652, 653, 654`: unstable (FAIL) | strictly id descending, each row once (OK) |

Ids differ between runs because each run inserts new rows (rolled back) and the sequence moves on.

Also run: `python -c "import app.main"` imports OK. `ruff check app/dao/waitlist.py` (project config) passes with "All checks passed!".

### Assumptions

- I kept `.lower()` on the search term as the spec says. It changes nothing for matching (ILIKE ignores case) or for the escape characters.
- I wrapped the one new filter line over three lines to keep it under 88 characters. No other lines were touched.

### Seen, not fixed

- With `--select E501`, ruff reports two lines in the file over 88 characters: the class header and the `wants_product_updates` filter. Both were there before. The project's ruff config does not enable E501, so I left them alone.

### Risk

- Low. A search with no `%`, `_` or `\` gives the same SQL as before, apart from the `ESCAPE '\'` clause. Callers that relied on `%` / `_` as wildcards would see fewer results, which is what the fix intends.
