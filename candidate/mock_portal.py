#!/usr/bin/env python3
"""
QuickMart Partner Portal: mock API for the DataFuel backend take-home.

Standard library only. Run it and leave it running:

    python3 mock_portal.py            # serves http://127.0.0.1:8765
    PORT=9000 python3 mock_portal.py  # if 8765 is already taken

Do NOT modify this file. It behaves like the real partner portals we integrate
with, which means it is not always well behaved. Read API.md for the contract.
"""
import hashlib
import json
import os
import random
import threading
import time
from collections import deque
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

PORT = int(os.environ.get("PORT", "8765"))
API_KEY = "dfhire-2026"
IST = timezone(timedelta(hours=5, minutes=30))

CITIES = {"Mumbai": "MUM", "Delhi": "DEL", "Bengaluru": "BLR"}

SKU_NAMES = [
    "Amul Taaza Toned Milk 500ml", "Britannia Brown Bread 400g", "Maggi 2-Minute Noodles 280g",
    "Tata Salt 1kg", "Aashirvaad Atta 5kg", "Fortune Sunflower Oil 1L", "Amul Butter 100g",
    "Parle-G Biscuits 800g", "Surf Excel Easy Wash 1kg", "Colgate Strong Teeth 200g",
    "Dettol Handwash 200ml", "Lays Classic Salted 52g", "Coca-Cola 750ml", "Bisleri Water 1L",
    "Haldiram Bhujia 200g", "Nescafe Classic 50g", "Tata Tea Gold 500g", "Kissan Ketchup 950g",
    "Mother Dairy Curd 400g", "Epigamia Greek Yogurt 90g", "Onion 1kg", "Tomato 500g",
    "Banana Robusta 6pc", "Potato 1kg", "Eggs Farm Fresh 6pc", "Paneer Amul 200g",
    "Dove Soap 3x100g", "Harpic Toilet Cleaner 500ml", "Vim Dishwash Gel 250ml",
    "Pampers Pants M 20pc", "Real Mixed Fruit Juice 1L", "Kurkure Masala Munch 90g",
    "Cadbury Dairy Milk Silk 60g", "Red Bull 250ml", "Too Yumm Multigrain Chips 54g",
    "Sprite 750ml",
]
SKUS = [{"sku_id": f"SKU-{i + 1:04d}", "name": n} for i, n in enumerate(SKU_NAMES)]
RENAME_AFTER = datetime(2026, 9, 28, tzinfo=timezone.utc)
RENAMED = {"SKU-0001": "Amul Taaza Toned Milk 500 ml Pouch"}

INACTIVE = {"MUM-009", "DEL-010", "BLR-004", "BLR-010"}
SERVICEABLE_BUT_INACTIVE = {"MUM-009", "BLR-004"}
ACTIVE_NOT_SERVICEABLE = {"DEL-006"}

STORES = []
for city, code in CITIES.items():
    for i in range(1, 11):
        sid = f"{code}-{i:03d}"
        active = sid not in INACTIVE
        serviceable = (active and sid not in ACTIVE_NOT_SERVICEABLE) or sid in SERVICEABLE_BUT_INACTIVE
        STORES.append({"store_id": sid, "city": city, "name": f"QuickMart {city} #{i}",
                       "is_active": active, "is_serviceable": serviceable})
STORE_BY_ID = {s["store_id"]: s for s in STORES}

STORE_PAGE = 12
INV_PAGE = 15

_lock = threading.Lock()
_recent = deque()
_attempts = {}

# Fair-use ("soft ban") state, per API key. Sustained inventory load over a longer
# window than the burst limit gets a client silently degraded, and every request made
# while degraded pushes the recovery further out.
SOFT_WINDOW = 10.0
SOFT_LIMIT = 30
SOFT_BAN = 20.0
SOFT_EXTEND = 5.0
SOFT_MAX = 60.0
_soft_hist = {}
_soft_until = {}

NEW_STORE = "BLR-007"
NEW_STORE_LAUNCH = datetime(2026, 9, 27, 12, 0, tzinfo=timezone.utc)


def _utcnow_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def soft_banned(client: str) -> bool:
    now = time.monotonic()
    with _lock:
        until = _soft_until.get(client, 0.0)
        if until > now:
            _soft_until[client] = min(now + SOFT_MAX, until + SOFT_EXTEND)
            return True
        hist = _soft_hist.setdefault(client, deque())
        hist.append(now)
        while hist and now - hist[0] > SOFT_WINDOW:
            hist.popleft()
        if len(hist) > SOFT_LIMIT:
            _soft_until[client] = now + SOFT_BAN
            hist.clear()
            return True
        return False


def h(*parts) -> int:
    return int(hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()[:12], 16)


def parse_ts(s: str) -> datetime:
    dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("as_of must include a timezone")
    return dt.astimezone(timezone.utc)


def fmt(dt: datetime, store_id: str) -> str:
    if store_id.startswith("DEL"):
        return dt.astimezone(IST).isoformat(timespec="seconds")
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def inventory(store_id: str, as_of: datetime):
    if store_id == NEW_STORE and as_of < NEW_STORE_LAUNCH:
        return []
    carried = [s for s in SKUS if h("carry", store_id, s["sku_id"]) % 100 < 80]
    observed = as_of + timedelta(minutes=h("lag", store_id, as_of.isoformat()) % 21)
    items = []
    for s in carried:
        r = h("stock", store_id, s["sku_id"], as_of.isoformat()) % 100
        in_stock = r < (88 if not store_id.startswith("DEL") else 80)
        qty = (h("qty", store_id, s["sku_id"], as_of.isoformat()) % 40 + 1) if in_stock else 0
        if in_stock and h("ghost", store_id, s["sku_id"], as_of.isoformat()) % 100 < 5:
            qty = 0
        price = round(10 + h("price", s["sku_id"]) % 500 + 0.5 * (h("p2", s["sku_id"]) % 2), 2)
        name = RENAMED.get(s["sku_id"], s["name"]) if as_of >= RENAME_AFTER else s["name"]
        items.append({
            "sku_id": s["sku_id"],
            "name": name,
            "in_stock": in_stock,
            "qty": qty,
            "price": f"{price:.2f}" if store_id.startswith("BLR") else price,
            "observed_at": fmt(observed, store_id),
        })
    return items


class Handler(BaseHTTPRequestHandler):
    server_version = "QuickMartPortal/1.3"

    def log_message(self, fmt_, *args):
        pass

    def send_json(self, code, body, headers=None):
        raw = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        url = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(url.query).items()}
        parts = [p for p in url.path.split("/") if p]

        if parts == ["v1", "health"]:
            return self.send_json(200, {"ok": True})

        if self.headers.get("X-Api-Key") != API_KEY:
            return self.send_json(401, {"error": "missing or invalid X-Api-Key"})

        is_inventory = len(parts) == 4 and parts[:2] == ["v1", "stores"] and parts[3] == "inventory"
        if is_inventory and parts[2] in STORE_BY_ID and "as_of" in q and soft_banned(self.headers.get("X-Api-Key")):
            # Degraded ("soft-banned") response: HTTP 200, looks normal, but either empty or
            # a truncated slice of the real page with the listing cut short.
            sid = parts[2]
            try:
                as_of = parse_ts(q["as_of"])
            except ValueError as e:
                return self.send_json(400, {"error": str(e)})
            cursor = int(q.get("cursor", "0"))
            real = inventory(sid, as_of)[cursor:cursor + INV_PAGE]
            if real and random.random() < 0.5:
                real = real[:random.randint(1, max(1, len(real) // 3))]
            else:
                real = []
            return self.send_json(200, {"store_id": sid, "items": real, "partial": False,
                                        "next_cursor": None,
                                        "meta": {"source": "edge", "generated_at": _utcnow_iso()}})

        now = time.monotonic()
        with _lock:
            while _recent and now - _recent[0] > 1.0:
                _recent.popleft()
            if len(_recent) >= 8:
                return self.send_json(429, {"error": "rate limited"}, {"Retry-After": "2"})
            _recent.append(now)

        if random.random() < 0.07:
            return self.send_json(503, {"error": "upstream unavailable, try again"})
        if random.random() < 0.03:
            time.sleep(8)

        if parts == ["v1", "stores"]:
            page = int(q.get("page", "1"))
            start = (page - 1) * STORE_PAGE
            chunk = STORES[start:start + STORE_PAGE]
            nxt = page + 1 if start + STORE_PAGE < len(STORES) else None
            return self.send_json(200, {"stores": chunk, "page": page, "next_page": nxt})

        if len(parts) == 4 and parts[:2] == ["v1", "stores"] and parts[3] == "inventory":
            sid = parts[2]
            if sid not in STORE_BY_ID:
                return self.send_json(404, {"error": f"unknown store {sid}"})
            if "as_of" not in q:
                return self.send_json(400, {"error": "as_of is required (ISO-8601 with timezone)"})
            try:
                as_of = parse_ts(q["as_of"])
            except ValueError as e:
                return self.send_json(400, {"error": str(e)})

            key = (sid, as_of.isoformat())
            if sid == "MUM-007":
                with _lock:
                    _attempts[key] = _attempts.get(key, 0) + 1
                    n = _attempts[key]
                if n <= 2:
                    return self.send_json(500, {"error": "internal error"})

            if sid == "DEL-004" and as_of == datetime(2026, 9, 28, 10, 30, tzinfo=timezone.utc):
                return self.send_json(200, {"store_id": sid, "items": [], "partial": True, "next_cursor": None,
                                            "meta": {"source": "origin", "generated_at": _utcnow_iso()}})

            items = inventory(sid, as_of)
            cursor = int(q.get("cursor", "0"))
            page = items[cursor:cursor + INV_PAGE]
            if cursor > 0 and h("dup", sid, as_of.isoformat(), cursor) % 100 < 35:
                page = [items[cursor - 1]] + page
            nxt = cursor + INV_PAGE if cursor + INV_PAGE < len(items) else None
            return self.send_json(200, {"store_id": sid, "items": page, "partial": False,
                                        "next_cursor": None if nxt is None else str(nxt),
                                        "meta": {"source": "origin", "generated_at": _utcnow_iso()}})

        return self.send_json(404, {"error": "not found"})


if __name__ == "__main__":
    print(f"QuickMart mock portal on http://127.0.0.1:{PORT}  (Ctrl+C to stop)")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
