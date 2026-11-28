## Fix: "My invitations" finds invitations whatever the email's capitals, and invitation lists come back newest first

**Fixes BUG-1401 and BUG-1402.** One file (`app/dao/workspace_invitation.py`). No database change, no API shape change.

Not marked "Good to auto-merge": the email match fix (BUG-1402, `case-sensitive-email-match`) is not a pattern on the trivial list, and it changes which invitations a person sees, so the owner should look at it.

---

### What was wrong

**1. A person whose account email has capitals saw an empty "Invitations" panel (BUG-1402). This is the one people notice.**

Invitations are saved with the email in lower case. Accounts keep the capitals the person typed when registering. The "my invitations" list compared the two exactly, so they never matched. Accepting through the link in the email already worked, because that check ignores capitals. Only the panel in the app was empty.

*Example:* the owner of "Rahman Textiles" invites `john.doe@example.com` as a manager. John registered as `John.Doe@example.com`. He opens the app, and his Invitations panel is empty, even though the email link would let him join. After this fix he sees the invitation from Rahman Textiles.

**2. Invitation lists had no fixed order (BUG-1401)**

A workspace's invitation list (pending only, or with expired ones included) and a person's "my invitations" list had no sort at all. The database returned rows in whatever order it liked. After an invitation was edited, it could move to the bottom.

*Example:* invitations sent on Monday, Wednesday and Tuesday could come back as Monday, Tuesday, Wednesday one time and in another order after a change. Now they always come back Wednesday, Tuesday, Monday.

---

### What changed

All in `app/dao/workspace_invitation.py`:

```diff
+ from sqlalchemy import func

  # all three invitation lists (workspace pending, workspace all, my invitations)
+ .order_by(WorkspaceInvitation.invited_at.desc(), WorkspaceInvitation.id.desc())   # newest first, id breaks ties

  # my invitations
+ normalized_email = email.strip(" ").lower()                                       # the account email, trimmed and lower-cased
- WorkspaceInvitation.email == email,
+ func.lower(func.trim(WorkspaceInvitation.email)) == normalized_email,            # the stored email, trimmed and lower-cased the same way
```

The rules behind it: house rule HR-6 (every list ends its sort with `id`; dated lists are newest first), and the decision, made by Claude under the reviewer's delegation, that the email is matched ignoring case and surrounding spaces on both sides. That decision agrees with the owner's answer that an email identifies one account whatever its capitals.

### What you'll notice

- "My invitations" now shows invitations whose email differs from the account email only in capitals (or in spaces around it). These are exactly the invitations the person could already accept through the email link.
- Both invitation lists show the newest invitation first. Two invitations sent at the same moment show the later-created one first.
- Deliberately unchanged: the match is still a whole-email comparison. `doe@example.com` does not find `john.doe@example.com`'s invitation, and `_` is an ordinary character. Looking up an invitation by its link token, and the count of open invitations against the plan's member limit, are unchanged.

### What to look at when reviewing

- **Only the space character is trimmed.** The database's `trim()` removes spaces only, so the account email is trimmed the same way in Python (`strip(" ")`), not with a bare `strip()`. Tabs and newlines can't reach either side, because emails are validated on the way in. Object if you'd rather have tabs and newlines trimmed too.
- **The accept check doesn't trim.** If a stored invitation email ever had spaces around it (only possible through a manual database write or an import, since the app never saves one), it would now be listed but accepting it would still fail. That belongs with the workspace manager unit, not this file.
- **No index on the email.** The new comparison can't use an index, but there was none before either. The list is also filtered by status (indexed) and expiry, and the table holds only open invitations, so it stays small. A functional index would need a migration.
- **Possible duplicates.** If the same person was invited twice (BUG-1873/1874, still open), "my invitations" may now show both. That is correct for this list; the duplicates are the manager unit's problem.

---

<details>
<summary>Pipeline checks (for the record)</summary>

- **Impact review:** the only callers are the workspace service's `list_invitations` (`GET /workspaces/{id}/invitations/`) and `get_my_invitations` (`GET /workspaces/me/invitations/`). Both keep the order the database gives and don't re-sort. No other code uses these three methods.
- **Contract:** same response shape, status codes and messages. Only the order and the set of matched invitations change. The frontend (`workspaceApi.ts`) shows the lists as returned and needs no change, so there is no frontend PR.
- **Tests:** the 13 tests marked as known failures for these bugs (workspace invitation DAO and workspace service) now pass, and their markers are removed. Every other test in the full suite had the same result before and after (flip check CLEAN, base `092776b`).
- **Database:** no migration; one Alembic head.
- **Commits:** `c6b9a87` (fix, marker removals, bugs.md; pushed).

</details>

## Code review

Code review: **PASS**, 0 blockers, 0 majors, 1 minor, 0 nits (strict independent review, `review-1.md`).

Minor, for you to decide:
- **R1-1:** "My invitations" lower-cases the typed email in Python but the stored email in Postgres. They disagree on a few rare non-ASCII capitals (`İ`, `ẞ`); common letters such as `É` agree. With such a letter, someone could accept an invitation that their list doesn't show (the accept path lower-cases both sides in Python). Real email addresses almost never contain these letters, so this is safe to merge as is; a later fix would lower-case both sides in the same place.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
