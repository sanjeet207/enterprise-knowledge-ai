import pytest

from app import config
from app.services import admin


def test_test_accounts_are_matched_by_prefix_only(monkeypatch):
    monkeypatch.setattr(config, "INSIGHTS_EXCLUDE_PREFIXES", ("lockout.", "eval."))
    assert admin.exclusion_patterns() == ["lockout.%", "eval.%"]


def test_like_wildcards_in_a_prefix_cannot_widen_the_filter(monkeypatch):
    monkeypatch.setattr(config, "INSIGHTS_EXCLUDE_PREFIXES", ("a%b_",))
    assert admin.exclusion_patterns() == ["a\\%b\\_%"]


def test_an_empty_list_excludes_nothing(monkeypatch):
    monkeypatch.setattr(config, "INSIGHTS_EXCLUDE_PREFIXES", ())
    assert admin.exclusion_patterns() == []


def test_reset_refuses_a_real_tenant():
    from scripts import reset_demo_activity as r
    with pytest.raises(SystemExit):
        r.reset("acme-corp-production")
