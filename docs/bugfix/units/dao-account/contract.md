# Contract note: dao-account

Date: 2026-11-28. Endpoint `GET /accounts/by-tag/{tag_id}/`. No change to the response shape, status codes, error messages or inputs. Two value changes:

1. **Order is now fixed:** accounts come back by name ignoring case, then by id, before `skip` / `limit`.
   Example: tag "Supplier" on "Zulu" (id 10), "apple" (id 11), "Banana" (id 12), "apple" (id 13) → `apple(11), apple(13), Banana(12), Zulu(10)`. Before: whatever the database plan gave, so pages could repeat or skip accounts.
2. **A deleted tag (`is_active = false`) lists no accounts:** 200 `[]`. Before: 200 with the accounts that still carry it. The assignments are kept; re-activating the tag lists the accounts again. (A later fix, BUG-2982, turns this into 404 "Account tag {tag_id} not found".)

Frontend: no code in `../frontend/src` calls `/accounts/by-tag/`, so **no frontend change; the frontend stage is skipped.**
