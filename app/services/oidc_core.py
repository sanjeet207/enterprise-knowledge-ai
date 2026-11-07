"""The pure, testable parts of single sign-on (OpenID Connect, authorization code flow with PKCE).

No network and no third-party packages here: PKCE, the signed state cookie, claim checks and the account rule.
"""
import base64
import hashlib
import hmac
import json
import re
import secrets
import time
from typing import Any, Dict, Optional, Tuple

COOKIE_SECONDS = 600
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")


class OidcError(ValueError):
    """Sign-in could not be completed. The message is for logs; the person only sees a generic failure."""


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def new_verifier() -> str:
    return secrets.token_urlsafe(48)


def code_challenge(verifier: str) -> str:
    return _b64(hashlib.sha256(verifier.encode("ascii")).digest())


def sign_cookie(secret: str, payload: Dict[str, Any], now: Optional[float] = None) -> str:
    body = dict(payload, exp=int((now if now is not None else time.time()) + COOKIE_SECONDS))
    raw = _b64(json.dumps(body, separators=(",", ":")).encode())
    mac = hmac.new((secret + ":sso").encode(), raw.encode(), hashlib.sha256).digest()
    return raw + "." + _b64(mac)


def read_cookie(secret: str, value: str, now: Optional[float] = None) -> Dict[str, Any]:
    try:
        raw, mac = value.split(".", 1)
        expected = hmac.new((secret + ":sso").encode(), raw.encode(), hashlib.sha256).digest()
        if not hmac.compare_digest(_unb64(mac), expected):
            raise OidcError("bad signature")
        body = json.loads(_unb64(raw))
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        raise OidcError("unreadable state") from exc
    if body.get("exp", 0) < (now if now is not None else time.time()):
        raise OidcError("state expired")
    return body


def pick_email(claims: Dict[str, Any]) -> str:
    email = str(claims.get("email") or claims.get("preferred_username") or "").strip().lower()
    if not _EMAIL.match(email):
        raise OidcError("no usable email in the token")
    return email


def validate_claims(claims: Dict[str, Any], *, issuer: str, client_id: str, nonce: str,
                    now: Optional[float] = None) -> Tuple[str, str]:
    """Checks that remain after the signature is verified. Returns (subject, email)."""
    if claims.get("iss") != issuer:
        raise OidcError("wrong issuer")
    aud = claims.get("aud")
    if client_id not in (aud if isinstance(aud, list) else [aud]):
        raise OidcError("wrong audience")
    if float(claims.get("exp", 0)) < (now if now is not None else time.time()):
        raise OidcError("token expired")
    if not hmac.compare_digest(str(claims.get("nonce", "")), nonce):
        raise OidcError("nonce mismatch")
    if claims.get("email_verified") is False:
        raise OidcError("email not verified")
    subject = str(claims.get("sub") or "")
    if not subject:
        raise OidcError("no subject")
    return subject, pick_email(claims)


def choose_account(by_subject, unlinked_by_email):
    """Who is signing in? Returns (account, first_time).
    A person already linked to this identity, or a provisioned person who has not linked one yet (matched by email).
    Anyone else is refused: administrators create accounts, the identity provider only proves who you are."""
    if by_subject is not None:
        return by_subject, False
    if unlinked_by_email is not None:
        return unlinked_by_email, True
    return None, False
