#!/usr/bin/env python3
import argparse
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import requests

from db import IST, canonical_as_of, canonical_ts, init_db, ist_date_for_as_of, normalize_item

PORTAL = "http://127.0.0.1:8765"
HEADERS = {"X-Api-Key": "dfhire-2026"}


@dataclass
class Pacer:
    rate: float = 2.0
    last_call: float = 0.0

    def wait(self) -> None:
        gap = 1.0 / self.rate
        wait_for = self.last_call + gap - time.monotonic()
        if wait_for > 0:
            time.sleep(wait_for)
        self.last_call = time.monotonic()


class SoftBanError(Exception):
    pass


class ResponseError(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def get_conn(db_path: str = "osa.db") -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


def request_json(session: requests.Session, url: str, params: Optional[Dict[str, Any]] = None, timeout: float = 5.0) -> Tuple[Optional[dict], Optional[str]]:
    params = params or {}
    last_reason = "unknown"
    for attempt in range(1, 6):
        try:
            response = session.get(url, params=params, headers=HEADERS, timeout=timeout)
        except requests.RequestException as exc:
            last_reason = f"network error: {type(exc).__name__}"
        else:
            status = response.status_code
            if status == 200:
                try:
                    return response.json(), None
                except ValueError:
                    return None, "invalid JSON response"
            if status == 429:
                wait_seconds = float(response.headers.get("Retry-After", "2") or 2)
                time.sleep(wait_seconds)
                last_reason = "rate limited (429)"
                continue
            if status in (400, 401, 404):
                return None, f"http {status}"
            if status in (500, 503):
                last_reason = f"http {status}"
            else:
                last_reason = f"http {status}"
        if attempt < 5:
            time.sleep(min(2 ** attempt, 10))
    return None, f"gave up after 5 attempts ({last_reason})"


def fetch_store_list() -> List[dict]:
    session = requests.Session()
    stores: List[dict] = []
    page = 1
    while True:
        body, error = request_json(session, f"{PORTAL}/v1/stores", {"page": page})
        if error:
            raise RuntimeError(f"could not load store roster: {error}")
        stores.extend(body.get("stores", []))
        if body.get("next_page") is None:
            break
        page = int(body["next_page"])
    return stores


def save_store_list(conn: sqlite3.Connection, stores: List[dict]) -> List[str]:
    for store in stores:
        conn.execute(
            """
            INSERT INTO stores (store_id, city, name, is_active, is_serviceable)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(store_id) DO UPDATE SET
                city = excluded.city,
                name = excluded.name,
                is_active = excluded.is_active,
                is_serviceable = excluded.is_serviceable
            """,
            (
                store["store_id"],
                store["city"],
                store["name"],
                int(bool(store.get("is_active", False))),
                int(bool(store.get("is_serviceable", False))),
            ),
        )
    conn.commit()
    tracked = [store["store_id"] for store in stores if bool(store.get("is_active", False))]
    return tracked


def fetch_store_inventory(session: requests.Session, pacer: Pacer, store_id: str, as_of_utc: str) -> Tuple[str, Optional[str], List[dict]]:
    items_by_sku: Dict[str, dict] = {}
    cursor = "0"
    soft_ban_count = 0

    for page in range(1, 51):
        pacer.wait()
        body, error = request_json(session, f"{PORTAL}/v1/stores/{store_id}/inventory", {"as_of": as_of_utc, "cursor": cursor})
        if error:
            return "incomplete", error, []

        source = (body or {}).get("meta", {}).get("source")
        if source != "origin":
            if soft_ban_count >= 2:
                return "incomplete", "soft_ban", []
            soft_ban_count += 1
            time.sleep(30)
            cursor = "0"
            items_by_sku = {}
            continue

        if bool(body.get("partial", False)):
            return "incomplete", "portal returned partial snapshot", []

        for item in body.get("items", []):
            sku_id = item.get("sku_id")
            if not sku_id:
                continue
            normalized = normalize_item(item)
            items_by_sku[sku_id] = normalized

        next_cursor = body.get("next_cursor")
        if next_cursor is None:
            return "complete", None, list(items_by_sku.values())
        cursor = str(next_cursor)

    return "incomplete", "too many pages", []


def save_store_result(conn: sqlite3.Connection, as_of: str, store_id: str, status: str, reason: Optional[str], items: List[dict]) -> None:
    with conn:
        existing = conn.execute(
            "SELECT status FROM store_sweeps WHERE as_of = ? AND store_id = ?",
            (as_of, store_id),
        ).fetchone()
        if existing and existing["status"] == "complete" and status == "incomplete":
            return

        conn.execute(
            "DELETE FROM observations WHERE as_of = ? AND store_id = ?",
            (as_of, store_id),
        )
        conn.execute(
            "DELETE FROM store_sweeps WHERE as_of = ? AND store_id = ?",
            (as_of, store_id),
        )

        if status == "complete":
            rows = []
            for item in items:
                rows.append(
                    (
                        as_of,
                        store_id,
                        item["sku_id"],
                        item["name"],
                        item["in_stock"],
                        item["qty"],
                        item["price"],
                        item["observed_at"],
                    )
                )
            if rows:
                conn.executemany(
                    """
                    INSERT OR REPLACE INTO observations (as_of, store_id, sku_id, name, in_stock, qty, price, observed_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    rows,
                )

        conn.execute(
            """
            INSERT INTO store_sweeps (as_of, store_id, status, reason, item_count, fetched_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                as_of,
                store_id,
                status,
                reason,
                len(items),
                datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            ),
        )


def set_sweep_record(conn: sqlite3.Connection, as_of: str) -> None:
    ist_date = ist_date_for_as_of(as_of)
    conn.execute(
        """
        INSERT OR IGNORE INTO sweeps (as_of, ist_date, started_at, finished_at)
        VALUES (?, ?, ?, ?)
        """,
        (
            as_of,
            ist_date,
            datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        ),
    )
    conn.commit()


def run_sweep(as_of: str, db_path: str = "osa.db") -> Tuple[int, int, List[str]]:
    as_of = canonical_as_of(as_of)
    conn = get_conn(db_path)
    start = time.monotonic()
    store_rows = fetch_store_list()
    tracked = save_store_list(conn, store_rows)
    set_sweep_record(conn, as_of)

    session = requests.Session()
    pacer = Pacer(rate=2.0)
    complete = 0
    incomplete = []

    for store_id in tracked:
        status, reason, items = fetch_store_inventory(session, pacer, store_id, as_of)
        save_store_result(conn, as_of, store_id, status, reason, items)
        if status == "complete":
            complete += 1
        else:
            incomplete.append(f"{store_id}: {reason}")

    elapsed = time.monotonic() - start
    print(f"{len(tracked)} stores: {complete} complete, {len(incomplete)} incomplete ({'; '.join(incomplete) if incomplete else 'none'}) · {elapsed:.0f}s")
    conn.close()
    return len(tracked), complete, incomplete


def main() -> None:
    parser = argparse.ArgumentParser(description="Sweep QuickMart inventory for a timestamp.")
    parser.add_argument("--as-of", required=True, help="UTC timestamp such as 2026-09-28T04:30:00Z")
    parser.add_argument("--db", default="osa.db", help="database path")
    args = parser.parse_args()

    try:
        run_sweep(args.as_of, db_path=args.db)
    except ValueError as exc:
        raise SystemExit(str(exc))


if __name__ == "__main__":
    main()
