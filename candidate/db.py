import sqlite3
from datetime import datetime, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30))

CREATE_TABLES = """
CREATE TABLE IF NOT EXISTS stores (
    store_id TEXT PRIMARY KEY,
    city TEXT NOT NULL,
    name TEXT,
    is_active INTEGER NOT NULL,
    is_serviceable INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS sweeps (
    as_of TEXT PRIMARY KEY,
    ist_date TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT
);

CREATE TABLE IF NOT EXISTS store_sweeps (
    as_of TEXT NOT NULL,
    store_id TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('complete', 'incomplete')),
    reason TEXT,
    item_count INTEGER NOT NULL DEFAULT 0,
    fetched_at TEXT NOT NULL,
    PRIMARY KEY (as_of, store_id)
);

CREATE TABLE IF NOT EXISTS observations (
    as_of TEXT NOT NULL,
    store_id TEXT NOT NULL,
    sku_id TEXT NOT NULL,
    name TEXT NOT NULL,
    in_stock INTEGER NOT NULL,
    qty INTEGER NOT NULL,
    price REAL,
    observed_at TEXT NOT NULL,
    PRIMARY KEY (as_of, store_id, sku_id)
);
"""


def init_db(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(CREATE_TABLES)
    conn.commit()


def canonical_as_of(value: str) -> str:
    if not value:
        raise ValueError("as_of is required")
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("as_of must include a timezone")
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def ist_date_for_as_of(as_of_utc: str) -> str:
    dt = datetime.fromisoformat(as_of_utc.replace("Z", "+00:00")).astimezone(timezone.utc)
    return dt.astimezone(IST).date().isoformat()


def canonical_ts(value: str) -> str:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError(f"timestamp has no timezone: {value}")
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def normalize_item(item: dict) -> dict:
    if not isinstance(item, dict):
        raise ValueError("inventory item must be a dict")
    obs = item.get("observed_at")
    if not obs:
        raise ValueError(f"missing observed_at for sku {item.get('sku_id')}")
    price_raw = item.get("price")
    norm = {
        "sku_id": str(item["sku_id"]),
        "name": str(item.get("name", "")),
        "in_stock": 1 if bool(item.get("in_stock", False)) else 0,
        "qty": int(item.get("qty") or 0),
        "price": float(price_raw) if price_raw is not None else None,
        "observed_at": canonical_ts(obs),
    }
    return norm
