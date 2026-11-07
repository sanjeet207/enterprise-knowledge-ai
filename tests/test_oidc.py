import time
import types

import pytest

from app.services import oidc_core as core

SECRET = "s" * 40
ISS, CID = "https://login.example.test/tenant-1/v2.0", "client-123"


def claims(**over):
    base = {"iss": ISS, "aud": CID, "exp": time.time() + 300, "iat": time.time(), "nonce": "n1",
            "sub": "abc", "email": "Priya@Acme.test"}
    base.update(over)
    return base


def test_pkce_challenge_matches_the_rfc_example():
    # RFC 7636 appendix B
    assert core.code_challenge("dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk") == "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"


def test_verifiers_are_long_and_unique():
    a, b = core.new_verifier(), core.new_verifier()
    assert a != b and len(a) >= 43


def test_state_cookie_round_trip():
    cookie = core.sign_cookie(SECRET, {"state": "x", "nonce": "y", "verifier": "z"}, now=1000)
    body = core.read_cookie(SECRET, cookie, now=1100)
    assert body["state"] == "x" and body["verifier"] == "z"


def test_state_cookie_expires_and_resists_tampering():
    cookie = core.sign_cookie(SECRET, {"state": "x"}, now=1000)
    with pytest.raises(core.OidcError, match="expired"):
        core.read_cookie(SECRET, cookie, now=1000 + core.COOKIE_SECONDS + 1)
    raw, mac = cookie.split(".")
    with pytest.raises(core.OidcError):
        core.read_cookie(SECRET, raw + "." + mac[::-1], now=1100)
    with pytest.raises(core.OidcError):
        core.read_cookie("another-secret-" + "x" * 30, cookie, now=1100)
    with pytest.raises(core.OidcError):
        core.read_cookie(SECRET, "garbage", now=1100)


def test_valid_claims_return_subject_and_lowercase_email():
    assert core.validate_claims(claims(), issuer=ISS, client_id=CID, nonce="n1") == ("abc", "priya@acme.test")


def test_audience_may_be_a_list():
    assert core.validate_claims(claims(aud=["other", CID]), issuer=ISS, client_id=CID, nonce="n1")[0] == "abc"


@pytest.mark.parametrize("over,message", [
    ({"iss": "https://evil.test"}, "issuer"), ({"aud": "someone-else"}, "audience"),
    ({"exp": time.time() - 5}, "expired"), ({"nonce": "other"}, "nonce"),
    ({"email_verified": False}, "verified"), ({"sub": ""}, "subject"),
    ({"email": "not-an-email", "preferred_username": ""}, "email"),
])
def test_bad_claims_are_refused(over, message):
    with pytest.raises(core.OidcError, match=message):
        core.validate_claims(claims(**over), issuer=ISS, client_id=CID, nonce="n1")


def test_preferred_username_is_used_when_there_is_no_email_claim():
    c = claims(); c.pop("email"); c["preferred_username"] = "asha@acme.test"
    assert core.validate_claims(c, issuer=ISS, client_id=CID, nonce="n1")[1] == "asha@acme.test"


def test_account_choice_rules():
    linked, fresh = object(), object()
    assert core.choose_account(linked, fresh) == (linked, False)
    assert core.choose_account(None, fresh) == (fresh, True)
    assert core.choose_account(None, None) == (None, False)


def test_signed_id_token_is_verified_end_to_end(monkeypatch):
    jwt = pytest.importorskip("jwt")
    rsa = pytest.importorskip("cryptography.hazmat.primitives.asymmetric.rsa")
    pytest.importorskip("httpx")
    from app import config
    from app.services import oidc

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    monkeypatch.setattr(config, "OIDC_ISSUER", ISS)
    monkeypatch.setattr(config, "OIDC_CLIENT_ID", CID)
    fake = types.SimpleNamespace(get_signing_key_from_jwt=lambda t: types.SimpleNamespace(key=key.public_key()))
    monkeypatch.setattr(oidc, "_jwks_client", fake)

    good = jwt.encode(claims(), key, algorithm="RS256")
    assert oidc.verify_id_token(good, "n1") == ("abc", "priya@acme.test")

    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    forged = jwt.encode(claims(), other, algorithm="RS256")
    with pytest.raises(core.OidcError):
        oidc.verify_id_token(forged, "n1")
    unsigned = jwt.encode(claims(), key=None, algorithm="none")
    with pytest.raises(core.OidcError):
        oidc.verify_id_token(unsigned, "n1")
    with pytest.raises(core.OidcError):
        oidc.verify_id_token(good, "wrong-nonce")
