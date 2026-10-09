-- Fixed, parameterless, transactional helper. Installed in the bootstrap transaction.
CREATE FUNCTION public.fintrust_create_identity_indexes() RETURNS void
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $helper$
DECLARE
    target oid;
    expected record;
    actual record;
BEGIN
    IF session_user <> 'fintrust_migrate_dev' OR current_user <> 'fintrust_index_builder'
       OR current_database() <> 'fintrust' THEN
        RAISE EXCEPTION 'index helper identity mismatch';
    END IF;
    LOCK TABLE public.transactions IN ACCESS EXCLUSIVE MODE;
    target := pg_catalog.to_regclass('public.transactions');
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_class WHERE oid=target
        AND relkind='r' AND relowner='fintrust_transactions_owner'::pg_catalog.regrole
        AND relam=(SELECT oid FROM pg_catalog.pg_am WHERE amname='heap')
        AND NOT relrowsecurity AND NOT relforcerowsecurity) THEN
        RAISE EXCEPTION 'index helper table mismatch';
    END IF;
    -- Prevent table-owner-controlled types/collations/expressions from executing
    -- as the definer. Only the exact built-in column types are accepted.
    FOR expected IN SELECT * FROM (VALUES
        ('source_system','character varying(100)'),
        ('source_transaction_id','character varying(200)'),
        ('account_id','uuid'),('merchant','character varying(200)'),
        ('currency','character(3)'),('amount','numeric(15,2)'),
        ('tx_date','timestamp with time zone')) AS v(name, kind)
    LOOP
        IF NOT EXISTS (SELECT FROM pg_catalog.pg_attribute a
            JOIN pg_catalog.pg_type t ON t.oid=a.atttypid
            WHERE a.attrelid=target AND a.attname=expected.name AND NOT a.attisdropped
            AND a.attnum>0 AND a.attgenerated='' AND a.attidentity=''
            AND t.typnamespace='pg_catalog'::pg_catalog.regnamespace
            AND pg_catalog.format_type(a.atttypid,a.atttypmod)=expected.kind
            AND (a.attcollation=0 OR a.attcollation='pg_catalog.default'::pg_catalog.regcollation)) THEN
            RAISE EXCEPTION 'index helper column mismatch';
        END IF;
    END LOOP;
    IF EXISTS (SELECT FROM pg_catalog.pg_trigger WHERE tgrelid=target AND NOT tgisinternal)
       OR EXISTS (SELECT FROM pg_catalog.pg_policy WHERE polrelid=target) THEN
        RAISE EXCEPTION 'index helper relation security mismatch';
    END IF;
    -- Check all collisions before creating either index; never trust IF NOT EXISTS.
    FOR expected IN SELECT * FROM (VALUES
      ('idx_tx_source_identity', 'CREATE UNIQUE INDEX idx_tx_source_identity ON public.transactions USING btree (source_system, account_id, source_transaction_id) WHERE (source_transaction_id IS NOT NULL)'),
      ('idx_tx_duplicate_charge', 'CREATE INDEX idx_tx_duplicate_charge ON public.transactions USING btree (account_id, merchant, currency, amount, tx_date) WHERE (source_transaction_id IS NOT NULL)')) AS v(name, definition)
    LOOP
      IF pg_catalog.to_regclass('public.' || expected.name) IS NOT NULL THEN
        SELECT i.indrelid, i.indisvalid, i.indisready, c.relowner,
               pg_catalog.pg_get_indexdef(i.indexrelid) AS definition INTO actual
        FROM pg_catalog.pg_index i JOIN pg_catalog.pg_class c ON c.oid=i.indexrelid
        WHERE i.indexrelid=pg_catalog.to_regclass('public.' || expected.name);
        IF NOT FOUND OR actual.indrelid IS DISTINCT FROM target
          OR actual.indisvalid IS DISTINCT FROM true OR actual.indisready IS DISTINCT FROM true
          OR actual.relowner IS DISTINCT FROM 'fintrust_transactions_owner'::pg_catalog.regrole
          OR actual.definition IS DISTINCT FROM expected.definition THEN
            RAISE EXCEPTION 'index helper definition conflict';
        END IF;
      END IF;
    END LOOP;
    CREATE UNIQUE INDEX IF NOT EXISTS idx_tx_source_identity
        ON public.transactions(source_system, account_id, source_transaction_id)
        WHERE source_transaction_id IS NOT NULL;
    CREATE INDEX IF NOT EXISTS idx_tx_duplicate_charge
        ON public.transactions(account_id, merchant, currency, amount, tx_date)
        WHERE source_transaction_id IS NOT NULL;
    -- Disappear in the caller transaction. Later postcheck failure rolls this
    -- DROP and both indexes/column changes back, leaving a retryable helper.
    DROP FUNCTION public.fintrust_create_identity_indexes();
END
$helper$;
REVOKE ALL ON FUNCTION public.fintrust_create_identity_indexes() FROM PUBLIC;
ALTER FUNCTION public.fintrust_create_identity_indexes() OWNER TO fintrust_index_builder;
SET LOCAL ROLE fintrust_index_builder;
GRANT EXECUTE ON FUNCTION public.fintrust_create_identity_indexes() TO fintrust_migrate_dev;
RESET ROLE;
GRANT fintrust_index_builder TO fintrust_admin WITH SET FALSE, INHERIT FALSE, ADMIN FALSE;
-- Fail closed if administrator default privileges introduced another executor.
DO $$ BEGIN
 IF EXISTS (SELECT FROM pg_catalog.pg_proc p,
    LATERAL pg_catalog.aclexplode(COALESCE(p.proacl,pg_catalog.acldefault('f',p.proowner))) a
    WHERE p.oid='public.fintrust_create_identity_indexes()'::pg_catalog.regprocedure
      AND a.grantee NOT IN ('fintrust_index_builder'::pg_catalog.regrole,'fintrust_migrate_dev'::pg_catalog.regrole)) THEN
    RAISE EXCEPTION 'unexpected index helper executor';
 END IF;
END $$;
