"""Inspect and copy supplied synthetic CSV A/B bytes unchanged; no AWS or SQL."""
import sys as _runtime_sys
from pathlib import Path as _RuntimePath
_runtime_sys.path.insert(0, str(_RuntimePath(__file__).resolve().parents[1]/"backend"))
import argparse,csv,hashlib,io,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from fintrust.release_ingest import parse_file,FileRejected
NAMES=("fintrust_e2e_mixed_transactions.csv","fintrust_e2e_companion_transactions_B.csv")
def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("csv_a",type=Path);parser.add_argument("csv_b",type=Path);args=parser.parse_args()
    destination=ROOT/"tests/fixtures/e2e";destination.mkdir(parents=True,exist_ok=True);manifest=[]
    for path,name in zip((args.csv_a,args.csv_b),NAMES):
        payload=path.read_bytes();entry={"filename":name,"sha256":hashlib.sha256(payload).hexdigest(),"bytes":len(payload),"source_path_supplied_by_operator":str(path.resolve()),"unchanged":True}
        try:
            rows=parse_file(payload);entry.update(admission="PASSED",headers=next(csv.reader(io.StringIO(payload.decode("utf-8-sig")))),rows=len(rows),row_shape_errors=[{"source_row":n,"reason":error} for n,_,error in rows if error])
        except FileRejected as error:entry.update(admission="BLOCKED",reason_code=error.code)
        target=destination/name
        if target.exists() and target.read_bytes()!=payload:raise ValueError("Existing fixture differs; do not overwrite silently")
        target.write_bytes(payload);manifest.append(entry)
    # Remove machine paths from tracked fixture metadata.
    for entry in manifest:entry.pop("source_path_supplied_by_operator")
    (destination/"import-manifest.json").write_text(json.dumps({"files":manifest,"row_outcomes":"PENDING reviewed deterministic PG16 acceptance; import does not prove outcomes"},indent=2)+"\n")
    print(json.dumps(manifest,indent=2));return 0 if all(e["admission"]=="PASSED" for e in manifest) else 1
if __name__=="__main__":raise SystemExit(main())
