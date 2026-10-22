"""Scoped workforce provisioning outside the database VPC, with durable receipts.

This service has no database or transaction permissions. Password generation,
password change and MFA remain entirely within the existing Cognito user pool.
"""
import hashlib
import json
import logging
import os
import re
import time
import uuid
from datetime import datetime, timezone

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from .cognito_auth import GROUP_ROLES

logger = logging.getLogger(__name__)
ROLE_GROUPS = {role: group for group, role in GROUP_ROLES.items()}
DIRECTORY_KEY = 'WORKFORCE_DIRECTORY'


class ProvisioningConflict(Exception):
    pass


def clients():
    region = os.getenv('AWS_REGION', 'af-south-1')
    config = Config(retries={'total_max_attempts': 1}, connect_timeout=3, read_timeout=5)
    return (boto3.client('cognito-idp', region_name=region, config=config),
            boto3.resource('dynamodb', region_name=region, config=config))


def validated(body, principal):
    if principal.auth_source != 'cognito' or principal.role != 'Admin':
        raise PermissionError('Cloud administrator required')
    fields = {'request_id', 'username', 'display_name', 'email', 'role', 'accounts', 'notes'}
    if not isinstance(body, dict) or set(body) != fields:
        raise ValueError('Exact user provisioning fields required; never include a password')
    request_id = str(uuid.UUID(body['request_id']))
    username = body['username']
    if not isinstance(username, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,79}', username):
        raise ValueError('Use a username of 1 to 80 letters, numbers, dots, underscores or hyphens')
    username = username.lower()
    if body['role'] not in ROLE_GROUPS:
        raise ValueError('Approved application role required')
    if not isinstance(body['display_name'], str) or not 1 <= len(body['display_name'].strip()) <= 100:
        raise ValueError('A display name of at most 100 characters is required')
    if not isinstance(body['email'], str) or len(body['email']) > 254 or not re.fullmatch(r'[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+', body['email']):
        raise ValueError('Valid invitation email required')
    if not isinstance(body['notes'], str) or not 3 <= len(body['notes'].strip()) <= 500:
        raise ValueError('Record a reason of 3 to 500 characters')
    if not isinstance(body['accounts'], list) or len(body['accounts']) > 1000:
        raise ValueError('A bounded list of assigned account IDs is required')
    accounts = [str(uuid.UUID(value)) for value in body['accounts']]
    if len(accounts) != len(set(accounts)) or not set(accounts) <= set(principal.accounts):
        raise PermissionError('Accounts must be unique and within the administrator scope')
    if body['role'] != 'Maintainer' and not accounts:
        raise ValueError('Assign at least one account to this role')
    if body['role'] == 'Maintainer' and accounts:
        raise ValueError('Technical maintainers cannot receive financial account scope')
    return {**body, 'request_id': request_id, 'username': username,
            'accounts': sorted(accounts), 'display_name': body['display_name'].strip(),
            'notes': body['notes'].strip()}


def table_pair(dynamodb):
    return (dynamodb.Table(os.environ['COGNITO_USER_SCOPE_TABLE']),
            dynamodb.Table(os.environ['USER_PROVISIONING_TABLE']))


def current_administrator(principal, scopes, cognito):
    directory = scopes.get_item(Key={'subject': DIRECTORY_KEY}, ConsistentRead=True).get('Item', {})
    users = directory.get('users')
    if directory.get('schema_version') != 1 or not isinstance(users, list) or len(users) > 100:
        raise PermissionError('Workforce directory unavailable')
    matches = [u for u in users if u.get('username') == principal.subject]
    if len(matches) != 1:
        raise PermissionError('Administrator identity changed')
    actor = scopes.get_item(Key={'subject': matches[0]['cognito_sub']}, ConsistentRead=True).get('Item', {})
    if (actor.get('status') != 'ACTIVE' or actor.get('group') != 'Administrators'
            or actor.get('username') != principal.subject
            or set(actor.get('accounts', [])) != set(principal.accounts)):
        raise PermissionError('Administrator authority changed')
    groups = cognito.admin_list_groups_for_user(UserPoolId=os.environ['COGNITO_USER_POOL_ID'], Username=principal.subject).get('Groups', [])
    if [g['GroupName'] for g in groups] != ['Administrators']:
        raise PermissionError('Administrator membership changed')
    return directory


def summary(record):
    return {k: record.get(k) for k in ('request_id', 'username', 'display_name', 'role',
                                      'accounts', 'state', 'created_at', 'updated_at')}


def get_request(request_id, principal):
    if principal.auth_source != 'cognito' or principal.role != 'Admin':
        raise PermissionError('Cloud administrator required')
    request_id = str(uuid.UUID(request_id))
    cognito, dynamodb = clients()
    scopes, requests = table_pair(dynamodb)
    current_administrator(principal, scopes, cognito)
    record = requests.get_item(Key={'request_id': request_id}, ConsistentRead=True).get('Item')
    if not record or record.get('actor') != principal.subject:
        raise PermissionError('Provisioning request is outside your scope')
    return summary(record)


def append_directory(scopes, entry):
    for _ in range(6):
        directory = scopes.get_item(Key={'subject': DIRECTORY_KEY}, ConsistentRead=True).get('Item', {})
        before = directory.get('users')
        if directory.get('schema_version') != 1 or not isinstance(before, list):
            raise RuntimeError('Workforce directory unavailable')
        matches = [u for u in before if u.get('username') == entry['username']]
        if matches:
            if len(matches) == 1 and matches[0]['cognito_sub'] == entry['cognito_sub']:
                return
            raise ProvisioningConflict('Username already exists in the directory')
        if len(before) >= 100:
            raise ProvisioningConflict('Directory capacity reached; review before adding users')
        try:
            scopes.update_item(Key={'subject': DIRECTORY_KEY}, UpdateExpression='SET #users=:after',
                               ConditionExpression='#users=:before AND schema_version=:version',
                               ExpressionAttributeNames={'#users': 'users'},
                               ExpressionAttributeValues={':before': before, ':after': before + [entry], ':version': 1})
            return
        except ClientError as error:
            if error.response['Error']['Code'] != 'ConditionalCheckFailedException':
                raise
            time.sleep(.02)
    raise RuntimeError('Directory changed concurrently; operator reconciliation required')


def create_user(body, principal):
    body = validated(body, principal)
    cognito, dynamodb = clients()
    scopes, requests = table_pair(dynamodb)
    directory = current_administrator(principal, scopes, cognito)
    digest = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    request_id = body['request_id']
    prior = requests.get_item(Key={'request_id': request_id}, ConsistentRead=True).get('Item')
    if prior:
        if prior.get('actor') != principal.subject or prior.get('digest') != digest:
            raise ProvisioningConflict('Request ID was already used for another operation')
        # A replay only reports the durable outcome; it never recreates a user or resends an invitation.
        return summary(prior)
    if len(directory['users']) >= 100:
        raise ProvisioningConflict('Directory capacity reached')
    if any(u.get('username', '').lower() == body['username'] for u in directory['users']):
        raise ProvisioningConflict('Username already exists')
    now = datetime.now(timezone.utc).isoformat()
    record = {**body, 'actor': principal.subject, 'digest': digest, 'state': 'RESERVING',
              'created_at': now, 'updated_at': now}
    try:
        requests.put_item(Item=record, ConditionExpression='attribute_not_exists(request_id)')
    except ClientError as error:
        if error.response['Error']['Code'] == 'ConditionalCheckFailedException':
            return create_user(body, principal)
        raise

    def state(value):
        stamp = datetime.now(timezone.utc).isoformat()
        requests.update_item(Key={'request_id': request_id},
            UpdateExpression='SET #state=:state, updated_at=:now',
            ConditionExpression='actor=:actor AND digest=:digest',
            ExpressionAttributeNames={'#state': 'state'},
            ExpressionAttributeValues={':state': value, ':now': stamp, ':actor': principal.subject, ':digest': digest})
        record.update(state=value, updated_at=stamp)

    try:
        try:
            requests.put_item(Item={'request_id': 'USERNAME#' + body['username'], 'owner_request': request_id},
                              ConditionExpression='attribute_not_exists(request_id)')
        except ClientError as error:
            if error.response['Error']['Code'] != 'ConditionalCheckFailedException':
                raise
            state('USERNAME_RESERVED')
            return summary(record)
        state('CREATING')
        created = cognito.admin_create_user(UserPoolId=os.environ['COGNITO_USER_POOL_ID'],
            Username=body['username'], MessageAction='SUPPRESS', ForceAliasCreation=False,
            UserAttributes=[{'Name': 'email', 'Value': body['email']}, {'Name': 'name', 'Value': body['display_name']}])
        sub = str(uuid.UUID(next(a['Value'] for a in created['User']['Attributes'] if a['Name'] == 'sub')))
        state('CONFIGURING')
        group = ROLE_GROUPS[body['role']]
        cognito.admin_add_user_to_group(UserPoolId=os.environ['COGNITO_USER_POOL_ID'], Username=body['username'], GroupName=group)
        scopes.put_item(Item={'subject': sub, 'username': body['username'], 'status': 'PENDING',
            'group': group, 'accounts': body['accounts'], 'provisioning_request_id': request_id},
            ConditionExpression='attribute_not_exists(subject)')
        append_directory(scopes, {'username': body['username'], 'cognito_sub': sub,
                                  'display_name': body['display_name']})
        # Recheck the initiating administrator immediately before granting access.
        current_administrator(principal, scopes, cognito)
        scopes.update_item(Key={'subject': sub}, UpdateExpression='SET #status=:active',
            ConditionExpression='#status=:pending AND provisioning_request_id=:request',
            ExpressionAttributeNames={'#status': 'status'},
            ExpressionAttributeValues={':active': 'ACTIVE', ':pending': 'PENDING', ':request': request_id})
        state('INVITATION_SENDING')
        # Cognito owns the temporary password. Never return, store or log it here.
        cognito.admin_create_user(UserPoolId=os.environ['COGNITO_USER_POOL_ID'], Username=body['username'],
                                  MessageAction='RESEND', DesiredDeliveryMediums=['EMAIL'], ForceAliasCreation=False)
        state('INVITATION_REQUESTED')
    except Exception as error:
        uncertain = record['state'] in {'CREATING', 'INVITATION_SENDING'}
        final = 'INVITATION_UNKNOWN' if record['state'] == 'INVITATION_SENDING' else 'CREATION_UNKNOWN' if uncertain else 'SETUP_NEEDS_REVIEW'
        state(final)
        logger.warning(json.dumps({'event': 'user_provisioning_requires_review', 'request_id': request_id,
                                   'state': final, 'error_type': type(error).__name__}))
    return summary(record)


def lambda_handler(event, context):
    from . import cognito_auth
    marker = cognito_auth.set_gateway_claims((event.get('requestContext', {}).get('authorizer') or {}).get('claims'))
    headers = {'Content-Type': 'application/json', 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'}
    try:
        if event.get('resource') != '/v1/user-provisioning':
            raise PermissionError('Invalid administration route')
        principal = cognito_auth.authenticate('')
        if principal.role != 'Admin':
            raise PermissionError('Administrator required')
        method = event.get('httpMethod')
        if method == 'GET':
            query = event.get('queryStringParameters') or {}
            if set(query) != {'request_id'}:
                raise ValueError('Provisioning request ID required')
            data = get_request(query['request_id'], principal)
        elif method == 'POST':
            raw = event.get('body') or ''
            if event.get('isBase64Encoded') or len(raw.encode()) > 16384:
                raise ValueError('Bounded JSON request required')
            data = create_user(json.loads(raw), principal)
        else:
            raise ValueError('Unsupported method')
        return {'statusCode': 200 if method == 'GET' else 201 if data['state'] == 'INVITATION_REQUESTED' else 202,
                'headers': headers, 'body': json.dumps({'status': 'ok', 'data': data})}
    except (ValueError, TypeError, KeyError):
        status, message = 400, 'Check username, email, role, accounts and reason. Passwords must not be submitted.'
    except PermissionError:
        status, message = 403, 'Administrator authority and assigned-account scope are required.'
    except ProvisioningConflict:
        status, message = 409, 'Username or request ID already exists. Check the recorded request before retrying.'
    except Exception as error:
        logger.warning(json.dumps({'event': 'user_provisioning_unavailable', 'error_type': type(error).__name__}))
        status, message = 503, 'User provisioning is unavailable. Check your request status before retrying.'
    finally:
        cognito_auth.reset_gateway_claims(marker)
    return {'statusCode': status, 'headers': headers, 'body': json.dumps({'error': message, 'data': None})}
