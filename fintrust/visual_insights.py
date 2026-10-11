"""Read-only account-scoped aggregates. Historical unscored data is never given risk."""
from datetime import datetime,timedelta,timezone
from . import workflow_api as api
def read(principal,args):
    principal.require("read")
    if principal.role=="Maintainer":raise PermissionError("Financial insights unavailable to Maintainer")
    if set(args)-{"account_id","days"} or any(len(args.getlist(k))!=1 for k in args):raise ValueError("Unsupported insights filter")
    days=args.get("days","30")
    if days not in {"7","30","90","all"}:raise ValueError("Use 7, 30, 90 or all days")
    scope=[principal.account(args["account_id"])] if args.get("account_id") else list(principal.accounts)
    since=datetime.now(timezone.utc)-timedelta(days=int(days)) if days!="all" else datetime(1970,1,1,tzinfo=timezone.utc)
    params=(scope,since)
    where="t.account_id=ANY(%s::uuid[]) AND t.tx_date>=%s"
    q=api._query
    result={"days":days,"from_utc":since.isoformat(),"scope":"Transactions: assigned accounts, UTC time, counts rather than mixed-currency values. Batch/quality: administrator oversight including unassigned cases" if principal.role=="Admin" and not args.get("account_id") else "Assigned accounts, UTC time, counts rather than mixed-currency values. Batch totals include only wholly authorized batches; mixed/unassigned batches are excluded",
     "activity":q("SELECT (t.tx_date AT TIME ZONE 'UTC')::date::text AS label,count(*) AS count FROM transactions t WHERE "+where+" GROUP BY 1 ORDER BY 1",params),
     "accounts":q("SELECT t.account_id::text AS label,count(*) AS count FROM transactions t WHERE "+where+" GROUP BY 1 ORDER BY count(*) DESC,1",params),
     "cross_border":q("SELECT CASE WHEN t.cross_border THEN 'Cross-border' ELSE 'Domestic' END AS label,count(*) AS count FROM transactions t WHERE "+where+" GROUP BY 1 ORDER BY 1",params),
     "risk":q("SELECT p.result->>'risk_level' AS label,count(*) AS count FROM processed_transactions p JOIN transactions t USING(tx_id) WHERE "+where+" AND p.result->>'risk_level' IN ('Low','Medium','High') GROUP BY 1 ORDER BY 1",params),
     "rules":q("SELECT rule->>'rule' AS label,count(*) AS count FROM processed_transactions p JOIN transactions t USING(tx_id) CROSS JOIN LATERAL jsonb_array_elements(COALESCE(p.result->'triggered_rules','[]'::jsonb)) rule WHERE "+where+" GROUP BY 1 ORDER BY count(*) DESC,1",params),
     "reviews":q("SELECT w.review_status AS label,count(*) AS count FROM risk_reviews w JOIN risk_events r USING(risk_event_id) JOIN transactions t USING(tx_id) WHERE "+where+" GROUP BY 1 ORDER BY 1",params)}
    # Reuse batch/quarantine list authorization; never aggregate foreign-account rows.
    batches=[];quarantine=[]
    for kind,dest in (("batches",batches),("quarantine",quarantine)):
        from .auth import Principal
        scoped=principal if principal.role=="Admin" and not args.get("account_id") else Principal(principal.subject,"Read-only/Auditor",tuple(scope))
        page=api.list_page(kind,scoped,{"limit":100,**({"account_id":args["account_id"]} if args.get("account_id") else {})})
        for row in page["data"]:
            when=row.get("received_at" if kind=="batches" else "quarantined_at")
            if when and (datetime.fromisoformat(when.replace("Z","+00:00")) if isinstance(when,str) else when)>=since:dest.append(row)
        result[kind+"_bounded"]=page["meta"]["has_more"]
    reasons={}
    for row in quarantine:reasons[row["reason_code"]]=reasons.get(row["reason_code"],0)+1
    result["quality"]=[{"label":k,"count":v} for k,v in sorted(reasons.items())]
    result["batch_outcomes"]=[{"label":label,"count":sum(b.get(key) or 0 for b in batches)} for label,key in (("Accepted","accepted"),("Quarantined","quarantined"),("Duplicates","duplicate"),("Technical failures","failed_technical"),("Pending","pending"))]
    result["batch_reconciliation"]={"batches":len(batches),"rows_received":sum(b.get("rows_received") or 0 for b in batches),"counts_consistent":all(b["counts_consistent"] for b in batches),"unknown_totals":sum(b["rows_received"] is None for b in batches)}
    return result
