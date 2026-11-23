# Single sign-on (Microsoft Entra ID)

The portal supports OpenID Connect (authorization code flow with PKCE, state and nonce). The identity provider
proves **who** someone is; the portal's own database still decides **what** they may read. Nobody gets in just by
having a company login: an administrator must have created their account first (people list, "Add person"; leave the
password empty for an SSO-only account).

## Set up with Entra ID

1. Azure portal, Microsoft Entra ID, App registrations, **New registration**. Name it, choose **Single tenant**.
2. Redirect URI (type *Web*): `https://<your-host>/auth/sso/callback` (for local tests `http://127.0.0.1:8000/auth/sso/callback`).
3. Certificates & secrets: create a **client secret**. Copy its value now.
4. Copy the *Application (client) ID* and the *Directory (tenant) ID* from the Overview page.
5. Put these in `.env` (or in the Azure Container App settings / Key Vault references):

```
OIDC_ISSUER=https://login.microsoftonline.com/<tenant-id>/v2.0
OIDC_CLIENT_ID=<application-client-id>
OIDC_CLIENT_SECRET=<secret value>
OIDC_REDIRECT_URI=https://<your-host>/auth/sso/callback
```

6. Restart the server. The sign-in page now shows **Sign in with company SSO**. Set `PASSWORD_LOGIN_ENABLED=false`
   to require SSO for everyone (do that in production; the demo keeps passwords on).

## What is checked on every sign-in

- A random `state` and `nonce` and a PKCE verifier are kept in a short-lived, signed, HTTP-only cookie.
- The ID token's signature (RS256, keys fetched from the provider), issuer, audience, expiry and nonce are verified.
- Use a **single-tenant** issuer. The first time someone signs in, their account is matched by email and then locked to
  the provider's stable subject id (`sub`); after that the email in the token is no longer trusted. This avoids the
  well-known "nOAuth" email-claim takeover.
- A switched-off account cannot sign in. Every sign-in uses the same short-lived session token as password login.

## Let the company directory decide access (group mapping)

By default an administrator sets each person's level in the portal. In a company that is the wrong place for it: people
join, move and leave in the directory, and access should follow. With group mapping the Entra groups decide.

1. App registration, **Token configuration**, **Add groups claim**, choose *Security groups* and *Group ID* for the ID token.
2. Create (or reuse) one security group per reading level and one for portal administrators. Copy their object ids.
3. Set in `.env`:

```
OIDC_GROUP_LEVELS=<analyst-group-id>:1,<manager-group-id>:2,<director-group-id>:3,<partner-group-id>:4
OIDC_ADMIN_GROUP=<portal-admins-group-id>
# Optional: create the account on first sign-in for anyone in a mapped group
OIDC_AUTO_PROVISION=true
OIDC_PROVISION_TENANT=<company id used in the portal, e.g. acme>
```

Rules, all covered by `tests/test_sso_groups.py`:

- On **every** sign-in the person's level and administrator flag are set from their groups. Moving someone to a
  different group changes what they can read the next time they sign in; every change is written to the change history
  (`sso.sync`), as are links (`sso.link`) and created accounts (`sso.provision`).
- The **highest** mapped level wins. The administrator group alone gives level 1: running the portal is not the right
  to read restricted documents.
- **No mapped group, no sign-in.** The portal never invents access.
- A **switched-off** account stays off whatever the groups say.
- **Too many groups:** Entra leaves the group list out of the token for people in more than about 200 groups. The portal
  does not follow the lookup link; it refuses the sign-in (fail closed). Fix by filtering the claim to groups assigned to
  the application (*Groups assigned to the application* in Token configuration).
- Engagement teams (who may see a client's sensitive documents) stay managed in the portal.
- A removed person's existing session lasts until its token expires (`ACCESS_TOKEN_MINUTES`, 60 by default). Lower it
  if you need faster cut-off.

## Not done yet

Automatic **de-provisioning** between sign-ins (SCIM, so a leaver is switched off without waiting for their next
sign-in attempt) and syncing engagement teams from directory groups.
