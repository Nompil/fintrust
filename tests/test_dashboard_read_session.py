from concurrent.futures import ThreadPoolExecutor
import threading
import pytest
from fintrust.read_session import read_session, read_connection
from tests.test_release1_end_to_end import release_db
from tests.test_multi_user_operations import people


def test_dashboard_reuses_one_readonly_connection_and_preserves_scope(release_db, people, monkeypatch):
    from fintrust import db
    client, headers, _ = people
    original = db.get_connection
    opened = []
    def connect():
        conn = original()
        opened.append(conn)
        return conn
    monkeypatch.setattr(db, 'get_connection', connect)
    for endpoint in ('/v1/release1/overview', '/v1/release1/insights?days=all'):
        opened.clear()
        response = client.get(endpoint, headers=headers('analyst01'))
        assert response.status_code == 200, response.json
        assert len(opened) == 1
        assert opened[0].closed
    assert client.get('/v1/release1/insights?account_id=20000000-0000-4000-8000-000000000099',
                      headers=headers('analyst01')).status_code == 403


def test_readonly_session_rejects_writes_and_releases_connection(release_db):
    import psycopg2
    opened = []
    def connect():
        conn = release_db[2]()
        opened.append(conn)
        return conn
    with pytest.raises(psycopg2.errors.ReadOnlySqlTransaction):
        with read_session(connect):
            with read_connection(lambda: pytest.fail('Unexpected second connection')) as conn:
                with conn.cursor() as cur:
                    cur.execute('CREATE TABLE dashboard_forbidden_write(id integer)')
    assert opened[0].closed
    with read_connection(connect) as conn:
        assert conn is opened[1]
        with conn.cursor() as cur:
            cur.execute("SELECT to_regclass('dashboard_forbidden_write')")
            assert cur.fetchone() == (None,)


def test_concurrent_requests_never_share_connections():
    barrier = threading.Barrier(2)
    class Connection:
        def set_session(self, **settings):
            assert settings == {'readonly': True, 'isolation_level': 'REPEATABLE READ'}
        def rollback(self): pass
        def close(self): self.closed = True
    def request(_):
        expected = Connection()
        with read_session(lambda: expected):
            barrier.wait(timeout=5)
            with read_connection(lambda: pytest.fail('Unexpected factory call')) as actual:
                assert actual is expected
        assert expected.closed
        return expected
    with ThreadPoolExecutor(max_workers=2) as pool:
        first, second = pool.map(request, range(2))
    assert first is not second
