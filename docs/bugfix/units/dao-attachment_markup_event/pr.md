## Fix: a drawing's markup history now shows every entry, in a fixed order

**Fixes BUG-1437 and BUG-1436.** One file. No database change. No API shape change. The history can now hold more than 200 items, and entries with the same time always come back in the same order.

---

### What was wrong

**1. The markup history stopped at the 200 newest entries and gave no sign of it (BUG-1437). This is the one that matters most.**

Every save of someone's markup layer on an attachment (a drawing, a photo of a part, …) writes an entry in that attachment's history. The history panel shows those entries. The server returned only the newest 200, with no "more" link and no count, so anything older disappeared without a trace.

*Example:* two engineers mark up the drawing for a 4,50,000 taka pump order over three weeks, and the drawing collects 260 history entries. Someone opens the history to see who first circled the flange size. The 60 oldest entries, including that first markup, aren't there, and nothing on the page says the list is cut short. The owner ruled that logs are history and are never trimmed.

**2. Entries saved at the same moment came back in a random order (BUG-1436)**

The history is newest first, but the clock is coarse enough that several entries often share one time (autosave writes them fast). Among those, the database could return any order, and an update to one row could reshuffle them. The panel groups entries of one editing session that sit next to each other, so a reshuffle could split one session into two groups.

*Example:* Rahim's three autosaves at 10:42:07 show as "Rahim, 3 changes" on one load, and as "Rahim, 1 change / Karim … / Rahim, 2 changes" on the next.

---

### What changed

`app/dao/attachment_markup_event.py`, the function that reads an attachment's history:

```diff
         attachment_id: int,
-        limit: int = 200,                                   # the hidden cap, removed (nobody passed it)
     ) -> list[AttachmentMarkupEvent]:
 ...
-            .order_by(AttachmentMarkupEvent.created_at.desc())
-            .limit(limit)                                   # no more silent cut at 200
+            .order_by(
+                AttachmentMarkupEvent.created_at.desc(),    # newest first, as before
+                AttachmentMarkupEvent.id.desc(),            # same time: the later-written entry first
+            )
```

Plus a short docstring saying the list is uncapped and ordered newest first with `id` breaking ties. The ordering follows house rule HR-6 (every list ends its sort with `id`). Removing the cap follows the owner's ruling that logs are never trimmed; if a long history needs paging later, it's added at the endpoint (the BUG-982 precedent). The unused `limit` parameter is removed too, which was already on the dead-code checklist (now ticked).

### What you'll notice

- Attachments with more than 200 history entries now show all of them. Attachments with 200 or fewer look exactly the same.
- Entries with the same time always appear in the same order, so session groups in the history panel no longer split or jump around.
- Unchanged: who can see the history, the workspace check, the response shape, and the errors for a deleted or not-yet-uploaded attachment.

### What to look at when reviewing

- **Performance: the history read now costs one extra query per entry, with no upper bound (BUG-2119).** The manager looks up the author's name with a separate database query for each history entry. The 200 cap used to limit that to 200 queries; now it grows with the history. The systems engineer measured the full history read (manager plus JSON) on localhost:

  | Entries on the attachment | Queries | Time | Response size |
  |---|---|---|---|
  | 200 (today's maximum) | 205 | ~0.11 s | ~54 KiB |
  | 1,000 | 1,005 | ~0.6 s | ~271 KiB |
  | 5,000 | 5,005 | ~2.7 s | ~1.36 MiB |

  Over a network to a managed Postgres each query costs more, so 1,000 entries is plausibly 1–2 s in production. No attachment gets slower than today until it passes 200 entries, but a drawing that several people mark up actively can reach that in one working session and the low thousands over weeks. **Recommendation: plan the BUG-2119 manager fix (`managers-attachment_markup_manager`) in the next batch and merge it soon after this one.** It reads the authors together, so 1,005 queries at 1,000 entries becomes about 2–3.
- **Response size and refetching.** The panel refetches the whole history after every autosave (400 ms debounce), at about 270 bytes per entry. After BUG-2119 this payload is the remaining cost. The systems engineer suggests paging the history endpoint as a follow-up (low priority until BUG-2119 is fixed); say if you want it before launch. BUG-2118 (an unchanged save still writes a history entry) adds to the entry count, so fixing it helps too.
- **Removing the cap rather than raising it** is the owner's ruling (logs are never trimmed). Object if you'd rather have a cap plus paging in this PR.

## Code review

Code review: **PASS**, 0 blockers, 0 majors, 0 minors, 1 nit (strict independent review, `review-1.md`).

Nit: the new docstring on `list_for_attachment` is the only docstring in the file (accurate, fine to keep).

---

<details>
<summary>Pipeline checks (for the record)</summary>

- **Impact review:** the only caller is `AttachmentMarkupManager.list_events`, used by `GET /attachments/{id}/markups/events` through `AttachmentMarkupService.list_events`. It never passed `limit` and maps the rows 1:1 in order. No other caller in `app/`, `scripts/` or `alembic/`. The workspace filter is unchanged (HR-16). The existing `(attachment_id, created_at)` index still serves the query.
- **Contract:** no shape, status or message change. Values: more than 200 items possible, and a fixed order among ties. The frontend (`MarkupEventLogPanel.tsx`) uses the server order as given and doesn't slice, so there's no frontend PR (`contract.md`).
- **Tests:** the 5 tests marked as known failures for these two bugs (history DAO and markup manager) now pass, and their markers are removed. Every other test in the full suite had the same result as before (flip check CLEAN, base `092776b`; 30 ordering tests elsewhere that may pass either way by chance were ignored, as designed). The unit's own and its callers' test files: 165 passed, 114 known failures still marked for other bugs.
- **Commits:** `af94ef0` (fix, marker removals, bugs.md and dead-code checklist), on branch `bugfix/dao-attachment_markup_event`.

</details>
