# Next implementation step

Status: Completed 2026-10-29. Authenticated current-candidate retrieval is implemented.
Validation: 127 tests passed; 8 opt-in PostgreSQL tests skipped. See
[project state](project-state.md#current-candidate-retrieval-validation--2026-10-29)
for commands and limits. The original implementation brief is preserved below.

Generated: 2026-10-26T18:25:01+00:00 | Model: gpt-5.6-terra

## 1. Current project state

## Implemented

- FastAPI exposes database-independent `GET /health`, authenticated `GET /me`, and authenticated `POST /candidates` in `app/main.py`.
- Auth0 token validation and local-user resolution are implemented under `app/identity/`; `get_current_user` supplies the authenticated local ownership ID.
- `POST /candidates` already creates one candidate for that user, validates baseline fields, materializes a detached `CandidateResponse`, maps the exact ownership conflict to HTTP 409, and sanitizes other persistence failures as HTTP 503 (`app/candidates/dependencies.py`, `app/candidates/service.py`).
- The schema enforces one retained candidate per user through `candidates.user_id` and `uq_candidates_user_id` (`app/db/models.py`, `alembic/versions/20261024_0002_one_candidate_per_user.py`).
- Candidate retrieval/listing and authorization queries for existing resources are explicitly still planned in `.ai/project-state.md` and `docs/architecture.md`.

## Evidence limits and uncertainty

This recommendation is based only on supplied repository content. No tests, migrations, API calls, Auth0 login, or live database inspection were performed for this advisory response. The initial migration was omitted from supplied context because of size, so its exact generated SQL was not independently reviewed; current SQLAlchemy models and the later ownership migration provide the available schema evidence.

The repository records prior validation results in `.ai/project-state.md`, but those results are historical evidence, not validation performed now.

## 2. Next milestone

## Add authenticated current-candidate retrieval

Implement **`GET /candidates/me`** to return the authenticated user's single candidate baseline record.

Return the existing `CandidateResponse` with HTTP 200 when a candidate owned by the current authenticated user exists. Return a generic HTTP 404, for example `{"detail": "Candidate not found"}`, when that user has not completed candidate onboarding. Scope the lookup by both candidate ownership and authenticated `user_id`; never accept a candidate ID from the client for this milestone.

This is deliberately one small endpoint, not candidate updates, deletion/restoration semantics, candidate listing, CV ingestion, target roles, or general resource lookup.

## 3. Reasoning

`POST /candidates` is complete, but clients cannot currently retrieve the resulting onboarding state. A current-user retrieval endpoint closes that immediate API loop and is the smallest product-facing prerequisite for the next architecture step—CV ingestion and profile work must first locate the authenticated user's candidate ownership root.

It is also the lowest-risk place to establish the repository's planned existing-resource authorization pattern: query only by the server-derived `LocalUser.id`, return no cross-user result, and sanitize infrastructure errors. The one-candidate-per-user constraint means a singular current-candidate route is clearer and smaller than adding a collection endpoint. Reuse of `CandidateResponse` also keeps response serialization consistent with creation (`app/candidates/schemas.py`).

The proposed behavior should explicitly decide how retained soft-deleted candidates are handled. Because deletion/restoration behavior is documented as planned in `docs/database.md`, the safest small-scope contract is to retrieve the owned row as currently stored rather than introduce a new `deleted_at` filtering policy. If product owners instead require deleted candidates to be hidden, document that as a separate deletion-semantics decision before implementing it.

## 4. Tasks

1. **Confirm the narrow API contract before coding.**
   - Route: `GET /candidates/me`.
   - Authentication: reuse `get_current_user`; missing/invalid credentials must preserve the established HTTP 401 Bearer challenge, and identity resolution failures must preserve its existing HTTP 503 behavior.
   - Success: HTTP 200 using the existing `CandidateResponse` shape: `id`, `user_id`, `name`, `current_role`, and one-decimal-string-or-null `experience_years`.
   - No candidate: HTTP 404 with exactly a generic non-sensitive detail such as `Candidate not found`.
   - Persistence/configuration error: HTTP 503 with a generic candidate-service detail, consistent with creation.
   - Ownership: derive `user_id` only from `LocalUser`; do not add client-selected IDs or an unscoped candidate lookup.
   - Soft deletion: do not add deletion behavior or alter the current retained-record invariant in this milestone.

2. **Add a focused retrieval service in the existing candidates module.**
   - In `app/candidates/service.py`, add a query function taking a caller-owned SQLAlchemy `Session` and authenticated `UUID` user ID.
   - Query `Candidate` by `Candidate.user_id == user_id` and return the candidate or a dedicated domain exception such as `CandidateNotFound`.
   - Do not query by an arbitrary candidate ID, and do not make any schema or Alembic migration change.
   - Preserve the service convention already used by `create_candidate`: service code handles SQLAlchemy transaction cleanup for SQLAlchemy failures; HTTP translation remains outside the service.

3. **Add a lazy dependency/HTTP translation wrapper.**
   - In `app/candidates/dependencies.py`, add a retrieval helper that imports `SessionLocal` only when an authenticated request executes, opens a dedicated session, calls the service query, and materializes `CandidateResponse` before session closure.
   - Translate only the intentional not-found domain exception to HTTP 404.
   - Sanitize all unexpected persistence/configuration failures to HTTP 503 without exposing exception text, connection strings, candidate data, or SQL details.
   - Preserve public `/health` import isolation: do not import database settings/session modules at `app.main` import time.

4. **Wire the route without changing existing endpoint behavior.**
   - In `app/main.py`, add `GET /candidates/me` with `response_model=CandidateResponse` and `get_current_user`.
   - Convert `user.id` to `UUID` exactly as candidate creation currently does.
   - Keep `POST /candidates`, `/me`, and `/health` unchanged.

5. **Add focused automated tests in `tests/test_candidates.py` (or a new narrowly named candidate-retrieval test module if that keeps the file clearer).**
   - Use FastAPI dependency overrides/mocks as existing candidate tests do; tests must not require Auth0 or PostgreSQL by default.
   - Happy path: an authenticated owner receives HTTP 200, the expected serialized candidate response, and the persistence wrapper receives that authenticated owner UUID.
   - Empty onboarding state: a service-level `CandidateNotFound` produces exactly HTTP 404 and the generic detail.
   - Ownership boundary: verify a response is returned only from a lookup invoked with the current user's UUID; add a service-level query test demonstrating that querying user A cannot return user B's candidate.
   - Authentication failure: unauthenticated requests return the existing HTTP 401 Bearer challenge and candidate persistence is not called.
   - Failure sanitization: simulated session construction and database/query errors return HTTP 503 with the generic message; private error strings do not appear in response text or captured logs.
   - Lifecycle: confirm the dedicated session context exits and response serialization works after session closure.
   - If adding an opt-in PostgreSQL test, require `PREPBUDDY_TEST_DATABASE_URL` pointing at an isolated database migrated with `alembic upgrade head`; create two generated users/candidates inside an outer rollback transaction and verify each lookup returns only its owner's row. The test must skip when that variable is unset.

6. **Update implementation-status documentation and validate.**
   - Update `README.md` Backend API text with the endpoint, status codes, authentication requirement, and an example call only if the exact behavior is implemented.
   - Update `.ai/project-state.md` to move current-candidate retrieval from planned to implemented and record actual commands/results only after running them.
   - Update `.ai/decisions.md` only if an enduring policy decision is made (for example, explicit handling of retained soft-deleted candidates); do not add a decision entry merely for routine endpoint wiring.
   - Prerequisites for local validation: Python 3.12+, an activated virtual environment, and development dependencies installed:
     ```bash
     python -m pip install -e '.[dev]'
     ```
   - Run focused tests:
     ```bash
     python -m pytest -q tests/test_candidates.py tests/test_identity.py tests/test_health.py
     ```
     Expected result: all selected non-PostgreSQL tests pass; opt-in PostgreSQL tests, if present and `PREPBUDDY_TEST_DATABASE_URL` is absent, are reported as skipped.
   - Run the full default suite and static checks:
     ```bash
     python -m pytest -q
     ruff check app tests alembic tools
     python tools/project_advisor.py check
     git diff --check
     ```
     Expected result: test suite passes aside from only explicitly opt-in skips; Ruff, advisor required-file check, and whitespace check exit successfully.
   - Optional real PostgreSQL validation prerequisites: an isolated PostgreSQL database with pgvector support, valid `DATABASE_URL`, `PREPBUDDY_TEST_DATABASE_URL` set to that isolated database, and migrations applied:
     ```bash
     alembic upgrade head
     PREPBUDDY_TEST_DATABASE_URL="$DATABASE_URL" python -m pytest -q tests/test_candidates.py
     ```
     Expected result: the opt-in ownership/retrieval persistence cases run and pass without retaining generated test data because the outer transaction rolls back.

## 5. Relevant files

## Existing files to modify

- `app/main.py` — add the authenticated `GET /candidates/me` route while preserving existing health, identity, and creation routes.
- `app/candidates/__init__.py` — add a narrowly scoped `CandidateNotFound` domain exception if used.
- `app/candidates/service.py` — add the user-scoped candidate query using the caller-owned session.
- `app/candidates/dependencies.py` — add lazy session handling, detached response materialization, and 404/503 translation for retrieval.
- `tests/test_candidates.py` — extend existing candidate endpoint/service boundary tests, or split only retrieval-specific tests into a focused test file.
- `README.md` — document the endpoint only after implementation.
- `.ai/project-state.md` — record the delivered capability and actual validation evidence.
- `.ai/decisions.md` — modify only if soft-delete retrieval semantics require an explicit persistent decision.

## Existing files to consult, not expected to change

- `app/candidates/schemas.py` — reuse `CandidateResponse`; do not duplicate the schema.
- `app/identity/dependencies.py` and `app/identity/service.py` — preserve authentication and local-user behavior.
- `app/db/models.py` — `Candidate.user_id` is the ownership root and has a unique constraint.
- `app/db/session.py` — follow the existing lazy dedicated-session pattern.
- `tests/test_identity.py` and `tests/test_health.py` — guard current authentication and import-isolation behavior.
- `docs/architecture.md` and `docs/database.md` — source of planned authorization and retained-candidate constraints.

## Proposed files

- No new production module is required.
- Optional: `tests/test_candidate_retrieval.py` only if retrieval coverage would make `tests/test_candidates.py` materially unclear; otherwise keep all candidate endpoint coverage in the existing test file.
- No migration file should be created for this milestone.

## 6. Coding-agent instructions

Implement only the authenticated current-candidate retrieval milestone.

1. Read `AGENTS.md`, `README.md`, `docs/architecture.md`, `docs/database.md`, and the existing candidate/identity tests before editing.
2. Add `GET /candidates/me`, protected by the existing `get_current_user` dependency. Do not add a path parameter, list endpoint, candidate update, deletion, target-role behavior, document ingestion, or frontend work.
3. Implement a candidates-domain query that scopes the database lookup exclusively to the authenticated local user ID. A user with no candidate must receive an intentional domain-level not-found result, not a leaked SQLAlchemy exception.
4. Reuse `CandidateResponse` and its decimal serializer. Materialize the response while the session is open, then close the session before FastAPI serializes it.
5. Follow the existing lazy-import pattern in `app/candidates/dependencies.py` so importing `app.main` and calling `/health` still do not initialize database configuration, SQLAlchemy, Auth0, or JWT modules.
6. Map only the explicit no-candidate condition to generic HTTP 404. Map unexpected database/session/configuration failures to generic HTTP 503, and never include raw exceptions, SQL, database URLs, credentials, or candidate content in responses or logs.
7. Do not change schema, models, migrations, creation semantics, Auth0 verification, or ownership constraints. Do not invent deletion behavior; retain current stored-row semantics unless the product owner explicitly supplies a contrary requirement.
8. Add focused tests for successful retrieval, absent candidate, authenticated ownership scoping, unauthenticated short-circuiting, generic 503 sanitation, and dedicated-session closure. Use mocks/default test infrastructure; make any PostgreSQL test opt-in and rollback-safe.
9. Run the specified focused tests, full tests, Ruff, advisor check, and whitespace check. Report exact commands and outcomes truthfully. If environment limitations prevent a command, state that clearly rather than claiming success.
10. Preserve existing files and update README/project state only to describe behavior actually implemented and validated.

## 7. Definition of done

- `GET /candidates/me` exists in `app/main.py` and requires the existing authenticated local-user dependency.
- An authenticated user with a candidate receives HTTP 200 with the existing `CandidateResponse` fields; UUID fields serialize as strings and `experience_years` follows the established one-decimal-string-or-null behavior.
- An authenticated user without a candidate receives HTTP 404 with the documented generic `Candidate not found` response and no database exception details.
- The retrieval query is scoped by the authenticated user ID, with automated coverage demonstrating that one user's retrieval cannot return another user's candidate.
- Missing or invalid credentials remain HTTP 401 with `WWW-Authenticate: Bearer`, and candidate persistence is not invoked.
- Unexpected session, configuration, and database/query failures return a generic HTTP 503 candidate-service response; tests verify private simulated error text is absent from responses and captured logs.
- Retrieval opens and closes a dedicated session and materializes a detached response before the session closes.
- No Alembic migration, database model change, candidate update/list/delete route, CV ingestion feature, or authentication-provider behavior is introduced.
- Focused candidate/identity/health tests, the full default test suite, Ruff, `python tools/project_advisor.py check`, and `git diff --check` have been run and their actual outcomes are recorded. Any opt-in PostgreSQL tests are either passed against an isolated migrated database or explicitly reported as skipped because `PREPBUDDY_TEST_DATABASE_URL` was not configured.
- `README.md` and `.ai/project-state.md` accurately distinguish this implemented retrieval endpoint from still-planned broader resource authorization and onboarding workflows.
