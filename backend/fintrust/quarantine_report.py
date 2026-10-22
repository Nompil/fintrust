"""A source-review report, separate from accepted financial ledger reports."""
from datetime import datetime, time, timedelta, timezone

FIELDS = ('quarantine_id', 'batch_id', 'source_row', 'filename', 'candidate_account_id',
          'source_reference', 'quarantined_at', 'reason_code', 'reason_detail', 'workflow_status')


def report(principal, args):
    from . import workflow_api as api
    principal.require('read')
    if principal.role == 'Maintainer':
        raise PermissionError('Financial source-review report is outside technical operations scope')
    allowed = {'limit', 'offset', 'account_id', 'from', 'to', 'date_timezone', 'status', 'reason_code', 'batch_id'}
    if set(args) - allowed:
        raise ValueError('Unsupported quarantine report filter')
    zone = args.get('date_timezone', 'UTC')
    if zone not in {'UTC', 'Africa/Johannesburg'}:
        raise ValueError('Unsupported report timezone')
    tz = timezone(timedelta(hours=2)) if zone == 'Africa/Johannesburg' else timezone.utc
    filters = {k:v for k,v in args.items() if k != 'date_timezone' and v}
    dates = {}
    for key in ('from', 'to'):
        if filters.get(key):
            value = datetime.fromisoformat(filters[key].replace('Z', '+00:00'))
            if len(filters[key]) == 10:
                value = datetime.combine(value.date(), time(), tz)
            if value.tzinfo is None:
                raise ValueError('Timezone required for a report timestamp')
            dates[key] = value
            filters[key] = value.isoformat()
    if len(dates) == 2 and dates['from'] >= dates['to']:
        raise ValueError('Report end must be after start')
    result = api.list_page('quarantine', principal, filters)
    return {'data': [{key:row.get(key) for key in FIELDS} for row in result['data']],
            'meta': {**result['meta'], 'dataset':'quarantine', 'date_timezone':zone,
                     'date_field':'quarantined_at', 'date_end_exclusive':True},
            'meaning':'Rows held for source review, including rejected and historical resolved cases. Quarantine is not a fraud verdict and does not contribute to accepted ledger totals.'}
