# Notes

## Main decisions

- I track only stores where `is_active` is true. The server treats `is_serviceable` as a real-time operational flag; it can flip during the day and does not prove the store is part of the network. A shut-down store with `is_serviceable=true` is a data error, so we ignore inactive stores even if they look serviceable.
- I save the full roster of stores and flags to the database, but the OSA query only counts store-sweeps for active stores. That keeps the coverage honest and prevents dead stores from being counted as live inventory.
- The scraper uses a paced request loop (two requests per second) and never sends concurrent inventory calls. This is the main guard against the soft ban.
- Any inventory response where `meta.source` is not `origin` is treated as bad data. I discard the current attempt, wait, restart from page 1, and mark the store incomplete if the problem persists. This prevents degraded edge data from polluting the ledger.
- I dedupe by `sku_id` across pages and keep the latest row for that sku in a given store-sweep. I also reject `partial: true` snapshots entirely rather than converting missing data into out-of-stock.
- I store all timestamps in UTC, convert incoming strings to UTC before saving, and compute the IST day from the sweep's `as_of` UTC time. That keeps city-day logic consistent even when some cities return `+05:30` and others `Z`.
- If a rerun has incomplete data while a prior complete run exists for the same `(as_of, store_id)`, I keep the complete version rather than overwriting it. That preserves the stronger evidence and keeps re-runs idempotent.

## Answers to the short questions

- Brand says Delhi availability fell from 92% to 41% yesterday. What would you check first?
  I would first check coverage: how many Delhi stores were complete, whether any sweeps were partial or soft-banned, and whether the date fell on the correct IST day. Only after that would I inspect underlying stock-outs or store behavior.

- Dashboard says ₹4.20 lakh but store-level sum shows ₹4.61 lakh. Which number would you show and why?
  I would show the traceable number: the one built from the reconciled store-sweep rows, with the gap disclosed. If the totals differ, I would look for double counting, inactive stores, date boundary issues, or duplicate rows before claiming a result.

- Where would you not use an AI/LLM in this project?
  I would not use it to decide the final OSA math or parse partner responses deterministically. The calculations, completeness checks, and stored numbers need to be auditable and repeatable, so they should be implemented as explicit rules and tests.

## Bonus: 20,000 stores every 30 minutes

I would move the scraper to a queued worker model with a small concurrency limit, keep fair-use pacing per API key, separate ingestion from reporting, and persist coverage metadata so partial jobs can be retried later. I would also add alerts when `stores_complete` drops below a threshold for a city-day.
