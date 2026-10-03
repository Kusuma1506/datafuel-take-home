# DataFuel QuickMart OSA Take-home

This project implements a resilient scraper for the QuickMart mock API and a FastAPI endpoint that reports on-shelf availability (`/osa`) for a city and IST date.

## Overview

- Scraper: `sweep.py`
- API: `app.py`
- SQLite database: `osa.db`
- Tests: `tests/`
- Review: `REVIEW.md`
- Notes: `NOTES.md`
- AI log: `AI_LOG.md`

## Setup on Windows

Run these commands from the repository root:

```powershell
cd candidate
python -m venv .venv
& ".\.venv\Scripts\python.exe" -m pip install -r requirements.txt
```

## Start the mock server

Open one terminal and run:

```powershell
cd candidate
& ".\.venv\Scripts\python.exe" mock_portal.py
```

If port 8765 is already in use, start on another port:

```powershell
$env:PORT=9000; python mock_portal.py
```

## Run the six required sweeps

```powershell
cd candidate
& ".\.venv\Scripts\python.exe" sweep.py --as-of 2026-09-27T04:30:00Z
& ".\.venv\Scripts\python.exe" sweep.py --as-of 2026-09-27T10:30:00Z
& ".\.venv\Scripts\python.exe" sweep.py --as-of 2026-09-27T19:00:00Z
& ".\.venv\Scripts\python.exe" sweep.py --as-of 2026-09-28T04:30:00Z
& ".\.venv\Scripts\python.exe" sweep.py --as-of 2026-09-28T10:30:00Z
& ".\.venv\Scripts\python.exe" sweep.py --as-of 2026-09-28T18:40:00Z
```

## Start the API

Open a second terminal and run:

```powershell
cd candidate
& ".\.venv\Scripts\python.exe" -m uvicorn app:app --host 127.0.0.1 --port 8001
```

## Check the API manually

```powershell
Invoke-WebRequest "http://127.0.0.1:8001/osa?city=Mumbai&date=2026-09-28" -UseBasicParsing
Invoke-WebRequest "http://127.0.0.1:8001/osa?city=Delhi&date=2026-09-28" -UseBasicParsing
Invoke-WebRequest "http://127.0.0.1:8001/osa?city=Bengaluru&date=2026-09-28" -UseBasicParsing
Invoke-WebRequest "http://127.0.0.1:8001/osa?city=Paris" -UseBasicParsing
```

## Run tests

```powershell
cd candidate
& ".\.venv\Scripts\python.exe" -m pytest -q
```

## Notes on correctness

- Only active stores are tracked.
- Incomplete store-sweeps are excluded from OSA calculations and included in `coverage.incomplete`.
- The scraper handles rate limits, timeouts, retries, soft bans, partial snapshots, duplicate items, and mixed timestamp formats.
- The API uses `in_stock` rather than `qty`, and date grouping is based on IST calendar days.

