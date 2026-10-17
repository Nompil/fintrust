import copy
import unittest

from infrastructure import migration
from infrastructure.service_preparation.database_preflight.prepare import template


class PreflightBoundaryTests(unittest.TestCase):
    def test_disabled_default_and_no_positive_reservation(self):
        doc = template()
        self.assertEqual(doc['Parameters']['EnableReadOnlyPreflight']['Default'], 'false')
        self.assertEqual(doc['Conditions']['PreflightEnabled'],
                         {'Fn::Equals': [{'Ref': 'EnableReadOnlyPreflight'}, 'true']})
        self.assertEqual(doc['Resources']['Runner']['Properties']['ReservedConcurrentExecutions'],
                         {'Fn::If': ['PreflightEnabled', {'Ref': 'AWS::NoValue'}, 0]})

    def test_only_canonical_preflight_resources_and_properties(self):
        candidate = copy.deepcopy(template()['Resources'])
        candidate['Runner']['Properties']['ReservedConcurrentExecutions'] = 0
        self.assertEqual(candidate, migration.runner_template('preflight')['Resources'])
        self.assertEqual(candidate['Runner']['Properties']['Handler'],
                         'migration_runner.preflight_entry.lambda_handler')
        self.assertEqual({r['Type'] for r in candidate.values()},
                         {'AWS::Logs::LogGroup', 'AWS::Lambda::Function', 'AWS::Lambda::Version'})

    def test_original_write_phase_templates_remain_disabled(self):
        for phase in migration.PHASES:
            doc = migration.runner_template(phase)
            self.assertEqual(doc['Resources']['Runner']['Properties']['ReservedConcurrentExecutions'], 0)
            self.assertNotIn('EnableReadOnlyPreflight', doc['Parameters'])

    def test_network_is_single_az_without_existing_database_edits(self):
        doc = migration.network_template()
        self.assertEqual(len(doc['Resources']), 4)
        self.assertEqual(doc['Resources']['SecretsEndpoint']['Properties']['SubnetIds'], [migration.SUBNET])
        self.assertEqual(doc['Resources']['SecretsEndpoint']['Properties']['VpcEndpointType'], 'Interface')
        self.assertFalse(any(r['Type'].startswith(('AWS::RDS::', 'AWS::IAM::'))
                             for r in doc['Resources'].values()))


if __name__ == '__main__':
    unittest.main()
