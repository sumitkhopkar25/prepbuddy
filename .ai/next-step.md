# Next implementation step

Generated: 2026-09-21T21:46:52+00:00 | Model: gpt-5.6-terra

## 1. Current project state

## Implemented

- The repository has an accepted MVP architecture, including an explicit implementation order, in [`docs/architecture.md`](docs/architecture.md#15-mvp-implementation-order).
- The PostgreSQL schema is represented in SQLAlchemy models under [`app/db/models.py`](app/db/models.py), with `users`, `candidates`, and ownership foreign keys already modeled. Alembic configuration and an initial migration exist, although the migration source was omitted from supplied context because it exceeds the context limit.
- The FastAPI skeleton is implemented in [`app/main.py`](app/main.py). It exposes only `GET /health`, deliberately without database initialization; its behavior is covered by [`tests/test_health.py`](tests/test_health.py).
- Database metadata constraints are tested without a live database in [`tests/test_database_metadata.py`](tests/test_database_metadata.py).
- [`README.md`](README.md#backend-api) and [`.ai/project-state.md`](.ai/project-state.md) report that health tests, the full test suite, Ruff, and dependency checks passed during a prior local validation. This is historical repository evidence, not validation performed for this recommendation.

## Not implemented

No authenticated API request boundary, external-identity mapping, candidate ownership enforcement, document-ingestion endpoint, or candidate workflow endpoint exists. This matches the stated planned work in [`.ai/project-state.md`](.ai/project-state.md) and the architecture’s next implementation step after the skeleton.

## Uncertainty and constraints

The accepted architecture requires an external authentication provider behind an application interface but intentionally does not choose a provider ([`docs/architecture.md`](docs/architecture.md#4-finalized-technology-choices)). Therefore, this milestone should establish a provider-neutral authentication contract rather than integrate a real identity vendor or accept an insecure development header as production authentication. Database evidence is limited to models, documentation, and the existence of a migration; no live database, migration application, or test execution has occurred for this recommendation.

## 2. Next milestone

## Add a provider-neutral authenticated-principal boundary to FastAPI

Create a small `identity` module that defines the authenticated principal contract and a FastAPI dependency for resolving the current user. Require authentication by default for a minimal protected probe endpoint, while keeping `/health` public and database-independent.

The milestone should **not** select or integrate a real authentication vendor, create user records, add candidate APIs, or implement authorization queries yet. Its deliverable is the secure, testable API boundary that later user/candidate endpoints will use for ownership scoping.

## 3. Reasoning

[`docs/architecture.md`](docs/architecture.md#15-mvp-implementation-order) places “Authentication and user/candidate ownership” immediately after the completed backend skeleton. It also requires every query to be scoped to an authenticated user ([`docs/architecture.md`](docs/architecture.md#12-security-and-privacy)). The schema already anticipates this boundary through `User.auth_provider_subject` and `Candidate.user_id` in [`app/db/models.py`](app/db/models.py).

Adding ingestion or candidate endpoints before a consistent authenticated-principal dependency would create an API surface that cannot safely enforce the ownership model. Conversely, implementing a real provider integration now is underdetermined because no provider is selected. A narrow provider-neutral contract lets the application make secure default behavior explicit: missing or invalid credentials receive `401`, protected handlers receive a typed principal, and liveness remains available without configuration or database access.

This is a prerequisite-focused implementation step rather than a broad identity system, and it preserves the existing decision that health checks must not import or initialize database configuration ([`.ai/decisions.md`](.ai/decisions.md)).

## 4. Tasks

1. **Inspect and preserve the existing API liveness boundary.**
   - Review [`app/main.py`](app/main.py) and [`tests/test_health.py`](tests/test_health.py) before editing.
   - Keep `create_app()`, `app = create_app()`, and `GET /health` behavior unchanged: `200 {"status": "ok"}` without database settings, sessions, or authentication configuration.

2. **Add a small provider-neutral identity contract.**
   - Create `app/identity/__init__.py` and `app/identity/service.py` (or equivalently named, focused modules).
   - Define an immutable typed authenticated-principal value containing at least `subject: str`, corresponding to the existing `users.auth_provider_subject` column in [`app/db/models.py`](app/db/models.py).
   - Define a narrow protocol/abstract interface for validating a bearer token and returning that principal. Keep token parsing and identity-provider behavior behind this interface.
   - Define explicit authentication-domain errors for absent credentials and invalid credentials. Do not import `app.db.config`, `app.db.session`, or SQLAlchemy in these identity-contract modules.

3. **Implement FastAPI authentication dependencies and a temporary deterministic test adapter.**
   - Create `app/identity/dependencies.py` with a FastAPI dependency that reads the standard `Authorization: Bearer <token>` header and returns the typed principal through the validator interface.
   - Missing header, a non-Bearer scheme, an empty Bearer token, and rejected token values must produce HTTP `401` with a `WWW-Authenticate: Bearer` response header. Do not reveal token contents in response details or logs.
   - Make validator selection injectable through FastAPI dependency overrides or application state so HTTP tests can supply a deterministic fake validator. Do not use a trust-based identity header or hard-coded production token.
   - Until a real provider is chosen, the default runtime validator must fail closed: requests to protected endpoints return `401` rather than silently accepting an identity. Document this temporary behavior in code comments/docstrings only where needed.

4. **Expose one protected probe endpoint without adding persistence.**
   - Add `GET /me` (or `GET /identity/me`) in [`app/main.py`](app/main.py), protected by the current-principal dependency.
   - On successful validation, return only the authenticated subject, for example `{"subject": "provider-user-123"}`. This verifies dependency wiring without prematurely claiming that a local `users` database row has been resolved.
   - Do not change `/health`, add database calls, or make the application require `.env` merely to start.

5. **Add focused HTTP and unit tests.**
   - Add `tests/test_identity.py` for contract/dependency behavior and extend [`tests/test_health.py`](tests/test_health.py) only if needed to explicitly protect the existing public-liveness guarantee.
   - Test the happy path with an overridden fake validator: `GET /me` plus a valid Bearer token returns `200` and the expected subject.
   - Test relevant failure cases: no `Authorization` header, malformed/non-Bearer authorization value, blank Bearer token, and a validator-rejected token. Each must return `401` and `WWW-Authenticate: Bearer`.
   - Test that the default validator fails closed, so `GET /me` cannot return a successful identity without a configured real adapter or an explicit test override.
   - Retain the existing `GET /health == 200` and `POST /health == 405` checks.

6. **Update implementation-status documentation after code changes.**
   - Update [`.ai/project-state.md`](.ai/project-state.md) to state precisely that a provider-neutral authenticated-principal boundary and protected probe endpoint exist, while external provider integration, user persistence/upsert, candidate ownership queries, and authorization on resource endpoints remain planned.
   - Add a concise entry to [`.ai/decisions.md`](.ai/decisions.md) recording the fail-closed, provider-neutral boundary and the continued public/database-independent health endpoint.

7. **Validate locally; do not claim success unless commands are actually run.**
   - Prerequisites: Python 3.12+, an activated virtual environment, and project dependencies installed with:
     ```bash
     python -m pip install -e '.[dev]'
     ```
     No `.env`, PostgreSQL instance, Docker service, or Alembic migration should be required for these tests.
   - Run focused tests:
     ```bash
     python -m pytest -q tests/test_identity.py tests/test_health.py
     ```
     Expected result: all selected tests pass; valid overridden authentication reaches `/me`; missing, malformed, blank, invalid, and default-unconfigured authentication attempts return `401`; health behavior remains `200`/`405`.
   - Run the full current test suite:
     ```bash
     python -m pytest -q
     ```
     Expected result: all tests pass, including existing metadata and project-advisor tests.
   - Run linting:
     ```bash
     ruff check app tests
     ```
     Expected result: no Ruff violations.
   - Optionally verify process behavior without database configuration:
     ```bash
     env -u DATABASE_URL python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
     ```
     In another terminal, expected results are `curl -i http://127.0.0.1:8000/health` returning HTTP 200 and `curl -i http://127.0.0.1:8000/me` returning HTTP 401 with `WWW-Authenticate: Bearer`. Stop Uvicorn afterward. This is not a database readiness or migration test.

## 5. Relevant files

## Existing files to modify

- [`app/main.py`](app/main.py) — retain the existing app factory and public liveness endpoint; register one protected identity probe endpoint.
- [`tests/test_health.py`](tests/test_health.py) — preserve existing assertions and, if useful, make the no-auth/no-database liveness boundary explicit.
- [`.ai/project-state.md`](.ai/project-state.md) — record the newly implemented boundary without overstating provider or persistence support.
- [`.ai/decisions.md`](.ai/decisions.md) — record the provider-neutral, fail-closed authentication decision.

## Existing files to consult, not change unless a concrete need arises

- [`docs/architecture.md`](docs/architecture.md) — identity boundary, ownership, privacy, and implementation order.
- [`app/db/models.py`](app/db/models.py) — `User.auth_provider_subject` and candidate ownership structure; do not use database access in this milestone.
- [`pyproject.toml`](pyproject.toml) — FastAPI and test dependencies already available.
- [`README.md`](README.md) — current API behavior documentation; update only if the protected probe is intended as user-facing local API documentation.

## Proposed new files

- `app/identity/__init__.py` — identity package marker and intentionally small public exports.
- `app/identity/service.py` — typed principal, validator protocol, and domain errors.
- `app/identity/dependencies.py` — Bearer parsing, fail-closed default adapter, and FastAPI dependency wiring.
- `tests/test_identity.py` — focused unit/HTTP tests for authentication behavior.

No Alembic migration or database-model change is proposed because the existing schema already contains the provider subject and this milestone must not persist or query identities.

## 6. Coding-agent instructions

Implement only the provider-neutral authenticated-principal boundary described above. Preserve all existing files and public health behavior.

1. Start by reading `AGENTS.md`, `docs/architecture.md`, `app/main.py`, and the existing health tests.
2. Keep the identity package independent of `app.db.config` and `app.db.session`. In particular, importing `app.main` with `DATABASE_URL` absent must continue to work.
3. Use standard HTTP Bearer semantics. Authentication must fail closed by default; never add a production fallback that derives identity from an unverified request header, a hard-coded token, or a query parameter.
4. Keep the identity-provider abstraction minimal and injectable. A fake validator belongs in tests, not as an accepted runtime authentication path.
5. Add exactly one protected probe route to demonstrate the contract. Do not implement user creation, database user lookup, candidate endpoints, authorization repositories, external OAuth/OIDC/JWT verification, migrations, queues, or frontend work.
6. Ensure error responses expose no supplied token and include `WWW-Authenticate: Bearer` for every `401` authentication failure.
7. Write focused tests for successful injected validation and all listed rejection cases, then run the focused suite, full suite, and Ruff commands from the task list. Report commands actually run and their results, including any environmental limitation; do not claim validation passed if it was not executed.
8. Update `.ai/project-state.md` and `.ai/decisions.md` only after implementation, accurately distinguishing this boundary from the still-unimplemented provider integration and ownership persistence.

## 7. Definition of done

- A typed authenticated-principal contract and a narrow provider-validator interface exist under `app/identity/`.
- `GET /me` (or the chosen documented equivalent) depends on Bearer authentication and returns the validated principal subject only when an injected validator accepts the token.
- Without an explicit validator override/configuration, protected requests fail closed with HTTP `401`; they never infer an identity from an untrusted header.
- Missing credentials, non-Bearer credentials, blank Bearer credentials, and rejected tokens return HTTP `401` with `WWW-Authenticate: Bearer` and do not expose the token value.
- `GET /health` remains public and returns `200 {"status":"ok"}`; `POST /health` remains `405`; application import and liveness testing do not require `DATABASE_URL` or a database connection.
- Focused tests in `tests/test_identity.py` cover the accepted-token path and each relevant authentication failure path, while existing health tests remain present.
- `.ai/project-state.md` and `.ai/decisions.md` accurately describe the implemented fail-closed contract and explicitly leave provider integration, database user resolution, and candidate ownership enforcement as future work.
- The coding agent has run `python -m pytest -q tests/test_identity.py tests/test_health.py`, `python -m pytest -q`, and `ruff check app tests`, with actual results reported. These validations are required acceptance checks; they have not been run as part of this recommendation.
