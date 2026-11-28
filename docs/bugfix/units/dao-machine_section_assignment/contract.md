# API contract: dao-machine_section_assignment

**No contract change** (no frontend work; the frontend stage is skipped).

Request inputs, status codes, error messages and response fields of `POST /machines/`,
`PUT /machines/{id}/` and `DELETE /factory-sections/{id}/` are unchanged. The assignment row's
`id`, `created_by` and `created_at` are not in any response (`MachineResponse` exposes only
`factory_section_id` / `factory_section_name`), and the frontend does not reference the assignment
row.

Value changes nobody can see from the API today:

- Re-sending a machine's current section (for example "Press 4" stays in "Cutting" while Karim edits
  its note) no longer re-creates the link row: it keeps Rahim's January `created_by` / `created_at`
  and its id. `factory_section_id` in the response is "Cutting" either way.
- Deleting a section unassigns its machines in row-id order; the response does not list them.
