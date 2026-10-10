# Release 1 CSV acceptance manifest

Actual external artifacts: CSV A `fintrust_e2e_mixed_transactions.csv` and CSV B
`fintrust_e2e_companion_transactions_B.csv`. Both are outside the repository.
**Their paths, bytes, hashes, transaction references and exact counts are unknown.**
Do not invent these. No claim that the actual A/B datasets were executed.
The executable local scenarios in `tests/test_release1_end_to_end.py` exercise
these decisions; they are constructed test cases, not replacements for A/B.
Import later into a reviewed fixture directory, preserve original bytes, record
SHA256, record each row/reference expectation and freeze first receipt timestamps.
Until then this is a scenario manifest, not a per-row manifest of unseen files.

| Scenario | Validation/quarantine | Identity outcome | Risk flags / level | Alert / review | Reconciliation contribution |
|---|---|---|---|---|---|
| Normal debit 10 ZAR, ZA | Valid | ACCEPTED | 0 Low | Neither | accepted +1 |
| 49,999.99 / 50,000.00 | Valid | ACCEPTED | No HIGH_AMOUNT, 0 Low | Neither | accepted +1 each |
| 50,000.01 | Valid | ACCEPTED | HIGH_AMOUNT, 30 Low | Neither by amount alone | accepted +1 |
| 200,000.00 | Valid | ACCEPTED | HIGH_AMOUNT, 30 Low | Neither alone | accepted +1 |
| 200,000.01 | Valid | ACCEPTED | HIGH_AMOUNT + VERY_HIGH_AMOUNT, 55 Medium | Review required; no automatic email | accepted +1 |
| Foreign supported country only | Valid | ACCEPTED | CROSS_BORDER, 15 Low | Neither; not a fraud verdict | accepted +1 |
| 200,000.01 + foreign country | Valid | ACCEPTED | 55 + 15 = 70 High | One logical alert; review required | accepted +1 |
| Five accepted events within 300 seconds | Valid | ACCEPTED | No HIGH_VELOCITY | Other factors determine review/alert | accepted +1 per distinct event |
| Sixth accepted event at exactly 300 seconds from first | Valid | ACCEPTED | HIGH_VELOCITY +30; current counts itself | Other factors determine level | accepted +1 |
| Sixth at 300 seconds +1 microsecond (others at 60/120/180/240) | Valid | ACCEPTED | First excluded, count5; no velocity | Other factors determine level | accepted +1 |
| 10/11/12 spread over one hour | Valid | ACCEPTED | No hourly rule exists; explore future rule only | Depends on actual five-minute clustering/other factors | accepted per distinct event |
| Very high + cross-border + velocity | Valid | ACCEPTED | 55+15+30=100 High | One logical alert; review | accepted +1 |
| Same source identity/equal content repeated in file | Valid values | DUPLICATE, canonical tx linked | Reuse frozen canonical result | No second logical alert/review | duplicate +1, not quarantine |
| Same accepted identity in different file | Valid values | DUPLICATE_TRANSACTION | Frozen result reused | No additional logical effect | duplicate +1 |
| Same identity/changed amount or other material field | DUPLICATE_IDENTITY_CONFLICT | QUARANTINED | Not rescored into ledger | Correction review; no email | quarantined +1 |
| Whole identical file renamed/reuploaded/new version | Audit DUPLICATE_FILE attempt | Original batch/occurrences unchanged | No rescoring | No new logical effects | no new rows in original batch |
| Distinct source IDs, same account/merchant/currency/amount, within closed +/-120s | Valid | Both ACCEPTED | POSSIBLE_DUPLICATE_CHARGE +40 on subsequent admission; Medium minimum | Review, not database dedup | accepted +1 each |
| Missing account/amount/date/type/country/currency | MISSING_REQUIRED_FIELD; multiple deterministic reasons | QUARANTINED | None | Correction | quarantined +1 |
| Unknown UUID account | UNKNOWN_ACCOUNT | QUARANTINED | None | Admin assigns eligible scoped account for correction | quarantined +1 |
| Closed/inactive account, genuinely new identity | INACTIVE_ACCOUNT | QUARANTINED | None | Correction/operational review | quarantined +1 |
| Missing stable source namespace/reference | MISSING_SOURCE_IDENTITY | QUARANTINED | None | Correction | quarantined +1 |
| Missing internal UUID but valid stable source identity | Valid; deterministic internal UUID generated | ACCEPTED | Normal rules | Normal behavior | accepted +1 |
| Non-numeric/nonfinite amount | INVALID_AMOUNT | QUARANTINED | None | Correction | quarantined +1 |
| Zero / negative amount | ZERO_AMOUNT / NEGATIVE_AMOUNT | QUARANTINED | None | Correction; not a refund conversion | quarantined +1 |
| More than two nonzero decimal places / amount >=10^13 | AMOUNT_PRECISION / AMOUNT_OUT_OF_RANGE | QUARANTINED | None | Correction | quarantined +1 |
| Refund/reversal/chargeback type | UNSUPPORTED_FINANCIAL_OPERATION | QUARANTINED | None | Deferred business semantics | quarantined +1 |
| Malformed/naive/date-only/impossible or >6-digit precision timestamp | INVALID_TIMESTAMP | QUARANTINED | None | Correction | quarantined +1 |
| Timestamp > first receipt +5min | FUTURE_TIMESTAMP; equality permitted | QUARANTINED if above | None | Correction; retries use original receipt | quarantined +1 |
| Late transaction | Valid, no arbitrary lower-age rejection | ACCEPTED | Event-time history known at arrival; no retroactive rescoring | Normal behavior | accepted +1 |
| Unsupported country / currency | UNSUPPORTED_COUNTRY / UNSUPPORTED_CURRENCY | QUARANTINED | None | Correction | quarantined +1 |
| Extra values / short row / row >32 KiB | MALFORMED_ROW / ROW_TOO_LARGE | QUARANTINED | None | Correction | quarantined +1 |
| Empty/header-only file | FAILED, EMPTY_FILE / HEADER_ONLY_FILE | No financial rows | None | Operational failure visible | received0, FAILED |
| Header drift/malformed quoting/invalid UTF8/oversized file or >5000 rows | File failure before any financial publication | No partial financial publication | None | Operational repair and immutable retry | total unknown where unparseable; FAILED |

Only five currencies (ZAR/USD/EUR/GBP/KES) and six demo countries
(ZA/US/GB/KE/DE/FR) are approved; this is an explicit demo whitelist, not complete
ISO validation. Thresholds apply in transaction currency, without FX conversion.
A possible duplicate depends on accepted history/arrival order; A/B expectations
must therefore specify execution order and the first receipt clock.

The ledger outcome partition is `received = accepted + quarantined + duplicate +
technical_failed + pending`. A retry of the same occurrence changes no totals.
A different corrected occurrence belongs to its own correction batch.
Business completion and projection/alert delivery backlogs are separate.
