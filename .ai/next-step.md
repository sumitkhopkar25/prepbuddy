# Next implementation step

Generated: 2026-09-28T20:15:35+00:00 | Model: gpt-5.6-terra

## 1. Current project state

## Implemented

- The PostgreSQL schema, SQLAlchemy models, and initial Alembic migration are present (`app/db/models.py`, `alembic/versions/20260830_0001_initial_prepbuddy_schema.py`), although the migration content was omitted from the supplied context because it exceeded the collection limit.
- FastAPI exposes a database-independent `GET /health` endpoint and a protected `GET /me` identity probe (`app/main.py`). The existing health test specifically verifies that importing and calling health does not load database configuration or SQLAlchemy (`tests/test_identity.py`).
- Identity currently validates only an external subject through an injectable `TokenValidator`; the default validator deliberately rejects every token (`app/identity/service.py`, `app/identity/dependencies.py`).
- The `users` table already has a unique `auth_provider_subject` column (`app/db/models.py`), but no code resolves an authenticated principal to a local `User` row. This gap is also explicitly listed as planned work in `.ai/project-state.md`.

## Uncertainty and constraints

- No live database, migration, or current test run was performed for this assessment; prior validation notes in `.ai/project-state.md` are historical evidence only.
- A real authentication-provider adapter remains unimplemented, so this milestone should continue using the existing injectable fake validator in tests rather than selecting a provider.
- The initial migration was not available in the supplied file contents. Confirm that its `users` table matches `app/db/models.py` before relying on an integration test, but no new migration should be needed if it does.

## 2. Next milestone

## Add database-backed local-user resolution for authenticated requests

Make `GET /me` resolve the verified external subject to a persistent `users` row, creating that row on the first authenticated request and returning the local user ID with the verified subject. Keep `GET /health` public and database-independent.

This is a narrow identity/ownership foundation: it creates the local ownership root required before candidate creation, CV ingestion, and candidate-scoped authorization can be safely implemented.

## 3. Reasoning

The accepted implementation order places “Authentication and user/candidate ownership” immediately before document upload and candidate-profile workflows (`docs/architecture.md` §15). The repository has already completed the provider-neutral authentication boundary, but it intentionally stops before local persistence: `AuthenticatedPrincipal` says it “does not imply a local user record exists” (`app/identity/service.py`), and `/me` returns only the subject (`app/main.py`).

The schema is already prepared for this exact step: `User.auth_provider_subject` is non-null and unique (`app/db/models.py`). Implementing resolution/upsert now turns a verified external identity into the durable ownership root needed by every later candidate, document, job, and plan query. It is smaller and more foundational than beginning upload or AI extraction while ownership is still absent.

This should not select an external provider or create candidates yet. Provider selection is explicitly unresolved, and candidate onboarding would broaden the milestone beyond local-user resolution. The implementation must also preserve the current liveness boundary: importing `app.main` and serving `/health` without `DATABASE_URL` must not eagerly import database settings or SQLAlchemy, as covered by `tests/test_identity.py` and recorded in `.ai/decisions.md`.

## 4. Tasks

1. **Confirm the persistence contract without changing the schema.**
   - Inspect `User` in `app/db/models.py` and the initial migration file `alembic/versions/20260830_0001_initial_prepbuddy_schema.py`.
   - Verify that the migration creates `users.auth_provider_subject` as a unique, non-null column compatible with the model.
   - Do not create an Alembic revision unless this inspection reveals a real schema/model mismatch; this milestone should use the existing `users` table.

2. **Implement a small local-user resolver service.**
   - Add a focused identity persistence module, for example `app/identity/user_service.py`.
   - Give it a testable function/service that accepts a verified `AuthenticatedPrincipal` and a caller-supplied SQLAlchemy session, finds `User` by `auth_provider_subject`, and creates then persists a `User` only when no matching row exists.
   - Return the resolved local user object (or a small immutable result containing its UUID and subject).
   - Ensure repeated resolution of the same subject is idempotent: it must return the same user and must not create duplicate rows.
   - Roll back failed writes before propagating or translating database failures. Handle the unique-subject race safely if practical within the small service: on a unique-conflict during first creation, roll back and re-query the existing user.
   - Do not store token text, add provider-specific claims, or infer email/display name; the current principal contract contains only `subject`.

3. **Wire resolution into protected `/me` while preserving liveness isolation.**
   - Update `app/main.py` so a successfully authenticated `GET /me` resolves/creates the local user and returns at least `{"id": "<UUID>", "subject": "<verified-subject>"}`.
   - Defer imports or session construction such that application import and `GET /health` still work when `DATABASE_URL` is absent. In particular, do not import `app.db.config`, `app.db.session`, or SQLAlchemy at `app.main` module-import time.
   - Keep missing, malformed, and rejected bearer credentials as the current generic `401` response with `WWW-Authenticate: Bearer`; authentication must occur before any database resolution.
   - Translate unavailable/unexpected database persistence failures for an otherwise valid principal into a generic `503` response without exposing database URLs, SQL, token values, or exception details.

4. **Add targeted tests.**
   - Update `tests/test_identity.py` for the changed successful `/me` response, using the existing fake validator and an injected/mocked persistence seam so normal identity tests do not need PostgreSQL.
   - Preserve and run the existing fresh-process health/import assertion: `/health` must still succeed with no `DATABASE_URL`, and database modules/SQLAlchemy must remain unloaded until a database-backed protected request is made.
   - Add `tests/test_identity_persistence.py` for resolver behavior. Cover: existing subject returns the existing user without insert; a new subject creates a user; resolving the same subject twice produces one persisted row and stable UUID; and a write/database failure is rolled back and becomes the expected generic API failure when tested at the route boundary.
   - If the project’s local PostgreSQL service is available, make this new test a true database integration test with uniquely generated subjects and explicit cleanup/transaction isolation. It must not depend on or alter real user data.

5. **Validate locally.**
   - Prerequisites: Python 3.12+, a virtual environment, and dependencies installed:
     ```bash
     python -m pip install -e '.[dev]'
     ```
   - Run database-independent focused tests first:
     ```bash
     python -m pytest -q tests/test_health.py tests/test_identity.py
     ```
     Expected result: health remains `200`/`405` as applicable; valid fake authentication resolves the mocked local user; malformed, absent, and rejected tokens remain `401`; no database is required for public health.
   - Start the local database and apply the existing schema before the persistence integration test. Prerequisite: a project-root `.env` containing the non-secret local settings documented in `docs/database.md`.
     ```bash
     docker compose up -d postgres
     alembic upgrade head
     python -m pytest -q tests/test_identity_persistence.py
     ```
     Expected result: the integration test creates/resolves only isolated test users, repeated subject resolution yields one user, and failure-path assertions do not expose internal database details.
   - Run the full suite and lint:
     ```bash
     python -m pytest -q
     ruff check app tests
     python tools/project_advisor.py check
     git diff --check
     ```
     Expected result: all tests selected by the repository pass, Ruff reports no violations, required advisor files are reported `OK`, and whitespace checks are clean. If PostgreSQL is unavailable, report the integration test as unrun rather than treating it as passed.

6. **Update implementation-state documentation after validation.**
   - Update `.ai/project-state.md` to distinguish the implemented local-user resolution from still-planned provider integration, candidate creation, and resource-level ownership authorization.
   - Add a concise decision entry in `.ai/decisions.md` only if the implementation establishes a durable boundary (for example, lazy database access from protected routes to preserve liveness isolation).

## 5. Relevant files

## Existing files to modify

- `app/main.py` — contains `/health` and `/me`; `/me` currently returns only an external subject.
- `app/identity/service.py` — defines `AuthenticatedPrincipal` and provider-neutral contracts.
- `app/identity/dependencies.py` — supplies bearer validation and is the existing authentication seam.
- `app/db/models.py` — defines `User` and its unique `auth_provider_subject` ownership key.
- `app/db/session.py` and `app/db/config.py` — existing database session/configuration code; use carefully so they are not imported during health-only application startup.
- `tests/test_identity.py` — current valid-token, rejected-token, and database-free health/import behavior.
- `tests/test_health.py` — liveness behavior that must remain unchanged.
- `.ai/project-state.md` — must be updated after implementation and validation.
- `.ai/decisions.md` — update only if a new durable implementation decision is made.
- `alembic/versions/20260830_0001_initial_prepbuddy_schema.py` — inspect only to confirm schema parity; its content was truncated from supplied evidence.

## Proposed files

- `app/identity/user_service.py` — focused, database-backed local-user lookup/create logic that accepts an already verified principal and an injected session.
- `tests/test_identity_persistence.py` — targeted persistence and route failure-path coverage, preferably using the local PostgreSQL schema with isolated generated subjects.

## Files not expected to change

- `compose.yaml`, `alembic.ini`, and the Alembic migration should remain unchanged unless migration inspection demonstrates an actual mismatch.
- No authentication-provider adapter, candidate endpoint, frontend, queue, object storage, extraction, or migration should be added in this milestone.

## 6. Coding-agent instructions

Implement only database-backed resolution of a verified external identity to the existing `users` table.

1. Preserve all existing files and public health behavior. `GET /health` must remain unauthenticated, database-independent, and usable with neither `DATABASE_URL` nor a `.env` file.
2. Keep authentication and persistence separated. Continue to use `TokenValidator` for token verification; do not select or integrate Auth0, Clerk, Firebase, or another provider.
3. Add a small persistence service under `app/identity/` that receives a verified `AuthenticatedPrincipal` plus an injected SQLAlchemy session. It should lookup-or-create `User` by `auth_provider_subject`, commit only as needed, roll back on errors, and be idempotent for repeated requests.
4. Change only successful authenticated `/me` behavior to expose the resolved local user UUID alongside the verified subject. Preserve current generic `401` behavior and headers for authentication failures. Map database operational/write failures to a generic `503` without logging or returning credentials, raw SQL, connection strings, or token values.
5. Avoid eager database imports from `app.main`; imports/configuration that require `DATABASE_URL` must occur only on a protected request that needs persistence. Retain or strengthen the existing no-database health/import regression test.
6. Add narrow unit/route tests plus an isolated PostgreSQL-backed persistence test if local database testing is supported. Use generated subjects, clean up test data or rollback test transactions, and never depend on live user records.
7. Do not add a migration unless inspection proves the existing migration lacks the already-modeled `users` contract. If a mismatch is found, stop and report it with the specific model/migration discrepancy rather than silently changing schema scope.
8. Run the validation commands in the task list. Record what actually ran, what was skipped, and any environment limitation in `.ai/project-state.md`; do not state that unrun database tests passed.

## 7. Definition of done

- `GET /me` with a successfully validated principal resolves a row in `users` using the existing unique `auth_provider_subject` field and returns both the stable local UUID and verified subject.
- The first successful request for a new subject creates exactly one local `User`; subsequent requests for that subject return the same UUID and do not add another user.
- Missing, malformed, unsupported-scheme, and rejected credentials still return HTTP `401`, `{"detail": "Authentication required"}`, and `WWW-Authenticate: Bearer`; no database lookup occurs before successful authentication.
- A database failure after valid authentication is handled as a generic HTTP `503` without sensitive connection, SQL, token, or exception content in the response.
- `GET /health` still returns `200` with `{"status": "ok"}` without `DATABASE_URL`; `POST /health` remains `405`; health-only import behavior does not eagerly load database configuration, session code, or SQLAlchemy.
- Tests cover existing-user lookup, new-user creation, repeat-resolution idempotency, authentication-before-persistence, and database failure handling. The PostgreSQL integration test is run only after its documented Docker/migration prerequisites are met and isolates its data.
- `python -m pytest -q`, `ruff check app tests`, `python tools/project_advisor.py check`, and `git diff --check` are executed and their actual outcomes are recorded. This plan does not claim those commands have passed yet.
- `.ai/project-state.md` accurately records local user resolution as implemented only after successful validation, while provider integration, candidate ownership endpoints, and broader authorization remain explicitly planned.
