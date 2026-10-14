"""Queue summaries must not imply two independent amount dimensions."""
from copy import deepcopy

import pytest

from fintrust.analyst_workflow import primary_reason
from fintrust.rules import evaluate


@pytest.mark.parametrize('reverse', [False, True])
def test_historical_amount_summary_keeps_score_and_full_evidence(reverse):
    signals = [
        {'rule': 'HIGH_AMOUNT', 'points': 30, 'reason': 'Amount exceeds 50000'},
        {'rule': 'VERY_HIGH_AMOUNT', 'points': 25, 'reason': 'Amount exceeds 200000'},
    ]
    if reverse:
        signals.reverse()
    signals.append({'rule': 'CROSS_BORDER', 'points': 15})
    risk = {'score': 70, 'risk_level': 'High',
            'rule_version': 'fintrust-r1-rules-2026-10-09', 'triggered_rules': signals}
    original = deepcopy(risk)
    assert primary_reason(risk) == 'Very high amount + Cross-border'
    assert risk == original
    assert sum(s['points'] for s in risk['triggered_rules']) == 70


@pytest.mark.parametrize('rule,label', [
    ('HIGH_AMOUNT', 'High amount'), ('VERY_HIGH_AMOUNT', 'Very high amount'),
])
def test_single_historical_amount_rule_remains_visible(rule, label):
    assert primary_reason({'triggered_rules': [{'rule': rule}]}) == label


def test_current_exclusive_amount_band_summary_and_score_are_preserved():
    risk = evaluate({'amount': '200000.01', 'currency': 'ZAR', 'country': 'US'})
    original = deepcopy(risk)
    assert primary_reason(risk) == 'Amount risk + Cross-border'
    assert risk['score'] == 55
    assert [s['rule'] for s in risk['triggered_rules']] == ['AMOUNT_RISK', 'CROSS_BORDER']
    assert risk == original
