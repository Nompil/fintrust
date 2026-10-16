"""Browser smoke for Cognito PKCE and user switching; OAuth is mocked locally."""
import os
import subprocess
import threading
import base64
from urllib.parse import parse_qsl
from pathlib import Path

import pytest
from werkzeug.serving import make_server

from fintrust import api, cognito_auth
from fintrust.auth import Principal


@pytest.mark.skipif(not os.getenv('FINTRUST_NODE'), reason='Explicit installed Node/Playwright browser gate')
@pytest.mark.parametrize('prefix', ['', '/dev'])
def test_cognito_pkce_callback_and_switch_user(monkeypatch, tmp_path, prefix):
    monkeypatch.setenv('AUTH_MODE', 'cognito')
    monkeypatch.setenv('AWS_REGION', 'af-south-1')
    monkeypatch.setenv('COGNITO_USER_POOL_ID', 'af-south-1_TestPool')
    monkeypatch.setenv('COGNITO_APP_CLIENT_ID', 'synthetic-client-id')
    monkeypatch.setenv('COGNITO_DOMAIN', 'https://imbokodo-test.auth.af-south-1.amazoncognito.com')
    monkeypatch.setenv('COGNITO_REDIRECT_URI', 'https://workbench.example.test/release1')
    monkeypatch.setenv('COGNITO_LOGOUT_URI', 'https://workbench.example.test/release1')
    monkeypatch.setenv('COGNITO_USER_SCOPE_TABLE', 'synthetic-scopes')
    monkeypatch.setattr(cognito_auth, 'authenticate', lambda _token: Principal(
        'auditor01', 'Read-only/Auditor', (), auth_source='cognito',
        user_id='20000000-0000-4000-8000-000000000001', display_name='auditor01'))

    def gateway(environ, start_response):
        # Reject root requests so the browser must retain the deployed stage
        # for every asset, auth-config read, sign-in POST and application read.
        path = environ['PATH_INFO']
        if not path.startswith(prefix + '/'):
            start_response('404 Not Found', [('Content-Type', 'text/plain')])
            return [b'Outside API Gateway stage']
        headers = {k[5:].replace('_', '-'): v for k, v in environ.items() if k.startswith('HTTP_')}
        headers.update({'Host': environ['HTTP_HOST'], 'X-Forwarded-Proto': 'http',
                        'X-Forwarded-Port': str(environ['SERVER_PORT'])})
        size = int(environ.get('CONTENT_LENGTH') or 0)
        event = {'httpMethod': environ['REQUEST_METHOD'], 'path': path[len(prefix):],
                 'headers': headers, 'queryStringParameters': dict(parse_qsl(environ.get('QUERY_STRING', ''))),
                 'body': environ['wsgi.input'].read(size).decode() if size else None,
                 'isBase64Encoded': False,
                 'requestContext': {'stage': 'dev', 'domainName': 'example.execute-api.af-south-1.amazonaws.com'}}
        response = api.lambda_handler(event, None)
        status = response['statusCode']
        start_response(str(status) + ' Response', list(response['headers'].items()))
        body = response.get('body', '')
        return [base64.b64decode(body) if response.get('isBase64Encoded') else body.encode()]

    server = make_server('127.0.0.1', 0, gateway if prefix else api.app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        root = Path(__file__).resolve().parents[1]
        output = tmp_path.as_posix()
        result = subprocess.run([
            os.environ['FINTRUST_NODE'], str(root / 'tools/verify_cognito_auth_ui.cjs'),
            f'http://127.0.0.1:{server.server_port}', output, prefix,
        ], capture_output=True, text=True, timeout=90)
        assert result.returncode == 0, result.stderr
        assert 'Cognito PKCE authorize/callback/token exchange' in result.stdout
    finally:
        server.shutdown()
        thread.join(timeout=10)
        server.server_close()
