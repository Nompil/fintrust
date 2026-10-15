import itertools
import unittest
import prepare_services as config


def resolve(value, parameters, conditions):
    if not isinstance(value, dict):
        return value
    if 'Ref' in value:
        return parameters[value['Ref']]
    if 'Condition' in value:
        return resolve(conditions[value['Condition']], parameters, conditions)
    if 'Fn::Equals' in value:
        a, b = value['Fn::Equals']
        return resolve(a, parameters, conditions) == resolve(b, parameters, conditions)
    if 'Fn::And' in value:
        return all(resolve(v, parameters, conditions) for v in value['Fn::And'])
    if 'Fn::Not' in value:
        return not resolve(value['Fn::Not'][0], parameters, conditions)
    if 'Fn::If' in value:
        name, yes, no = value['Fn::If']
        return resolve(yes if resolve(conditions[name], parameters, conditions) else no, parameters, conditions)
    raise AssertionError(value)


class ConfigurationTests(unittest.TestCase):
    def test_monthly_schedule_is_independent_of_consumers_and_requires_function_capacity(self):
        t = config.application_template()
        for functions, consumers, reports in itertools.product(['false', 'true'], repeat=3):
            p = {'EnableFunctions': functions, 'EnableConsumers': consumers, 'EnableMonthlyReports': reports}
            state = resolve(t['Resources']['MonthlySchedule']['Properties']['State'], p, t['Conditions'])
            self.assertEqual(state == 'ENABLED', functions == reports == 'true')
            for resource in t['Resources'].values():
                if resource['Type'] == 'AWS::Lambda::EventSourceMapping':
                    self.assertEqual(resolve(resource['Properties']['Enabled'], p, t['Conditions']),
                                     functions == consumers == 'true')

    def test_existing_foundation_is_not_recreated_and_code_is_versioned(self):
        t = config.application_template()
        forbidden = {'AWS::SQS::Queue', 'AWS::RDS::DBInstance', 'AWS::EC2::VPCEndpoint', 'AWS::EC2::NatGateway',
                     'AWS::S3::Bucket', 'AWS::DynamoDB::Table', 'AWS::IAM::Role'}
        for name, resource in t['Resources'].items():
            self.assertNotIn(resource['Type'], forbidden)
            if resource['Type'] == 'AWS::Lambda::Function':
                self.assertNotEqual(name, 'IngestFunction')
                self.assertEqual(resource['Properties']['Code']['S3ObjectVersion'], {'Ref': 'CodeObjectVersion'})
            if resource['Type'] == 'AWS::Logs::LogGroup':
                self.assertEqual(resource['Properties']['RetentionInDays'], 14)
                self.assertEqual(resource['DeletionPolicy'], 'Retain')
        self.assertIn('DeadLetterConfig', t['Resources']['MonthlySchedule']['Properties']['Targets'][0])

    def test_same_mailbox_cannot_create_duplicate_ses_identities(self):
        t = config.ses_template()
        for sender, recipient in itertools.product(['false', 'true'], repeat=2):
            p = {'SesSender': config.EMAIL, 'SesRecipient': config.EMAIL,
                 'CreateSenderIdentity': sender, 'CreateRecipientIdentity': recipient}
            self.assertFalse(resolve(t['Conditions']['CreateRecipient'], p, t['Conditions']))
            p['SesRecipient'] = 'separate@example.com'
            self.assertEqual(resolve(t['Conditions']['CreateRecipient'], p, t['Conditions']), recipient == 'true')
        for p in ['CreateSenderIdentity', 'CreateRecipientIdentity']:
            self.assertEqual(t['Parameters'][p]['Default'], 'false')

    def test_email_permission_cannot_send_to_other_recipients_or_from_other_identities(self):
        s = config.alert_send_policy()['Statement'][0]
        self.assertEqual(s['Action'], ['ses:SendEmail'])
        self.assertEqual(s['Resource'], 'arn:aws:ses:af-south-1:966467878406:identity/' + config.EMAIL)
        self.assertEqual(s['Condition']['ForAllValues:StringEquals']['ses:Recipients'], [config.EMAIL])
        self.assertEqual(s['Condition']['StringEquals']['ses:FromAddress'], config.EMAIL)

    def test_monitoring_is_opt_in_and_has_no_custom_metrics_or_automatic_actions(self):
        t = config.monitoring_template()
        self.assertEqual(t['Parameters']['EnableAlarms']['Default'], 'false')
        self.assertEqual(len(t['Resources']), 18)
        for resource in t['Resources'].values():
            self.assertEqual(resource['Condition'], 'AlarmsEnabled')
            self.assertEqual(resource['Type'], 'AWS::CloudWatch::Alarm')
            self.assertIn(resource['Properties']['Namespace'], ['AWS/Lambda', 'AWS/SQS', 'AWS/RDS'])
            self.assertFalse(resource['Properties']['ActionsEnabled'])
            self.assertNotIn('AlarmActions', resource['Properties'])
        storage = t['Resources']['DatabaseStorage']['Properties']
        self.assertEqual(storage['ComparisonOperator'], 'LessThanThreshold')
        self.assertEqual(t['Resources']['AlertStreamLag']['Properties']['Statistic'], 'Maximum')

    def test_optional_recovery_cost_is_not_implicitly_enabled(self):
        t = config.cognito_template()
        self.assertEqual(t['Parameters']['EnableScopeRecovery']['Default'], 'false')
        for resource in t['Resources'].values():
            if resource['Type'] == 'AWS::DynamoDB::Table':
                expression = resource['Properties']['PointInTimeRecoverySpecification']['PointInTimeRecoveryEnabled']
                self.assertFalse(resolve(expression, {'EnableScopeRecovery': 'false'}, t['Conditions']))
                self.assertTrue(resource['Properties']['DeletionProtectionEnabled'])


if __name__ == '__main__':
    unittest.main()
