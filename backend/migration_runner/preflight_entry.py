from . import admin, common

def workflow_checkpoint(conn,op):
    """Verify exact 001/002 catalogs read-only, without replaying their DDL."""
    from . import config,iam
    from .workflow_catalog import _catalog,TABLES
    from .contract import assess,safe_report
    from .sql_binding import MIGRATION_SHA256
    from .release1_preflight import supplement
    with conn.cursor() as cur:
        common.setup(cur,read_only=True);iam.identity(cur)
        cur.execute('SELECT version,source_sha256,catalog_sha256 FROM public.schema_migrations ORDER BY version')
        saved=cur.fetchall()
        expected=[(1,MIGRATION_SHA256,_catalog(cur,'public',1)),
                  (2,'5b2c04440eea244bfce150347dfa1953dd2a7e7ddb6af7e3a66e187d1c912f02',_catalog(cur,'public',2))]
        if saved!=expected:raise common.Refused('checkpoint_002_catalog_or_history_mismatch')
        catalog=common.catalog(cur)
        # These triggers were just checked against the immutable 002 signature.
        # The original 001 checker still rejects every other table's triggers.
        catalog['triggers']=[t for t in catalog.get('triggers') or [] if t['table'] not in TABLES]
        data=common.data(cur);assessment=assess(catalog,data)
        if assessment['state']!='correct':raise common.Refused('checkpoint_001_contract_mismatch')
        result=safe_report(catalog,data,assessment);result['release1']=supplement(cur)
        result['workflow_checkpoint']={'version':2,'catalog_sha256':expected[1][2],'read_only':True}
    return result,False

def lambda_handler(event, context):
    if isinstance(event,dict) and event.get('operation')=='preflight_workflows':
        from . import iam
        return common.run(event,{'preflight_workflows'},iam.connection,workflow_checkpoint)
    return common.run(event, {"preflight"}, admin.connection, admin.preflight)
