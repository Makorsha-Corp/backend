## Fix: waitlist search finds only what you typed, and the waitlist keeps a fixed order

**Fixes BUG-1410 and BUG-1411.** One file (`app/dao/waitlist.py`), no database change, no API change.

---

### What was wrong

**1. Some characters in the waitlist search acted as wildcards (BUG-1410). This is the one admins notice.**

On the platform's waitlist page, an admin types part of an email to find a signup. The database treats `_` as "any one character" and `%` as "anything", and the search text was passed in as is. So `_` and `%` stopped meaning themselves.

*Example:* the waitlist holds `rahim_k@shop.com.bd` and `rahimak@shop.com.bd`. An admin searches `rahim_k` and gets **both**. Searching just `%` returned **every** signup. A backslash went wrong too: searching `c\d` did not find `c\d@x.com` at all, and found `cd@x.com` instead.

**2. Signups made at the same moment came back in a random order (BUG-1411)**

The list is newest first, by signup time. Signups saved together share one timestamp, and then the database could return them in any order. The list could reshuffle between refreshes, and moving between pages could show a signup twice or skip it.

*Example:* three signups share the time 10:00:00 and the page size is 2. Page 1 shows Karim and Nadia; page 2 can show Nadia again, and Sumi is never seen.

---

### What changed

`app/dao/waitlist.py`:

```diff
+   _ILIKE_ESCAPE = "\\"
+   @staticmethod
+   def _escape_ilike(value): ...            # backslash doubled first, then % and _ escaped

-   term = f"%{search.strip().lower()}%"
-   query = query.filter(self.model.email.ilike(term))
+   term = f"%{self._escape_ilike(search.strip().lower())}%"
+   query = query.filter(
+       self.model.email.ilike(term, escape=self._ILIKE_ESCAPE)   # %, _ and \ match literally
+   )

-   query.order_by(self.model.created_at.desc())
+   query.order_by(self.model.created_at.desc(), self.model.id.desc())   # tie-break on id
```

The escape helper is the same as the one in the help-ticket, machine and account-invoice files
(house rule HR-8: search text is literal). The order follows house rule HR-6: every paged list
ends its sort with `id`. Here that is newest `id` first, to match "newest first".

### What you'll notice

- Searches that contain `_`, `%` or `\` return only the emails that really contain those characters, so these searches return fewer results than before. A `\` search now finds what it should. Searches without those characters return the same rows as before.
- Signups with the same time always come back in the same order, newest `id` first, and paging never repeats or skips one.
- Unchanged: the search is still on the email only, still ignores capitals and leading/trailing spaces; the status and product-updates filters and the total count work as before.

### What to look at when reviewing

- **Another private copy of the escape helper.** The brief asked for the same-file convention used by other DAOs; a shared helper for all DAOs is a separate follow-up. Object if you'd rather have the shared helper first.
- **Backslash is escaped too.** The spec asks for `\` to match literally, not only `%` and `_`. This is stricter than escaping just the two wildcards.
- **Not in this PR:** the waitlist page's search box says "Search email or name…" but only the email is searched. That is a frontend text issue and is logged separately.

---

<details>
<summary>Pipeline checks (for the record)</summary>

- **Impact review:** the only caller is `WaitlistService.list_signups` behind `GET /waitlist`, a straight pass-through. The endpoint already limits `skip`, `limit` and the search length. No other method in the file changed. The table is platform data (no workspace), so HR-16 does not apply.
- **Contract:** same inputs, status codes, messages and fields (`items`, `total`, `skip`, `limit`). Only the values change as described above. No frontend PR.
- **Tests:** the 7 tests marked as known failures for these bugs (waitlist DAO and waitlist service) now pass, and their markers are removed. Every other test in the full suite had the same result before and after (flip check CLEAN, base `092776b`).
- **Migrations:** none.
- **Commits:** `db3bb3f` (fix, marker removals, bugs.md), on `bugfix/dao-waitlist`, pushed.

</details>

## Code review

Code review: **PASS**, 0 blockers, 0 majors, 0 minors, 0 nits (strict independent review, `review-1.md`).
The reviewer checked `a_b`, `p%q`, `%`, `c\d` and backslash searches, and paging 3 at a time over 10 signups with the same timestamp: every row appears once.
