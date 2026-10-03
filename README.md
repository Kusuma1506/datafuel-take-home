# DataFuel QuickMart OSA Take-home

A resilient scraper and FastAPI report API for on-shelf availability (OSA), backed by SQLite.

The implementation and assignment materials are in [`candidate/`](candidate/). These commands assume Windows PowerShell and a fresh clone of this repository.

## Setup

```powershell
cd candidate
python -m venv .venv
& ".\.venv\Scripts\python.exe" -m pip install -r requirements.txt
```

## Run

Start the mock portal in one terminal:

```powershell
cd candidate
& ".\.venv\Scripts\python.exe" mock_portal.py
```

In a second terminal, run all six required sweeps:

```powershell
cd candidate
& ".\.venv\Scripts\python.exe" sweep.py --as-of 2026-09-27T04:30:00Z
& ".\.venv\Scripts\python.exe" sweep.py --as-of 2026-09-27T10:30:00Z
& ".\.venv\Scripts\python.exe" sweep.py --as-of 2026-09-27T19:00:00Z
& ".\.venv\Scripts\python.exe" sweep.py --as-of 2026-09-28T04:30:00Z
& ".\.venv\Scripts\python.exe" sweep.py --as-of 2026-09-28T10:30:00Z
& ".\.venv\Scripts\python.exe" sweep.py --as-of 2026-09-28T18:40:00Z
```

Start the report API in another terminal:

```powershell
cd candidate
& ".\.venv\Scripts\python.exe" -m uvicorn app:app --host 127.0.0.1 --port 8001
```

Example request:

```powershell
Invoke-RestMethod "http://127.0.0.1:8001/osa?city=Mumbai&date=2026-09-28"
```

Run the tests from `candidate/`:

```powershell
cd candidate
& ".\.venv\Scripts\python.exe" -m pytest -q
```

If port 8765 is busy, start the portal with `$env:PORT=9000; & ".\.venv\Scripts\python.exe" mock_portal.py` and update `PORTAL` in `candidate/sweep.py` to use that port.
