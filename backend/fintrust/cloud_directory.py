"""Read-only workforce metadata; it never replaces Cognito authentication.

Operators and the isolated Admin provisioning service update scope records. The
financial API has GetItem permission only. Membership/status is checked against each user's authoritative scope item,
so a stale directory entry cannot authorize a disabled or reassigned user.
"""
import os,uuid
from contextlib import contextmanager

KEY='WORKFORCE_DIRECTORY'

def enabled():
    return os.getenv('AUTH_MODE','cognito' if os.getenv('AWS_EXECUTION_ENV') else 'local')=='cognito'

def read():
    if not enabled():raise PermissionError('Cloud workforce directory unavailable')
    import boto3
    name=os.environ.get('COGNITO_USER_SCOPE_TABLE')
    if not name:raise PermissionError('Cloud workforce directory unavailable')
    table=boto3.resource('dynamodb',region_name=os.getenv('AWS_REGION','af-south-1')).Table(name)
    item=table.get_item(Key={'subject':KEY},ConsistentRead=True).get('Item')
    if not item or item.get('schema_version')!=1 or not isinstance(item.get('users'),list) or len(item['users'])>100:
        raise PermissionError('Cloud workforce directory unavailable')
    users=[];seen=set()
    from .cognito_auth import GROUP_ROLES
    for user in item['users']:
        if not isinstance(user,dict):raise PermissionError('Invalid cloud workforce metadata')
        subject=user.get('username');sub=user.get('cognito_sub')
        if not isinstance(subject,str) or not 1<=len(subject)<=128 or subject in seen:
            raise PermissionError('Invalid cloud workforce metadata')
        try:sub=str(uuid.UUID(sub))
        except (ValueError,TypeError,AttributeError):raise PermissionError('Invalid cloud workforce metadata') from None
        seen.add(subject)
        scope=table.get_item(Key={'subject':sub},ConsistentRead=True).get('Item',{})
        role=GROUP_ROLES.get(scope.get('group'))
        if scope.get('username')!=subject or scope.get('status')!='ACTIVE' or not role:continue
        accounts=scope.get('accounts')
        if not isinstance(accounts,list) or len(accounts)>1000:raise PermissionError('Invalid cloud workforce scope')
        try:accounts=[str(uuid.UUID(value)) for value in accounts]
        except (ValueError,TypeError,AttributeError):raise PermissionError('Invalid cloud workforce scope') from None
        if len(set(accounts))!=len(accounts):raise PermissionError('Invalid cloud workforce scope')
        users.append({'subject':subject,'cognito_sub':sub,'user_id':str(uuid.uuid5(uuid.NAMESPACE_URL,'cognito:'+sub)),
                      'role':role,'status':'ACTIVE','accounts':accounts,'auth_source':'cognito',
                      'display_name':user.get('display_name',subject) if isinstance(user.get('display_name',subject),str) else subject})
    return {'principals':users,'auth_source':'cognito'}

@contextmanager
def mutation_guard(principal):
    if principal.auth_source!='cognito':raise PermissionError('Cognito identity required')
    users=[u for u in read()['principals'] if u['subject']==principal.subject]
    if len(users)!=1 or users[0]['role']!=principal.role or set(users[0]['accounts'])!=set(principal.accounts):
        raise PermissionError('Identity changed')
    # This is a fresh authorization check, not a distributed lock with Cognito.
    yield
