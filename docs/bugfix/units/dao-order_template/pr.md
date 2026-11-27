## Fix: expense order templates and their lines always come back in the same order

**Fixes BUG-1210 and BUG-1211.** One file, two one-line changes. No database change, no API change.

> ✅ **Good to auto-merge.** A small, low-risk ordering fix in one file. It changes no money, stock or workflow behaviour, changes no API, and every other test in the suite behaved the same before and after.

---

### What was wrong

**1. The template list could show a template twice and skip another (BUG-1210)**

The *Order templates* page lists templates newest first. Templates made at the same moment, for example several created by an import or a quick double-click, have the same creation time. The list only sorted by that time, so the database could return tied templates in any order, and the order could change between one page and the next.

*Example:* 5 templates created in the same second, shown 1 per page:
page 1 → template A, page 2 → **template A again**, page 3 → C, page 4 → D, page 5 → B. Template **E never appears**.

**2. A template's lines could change order (BUG-1211)**

A template's lines are sorted by line number. Two lines can end up with the same number, for example when two people add a line at the same time. Those lines had no fixed order, so they could swap places after any edit, and the expense order made from the template copied them in whatever order came back.

---

### What changed

`app/dao/order_template.py`. Each list now has a final "tie-breaker" sort on the row's id, so the order is always the same:

```diff
- .order_by(desc(OrderTemplate.created_at))
+ .order_by(desc(OrderTemplate.created_at), desc(OrderTemplate.id))      # newest first, then newest id

- .order_by(OrderTemplateItem.line_number)
+ .order_by(OrderTemplateItem.line_number, OrderTemplateItem.id)          # line number, then oldest line first
```

This follows house rule HR-6: every list that is paged or shown in order ends its sort with `id`.

### What you'll notice

- Paging through templates never repeats or skips one.
- Lines that share a line number always appear in the order they were added, on the template and on any expense order made from it.
- Nothing else changes: same filters, same page sizes, same responses.

### What to look at when reviewing

- The two `order_by` lines above. That's the whole change.
- The direction of each tie-breaker. Templates use newest-id-first, to match "newest first". Lines use oldest-id-first, to match "line 1, 2, 3".

---

<details>
<summary>Pipeline checks (for the record)</summary>

- **Impact review:**
  - Callers: `OrderTemplateManager.list_templates`, `add_item` (uses only the highest line number) and `get_items`.
  - `create_expense_order_from_template` re-sorts lines by line number with a stable sort, so it keeps the new tie-break. Nothing relied on the old order.
- **Contract:** no change. No frontend PR.
- **Tests:** the 7 tests that were marked as known failures for these bugs now pass, and their markers are removed. Every other test in the full suite (24,423 tests) had the same result before and after the fix (flip check CLEAN, base `d5fea1c`).
- **Seen, not fixed:** two lines can still get the same line number when added at the same instant. Preventing that needs a database constraint, so it's a separate change.
- **Commits:** `4fcd227` (fix), `15111ab` (merge of main for Postgres 18 CI).

</details>
