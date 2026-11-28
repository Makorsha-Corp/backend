# Code review 1: dao-waitlist (2026-11-27)
Verdict: PASS   (blockers: 0, majors: 0, minors: 0, nits: 0)
Diff reviewed: 092776b..db3bb3f, files: app/dao/waitlist.py (no alembic changes)

## 1. What a correct fix must do (written before reading the diff)

- **BUG-1410 (HR-8, R2/R2a):** the search text is escaped before it goes into
  the `ILIKE` pattern. The backslash must be doubled **first**, then `%` and
  `_` get a backslash in front, and the `ILIKE` must name `\` as its escape
  character. The `%...%` wrapper stays unescaped. The order matters: escaping
  `%` first and the backslash second would double the backslashes just added.
  Trimming and lower-casing stay as they are. `""` and `None` add no filter.
  `"   "` trims to `""` and gives a `%%` pattern that matches every row (R2a).
  Only `email` is searched. Expected results: `a_b` finds `a_b@…` and not `axb@…`;
  `%` finds only emails that contain `%`; `c\d` finds `c\d` and not `cd` or
  `c\\d`; `\` finds every email that contains a backslash.
- **BUG-1411 (HR-6, R5):** `ORDER BY created_at DESC, id DESC`, applied in SQL
  before `OFFSET`/`LIMIT`. With tied `created_at`, paging must not repeat or
  skip a row.
- **Must not change:** `total` is still the count after the filters and before
  paging (HR-5, R6). `limit=0` still gives `([], total)`, and a negative
  `skip`/`limit` still raises `DataError`. The status and
  `wants_product_updates` filters stay as they are. `get_by_email`,
  `create_signup`, `update_status`, the inherited `BaseDAO` methods and the
  `waitlist_dao` singleton are unchanged. Signatures and return types are
  unchanged. The helper is private to this file and follows the
  `app/dao/help_ticket.py` convention.

## 2. Findings

None.

Evidence collected (throwaway check against `bf_dao_waitlist_test`, one rolled-back
transaction, 10 rows inserted in it so they share one `created_at`):

| search | found (suffix stripped) |
|---|---|
| `a_b` | `a_b` only (not `axb`) |
| `p%q` | `p%q` only (not `pzzq`) |
| `%` | `p%q`, `q\%` |
| `_` | `a_b` |
| `c\d` | `c\d` only (not `cd`, not `c\\d`) |
| `\` | the four emails containing a backslash |
| `\\` | `c\\d` only |
| `\%` | `q\%` only |
| `" big"`, `BIG` | `BIG@…` |

- Tied timestamps: all 10 rows had 1 distinct `created_at`. The result came
  back in strict `id` descending order. Paging with `limit=3` over 4 pages
  returned all 10 ids, none repeated or missing. `limit=0` gave `([], 10)`.
- Compiled SQL: `WHERE email ILIKE %(email_1)s ESCAPE '\\' ORDER BY created_at DESC, id DESC`.
  The count runs on the filtered, unordered query.
- Convention: `_ILIKE_ESCAPE` / `_escape_ilike` are character-for-character the
  same as `app/dao/help_ticket.py:16-23`, and are used the same way as at
  `app/dao/help_ticket.py:147-152`.
- `ruff check app/dao/waitlist.py`: all checks passed.
- Scope: the only file changed under `app/` is `app/dao/waitlist.py`. The
  changes there are the helper plus the two lines in `list_signups`; the other
  methods are untouched. There is no sibling method in the file that searches
  or pages. The caller `WaitlistService.list_signups`
  (`app/services/waitlist_service.py:114-124`) passes keyword arguments
  through unchanged, so it is unaffected.

## 3. Questions (unproven)

- None that need action. Note: `search.strip().lower()` is kept from before.
  Lower-casing is redundant under `ILIKE`, and for a few Unicode characters
  (for example `İ`) it could change what is matched. The lower-casing is
  spec R2 behaviour and was there before this change, so it is not a finding.

## 4. What is good

- The escape order is right (backslash first), and the escape character is
  passed to `ILIKE`, so a literal `\` works as R2 requires.
- The change is minimal: the order fix is one line, and the helper matches the
  existing DAO convention exactly instead of inventing a variant.
