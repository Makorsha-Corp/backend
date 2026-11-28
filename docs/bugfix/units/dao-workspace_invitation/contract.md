# Contract note: dao-workspace_invitation

**No contract change.** Response shapes, fields, status codes and error messages are the same, so the frontend stage is skipped.

What a user can notice (for the PR body; the frontend (`workspaceApi.ts` `getWorkspaceInvitations`, `getMyInvitations`) shows the lists as returned and needs no change):

- `GET /workspaces/{id}/invitations/` (with or without `include_expired`) and `GET /workspaces/me/invitations/` now always return the newest invitation first (`invited_at` descending, then `id` descending). Example: invitations sent Mon, Wed, Tue come back Wed, Tue, Mon. Before, the order was undefined.
- `GET /workspaces/me/invitations/` now also lists invitations whose email differs from the account's only in capitals. Example: John registered as `John.Doe@example.com` and was invited as `john.doe@example.com`. His panel used to be empty and now shows the invitation, which he could already accept through the email link.
