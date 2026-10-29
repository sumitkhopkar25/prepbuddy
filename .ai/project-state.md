# Project state

Last reviewed: 2026-10-29.

## Present in the repository

- Product scope and behavior: `README.md`.
- Accepted MVP design: `docs/architecture.md`.
- Database documentation: `docs/database.md`.
- Python package and dependencies: `app/` and `pyproject.toml`.
- Database models, configuration, and session support: `app/db/`.
- Alembic configuration and initial schema migration: `alembic.ini` and `alembic/`.
- One-candidate-per-user schema rule: `Candidate` has the
  `uq_candidates_user_id` unique constraint; migration `20261024_0002` adds it
  without changing the initial migration or deleting existing records. Users
  may exist before onboarding. The limit includes retained soft-deleted candidates.
  See `docs/database.md#candidate-ownership`.
- Database metadata tests: `tests/test_database_metadata.py`.
- Candidate ownership checks: `tests/test_candidate_ownership.py`, including
  functional constraint checks and opt-in PostgreSQL migration tests.
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
- Authenticated candidate creation: `POST /candidates` in `app/main.py` and
  `app/candidates/` returns 201 with a detached response. Ownership comes from
  `get_current_user`; optional baseline fields are validated, and client-supplied
  owner IDs/unknown fields are rejected. Only the exact ownership unique violation
  becomes a generic 409 after rollback; other persistence/configuration failures
  become generic 503. Synchronous persistence stays lazy. Tests: `tests/test_candidates.py`.
- Authenticated current-candidate retrieval: `GET /candidates/me` in `app/main.py`
  queries only by the authenticated local user's UUID. It returns the existing
  detached response with HTTP 200, generic 404 for no candidate, and sanitized 503
  for persistence/configuration failures. Retained soft-deleted rows remain
  retrievable; deletion/restoration behavior is still planned. Tests:
  `tests/test_candidate_retrieval.py`, including in-memory SQLite ownership isolation.
- Local service configuration: `compose.yaml` and the Git-ignored `.env`.
- Database credentials are required from environment configuration; Docker's
  PostgreSQL port is published only on host loopback. See `docs/database.md`.
- Disposable PostgreSQL test runner: `tools/test_postgresql.py` and
  `compose.test.yaml` provision an isolated pgvector database, apply migrations,
  enable the PostgreSQL tests, and remove the test container/network afterward.
- Automated backend HTTP flow: `tests/test_api_postgresql.py` runs a real Uvicorn
  server with production JWT validation and committed PostgreSQL persistence.
  Only the external JWKS transport is replaced with generated signing keys.
  Two users exercise onboarding, retrieval, validation, and ownership isolation.

## Planned work

The API skeleton and provider-neutral authentication boundary are implemented.
Auth0 backend verification, authenticated candidate creation, and current-candidate
retrieval are implemented.
Live tenant configuration/testing, frontend login/session integration, candidate
listing, ownership queries for other existing resources, CV ingestion, profile
extraction, target-role selection, and resource authorization remain planned.
Database readiness checks,
broader backend configuration, the Next.js frontend, background processing, and
preparation workflows also remain planned. Follow the
implementation order in `docs/architecture.md` when selecting the next milestone.

## PostgreSQL and API flow validation — 2026-10-29

The user enabled Docker Desktop integration for this WSL distro. Docker is now
available; sandbox access to its socket still requires execution outside the
sandbox. Added a one-command runner with per-run generated credentials, a unique
Compose project, loopback dynamic port, and temporary PostgreSQL storage. Child
processes receive test-only database URLs; development `.env` and volumes remain
unchanged. Contributor guidance now requests this runner for persistence/API work.

Validation:

- `.venv/bin/python tools/test_postgresql.py` passed outside the sandbox:
  **142 passed, zero skipped**, with the two existing Starlette/AnyIO warnings.
  A fresh PostgreSQL 16 + pgvector database successfully applied migrations
  `20260830_0001` and `20261024_0002`. All previously skipped PostgreSQL checks ran.
  Docker confirmed removal of the test container and its network after the run.
- The new HTTP test verified missing/expired authentication, stable local-user
  resolution, 404 before onboarding, rejected client ownership, 201 creation,
  200 retrieval, 409 duplicate rejection, two-user isolation, and committed rows
  visible from independent database sessions. It removed its generated rows.
- `.venv/bin/python -m pytest -q tests/test_postgresql_runner.py`: 6 passed.
  These tests cover test-only URL selection, cleanup after startup/migration/test
  failures, cleanup failure reporting, secret redaction, and unavailable Docker.
- `.venv/bin/ruff check app tests alembic tools`,
  `.venv/bin/python tools/project_advisor.py`, advisor `next --dry-run`, and
  `git diff --check` passed. The runner's six checks also passed after improving
  the cleanup retry command; the database/API implementation was unchanged.

This is an automated end-to-end test of the implemented backend with a substituted
Auth0 signing-key transport. It does not perform a real Auth0 browser login or test
a frontend. See [database testing](../docs/database.md#automated-postgresql-and-api-testing)
for the repeatable command and existing isolated database configuration.

## Current-candidate retrieval validation — 2026-10-29

Implemented `GET /candidates/me` in `app/main.py` and `app/candidates/`. The service
queries by authenticated ownership, raises `CandidateNotFound` for an absent row,
and rolls back SQLAlchemy failures. The HTTP boundary lazily opens a dedicated
session, materializes `CandidateResponse` before closure, and maps intentional
absence to generic 404 and unexpected persistence/configuration errors to generic
503. Authentication and identity resolution retain their existing 401/503 behavior.
No models or migrations changed. Retained soft-deleted rows are retrievable; see
the [retrieval decision](decisions.md#current-candidate-retrieval--2026-10-29).

Validation using the existing Python 3.12 virtual environment:

- `timeout 45s .venv/bin/python -m pytest -q tests/test_candidate_retrieval.py tests/test_candidates.py tests/test_identity.py tests/test_health.py`
  timed out in the sandbox with no output, consistent with prior TestClient stalls.
- `timeout 60s .venv/bin/python -m pytest -q tests/test_candidate_retrieval.py tests/test_candidates.py tests/test_identity.py tests/test_health.py`
  passed outside the sandbox: 66 passed, 2 PostgreSQL tests skipped.
- `timeout 60s .venv/bin/python -m pytest -q` passed outside the sandbox:
  127 passed, 8 PostgreSQL tests skipped. Both successful test runs reported the
  two existing Starlette/AnyIO deprecation warnings.
- `.venv/bin/ruff check app tests alembic tools` passed after correcting three
  lint findings in the new test file.
- `.venv/bin/python tools/project_advisor.py`,
  `.venv/bin/python tools/project_advisor.py check`,
  `.venv/bin/python tools/project_advisor.py next --dry-run`, and
  `git diff --check` passed.

The 15 new retrieval checks cover serialized response fields, authenticated UUID
propagation, ignored client-selected ownership, missing onboarding, authentication
and identity failures, configuration/session/query/serialization error sanitization,
rollback, and session closure. In-memory SQLite checks execute the real service
query for two candidate owners and a third user without a candidate, including
retained soft-deleted rows. The existing fresh-process health test still verifies
database/provider import isolation.

`PREPBUDDY_TEST_DATABASE_URL` was unset, so no live PostgreSQL or Auth0 validation
was performed. README and architecture now reflect retrieval. The existing
next-step brief is preserved and marked complete; advisor context was checked
offline without an external plan-regeneration request.

## Candidate creation validation — 2026-10-24

Implemented the authenticated creation milestone in `app/candidates/` and
`app/main.py`. Requests reject unknown fields and owner IDs, trim optional text,
and validate experience against `NUMERIC(4,1)`. Responses contain UUID strings
and experience as a one-decimal-place string or null. The synchronous route uses
a dedicated session, commits successful creation, rolls back database failures,
and materializes its response before session closure. Only PostgreSQL `23505`
on `uq_candidates_user_id` becomes a generic 409; other persistence/configuration
errors become generic 503. No schema or authentication changes were needed.

Using the existing Python 3.12 virtual environment:

- `.venv/bin/python -m pytest -q tests/test_candidates.py tests/test_candidate_ownership.py tests/test_identity.py tests/test_health.py`:
  54 passed, 7 PostgreSQL checks skipped, two existing upstream warnings.
- `.venv/bin/python -m pytest -q`: 112 passed, 8 PostgreSQL checks skipped, two
  existing upstream warnings. Both pytest commands ran outside the sandbox with
  a 60-second timeout because of the previously confirmed test-client stall.
- `.venv/bin/ruff check app tests alembic tools`,
  `.venv/bin/python tools/project_advisor.py check`, advisor `next --dry-run`,
  and `git diff --check` passed.

Tests cover response data, authenticated ownership, blank/oversized input,
invalid experience, rejected owner/extra fields, authentication failures,
generic errors without private details in responses/logs, the exact duplicate
constraint race path, rollback, and dedicated-session cleanup. The existing
fresh-process health test confirms that application import and `/health` still
avoid database, SQLAlchemy, Auth0, and JWT imports without database configuration.

Two new opt-in PostgreSQL service cases cover persisted creation and duplicate
rejection before/after soft deletion, using generated identities and an outer
rollback transaction. They were skipped because `PREPBUDDY_TEST_DATABASE_URL`
is unset. No live database, migration, Auth0 login, or concurrent PostgreSQL test
was exercised; the race error path was simulated with the exact PostgreSQL error
metadata. Apply the existing ownership migration before using this API.

README and architecture now describe the implemented API. `.ai/next-step.md` is
marked complete and preserves the implementation brief. No external advisor
regeneration was performed; retrieval, existing-resource authorization, CV
ingestion, extraction, and target-role workflows remain planned.

## Candidate ownership validation — 2026-10-24

Resolved the MVP relationship as zero or one candidate per user, with exactly one
user per candidate. The SQLAlchemy model and new `20261024_0002` migration enforce
the limit across retained soft-deleted records too. The migration checks for
duplicate owners under a table lock and refuses to proceed without changing
records if duplicates exist. The initial migration is unchanged. README,
architecture, database guidance, decisions, and `.ai/next-step.md` now agree.
At that checkpoint candidate creation remained planned: first creation returns 201; duplicate or
concurrent creation rejected by this unique constraint returns a generic 409.

Using the existing Python 3.12 virtual environment:

- `.venv/bin/python -m pytest -q tests/test_candidate_ownership.py tests/test_database_metadata.py`:
  6 passed, 5 PostgreSQL migration checks skipped. SQLite functional checks cover
  accounts before onboarding, independent owners, and duplicate rejection both
  before and after soft deletion.
- `.venv/bin/python -m pytest -q`: 79 passed, 6 PostgreSQL checks skipped, two
  existing upstream deprecation warnings. The sandbox run stalled and was
  interrupted; the complete suite passed outside the sandbox.
- `.venv/bin/ruff check app tests alembic tools`, the advisor required-file check,
  advisor `next --dry-run`, and `git diff --check` passed.
- Alembic generated PostgreSQL SQL for the full upgrade, the incremental upgrade,
  and the new migration's downgrade. There is one head, `20261024_0002`.

No live PostgreSQL migration or duplicate-data audit was performed.
`PREPBUDDY_TEST_DATABASE_URL` is unset, the localhost PostgreSQL probe received no
response, and Docker is unavailable in this WSL distro. The five new PostgreSQL
migration tests use a temporary table and rollback, covering upgrade preservation,
duplicate preflight refusal (including soft-deleted rows), and downgrade behavior.
They do not migrate an existing application's schema. Apply `alembic upgrade head`
when the target database is available. The next-step plan was reconciled locally;
no external advisor regeneration was performed.

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
