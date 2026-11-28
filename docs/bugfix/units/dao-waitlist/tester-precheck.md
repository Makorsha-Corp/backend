# Tester pre-check: dao-waitlist

Date: 2026-11-27 (batch 4). Source `app/dao/waitlist.py`. Spec `tests/unit/dao/waitlist.spec.md`.
Database `bf_dao_waitlist_test`.

Search: grepped the bare numbers `1410`, `1411` in `tests/**/*.py`. Markers are plain
`pytest.mark.xfail(strict=..., reason="BUG-14xx: ...")`; no helper constants. Files that use
`waitlist_dao` / `list_signups`:
- `E:\Projects\Makorsh-Corp\backend\tests\unit\dao\test_waitlist.py` (unit's own; targets)
- `E:\Projects\Makorsh-Corp\backend\tests\unit\services\test_waitlist_service.py` (targets, pass-through)
- `E:\Projects\Makorsh-Corp\backend\tests\test_waitlist.py`, `tests\test_waitlist_admin.py` (legacy; no target)

Run today with `--runxfail`: all 7 targets fail, each on the Then its card names.

Candidate fix swapped in with a scratch plugin (no `app/` edit): search escaped (`\` doubled,
then `%`, `_`) with `escape='\'`, and `ORDER BY created_at DESC, id DESC`. Over the 4 files:

| Candidate | Result |
|---|---|
| none (today) | 87 passed, 10 xfailed |
| candidate fix | 87 passed; exactly the 7 targets flip (5 strict now XPASS-strict, 2 non-strict XPASS); the 3 other xfails (BUG-1579, BUG-1580) unchanged |

## BUG-1410: `%`, `_` (and `\`) in the search act as wildcards

| File | Test | Strict | Fails today on |
|---|---|---|---|
| DAO | WLS-LS-04 (`a_b` vs `axb`) | yes | Then 2: `[A, B]` instead of `[A]` |
| DAO | WLS-LS-05 (`p%q` vs `pzzq`) | yes | Then 2: `[A, B]` instead of `[A]` |
| DAO | WLS-LS-06 (`c\d` vs `cd`) | yes | Then 2: `[B]` instead of `[A]` (Postgres's default `ILIKE` escape eats the backslash) |
| service | WSV-L-06 (pass-through `a_b`) | yes | Then 2: `[A, B]` instead of `[A]` |

Verdict: **right.** Each checks spec `list_signups` R2 exactly (literal `%`, `_`, `\`; substring,
case-insensitive), nothing extra. A correct fix passes all four; the bug fails each on the named line.
WLS-LS-06 needs the backslash itself escaped (HR-8 as written in the spec), so a fix that escapes
only `%` and `_` fails it, as intended.

## BUG-1411: tied `created_at`, no `id` tie-break

| File | Test | Strict | Fails today on |
|---|---|---|---|
| DAO | WLS-LS-15 (three tied rows, lowest id updated) | no | Then 2: `[B, C, A]` instead of `[C, B, A]` (physical order) |
| DAO | WLS-LS-16 (SQL text of the ORDER BY) | yes | Then 4: ORDER BY is `created_at DESC` only |
| service | WSV-L-07 (pass-through tie) | no | Then 2: same as WLS-LS-15 |

Verdict: **right.** R5 says `created_at` descending, then `id` descending, before paging. The
non-strict cards say so; WLS-LS-16 is the strict proof.
**Risk note for the systems engineer:** WLS-LS-16 is a SQL-text check (`".id"` in the ORDER BY part,
`created_at` before it, exactly two `DESC`, exactly one comma). The normal ORM fix
`order_by(created_at.desc(), id.desc())` passes it; a raw `text()` sort, a third sort key, or
`nulls_last()` wrappers that change the text could fail it.

## Wrong tests

None. `docs/bugfix/wrong-tests.md` left alone.

## Outside this unit

- No other open bug in `app/dao/waitlist.py`. Neighbours (out of scope, listed in the brief):
  BUG-1579 (schema), BUG-1580 (service), BUG-540, BUG-541 (`app/core/waitlist_admin.py`).
- Codebase convention for escaping: private `_escape_ilike` in `app/dao/help_ticket.py`,
  `app/dao/machine.py`, `app/dao/account_invoice.py`. A shared helper is follow-up F8.
