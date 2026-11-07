import pytest

from app.services import validation


def test_email_is_cleaned_and_lowercased():
    assert validation.clean_email("  Priya.Sharma@Acme.test ") == "priya.sharma@acme.test"


@pytest.mark.parametrize("bad", ["", "no-at-sign", "a@b", "a b@c.com", "@x.com", "a@" + "b" * 260 + ".com"])
def test_bad_emails_are_refused(bad):
    with pytest.raises(ValueError):
        validation.clean_email(bad)


def test_password_length_rules():
    assert validation.check_password("long-enough-1")
    with pytest.raises(ValueError):
        validation.check_password("short")
    with pytest.raises(ValueError):
        validation.check_password("x" * 129)


def test_level_must_be_one_to_four():
    assert validation.check_level(3) == 3
    for bad in (0, 5, -1):
        with pytest.raises(ValueError):
            validation.check_level(bad)
