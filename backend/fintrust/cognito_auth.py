"""Cognito access-token verification and separate application account scoping."""
import os
import re
import uuid
from contextvars import ContextVar
from functools import lru_cache
from time import time

import jwt
from jwt import PyJWKClient

GROUP_ROLES = {
    "Analysts": "Risk/Compliance Analyst",
    "Administrators": "Admin",
    "Auditors": "Read-only/Auditor",
    "Maintainers": "Maintainer",
}

# API Gateway's Cognito authorizer validates the JWT before invoking the Lambda.
# The Lambda must not fetch public JWKS because it runs without public egress.
# Only the Lambda proxy adapter sets this context from requestContext.authorizer.
_gateway_claims = ContextVar("fintrust_gateway_claims", default=None)


def set_gateway_claims(claims):
    """Set the API Gateway authorizer claims for the active Lambda invocation."""
    if not isinstance(claims, dict):
        claims = None
    return _gateway_claims.set(claims)


def reset_gateway_claims(token):
    _gateway_claims.reset(token)


def configuration():
    region = os.getenv("AWS_REGION", "af-south-1")
    pool_id = os.getenv("COGNITO_USER_POOL_ID", "")
    client_id = os.getenv("COGNITO_APP_CLIENT_ID", "")
    domain = os.getenv("COGNITO_DOMAIN", "").rstrip("/")
    redirect = os.getenv("COGNITO_REDIRECT_URI", "")
    logout = os.getenv("COGNITO_LOGOUT_URI", "")
    scope_table = os.getenv("COGNITO_USER_SCOPE_TABLE", "")
    if not pool_id or not client_id or not domain or not redirect or not logout:
        raise RuntimeError("Cognito authentication configuration is incomplete")
    if not re.fullmatch(r"[a-z]{2}(?:-[a-z]+)+-\d+_[A-Za-z0-9]+", pool_id):
        raise RuntimeError("Invalid Cognito User Pool ID")
    if pool_id.split("_", 1)[0] != region:
        raise RuntimeError("Cognito User Pool region does not match AWS_REGION")
    if not domain.startswith("https://") or any(c in domain for c in "?#"):
        raise RuntimeError("Cognito domain must be an HTTPS origin")
    for uri in (redirect, logout):
        if not uri.startswith("https://") or any(c in uri for c in "?#"):
            raise RuntimeError("Cognito callback and logout URLs must be HTTPS URLs")
    issuer = f"https://cognito-idp.{region}.amazonaws.com/{pool_id}"
    return {"region": region, "pool_id": pool_id, "client_id": client_id,
            "domain": domain, "redirect_uri": redirect, "logout_uri": logout,
            "issuer": issuer, "scope_table": scope_table}


@lru_cache(maxsize=8)
def _jwks_client(issuer):
    return PyJWKClient(issuer + "/.well-known/jwks.json", cache_keys=True, timeout=5)


def verify_access_token(encoded):
    """Verify RS256 signature and required Cognito access-token claims."""
    cfg = configuration()
    if not isinstance(encoded, str) or len(encoded) > 16384:
        raise PermissionError("Authentication required")
    try:
        key = _jwks_client(cfg["issuer"]).get_signing_key_from_jwt(encoded)
        claims = jwt.decode(encoded, key.key, algorithms=["RS256"], issuer=cfg["issuer"],
                            options={"require": ["exp", "iat", "iss", "sub", "token_use",
                                                 "client_id", "username", "cognito:groups"]})
        if claims["token_use"] != "access" or claims["client_id"] != cfg["client_id"]:
            raise PermissionError("Authentication required")
        if not isinstance(claims["sub"], str) or not claims["sub"] or len(claims["sub"]) > 128:
            raise PermissionError("Authentication required")
        if not isinstance(claims["username"], str) or not claims["username"] or len(claims["username"]) > 128:
            raise PermissionError("Authentication required")
        groups = claims["cognito:groups"]
        if (not isinstance(groups, list) or len(groups) != 1
                or not isinstance(groups[0], str) or groups[0] not in GROUP_ROLES):
            raise PermissionError("Authentication required")
        return claims, GROUP_ROLES[groups[0]]
    except PermissionError:
        raise
    except Exception:
        # Do not expose signature, key-fetch, issuer or claim parsing diagnostics.
        raise PermissionError("Authentication required") from None


def _account_scope(subject, username):
    table_name = os.getenv("COGNITO_USER_SCOPE_TABLE", "")
    if not table_name:
        raise PermissionError("Authentication required")
    try:
        import boto3
        item = boto3.resource("dynamodb", region_name=os.getenv("AWS_REGION", "af-south-1"))\
            .Table(table_name).get_item(Key={"subject": subject}, ConsistentRead=True).get("Item")
        if not item or item.get("status") != "ACTIVE" or item.get("username") != username:
            raise PermissionError("Authentication required")
        accounts = item.get("accounts")
        if not isinstance(accounts, list) or len(accounts) > 1000:
            raise PermissionError("Authentication required")
        normalized = tuple(str(uuid.UUID(str(value))) for value in accounts)
        if len(set(normalized)) != len(normalized):
            raise PermissionError("Authentication required")
        return normalized
    except PermissionError:
        raise
    except Exception:
        raise PermissionError("Authentication required") from None


def _role_from_gateway_claims(claims):
    """Validate the required authorizer claims without network access."""
    cfg = configuration()
    now = int(time())
    if (not isinstance(claims, dict)
            or claims.get("iss") != cfg["issuer"]
            or claims.get("token_use") != "access"
            or claims.get("client_id") != cfg["client_id"]):
        raise PermissionError("Authentication required")
    try:
        exp = int(claims["exp"])
        issued = int(claims["iat"])
    except (KeyError, TypeError, ValueError):
        raise PermissionError("Authentication required") from None
    if exp <= now or issued > now + 60 or not isinstance(claims.get("scope"), str):
        raise PermissionError("Authentication required")
    if "openid" not in claims["scope"].split():
        raise PermissionError("Authentication required")
    subject = claims.get("sub")
    username = claims.get("username")
    if (not isinstance(subject, str) or not subject or len(subject) > 128
            or not isinstance(username, str) or not username or len(username) > 128):
        raise PermissionError("Authentication required")
    raw_groups = claims.get("cognito:groups", "")
    if isinstance(raw_groups, str):
        groups = [value.strip() for value in raw_groups.split(",") if value.strip()]
    elif isinstance(raw_groups, list):
        groups = raw_groups
    else:
        groups = []
    if len(groups) != 1 or not isinstance(groups[0], str) or groups[0] not in GROUP_ROLES:
        raise PermissionError("Authentication required")
    return claims, GROUP_ROLES[groups[0]]


def authenticate(encoded):
    claims = _gateway_claims.get()
    if claims is not None:
        claims, role = _role_from_gateway_claims(claims)
    elif os.getenv("AWS_EXECUTION_ENV"):
        # Cloud Cognito mode is only valid behind API Gateway's authorizer. Never
        # fall back to outbound JWKS access from the private application Lambda.
        raise PermissionError("Authentication required")
    else:
        claims, role = verify_access_token(encoded)
    from .auth import Principal
    accounts = _account_scope(claims["sub"], claims["username"])
    return Principal(claims["username"], role, accounts, auth_source="cognito",
                     user_id=str(uuid.uuid5(uuid.NAMESPACE_URL, "cognito:" + claims["sub"])),
                     display_name=claims["username"], email=claims.get("email"))
