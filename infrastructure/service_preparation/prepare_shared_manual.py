"""Render a separate, inactive candidate for individual shared-capacity tests.

No AWS calls, credential access, uploads, migration changes or activation.
The reserved-concurrency deployment template remains unchanged.
"""
import hashlib
import json
from pathlib import Path

from prepare_services import application_template, enabled, flag, ref

ROOT = Path(__file__).resolve().parent
FUNCTIONS = {'ScoringFunction': 'scoring', 'AlertFunction': 'alert',
             'ReportFunction': 'report', 'ApiFunction': 'api'}


def build_template():
    template = application_template()
    template['Description'] = 'FinTrust dev manual shared-capacity test candidate; inactive by default; no automated consumers or reports'
    parameters = template['Parameters']
    parameters['Stage']['AllowedValues'] = ['dev']
    for name in ('EnableFunctions', 'EnableConsumers', 'EnableMonthlyReports'):
        parameters[name]['AllowedValues'] = ['false']
        parameters[name]['Default'] = 'false'
    parameters['EnableManualTest'] = flag('Explicitly release only the selected test function into shared capacity; not a per-function limit.')
    parameters['ManualTestFunction'] = {'Type': 'String', 'Default': 'none',
        'AllowedValues': ['none', *FUNCTIONS.values()],
        'Description': 'Select one service for sequential synchronous testing after live prerequisites and invocation permissions are verified.'}
    template.setdefault('Rules', {})['ManualTestNeedsSelection'] = {'Assertions': [{
        'Assert': {'Fn::Or': [
            {'Fn::Equals': [ref('EnableManualTest'), 'false']},
            {'Fn::Not': [{'Fn::Equals': [ref('ManualTestFunction'), 'none']}]}]},
        'AssertDescription': 'An enabled manual test must select exactly one service.'}]}
    for name, service in FUNCTIONS.items():
        condition = name + 'ManualTestEnabled'
        template['Conditions'][condition] = {'Fn::And': [enabled('EnableManualTest'),
            {'Fn::Equals': [ref('ManualTestFunction'), service]}]}
        template['Resources'][name]['Properties']['ReservedConcurrentExecutions'] = {
            'Fn::If': [condition, ref('AWS::NoValue'), 0]}
    for resource in template['Resources'].values():
        if resource['Type'] == 'AWS::Lambda::EventSourceMapping':
            resource['Properties']['Enabled'] = False
    template['Resources']['MonthlySchedule']['Properties']['State'] = 'DISABLED'
    return template


def main():
    out = ROOT / 'shared_manual'
    out.mkdir(exist_ok=True)
    path = out / 'application-functions-shared-manual.json'
    template = build_template()
    path.write_text(json.dumps(template, indent=2) + '\n', encoding='utf-8', newline='\n')
    candidate_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    validation_path = out / 'aws-template-validation.json'
    validation = json.loads(validation_path.read_text(encoding='utf-8')) if validation_path.exists() else {}
    manifest = {'status': 'LOCAL_CANDIDATE_NOT_DEPLOYED', 'aws_changes': False,
        'template_sha256': candidate_hash,
        'reserved_template_sha256': hashlib.sha256((ROOT / 'templates/application-functions.json').read_bytes()).hexdigest(),
        'account': '966467878406', 'region': 'af-south-1', 'stage': 'dev',
        'same_resources_as_reserved_template': True,
        'defaults': {'EnableManualTest': 'false', 'ManualTestFunction': 'none',
                     'EnableFunctions': 'false', 'EnableConsumers': 'false', 'EnableMonthlyReports': 'false'},
        'per_function_cap_when_selected': None,
        'maximum_selected_function_count': 1,
        'automatic_consumers_permitted': False, 'scheduled_reports_permitted': False,
        'migration_runner_modified': False, 'ingest_modified': False,
        'live_validation': validation.get('status', 'NOT_PERFORMED') if validation.get('template_sha256') == candidate_hash else 'NOT_CURRENTLY_VERIFIED',
        'remaining_gates': ['Immutable artifact upload/version and disabled deployment',
            'Approved database access, migrations, IAM/TLS and grants for DB-dependent tests',
            'Reviewed qualified test invocation permission and inactive upstream paths',
            'Single operator, sequential synchronous invocation and verified return to concurrency zero',
            'Separate reviewed capacity strategy for integrated cloud E2E/production']}
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({'status': manifest['status'], 'template_sha256': manifest['template_sha256']}))


if __name__ == '__main__':
    main()
