# House rules

Product-wide behavior decisions made during spec review. The test describer
applies these **without asking**: code that breaks a rule is recorded as a bug
against the rule, and the spec states the rule's behavior as intended.

A reviewer can still override a rule for one module by answering that module's
item differently — note why. To change a rule for everyone, edit it here.

Each rule lists the reviewed bugs it came from.

## Names and free-text values

**HR-1. Names are trimmed and never blank.**
User-entered names/labels are stored with leading/trailing whitespace removed.
Blank or whitespace-only values are rejected by the Pydantic schema (422), so
every entry point gets the check. Inner whitespace and case are kept as typed.
*(BUG-004)*

**HR-2. Name uniqueness is real uniqueness.**
Where names must be unique (per workspace, among live rows):
- compare case-insensitively after trimming ("Sales" = " sales ");
- check against **all** live rows — never a paginated/capped fetch;
- soft-deleted rows do not count (their name can be reused);
- enforce in the database too (partial unique index on live rows, normalised
  name); a violation surfaces as 409, never 500.
*(BUG-001, BUG-002, BUG-003)*

**HR-3. Categorical free text is normalised.**
Free-text values used for grouping/filtering (units, similar codes) are stored
trimmed, filtered and grouped case-insensitively, and displayed lowercase.
*(BUG-017)*

## Soft delete

**HR-4. Soft-deleted rows are hidden unless asked for.**
- `get` by id returns 404 for a soft-deleted row by default; an
  `include_deleted=True` option returns it.
- Lists/searches exclude soft-deleted rows by default; where an
  `include_deleted` option exists it is reachable from the API.
- Filters, joins and searches through related rows ignore related rows that are
  soft-deleted (e.g. a deleted tag neither filters nor matches).
- **Scope:** enforced where API-facing behavior lives — managers and
  module-specific DAO query methods. The generic `BaseDAO` methods (`get`,
  `get_by_id_and_workspace`, `get_by_workspace`, `get_multi`) stay raw and DO
  return soft-deleted rows, because callers like "already deleted → 400" checks
  and `restore` need them. Do not flag inherited BaseDAO calls as HR-4
  violations; flag the manager method that exposes the result.
*(BUG-005, BUG-010, BUG-014, BUG-015; scope set in BaseDAO spec review)*

## Lists, search, pagination

**HR-5. Filter first, then page.**
All filtering (soft-delete, search, flags) happens in the query before
`skip`/`limit`. A page is only short when there are no more results. Search
covers the whole scope, not the current page.
*(BUG-006, BUG-007)*

**HR-6. Every paged or top-N result has a stable order.**
Default: name case-insensitive ascending, then `id` ascending. Score-ranked
results break ties the same way. Generic `BaseDAO` lists only guarantee `id`
ascending (stable paging); choosing a display order is the manager's job.
*(BUG-008, BUG-018; BaseDAO scope set in BaseDAO spec review)*

**HR-7. `limit` is at least 1.**
List endpoints require `limit >= 1` (422 otherwise).
*(BUG-016)*

**HR-8. Search text is literal.**
Text placed in `LIKE`/`ILIKE` patterns is escaped: `%` and `_` match literally.
Digit-only shortcuts (e.g. "search also matches id") accept ASCII `0-9` only and
never raise on other input.
*(BUG-012, BUG-013)*

## Audit and state

**HR-9. Audit stamps mean something changed.**
`updated_by` (and similar "last changed by" fields) is written only when at
least one field actually changes value.
*(BUG-009)*

**HR-10. Harmful state transitions lock the row.**
A method that checks a row's state and then changes it reads the row with a
row lock (`SELECT … FOR UPDATE`) **when a race would cause real harm**: money
(payments, invoices, refunds), stock quantities, approvals/decisions, or
duplicate side effects (events, emails, external calls). The loser sees the new
state and gets the normal "wrong state" error.
Plain soft deletes, restores and renames do **not** need a lock — the worst a
race does there is overwrite an audit stamp.
*(payment spec Q11; narrowed by reviewer after department cases gap 6)*

## External systems and background jobs

**HR-11. Verified results beat unverified ones.**
A result verified server-to-server with an external system (e.g. payment gateway
validation) is authoritative. Signals that cannot be verified (browser
redirects, timeouts, sweeps finding nothing) never make a record final: a later
verified result replaces them. Input that fails verification (unknown or foreign
ids) is logged and ignored — it never changes the record.
*(payment spec Q5, Q8, Q9)*

**HR-12. When in doubt about money, hold — don't pass or silently fail.**
If an external confirmation is missing data needed to verify it (amount,
currency), the record goes to manual review (e.g. `RISK_HOLD`), not success.
*(payment spec Q6)*

**HR-13. Record every attempt.**
Calls to external systems that start a business process leave a record even
when the external system refuses, including the reason.
*(payment spec Q1)*

**HR-14. Batch jobs isolate failures.**
A background sweep/batch that processes many rows handles each row
independently: one row's error is logged and skipped, the rest still complete
and are saved.
*(payment spec Q14)*

## Money and workspaces

**HR-15. Money rounds half up.**
All money rounds half away from zero, everywhere (0.125 → 0.13, -1.005 → -1.01),
matching the database's `Numeric` columns. Python `quantize` passes
`ROUND_HALF_UP`; its default, half to even, is a bug.
*(owner, 2026-10-30; BUG-1040)*

**HR-16. Nothing links across workspaces.**
A row linking to another workspace's row is invalid data, never a normal state.
Every write that sets such a link refuses it, as "not found", and no response
shows another workspace's ids or names. A refused delete that finds such a row
shows one generic `{"type": "other_workspace"}` blocker, with no id.
*(owner, 2026-10-30; BUG-948, BUG-968, BUG-1010 … BUG-1023)*
