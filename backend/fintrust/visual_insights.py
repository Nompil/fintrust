"""Read-only account-scoped aggregates. Historical unscored data is never given risk."""
from datetime import datetime,timedelta,timezone
import re
from . import workflow_api as api
from . import analyst_workflow as analyst
def read(principal,args):
    principal.require("read")
    if principal.role=="Maintainer":raise PermissionError("Financial insights unavailable to Maintainer")
    if set(args)-{"account_id","days","from","to","risk_level","scenario","review_status","country","tx_type","cross_border"} or any(len(args.getlist(k))!=1 for k in args):raise ValueError("Unsupported insights filter")
    days=args.get("days","30")
    if days not in {"1","7","30","90","all"}:raise ValueError("Use 1, 7, 30, 90 or all days")
    scope=[principal.account(args["account_id"])] if args.get("account_id") else list(principal.accounts)
    since=datetime.now(timezone.utc)-timedelta(days=int(days)) if days!="all" else datetime(1970,1,1,tzinfo=timezone.utc)
    params=[scope,since]
    where="t.account_id=ANY(%s::uuid[]) AND t.tx_date>=%s"
    until=None
    for key,operator in (("from",">="),("to","<")):
        if args.get(key):
            try:
                value=datetime.fromisoformat(args[key].replace("Z","+00:00"))
                if value.tzinfo is None:value=value.replace(tzinfo=timezone(timedelta(hours=2)))
                value=value.astimezone(timezone.utc)
            except (TypeError,ValueError):raise ValueError("Use a SAST date or timezone-bearing ISO timestamp") from None
            if key=="from":since=value;params[1]=value
            else:until=value
            where+=" AND t.tx_date"+operator+"%s";params.append(value)
    if until is not None and until<=since:raise ValueError("End must follow the start of the selected period")
    choices={"risk_level":{"Low","Medium","High"},"review_status":{"OPEN","UNDER_REVIEW","CLEARED","CONFIRMED_RISK","ESCALATED"},"tx_type":{"debit","credit","transfer","fee"},"scenario":{"AMOUNT_RISK","HIGH_AMOUNT","VERY_HIGH_AMOUNT","HIGH_VELOCITY","CROSS_BORDER","POSSIBLE_DUPLICATE_CHARGE","TRANSFER","MERCHANT_MARKER"}}
    for key,allowed in choices.items():
        if args.get(key) and args[key] not in allowed:raise ValueError("Unsupported analytical filter value")
    if args.get("country"):
        if not re.fullmatch("[A-Za-z]{2}",args["country"]):raise ValueError("Use a two-letter country code")
        where+=" AND t.country=%s";params.append(args["country"].upper())
    if args.get("tx_type"):where+=" AND t.tx_type=%s";params.append(args["tx_type"])
    if args.get('cross_border'):
        if args['cross_border'] not in {'0','1'}:raise ValueError('Use 1 for cross-border or 0 for domestic')
        where+=' AND t.cross_border=%s';params.append(args['cross_border']=='1')
    if args.get("risk_level"):
        where+=" AND EXISTS(SELECT 1 FROM processed_transactions fp WHERE fp.tx_id=t.tx_id AND fp.result->>'risk_level'=%s AND "+analyst.assessed_sql('fp')+")";params.append(args["risk_level"])
    if args.get("scenario"):
        where+=" AND EXISTS(SELECT 1 FROM processed_transactions fp CROSS JOIN LATERAL jsonb_array_elements(COALESCE(fp.result->'triggered_rules','[]'::jsonb)) fr WHERE fp.tx_id=t.tx_id AND fr->>'rule'=ANY(%s::text[]))";params.append(['AMOUNT_RISK','HIGH_AMOUNT','VERY_HIGH_AMOUNT'] if args['scenario']=='AMOUNT_RISK' else [args['scenario']])
    if args.get("review_status"):
        where+=" AND EXISTS(SELECT 1 FROM risk_reviews fw JOIN risk_events fe USING(risk_event_id) WHERE fe.tx_id=t.tx_id AND fw.review_status=%s)";params.append(args["review_status"])
    params=tuple(params)
    q=api._query
    result={"days":days,"from_utc":since.isoformat(),"scope":"Transactions: assigned accounts, SAST display with UTC timestamps retained, counts rather than mixed-currency values. Processing/quality: administrator oversight including unassigned cases" if principal.role=="Admin" and not args.get("account_id") else "Assigned accounts, SAST display with UTC timestamps retained, counts rather than mixed-currency values. Processing totals include only authorized runs; mixed/unassigned runs are excluded",
     "activity":q("SELECT (t.tx_date AT TIME ZONE 'Africa/Johannesburg')::date::text AS label,count(*) AS count FROM transactions t WHERE "+where+" GROUP BY 1 ORDER BY 1",params),
     "accounts":q("SELECT t.account_id::text AS label,count(*) AS count FROM transactions t WHERE "+where+" GROUP BY 1 ORDER BY count(*) DESC,1",params),
     "cross_border":q("SELECT CASE WHEN t.cross_border THEN 'Cross-border' ELSE 'Domestic' END AS label,count(*) AS count FROM transactions t WHERE "+where+" GROUP BY 1 ORDER BY 1",params),
     "risk":q("SELECT p.result->>'risk_level' AS label,count(*) AS count FROM processed_transactions p JOIN transactions t USING(tx_id) WHERE "+where+" AND "+analyst.assessed_sql()+" GROUP BY 1 ORDER BY 1",params),
     "rules":q("SELECT CASE WHEN rule->>'rule' IN ('HIGH_AMOUNT','VERY_HIGH_AMOUNT','AMOUNT_RISK') THEN 'AMOUNT_RISK' ELSE rule->>'rule' END AS label,count(DISTINCT p.tx_id) AS count FROM processed_transactions p JOIN transactions t USING(tx_id) CROSS JOIN LATERAL jsonb_array_elements(COALESCE(p.result->'triggered_rules','[]'::jsonb)) rule WHERE "+where+" GROUP BY 1 ORDER BY count(DISTINCT p.tx_id) DESC,1",params),
     "reviews":q("SELECT w.review_status AS label,count(*) AS count FROM risk_reviews w JOIN risk_events r USING(risk_event_id) JOIN transactions t USING(tx_id) WHERE "+where+" GROUP BY 1 ORDER BY 1",params)}
    result["rule_count_note"]="Amount risk groups legacy amount bands once per transaction. All classifications remain as recorded under their rule version; independent dimensions can overlap."
    result["scoring_versions"]=q("SELECT p.result->>'rule_version' AS label,count(*) AS count FROM processed_transactions p JOIN transactions t USING(tx_id) WHERE "+where+" GROUP BY 1 ORDER BY 1",params)
    result["risk_trend"]=q("SELECT (t.tx_date AT TIME ZONE 'Africa/Johannesburg')::date::text AS label,count(*) AS count FROM processed_transactions p JOIN transactions t USING(tx_id) WHERE "+where+" AND p.result->>'risk_level'='High' AND "+analyst.assessed_sql()+" GROUP BY 1 ORDER BY 1",params)
    result["high_accounts"]=q("SELECT t.account_id::text AS label,count(*) AS count FROM processed_transactions p JOIN transactions t USING(tx_id) WHERE "+where+" AND p.result->>'risk_level'='High' AND "+analyst.assessed_sql()+" GROUP BY 1 ORDER BY count(*) DESC,1",params)
    result["transactions"]=q(api.transaction_select()+" WHERE "+where+" ORDER BY t.tx_date DESC,t.tx_id LIMIT 25",params)
    from .analyst_workflow import assessment,policy
    for row in result['transactions']:
        assessment(row);row['risk_level']=(row.get('risk') or {}).get('risk_level')
    result['applied_filters']={k:v for k,v in args.items() if v}
    result['display_timezone']='Africa/Johannesburg'
    result['sla_policy']=policy()
    total=sum(r["count"] for r in result["activity"])
    scored=sum(r["count"] for r in result["risk"])
    high=sum(r["count"] for r in result["risk"] if r["label"]=="High")
    review_counts={r["label"]:r["count"] for r in result["reviews"]}
    risk_counts={r['label']:r['count'] for r in result['risk']}
    result["metrics"]={"transactions":total,"scored_transactions":scored,"high_risk_rate":round(100*high/scored,2) if scored else None,"high_count":high,"medium_count":risk_counts.get('Medium',0),"low_count":risk_counts.get('Low',0),"open_reviews":sum(review_counts.get(k,0) for k in ("OPEN","UNDER_REVIEW","ESCALATED")),"cleared":review_counts.get("CLEARED",0),"confirmed_risk":review_counts.get('CONFIRMED_RISK',0),"escalated":review_counts.get("ESCALATED",0)}
    for key in ('medium','low'):result['metrics'][key+'_risk_rate']=round(100*result['metrics'][key+'_count']/scored,2) if scored else None
    result['metrics'].update(api.review_workload(principal,where,params))
    result['metrics']['historical_unscored']=q("SELECT count(*) AS count FROM transactions t LEFT JOIN processed_transactions p USING(tx_id) WHERE "+where+" AND p.result IS NULL AND t.raw_file='seed/week13-day2.csv' AND t.batch_id IS NULL AND t.source_system IS NULL AND t.source_transaction_id IS NULL AND t.transaction_fingerprint IS NULL AND NOT EXISTS(SELECT 1 FROM ingestion_records i WHERE i.canonical_tx_id=t.tx_id)",params)[0]['count']
    result['metrics']['assessment_not_recorded']=max(0,total-scored-result['metrics']['historical_unscored'])
    result['metric_notes']={'high_risk_rate':'Recorded HIGH assessments / all recorded LOW, MEDIUM and HIGH assessments in the selected transaction scope. Historical unscored entries are excluded.', 'reviews_over_sla':'Active visible reviews beyond their configured target; escalation uses its recorded escalation time. No automatic decision is made.', 'quarantined':'Visible quarantine cases in the selected intake-date range; accepted-transaction risk filters do not apply.'}
    result["quality_scope_note"]="Quarantine and batch counts use account scope and intake date only; accepted-transaction risk, scenario, review, country and type filters do not apply to invalid rows. Review outcomes are current states of transactions in the selected period, not decisions made today."
    # Reuse batch/quarantine list authorization; never aggregate foreign-account rows.
    batches=[];quarantine=[]
    for kind,dest in (("batches",batches),("quarantine",quarantine)):
        from .auth import Principal
        scoped=principal if not args.get('account_id') else Principal(principal.subject,"Read-only/Auditor",tuple(scope))
        filters={'from':since.isoformat(),**({'to':until.isoformat()} if until else {}),**({'account_id':args['account_id']} if args.get('account_id') else {})}
        offset=0
        while True:
            page=api.list_page(kind,scoped,{'limit':100,'offset':offset,**filters})
            dest.extend(page['data'])
            if not page['meta']['has_more'] or offset>=100000:break
            offset+=100
        result[kind+"_bounded"]=page["meta"]["has_more"]
    reasons={}
    for row in quarantine:reasons[row["reason_code"]]=reasons.get(row["reason_code"],0)+1
    result["metrics"]["quarantined"]=len(quarantine)
    result['metrics']['quarantine_open']=sum(row['workflow_status']=='OPEN' for row in quarantine)
    result['metrics']['quarantine_resolved']=sum(row['workflow_status']=='RESOLVED' for row in quarantine)
    result['metrics']['quarantine_rejected']=sum(row['workflow_status']=='REJECTED' for row in quarantine)
    result['metrics']['processing_failures']=sum(b.get('failed_technical') or 0 for b in batches)
    result["quality"]=[{"label":k,"count":v} for k,v in sorted(reasons.items())]
    result["batch_outcomes"]=[{"label":label,"count":sum(b.get(key) or 0 for b in batches)} for label,key in (("Accepted","accepted"),("Quarantined","quarantined"),("Duplicates","duplicate"),("Technical failures","failed_technical"),("Pending","pending"))]
    result["batch_reconciliation"]={"batches":len(batches),"rows_received":sum(b.get("rows_received") or 0 for b in batches),"counts_consistent":all(b["counts_consistent"] for b in batches),"unknown_totals":sum(b["rows_received"] is None for b in batches)}
    return result
