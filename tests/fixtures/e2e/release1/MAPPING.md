# Release 1 fixture derivation

These are explicitly synthetic, test-only conventions, not an upstream banking mapping. Original CSV A/B remain byte-for-byte unchanged at their existing paths. Every original row remains in its original order. Invalid values are preserved to exercise quarantine.

| Original | Release 1 | Reason | Semantic change | Contract requirement |
|---|---|---|---|---|
| transaction_id: TX-* | source_transaction_id: same TX-* | Upstream reference, not internal UUID | Corrects identity interpretation; internal UUID is generated | Yes |
| ACC101/102/103/104 | 20000000-0000-4000-8000-000000000001/2/3/4 | Existing seeded accounts | Test-only alias mapping | Yes |
| ACC999999 | 20000000-0000-4000-8000-000000999999 | Valid UUID of an account deliberately absent from seed | Remains unknown | Yes |
| Empty account | Empty account | Preserve missing-value case | None | No conversion |
| transaction_timestamp | tx_date, unchanged value | Required header | None | Yes |
| transaction_type: PURCHASE | tx_type: debit | Test-only outgoing purchase convention | Explicit financial interpretation; not approved for real sources | Yes |
| No namespace | source_system: fintrust-e2e-release1 | Shared trusted namespace across A/B | Adds synthetic provenance | Yes |
| No merchant | merchant: Fixture Shop | Deterministic similar-charge context | Adds synthetic merchant metadata | Optional |
| amount/currency/country | Unchanged | Preserve boundaries and invalid values | None | Existing fields |

A appends R1-VEL-001..006 one minute apart, with different amounts: the sixth includes the first at the exact closed 300-second boundary. R1-VEL-OUTSIDE is 300 seconds plus one microsecond after the sixth. R1-HIGH-001 combines amount >200000 and US country for score 70. R1-INVALID-COUNTRY uses ZZA to exercise malformed country, alongside original ZZ unsupported country. B appends TX-E2E-005 with amount 75001 to conflict with the accepted 75000 trusted identity. Appended rows are test coverage, not original content.

Receipt clock is fixed to 2026-10-09T22:00:00Z. Local test seed timestamps are pinned to 2020 to prevent random historical seed velocity from polluting these event-time tests. Original twelve four-minute-spaced velocity rows are retained; they do not demonstrate >5 in five minutes. The 10/11/12-per-hour rule remains deferred.

## Independent expected outcomes

A: 42 received = 29 accepted + 12 quarantined + 1 duplicate + 0 technical failures. Accepted risk: 25 Low, 3 Medium, 1 High.
B: 12 received = 7 accepted + 4 quarantined + 1 duplicate + 0 technical failures. Accepted risk: 5 Low, 1 Medium, 1 High.
Exact A replay: DUPLICATE_FILE; no additional ledger, quarantine, reviews or alerts.
Total: 36 new ledger entries, 16 quarantine cases, 2 duplicate row occurrences; 4 Medium and 2 High reviews. All 36 accepted records retain risk metadata. Only the two High records are eligible for the implemented alert consumer.
