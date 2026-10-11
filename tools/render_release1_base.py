"""Render reviewed base SQL only. No database connection, AWS call or seeding."""
import hashlib,json,argparse
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def render():
    manifest=json.loads((ROOT/"sql/bootstrap/release1-base-manifest.json").read_text(encoding="utf-8"))
    source=(ROOT/manifest["base"]["path"]).read_text(encoding="utf-8").replace("\r\n","\n")
    marker="-- Additive identity hardening."
    if source.count(marker)!=1:raise ValueError("Base section boundary changed; review required")
    base=source.split(marker)[0]
    if hashlib.sha256(base.encode()).hexdigest()!=manifest["base"]["sha256"]:raise ValueError("Base source checksum mismatch; review required")
    guard="""DO $$ BEGIN
IF EXISTS(SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
 WHERE n.nspname='public' AND c.relkind IN ('r','p','v','m','S','f')
 AND NOT EXISTS(SELECT 1 FROM pg_depend d WHERE d.classid='pg_class'::regclass AND d.objid=c.oid AND d.deptype='e'))
THEN RAISE EXCEPTION 'Base bootstrap requires an empty application schema; manual review required'; END IF;
END $$;
"""
    return "-- PROPOSED: PostgreSQL 16 verification and live approval required. No seed data.\nBEGIN;\n"+guard+base+"\nCOMMIT;\n"
if __name__=="__main__":
    parser=argparse.ArgumentParser();parser.add_argument("--output",required=True);args=parser.parse_args()
    output=Path(args.output).resolve()
    build=(ROOT/"build").resolve()
    if not output.is_relative_to(build):raise ValueError("Output must remain in ignored build directory")
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(render(),encoding="utf-8")
    print("Base SQL rendered locally; not executed. PostgreSQL 16 gate remains required.")
