import pytest

from app.services.upload_policy import can_delete, check_upload

TEAM = "11111111-1111-1111-1111-111111111111"


def test_administrator_may_publish_company_wide_at_any_level():
    check_upload(True, 1, 4, None, False)


def test_administrator_may_publish_into_any_team():
    check_upload(True, 1, 3, TEAM, False)


def test_analyst_cannot_upload():
    with pytest.raises(PermissionError, match="role cannot"):
        check_upload(False, 1, 1, TEAM, True)


def test_manager_cannot_publish_company_wide():
    with pytest.raises(PermissionError, match="administrators"):
        check_upload(False, 2, 1, None, False)


def test_manager_must_belong_to_the_team():
    with pytest.raises(PermissionError, match="belong to"):
        check_upload(False, 2, 1, TEAM, False)


def test_manager_cannot_classify_above_own_level():
    with pytest.raises(PermissionError, match="above your own level"):
        check_upload(False, 2, 3, TEAM, True)


def test_manager_may_add_to_own_team_up_to_own_level():
    check_upload(False, 2, 2, TEAM, True)
    check_upload(False, 3, 3, TEAM, True)


def test_delete_rights():
    assert can_delete(True, "u1", "someone-else")
    assert can_delete(False, "u1", "u1")
    assert not can_delete(False, "u1", "u2")
    assert not can_delete(False, "u1", None)
