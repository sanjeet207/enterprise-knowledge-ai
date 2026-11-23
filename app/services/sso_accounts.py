"""Who gets in after the identity provider has proven who someone is, and with what access.

Without group mapping: administrators create accounts and set levels in the portal (the provider only proves identity).
With group mapping (OIDC_GROUP_LEVELS): the company directory decides. Level and administrator flag follow the person's
groups on every sign-in, a person with no mapped group is refused, and accounts can be created on first sign-in.
"""
from app import config
from app.services import admin, oidc_core, users


def sign_in(identity: oidc_core.Identity) -> users.User:
    """The account to sign in, or OidcError. Records link, provision and sync events in the change history."""
    mapped = bool(config.OIDC_GROUP_LEVELS)
    access = None
    if mapped:
        access = oidc_core.directory_access(identity, oidc_core.parse_group_map(config.OIDC_GROUP_LEVELS),
                                            config.OIDC_ADMIN_GROUP)
        if access is None:
            reason = "group list incomplete (too many groups)" if identity.groups_overage else "no mapped directory group"
            raise oidc_core.OidcError(reason)

    by_subject = users.get_by_sso(config.OIDC_ISSUER, identity.subject)
    by_email = users.get_unlinked_by_email(identity.email)
    user, first_time = oidc_core.choose_account(by_subject, by_email)
    created = False
    if user is None:
        if not (mapped and config.OIDC_AUTO_PROVISION and config.OIDC_PROVISION_TENANT):
            raise oidc_core.OidcError("no provisioned account for this identity")
        new_id = admin.create_user(config.OIDC_PROVISION_TENANT, identity.email, None, access[0], access[1])
        user = users.get_by_id(new_id) if new_id else None
        if user is None:
            raise oidc_core.OidcError("could not create the account (email already used elsewhere)")
        first_time = created = True
    if not user.is_active:
        raise oidc_core.OidcError("account is switched off")
    if first_time and not users.link_sso(user.id, config.OIDC_ISSUER, identity.subject):
        raise oidc_core.OidcError("account was linked by someone else")
    if created:
        admin.record(user, "sso.provision", user.email, {"level": access[0], "admin": access[1]})
    elif first_time:
        admin.record(user, "sso.link", user.email)
    if access and (user.level, user.is_admin) != access:
        admin.update_user(user.tenant_id, user.id, {"level": access[0], "is_admin": access[1]})
        admin.record(user, "sso.sync", user.email, {"from": {"level": user.level, "admin": user.is_admin},
                                                    "to": {"level": access[0], "admin": access[1]}})
        user = users.get_by_id(user.id)
    return user
