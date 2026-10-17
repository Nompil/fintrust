# Overview and Insights read performance

The preserved local Overview reader opened 62 database connections; its subsequent
all-dates Insights reader opened 38. A read-only measurement took 4.525 seconds
and 3.123 seconds respectively. Most time was spent establishing connections.

The corrected API endpoints each own one request-scoped, read-only PostgreSQL
REPEATABLE READ transaction. Existing readers borrow that connection; cleanup
rolls it back and closes it even on failure. Context-local state separates
concurrent requests. There is no cached result shared between users, and the
existing account filters and role checks remain authoritative.

The optimized preserved-source measurements were 0.647 seconds for Overview and
0.404 seconds for Insights, one connection each. These are local backend timings,
not full browser navigation timings or cloud load-test results.

The isolated PostgreSQL 16 regression passed 58 tests with no failures or skips,
covering read-only enforcement, error cleanup, concurrent-request separation,
account scope, SLA aggregates, query readers and case/analytical APIs. Its task-owned
database cluster was removed. The running local server was restarted without
reset or seed options. All 208 ledger rows and their contents, existing credentials,
and served static assets were verified preserved; unauthenticated Overview returned 401.

No AWS resource was changed. The previously staged and disabled cloud package does
not include this fix. Build, verify and deploy a new immutable final package before
claiming that the optimized code is running in AWS.
