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

## Local setup

Copy `.env.example` to `.env`, then start PostgreSQL and apply the migration:

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

