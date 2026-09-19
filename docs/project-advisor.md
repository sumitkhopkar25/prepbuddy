# Project advisor

Generate one basic implementation milestone and a concrete testing plan:

Install dependencies with `python -m pip install -e '.[dev]'`, then fill in the
project-root `.env` file (ignored by Git):

```dotenv
OPENAI_API_KEY=your-api-key
ADVISOR_MODEL=your-model-id
```

Run `python tools/project_advisor.py next`.

Choose a model available to your API account that supports the Responses API and
structured outputs. You can override `ADVISOR_MODEL` with `--model MODEL_ID`.
The script uses `python-dotenv` to read the project-root `.env` regardless of your
working directory. Exported environment variables override `.env` values, and
`--model` overrides both. Git is required. The key and model are not stored in Python code.

The command sends selected repository context to OpenAI and saves the validated
response in `.ai/next-step.md`. Each successful run replaces that plan. Failed
requests or invalid responses leave the previous plan intact. No implementation
commands, tests, or migrations are executed by the advisor.

The output contains:

1. Current project state, with evidence and uncertainties
2. One next milestone
3. Reasoning for its priority
4. Ordered tasks, including test commands, prerequisites, and expected results
5. Relevant existing and proposed files
6. Instructions ready to hand to a coding agent
7. Definition of done with observable acceptance criteria

## Inspect context without an API call

```bash
python tools/project_advisor.py next --dry-run
```

This prints the context as JSON without credentials, network access, or writing a plan.
The context includes goals from the README, architecture, project state, decisions,
database documentation, models and migrations, source and test files, Git status,
and the latest 15 commit summaries. Uncommitted source changes and unignored new
files are included. No live database connection is made.

Collection excludes ignored files, environment files, secret/credential-named files,
symlinks, dependency directories, caches, and the previous generated plan. Only
selected text extensions are included in the reported structure and file contents.
Files larger than 60 KB are omitted; content has a total 180 KB budget with core
documentation prioritized. Omissions are reported to the model. Git summaries are
limited to 12,000 characters. Filename filtering is not a general secret scanner:
review the dry-run context if source files or commit messages contain sensitive data.

## Local validation

```bash
python tools/project_advisor.py check
python -m pytest -q
ruff check tools/project_advisor.py tests/test_project_advisor.py
```

The default command remains `check`. Advisor tests mock the API; they require no
credentials or network connection. A live `next` run requires API credentials,
model access, and network access.

The API integration follows the official
[Structured Outputs documentation](https://developers.openai.com/api/docs/guides/structured-outputs).
