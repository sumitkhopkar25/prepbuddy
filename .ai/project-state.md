# Project state

Last reviewed: 2026-09-21.

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
- Local service configuration: `compose.yaml` and the Git-ignored `.env`.
- Database credentials are required from environment configuration; Docker's
  PostgreSQL port is published only on host loopback. See `docs/database.md`.

## Planned work

The minimal API skeleton is implemented. Database readiness checks, broader backend
configuration, authentication and ownership enforcement, the Next.js frontend,
background processing, and preparation workflows remain planned. Follow the
implementation order in `docs/architecture.md` when selecting the next milestone.

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
