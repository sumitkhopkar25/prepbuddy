# Project state

Last reviewed: 2026-09-19.

## Present in the repository

- Product scope and behavior: `README.md`.
- Accepted MVP design: `docs/architecture.md`.
- Database documentation: `docs/database.md`.
- Python package and dependencies: `app/` and `pyproject.toml`.
- Database models, configuration, and session support: `app/db/`.
- Alembic configuration and initial schema migration: `alembic.ini` and `alembic/`.
- Database metadata tests: `tests/test_database_metadata.py`.
- Local service configuration: `compose.yaml` and the Git-ignored `.env`.
- Database credentials are required from environment configuration; Docker's
  PostgreSQL port is published only on host loopback. See `docs/database.md`.

## Planned work

The architecture describes the intended FastAPI API, Next.js frontend, background
processing, and preparation workflows. Their application implementations are not
present in the inspected tree. Follow the implementation order in
`docs/architecture.md`, starting with the backend skeleton after the database foundation.

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
