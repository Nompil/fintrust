"""Evidence-backed, read-only Analyst states and configurable review targets.

These projections do not change scoring, assignment, decisions, or stored history.
Assignment and escalation clocks come from the existing immutable review history.
"""
import os
from datetime import datetime, timedelta, timezone

ACTIVE = frozenset({'OPEN', 'UNDER_REVIEW', 'ESCALATED'})
REVIEW_LABELS = {'OPEN':'Open', 'UNDER_REVIEW':'Under review', 'CLEARED':'Cleared',
                 'CONFIRMED_RISK':'Confirmed risk', 'ESCALATED':'Escalated'}


def now_utc():
    return datetime.now(timezone.utc)


def clock_sql():
    # The timestamp is generated internally, never from request/config text.
    # One shared clock makes queue filtering, metrics and presentation testable.
    return "TIMESTAMPTZ '"+_time(now_utc()).astimezone(timezone.utc).isoformat()+"'"


def sast_day(now=None):
    current=_time(now or now_utc()).astimezone(timezone(timedelta(hours=2)))
    start=current.replace(hour=0,minute=0,second=0,microsecond=0)
    return start.astimezone(timezone.utc),(start+timedelta(days=1)).astimezone(timezone.utc)


def due_today_sql(due=None):
    due=due or due_sql();start,end=sast_day()
    return '('+due+">=TIMESTAMPTZ '"+start.isoformat()+"' AND "+due+"<TIMESTAMPTZ '"+end.isoformat()+"')"


def policy():
    enabled = os.getenv('FINTRUST_REVIEW_SLA_ENABLED', 'true').lower()
    if enabled not in {'true', 'false'}:
        raise ValueError('Invalid review SLA enabled configuration')
    legacy = os.getenv('FINTRUST_REVIEW_SLA_SECONDS')
    values = {}
    for key, default in (('MEDIUM',86400), ('HIGH',14400), ('ESCALATED',7200)):
        raw = os.getenv('FINTRUST_REVIEW_'+key+'_SLA_SECONDS', legacy if key!='ESCALATED' and legacy is not None else str(default))
        if not raw.isdigit() or not 60 <= int(raw) <= 31536000:
            raise ValueError('Invalid configured review SLA')
        values[key] = int(raw)
    raw = os.getenv('FINTRUST_REVIEW_SLA_DUE_SOON_SECONDS', '3600')
    if not raw.isdigit() or not 60 <= int(raw) <= 31536000:
        raise ValueError('Invalid configured review due-soon window')
    return {'enabled':enabled=='true', 'targets':values, 'due_soon_seconds':int(raw)}


def _time(value):
    if value is None: return None
    if isinstance(value,str): value=datetime.fromisoformat(value.replace('Z','+00:00'))
    if value.tzinfo is None: raise ValueError('Recorded timestamp must include timezone')
    return value


def historical(row):
    # The canonical bootstrap dataset is explicit legacy provenance. Absence of
    # an assessment, old event time, or a missing source reference is not proof.
    return (row.get('raw_file')=='seed/week13-day2.csv' and not row.get('batch_id')
            and not row.get('source_system') and not row.get('source_transaction_id')
            and not row.get('transaction_fingerprint') and not row.get('has_occurrence'))


def assessed_sql(alias='p'):
    if alias not in {'p','fp'}:raise ValueError('Unsupported assessment alias')
    return "("+alias+".result->>'risk_level' IN ('Low','Medium','High') AND CASE WHEN jsonb_typeof("+alias+".result->'score')='number' THEN ("+alias+".result->>'score')::numeric BETWEEN 0 AND 100 ELSE FALSE END)"


def valid_assessment(risk):
    risk=risk or {};score=risk.get('score',risk.get('risk_score'))
    return risk.get('risk_level') in {'Low','Medium','High'} and type(score) in {int,float} and 0<=score<=100


def primary_reason(risk,reason=None):
    signals=(risk or {}).get('triggered_rules') or []
    labels={'AMOUNT_RISK':'Amount risk','HIGH_AMOUNT':'High amount','VERY_HIGH_AMOUNT':'Very high amount',
            'HIGH_VELOCITY':'High velocity','CROSS_BORDER':'Cross-border',
            'POSSIBLE_DUPLICATE_CHARGE':'Possible duplicate charge','TRANSFER':'Transfer','MERCHANT_MARKER':'Merchant marker'}
    parts=[]
    for signal in signals:
        rule=signal.get('rule')
        if not rule: continue
        text=labels.get(rule,rule.replace('_',' ').capitalize())
        # Use frozen measured values only, never recalculate a scoring window.
        observed=signal.get('triggered_value',signal.get('observed_count'))
        if rule=='HIGH_VELOCITY' and type(observed) is int and signal.get('window_seconds') is not None:
            text+=' · '+str(observed)+' in '+str(int(signal['window_seconds'])//60)+' min'
        parts.append(text)
    if parts:return ' + '.join(parts[:2])
    if valid_assessment(risk) and (risk or {}).get('triggered_rules')==[]:return 'No triggered rules'
    recorded=reason or (risk or {}).get('reason')
    return recorded.strip() if isinstance(recorded,str) and recorded.strip() else 'No recorded explanation'


def assessment(row):
    risk=row.get('risk') or {}
    level=risk.get('risk_level')
    valid=valid_assessment(risk)
    if valid: state,label,note='ASSESSED',level,'Recorded assessment; original rule version preserved.'
    elif row.get('assessment_failed') or row.get('disposition')=='FAILED_TECHNICAL':
        state,label,note='FAILED','Assessment failed','A recorded technical processing failure exists; no risk score is inferred.'
    elif row.get('assessment_pending') or row.get('disposition') in {'RECEIVED','QUEUED'}:
        state,label,note='PENDING','Pending assessment','Recorded processing is incomplete.'
    elif not risk and historical(row):
        state,label,note='HISTORICAL','Historical — not scored','This bootstrap transaction predates the Release 1 scoring evidence available in FinTrust.'
    else:
        state,label,note='NOT_RECORDED','Not recorded','No complete assessment or recorded pending/failure state is available. Missing evidence is not LOW risk.'
    review=row.get('review_status')
    if review in REVIEW_LABELS: rstate,rlabel,rnote=review,REVIEW_LABELS[review],'Recorded current review state.'
    elif valid and level=='Low': rstate,rlabel,rnote='NOT_REQUIRED','No review required','Recorded LOW assessment does not require routine review.'
    elif state=='HISTORICAL': rstate,rlabel,rnote='HISTORICAL','Historical — no review record','No Release 1 review record exists for this bootstrap transaction.'
    else: rstate,rlabel,rnote='NOT_RECORDED','Not recorded','No review artefact is recorded; review creation is not inferred from risk alone.'
    row.update(assessment_state=state,assessment_label=label,assessment_note=note,
               review_state=rstate,review_label=rlabel,review_note=rnote,primary_reason=primary_reason(risk,row.get('reason')))
    return row


def alert_projection(row, claim=None, receipts=()):
    """Keep notification evidence separate from risk classification and review."""
    state=(claim or {}).get('delivery_state')
    if state in {'PENDING','SENDING','RETRYING','SENT','FAILED','UNKNOWN'}:
        return {'alert_state':state,'alert_state_source':'DYNAMODB_CLAIM',
                'alert_state_note':'Recorded cloud delivery claim. SENDING, RETRYING and UNKNOWN do not prove delivery.'}
    recorded={receipt.get('delivery_state') for receipt in receipts}
    for actual in ('SENT','FAILED','UNKNOWN','SENDING','PENDING'):
        if actual in recorded:
            return {'alert_state':actual,'alert_state_source':'SQL_RECEIPT',
                    'alert_state_note':'Recorded SQL delivery evidence; the independent cloud delivery claim is shown separately.'}
    if row.get('assessment_state')=='HISTORICAL':value='NOT_APPLICABLE';source='HISTORICAL_PROVENANCE'
    elif row.get('assessment_state')=='ASSESSED':
        if (row.get('risk') or {}).get('risk_level')=='High':
            value='UNAVAILABLE' if state=='UNAVAILABLE' else 'PENDING';source='CLOUD_READ_UNAVAILABLE' if state=='UNAVAILABLE' else 'REQUIRED_ALERT_INTENT'
        else:value='NOT_REQUIRED';source='RECORDED_ASSESSMENT_POLICY'
    else:value='NOT_RECORDED';source='MISSING_ASSESSMENT_EVIDENCE'
    return {'alert_state':value,'alert_state_source':source,
            'alert_state_note':'No delivery receipt or readable delivery claim is recorded. Pending indicates the independent high-risk alert path, not email delivery.'}


def history_fields(history, owner):
    assignment=None; escalation=None; previous_owner=None;previous_version=0
    for h in sorted(history,key=lambda x:x['version']):
        if h['version']==previous_version+1 and h.get('reviewer_subject') != previous_owner:
            assignment=h if h.get('reviewer_subject')==owner and owner else None
        previous_owner=h.get('reviewer_subject')
        previous_version=h['version']
        if h.get('after_status')=='ESCALATED' and h.get('before_status')!='ESCALATED': escalation=h
    return {'assigned_at':assignment.get('changed_at') if assignment else None,
            'assigned_by':assignment.get('actor_subject') if assignment else None,
            'escalated_at':escalation.get('changed_at') if escalation else None}


def review(row, now=None, history=None, users=None):
    now=_time(now or now_utc()); configured=policy()
    if history is not None:
        derived=history_fields(history,row.get('reviewer_subject'))
        for field,value in derived.items():
            if value is not None or field not in row:row[field]=value
    created=_time(row.get('review_created_at') or row.get('created_at'))
    status=row.get('review_status'); level=(row.get('risk') or {}).get('risk_level') or row.get('risk_level')
    owner=row.get('reviewer_subject'); user=(users or {}).get(owner)
    row['assignment_status']='ASSIGNED' if owner else 'UNASSIGNED'
    row['assignee_label']=(user.get('display_name',owner)+' ('+owner+')') if user else owner or 'Unassigned'
    row['assignee_active']=bool(user and user.get('status','ACTIVE')=='ACTIVE' and user.get('role')=='Risk/Compliance Analyst' and user.get('token_sha256')) if owner and users is not None else None
    if owner and users is not None and not row['assignee_active']:row['assignee_label']+=' [inactive: Admin reassignment required]'
    target=configured['targets'].get('ESCALATED' if status=='ESCALATED' else (level or '').upper()) if status in REVIEW_LABELS else None
    start=(_time(row.get('escalated_at')) if status=='ESCALATED' else created) if status in REVIEW_LABELS else None
    due=start+timedelta(seconds=target) if start and target and configured['enabled'] else None
    remaining=int((due-now).total_seconds()) if due else None
    active=status in ACTIVE
    state=('NOT_APPLICABLE' if not active or level=='Low' else 'NOT_CONFIGURED' if not configured['enabled']
           else 'NOT_RECORDED' if due is None else 'OVERDUE' if due<=now
           else 'DUE_SOON' if (due-now).total_seconds()<=configured['due_soon_seconds'] else 'WITHIN_SLA')
    row.update(age_seconds=max(0,int((now-created).total_seconds())) if created else None,
               sla_seconds=target if configured['enabled'] else None,sla_started_at=start,sla_due_at=due,
               sla_state=state,remaining_seconds=remaining if active else None,
               overdue_seconds=max(0,-remaining) if active and remaining is not None else 0,
               over_sla=state=='OVERDUE',due_soon=state=='DUE_SOON')
    if state=='OVERDUE': label='Overdue by '+_duration(row['overdue_seconds'])
    elif state=='DUE_SOON': label='Due soon · '+_duration(remaining)+' remaining'
    elif state=='WITHIN_SLA': label='Within SLA · Due in '+_duration(remaining)
    else: label={'NOT_APPLICABLE':'Not applicable','NOT_CONFIGURED':'Not configured','NOT_RECORDED':'Not recorded'}[state]
    row['sla_label']=label
    start_day,end_day=sast_day(now)
    row['due_today']=bool(active and due and start_day<=due<end_day)
    row['priority']=('OVERDUE' if row['over_sla'] else 'HIGH_PRIORITY' if active and level=='High'
                     else 'DUE_SOON' if row['due_soon'] else 'SPECIALIST_REVIEW' if status=='ESCALATED'
                     else 'MEDIUM_PRIORITY' if active and level=='Medium' else 'CLOSED' if status in {'CLEARED','CONFIRMED_RISK'} else 'NOT_RECORDED')
    return row


def _duration(seconds):
    if 0<=seconds<60:return '<1m'
    minutes=max(0,seconds)//60
    return str(minutes//60)+'h '+str(minutes%60)+'m'


def decorate(rows,now=None):
    from .identity_registry import read_registry
    users={u['subject']:u for u in read_registry()['principals']}
    now=now or now_utc()
    for row in rows: assessment(row);review(row,now,users=users)
    return rows


def review_history_join():
    """SQL metadata from immutable history; joins require existing alias w."""
    return """ LEFT JOIN LATERAL (
        SELECT h.changed_at AS assigned_at,h.actor_subject AS assigned_by
        FROM risk_review_history h LEFT JOIN risk_review_history previous
          ON previous.risk_event_id=h.risk_event_id AND previous.version=h.version-1
        WHERE h.risk_event_id=w.risk_event_id AND h.reviewer_subject=w.reviewer_subject
          AND h.reviewer_subject IS DISTINCT FROM previous.reviewer_subject
        ORDER BY h.version DESC LIMIT 1) assignment ON TRUE
        LEFT JOIN LATERAL (SELECT h.changed_at AS escalated_at FROM risk_review_history h
          WHERE h.risk_event_id=w.risk_event_id AND h.after_status='ESCALATED'
            AND h.before_status IS DISTINCT FROM 'ESCALATED'
          ORDER BY h.version DESC LIMIT 1) escalation ON TRUE """


def due_sql():
    configured=policy()
    if not configured['enabled']: return 'NULL::timestamptz'
    values=configured['targets']
    return "(CASE WHEN w.review_status='ESCALATED' THEN escalation.escalated_at + INTERVAL '"+str(values['ESCALATED'])+" seconds' WHEN p.result->>'risk_level'='High' THEN w.created_at + INTERVAL '"+str(values['HIGH'])+" seconds' WHEN p.result->>'risk_level'='Medium' THEN w.created_at + INTERVAL '"+str(values['MEDIUM'])+" seconds' ELSE NULL END)"


def priority_sql():
    due=due_sql(); window=policy()['due_soon_seconds'];now=clock_sql()
    active="w.review_status IN ('OPEN','UNDER_REVIEW','ESCALATED')"
    return "CASE WHEN "+active+" AND "+due+"<="+now+" THEN 0 WHEN "+active+" AND p.result->>'risk_level'='High' THEN 1 WHEN "+active+" AND "+due+"<="+now+"+INTERVAL '"+str(window)+" seconds' THEN 2 WHEN w.review_status='ESCALATED' THEN 3 WHEN "+active+" AND p.result->>'risk_level'='Medium' THEN 4 ELSE 5 END,w.created_at,w.risk_event_id"
