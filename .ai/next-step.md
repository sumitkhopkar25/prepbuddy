# Next implementation step

Generated: 2026-09-19T09:38:52+00:00 | Model: gpt-5.6-terra

## 1. Current project state

## Implemented

- The repository has a PostgreSQL/SQLAlchemy foundation: database configuration and session setup are in `app/db/config.py` and `app/db/session.py`; the full ORM metadata is in `app/db/models.py`; Alembic is configured in `alembic/env.py`; and metadata constraints are covered by `tests/test_database_metadata.py`.
- The accepted MVP architecture specifies FastAPI as the backend and explicitly places “Backend application skeleton, configuration, and health checks” immediately after database/migrations in its implementation order (`docs/architecture.md`, sections 4 and 15).
- The root package currently contains only `app/__init__.py` and `app/db/`; there is no FastAPI application factory, API route, or backend runtime entry point in the supplied tree.
- `pyproject.toml` contains database dependencies and test/lint tooling, but does not list `fastapi`, an ASGI server, or an HTTP test client explicitly.

## Uncertainty and constraints

- No tests, migrations, Docker services, or live database queries have been run; database evidence is limited to the supplied models, documentation, and migration history.
- The initial migration file was omitted from supplied contents because it exceeds the context limit, so its exact generated schema cannot be independently compared here.
- Git status shows unrelated uncommitted documentation/advisor changes and a deleted `.env.example`; this milestone should not alter or restore those files unless separately requested.

## 2. Next milestone

## Add a minimal FastAPI application skeleton with a database-independent health endpoint

Create an importable FastAPI application exposed as `app.main:app`, with `GET /health` returning a stable JSON readiness response. Add focused HTTP tests that verify the successful response and that unsupported methods are rejected.

This creates the first runnable backend product boundary without prematurely implementing authentication, persistence writes, document ingestion, or background workers.

## 3. Reasoning

The database schema is already the only substantive product implementation, while the planned API does not yet exist. A small FastAPI entry point and health endpoint is the highest-value next step because it makes the selected backend stack executable and establishes a testable seam for later identity, ingestion, and profile modules.

The endpoint should deliberately avoid opening a database connection. `app/db/session.py` currently creates an engine at import time, and health checks must remain usable for process/liveness diagnostics even when PostgreSQL is unavailable. Database connectivity/readiness can be added later as a separately designed check with explicit timeout and failure semantics.

This is directly aligned with the accepted implementation order in `docs/architecture.md` while keeping scope below the next larger milestones—authentication and document upload.

## 4. Tasks

1. **Add the minimal runtime dependencies.**
   - Update `pyproject.toml` production dependencies with bounded compatible versions of FastAPI and Uvicorn (for example, `fastapi>=0.115,<1` and `uvicorn[standard]>=0.30,<1`).
   - Add `httpx` to the `dev` optional dependencies if required by the chosen FastAPI/Starlette test-client version.
   - Do not add Redis, object-storage, authentication, queue, or AI-provider dependencies.

2. **Create the application entry point.**
   - Add `app/main.py` containing a small `create_app()` factory and module-level `app = create_app()` for ASGI discovery.
   - Configure a `FastAPI` instance with a concise service title/version appropriate to the existing package metadata.
   - Register `GET /health` to return a deterministic JSON body such as `{"status": "ok"}` with HTTP 200.
   - Do not import `app.db.session`, create tables, run migrations, connect to PostgreSQL, or expose configuration/secrets from the health handler.

3. **Add focused endpoint tests.**
   - Add `tests/test_health.py` using FastAPI/Starlette’s test client against the application factory or module-level app.
   - Happy path: assert `GET /health` returns HTTP 200 and exactly the documented stable JSON payload.
   - Relevant failure case: assert an unsupported request method such as `POST /health` returns HTTP 405. This confirms the route is read-only rather than silently accepting invalid health-check traffic.

4. **Validate locally.**
   - Prerequisite: Python 3.12 or newer and a virtual environment. Install the editable project and development extras:
     ```bash
     python -m pip install -e '.[dev]'
     ```
   - Run the focused tests:
     ```bash
     python -m pytest -q tests/test_health.py
     ```
     Expected result: both the 200 health-response test and the 405 unsupported-method test pass. No PostgreSQL or `.env` setup should be required.
   - Run the full currently configured test suite:
     ```bash
     python -m pytest -q
     ```
     Expected result: the new health tests and existing metadata/advisor tests pass.
   - Lint changed application and test code:
     ```bash
     ruff check app tests
     ```
     Expected result: no Ruff violations.
   - Manual ASGI smoke test, after installing dependencies, in one terminal:
     ```bash
     python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
     ```
     In a second terminal:
     ```bash
     curl -i http://127.0.0.1:8000/health
     curl -i -X POST http://127.0.0.1:8000/health
     ```
     Expected results: the first command returns `200 OK` with `{"status":"ok"}` (JSON spacing may vary); the second returns `405 Method Not Allowed`. Stop Uvicorn after the smoke test.

5. **Record implementation state only if the repository convention requires it.**
   - Update `.ai/project-state.md` narrowly to say that the FastAPI skeleton and health endpoint now exist, but only after implementation and validation have been performed.
   - Do not claim database connectivity, authentication, upload handling, or background processing exists.

## 5. Relevant files

## Existing files to modify

- `pyproject.toml` — add only the minimum FastAPI/ASGI runtime and test-client dependency support.
- `app/__init__.py` — preserve unchanged unless a minimal package-level adjustment is genuinely necessary; it is not expected to need one.
- `tests/test_database_metadata.py` — preserve unchanged; it protects the completed database metadata foundation.
- `.ai/project-state.md` — optionally update after implementation to distinguish the new API skeleton from still-planned workflows.

## Existing files to consult, not modify for this milestone

- `docs/architecture.md` — source for the FastAPI choice and implementation order.
- `app/db/config.py` and `app/db/session.py` — confirm that the initial health endpoint must not depend on database engine/session initialization.
- `AGENTS.md` — contributor validation and file-preservation guidance.

## Proposed new files

- `app/main.py` — FastAPI application factory, module-level ASGI application, and `GET /health` route.
- `tests/test_health.py` — HTTP-level tests for the health endpoint’s success and unsupported-method behavior.

## Files explicitly out of scope

- `alembic/`, `app/db/models.py`, and database migrations.
- Any authentication, document upload, extraction, queue/worker, Redis, S3, LLM, or frontend files.
- The deleted `.env.example` and unrelated uncommitted advisor/documentation changes shown in Git status.

## 6. Coding-agent instructions

Implement only a minimal, runnable FastAPI health-check boundary.

1. Read `AGENTS.md`, `docs/architecture.md`, and `pyproject.toml` before editing.
2. Preserve all existing database code, migrations, tests, documentation, and unrelated working-tree changes. Do not modify the deleted `.env.example` as part of this task.
3. Add minimal bounded dependencies needed to run FastAPI under Uvicorn and test its routes. Keep provider, queue, database-health, and authentication dependencies out of scope.
4. Create `app/main.py` with `create_app()` and `app = create_app()` so both application-factory testing and `uvicorn app.main:app` work.
5. Implement only `GET /health`, returning a fixed, non-sensitive `{"status": "ok"}` JSON response. Do not import the database session/engine, run migrations, make network calls, or read/return environment configuration in this endpoint.
6. Add `tests/test_health.py` covering a successful GET and rejected POST request. Keep tests hermetic: they must not need Docker, PostgreSQL, credentials, or `.env`.
7. Run the focused tests, full test suite, and Ruff commands listed in the task section. If dependencies cannot be installed or validation cannot run, report the exact command, failure, and reason rather than asserting success.
8. If updating `.ai/project-state.md`, describe only code actually added and validation actually performed; do not mark later architecture stages complete.

## 7. Definition of done

- `app.main` is importable and exposes a module-level ASGI application named `app`.
- `create_app()` constructs the FastAPI application without requiring a database connection, Docker, credentials, or a populated `.env` file.
- `GET /health` returns HTTP 200 and the stable JSON payload `{"status": "ok"}`.
- `POST /health` returns HTTP 405, demonstrating that the health route accepts only its intended read method.
- Focused HTTP tests exist in `tests/test_health.py` and cover both behaviors.
- `pyproject.toml` declares the minimum required runtime/testing dependencies with bounded versions compatible with the project’s Python 3.12 target.
- The coding agent has attempted and reported results for:
  ```bash
  python -m pytest -q tests/test_health.py
  python -m pytest -q
  ruff check app tests
  ```
- No database models, Alembic migration, or unrelated working-tree files are changed by this milestone.

These are acceptance criteria and required validation outcomes; they have not been executed or verified from the supplied repository evidence.
