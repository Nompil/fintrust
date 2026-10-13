WITH high_risk AS (
    SELECT
        t.account_id,
        t.tx_date,
        COUNT(*) OVER (
            PARTITION BY t.account_id
            ORDER BY t.tx_date
            RANGE BETWEEN INTERVAL '30 days' PRECEDING AND CURRENT ROW
        ) AS tx_count_30d
    FROM transactions t
    WHERE EXISTS (
        SELECT 1 FROM risk_events re LEFT JOIN processed_transactions p USING(tx_id)
        WHERE re.tx_id = t.tx_id AND (p.result->>'risk_level'='High' OR (p.result IS NULL AND re.risk_score>=70))
    )
)
SELECT DISTINCT account_id
FROM high_risk
WHERE tx_count_30d > 3
ORDER BY account_id;
