"""Local-only governance of existing hashed-token identities, never password storage."""
import json, os, re, threading, uuid
from datetime import datetime, timezone
from pathlib import Path
from .auth import Principal
from . import frontend_workflows
LOCK=threading.RLock()
ROLES={"Admin","Risk/Compliance Analyst","Read-only/Auditor","Maintainer"}
def check(principal):
    if principal.role!="Admin":raise PermissionError("Admin required")
    if os.getenv("FINTRUST_MODE")!="local":raise PermissionError("Local identity governance only")
    path=os.getenv("FINTRUST_AUTH_FILE")
    if not path:raise PermissionError("Identity registry unavailable")
    return Path(path)
def metadata(p):
    return {"username":p["subject"],"display_name":p.get("display_name",p["subject"]),"role":p["role"],"status":p.get("status","ACTIVE"),"created_at":p.get("created_at"),"credential_provisioned":bool(p.get("token_sha256"))}
def listing(principal):
    with LOCK:
        registry=json.loads(check(principal).read_text(encoding="utf-8"))
        return [metadata(p) for p in registry["principals"] if set(p["accounts"])<=set(principal.accounts)]
def change(principal,body):
    check(principal)
    if not isinstance(body,dict) or set(body)!={"username","display_name","role","status","notes"}:raise ValueError("Exact local user fields required")
    if not isinstance(body["username"],str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}",body["username"]):raise ValueError("Invalid username")
    if not isinstance(body["role"],str) or not isinstance(body["status"],str) or body["role"] not in ROLES or body["status"] not in {"ACTIVE","DISABLED"}:raise ValueError("Approved role and status required")
    if not isinstance(body["display_name"],str) or not 1<=len(body["display_name"].strip())<=100:raise ValueError("Bounded display name required")
    if not isinstance(body["notes"],str) or not 1<=len(body["notes"].strip())<=500:raise ValueError("Change reason required")
    if body["username"]==principal.subject and (body["role"]!="Admin" or body["status"]!="ACTIVE"):raise ValueError("Cannot disable or demote current administrator")
    with LOCK:
        path=check(principal);registry=json.loads(path.read_text(encoding="utf-8"));users=registry["principals"]
        matches=[p for p in users if p["subject"]==body["username"]]
        if len(matches)>1:raise ValueError("Ambiguous registry identity")
        old=matches[0] if matches else None
        if old and not set(old["accounts"])<=set(principal.accounts):raise PermissionError("User outside assigned scope")
        if old and old["role"]=="Admin" and old.get("status","ACTIVE")=="ACTIVE" and (body["role"]!="Admin" or body["status"]!="ACTIVE") and sum(p["role"]=="Admin" and p.get("status","ACTIVE")=="ACTIVE" and bool(p.get("token_sha256")) for p in users)<=1:raise ValueError("Preserve an active provisioned administrator")
        entry=dict(old) if old else {"subject":body["username"],"accounts":list(principal.accounts),"token_sha256":"","created_at":datetime.now(timezone.utc).isoformat()}
        entry.update(display_name=body["display_name"].strip(),role=body["role"],status=body["status"])
        # Receipt is written before mutation: failure cannot silently grant authority.
        event={"event_id":str(uuid.uuid4()),"filename":"local-user-governance","actor":principal.subject,"actor_role":principal.role,"accounts":list(principal.accounts),"attempted_at":datetime.now(timezone.utc).isoformat(),"action":"USER_CREATED" if old is None else "USER_DISABLED" if old.get("status","ACTIVE")!="DISABLED" and entry["status"]=="DISABLED" else "USER_REACTIVATED" if old.get("status")=="DISABLED" and entry["status"]=="ACTIVE" else "USER_ROLE_CHANGED" if old["role"]!=entry["role"] else "USER_UPDATED","result":"REQUESTED","reason_code":None,"batch_id":None,"rows_processed":None,"target":entry["subject"],"before":metadata(old) if old else None,"after":metadata(entry),"notes":body["notes"].strip()}
        from . import score
        score.s3.put_object(Bucket=os.environ["QUARANTINE_BUCKET"],Key=frontend_workflows.PREFIX+event["event_id"]+".json",Body=json.dumps(event).encode(),ContentType="application/json",IfNoneMatch="*")
        updated=[entry if p["subject"]==entry["subject"] else p for p in users]
        if old is None:updated.append(entry)
        registry["principals"]=updated
        temp=path.with_name(path.name+"."+uuid.uuid4().hex+".tmp")
        try:
            temp.write_text(json.dumps(registry,indent=2)+"\n",encoding="utf-8");os.replace(temp,path)
        finally:
            if temp.exists():temp.unlink()
        event["result"]="SUCCESS"
        score.s3.put_object(Bucket=os.environ["QUARANTINE_BUCKET"],Key=frontend_workflows.PREFIX+event["event_id"]+".json",Body=json.dumps(event).encode(),ContentType="application/json")
        return metadata(entry)
