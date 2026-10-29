# Database architecture

PrepBuddy uses PostgreSQL as its system of record and `pgvector` for job-profile
embeddings. The schema is implemented with SQLAlchemy 2.x and managed by Alembic.

## Design principles

- Candidate, job, cluster, fit, and plan history is preserved rather than overwritten.
- Raw evidence is separated from structured interpretation and recommendations.
- Frequently queried skills and cluster membership are relational; flexible AI output and
  explanations use JSONB.
- Active versions are protected by partial unique indexes.
- Plan changes are proposed separately and require acceptance before a new plan version is
  activated.
- All ownership roots lead back to a candidate and user. API authorization must still scope
  every query to the authenticated user.

## Schema areas

| Area | Main tables |
| --- | --- |
| Identity | `users`, `candidates`, `candidate_target_roles` |
| Taxonomy | `taxonomy_occupations`, `taxonomy_skills`, `taxonomy_occupation_skills`, `skill_aliases` |
| Source and provenance | `source_documents`, `extraction_runs`, `evidence_references`, `user_corrections` |
| Candidate profile | `candidate_profile_versions`, `candidate_skills` |
| Job profiles | `job_descriptions`, `job_profile_versions`, profile detail tables |
| Clustering | `clustering_runs`, `clusters`, `cluster_versions`, `cluster_memberships`, `cluster_skill_summaries` |
| Evaluation | `fit_evaluations` |
| Market signals | `market_signal_snapshots`, `market_signals` |
| Planning | `prep_plans`, `prep_plan_versions`, `prep_tasks`, `plan_change_proposals` |

`fit_evaluations` supports exactly one target per row: a target role, an individual job,
or a cluster. PostgreSQL enforces this with a check constraint.

## Candidate ownership

The MVP allows a user to own zero or one candidate. Each candidate must belong to
exactly one user through the non-null `candidates.user_id` foreign key to `users.id`.
The `uq_candidates_user_id` unique constraint enforces the per-user limit, including
concurrent inserts. A user may exist before candidate onboarding is complete.

The constraint includes soft-deleted records (`deleted_at IS NOT NULL`): retaining
a deleted candidate does not release its user's slot for another candidate. Updating
a CV or target direction uses the same candidate; profile history belongs in
`candidate_profile_versions`, which separately permits only one active version.
Deletion/restoration API behavior and career-coach access remain planned.

Migration `20261024_0002` adds this constraint after the initial schema. It takes an
exclusive table lock for the transaction, checks for duplicate owners, and aborts
with a generic error if any exist, including soft-deleted duplicates. It does not
delete, merge, or reassign records. Resolve duplicates deliberately before retrying;
the check does not output user IDs or candidate contents. Downgrading to
`20260830_0001` removes only the new unique constraint and preserves candidate data
and the existing ownership index. Keep the initial migration unchanged.

## Local setup

Set `DATABASE_URL` in the project-root `.env` file (ignored by Git). For the
local PostgreSQL service, use:

```dotenv
DATABASE_URL=postgresql+psycopg://prepbuddy:prepbuddy@localhost:5432/prepbuddy
POSTGRES_DB=prepbuddy
POSTGRES_USER=prepbuddy
POSTGRES_PASSWORD=prepbuddy
```

These are example local development values. The application requires `DATABASE_URL`
from `.env` or the process environment; there is no credential fallback in source.
Keep its database name, username, and password consistent with the `POSTGRES_*`
values used by Docker Compose. URL-encode special characters in URL credentials.
Docker publishes PostgreSQL only on `127.0.0.1`, so other machines cannot connect
through the host's network interfaces. The URL's `localhost` only controls where
the application connects; it does not control where PostgreSQL accepts connections.

The `POSTGRES_*` values initialize a new database volume. Changing them does not
change credentials in an existing database; update the database role separately
if rotating credentials, preserving the existing volume.

From the project root, start PostgreSQL and apply the migration:

```bash
docker compose up -d postgres
alembic upgrade head
```

The initial migration enables the `vector` extension. The configured embedding width is
1,536 dimensions in `app/db/models.py`; changing embedding providers to one with a different
width requires a migration.

To inspect SQL without connecting to a database:

```bash
alembic upgrade head --sql
```

## Automated PostgreSQL and API testing

With Python development dependencies installed and Docker Desktop running, execute
from the repository root:

```bash
.venv/bin/python tools/test_postgresql.py
```

On Windows/WSL, enable this distro in Docker Desktop under **Settings → Resources →
WSL Integration**, then apply the change. `docker version` must show both a client
and a server. See [Docker's WSL instructions](https://docs.docker.com/desktop/features/wsl/).

The runner uses `compose.test.yaml` to start a uniquely named PostgreSQL 16 + pgvector
container with a generated password, an automatically assigned loopback port, and
temporary in-memory storage. It waits for readiness, supplies `DATABASE_URL` and
`PREPBUDDY_TEST_DATABASE_URL` only to its child processes, applies `alembic upgrade
head`, and runs the full pytest suite. It removes that run's container and network
on completion or failure. It does not change `.env`, the development Compose
service, or its database volume. Docker must remain available for cleanup; a
cleanup failure is reported as a failed run. The first run may download the image.

Pass pytest arguments to select tests, for example:

```bash
.venv/bin/python tools/test_postgresql.py -q tests/test_api_postgresql.py
```

`tests/test_api_postgresql.py` starts a real loopback Uvicorn server and exercises
HTTP authentication, persistent local-user resolution, missing candidate state,
candidate creation and retrieval, duplicate rejection, input validation, and
two-user ownership isolation. It verifies committed data through independent
PostgreSQL sessions and removes only its generated users/candidates afterward.
JWT signatures and claims use the production validator with generated RSA keys;
only the Auth0 signing-key HTTP transport is replaced. This checks the implemented
backend flow, not a real Auth0 browser login or a frontend (which is still planned).
Use [the live authentication procedure](authentication.md#5-sign-in-and-call-me-from-postman)
for that external-provider check.

### Using an existing isolated test database

Alternatively, provision a separate PostgreSQL database with pgvector available.
The migration account must be allowed to create the `vector` extension (or an
administrator must install it first). Export its URL in your terminal:

```bash
export PREPBUDDY_TEST_DATABASE_URL='postgresql+psycopg://TEST_USER:TEST_PASSWORD@127.0.0.1:5432/prepbuddy_test'
DATABASE_URL="$PREPBUDDY_TEST_DATABASE_URL" .venv/bin/python -m alembic upgrade head
DATABASE_URL="$PREPBUDDY_TEST_DATABASE_URL" .venv/bin/python -m pytest -q
```

Replace the placeholders locally. The opt-in tests read the process environment;
adding `PREPBUDDY_TEST_DATABASE_URL` to `.env` alone does not enable them. Without
the exported variable, normal `python -m pytest -q` skips the PostgreSQL cases.
Use a database dedicated to automated tests: migrations change its schema and the
HTTP flow commits generated rows before cleanup. Existing service and constraint
tests use rollback transactions. The disposable runner handles this configuration
automatically and is the preferred local command.
