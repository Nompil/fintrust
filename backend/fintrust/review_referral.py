"""Specialist referral metadata inside the existing immutable review history.

Referring never assigns a case. Only the existing Administrator assignment flow
changes another person's ownership. Legacy five-field notes remain plain text.
"""
import hashlib
import json
import os
import uuid
from .identity_registry import locked_registry, read_registry

FORMAT='fintrust.review-referral.v1'
ASSIGNMENT_NOTE='Referral does not change assignment. Administrator assignment is separate.'


def _eligible(user,account):
    return (user.get('role')=='Risk/Compliance Analyst' and user.get('status','ACTIVE')=='ACTIVE'
            and bool(user.get('token_sha256')) and str(account) in user.get('accounts',[]))


def target(value,principal,account):
    if not isinstance(value,str) or not 1<=len(value)<=210:raise ValueError('Recorded referral target required')
    users=read_registry()['principals']
    actor=[u for u in users if u['subject']==principal.subject and _eligible(u,account)]
    if len(actor)!=1:raise PermissionError('Current scoped Analyst required')
    if value=='SPECIALIST_REVIEW':
        return {'value':value,'kind':'DESTINATION','label':'Specialist Review — administrator routing required'}
    if not value.startswith('analyst:'):raise ValueError('Unsupported referral destination')
    subject=value[len('analyst:'):]
    if subject==principal.subject:raise ValueError('Choose another eligible reviewer')
    found=[u for u in users if u['subject']==subject and _eligible(u,account)]
    if len(found)!=1:raise PermissionError('Requested reviewer must be active, provisioned and account-scoped')
    return {'value':value,'kind':'ANALYST','label':'Requested reviewer: '+found[0].get('display_name',subject)+' ('+subject+')'}


def options(event,principal):
    from . import workflow_api as api
    principal.require('review')
    if type(event) is not int or event<1:raise ValueError('Invalid review reference')
    with locked_registry(os.environ['FINTRUST_AUTH_FILE']):
        users=read_registry()['principals']
        current=[u for u in users if u['subject']==principal.subject and u['role']==principal.role and u.get('status','ACTIVE')=='ACTIVE']
        if len(current)!=1:raise PermissionError('Identity changed')
        rows=api._query('SELECT w.review_status,w.reviewer_subject,t.account_id::text FROM risk_reviews w JOIN risk_events r USING(risk_event_id) JOIN transactions t USING(tx_id) WHERE w.risk_event_id=%s',(event,))
        if not rows:raise api.NotFound()
        row=rows[0];principal.account(row['account_id'])
        if row['reviewer_subject']!=principal.subject:raise PermissionError('Only the current owner may request referral')
        if row['review_status']!='UNDER_REVIEW':raise api.Conflict('Referral requires an active investigation')
        result=[target('SPECIALIST_REVIEW',principal,row['account_id'])]
        result.extend(target('analyst:'+u['subject'],principal,row['account_id']) for u in users if u['subject']!=principal.subject and _eligible(u,row['account_id']))
        return result


def encode(body,principal,validated,digest):
    return json.dumps({'format':FORMAT,'notes':body['notes'],'target':validated,
        'actor':{'subject':principal.subject,'role':principal.role},'request_id':body['request_id'],
        'request_digest':digest},ensure_ascii=False,sort_keys=True,separators=(',',':'))


def decode(history):
    """A legacy user-controlled JSON-looking note must never become metadata."""
    raw=history.get('notes')
    if not isinstance(raw,str) or not raw.startswith('{'):return None
    try:
        value=json.loads(raw)
        if set(value)!={'format','notes','target','actor','request_id','request_digest'} or value['format']!=FORMAT:return None
        if history.get('after_status')!='ESCALATED' or history.get('resolution_code')!='SPECIALIST_REVIEW':return None
        if set(value['target'])!={'value','kind','label'} or set(value['actor'])!={'subject','role'}:return None
        if not isinstance(value['notes'],str) or not 1<=len(value['notes'].strip())<=2000:return None
        if not all(isinstance(value['target'][k],str) for k in value['target']):return None
        if value['actor']['subject']!=history.get('actor_subject') or value['actor']['role']!='Risk/Compliance Analyst':return None
        if uuid.UUID(str(history.get('request_id')))!=uuid.UUID(value['request_id']) or history.get('request_digest')!=value['request_digest']:return None
        body={'request_id':value['request_id'],'expected_version':history['version']-1,'status':'ESCALATED',
              'notes':value['notes'],'resolution_code':'SPECIALIST_REVIEW','referral_target':value['target']['value']}
        digest=hashlib.sha256(json.dumps(body,sort_keys=True).encode()).hexdigest()
        if digest!=history.get('request_digest'):return None
        if value['target']['value']=='SPECIALIST_REVIEW' and value['target']['kind']!='DESTINATION':return None
        if value['target']['value']!='SPECIALIST_REVIEW' and (not value['target']['value'].startswith('analyst:') or value['target']['kind']!='ANALYST'):return None
        return value
    except (ValueError,TypeError,KeyError,AttributeError):return None


def history_projection(history):
    result=[]
    for original in history:
        row=dict(original);value=decode(original)
        if value:
            row.update(raw_notes=row['notes'],notes=value['notes'],actor_role=value['actor']['role'],actor_type='HUMAN',
                       referral_target=value['target']['value'],referral_target_label=value['target']['label'],referral_kind=value['target']['kind'])
            row.pop('actor_role_note',None)
        result.append(row)
    return result


def project(row,history):
    # Decode raw history, not already projected human notes.
    row.update(referral_target=None,referral_target_label='Not recorded',referral_kind=None,
               referral_requested_by=None,referral_requested_at=None,referral_note=None,
               referral_assignment_note=ASSIGNMENT_NOTE)
    row['referral_active']=row.get('review_status')=='ESCALATED'
    for h in reversed(history):
        if h.get('after_status')=='ESCALATED' and h.get('before_status')!='ESCALATED':
            value=decode(h)
            if value:
                row.update(referral_target=value['target']['value'],referral_target_label=value['target']['label'],
                    referral_kind=value['target']['kind'],referral_requested_by=h['actor_subject'],
                    referral_requested_at=h['changed_at'],referral_note=value['notes'])
            break
    raw=row.get('review_notes')
    current=next((h for h in reversed(history) if h.get('version')==row.get('version')),None)
    value=decode(current) if current else None
    if value:row.update(raw_review_notes=raw,review_notes=value['notes'])
    return row


def decorate(rows):
    from . import workflow_api as api
    identifiers=list({r['risk_event_id'] for r in rows if r.get('risk_event_id') and r.get('version')})
    if not identifiers:return rows
    history=api._query('''SELECT h.* FROM risk_review_history h WHERE risk_event_id=ANY(%s::bigint[])
        AND (h.version=(SELECT w.version FROM risk_reviews w WHERE w.risk_event_id=h.risk_event_id)
          OR h.version=(SELECT max(previous.version) FROM risk_review_history previous
            WHERE previous.risk_event_id=h.risk_event_id AND previous.after_status='ESCALATED'
              AND previous.before_status IS DISTINCT FROM 'ESCALATED')) ORDER BY h.risk_event_id,h.version''',(identifiers,))
    for row in rows:project(row,[h for h in history if h['risk_event_id']==row.get('risk_event_id')])
    return rows
