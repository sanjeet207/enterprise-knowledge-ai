"""Single sign-on with an OpenID Connect provider such as Microsoft Entra ID. Network and signature checks live here."""
import urllib.parse
from typing import Any, Dict, Tuple

import httpx

from app import config
from app.services import oidc_core

_discovery: Dict[str, Any] | None = None
_jwks_client = None


def _config_doc() -> Dict[str, Any]:
    global _discovery
    if _discovery is None:
        url = config.OIDC_ISSUER.rstrip("/") + "/.well-known/openid-configuration"
        doc = httpx.get(url, timeout=10).raise_for_status().json()
        if doc.get("issuer") != config.OIDC_ISSUER:
            raise oidc_core.OidcError("issuer in discovery document does not match OIDC_ISSUER")
        _discovery = doc
    return _discovery


def authorize_url(state: str, nonce: str, challenge: str) -> str:
    params = {
        "client_id": config.OIDC_CLIENT_ID, "response_type": "code", "redirect_uri": config.OIDC_REDIRECT_URI,
        "scope": "openid email profile", "state": state, "nonce": nonce,
        "code_challenge": challenge, "code_challenge_method": "S256",
    }
    return _config_doc()["authorization_endpoint"] + "?" + urllib.parse.urlencode(params)


def exchange_code(code: str, verifier: str) -> str:
    """Trade the one-time code for an ID token."""
    data = {"grant_type": "authorization_code", "code": code, "redirect_uri": config.OIDC_REDIRECT_URI,
            "client_id": config.OIDC_CLIENT_ID, "code_verifier": verifier}
    if config.OIDC_CLIENT_SECRET:
        data["client_secret"] = config.OIDC_CLIENT_SECRET
    response = httpx.post(_config_doc()["token_endpoint"], data=data, timeout=15)
    if response.status_code != 200:
        raise oidc_core.OidcError(f"token endpoint returned {response.status_code}")
    token = response.json().get("id_token")
    if not token:
        raise oidc_core.OidcError("no id_token in the response")
    return token


def verify_id_token(id_token: str, nonce: str) -> Tuple[str, str]:
    """Verify the signature (RS256, keys from the provider) and every claim. Returns (subject, email)."""
    import jwt
    global _jwks_client
    if _jwks_client is None:
        _jwks_client = jwt.PyJWKClient(_config_doc()["jwks_uri"])
    try:
        key = _jwks_client.get_signing_key_from_jwt(id_token).key
        claims = jwt.decode(id_token, key, algorithms=["RS256"], audience=config.OIDC_CLIENT_ID,
                            issuer=config.OIDC_ISSUER, options={"require": ["exp", "iat", "iss", "aud"]})
    except jwt.PyJWTError as exc:
        raise oidc_core.OidcError(f"invalid id_token: {exc.__class__.__name__}") from exc
    return oidc_core.validate_claims(claims, issuer=config.OIDC_ISSUER, client_id=config.OIDC_CLIENT_ID, nonce=nonce)
