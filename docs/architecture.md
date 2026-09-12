# PrepBuddy architecture reference

**Status:** Accepted for MVP  
**Last updated:** 12 September 2026

This document records the agreed technical design for PrepBuddy. It is the main reference for
implementation decisions. Product behavior and examples remain in the project README, while
database details are documented separately in [database.md](database.md).

## 1. Product boundary

PrepBuddy turns a candidate's CV, target direction, and collection of job descriptions into a
small number of meaningful preparation clusters and a stable weekly preparation plan.

The MVP is intentionally focused on software and technology roles. It is not intended to be a
general job tracker, automatic application tool, or per-job resume generator.

The four central domain concepts are:

1. **Candidate profile** — what the candidate can currently demonstrate.
2. **Job profile** — a structured interpretation of one job description.
3. **Cluster profile** — preparation patterns shared by similar jobs.
4. **Prep plan** — a versioned and temporarily locked execution plan.

## 2. Architectural principles

- Start with a modular monolith, not microservices.
- Run slow AI and document-processing work asynchronously.
- Separate source evidence, computed interpretation, and user-facing recommendations.
- Use deterministic application rules for scores, thresholds, locks, and state changes.
- Use LLMs for language understanding and explanation, not as the sole decision-maker.
- Preserve important history through immutable versions rather than overwriting records.
- Keep live market signals separate from the active preparation plan.
- Make important recommendations explainable using their source evidence.
- Treat CVs and other personal information as sensitive data from the beginning.

## 3. System overview

```text
┌──────────────────────────────┐
│ Next.js web application      │
│ React + TypeScript + Tailwind│
└──────────────┬───────────────┘
               │ HTTPS / JSON API
               ▼
┌──────────────────────────────────────────────────────┐
│ FastAPI modular monolith                             │
│                                                      │
│ Identity │ Ingestion │ Profiles │ Taxonomy           │
│ Clusters │ Scoring   │ Signals  │ Planning           │
└───────┬──────────┬──────────────┬────────────────────┘
        │          │              │
        ▼          ▼              ▼
  PostgreSQL    Redis queue   S3-compatible storage
  + pgvector         │        Original CV documents
                     ▼
              Background worker
              ┌──────┴──────────┐
              │ LLMs │ Embeddings│
              └─────────────────┘
```

The API and worker use the same Python codebase and domain modules. They are separate runtime
processes, but not separate services with independent data models.

## 4. Finalized technology choices

| Layer | Choice | Reason |
| --- | --- | --- |
| Web application | Next.js, React, TypeScript | Strong typed UI ecosystem and straightforward deployment |
| Styling | Tailwind CSS | Fast, consistent UI implementation |
| Backend API | Python with FastAPI | Good schema validation and natural access to AI/ML libraries |
| Data validation | Pydantic | Validates API and structured model output |
| Persistence | SQLAlchemy 2.x | Explicit models and mature PostgreSQL support |
| Migrations | Alembic | Reproducible, versioned schema changes |
| Primary database | PostgreSQL | Transactions, relational integrity, JSONB, and strong querying |
| Vector storage | pgvector | Keeps MVP embedding search with the main dataset |
| Asynchronous work | Redis-backed worker queue | Keeps document and AI jobs away from request latency |
| File storage | S3-compatible object storage | Durable storage for original uploads |
| Deployment | Vercel plus a container host and managed PostgreSQL | Simple MVP operations with independently scalable web/API/worker processes |

The LLM, embedding, authentication, object-storage, queue-library, and cloud vendors must be
accessed through small application interfaces. Their exact providers are deployment choices and
must not leak into the core domain model.

## 5. Backend module boundaries

The modular monolith is divided by business responsibility:

### Identity

Maps the external authentication identity to a PrepBuddy user and ensures every query is scoped
to that user.

### Ingestion

Accepts CVs and job descriptions, stores original documents, extracts text, detects duplicates,
and coordinates processing jobs.

### Profiles

Creates and versions candidate and job profiles. It also records confidence, extraction metadata,
user corrections, and evidence references.

### Taxonomy

Normalizes role and skill names using ESCO as the initial European taxonomy. ESCO is a foundation
for naming and cold-start recommendations; it does not determine the user's final clusters.

### Clustering

Calculates job similarity, runs clustering, creates cluster versions, and preserves manual user
membership decisions.

### Scoring

Evaluates the candidate against a target role, individual job, or cluster using a versioned,
deterministic scoring policy.

### Market signals

Continuously summarizes repeated and changing requirements without changing the active plan.

### Planning

Generates versioned preparation plans and tasks, enforces lock periods, and manages proposed plan
changes and user approval.

These boundaries should be enforced in code even though the modules share one application and
database.

## 6. Evidence-to-recommendation model

The application uses three distinct layers:

```text
Source evidence
"React appears in 13 of 18 jobs"
              │
              ▼
Computed interpretation
"React is a high-frequency required cluster skill"
              │
              ▼
Recommendation
"Add React architecture practice to next week's plan"
```

Original text and evidence references are retained. Extracted profiles record the model, prompt,
and schema version that created them. Business rules calculate scores and decide whether a signal
is strong enough to propose a plan change. The LLM may then explain the result in clear language.

## 7. Main processing flows

### CV processing

1. Validate and store the original CV securely.
2. Extract its text.
3. Create a schema-validated candidate profile with an LLM.
4. Normalize occupations and skills against the taxonomy.
5. Attach extracted facts to supporting source excerpts.
6. Ask the user to confirm or correct the profile.
7. Activate the confirmed candidate-profile version.
8. Evaluate it against the selected target roles and create a baseline roadmap.

### Job-description processing

1. Store the original job description and reject duplicates using a content hash.
2. Extract a schema-validated job profile.
3. Normalize skills, tools, role family, seniority, and domain.
4. Create an embedding from a stable canonical representation of the profile.
5. Calculate individual-job fit.
6. Update market-signal snapshots.
7. Assign the job to an existing cluster or initiate a new clustering run.
8. Re-evaluate affected clusters.
9. Create a plan-change proposal when deterministic major-shift rules are met.
10. Leave the locked active plan unchanged until refresh or user approval.

Processing takes place in background jobs. The UI displays durable states such as `PENDING`,
`PROCESSING`, `SUCCEEDED`, and `FAILED` and allows failed work to be retried safely.

## 8. Dynamic clustering

Embeddings are only one clustering input. The initial hybrid similarity model is:

| Signal | Initial weight |
| --- | ---: |
| Skill similarity | 40% |
| Responsibility similarity | 25% |
| Role-family similarity | 10% |
| Tools/platform similarity | 10% |
| Seniority compatibility | 5% |
| Domain similarity | 5% |
| Interview-depth similarity | 5% |

The initial algorithm is hierarchical agglomerative clustering because each user is expected to
have a relatively small dataset and the results need to be inspectable. The algorithm and weights
are versioned configuration so they can be evaluated and changed later.

User actions—moving a job, merging or splitting clusters, and excluding jobs—become explicit
constraints. Future clustering runs must preserve those choices unless the user changes them.

Clusters have two levels:

- A logical cluster keeps its user-facing identity and name over time.
- A cluster version records one clustering run's membership and computed profile.

## 9. Fit evaluation

PrepBuddy supports three evaluation levels:

1. Candidate against a target direction before any jobs exist.
2. Candidate against an individual job for lightweight prioritization.
3. Candidate against a cluster, which is the primary input to preparation planning.

The first scoring policy reports an explainable readiness score from 0 to 100:

```text
Skill coverage              0–40
Relevant experience         0–20
Seniority evidence          0–15
Project proof               0–15
Interview readiness         0–10
                           ─────
Overall                     0–100
```

The application distinguishes between a skill being absent, weakly evidenced, explicitly
demonstrated, and demonstrated at the required depth. The scoring policy version is stored with
every evaluation so older results retain their meaning after formulas change.

## 10. Planning stages and stability

| Job descriptions | Stage | Behavior |
| ---: | --- | --- |
| 0 | `BASELINE` | CV- and target-role-based roadmap |
| 1–4 | `EARLY_SIGNAL` | Job-level analysis and early cluster hints |
| 5–9 | `DRAFT_CLUSTER_PLAN` | Draft cluster plan with lower confidence |
| 10–15 | `STABLE_PLAN` | First stable cluster-based plan |
| 15+ | `WEEKLY_REFRESH` | Continuous signals with controlled weekly plan updates |

An active weekly plan is locked for seven days. It is never edited in place. New evidence may
create a proposed plan version, which becomes active only at a refresh boundary or after explicit
user approval.

A major shift is calculated from configurable rules, including:

- A meaningful change in cluster membership
- A skill crossing a frequency threshold
- A new high-confidence cluster
- A sustained change in target-role direction
- A large difference between recent and historical job profiles

Minor or isolated requirements remain market signals and do not modify the plan.

## 11. Data and versioning strategy

PostgreSQL is the source of truth. Relational tables store data used for filtering, counting,
constraints, and scoring. JSONB stores flexible model output, explanations, and snapshot details.

The following records are versioned:

- Candidate profiles
- Job profiles
- Cluster profiles and membership
- Fit evaluations
- Preparation plans

Only one version of a candidate profile, job profile, cluster, or plan may be active at a time.
The database enforces this where possible. See [database.md](database.md) for table-level details.

## 12. Security and privacy

- Encrypt network traffic and managed storage.
- Authorize every read and write against the authenticated user's ownership boundary.
- Do not log raw CV or job-description content.
- Use private object storage and short-lived signed URLs.
- Keep secrets out of source control.
- Support document, candidate, and account deletion.
- Define retention and backup policies before production use.
- Obtain explicit consent before using uploaded content outside the user's requested processing.
- Design for EU GDPR obligations because the initial market includes Ireland and Europe.

Database ownership columns are necessary but do not replace API authorization. PostgreSQL row-level
security can be added as defence in depth when the authentication provider is selected.

## 13. Reliability, observability, and cost control

Background work must be idempotent: retrying the same job must not create duplicate active
profiles, clusters, or plans. Document hashes, extraction-run records, and version constraints
support this behavior.

Production monitoring should cover:

- API error rate and latency
- Queue depth, job duration, retries, and permanent failures
- LLM and embedding latency, token use, and cost
- Extraction confidence and user-correction rate
- Cluster stability and manual reassignment rate
- Plan-proposal acceptance and rejection rate

Cost is controlled by deduplicating documents, caching extraction results, batching embeddings,
recomputing only affected clusters, and using smaller models for structured extraction when their
quality is sufficient.

## 14. Deployment model

The MVP has four deployable runtime components:

1. Next.js web application on Vercel.
2. FastAPI container on Render, Railway, Fly.io, or an equivalent host.
3. A worker container built from the same backend code.
4. Managed PostgreSQL with pgvector, plus managed Redis and object storage.

The API and worker should be independently scalable. Microservices are not planned for the MVP;
a module should be extracted only when operational scale or team ownership provides a concrete
reason.

## 15. MVP implementation order

1. Database and migrations.
2. Backend application skeleton, configuration, and health checks.
3. Authentication and user/candidate ownership.
4. Document upload and text extraction.
5. Candidate-profile extraction, review, and correction.
6. Target-role selection and baseline evaluation.
7. Job-profile extraction and individual fit.
8. Skill normalization, embeddings, and clustering.
9. Cluster-level evaluation and market signals.
10. Versioned plan generation, locking, and change approval.
11. Dashboard and operational monitoring.

## 16. Explicitly deferred from the MVP

- Supporting all professions
- Microservices
- Gmail, calendar, LinkedIn, and job-board integrations
- Automatic job applications
- Career-coach multi-user workflows
- Advanced model training
- A separate vector database
- Per-job resume and cover-letter generation

These features may be added later without changing the core evidence, versioning, clustering, and
planning model.

