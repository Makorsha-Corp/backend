# Impact review: dao-help_ticket (round 1, 2026-11-27)

Diff: worktree `E:\Projects\Makorsh-Corp\bugfix-worktrees\dao-help_ticket`, `git diff origin/main -- app alembic` (base `614bbce`). Only `app/dao/help_ticket.py` changed. No migration.

## Changes reviewed

| Function | Change | Bug |
|---|---|---|
| `create_with_user` | `datetime.now().year` → `utcnow().year` (module import `from app.utils.time import utcnow`); unused `from datetime import datetime` removed | BUG-1441 |
| `list_by_workspace`, `list_platform` | `ORDER BY created_at DESC` → `created_at DESC, id DESC`, still before offset/limit | BUG-1442 |
| `list_platform` | trimmed search escaped (`\` first, then `%`, `_`) via new `_escape_ilike`; all four `ilike` calls pass `escape="\\"` | BUG-1443 |

## Upstream

- `help_ticket_dao` callers: `HelpTicketManager.list_tickets` / `list_platform_tickets` / `create_ticket` / `get_by_id_and_workspace` / `get_platform_ticket` / `update_ticket`; `HelpTicketService` (`get_by_id` refreshes only); `AttachmentManager` (entity map, base lookup only). Endpoints: `GET/POST /help-tickets/` (`help_tickets.py`), `GET /platform/help/tickets` (`platform_help.py`).
- No caller re-sorts, de-duplicates or set-converts the lists: the manager maps rows 1:1 (`_to_platform_item`), the service maps 1:1 (`to_response`). New tie-break reaches the endpoint intact.
- No caller depends on wildcard search: the manager/service pass `search` straight through; the endpoint only caps it at 200 chars. Trimming and the `if search:` skip are unchanged, so `None`, `""` and spaces-only behave as before (spec R3, R4).
- No change in return types, errors or flush/commit behaviour. `create_with_user` still flushes only; the service commits (TC rules unaffected).
- OQ-66 / BUG-3251 (who may change status) lives in `update_ticket` / the manager's permission helpers; this diff does not touch those paths and nothing there reads order or search.

## Downstream

- `app.utils.time.utcnow` returns naive UTC; only `.year` is read. Fine.
- `generate_ticket_number` unchanged (BUG-1440 stays out of scope, as the brief says); its `LIKE f"{prefix}%"` uses an int year, so no escaping issue.
- No locks involved.

## Query shape (compiled, Postgres dialect)

`list_platform(status="pending", search=…)`: `WHERE status = 'pending' AND (title ILIKE … ESCAPE '\' OR ticket_number ILIKE … ESCAPE '\' OR description ILIKE … ESCAPE '\' OR workspaces.name ILIKE … ESCAPE '\') ORDER BY help_tickets.created_at DESC, help_tickets.id DESC LIMIT … OFFSET …`. AND/OR precedence correct; ORDER BY uses ORM columns; `\`, `%`, `_` escaped in the term.

Database check (rowkit, marker_test, rolled back; script in my scratchpad): `X_Y` finds only ticket number `HELP-X_Y` (not `HELP-XZY`); `5%` finds only description `5%off` (not `5 off`); case-insensitive still works (`x_y`); spaces-only and `None` return all; workspace name `Acme_Ltd` matched by `e_L`; `list_by_workspace` returns highest id first on tie. This covers the three fields the target tests do not exercise (pre-check coverage note).

## Workspace bound (HR-16)

No new join or subquery. `list_by_workspace` still filters `workspace_id`; `list_platform` is cross-workspace by design (platform admins only, endpoint dependency `get_platform_admin`).

## Shortcuts / helper copy

- `_ILIKE_ESCAPE` and `_escape_ilike` are a verbatim copy of `AccountInvoiceDAO`'s. Under the one-file rule (brief §5: only this file may change) a copy is the only option that stays in scope; importing the private helper from `AccountInvoiceDAO` would couple two unrelated DAOs through a private name, which is worse. **Acceptable for this unit.** Follow-up (not blocking): 9 other DAOs still use unescaped `ilike` (only `account_invoice.py` passes `escape=`). As more `unescaped-like-wildcards` units land the copy will multiply; the planner should consider one small shared-helper unit (e.g. `app/utils/search.py`, then migrate the copies) once a few have merged.
- Escaping is applied to every one of the four fields through the single shared `term`; no field-specific shortcut.

## Tests interplay

- The `create=True` correction from `wrong-tests.md` (BUG-1441 entry) is on `origin/main` (`614bbce`): `tests/unit/dao/test_help_ticket.py:146`, `tests/unit/services/test_help_ticket_service.py:263`, `tests/unit/managers/test_help_ticket_manager.py:246`. So removing the unused `datetime` import is safe and BUG-1441 stays in the unit.

## API contract

No shape, status or message change. Visible value changes: platform search with `%`, `_`, `\` now matches literally; tied tickets now come back highest id first. See `contract.md`. Frontend `PlatformSupportPage.tsx` sends the trimmed search box text as `search`; it does not sort or re-filter. `HelpPage.tsx` sends no search. No frontend change.

## Database

No schema change, no constraint. No check script needed.

## Neighbouring bugs

- BUG-1440 (numbering race): untouched, not made worse.
- BUG-1577, BUG-1578, BUG-3250, BUG-3251, BUG-3270 (manager): independent of this diff.
- BUG-100 (base `get_by_workspace` no order): not used by these paths.

## Scope

Nothing changed beyond the three bugs (the removed import is a direct consequence of BUG-1441).

## New bugs found

None.

## Verdict

**APPROVE.** Contract change: no.
