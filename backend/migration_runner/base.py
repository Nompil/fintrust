"""Fixed empty-schema initialization. No seed data, caller SQL or repair mode."""
import hashlib
from . import common, config

BASE_SHA256 = '1232b4a79fa601ab2f376fae575842d7a1caf009e2b542d2f0d845ed97f8d519'
MARKER = '-- Additive identity hardening.'


def source():
    text = (config.ROOT / 'sql/schema.sql').read_text(encoding='utf-8').replace('\r\n', '\n')
    if text.count(MARKER) != 1:
        raise common.Refused('base_source_boundary_mismatch')
    base = text.split(MARKER)[0]
    if hashlib.sha256(base.encode()).hexdigest() != BASE_SHA256:
        raise common.Refused('base_source_hash_mismatch')
    # A concurrent/unreviewed object must fail rather than be silently skipped.
    return base.replace('CREATE TABLE IF NOT EXISTS ', 'CREATE TABLE ').replace(
        'CREATE INDEX IF NOT EXISTS ', 'CREATE INDEX ')


def initialize(conn, op):
    if op != 'initialize_base':
        raise common.Refused('operation_not_allowed')
    body = source()
    with conn.cursor() as cur:
        common.setup(cur, read_only=False)
        common.session_check(cur, config.MASTER)
        cur.execute("SELECT pg_advisory_xact_lock(hashtext('fintrust-empty-base:public'))")
        cur.execute("""SELECT EXISTS(
            SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE n.nspname='public' AND NOT EXISTS(
              SELECT 1 FROM pg_depend d WHERE d.classid='pg_class'::regclass
                AND d.objid=c.oid AND d.deptype='e')) OR EXISTS(
            SELECT 1 FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
            WHERE n.nspname='public' AND NOT EXISTS(
              SELECT 1 FROM pg_depend d WHERE d.classid='pg_proc'::regclass
                AND d.objid=p.oid AND d.deptype='e')) OR EXISTS(
            SELECT 1 FROM pg_type t JOIN pg_namespace n ON n.oid=t.typnamespace
            WHERE n.nspname='public' AND t.typrelid=0 AND t.typtype IN ('d','e','r','m')
              AND NOT EXISTS(SELECT 1 FROM pg_depend d WHERE d.classid='pg_type'::regclass
                AND d.objid=t.oid AND d.deptype='e'))""")
        if cur.fetchone() != (False,):
            raise common.Refused('base_requires_empty_public_schema')
        cur.execute('SET LOCAL search_path = public, pg_catalog')
        cur.execute(body)
        catalog, data, assessment = common.inspect(cur)
        if not assessment['base_valid'] or assessment['state'] != 'absent':
            raise common.Refused('base_postcheck_failed')
        if any(row['owner'] != config.MASTER for row in catalog['relations']):
            raise common.Refused('base_owner_postcheck_failed')
        if any(data['row_counts'].values()):
            raise common.Refused('base_nonempty_postcheck_failed')
    return {'base_initialized': True, 'tables': list(config.TABLES),
            'row_counts': data['row_counts'], 'seed_executed': False,
            'identity_migration_applied': False}, True
