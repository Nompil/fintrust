"""Reuse immutable evidence only within one HTTP request; never cache identity grants."""
from copy import deepcopy
from functools import wraps
from flask import g, has_request_context


def request_cached(function):
    @wraps(function)
    def read(*args, **kwargs):
        if not has_request_context():
            return function(*args, **kwargs)
        cache = g.setdefault('immutable_evidence_cache', {})
        key = (function.__module__, function.__name__, repr(args), repr(sorted(kwargs.items())))
        if key not in cache:
            cache[key] = deepcopy(function(*args, **kwargs))
        return deepcopy(cache[key])
    return read


def invalidate():
    if has_request_context():
        g.pop('immutable_evidence_cache', None)
