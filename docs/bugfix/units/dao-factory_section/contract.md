# Contract: dao-factory_section

No contract change (no frontend stage). Response shape, status codes, inputs and error messages
of `GET /factory-sections/` are unchanged; the endpoint still never sends `include_deleted`.

Value-only changes on `GET /factory-sections/?factory_id=…` (no frontend work needed; the UI just
renders the list):
- Order is now name case-insensitive, then id. Example: "Zulu", "bolt", "apple", "Bolt", "Banana"
  ("bolt" created first) come back apple, Banana, bolt, Bolt, Zulu.
- Sections of a soft-deleted factory are no longer listed; they return unchanged when the factory
  is restored. Example: factory 9 deleted with "Cutting" and "Paint" → `[]`; restore → both back.
- Deleted sections no longer use up page places: 100 deleted then 1 live section → the default page
  now returns that 1 live section (before: an empty or short list after the manager's filter).
