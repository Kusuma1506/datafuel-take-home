"""
review_me.py: written by an AI coding assistant in one shot and merged without review.

Your job (write it in REVIEW.md):
  1. Find at least 5 real problems, most serious first. For each, say what goes wrong,
     with a concrete example (not just "bad practice").
  2. Fix the 2-3 most serious ones in this file.
Don't rewrite it from scratch. Reviewing is the skill being tested.
"""
import sqlite3
import time
from datetime import date, datetime, timedelta, timezone

import requests

PORTAL = "http://127.0.0.1:8765"
HEADERS = {"X-Api-Key": "dfhire-2026"}


def fetch_inventory(store_id, as_of, cursor="0", results=None):
    """Fetch every inventory page for a store, retrying until it works."""
    if results is None:
        results = []

    for attempt in range(1, 6):
        try:
            r = requests.get(
                f"{PORTAL}/v1/stores/{store_id}/inventory",
                params={"as_of": as_of, "cursor": cursor},
                headers=HEADERS,
                timeout=5,
            )
            if r.status_code == 429:
                time.sleep(float(r.headers.get("Retry-After", "2") or "2"))
                continue
            if r.status_code in (400, 401, 404):
                raise ValueError(f"request failed with HTTP {r.status_code}")
            r.raise_for_status()
            break
        except ValueError:
            raise
        except requests.RequestException:
            if attempt == 5:
                raise
            time.sleep(min(2 ** attempt, 10))
    else:
        return results

    body = r.json()
    results.extend(body["items"])
    if body.get("next_cursor"):
        return fetch_inventory(store_id, as_of, body["next_cursor"], results)
    return results


def save(conn, store_id, items):
    for it in items:
        conn.execute(
            "INSERT OR REPLACE INTO inventory (store_id, sku_id, name, in_stock, qty, observed_at) VALUES (?, ?, ?, ?, ?, ?)",
            (store_id, it["sku_id"], it["name"], int(bool(it["in_stock"])), it["qty"], it["observed_at"]),
        )
    conn.commit()


def city_osa(conn, city, day=None):
    """On-shelf availability for a city on a day. Defaults to yesterday in IST."""
    IST = timezone(timedelta(hours=5, minutes=30))
    if day is None:
        day = (datetime.now(IST) - timedelta(days=1)).date().isoformat()
    stores = [r[0] for r in conn.execute(
        "SELECT store_id FROM stores WHERE city = ?", (city,))]
    if not stores:
        return 0.0

    per_store = []
    for s in stores:
        rows = conn.execute(
            "SELECT in_stock FROM inventory WHERE store_id = ? AND substr(observed_at, 1, 10) = ?",
            (s, day),
        ).fetchall()
        if not rows:
            per_store.append(None)
            continue
        seen = len(rows)
        in_stock = sum(1 for (status,) in rows if status == 1)
        per_store.append(in_stock / seen)

    valid = [p for p in per_store if p is not None]
    if not valid:
        return 0.0
    return round(100 * sum(valid) / len(valid), 2)


if __name__ == "__main__":
    conn = sqlite3.connect("osa.db")
    conn.execute("CREATE TABLE IF NOT EXISTS stores (store_id TEXT, city TEXT)")
    conn.execute("CREATE TABLE IF NOT EXISTS inventory (store_id TEXT, sku_id TEXT, name TEXT, "
                 "in_stock INT, qty INT, observed_at TEXT)")
    as_of = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for sid in ["MUM-001", "MUM-002"]:
        save(conn, sid, fetch_inventory(sid, as_of))
    print(city_osa(conn, "Mumbai"))
