# Real-Time Architecture Plan

## When to build this

Build real-time **after** all tables, business logic, and frontend flows are stable.
Real-time is infrastructure — adding it mid-build means doing it twice.
Polling on navigation is acceptable for everything that doesn't need it.

---

## Technology Choice

**SSE (Server-Sent Events)** over WebSockets.

- Real-time needs are mostly read/push — server tells clients something changed
- Not bidirectional, so WebSockets is overkill
- FastAPI has native SSE support
- Works over regular HTTP, no special infrastructure
- If multiple backend workers are ever needed, add Redis pub/sub between them

---

## Two Patterns

### Pattern 1 — Collaborative Presence (Entity-level)

For pages where **multiple people can be on the same record simultaneously**.

**Use for:** Purchase Orders, Machines, Work Orders, Production Batches

**What it does:**
- When a user opens a record, they announce themselves via SSE connection
- Everyone on that record sees who else is viewing ("4 others viewing")
- When someone leaves (tab close, navigate away), they disappear from presence list
- When anyone mutates the record (PUT/PATCH), server broadcasts the update to all connected users on that record — their page updates without a refresh

**Endpoint pattern:**
```
GET /stream/{entity_type}/{entity_id}/
```

Examples:
```
/stream/purchase-order/123/
/stream/machine/45/
/stream/work-order/89/
```

**Per-connection state tracked:**
- `entity_type` + `entity_id`
- `user_id` + `user_name`
- The SSE connection itself

**Flow:**
```
User opens PO #123
  → connects to SSE stream for purchase-order/123
  → server registers them as present
  → server pushes current presence list to everyone on that order

User A updates the supplier on PO #123
  → normal PUT request saves to DB
  → server broadcasts "order_updated" event to all SSE connections on purchase-order/123
  → Users B, C, D, E receive event → RTK Query refetches the order

User closes tab
  → SSE connection drops
  → server removes them from presence
  → broadcasts updated presence list to remaining users
```

**Build once, reuse everywhere** — same logic, just parameterized by entity type and ID.

---

### Pattern 2 — Workspace Event Stream (Broad notifications)

For pages where nobody is "on the same record" but **upstream actions affect downstream data**.

**Use for:** Inventory levels, dashboard totals, stock alerts

**What it does:**
- One workspace-level SSE stream per user session
- When a significant event happens (PO completed, batch finished, stock updated), server broadcasts a notification on the workspace stream
- Clients listening refetch the relevant data

**Endpoint:**
```
GET /stream/workspace/
```

**Example events pushed on this stream:**
- `inventory_updated` — triggered when a PO is completed and items are added
- `low_stock_alert` — triggered when stock drops below threshold
- `batch_completed` — triggered when a production batch finishes

**Flow:**
```
User completes PO #123
  → server saves PO completion, updates inventory
  → broadcasts "inventory_updated" on workspace stream
  → anyone with inventory page open receives event → refetches inventory
```

---

## Which Pattern Goes Where

| Area | Pattern | Reason |
|---|---|---|
| Purchase Orders | Entity presence | Multiple people coordinate on same PO |
| Machines | Entity presence | Concurrent edits to specs/status |
| Work Orders | Entity presence | Shop floor + management on same job |
| Production Batches | Entity presence | Multiple people tracking progress |
| Inventory | Workspace stream | Changes driven by upstream actions, not direct editing |
| Dashboard totals | Workspace stream | Aggregates change when upstream data changes |
| Accounts / Invoices | Neither (pull on nav) | Rarely concurrent, pull-fresh is fine |
| Settings / Reports | Neither (pull on nav) | No concurrent editing |

---

## Infrastructure

**Single worker (current):** In-memory pub/sub is fine. Dictionary of `entity_type/entity_id → list of SSE connections`.

**Multiple workers (future scaling):** Replace in-memory with Redis pub/sub. Each worker subscribes to Redis channels and forwards events to its local SSE connections. This is the only change needed — the API surface stays the same.

---

## Implementation Order

1. Build entity stream for Purchase Orders first (highest need)
2. Reuse same infrastructure for Machines and Work Orders
3. Add workspace stream for inventory notifications
4. Everything else stays as pull-on-navigate
