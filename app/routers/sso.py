import logging
import secrets

from fastapi import APIRouter, Cookie, Request
from fastapi.responses import RedirectResponse

from app import config
from app.security import create_access_token
from app.services import oidc, oidc_core, sso_accounts

router = APIRouter(prefix="/auth", tags=["Auth"])
logger = logging.getLogger("eka.sso")
COOKIE = "eka_sso"


@router.get("/config")
def auth_config():
    """What the sign-in page should offer."""
    return {"sso": config.OIDC_ENABLED, "password": config.PASSWORD_LOGIN_ENABLED}


def _failed(reason: str) -> RedirectResponse:
    logger.warning("SSO sign-in refused: %s", reason)
    response = RedirectResponse("/#sso_error=1", status_code=303)
    response.delete_cookie(COOKIE, path="/auth/sso")
    return response


@router.get("/sso/login")
def sso_login():
    if not config.OIDC_ENABLED:
        return _failed("SSO is not configured")
    state, nonce, verifier = secrets.token_urlsafe(24), secrets.token_urlsafe(24), oidc_core.new_verifier()
    try:
        url = oidc.authorize_url(state, nonce, oidc_core.code_challenge(verifier))
    except Exception as exc:
        return _failed(f"provider unreachable: {exc.__class__.__name__}")
    response = RedirectResponse(url, status_code=303)
    cookie = oidc_core.sign_cookie(config.JWT_SECRET, {"state": state, "nonce": nonce, "verifier": verifier})
    response.set_cookie(COOKIE, cookie, max_age=oidc_core.COOKIE_SECONDS, httponly=True, samesite="lax",
                        secure=config.OIDC_REDIRECT_URI.startswith("https://"), path="/auth/sso")
    return response


@router.get("/sso/callback")
def sso_callback(request: Request, code: str = "", state: str = "", error: str = "",
                 eka_sso: str = Cookie(default="")):
    if error or not code or not state or not eka_sso:
        return _failed(f"provider error or missing parameters ({error or 'none'})")
    try:
        saved = oidc_core.read_cookie(config.JWT_SECRET, eka_sso)
        if not secrets.compare_digest(saved["state"], state):
            raise oidc_core.OidcError("state mismatch")
        identity = oidc.verify_identity(oidc.exchange_code(code, saved["verifier"]), saved["nonce"])
        user = sso_accounts.sign_in(identity)
    except Exception as exc:
        return _failed(f"{exc.__class__.__name__}: {exc}")
    response = RedirectResponse("/#sso_token=" + create_access_token(user.id), status_code=303)
    response.delete_cookie(COOKIE, path="/auth/sso")
    return response

