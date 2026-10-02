# QuickMart DataFuel take-home

This repo contains a safe scraper for the QuickMart API, an idempotent SQLite database, and a FastAPI report endpoint for `/osa`.

## Setup

```bash
python -m venv venv
# Windows
venv\Scripts\activate
# macOS / Linux
# source venv/bin/activate

python -m pip install -r requirements.txt
```

## Start the mock server

In one terminal:

```bash
python mock_portal.py
```

If port 8765 is busy:

```bash
$env:PORT=9000; python mock_portal.py
```

Then use port 9000 everywhere below.

## Run the sweeps

```bash
python sweep.py --as-of 2026-09-27T04:30:00Z
python sweep.py --as-of 2026-09-27T10:30:00Z
python sweep.py --as-of 2026-09-27T19:00:00Z
python sweep.py --as-of 2026-09-28T04:30:00Z
python sweep.py --as-of 2026-09-28T10:30:00Z
python sweep.py --as-of 2026-09-28T18:40:00Z
```

The script writes to `osa.db` and keeps output idempotent.

## Start the report API

```bash
uvicorn app:app --host 127.0.0.1 --port 8000
```

Then request:

```bash
curl "http://127.0.0.1:8000/osa?city=Mumbai&date=2026-09-28"
curl "http://127.0.0.1:8000/osa?city=Delhi"
curl "http://127.0.0.1:8000/osa?city=Bengaluru"
```

## Run tests

```bash
pytest -q
```

## Notes

- Only active stores are tracked for OSA reporting.
- Incomplete store-sweeps are explicitly excluded from the OSA math and listed in `coverage.incomplete`.
- The server is intentionally flaky; the scraper handles 429, slow requests, partial data, duplicates, soft bans, and mixed timezones without storing bad numbers.

  (If it won't even start, email us.)
- **The brief doesn't say how to handle something.** Pick a sensible option, write it in
  `NOTES.md`, move on.
- **Can I look inside `mock_portal.py`?** Yes, you can read it, but build your code from
  `API.md` and what you observe, as you would with a real app whose code you can't see.
- **Do I need a camera?** No. Screen + voice is enough.
- **I can't finish in time.** Submit what you have, with `NOTES.md` explaining what's left.
- **Questions?** vansh@datafuel.tech. Asking is a good sign, not a bad one.
