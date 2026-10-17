"""Bounded, idempotent recovery of already authorized SQL outbox work."""
import os

def run(event):
    rule=os.environ.get('FINTRUST_OUTBOX_RULE_ARN')
    if (not rule or not isinstance(event,dict) or event.get('source')!='aws.events'
            or event.get('detail-type')!='Scheduled Event' or event.get('resources')!=[rule]
            or event.get('account')!='966467878406' or event.get('region')!='af-south-1'):
        raise ValueError('Unrecognized outbox schedule')
    from .release_workflow import drain_corrections,drain_projections
    return {'corrections':drain_corrections(limit=5),'projections':drain_projections(limit=5)}
