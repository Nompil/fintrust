"""Fail-closed bearer authentication for local Release 1 integration.
Opaque 256-bit credentials are stored only as hashes in an ignored operator file.
Never trust role/subject/account values supplied by HTTP headers or JSON bodies.
Deployment federation is a separate approval; this is not a Cognito substitute.
"""
import hashlib
import hmac
import json
import os
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID
from flask import request
from .release_contract import authorize

@dataclass(frozen=True)
class Principal:
    subject: str
    role: str
    accounts: tuple
    auth_source: str = "local"
    user_id: str | None = None
    display_name: str | None = None
    email: str | None = None
    def require(self,action): authorize(self.role,action)
    def account(self,identifier):
        value=str(UUID(str(identifier)))
        if value not in self.accounts: raise PermissionError("Object is outside the assigned account scope")
        return value

def authenticate():
    value=request.headers.get("Authorization","")
    if not value.startswith("Bearer ") or not 1<=len(value[7:])<=16384:
        raise PermissionError("Authentication required")
    mode=os.getenv("AUTH_MODE", "cognito" if os.getenv("AWS_EXECUTION_ENV") else "local").lower()
    if mode=="cognito":
        from .cognito_auth import authenticate as authenticate_cognito
        return authenticate_cognito(value[7:])
    if mode!="local" or len(value[7:])<32:
        raise PermissionError("Authentication required")
    path=os.getenv("FINTRUST_AUTH_FILE")
    if not path: raise PermissionError("Authentication required")
    try:
        from .identity_registry import read_registry
        registry=read_registry()
        digest=hashlib.sha256(value[7:].encode()).hexdigest()
        found=[p for p in registry["principals"] if hmac.compare_digest(p["token_sha256"],digest)]
        if len(found)!=1: raise PermissionError("Authentication required")
        p=found[0]
        if p.get("status","ACTIVE")!="ACTIVE": raise PermissionError("Authentication required")
        principal=Principal(p["subject"],p["role"],tuple(str(UUID(x)) for x in p["accounts"]))
        principal.require("read")
        if not principal.subject or len(principal.subject)>200: raise ValueError()
        return principal
    except (OSError,ValueError,KeyError,TypeError): raise PermissionError("Authentication required") from None
