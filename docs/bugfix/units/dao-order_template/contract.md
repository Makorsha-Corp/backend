# Contract note: dao-order_template (round 1, 2026-11-27)

No contract change.

`GET /order-templates/` and `GET /order-templates/{id}/items/` return the same fields, status codes and messages. Only the order of rows that tie (same `created_at` for templates, same `line_number` for lines) is now fixed: newest first then highest id for templates; line number then lowest id for lines. The frontend needs no change; the frontend stage is skipped.
