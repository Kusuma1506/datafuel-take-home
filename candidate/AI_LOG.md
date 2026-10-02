# AI log

I used GitHub Copilot to help draft the initial schema, the pacing logic, and the API query shape. I checked every result against the server behavior in `mock_portal.py` and the contract in `API.md` before accepting it.

## Prompts that mattered

1. "Design a SQLite schema for a safe, idempotent sweep that records incomplete store snapshots and OSA calculations."
2. "Explain the soft-ban pattern in this QuickMart API and how to detect it without saving degraded data."
3. "Write a FastAPI route that validates city/date and computes city OSA from complete store-sweeps only."

## Times the AI was wrong

1. It initially suggested sending inventory requests in parallel. That would trigger the soft ban almost immediately. I caught this by observing `meta.source == "edge"` and the server's fair-use behavior.
2. It initially suggested grouping by the UTC date instead of the IST date. I noticed that 19:00 UTC on 27 Sep is 00:30 IST on 28 Sep, which changes the day grouping. The tests cover this exact case.
3. It suggested using `qty` for the in-stock calculation. I rejected that because the assignment explicitly says to use `in_stock`, and the server includes ghost stock cases where `in_stock=true` but `qty=0`.

## Final check

I rely on the API contract, the mocked portal behavior, and validation tests rather than trusting the AI output uncritically.
