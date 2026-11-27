# Contract note: dao-work_order_template (round 1, 2026-11-27)

No contract change.

Same fields, status codes and messages on every endpoint. These behaviours change, as intended:
- `GET /work-order-templates/`: templates with the same `created_at` come back highest id first, so pages never repeat or miss one.
- `GET /work-order-templates/{id}/approvers/` (and the approvers copied onto a work order made from a template): in the order they were chosen (id ascending).
- `POST /work-order-templates/generate-drafts/` (deprecated) with `factory_id`: a recurring template whose default factory section is deleted gets no draft.

The frontend needs no change, so the frontend stage is skipped.
