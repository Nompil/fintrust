CREATE OR REPLACE VIEW v_account_summary AS
SELECT
    a.account_id,
    a.account_type,
    a.balance,
    a.status,
    c.full_name AS customer_name,
    c.kyc_status,
    COUNT(t.tx_id) AS total_transactions,
    MAX(t.tx_date) AS last_tx_date,
    CASE WHEN COUNT(t.tx_id) = 0 THEN 0
         WHEN COUNT(DISTINCT t.currency) = 1 THEN SUM(t.amount)
         ELSE NULL END AS total_tx_value,
    CASE WHEN COUNT(DISTINCT t.currency) = 1 THEN MAX(t.currency)
         ELSE NULL END AS currency
FROM accounts a
JOIN customers c ON c.customer_id = a.customer_id
LEFT JOIN transactions t ON t.account_id = a.account_id
GROUP BY a.account_id, a.account_type, a.balance, a.status,
         c.full_name, c.kyc_status;

CREATE OR REPLACE VIEW v_account_currency_summary AS
SELECT account_id, currency, COUNT(*) AS total_transactions,
       SUM(amount) AS gross_amount
FROM transactions
GROUP BY account_id, currency;
