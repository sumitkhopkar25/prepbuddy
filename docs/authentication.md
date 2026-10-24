# Auth0 authentication

PrepBuddy accepts Auth0 **user access tokens** for one configured tenant and API.
`GET /me` validates the token and resolves/creates the local `users` row, returning
`{"id": "<local UUID>", "subject": "<Auth0 user ID>"}`. Passwords stay with Auth0.
The frontend login UI is still planned; use Postman for the first live test.

## 1. Create your Auth0 tenant

Sign up at [Auth0](https://auth0.com/) and create a development tenant. Choose the
appropriate region (for example, EU for your intended European deployment).
Record the tenant domain, such as `dev-example.eu.auth0.com`.

## 2. Register the PrepBuddy API

In the Auth0 dashboard, open **Applications → APIs → Create API**:

| Field | Value |
| --- | --- |
| Name | `PrepBuddy API` |
| Identifier | `https://api.prepbuddy.local` |
| Signing algorithm | `RS256` |

The identifier is a unique audience label; no website needs to exist at that URL.
Keep it distinct from the application's Client ID. Use a user access token for
this API, not an ID token, Management API token, or API dashboard machine token.
`/me` rejects client-credentials tokens because they represent services rather than users.

## 3. Create a development login application

Open **Applications → Applications → Create Application**:

- Name: `PrepBuddy Local Testing`.
- Type: **Native** (Postman is the development desktop client).
- In Settings, add `https://oauth.pstmn.io/v1/browser-callback` to **Allowed Callback URLs**.
- If Postman displays a different callback URL, register that exact URL too.
- Under Advanced Settings, ensure **Authorization Code** is an enabled grant type and
  **Token Endpoint Authentication Method** is `None` for this public client.
- Save and copy its **Client ID**. This development flow needs no client secret.
- On the application's **Connections** tab, enable your email/password database
  connection (often `Username-Password-Authentication`).

Use Auth0's signup screen to create a test account, or create one under
**User Management → Users**. Start with email/password; social login can be enabled
later. Create a second account when testing identity separation.

This development application is separate from the eventual Next.js application,
which will have its own SDK, application type, and callback/logout URLs.

## 4. Configure and start PrepBuddy

Add these entries to the project-root `.env`, keeping all existing settings:

```dotenv
AUTH0_DOMAIN=dev-example.eu.auth0.com
AUTH0_AUDIENCE=https://api.prepbuddy.local
```

Replace the example domain with your actual tenant domain. Do not include `https://`
or a trailing slash in `AUTH0_DOMAIN`. The validator builds the exact issuer as
`https://<AUTH0_DOMAIN>/`. A custom Auth0 domain must match the tokens' issuer.
These two values are public configuration; do not add a client secret for API verification.

From the project root in WSL:

```bash
source .venv/bin/activate
python -m pip install -e '.[dev]'
docker compose up -d postgres
alembic upgrade head
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

See [database setup](database.md) for `DATABASE_URL` and Docker settings.
Restart the API after changing Auth0 configuration; settings and signing keys are cached.

## 5. Sign in and call /me from Postman

In the Postman desktop application, create **GET `http://localhost:8000/me`**.
Select **Authorization → OAuth 2.0**, then configure a new token:

| Field | Value |
| --- | --- |
| Grant type | Authorization Code (With PKCE) |
| Authorize using browser | Enabled |
| Callback URL | The exact callback registered in step 3 |
| Auth URL | `https://<your-domain>/authorize` |
| Access Token URL | `https://<your-domain>/oauth/token` |
| Client ID | The Local Testing application's Client ID |
| Client Secret | Leave empty |
| Code Challenge Method | SHA-256 / S256 |
| Scope | `openid profile email` |
| State | A fresh random value for this login attempt |
| Client Authentication | Send client credentials in body (no secret) |

In **Advanced Options → Auth Request**, add `audience` with value
`https://api.prepbuddy.local` as a query parameter. If that UI is unavailable, use
`https://<your-domain>/authorize?audience=https%3A%2F%2Fapi.prepbuddy.local`
as the Auth URL instead. The audience must exactly match `AUTH0_AUDIENCE`.
Let Postman generate the PKCE verifier. Keep token sharing/sync disabled.

Click **Get New Access Token**, sign in using Auth0's browser page, approve consent
if asked, then select **Use Token** (the access token). Send the `/me` request.
Expected: HTTP 200 with a local UUID and your Auth0 subject. Repeat it: the UUID
should stay the same. Log out of the Auth0 browser session (or add `prompt=login`
to the authorization request) and sign in as the second user: their UUID must differ.
A live `/me` call commits the user to PostgreSQL, so you can inspect it in pgAdmin:

```sql
SELECT id, auth_provider_subject, created_at
FROM users
ORDER BY created_at DESC;
```

## Failure responses and troubleshooting

| Result | Meaning / check |
| --- | --- |
| 401, `Authentication required` | Missing, malformed, expired, or invalid token; verify issuer, audience, RS256, and that it is a user access token |
| 401 with no Auth0 settings | Authentication is deliberately disabled until configured |
| 503, `Authentication service unavailable` | Incomplete/invalid configuration or public-key service unavailable; check domain, HTTPS/network access, and restart after changing settings |
| 503, `Identity service unavailable` | Token was accepted but database resolution failed; check local PostgreSQL and migrations |
| Browser callback mismatch | Register the exact Postman callback in the Auth0 application's Allowed Callback URLs |
| Connection refused | Check Uvicorn is running on port 8000 and Windows can reach the WSL service |

`GET /health` remains public and does not load Auth0 settings or the database.
Provider failures never grant access. Tokens, credentials, and raw exceptions are
not logged or returned by the authentication adapter.

## Automated tests and boundaries

```bash
python -m pytest -q tests/test_auth0.py tests/test_identity.py tests/test_health.py
python -m pytest -q
ruff check app tests
```

Tests generate RSA keys, verify actual JWT signatures, and replace only network
and persistence boundaries. No Auth0 account is needed. They cover different users,
issuer/audience/expiry/required claims, rejected service tokens, signature/algorithm
failures, cached keys and rotation, outages, and configuration. PostgreSQL integration
remains opt-in via `PREPBUDDY_TEST_DATABASE_URL` (see `tests/test_identity_persistence.py`).

The adapter uses PyJWT's cached JWKS client with a five-minute cache, a five-second
network timeout, and its 30-second refresh cooldown for unknown keys. A newly rotated
key may require a retry after that cooldown. Blocking verification runs in a worker
thread. Token URLs never choose the key endpoint; configuration selects one HTTPS issuer.

Local signature verification does not immediately observe logout or account blocking;
an already issued access token may remain valid until expiry. Configure an appropriate
access-token lifetime in Auth0. Fine-grained resource ownership checks, role/scope
policies, immediate revocation, and a production frontend login/session flow remain
future work. The current subject-only ownership key assumes one trusted issuer;
changing tenants requires an explicit identity migration rather than changing the
configured domain against existing accounts.

## References

- [Auth0 access-token validation](https://auth0.com/docs/secure/tokens/access-tokens/validate-access-tokens)
- [Auth0 Authorization Code with PKCE](https://auth0.com/docs/get-started/authentication-and-authorization-flow/authorization-code-flow-with-pkce/call-your-api-using-the-authorization-code-flow-with-pkce)
- [Postman OAuth 2.0 setup](https://learning.postman.com/docs/use/send-requests/authorization/oauth-20/)
- [PyJWT verification and JWKS](https://pyjwt.readthedocs.io/en/stable/usage.html)
