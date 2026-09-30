-- Net movement from a zero opening balance, separately for each currency.
-- Transfers are treated as outgoing in this teaching model.
SELECT
    account_id,
    currency,
    tx_date,
    tx_id,
    CASE WHEN tx_type IN ('credit') THEN amount ELSE -amount END AS signed_amount,
    SUM(CASE WHEN tx_type IN ('credit') THEN amount ELSE -amount END) OVER (
        PARTITION BY account_id, currency
        ORDER BY tx_date, tx_id
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ) AS running_balance
FROM transactions
ORDER BY account_id, currency, tx_date, tx_id;
