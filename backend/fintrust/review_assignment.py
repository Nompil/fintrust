"""One owner per review, versioned and audited through existing domain history."""
import os,uuid
from datetime import datetime,timezone
from psycopg2.extras import RealDictCursor
from . import workflow_api as api
from .identity_registry import read_registry,locked_registry
from .local_users import metadata
def sla_seconds():
    raw=os.getenv('FINTRUST_REVIEW_SLA_SECONDS')
    if raw is None:return None
    if not raw.isdigit() or not 60<=int(raw)<=31536000:raise ValueError('Invalid configured review SLA')
    return int(raw)
def candidates(principal):
    principal.require('assign_review')
    return [metadata(u) for u in read_registry()['principals'] if u['role']=='Risk/Compliance Analyst' and u.get('status','ACTIVE')=='ACTIVE' and u.get('token_sha256') and set(u['accounts'])&set(principal.accounts)]
def decorate(rows,now=None):
    now=now or datetime.now(timezone.utc);sla=sla_seconds()
    users={u['subject']:u for u in read_registry()['principals']}
    for row in rows:
        owner=row.get('reviewer_subject');user=users.get(owner)
        row['assignment_status']='ASSIGNED' if owner else 'UNASSIGNED'
        row['assignee_label']=(user.get('display_name',owner)+' ('+owner+')') if user else owner or 'Unassigned'
        row['assignee_active']=bool(user and user.get('status','ACTIVE')=='ACTIVE' and user['role']=='Risk/Compliance Analyst' and user.get('token_sha256')) if owner else None
        if owner and not row['assignee_active']:row['assignee_label']+=' [inactive: Admin reassignment required]'
        row['age_seconds']=max(0,int((now-row['created_at']).total_seconds()))
        row['sla_seconds']=sla;row['over_sla']=row['age_seconds']>=sla if sla is not None and row['review_status'] in {'OPEN','UNDER_REVIEW','ESCALATED'} else False
    return rows
def assign(event,body,principal):
    principal.require('assign_review')
    if type(event) is not int or event<1:raise ValueError('Invalid risk event')
    request,digest=api._body(body,{'request_id','expected_version','assignee','notes'})
    if type(body['expected_version']) is not int or body['expected_version']<1:raise ValueError('Expected version required')
    target=body['assignee']
    if target is not None and (not isinstance(target,str) or not 1<=len(target)<=200):raise ValueError('Invalid assignee')
    if principal.role!='Admin' and target!=principal.subject:raise PermissionError('Analysts may claim only themselves')
    # Hold the identity lock through commit: concurrent disable/role changes cannot
    # slip between active-role validation and a new assignment.
    with locked_registry(os.environ['FINTRUST_AUTH_FILE']):
        users=read_registry()['principals']
        current=[u for u in users if u['subject']==principal.subject]
        if len(current)!=1 or current[0]['role']!=principal.role or current[0].get('status','ACTIVE')!='ACTIVE':raise PermissionError('Identity changed')
        conn=api.connection()
        try:
            with conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute('SELECT w.*,t.account_id::text FROM risk_reviews w JOIN risk_events r USING(risk_event_id) JOIN transactions t USING(tx_id) WHERE w.risk_event_id=%s FOR UPDATE OF w',(event,));row=cur.fetchone()
                    if not row:raise api.NotFound()
                    principal.account(row['account_id'])
                    cur.execute('SELECT * FROM risk_review_history WHERE request_id=%s',(request,));prior=cur.fetchone()
                    if prior:
                        if prior['risk_event_id']!=event or prior['actor_subject']!=principal.subject or prior['request_digest']!=digest:raise api.Conflict('Request reused')
                        return {'risk_event_id':event,'version':prior['version'],'reviewer_subject':prior['reviewer_subject'],'review_status':prior['after_status'],'replayed':True}
                    if row['version']!=body['expected_version']:raise api.Conflict('Review changed')
                    if row['review_status'] not in {'OPEN','UNDER_REVIEW','ESCALATED'}:raise api.Conflict('Only active reviews can be assigned; terminal decisions are unchanged')
                    if principal.role!='Admin' and (row['reviewer_subject'] is not None or row['review_status']!='OPEN'):raise api.Conflict('Review already owned')
                    if row['review_status']=='ESCALATED' and target is None:raise api.Conflict('Escalated review requires a named owner')
                    if target==row['reviewer_subject']:raise api.Conflict('Assignment unchanged')
                    if target:
                        matches=[u for u in users if u['subject']==target and u['role']=='Risk/Compliance Analyst' and u.get('status','ACTIVE')=='ACTIVE' and u.get('token_sha256') and row['account_id'] in u['accounts']]
                        if len(matches)!=1:raise PermissionError('Assignee must be an active provisioned scoped Analyst')
                    escalated=row['review_status']=='ESCALATED'
                    status='ESCALATED' if escalated else 'UNDER_REVIEW' if target else 'OPEN'
                    cur.execute('''UPDATE risk_reviews SET reviewer_subject=%s,review_status=%s,review_notes=%s,
                        reviewed_by=%s,reviewed_at=%s,resolution_code=%s,change_actor=%s,
                        change_request_id=%s,request_digest=%s,version=version+1 WHERE risk_event_id=%s RETURNING version''',
                        (target,status,body['notes'],row['reviewed_by'] if escalated else None,row['reviewed_at'] if escalated else None,row['resolution_code'] if escalated else None,principal.subject,request,digest,event))
                    return {'risk_event_id':event,'version':cur.fetchone()['version'],'reviewer_subject':target,'review_status':status}
        finally:conn.close()
