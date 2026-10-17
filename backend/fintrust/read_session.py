"""One connection and read-only snapshot per dashboard request; no result cache."""
from contextlib import contextmanager
from contextvars import ContextVar

_active = ContextVar('fintrust_read_session', default=None)


@contextmanager
def read_session(factory):
    if _active.get() is not None:
        yield _active.get()
        return
    conn = factory()
    token = None
    try:
        conn.set_session(readonly=True, isolation_level='REPEATABLE READ')
        token = _active.set(conn)
        yield conn
    finally:
        if token is not None:
            _active.reset(token)
        try:
            conn.rollback()
        finally:
            conn.close()


@contextmanager
def read_connection(factory):
    conn = _active.get()
    if conn is not None:
        yield conn
        return
    conn = factory()
    try:
        yield conn
    finally:
        conn.close()
