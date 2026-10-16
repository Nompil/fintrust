"""Actual Lambda proxy adapter preserves stage URLs without trusting headers."""
import pytest
from fintrust import api, cognito_auth


def event(stage='dev', domain='example.execute-api.af-south-1.amazonaws.com'):
    return {'httpMethod': 'GET', 'path': '/', 'queryStringParameters': None,
            'headers': {'Host': domain, 'X-Forwarded-Proto': 'https', 'X-Forwarded-Port': '443'},
            'body': None, 'isBase64Encoded': False,
            'requestContext': {'stage': stage, 'domainName': domain}}


@pytest.mark.parametrize('stage', ['dev', 'staging', 'prod'])
def test_proxy_document_uses_trusted_stage_and_resets_between_requests(monkeypatch, stage):
    monkeypatch.setenv('AUTH_MODE', 'local')
    response = api.lambda_handler(event(stage), None)
    assert response['statusCode'] == '200'
    assert f'name="fintrust-api-base" content="/{stage}"' in response['body']
    assert f'src="/{stage}/assets/js/release1.js' in response['body']
    assert 'src="/assets/' not in response['body']
    assert api._public_base_path.get() == ''
    assert cognito_auth._gateway_claims.get() is None
    with api.app.test_client() as client:
        local = client.get('/release1').get_data(as_text=True)
    assert 'name="fintrust-api-base" content=""' in local
    assert 'src="/assets/js/release1.js' in local


@pytest.mark.parametrize('stage,domain', [('dev','workbench.example.test'), ('bad"><script>', 'x.execute-api.af-south-1.amazonaws.com'), ({},'x.execute-api.af-south-1.amazonaws.com')])
def test_custom_domain_root_and_invalid_stage_never_inject_a_prefix(monkeypatch, stage, domain):
    monkeypatch.setenv('AUTH_MODE', 'local')
    response = api.lambda_handler(event(stage, domain), None)
    assert response['statusCode'] == '200'
    assert 'name="fintrust-api-base" content=""' in response['body']
    assert api._public_base_path.get() == ''


def test_gateway_failure_resets_prefix_and_claims(monkeypatch):
    def fail(*args, **kwargs):
        assert api._public_base_path.get() == '/dev'
        raise RuntimeError('synthetic adapter failure')
    monkeypatch.setattr(api.awsgi, 'response', fail)
    with pytest.raises(RuntimeError):
        api.lambda_handler(event(), None)
    assert api._public_base_path.get() == ''
    assert cognito_auth._gateway_claims.get() is None
