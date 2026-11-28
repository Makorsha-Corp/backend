# Tester pre-check: dao-workspace_invitation

Date: 2026-11-27. Base: main checkout, `app/dao/workspace_invitation.py` identical to `origin/main`.
Database: `bf_dao_workspace_invitation_test`. Run: the 13 target tests with `--runxfail -rf`: **13 failed today**, each on the line its card names.

**Verdict: both bugs go ahead. No wrong tests.**

## BUG-1401 (invitation lists have no sort order): RIGHT

| Test | Kind | Rule | Fails today on |
|---|---|---|---|
| `tests/unit/dao/test_workspace_invitation.py::test_wsi_gp_06__newest_invitation_first_and_on_a_tie_the_higher_id_first` | non-strict | `get_pending_invitations` R4 | Then 2 (`[1, 2, 3, 4]` vs `[4, 2, 1, 3]`) |
| `...::test_wsi_gp_07__the_query_orders_by_invited_at_then_id_both_descending` | strict | `get_pending_invitations` R4 | Then 2 (no `ORDER BY`) |
| `...::test_wsi_ui_08__newest_invitation_first_and_on_a_tie_the_higher_id_first` | non-strict | `get_user_invitations` R4 | Then 2 |
| `...::test_wsi_ui_09__the_query_orders_by_invited_at_then_id_both_descending` | strict | `get_user_invitations` R4 | Then 2 |
| `...::test_wsi_ga_05__newest_invitation_first_and_on_a_tie_the_higher_id_first` | non-strict | `get_all_invitations` R3 | Then 2 |
| `...::test_wsi_ga_06__the_query_orders_by_invited_at_then_id_both_descending` | strict | `get_all_invitations` R3 | Then 2 |
| `tests/unit/services/test_workspace_service.py::test_wss_li_07__invitation_query_ordered` | strict | `list_invitations` R4 (pass-through) | Then 2 (no `ORDER BY`) |
| `...::test_wss_mi_07__invitation_query_ordered` | strict | `get_my_invitations` R1 (pass-through) | Then 2 |

- The row-order cards use `invited_at` T2, T3, T1, T3 for A, B, C, D and expect `[D, B, A, C]`: exactly `invited_at` descending, `id` descending on the tie. Matches the row ("newest first, `invited_at` descending, then `id` descending") and HR-6.
- Non-strict on the physical-order cards is right (the card says today's order can match by accident); the strict SQL-text cards are the proof.
- **SQL-text risk for the systems engineer:** the DAO strict cards check the text after `ORDER BY`: contains `invited_at` before `.id`, exactly two `DESC`, exactly one comma. A normal ORM `order_by(WorkspaceInvitation.invited_at.desc(), WorkspaceInvitation.id.desc())` passes. A raw `text()` sort without the table prefix, a third sort key, or `NULLS LAST` style extras would fail (`invited_at` is NOT NULL, so none is needed). The service cards only need some statement on `workspace_invitations` with `ORDER BY`.
- No dependency on another unfixed bug (`WSS-MI-06`, BUG-2252, is a separate test and stays xfailed).

## BUG-1402 ("my invitations" is case-sensitive on the email): RIGHT

Settled check: the row's intended behaviour is decided (Claude, delegated, 2026-11-03) and states it is independent of the account-email question. That question is OQ-1, and it is **answered** (owner, 2026-11-04: an email identifies one account whatever its capitals; BUG-1860–1862 in `profile.py`). BUG-1402 is consistent with it and shows a person only invitations they can already accept (the accept check is case-insensitive). Nothing parked.

| Test | Kind | Rule | Fails today on |
|---|---|---|---|
| `tests/unit/dao/test_workspace_invitation.py::test_wsi_ui_02__the_email_is_matched_ignoring_case_on_the_argument_side` | strict | `get_user_invitations` R2 | Then 2 (`[]`) |
| `...::test_wsi_ui_03__the_email_is_matched_ignoring_surrounding_spaces_on_the_argument_side` | strict | R2 | Then 2 |
| `...::test_wsi_ui_04__a_stored_email_with_capitals_is_found_by_the_lower_case_one` | strict | R2 | Then 2 |
| `...::test_wsi_ui_13__a_stored_email_with_a_leading_space_is_found_by_the_plain_one` | strict | R2 | Then 2 |
| `tests/unit/services/test_workspace_service.py::test_wss_mi_04__email_matches_ignoring_capitals` | strict | `get_my_invitations` R1 (pass-through) | Then 1 (`set()`) |

- Covers both sides (argument and stored value), case and surrounding spaces, as the row says ("ignoring case and surrounding spaces on both sides"). Nothing beyond the rule.
- Guards that already pass and must keep passing (R2a): `test_wsi_ui_05` (part of an email finds nothing), `test_wsi_ui_06` (`_` is not a wildcard, so an unescaped `ILIKE` fix would break it), `test_wsi_ui_10`, `test_wsi_ui_12`. The brief states this in words under R2a.
- **Note for the systems engineer:** trimming should be the same on both sides. SQL `trim()` removes spaces only; Python `str.strip()` also removes tabs and newlines. The cards use plain spaces, so either passes; mixing them is a consistency point for the reviewer, not a test issue.

## Outside this unit

- `WorkspaceManager.validate_invitation_for_user` already compares case-insensitively; `create_invitation` stores lower-cased. With BUG-1402 fixed the list and the accept check agree. Account email itself (BUG-1860–1862, `profile.py`) is a separate unit.
- `WorkspaceService.list_invitations` / `get_my_invitations` add no order of their own, so BUG-1401's DAO fix reaches both endpoints as-is.
- Expiry boundary difference (lists `<= now` expired, accept `< now`): BUG-1987 (manager) and BUG-2561 (auth service), not this unit.
