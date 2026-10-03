import sqlite3

from fastapi.testclient import TestClient

from app import app, build_report
from db import init_db


def make_conn():
    conn = sqlite3.connect(":memory:")
    init_db(conn)
    conn.execute(
        "INSERT INTO stores (store_id, city, name, is_active, is_serviceable) VALUES (?, ?, ?, ?, ?)",
        ("MUM-001", "Mumbai", "QuickMart Mumbai #1", 1, 1),
    )
    conn.execute(
        "INSERT INTO stores (store_id, city, name, is_active, is_serviceable) VALUES (?, ?, ?, ?, ?)",
        ("MUM-002", "Mumbai", "QuickMart Mumbai #2", 1, 1),
    )
    return conn


def test_incomplete_store_is_excluded_and_reported():
    conn = make_conn()
    conn.execute(
        "INSERT INTO sweeps (as_of, ist_date, started_at, finished_at) VALUES (?, ?, ?, ?)",
        ("2026-09-28T04:30:00Z", "2026-09-28", "2026-09-28T04:30:00Z", "2026-09-28T04:40:00Z"),
    )
    conn.execute(
        "INSERT INTO store_sweeps (as_of, store_id, status, reason, item_count, fetched_at) VALUES (?, ?, ?, ?, ?, ?)",
        ("2026-09-28T04:30:00Z", "MUM-001", "complete", None, 1, "2026-09-28T04:34:00Z"),
    )
    conn.execute(
        "INSERT INTO observations (as_of, store_id, sku_id, name, in_stock, qty, price, observed_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("2026-09-28T04:30:00Z", "MUM-001", "SKU-0001", "Milk", 1, 12, 40.0, "2026-09-28T04:35:00Z"),
    )
    conn.execute(
        "INSERT INTO store_sweeps (as_of, store_id, status, reason, item_count, fetched_at) VALUES (?, ?, ?, ?, ?, ?)",
        ("2026-09-28T04:30:00Z", "MUM-002", "incomplete", "partial", 0, "2026-09-28T04:36:00Z"),
    )

    report = build_report(conn, "Mumbai", "2026-09-28")

    assert report["osa_pct"] == 100.0
    assert report["coverage"]["incomplete"][0]["store_id"] == "MUM-002"
    assert report["coverage"]["stores_complete"] == 1


def test_ist_day_mapping_is_used_for_sweeps():
    conn = make_conn()
    conn.execute(
        "INSERT INTO sweeps (as_of, ist_date, started_at, finished_at) VALUES (?, ?, ?, ?)",
        ("2026-09-27T19:00:00Z", "2026-09-28", "2026-09-27T19:00:00Z", "2026-09-27T19:05:00Z"),
    )
    conn.execute(
        "INSERT INTO store_sweeps (as_of, store_id, status, reason, item_count, fetched_at) VALUES (?, ?, ?, ?, ?, ?)",
        ("2026-09-27T19:00:00Z", "MUM-001", "complete", None, 1, "2026-09-27T19:02:00Z"),
    )
    conn.execute(
        "INSERT INTO observations (as_of, store_id, sku_id, name, in_stock, qty, price, observed_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("2026-09-27T19:00:00Z", "MUM-001", "SKU-0002", "Bread", 1, 4, 30.0, "2026-09-27T19:02:00Z"),
    )

    report = build_report(conn, "Mumbai", "2026-09-28")

    assert report["observations"] == 1
    assert report["osa_pct"] == 100.0


def test_no_data_returns_null_and_no_data_status():
    conn = make_conn()
    report = build_report(conn, "Mumbai", "2026-09-29")

    assert report["status"] == "no_data"
    assert report["osa_pct"] is None


def test_invalid_city_returns_400():
    client = TestClient(app)
    response = client.get("/osa?city=Paris")
    assert response.status_code == 400
    assert "city must be one of" in response.json()["detail"]


def test_non_zero_padded_date_returns_400():
    client = TestClient(app)
    response = client.get("/osa?city=Mumbai&date=2026-9-8")

    assert response.status_code == 400
    assert response.json()["detail"] == "date must be YYYY-MM-DD"
