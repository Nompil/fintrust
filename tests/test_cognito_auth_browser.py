"""Browser smoke for Cognito PKCE and user switching; OAuth is mocked locally."""
import os
import subprocess
import threading
from pathlib import Path

import pytest
from werkzeug.serving import make_server

from fintrust import api, cognito_auth
from fintrust.auth import Principal


@pytest.mark.skipif(not os.getenv('FINTRUST_NODE'), reason='Explicit installed Node/Playwright browser gate')
def test_cognito_pkce_callback_and_switch_user(monkeypatch, tmp_path):
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

    server = make_server('127.0.0.1', 0, api.app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        root = Path(__file__).resolve().parents[1]
        output = tmp_path.as_posix()
        result = subprocess.run([
            os.environ['FINTRUST_NODE'], str(root / 'tools/verify_cognito_auth_ui.cjs'),
            f'http://127.0.0.1:{server.server_port}', output,
        ], capture_output=True, text=True, timeout=90)
        assert result.returncode == 0, result.stderr
        assert 'Cognito PKCE authorize/callback/token exchange' in result.stdout
    finally:
        server.shutdown()
        thread.join(timeout=10)
        server.server_close()
