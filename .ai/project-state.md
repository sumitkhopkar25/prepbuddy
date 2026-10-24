# Project state

Last reviewed: 2026-10-05.

## Present in the repository

- Product scope and behavior: `README.md`.
- Accepted MVP design: `docs/architecture.md`.
- Database documentation: `docs/database.md`.
- Python package and dependencies: `app/` and `pyproject.toml`.
- Database models, configuration, and session support: `app/db/`.
- Alembic configuration and initial schema migration: `alembic.ini` and `alembic/`.
- Database metadata tests: `tests/test_database_metadata.py`.
- FastAPI application factory and ASGI entry point: `app/main.py` (`app.main:app`).
- Database-independent liveness endpoint: `GET /health` returns `200` with
  `{"status": "ok"}`; `POST /health` returns `405`. HTTP tests: `tests/test_health.py`.
- Provider-neutral immutable authenticated principal and injectable bearer-token validator:
  `app/identity/`. `GET /me` returns the resolved local user UUID and verified external subject; the default
  validator uses Auth0 when configured and rejects tokens when unconfigured.
  Invalid credentials return HTTP 401 with `WWW-Authenticate: Bearer`.
  Tests: `tests/test_identity.py` and `tests/test_auth0.py`.
- Auth0 RS256 user-access-token verification: `app/identity/auth0.py`; first-time
  account setup and Postman PKCE testing: `docs/authentication.md`.
- Local service configuration: `compose.yaml` and the Git-ignored `.env`.
- Database credentials are required from environment configuration; Docker's
  PostgreSQL port is published only on host loopback. See `docs/database.md`.

## Planned work

The API skeleton and provider-neutral authentication boundary are implemented.
Auth0 backend verification is implemented; live tenant configuration/testing, frontend
login/session integration, candidate creation and ownership queries, and resource
authorization remain planned. Database readiness checks,
broader backend configuration, the Next.js frontend, background processing, and
preparation workflows also remain planned. Follow the
implementation order in `docs/architecture.md` when selecting the next milestone.

## Identity boundary validation — 2026-09-26

Using the existing Python 3.12 environment, passed 16 focused identity/health tests
and all 30 tests with `python -m pytest -q tests/test_identity.py tests/test_health.py`
and `python -m pytest -q`. `ruff check app tests`, the advisor required-file check,
and `git diff --check` passed. Two upstream test-client deprecation warnings remain.
Commands ran outside the sandbox because its host-mount configuration prevented startup.
A fresh-process test without `DATABASE_URL` or a working-directory `.env` confirmed
public health behavior and absence of database imports. No live provider, database,
or migration was exercised.

Next-plan regeneration was blocked by automatic approval review because it exports
repository context to the configured OpenAI API. The existing plan is preserved.

## Backend validation — 2026-09-21

Using the existing Python 3.12 virtual environment, installed `.[dev]`, passed the
2 focused health tests and all 16 tests, and passed `ruff check app tests`,
`pip check`, and the advisor required-file check. Tests required execution outside
the restricted sandbox because the HTTP test client stalled inside it. The installed
Starlette test client emitted two upstream deprecation warnings concerning HTTPX
and AnyIO; tests still passed.

A temporary loopback Uvicorn server returned GET 200 and POST 405 from a directory
without `.env`, with `DATABASE_URL` removed. A separate import check confirmed that
the ASGI entry point does not import database configuration or session modules.
No live database or migrations were exercised.

Next-plan regeneration was attempted, but network access failed in the sandbox and
automatic approval review rejected the external repository-context export on retry.
The existing `.ai/next-step.md` is preserved pending explicit user authorization.

## Repository support

`AGENTS.md` provides contributor guidance. `.ai/decisions.md` indexes architectural
decisions. `tools/project_advisor.py` checks required files and provides a `next` command that
collects repository context and requests an implementation and testing plan from OpenAI,
saving the validated result to `.ai/next-step.md`. Offline tests cover context collection,
response handling, and preservation of the previous plan on request failure.
See `docs/project-advisor.md` for configuration.

Advisor configuration (2026-09-14): `python-dotenv` reads the root `.env`;
`ADVISOR_MODEL` selects the advisor model; process environment variables and the
model CLI flag can override local values.
See [advisor setup](../docs/project-advisor.md).

## Local-user resolution validation — 2026-09-28

Implemented lookup/create in `app/identity/user_service.py` using caller-owned dedicated
sessions, rollback on database errors, and PostgreSQL unique-subject race recovery.
Authenticated `/me` accesses persistence lazily in a synchronous dependency and returns
`id` and `subject`; persistence/configuration failures return a generic 503. The model
and migration match; no schema changes were needed.

Python 3.12 full suite: 38 passed, one PostgreSQL integration test skipped, two upstream
deprecation warnings. Ruff, advisor required-file checks, and whitespace checks passed.
Commands ran outside the sandbox due to its host-mount startup failure. Docker is
unavailable in this WSL distro; live migration and PostgreSQL validation were not run.
The integration test uses generated subjects and an outer rollback transaction; enable
it with `PREPBUDDY_TEST_DATABASE_URL` pointing to an isolated migrated PostgreSQL database.
Provider integration, candidate creation, and resource authorization remain planned.

Advisor next-plan generation was rejected by automatic approval review because sending
repository context to the external OpenAI API requires explicit authorization. The
existing next-step plan is preserved.

## Auth0 adapter validation — 2026-10-05

Auth0 was selected by the user. Added lazy environment configuration, RS256 signature
verification with PyJWT, exact issuer/API audience checks, required claims and human
subject validation, cached public keys with refresh cooldown and timeout, and generic
401/503 responses. Verification runs in a worker thread. Health remains independent
of provider settings, JWT imports, and database configuration. No persistence changes.

Installed `.[dev]` including `PyJWT[crypto]` in the existing Python 3.12 environment.
Full suite: 76 passed, one opt-in PostgreSQL test skipped, two existing upstream
deprecation warnings. Ruff, `pip check`, advisor required-file checks, and
`git diff --check` passed. Tests ran outside the sandbox because TestClient stalled
inside it; dependency installation also required network access outside the sandbox.
The Auth0 tests use generated RSA signatures and mocked HTTP/persistence boundaries.
No real tenant, live login, or PostgreSQL integration was exercised. The user has not
yet created an Auth0 tenant; `.env` was left intact. Follow `docs/authentication.md`
to create the account and perform a real two-user `/me` check.

Advisor regeneration remains deferred after the earlier automatic approval rejection
of external repository-context export; this turn did not retry that export or replace
the user's existing `.ai/next-step.md`.
