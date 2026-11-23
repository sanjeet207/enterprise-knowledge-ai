import pytest

from app.services import access_requests as ar


def test_a_request_needs_a_question_and_a_real_reason():
    assert ar.clean_request("  the  Titan   valuation ", "I am staffed on the review next week") == (
        "the Titan valuation", "I am staffed on the review next week")
    with pytest.raises(ValueError):
        ar.clean_request("   ", "I am staffed on the review")
    with pytest.raises(ValueError):
        ar.clean_request("the Titan valuation", "pls")  # a reason is the point of the request
    with pytest.raises(ValueError):
        ar.clean_request("x" * (ar.MAX_QUESTION + 1), "a proper reason here")
    with pytest.raises(ValueError):
        ar.clean_request("the Titan valuation", "r" * (ar.MAX_REASON + 1))


def test_only_a_pending_request_can_be_decided():
    assert ar.check_decision("pending", "approved", "", "admin-1", "user-1") == ""
    with pytest.raises(ValueError):
        ar.check_decision("approved", "denied", "too late", "admin-1", "user-1")


def test_nobody_decides_their_own_request():
    with pytest.raises(PermissionError):
        ar.check_decision("pending", "approved", "", "same-person", "same-person")


def test_a_denial_must_say_why():
    with pytest.raises(ValueError):
        ar.check_decision("pending", "denied", "", "admin-1", "user-1")
    assert ar.check_decision("pending", "denied", " Ask the engagement lead to add you to the team ", "admin-1", "user-1") \
        == "Ask the engagement lead to add you to the team"


def test_unknown_decisions_are_rejected():
    with pytest.raises(ValueError):
        ar.check_decision("pending", "maybe", "", "admin-1", "user-1")


def test_the_router_is_mounted_and_admin_routes_need_an_administrator():
    from app.main import app
    routes = {(r.path, tuple(sorted(r.methods))) for r in app.routes if hasattr(r, "methods")}
    assert ("/access-requests", ("POST",)) in routes
    assert ("/admin/access-requests/{request_id}/decision", ("POST",)) in routes
    admin_route = next(r for r in app.routes if getattr(r, "path", "") == "/admin/access-requests")
    names = [d.call.__name__ for d in admin_route.dependant.dependencies]
    assert "require_admin" in names


def test_only_a_company_question_refusal_offers_a_request():
    import inspect
    from app.agents import orchestrator
    source = inspect.getsource(orchestrator)
    assert source.count('can_request_access') == 1  # never on the off-topic refusal
    assert source.index('can_request_access') > source.index('return finish("refused", OFF_TOPIC')
