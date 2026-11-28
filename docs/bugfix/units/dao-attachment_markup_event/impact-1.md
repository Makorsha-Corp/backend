# Impact review, round 1: dao-attachment_markup_event

Date: 2026-11-28. Diff: `git diff origin/main -- app alembic` in the unit worktree
(one file, `app/dao/attachment_markup_event.py`; no migration).

## Change

- `list_for_attachment` (BUG-1436): `ORDER BY created_at DESC` becomes
  `ORDER BY created_at DESC, id DESC`.
- `list_for_attachment` (BUG-1437): `limit: int = 200` parameter and `.limit(limit)` removed.
  Signature now `(db, *, workspace_id, attachment_id) -> list[AttachmentMarkupEvent]`.
- New docstring (uncapped, newest first, id breaks ties). `create_event`, the singleton and the
  filter are untouched. No import change.

## Query shape (compiled, Postgres dialect, `scripts/bugfix/compile_query.py`)

```
SELECT attachment_markup_events.id, ... FROM attachment_markup_events
WHERE attachment_markup_events.workspace_id = 1 AND attachment_markup_events.attachment_id = 2
ORDER BY attachment_markup_events.created_at DESC, attachment_markup_events.id DESC
```

- ORM columns only; `created_at` before the table-qualified `.id`; exactly two `DESC`; no LIMIT,
  so the order part runs to the end of the statement (the precheck's SQL-text risk does not
  apply).
- Workspace bound (HR-16): the row's own `workspace_id` filter is unchanged.
- Index `(attachment_id, created_at)` still serves the filter and first key; the `id` tie-break
  is an incremental sort within equal `created_at` (cheap). The SQL itself is not the cost; see
  "Performance" below.

## Upstream

- Only caller in `app/`: `AttachmentMarkupManager.list_events`
  (`app/managers/attachment_markup_manager.py:337`), keyword call, never passed `limit`. Grep of
  `list_for_attachment` and `attachment_markup_event_dao` over `app/`, `scripts/`, `alembic/`:
  no other caller. No caller re-sorts or filters: the manager maps rows 1:1 in order to
  `AttachmentMarkupEventResponse` (`_to_event_response`).
- Service `AttachmentMarkupService.list_events` wraps the list in
  `AttachmentMarkupEventListResponse(items=...)` and commits; transaction contract unchanged (read).
- Endpoint `GET /attachments/{id}/markups/events` (`app/api/v1/endpoints/attachments.py:209`):
  404/400 mappings unchanged; no new error path (the removed `limit` could raise `DataError`
  only when passed directly, which nobody did).
- The manager's 404 for a deleted / non-ready attachment happens before the DAO call (R5 holds).
- Legacy `tests/test_attachment_markup.py` mocks the method without `limit`: unaffected.

## Downstream

None: one SELECT, no lock, no flush, no commit.

## Performance: the N+1 (BUG-2119) gets worse

`_to_event_response` calls `_resolve_user_name` → `profile_dao.get`, which is
`db.query(Profile).filter(id==...).first()` — a real statement per row, the identity map does
not short-circuit it. Today the cap bounded this at 200 reads; the fix removes the bound.

Measured (throwaway check on `bf_dao_attachment_markup_event_test`, worktree code, local Postgres,
5 authors, realistic `{"pages":[1,2,3]}` metadata and 36-char session ids, manager `list_events`
end to end plus JSON serialisation):

| Events on the attachment | SQL statements | Manager time | JSON body |
|---|---|---|---|
| 200 (today's max) | 205 | ~0.11 s | ~54 KiB |
| 1 000 | 1 005 | ~0.6 s | ~271 KiB |
| 5 000 | 5 005 | ~2.7 s | ~1.36 MiB |

Linear: ~0.55 ms and ~1 statement per event on localhost; over a network to a managed Postgres
each round trip costs more (1–2 ms typical), so 1 000 events is plausibly 1–2 s in production.

How many events are realistic: every PUT of one's own layer writes an event
(`markup_saved` / `markup_updated`, and BUG-2118 writes one even for an unchanged save), and the
frontend autosaves with a **400 ms debounce** (`markupAutoSaveScheduler.ts`,
`MARKUP_AUTOSAVE_DEBOUNCE_MS`). Every successful PUT/DELETE invalidates the
`AttachmentMarkupEvents` tag, so while the panel is open the **whole history is refetched after
every autosave**. A drawing marked actively by a few people can pass 200 events in a working
session and reach the low thousands over weeks. So the regression is real but gradual: no
attachment is slower than today until it passes 200 events, and the response grows ~270 bytes per
event.

Judgement: **not blocking.** The brief's intended behaviour (owner's ruling: logs are never
trimmed; BUG-982 precedent: paging, if needed, comes later at the endpoint) requires removing the
cap, and the fixer did exactly that. The cost sits in BUG-2119 (manager, its own unit) and in the
unpaged endpoint. But the PR **must call it out**:

- state the numbers above and that BUG-2119 turns 1 005 statements at 1 000 events into ~2–3;
- recommend the `managers-attachment_markup_manager` unit (BUG-2119) is planned in the next batch
  and merged soon after this one (bottom-up order allows it: this DAO is its dependency);
- mention the response-size growth and the refetch-on-every-autosave pattern (follow-up candidate
  below), so the owner can decide whether endpoint paging is needed before launch.

## API contract

No shape, status or message change. Value changes: more than 200 items possible; fixed order among
entries with equal `created_at`. Frontend (`MarkupEventLogPanel.tsx`, `formatMarkupEventDisplay.ts`
`groupEventsBySession`) uses the server order as given and groups **consecutive** entries by
`session_id`; it does not re-sort, slice or virtualise. A stable order makes the grouping stable
(before, an update could reshuffle tied entries and split a session group). Rendering a few
thousand short rows is fine for React; no frontend change needed. See `contract.md`.

## Database

No constraint, index or migration. No check script needed.

## Neighbouring bugs

- **BUG-2119** (manager N+1 profile reads): made worse in magnitude, see above. Not a clash; it
  is the fix that bounds the cost.
- **BUG-2118** (unchanged save writes `markup_updated`): inflates event counts, so it compounds
  the size growth; fixing it reduces both.
- **BUG-1435** (`app/dao/attachment_markup.py`, layer tie order): separate file, no overlap.
- BUG-2115/2116/2117/2120: unaffected.

## Shortcuts / scope

None. One function, exactly the two bugs. The docstring is the only extra and it is accurate.

## New bugs found

- Candidate (orchestrator to decide, owner range): pattern `unpaged-growing-list`, file
  `app/api/v1/endpoints/attachments.py` (`GET /attachments/{id}/markups/events`, with the
  frontend's `getAttachmentMarkupEvents` refetched on every autosave).
  Title: "Markup history is sent whole, and again after every autosave". Today (after this fix):
  the full history, ~270 bytes per entry, is returned and refetched after every 400 ms-debounced
  save; 1 000 entries ≈ 271 KiB per save. Intended: history paged at the endpoint (newest page
  first, `created_at DESC, id DESC` keyset) or only the newest page refetched after a save, per
  the BUG-982 precedent ("if a long history ever needs paging, it is added at the endpoint
  later"). Frontend part as a note in `bugs.md`. Low priority until BUG-2119 is fixed; then
  only the payload size remains.

## Verdict

**APPROVE.** No contract change for the frontend stage. PR must carry the performance note above.
