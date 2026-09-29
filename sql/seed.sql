INSERT INTO customers (customer_id, full_name, id_number, kyc_status)
VALUES
    ('10000000-0000-4000-8000-000000000001', 'Ava Mokoena', 'ID-FT-0001', 'verified'),
    ('10000000-0000-4000-8000-000000000002', 'Liam Botha', 'ID-FT-0002', 'verified'),
    ('10000000-0000-4000-8000-000000000003', 'Noah Naidoo', 'ID-FT-0003', 'pending'),
    ('10000000-0000-4000-8000-000000000004', 'Mia Patel', 'ID-FT-0004', 'verified'),
    ('10000000-0000-4000-8000-000000000005', 'Zoe Govender', 'ID-FT-0005', 'verified')
ON CONFLICT (customer_id) DO NOTHING;

INSERT INTO accounts (account_id, customer_id, account_type, balance, status)
VALUES
    ('20000000-0000-4000-8000-000000000001', '10000000-0000-4000-8000-000000000001', 'cheque', 12000.00, 'active'),
    ('20000000-0000-4000-8000-000000000002', '10000000-0000-4000-8000-000000000002', 'savings', 43500.00, 'active'),
    ('20000000-0000-4000-8000-000000000003', '10000000-0000-4000-8000-000000000003', 'cheque', 8200.00, 'active'),
    ('20000000-0000-4000-8000-000000000004', '10000000-0000-4000-8000-000000000004', 'business', 98000.00, 'active'),
    ('20000000-0000-4000-8000-000000000005', '10000000-0000-4000-8000-000000000005', 'credit', -2500.00, 'active')
ON CONFLICT (account_id) DO NOTHING;

INSERT INTO transactions (tx_id, account_id, amount, currency, merchant, tx_date, tx_type, cross_border, raw_file)
SELECT
    ('30000000-0000-4000-8000-' || LPAD(item::text, 12, '0'))::UUID,
    ('20000000-0000-4000-8000-' || LPAD((1 + ((item - 1) % 5))::text, 12, '0'))::UUID,
    ROUND((50 + RANDOM() * 24950)::numeric, 2),
    CASE WHEN item % 19 = 0 THEN 'USD' ELSE 'ZAR' END,
    CASE WHEN item % 13 = 0 THEN 'HighRisk Retail' ELSE 'FinTrust Merchant' END,
    NOW() - ((item % 90) || ' days')::INTERVAL,
    CASE item % 4
        WHEN 0 THEN 'credit'
        WHEN 1 THEN 'debit'
        WHEN 2 THEN 'transfer'
        ELSE 'fee'
    END,
    item % 17 = 0,
    'seed/week13-day2.csv'
FROM generate_series(1, 200) AS item
ON CONFLICT (tx_id) DO NOTHING;

INSERT INTO risk_events (tx_id, risk_score, reason)
SELECT
    t.tx_id,
    CASE WHEN t.cross_border THEN 75 ELSE 65 END,
    CASE WHEN t.cross_border THEN 'cross_border_seed_rule' ELSE 'high_value_seed_rule' END
FROM transactions t
WHERE t.raw_file = 'seed/week13-day2.csv'
  AND (t.cross_border OR t.amount > 15000)
  AND NOT EXISTS (
      SELECT 1 FROM risk_events re WHERE re.tx_id = t.tx_id
  );
