BEGIN;
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
COMMIT;
