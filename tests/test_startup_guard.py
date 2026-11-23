import pytest

from app.services import startup_guard as g


def test_finds_demo_domains_and_subdomains():
    assert g.demo_accounts(["a@acme.test", "b@corp.com", "c@x.northwind.test"]) == ["a@acme.test", "c@x.northwind.test"]


def test_lookalike_domain_is_not_demo():
    assert g.demo_accounts(["a@notacme.test", "b@acme.test.evil.com"]) == []


def test_production_refuses_demo_accounts():
    with pytest.raises(g.DemoDataInProduction):
        g.check("production", False, ["a@acme.test"])


def test_production_allows_when_deliberate():
    assert g.check("production", True, ["a@acme.test"]) == ["a@acme.test"]


def test_development_never_blocks():
    assert g.check("development", False, ["a@acme.test"]) == ["a@acme.test"]


def test_production_with_real_accounts_starts():
    assert g.check("Production", False, ["a@company.com"]) == []
