CREATE OR REPLACE VIEW v_account_summary AS
SELECT
    t.account_id,
    a.account_type,
    a.balance,
    a.status,
    c.full_name AS customer_name,
    c.kyc_status,
    COUNT(t.tx_id) AS total_transactions,
    MAX(t.tx_date) AS last_tx_date,
    COALESCE(SUM(t.amount), 0) AS total_tx_value
FROM accounts a
JOIN customers c ON c.customer_id = a.customer_id
LEFT JOIN transactions t ON t.account_id = a.account_id
GROUP BY a.account_id, a.account_type, a.balance, a.status,
         c.full_name, c.kyc_status;
