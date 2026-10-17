"""Check the manual candidate cannot silently activate the automatic pipeline."""
import copy
import itertools
import unittest

from prepare_services import application_template
from prepare_shared_manual import build_template, FUNCTIONS
from test_preparation import resolve


class SharedManualTests(unittest.TestCase):
    def test_default_and_every_disabled_selection_throttle_all_functions(self):
        template = build_template()
        self.assertEqual(template['Parameters']['EnableManualTest']['Default'], 'false')
        self.assertEqual(template['Parameters']['ManualTestFunction']['Default'], 'none')
        for selection in ['none', *FUNCTIONS.values()]:
            parameters = {'EnableManualTest': 'false', 'ManualTestFunction': selection, 'AWS::NoValue': 'OMIT'}
            for name in FUNCTIONS:
                concurrency = template['Resources'][name]['Properties']['ReservedConcurrentExecutions']
                self.assertEqual(resolve(concurrency, parameters, template['Conditions']), 0)

    def test_enabled_selection_releases_only_one_function_and_reserves_no_slots(self):
        template = build_template()
        for selection in FUNCTIONS.values():
            parameters = {'EnableManualTest': 'true', 'ManualTestFunction': selection, 'AWS::NoValue': 'OMIT'}
            released = []
            for name, service in FUNCTIONS.items():
                expression = template['Resources'][name]['Properties']['ReservedConcurrentExecutions']
                capacity = resolve(expression, parameters, template['Conditions'])
                self.assertIn(capacity, [0, 'OMIT'])
                if capacity == 'OMIT':
                    released.append(service)
            self.assertEqual(released, [selection])
        rule = template['Rules']['ManualTestNeedsSelection']['Assertions'][0]['Assert']
        # CloudFormation rejects enabling without a concrete service selection.
        for active, selection in itertools.product(['false', 'true'], ['none', *FUNCTIONS.values()]):
            permitted = resolve(rule, {'EnableManualTest': active, 'ManualTestFunction': selection}, template['Conditions'])
            self.assertEqual(permitted, active == 'false' or selection != 'none')

    def test_manual_settings_cannot_enable_automatic_paths(self):
        template = build_template()
        for key in ['EnableFunctions', 'EnableConsumers', 'EnableMonthlyReports']:
            self.assertEqual(template['Parameters'][key]['AllowedValues'], ['false'])
            self.assertEqual(template['Parameters'][key]['Default'], 'false')
        for resource in template['Resources'].values():
            if resource['Type'] == 'AWS::Lambda::EventSourceMapping':
                self.assertIs(resource['Properties']['Enabled'], False)
            self.assertNotIn('ProvisionedConcurrencyConfig', resource['Properties'])
        self.assertEqual(template['Resources']['MonthlySchedule']['Properties']['State'], 'DISABLED')

    def test_identity_artifact_network_permissions_and_resource_set_are_preserved(self):
        original = application_template()
        candidate = build_template()
        restored = copy.deepcopy(candidate['Resources'])
        for name in FUNCTIONS:
            restored[name]['Properties']['ReservedConcurrentExecutions'] = original['Resources'][name]['Properties']['ReservedConcurrentExecutions']
        for name, resource in restored.items():
            if resource['Type'] == 'AWS::Lambda::EventSourceMapping':
                resource['Properties']['Enabled'] = original['Resources'][name]['Properties']['Enabled']
        restored['MonthlySchedule']['Properties']['State'] = original['Resources']['MonthlySchedule']['Properties']['State']
        self.assertEqual(restored, original['Resources'])
        self.assertEqual(candidate['Outputs'], original['Outputs'])
        self.assertEqual(candidate['Parameters']['Stage']['AllowedValues'], ['dev'])


if __name__ == '__main__':
    unittest.main()
