# Contract note: dao-machine (round 1, 2026-11-27)

No contract change (no field, status code, message or input changes). Values that now behave differently, and the frontend already handles them:

- **`GET /machines/?latest_event_type=RUNNING|IDLE|OFF|MAINTENANCE`** (BUG-886): returns 200 with the machines whose latest status change has that status, instead of a 500. Example: 5 machines running, user picks "Running" in the filter: the 5 machines are listed.
- **`GET /machines/?search=…`** (BUG-888, BUG-892): the text is trimmed, and `%`, `_`, `\` match literally. Example: `"Press 4 "` finds "Press 4"; `%` finds only model number "50%"; spaces only lists everything.
- **`GET /machines/` name sort** (BUG-887): case-insensitive, ties by `id`. Example: "apple", "Banana", "Zulu".
- **`GET /machines/`** (BUG-889, BUG-890): machines of a soft-deleted factory are not listed; filtering by a soft-deleted section returns `[]`. Example: Factory 9 deleted with "Press 4": "Press 4" no longer appears; restoring the factory brings it back unchanged.
- **Work-order draft generation** (BUG-891): no drafts for machines of a soft-deleted factory or section.

Frontend: `MachinesFiltersDialog.tsx` / `machinesApi.ts` already send `latest_event_type` and `search` as is and show the list in server order. No change needed, so the frontend stage is skipped.
