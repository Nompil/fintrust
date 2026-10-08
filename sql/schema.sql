CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS customers (
    customer_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    full_name VARCHAR(150) NOT NULL,
    id_number VARCHAR(20) UNIQUE NOT NULL,
    kyc_status VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (kyc_status IN ('pending', 'verified', 'rejected', 'frozen')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS accounts (
    account_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id UUID NOT NULL REFERENCES customers(customer_id) ON DELETE RESTRICT,
    account_type VARCHAR(30) NOT NULL
        CHECK (account_type IN ('cheque', 'savings', 'credit', 'business')),
    balance NUMERIC(15, 2) NOT NULL DEFAULT 0.00,
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    opened_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS transactions (
    tx_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id UUID NOT NULL REFERENCES accounts(account_id) ON DELETE RESTRICT,
    amount NUMERIC(15, 2) NOT NULL CHECK (amount > 0),
    currency CHAR(3) NOT NULL DEFAULT 'ZAR'
        CHECK (currency IN ('ZAR', 'USD', 'EUR', 'GBP', 'KES')),
    merchant VARCHAR(200),
    tx_date TIMESTAMPTZ NOT NULL,
    tx_type VARCHAR(30) NOT NULL CHECK (tx_type IN ('debit', 'credit', 'transfer', 'fee')),
    cross_border BOOLEAN NOT NULL DEFAULT FALSE,
    raw_file VARCHAR(200) NOT NULL
);

CREATE TABLE IF NOT EXISTS risk_events (
    risk_event_id BIGSERIAL PRIMARY KEY,
    tx_id UUID NOT NULL REFERENCES transactions(tx_id),
    risk_score INTEGER NOT NULL CHECK (risk_score BETWEEN 0 AND 100),
    reason VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS alerts (
    alert_id BIGSERIAL PRIMARY KEY,
    risk_event_id BIGINT NOT NULL REFERENCES risk_events(risk_event_id),
    severity VARCHAR(20) NOT NULL,
    message TEXT NOT NULL,
    sent_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tx_account_date
    ON transactions (account_id, tx_date DESC);

CREATE INDEX IF NOT EXISTS idx_tx_high_amount
    ON transactions (amount) WHERE amount > 50000;

CREATE INDEX IF NOT EXISTS idx_tx_crossborder
    ON transactions (cross_border) WHERE cross_border = TRUE;

CREATE INDEX IF NOT EXISTS idx_risk_events_tx_date
    ON risk_events (tx_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_tx_account_cursor
    ON transactions (account_id, tx_date DESC, tx_id DESC);

-- Additive Phase 1 upgrade: existing historical alerts remain unverified (UNKNOWN).
ALTER TABLE transactions ALTER COLUMN raw_file TYPE TEXT;
ALTER TABLE alerts ALTER COLUMN sent_at DROP NOT NULL;
ALTER TABLE alerts ALTER COLUMN sent_at DROP DEFAULT;
ALTER TABLE alerts ADD COLUMN IF NOT EXISTS delivery_key BIGINT UNIQUE;
ALTER TABLE alerts ADD COLUMN IF NOT EXISTS delivery_state VARCHAR(10) NOT NULL DEFAULT 'UNKNOWN'
    CHECK (delivery_state IN ('PENDING','SENDING','SENT','FAILED','UNKNOWN'));
ALTER TABLE alerts ADD COLUMN IF NOT EXISTS provider_message_id TEXT;
CREATE TABLE IF NOT EXISTS processed_transactions (
    tx_id UUID PRIMARY KEY REFERENCES transactions(tx_id),
    fingerprint CHAR(64) NOT NULL,
    result JSONB NOT NULL,
    processed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Additive identity hardening. Review/apply as administrator before new workers.
ALTER TABLE transactions ADD COLUMN IF NOT EXISTS source_system VARCHAR(100);
ALTER TABLE transactions ADD COLUMN IF NOT EXISTS source_transaction_id VARCHAR(200);
ALTER TABLE transactions ADD COLUMN IF NOT EXISTS transaction_fingerprint CHAR(64)
    CHECK (transaction_fingerprint ~ '^[0-9a-f]{64}$');
ALTER TABLE transactions ADD COLUMN IF NOT EXISTS batch_id UUID;
ALTER TABLE transactions ADD COLUMN IF NOT EXISTS file_sha256 CHAR(64)
    CHECK (file_sha256 ~ '^[0-9a-f]{64}$');
ALTER TABLE transactions ADD COLUMN IF NOT EXISTS source_row INTEGER CHECK (source_row >= 2);
ALTER TABLE transactions ADD COLUMN IF NOT EXISTS country CHAR(2);
DO $$ BEGIN
    IF NOT EXISTS (SELECT FROM pg_constraint WHERE conname='transactions_source_identity_check'
                   AND conrelid='transactions'::regclass) THEN
        ALTER TABLE transactions ADD CONSTRAINT transactions_source_identity_check
            CHECK (source_transaction_id IS NULL OR
                   (length(btrim(source_transaction_id)) > 0 AND length(btrim(source_system)) > 0
                    AND source_system IS NOT NULL));
    END IF;
END $$;
-- References are unique within an upstream system/account, never amount/time.
CREATE UNIQUE INDEX IF NOT EXISTS idx_tx_source_identity
    ON transactions(source_system, account_id, source_transaction_id)
    WHERE source_transaction_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_tx_duplicate_charge
    ON transactions(account_id, merchant, currency, amount, tx_date)
    WHERE source_transaction_id IS NOT NULL;
-- Fingerprints intentionally have NO unique constraint: distinct charges survive.
