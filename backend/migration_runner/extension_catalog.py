"""Tool-only catalog contract copied from frozen application; AST equality tested."""
import hashlib
import json
from .workflow_catalog import _catalog, SchemaDrift

def _catalog_for_version(cur,schema,version):
    if version in {4,5,6}:
        # Current whole workflow and lifecycle catalogs validate intentional evolution;
        # earlier historical snapshots remain immutable in schema_migrations.
        return hashlib.sha256((_catalog(cur,schema,2)+_catalog_for_version(cur,schema,3)).encode()).hexdigest()
    if version!=3: return _catalog(cur,schema,version)
    tables=("transaction_lifecycle_events",)
    cur.execute("""SELECT c.relname,a.attname,pg_catalog.format_type(a.atttypid,a.atttypmod),a.attnotnull,
        pg_get_expr(d.adbin,d.adrelid) FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid
        JOIN pg_namespace n ON n.oid=c.relnamespace LEFT JOIN pg_attrdef d ON d.adrelid=a.attrelid AND d.adnum=a.attnum
        WHERE n.nspname=%s AND c.relname=ANY(%s) AND a.attnum>0 AND NOT a.attisdropped ORDER BY c.relname,a.attnum""",(schema,list(tables)))
    columns=cur.fetchall()
    if {x[0] for x in columns}!=set(tables): raise SchemaDrift("Operational table missing")
    cur.execute("SELECT indexname,indexdef FROM pg_indexes WHERE schemaname=%s AND tablename=ANY(%s) ORDER BY indexname",(schema,list(tables)));indexes=cur.fetchall()
    cur.execute("""SELECT c.relname,k.conname,pg_get_constraintdef(k.oid) FROM pg_constraint k
        JOIN pg_class c ON c.oid=k.conrelid JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname=%s AND c.relname=ANY(%s) ORDER BY c.relname,k.conname""",(schema,list(tables)));constraints=cur.fetchall()
    cur.execute("""SELECT c.relname,t.tgname,pg_get_triggerdef(t.oid) FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid
        JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname=%s AND c.relname=ANY(%s) AND NOT t.tgisinternal ORDER BY c.relname,t.tgname""",(schema,list(tables)));triggers=cur.fetchall()
    cur.execute("SELECT viewname,definition FROM pg_views WHERE schemaname=%s AND viewname=ANY(%s) ORDER BY viewname",(schema,["batch_reconciliation","quarantine_workflow"]));views=cur.fetchall()
    cur.execute("""SELECT DISTINCT p.proname,pg_get_functiondef(p.oid),p.prosecdef,p.proconfig
        FROM pg_proc p JOIN pg_trigger t ON t.tgfoid=p.oid JOIN pg_class c ON c.oid=t.tgrelid
        JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname=%s AND c.relname=ANY(%s) ORDER BY p.proname""",(schema,list(tables)));functions=cur.fetchall()
    values=[columns,indexes,constraints,triggers,views,functions]
    return hashlib.sha256(json.dumps(values,default=str,sort_keys=True).encode()).hexdigest()
