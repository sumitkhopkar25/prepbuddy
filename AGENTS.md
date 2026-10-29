# Working on PrepBuddy

- Read `README.md` for product scope and `docs/architecture.md` for the accepted design.
- Consult `docs/database.md` before changing persistence or migrations.
- Keep `.ai/project-state.md` current when implementation status changes and record
  architectural decisions in `.ai/decisions.md` with links to supporting documentation.
- Preserve existing files. Add the requested structure without removing existing code,
  documentation, configuration, or tests.
- Follow the modular monolith architecture and distinguish implemented features from plans.
- Keep secrets and personal document contents out of source control and logs.
- For Python changes, use the project's Ruff configuration and run relevant pytest checks.
- For persistence or database-backed API changes, run
  `.venv/bin/python tools/test_postgresql.py` when Docker is available. It creates
  an isolated database, applies migrations, runs the full suite, and cleans up.
  Do not point tests at the development database; report PostgreSQL checks as
  unverified if Docker or an explicitly configured isolated test database is unavailable.

Run `python tools/project_advisor.py` to check the required project files.
Run `python tools/project_advisor.py next` to generate an implementation and testing plan
in `.ai/next-step.md`. See `docs/project-advisor.md` for configuration and context limits.
