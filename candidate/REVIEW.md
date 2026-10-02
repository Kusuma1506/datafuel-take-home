# Review of review_me.py

These are the most important issues in the file, ranked from most serious to least serious. I fixed the top three in the script itself.

1. Shared mutable default argument causes cross-call contamination
   - What goes wrong: `fetch_inventory(..., results=[])` keeps a single list object for all calls. If one store call adds items, the next store inherits the old ones.
   - Concrete example: the second call for `MUM-002` can include products from `MUM-001` because the same list is reused.
   - Fix: make `results=None` and create a new list inside the function.

2. Requests have no timeout and can hang forever
   - What goes wrong: a slow request can block the whole script for 8+ seconds, and the loop continues forever without respect for server behavior.
   - Concrete example: a request to a slow endpoint can stall for 8 seconds; the script never exits or recovers cleanly.
   - Fix: use `timeout=5` and fail fast, then retry with limited attempts.

3. Retry loop does not distinguish permanent 4xx failures from transient failures
   - What goes wrong: the code catches every exception and retries forever, even for `400`, `401`, or `404`. Those responses will never succeed and can keep the process looping.
   - Concrete example: a wrong API key or malformed `as_of` hits 401 or 400 forever, wasting time and risking a soft ban.
   - Fix: do not retry on 400/401/404 and respect `Retry-After` on 429.

4. Wrong timestamp semantics for the day filter
   - What goes wrong: `datetime.utcnow().isoformat()` creates a timezone-naive string. The server expects ISO-8601 with timezone and the report logic must use IST day boundaries.
   - Concrete example: `2026-09-27T19:00:00Z` should count on the IST date `2026-09-28`, not on `2026-09-27`.
   - Fix: use UTC-aware timestamps and convert to IST before date filtering.

5. It writes SQL with string interpolation
   - What goes wrong: names with apostrophes or malicious input break the SQL and can corrupt data.
   - Concrete example: a name like `Amul's Milk` produces invalid SQL syntax.
   - Fix: use parameterized SQL and `INSERT OR REPLACE` when updating rows.

6. `city_osa` uses `qty` instead of the server's `in_stock` flag
   - What goes wrong: ghost stock (`in_stock=True`, `qty=0`) is silently treated as out of stock.
   - Concrete example: a product reported as in stock but with `qty=0` would be counted as unavailable.
   - Fix: process `in_stock` and ignore `qty` for the OSA calculation.

7. The script ignores whether the data is complete or incomplete
   - What goes wrong: incomplete snapshots are treated as normal inventory, which drags the OSA down unfairly.
   - Concrete example: one partial store with no items can falsely push the city OSA from 90% to 50%.
   - Fix: record completeness and exclude incomplete store-sweeps from the OSA calculation.

Fixed in the file:
- shared default list bug
- timeout + retry handling without infinite 4xx loops
- timezone-aware default as_of and IST-aware day logic
