import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException

from db import IST, init_db

app = FastAPI()
ALLOWED_CITIES = {"Mumbai", "Delhi", "Bengaluru"}


def get_conn():
    conn = sqlite3.connect("osa.db")
    conn.row_factory = sqlite3.Row
    return conn


def build_report(conn: sqlite3.Connection, city: str, date_str: str):
    expected = conn.execute(
        "SELECT COUNT(*) FROM stores WHERE city = ? AND is_active = 1",
        (city,),
    ).fetchone()[0]

    sweeps = conn.execute(
        "SELECT as_of FROM sweeps WHERE ist_date = ? ORDER BY as_of",
        (date_str,),
    ).fetchall()
    if not sweeps:
        return {
            "city": city,
            "date": date_str,
            "osa_pct": None,
            "observations": 0,
            "coverage": {
                "stores_expected": expected,
                "stores_complete": 0,
                "incomplete": [],
            },
            "skus": [],
            "status": "no_data",
        }

    total_obs = 0
    total_in_stock = 0
    sku_rows = {}

    sel = conn.execute(
        """
        SELECT o.sku_id, o.name, o.observed_at, o.in_stock
        FROM observations o
        JOIN store_sweeps ss ON ss.as_of = o.as_of AND ss.store_id = o.store_id
        JOIN sweeps sw ON sw.as_of = o.as_of
        JOIN stores s ON s.store_id = o.store_id
        WHERE s.city = ? AND sw.ist_date = ? AND ss.status = 'complete'
        ORDER BY o.sku_id, o.observed_at DESC
        """,
        (city, date_str),
    )

    for row in sel:
        sku = row[0]
        name = row[1]
        observed_at = row[2]
        in_stock = int(row[3])
        pkg = sku_rows.setdefault(
            sku,
            {"sku_id": sku, "name": name, "observations": 0, "in_stock": 0, "last_observed": observed_at},
        )
        pkg["observations"] += 1
        pkg["in_stock"] += in_stock
        total_obs += 1
        total_in_stock += in_stock
        if observed_at > pkg["last_observed"]:
            pkg["name"] = name
            pkg["last_observed"] = observed_at

    skus = []
    for sku, pkg in sorted(sku_rows.items()):
        obs = pkg["observations"]
        in_stock = pkg["in_stock"]
        pct = round((in_stock / obs) * 100, 2) if obs else 0.0
        skus.append({
            "sku_id": sku,
            "name": pkg["name"],
            "observations": obs,
            "in_stock": in_stock,
            "osa_pct": pct,
        })

    complete_stores = conn.execute(
        """
        SELECT COUNT(DISTINCT ss.store_id)
        FROM store_sweeps ss
        JOIN sweeps sw ON sw.as_of = ss.as_of
        JOIN stores s ON s.store_id = ss.store_id
        WHERE s.city = ? AND sw.ist_date = ? AND ss.status = 'complete'
        """,
        (city, date_str),
    ).fetchone()[0]

    incomplete = conn.execute(
        """
        SELECT ss.store_id, ss.as_of AS sweep, ss.reason
        FROM store_sweeps ss
        JOIN sweeps sw ON sw.as_of = ss.as_of
        JOIN stores s ON s.store_id = ss.store_id
        WHERE s.city = ? AND sw.ist_date = ? AND ss.status = 'incomplete'
        ORDER BY ss.store_id, ss.as_of
        """,
        (city, date_str),
    ).fetchall()

    status = "ok"
    if complete_stores == 0:
        status = "partial"
    if total_obs == 0:
        osa_pct = None
    else:
        osa_pct = round((total_in_stock / total_obs) * 100, 2)

    return {
        "city": city,
        "date": date_str,
        "osa_pct": osa_pct,
        "observations": total_obs,
        "coverage": {
            "stores_expected": expected,
            "stores_complete": complete_stores,
            "incomplete": [
                {"store_id": row[0], "sweep": row[1], "reason": row[2]}
                for row in incomplete
            ],
        },
        "skus": skus,
        "status": status,
    }


@app.get("/osa")
def osa(city: str, date: Optional[str] = None):
    if city not in ALLOWED_CITIES:
        raise HTTPException(status_code=400, detail=f"city must be one of {sorted(ALLOWED_CITIES)}")

    if date is None:
        dt = datetime.now(IST) - timedelta(days=1)
        date_value = dt.date().isoformat()
    else:
        try:
            parsed_date = datetime.strptime(date, "%Y-%m-%d").date()
            date_value = parsed_date.isoformat()
            if date_value != date:
                raise ValueError("date must be zero-padded")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="date must be YYYY-MM-DD") from exc

    conn = get_conn()
    try:
        return build_report(conn, city, date_value)
    finally:
        conn.close()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=False)
