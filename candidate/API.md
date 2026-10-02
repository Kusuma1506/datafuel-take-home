# QuickMart Partner Portal API: v1

This is the contract for `mock_portal.py`. Treat it the way you'd treat a real third-party
partner API: it's mostly accurate, it doesn't tell you everything, and the service doesn't
always behave.

- **Base URL:** `http://127.0.0.1:8765` (or the port you started it on)
- **Auth:** every request except `/v1/health` needs the header
  `X-Api-Key: dfhire-2026`
- **Format:** all responses are JSON. All timestamps are ISO-8601.

---

## GET /v1/health
No auth. Use it to check the portal is running.
```json
{"ok": true}
```

---

## GET /v1/stores?page=N
QuickMart's full store roster across all cities, paginated. `page` starts at `1`.

**Example:** `GET /v1/stores?page=1`
```json
{
  "stores": [
    {"store_id": "MUM-001", "city": "Mumbai", "name": "QuickMart Mumbai #1",
     "is_active": true, "is_serviceable": true}
  ],
  "page": 1,
  "next_page": 2
}
```
Keep requesting `page = next_page` until `next_page` is `null`.

| Field | Meaning |
|---|---|
| `store_id` | Stable store identifier |
| `city` | `Mumbai`, `Delhi` or `Bengaluru` |
| `is_active` | The store is part of QuickMart's network. `false` = shut down / decommissioned |
| `is_serviceable` | The store is accepting orders **right now**. Can flip during the day (rain, maintenance, staff shortage) |

---

## GET /v1/stores/{store_id}/inventory?as_of=TS&cursor=C
The inventory snapshot of one store as of timestamp `TS`.

- `as_of` (**required**): ISO-8601 **with a timezone**, e.g. `2026-09-28T04:30:00Z`.
  URL-encode it if your HTTP library doesn't (`+05:30` → `%2B05:30`).
- `cursor` (optional): omit it or pass `0` for the first page, then pass back
  `next_cursor` until it is `null`. Page size is about 15 items.

**Example:** `GET /v1/stores/MUM-001/inventory?as_of=2026-09-28T04:30:00Z`
```json
{
  "store_id": "MUM-001",
  "items": [
    {"sku_id": "SKU-0002", "name": "Britannia Brown Bread 400g",
     "in_stock": true, "qty": 12, "price": 237.5,
     "observed_at": "2026-09-28T04:41:00Z"}
  ],
  "partial": false,
  "next_cursor": "15",
  "meta": {"source": "origin", "generated_at": "2026-09-30T06:12:44Z"}
}
```

| Field | Meaning |
|---|---|
| `items[].sku_id` | Stable product identifier |
| `items[].name` | Product display name |
| `items[].in_stock` | QuickMart's own availability flag for this SKU at this store |
| `items[].qty` | Units the store reports on hand. Informational |
| `items[].price` | Selling price in INR |
| `items[].observed_at` | When the store's snapshot was actually taken |
| `partial` | `true` = the portal could not assemble a complete snapshot for this store |
| `next_cursor` | Pass this back to get the next page; `null` = no more pages |
| `meta.source` | `origin` = generated live by the store's inventory system; `edge` = served by QuickMart's CDN edge layer |
| `meta.generated_at` | When the portal generated this response (wall-clock time, not the snapshot time) |

A store can legitimately carry no products at a given time (for example, before it launches).

---

## Errors, limits and fair use

| Status | Meaning | What it tells you |
|---|---|---|
| 400 | Bad request | e.g. `as_of` missing or has no timezone |
| 401 | Missing or wrong API key | |
| 404 | Unknown store or path | |
| 429 | Burst rate limit | Respect the `Retry-After` header (seconds) |
| 500 / 503 | Server-side failure | Usually transient |

- **Burst limit:** about **8 requests per second** across all clients → HTTP 429.
- **Fair use:** sustained high request volume from one API key over a longer period is
  **automatically degraded without an error**. QuickMart does not publish the thresholds.
- Some requests are slow. Don't wait on any single request forever.
