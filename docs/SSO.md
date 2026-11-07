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

## Not done yet

Group-to-level mapping (for example an Entra group "Directors" becoming level 3) and automatic account creation
(SCIM) are the next steps. Today an administrator sets each person's level in the Administration tab.
