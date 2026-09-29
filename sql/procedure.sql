CREATE OR REPLACE FUNCTION flag_account(p_account_id UUID, p_reason TEXT)
RETURNS VOID AS $$
DECLARE
    latest_tx_id UUID;
BEGIN
    SELECT tx_id INTO latest_tx_id
    FROM transactions
    WHERE account_id = p_account_id
    ORDER BY tx_date DESC
    LIMIT 1;

    IF latest_tx_id IS NULL THEN
        RAISE EXCEPTION 'No transactions found for account %', p_account_id;
    END IF;

    INSERT INTO risk_events (tx_id, risk_score, reason)
    VALUES (latest_tx_id, 100, p_reason);

    UPDATE accounts
    SET status = 'monitoring'
    WHERE account_id = p_account_id;
END;
$$ LANGUAGE plpgsql;
