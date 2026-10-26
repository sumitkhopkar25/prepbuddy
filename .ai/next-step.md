# Next implementation step

Generated: 2026-10-24T08:24:39+00:00 | Model: gpt-5.6-terra

Reconciled locally: 2026-10-24. The user approved one candidate per user for the
MVP. This revision incorporates that decision and the new ownership migration;
it was not regenerated through the advisor API.

Implementation status: **completed on 2026-10-24**. `POST /candidates`, baseline
validation, authenticated ownership, duplicate/race handling, and tests are now
implemented. The tasks below are the completed implementation brief. See
`.ai/project-state.md` for validation results and remaining work; a new milestone
has not been generated through the advisor API.

## 1. Current project state

PrepBuddy has a FastAPI application with a database-independent `GET /health` endpoint (`app/main.py`) and an authenticated `GET /me` endpoint that verifies Auth0 RS256 access tokens, resolves/creates a local `users` record, and returns its local UUID plus verified subject (`app/identity/auth0.py`, `app/identity/dependencies.py`, `app/identity/user_service.py`).

The schema contains the ownership root needed for onboarding: `candidates.user_id` is a required foreign key to `users.id`, with the `uq_candidates_user_id` unique constraint in `app/db/models.py` and migration `alembic/versions/20261024_0002_one_candidate_per_user.py`. A user owns zero or one candidate; optional baseline fields remain nullable. `app/candidates/` and `POST /candidates` now implement authenticated creation. Retrieval/listing and candidate-scoped authorization queries for existing resources remain planned, as recorded in `.ai/project-state.md`.

The original advisory response did not execute tests, migrations, or live Auth0/database checks, and its context omitted the initial migration. The ownership rule and candidate API have since been implemented locally. See `.ai/project-state.md` for actual validation and checks that remain unavailable.

## 2. Next milestone

Completed milestone: an authenticated **candidate creation endpoint**. The first `POST /candidates` creates a `Candidate` owned by the verified local user and returns HTTP 201 with the new candidate’s identifiers and supplied baseline fields. A second creation returns a generic HTTP 409 Conflict, including a concurrent request rejected by `uq_candidates_user_id`.

This is deliberately limited to creating the ownership root required before CV ingestion, target-role selection, and all candidate-scoped product workflows. Do not add document upload, profile extraction, target roles, a dashboard, or multi-candidate listing in this milestone.

## 3. Reasoning

The product’s CV-first workflow cannot begin until an authenticated user has a candidate record to own source documents, profiles, jobs, clusters, and plans. The database model already supports this directly through `Candidate.user_id` (`app/db/models.py`), while `/me` establishes only the `User` identity root (`app/main.py`, `app/identity/user_service.py`).

A small authenticated write endpoint is higher-value than further authentication planning because it turns identity into a usable product boundary and establishes the ownership link mandated by the architecture’s Identity module (`docs/architecture.md` §§5 and 12). The ownership constraint is now defined in the model and migration; this endpoint milestone needs no further schema changes. `candidates` already includes `name`, `current_role`, and `experience_years`, including a non-negative database constraint. Preserve the current lazy database-import behavior so `/health` stays independent of database configuration, as tested in `tests/test_identity.py`.

The ownership ambiguity is resolved: each user owns at most one candidate, including retained soft-deleted records. Further CV uploads, target roles, and profile revisions reuse that candidate. Do not create a fresh candidate for each CV or role. The database constraint protects concurrent requests; an application-only existence check is insufficient. See `README.md` §1 Candidate Profile, `docs/database.md#candidate-ownership`, and the 2026-10-24 decision in `.ai/decisions.md`.

## 4. Tasks

1. **Define the candidate API contract and Pydantic request/response models.**
   - Add a small `app/candidates/` module boundary, for example `schemas.py` and `service.py` (and `__init__.py`).
   - Define a create request with optional, trimmed `name` and `current_role`, plus optional `experience_years`. Reject blank strings after trimming and reject negative experience before persistence. Keep the accepted fields limited to columns already on `Candidate`; do not accept `user_id`, profile fields, or target roles from the client.
   - Define a response containing at least `id`, `user_id`, `name`, `current_role`, and `experience_years`. Serialize UUIDs as strings and numeric experience predictably.
   - Define a generic duplicate response, such as HTTP 409 with `{"detail": "Candidate already exists"}`. Do not expose database exception details.

2. **Implement a focused candidate creation service.**
   - In `app/candidates/service.py`, create a function that accepts a caller-owned SQLAlchemy `Session`, the authenticated local user UUID, and validated create data; instantiate `app.db.models.Candidate` with `user_id` set exclusively from the authenticated user; add, commit, and return the persisted candidate.
   - On SQLAlchemy persistence errors, roll back. Translate only PostgreSQL unique violations with SQLSTATE `23505` and constraint name `uq_candidates_user_id` into a candidate-already-exists domain error for HTTP 409. This includes concurrent first-creation requests. Other integrity/persistence errors remain generic HTTP 503 failures without leaking database URLs, SQL, or user input.
   - Follow the established dedicated-session and rollback conventions in `app/identity/user_service.py`. Consume the resolved model and migration without modifying the initial migration or adding another schema change. Retained soft-deleted candidates still occupy the user's slot.

3. **Add lazy candidate persistence wiring and `POST /candidates`.**
   - Add a candidate-specific dependency/helper that imports `SessionLocal` only when the authenticated endpoint executes, opens/closes a dedicated session, maps the candidate-already-exists error to generic HTTP 409, and converts other persistence/configuration failures to a generic HTTP 503 response such as `{"detail": "Candidate service unavailable"}`.
   - In `app/main.py`, add `POST /candidates` with HTTP 201. Require `get_current_user`; parse the request model; call the candidate service with `UUID(user.id)`; return the response model.
   - Ensure the route never trusts a client-provided owner ID and does not expose raw SQLAlchemy exceptions. Preserve `/health`’s current behavior and its lack of database/auth-provider imports before a protected endpoint is invoked.

4. **Add focused tests before considering broader onboarding.**
   - Add `tests/test_candidates.py` covering the HTTP happy path with overridden authentication and mocked candidate persistence: a valid authenticated request returns 201, returns the persisted candidate data, and passes the authenticated user ID—not client input—to the service.
   - Cover relevant failures: unauthenticated `POST /candidates` returns the existing 401 Bearer challenge and does not invoke candidate persistence; invalid negative experience and blank optional strings return 422; a simulated persistence/configuration error returns generic 503 and does not leak its private message.
   - Add service-level unit tests using a mocked SQLAlchemy `Session`: correct `Candidate.user_id`, `add`/`commit` on success, and `rollback` on `SQLAlchemyError`.
   - Cover duplicate creation as HTTP 409. Simulate the exact PostgreSQL unique-constraint violation to cover the race path and rollback; unrelated integrity errors must remain HTTP 503. Keep the existing `tests/test_candidate_ownership.py` constraint and migration coverage.
   - Retain existing health and identity tests to guard lazy-import/liveness behavior.

5. **Update implementation-state documentation, then validate.**
   - Update `.ai/project-state.md` to mark authenticated candidate creation as implemented and state that retrieval/listing, candidate authorization queries, CV ingestion, and target-role selection remain planned.
   - Prerequisites for local checks: Python 3.12+, a virtual environment, and development dependencies installed with `python -m pip install -e '.[dev]'`.
   - Run:
     ```bash
     python -m pytest -q tests/test_candidates.py tests/test_candidate_ownership.py tests/test_identity.py tests/test_health.py
     python -m pytest -q
     ruff check app tests
     python tools/project_advisor.py check
     git diff --check
     ```
     Expected after implementation: focused and full test commands complete successfully; Ruff reports no violations; advisor check reports required files present; whitespace check emits no errors.
   - Optional PostgreSQL validation requires an isolated PostgreSQL database with pgvector, `DATABASE_URL`/`PREPBUDDY_TEST_DATABASE_URL` configured, and migrations applied (`docker compose up -d postgres && alembic upgrade head`). Migration `20261024_0002` refuses existing duplicate owners without changing records; resolve any duplicates deliberately before retrying. Add an opt-in service integration test using the isolation pattern in `tests/test_identity_persistence.py`: first creation persists the authenticated owner; a second attempt rolls back and leaves exactly one candidate. The existing migration tests use a temporary table and do not apply migrations to the real schema. A concurrent creation check should observe one success and one conflict. Do not represent PostgreSQL validation as completed unless actually run.

## 5. Relevant files

**Existing files to modify**
- `app/main.py` — add the narrowly scoped authenticated `POST /candidates` route.
- `app/db/models.py` — consume the existing `Candidate` model only; no model change is expected.
- `tests/test_candidate_ownership.py` — retain coverage of the implemented uniqueness rule and migration safeguards.
- `app/db/session.py` — reuse `SessionLocal` through lazy endpoint execution; avoid eager imports in `app/main.py`.
- `app/identity/dependencies.py` and `app/identity/service.py` — reuse `get_current_user` and `LocalUser`; change only if a minimal shared dependency extension is genuinely needed.
- `tests/test_identity.py` and `tests/test_health.py` — keep unchanged unless a regression assertion is necessary.
- `.ai/project-state.md` — record the new implemented boundary and remaining work.
- `docs/architecture.md` and `docs/database.md` — reference only; they already define candidate ownership and schema intent.

**Existing files not expected to change**
- `alembic/versions/20260830_0001_initial_prepbuddy_schema.py` — preserve the historical initial migration.
- `alembic/versions/20261024_0002_one_candidate_per_user.py` — ownership constraint migration is already present; apply it before using candidate creation. No further migration is proposed for the API milestone.
- `app/identity/auth0.py` — token-verification behavior is out of scope.
- `compose.yaml` — local database setup is already present.

**Proposed new files**
- `app/candidates/__init__.py` — candidate module package.
- `app/candidates/schemas.py` — create-request and response Pydantic models.
- `app/candidates/service.py` — session-owned candidate creation and rollback behavior.
- `tests/test_candidates.py` — endpoint and service unit tests.

A separate `app/candidates/dependencies.py` is optional only if it materially clarifies lazy session lifecycle and generic 503 translation; keep the module count minimal.

## 6. Coding-agent instructions

Implement only authenticated candidate creation. Preserve all existing files and current `/health`, `/me`, Auth0, and database-session behavior.

Create a compact `app/candidates` business module with validated request/response schemas and a service that takes a caller-owned session. The authenticated owner must come exclusively from `LocalUser.id`; never accept or derive ownership from request JSON. Use the existing `Candidate` ORM table and its `uq_candidates_user_id` constraint. Migration `20261024_0002` implements this approved rule; do not rewrite the initial migration or add another migration for the API. Keep new dependencies, document ingestion, target roles, profile versions, and read/list endpoints out of this milestone.

Keep database imports lazy on the protected execution path so importing `app.main` and calling `/health` without `DATABASE_URL` remains valid. Use dedicated sessions, commit only successful creation, roll back on SQLAlchemy errors, and close sessions. Return generic HTTP 409 only for the exact `23505`/`uq_candidates_user_id` conflict, including concurrent attempts and retained soft-deleted candidates. Sanitize other persistence/configuration failures as 503 without logging/returning raw exception text. Use HTTP 201 for successful first creation, FastAPI/Pydantic validation for malformed baseline fields, and the existing authentication dependency for 401 behavior.

Write focused mocked tests for route ownership, validation, unauthenticated rejection, duplicate/race conflicts, unrelated integrity errors, sanitized persistence failure, and service rollback. Update `.ai/project-state.md` factually after code is complete. Run the specified pytest, Ruff, advisor-check, and whitespace commands; report commands and actual outcomes in the implementation handoff, including any unavailable PostgreSQL/Docker prerequisite. Do not claim live database or migration validation unless it was explicitly performed.

## 7. Definition of done

- `POST /candidates` exists in `app/main.py`, requires the established authenticated-user dependency, and returns HTTP 201 for a valid request.
- A successful response exposes the created candidate ID, authenticated owner ID, and accepted baseline fields, without accepting a request-controlled `user_id`.
- The persisted `Candidate.user_id` is derived from the verified local user UUID; no candidate is created for an unauthenticated request.
- The approved one-candidate-per-user rule is respected: a second creation returns a generic HTTP 409 after rollback, including concurrent attempts rejected by `uq_candidates_user_id`. Unrelated integrity errors remain generic HTTP 503. Existing candidate data is preserved.
- Optional text fields reject whitespace-only values, and negative `experience_years` is rejected with HTTP 422 before persistence.
- Other database/session/configuration failures on the protected endpoint produce a generic HTTP 503 response and do not expose raw exception details.
- Candidate creation rolls back its caller-owned session when a SQLAlchemy error occurs.
- `/health` remains a public 200 liveness endpoint independent of database configuration, and existing `/me` authentication behavior is not intentionally changed.
- `tests/test_candidates.py` covers the happy path and specified failure cases; focused tests, the full suite, Ruff, `python tools/project_advisor.py check`, and `git diff --check` have been run and their actual results are recorded in `.ai/project-state.md`. Live PostgreSQL/Auth0 checks must be reported separately from mocked checks.
- `.ai/project-state.md` accurately distinguishes this implemented candidate-creation boundary from still-planned candidate retrieval/authorization, CV ingestion, profile extraction, and target-role workflows.
