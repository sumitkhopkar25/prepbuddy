# Architectural decisions

## Accepted MVP architecture

Source: [`docs/architecture.md`](../docs/architecture.md), accepted for MVP and dated
2026-09-12. The following summarizes existing decisions; it does not change them.

- Build a modular monolith with a shared Python codebase for the API and worker.
- Use Next.js, React, TypeScript, and Tailwind for the planned web application.
- Use FastAPI, Pydantic, SQLAlchemy, and Alembic for the backend.
- Store relational data and embeddings in PostgreSQL with pgvector.
- Process slow work through a Redis-backed queue and store uploads in S3-compatible storage.
- Keep scoring and state transitions deterministic; use LLMs for interpretation and explanation.
- Preserve version history and keep active weekly preparation plans locked for seven days.
- Isolate provider choices behind application interfaces.

Refer to the architecture document for rationale, boundaries, and deferred features.

## Repository support structure — 2026-09-12

Add `AGENTS.md`, `.ai/project-state.md`, `.ai/decisions.md`, and
`tools/project_advisor.py` alongside the existing README and architecture document.
Preserve all existing files and directories, as requested by the project owner.

## Repository advisor — 2026-09-12

The `next` command uses the OpenAI Responses API with structured output to produce
one small implementation milestone and its testing plan. Configure the model through
`ADVISOR_MODEL` or `--model`; credentials come from `OPENAI_API_KEY` in the process
environment. The implementation uses the Python standard library. It inspects schema
files rather than live database records and never executes the generated instructions.

## Local advisor configuration — 2026-09-14

Superseding environment-only configuration, use `python-dotenv` to read the
project-root `.env`, which remains ignored by Git. Environment variables take
precedence, followed by `--model` for the model selection. Keep credentials out
of Python source. See [advisor setup](../docs/project-advisor.md).

Use `ADVISOR_MODEL` for advisor model configuration. Keep local configuration in
`.env` only, with setup documented in [database setup](../docs/database.md) and
[advisor setup](../docs/project-advisor.md).
