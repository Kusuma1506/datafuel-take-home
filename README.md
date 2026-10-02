# datafuel-take-home
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

'''powershell
cd "c:\Users\KUSUMA\Downloads\datafuel-take-home (1)\candidate"
python -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
& ".venv\Scripts\Activate.ps1"
python -m pip install -r requirements.txt
Start the mock server
Open one terminal and run:
cd "c:\Users\KUSUMA\Downloads\datafuel-take-home (1)\candidate"
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
& ".venv\Scripts\Activate.ps1"
python mock_portal.py
If port 8765 is already in use, start on another port:
$env:PORT=9000; python mock_portal.py $env:PORT=9000; python mock_portal.py
Run the six required sweeps:
cd "c:\Users\KUSUMA\Downloads\datafuel-take-home (1)\candidate"
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
& ".venv\Scripts\Activate.ps1"

python sweep.py --as-of 2026-09-27T04:30:00Z
python sweep.py --as-of 2026-09-27T10:30:00Z
python sweep.py --as-of 2026-09-27T19:00:00Z
python sweep.py --as-of 2026-09-28T04:30:00Z
python sweep.py --as-of 2026-09-28T10:30:00Z
python sweep.py --as-of 2026-09-28T18:40:00Z
Start the API
Open a second terminal and run:
cd "c:\Users\KUSUMA\Downloads\datafuel-take-home (1)\candidate"
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
& ".venv\Scripts\Activate.ps1"
python -m uvicorn app:app --host 127.0.0.1 --port 8001


Check the API manually
Invoke-WebRequest "http://127.0.0.1:8001/osa?city=Mumbai&date=2026-09-28" -UseBasicParsing
Invoke-WebRequest "http://127.0.0.1:8001/osa?city=Delhi&date=2026-09-28" -UseBasicParsing
Invoke-WebRequest "http://127.0.0.1:8001/osa?city=Bengaluru&date=2026-09-28" -UseBasicParsing
Invoke-WebRequest "http://127.0.0.1:8001/osa?city=Paris" -UseBasicParsing
Run tests
cd "c:\Users\KUSUMA\Downloads\datafuel-take-home (1)\candidate"
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
& ".venv\Scripts\Activate.ps1"
pytest -q
