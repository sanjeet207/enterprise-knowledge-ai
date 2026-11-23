import pytest

from app import config
from app.services import oidc_core as core
from app.services import sso_accounts
from app.services.users import User

ISS, CID = "https://login.example.test/t/v2.0", "client-1"
G_ANALYST, G_MANAGER, G_PARTNER, G_ADMIN = "aaaa-1", "bbbb-2", "dddd-4", "ffff-9"
MAP = f"{G_ANALYST}:1,{G_MANAGER}:2,{G_PARTNER}:4"


def ident(*groups, overage=False, email="asha@acme.test", sub="sub-1"):
    return core.Identity(sub, email, tuple(g.lower() for g in groups), overage)


# ---------- pure rules ----------
def test_group_map_parses_and_lowercases():
    assert core.parse_group_map("ABC:2, def:4") == {"abc": 2, "def": 4}


@pytest.mark.parametrize("bad", ["abc", "abc:", ":3", "abc:0", "abc:5", "abc:x", "abc:2,def"])
def test_malformed_group_map_is_an_error_not_a_default(bad):
    with pytest.raises(core.OidcError):
        core.parse_group_map(bad)


def test_highest_mapped_level_wins_and_unmapped_groups_are_ignored():
    m = core.parse_group_map(MAP)
    assert core.directory_access(ident(G_ANALYST, G_MANAGER, "other"), m) == (2, False)


def test_no_mapped_group_means_no_access():
    assert core.directory_access(ident("other"), core.parse_group_map(MAP)) is None
    assert core.directory_access(ident(), core.parse_group_map(MAP)) is None


def test_admin_group_alone_gives_level_one_never_more():
    assert core.directory_access(ident(G_ADMIN), core.parse_group_map(MAP), G_ADMIN) == (1, True)
    assert core.directory_access(ident(G_ADMIN, G_PARTNER), core.parse_group_map(MAP), G_ADMIN) == (4, True)


def test_group_overage_fails_closed_even_if_some_groups_are_listed():
    assert core.directory_access(ident(G_PARTNER, overage=True), core.parse_group_map(MAP)) is None


def test_identity_reads_groups_and_overage_from_claims():
    import time
    claims = {"iss": ISS, "aud": CID, "exp": time.time() + 99, "nonce": "n", "sub": "s", "email": "a@b.test",
              "groups": ["AAAA-1", " "]}
    got = core.identity_from_claims(claims, issuer=ISS, client_id=CID, nonce="n")
    assert got.groups == ("aaaa-1",) and not got.groups_overage
    claims = {**claims, "groups": None, "_claim_names": {"groups": "src1"}}
    assert core.identity_from_claims(claims, issuer=ISS, client_id=CID, nonce="n").groups_overage


# ---------- account flow with fakes ----------
class World:
    def __init__(self, existing=None):
        self.users, self.events, self.linked = {}, [], {}
        if existing:
            self.users[existing.id] = existing

    def install(self, monkeypatch):
        w = self
        monkeypatch.setattr(config, "OIDC_ISSUER", ISS)
        monkeypatch.setattr(config, "OIDC_GROUP_LEVELS", MAP)
        monkeypatch.setattr(config, "OIDC_ADMIN_GROUP", G_ADMIN)
        monkeypatch.setattr(config, "OIDC_AUTO_PROVISION", False)
        monkeypatch.setattr(config, "OIDC_PROVISION_TENANT", "acme")
        u = sso_accounts.users
        monkeypatch.setattr(u, "get_by_sso", lambda iss, sub: next((x for x in w.users.values() if w.linked.get(x.id) == sub), None))
        monkeypatch.setattr(u, "get_unlinked_by_email", lambda e: next((x for x in w.users.values() if x.email == e and x.id not in w.linked), None))
        monkeypatch.setattr(u, "get_by_id", lambda i: w.users.get(i))
        monkeypatch.setattr(u, "link_sso", lambda i, iss, sub: w.linked.setdefault(i, sub) == sub)
        a = sso_accounts.admin
        monkeypatch.setattr(a, "record", lambda actor, action, target, detail=None: w.events.append((action, detail)))

        def create(tenant, email, pw, level, is_admin):
            if any(x.email == email for x in w.users.values()):
                return None
            uid = f"u{len(w.users) + 1}"
            w.users[uid] = User(uid, tenant, email, level, True, is_admin)
            return uid

        def update(tenant, uid, ch):
            old = w.users[uid]
            w.users[uid] = User(uid, old.tenant_id, old.email, ch.get("level", old.level), old.is_active, ch.get("is_admin", old.is_admin))
            return True
        monkeypatch.setattr(a, "create_user", create)
        monkeypatch.setattr(a, "update_user", update)


def person(level=1, admin=False, active=True):
    return User("u0", "acme", "asha@acme.test", level, active, admin)


def test_existing_account_level_follows_the_directory(monkeypatch):
    w = World(person(level=1)); w.install(monkeypatch)
    got = sso_accounts.sign_in(ident(G_PARTNER))
    assert (got.level, got.is_admin) == (4, False)
    assert [e[0] for e in w.events] == ["sso.link", "sso.sync"]


def test_removed_from_a_group_loses_access_on_next_sign_in(monkeypatch):
    w = World(person(level=4)); w.install(monkeypatch)
    sso_accounts.sign_in(ident(G_PARTNER))
    got = sso_accounts.sign_in(ident(G_ANALYST))
    assert got.level == 1
    with pytest.raises(core.OidcError, match="no mapped"):
        sso_accounts.sign_in(ident("left-the-company-group"))


def test_admin_flag_is_synced_both_ways(monkeypatch):
    w = World(person(level=1, admin=False)); w.install(monkeypatch)
    assert sso_accounts.sign_in(ident(G_ANALYST, G_ADMIN)).is_admin is True
    assert sso_accounts.sign_in(ident(G_ANALYST)).is_admin is False


def test_unchanged_access_writes_no_sync_event(monkeypatch):
    w = World(person(level=2)); w.install(monkeypatch)
    sso_accounts.sign_in(ident(G_MANAGER))
    w.events.clear()
    sso_accounts.sign_in(ident(G_MANAGER))
    assert w.events == []


def test_unknown_person_is_refused_unless_auto_provisioning_is_on(monkeypatch):
    w = World(); w.install(monkeypatch)
    with pytest.raises(core.OidcError, match="no provisioned"):
        sso_accounts.sign_in(ident(G_MANAGER))
    monkeypatch.setattr(config, "OIDC_AUTO_PROVISION", True)
    got = sso_accounts.sign_in(ident(G_MANAGER))
    assert (got.level, got.tenant_id, got.is_admin) == (2, "acme", False)
    assert w.events[0][0] == "sso.provision"


def test_auto_provisioning_needs_a_mapped_group_and_a_company(monkeypatch):
    w = World(); w.install(monkeypatch)
    monkeypatch.setattr(config, "OIDC_AUTO_PROVISION", True)
    with pytest.raises(core.OidcError):
        sso_accounts.sign_in(ident("not-mapped"))
    monkeypatch.setattr(config, "OIDC_PROVISION_TENANT", "")
    with pytest.raises(core.OidcError, match="no provisioned"):
        sso_accounts.sign_in(ident(G_MANAGER))


def test_switched_off_account_stays_off_whatever_the_groups_say(monkeypatch):
    w = World(person(active=False)); w.install(monkeypatch)
    with pytest.raises(core.OidcError, match="switched off"):
        sso_accounts.sign_in(ident(G_PARTNER))


def test_overage_is_refused_with_a_clear_reason(monkeypatch):
    w = World(person()); w.install(monkeypatch)
    with pytest.raises(core.OidcError, match="too many groups"):
        sso_accounts.sign_in(ident(G_PARTNER, overage=True))


def test_without_group_mapping_levels_stay_under_portal_control(monkeypatch):
    w = World(person(level=3)); w.install(monkeypatch)
    monkeypatch.setattr(config, "OIDC_GROUP_LEVELS", "")
    got = sso_accounts.sign_in(ident("anything"))
    assert got.level == 3 and [e[0] for e in w.events] == ["sso.link"]
