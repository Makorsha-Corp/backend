## Fix: failed uploads no longer use up a record's 25 attachment places, and attachment lists keep a fixed order

**Fixes BUG-1432, BUG-1433 and BUG-1434.** One file, four small changes. No database change, no API shape change.

---

### What was wrong

**1. A failed upload took one of the record's 25 places forever (BUG-1434). This is the one users feel.**

Every record (a purchase order, a help ticket, …) can hold up to 25 attachments. When an upload fails, for example the network drops or the file is rejected, the attachment is kept in the database with the status *failed*. It's hidden from the attachment list, but **it was still counted toward the 25**.

*Example:* a purchase order has 20 photos and 5 uploads that failed. The panel shows **"25/25 attachments: delete one to add more"**, but the user sees only 20 files and has nothing to delete. The record is stuck.

**2. Attachments uploaded at the same moment came back in random order (BUG-1432)**

The attachment list is newest first, but attachments uploaded together (a multi-file upload) share one upload time. The database could return those in any order, so the list could reshuffle, and paging could repeat or skip a file.

**3. An attachment's links had no order (BUG-1433)**

One attachment can be linked to several records. The code treats "the first link" as the attachment's main record when writing its history entry, but the links weren't sorted. So "the first link" could be a different record each time.

---

### What changed

All in `app/dao/attachment_link.py`:

```diff
  # the 25-attachment count
    Attachment.is_deleted == False,
+   Attachment.upload_status != "failed",          # failed uploads no longer count

  # the attachment list
- .order_by(Attachment.uploaded_at.desc())
+ .order_by(Attachment.uploaded_at.desc(), Attachment.id.desc())   # tie-break on id

  # an attachment's links
+ .order_by(AttachmentLink.id.asc())               # the first link is the one made first
```

Uploads still **in progress** keep their place, so two people uploading at once can't overshoot the limit. Deleted attachments still never count.

### What you'll notice

- The *X/25 attachments* counter matches the files the user can actually see, plus any uploads still in progress. A record full of failed uploads is no longer stuck.
- The upload limit is reached only when 25 attachments are ready or in progress.
- Lists of attachments keep the same order every time.

### What to look at when reviewing

- **The new count rule.** "Failed doesn't count, in progress does" is the intended behaviour from the spec.
- **One side effect we accepted.** If someone retries a failed upload directly through the API, the record can end up with 26 rows, because the retry path doesn't re-check the limit. The limit is a soft cap against clutter, the browser never does this, and two parallel uploads at 24 can already reach 26. It's recorded as a delegated decision. Say so if you'd rather have a hard cap.
- **Right now the change is small in practice.** Two other open bugs (BUG-2095, BUG-2204) keep most failed uploads marked as *pending*, so they still count until those are fixed.

---

<details>
<summary>Pipeline checks (for the record)</summary>

- **Impact review:**
  - The capacity check is reached from `POST /attachments/sign` and phone-upload promote.
  - `slot_count` in `GET /attachments/` is the shown counter.
  - The attachment ledger uses the first link. Nothing relied on the old count or order.
  - The frontend (`AttachmentPanel.tsx`) already handles the new value, so there is no frontend PR.
- **Contract:** same response shape and messages. `slot_count`'s value now excludes failed uploads.
- **Tests:** the 12 tests marked as known failures for these bugs (DAO, attachment manager and attachment service) now pass, and their markers are removed. Every other test in the full suite had the same result before and after (flip check CLEAN, base `d5fea1c`).
- **Follow-up:** once BUG-2095/2204 are fixed, failed rows will pile up, still holding Cloudinary files. The planned clean-up job should remove them; this is noted in `docs/future/subscription-payments.md`.
- **Commits:** `11db000` (fix), `63122d1` (merge of main for Postgres 18 CI).

</details>
