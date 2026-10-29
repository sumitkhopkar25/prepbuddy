# Architectural decisions

## Isolated PostgreSQL API validation — 2026-10-29

Run local database validation with a uniquely named disposable PostgreSQL +
pgvector container, generated credentials, loopback-only dynamic port, and
temporary storage. Apply the real Alembic migrations and set both database URL
variables only for child commands. Keep the development database and `.env`
independent of this runner. See [automated testing](../docs/database.md#automated-postgresql-and-api-testing).

The automated API flow uses real HTTP, production JWT validation, and committed
PostgreSQL persistence for two generated users. Replace only the external JWKS
transport with generated signing keys; real Auth0 browser login remains a separate
integration check. This permits repeatable backend validation without storing user
tokens or requiring interactive login. Tests clean up their generated rows and the
runner removes its own container after completion or failure.

## Current-candidate retrieval — 2026-10-29

`GET /candidates/me` queries only by the authenticated local user's UUID and returns
the existing candidate response or generic HTTP 404. Retrieve the owned row as
stored, including retained soft-deleted candidates, consistent with the
[retained-candidate ownership invariant](../docs/database.md#candidate-ownership).
This endpoint does not introduce deletion/restoration behavior; that policy remains
planned. The query adds no schema or migration change and follows the existing lazy
session and sanitized HTTP error boundaries. See the
[API contract](../README.md#backend-api) and
[identity boundary](../docs/architecture.md#identity).

## Authenticated candidate creation — 2026-10-24

Implement `POST /candidates` as a synchronous route behind `get_current_user`.
Only the authenticated local user sets ownership. Accept optional trimmed
baseline text (1–200 characters) and non-negative experience matching `NUMERIC(4,1)`;
reject unknown request fields, including owner IDs. Serialize response UUIDs as
strings and experience as a one-decimal-place string or null. See the
[API contract](../README.md#backend-api) and
[identity boundary](../docs/architecture.md#identity).

Keep the `app/candidates` persistence service separate from HTTP error translation.
Load database imports inside protected execution, use a dedicated caller-owned
session, and materialize a detached response before closing it. Let the existing
database constraint enforce the ownership limit, including concurrent attempts:
roll back and translate only PostgreSQL `23505` on `uq_candidates_user_id` to
`CandidateAlreadyExists` and generic HTTP 409. Other persistence/configuration
errors become generic HTTP 503 without exposing or logging exception details.
Use the [existing ownership migration](../docs/database.md#candidate-ownership);
this API milestone adds no schema change. Retrieval and resource authorization
queries remain planned.

## One candidate per user for the MVP — 2026-10-24

A user owns zero or one candidate; each candidate belongs to exactly one user.
The account exists independently of candidate onboarding. Additional CV uploads,
target roles, and profile revisions reuse the same candidate. Profile versions
preserve that person's history. This makes the personal workflow in the
[product scope](../README.md#1-candidate-profile) explicit under the
[identity boundary](../docs/architecture.md#identity); career-coach workflows
remain deferred.

Enforce this in SQLAlchemy and a new Alembic migration with the full
`uq_candidates_user_id` unique constraint, including retained soft-deleted rows.
The migration locks the table, rejects existing duplicates without exposing
identifiers, and preserves all records. Do not modify the initial migration or
automatically merge/delete candidates. See
[database ownership and migration behavior](../docs/database.md#candidate-ownership).

The candidate API contract is: the first creation returns 201;
a second creation returns a generic 409, including concurrent requests rejected
by this specific constraint. Roll back before translating the conflict. Other
integrity/persistence failures remain generic 503 errors. Owner identity always
comes from the authenticated local user. See the
[updated implementation plan](next-step.md).

## Provider-neutral authentication boundary — 2026-09-26

Use an immutable external-subject principal and an asynchronous token-validator
protocol in `app/identity/`, with FastAPI dependency injection for provider adapters.
The default validator fails closed. Missing, malformed, and rejected bearer credentials
return a generic HTTP 401 with `WWW-Authenticate: Bearer`, without exposing credentials.
`GET /me` demonstrates validated subject resolution only; no local user row is implied.
`GET /health` remains public and database-independent. Provider selection, user
persistence, and ownership enforcement remain future work under the
[identity module boundary](../docs/architecture.md#5-backend-module-boundaries) and
[security requirements](../docs/architecture.md#12-security-and-privacy).

## Initial API liveness boundary — 2026-09-21

Expose a FastAPI factory and `app.main:app` with `GET /health` returning a fixed
`{"status": "ok"}` response. This reports process liveness only; database readiness
requires a separate future design with explicit failure and timeout behavior.
Application construction and health requests do not initialize database settings
or sessions. Use base Uvicorn without optional performance/reload extras for this
minimal runtime. This implements the first API boundary in the
[accepted backend milestone](../docs/architecture.md#15-mvp-implementation-order).
See [local API setup](../README.md#backend-api).

## Local database configuration — 2026-09-19

Require `DATABASE_URL` from environment configuration instead of embedding default
credentials in Python. Docker Compose reads `POSTGRES_*` values from `.env` and
publishes PostgreSQL on host loopback only. Keep existing database credentials and
volumes intact. See [database setup](../docs/database.md).

## Accepted MVP architecture

Source: [`docs/architecture.md`](../docs/architecture.md), accepted for MVP and dated
2026-09-12. The following summarizes existing decisions; it does not change them.

- Build a modular monolith with a shared Python codebase for the API and worker.
- Use Next.js, React, TypeScript, and Tailwind for the planned web application.
- Use FastAPI, Pydantic, SQLAlchemy, and Alembic for the backend.
- Store relational data and embeddings in PostgreSQL with pgvector.
- Process slow work through a Redis-backed queue and store uploads in S3-compatible storage.
- Keep scoring and state transitions deterministic; use LLMs for interpretation and explanation.
- Preserve version history and keep active weekly preparation plans locked for seven days.
- Isolate provider choices behind application interfaces.

Refer to the architecture document for rationale, boundaries, and deferred features.

## Repository support structure — 2026-09-12

Add `AGENTS.md`, `.ai/project-state.md`, `.ai/decisions.md`, and
`tools/project_advisor.py` alongside the existing README and architecture document.
Preserve all existing files and directories, as requested by the project owner.

## Repository advisor — 2026-09-12

The `next` command uses the OpenAI Responses API with structured output to produce
one small implementation milestone and its testing plan. Configure the model through
`ADVISOR_MODEL` or `--model`; credentials come from `OPENAI_API_KEY` in the process
environment. The implementation uses the Python standard library. It inspects schema
files rather than live database records and never executes the generated instructions.

## Local advisor configuration — 2026-09-14

Superseding environment-only configuration, use `python-dotenv` to read the
project-root `.env`, which remains ignored by Git. Environment variables take
precedence, followed by `--model` for the model selection. Keep credentials out
of Python source. See [advisor setup](../docs/project-advisor.md).

Use `ADVISOR_MODEL` for advisor model configuration. Keep local configuration in
`.env` only, with setup documented in [database setup](../docs/database.md) and
[advisor setup](../docs/project-advisor.md).

## Persistent local identity with lazy database access — 2026-09-28

Superseding the subject-only `/me` probe, resolve the verified subject to the existing
unique user ownership root. A dedicated session commits new users, rolls back failures,
and re-queries the winner of a unique-subject creation race. Run synchronous persistence
after authentication in a FastAPI dependency, deferring database imports until execution.
Return a detached identity result and sanitize persistence/configuration errors as 503.
This preserves public liveness isolation and implements the
[identity boundary](../docs/architecture.md#5-backend-module-boundaries) using the
[existing schema](../docs/database.md).

## Auth0 user access tokens — 2026-10-05

The user selected Auth0. Keep the provider behind `TokenValidator`; use PyJWT's
RS256 verification against one configured HTTPS issuer and API audience, with a
cached JWKS client (five-minute TTL, five-second timeout, 30-second unknown-key
refresh cooldown). Require exp/iat/iss/aud/sub, reject service-account subjects,
and return only the verified subject to the existing user resolver. Settings load
on verification and blocking work runs in a thread, preserving public liveness.
Invalid credentials return 401; configuration/connectivity failures return 503.

No client secret is needed for API verification. Use Postman's Authorization Code
with PKCE flow and a separate native Auth0 development client for initial live tests;
frontend SDK/session integration remains planned. Local JWT checks cannot immediately
revoke existing access tokens; token expiry bounds that delay. The current subject-only
user key assumes a single trusted issuer and requires a migration plan before switching
tenants or accepting multiple issuers. See [Auth0 setup and boundaries](../docs/authentication.md),
[Auth0 validation guidance](https://auth0.com/docs/secure/tokens/access-tokens/validate-access-tokens),
and the [accepted identity boundary](../docs/architecture.md#5-backend-module-boundaries).
