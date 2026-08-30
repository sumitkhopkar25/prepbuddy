# PrepBuddy

**PrepBuddy** is an AI-powered job preparation planner that helps candidates turn many job applications into a focused, realistic preparation roadmap.

Unlike traditional job trackers or resume-tailoring tools, PrepBuddy is designed around a core problem: candidates often apply to dozens of jobs at once, but they do not know which skills, projects, and interview topics deserve their limited preparation time.

PrepBuddy analyzes a candidate's CV, target role direction, and multiple job descriptions to identify repeated market patterns, group jobs into dynamic preparation clusters, evaluate the candidate's fit against those clusters, and generate a stable weekly preparation plan.

Existing tools often focus on:

- Resume tailoring
- Cover letter generation
- ATS keyword checks
- Job tracking
- Application autofill
- Generic interview practice

PrepBuddy focuses on a different problem:

> How can a candidate understand the repeated preparation patterns across many jobs and turn them into one focused execution roadmap?

The product helps answer questions such as:

- Which types of roles am I closest to?
- What skills are appearing repeatedly across my target jobs?
- Which gaps matter most for my current job search?
- Should I prepare differently for different branches of the same job domain?
- Which project should I build to improve my interview readiness?
- How do I avoid changing my preparation plan every time I add a new job description?

---

## Product Motivation

The motivation behind PrepBuddy is that job preparation is fragmented.

A candidate usually has:

- A CV in one place
- Job descriptions saved elsewhere
- A spreadsheet or Notion tracker
- Interview prep notes
- Coding practice plans
- System design topics
- Project ideas
- Follow-up reminders

But there is no single system that connects these pieces into a preparation strategy.

PrepBuddy identifies common role patterns and creates preparation clusters. The candidate then prepares for the clusters that matter most.

---

## Core Concept

PrepBuddy is based on four main objects:

```text
Candidate Profile
Job Profile
Cluster Profile
Prep Plan
```

### 1. Candidate Profile

Created from the user's CV and target role direction.

It represents:

- Current role
- Years of experience
- Core skills
- Secondary skills
- Projects
- Domains
- Seniority signals
- Achievements
- Weak areas
- Target role direction

Example:

```json
{
  "current_role": "Software Development Engineer",
  "experience_years": 6,
  "core_skills": ["JavaScript", "Node.js", "SQL", "REST APIs"],
  "secondary_skills": ["CI/CD", "Linux", "Oracle APEX"],
  "target_direction": ["Senior Full-Stack Engineer", "AI Product Engineer"],
  "weak_signals": ["React depth", "AWS deployment", "LLM production experience"]
}
```

---

### 2. Job Profile

Created from each job description uploaded by the user.

It represents:

- Role title
- Seniority
- Required skills
- Nice-to-have skills
- Responsibilities
- Tools/platforms
- Domain
- Work style
- AI relevance
- Likely interview topics

Example:

```json
{
  "job_title": "Senior Full-Stack Engineer",
  "seniority": "Senior",
  "core_skills": ["React", "TypeScript", "Node.js", "PostgreSQL"],
  "secondary_skills": ["AWS", "Docker", "CI/CD"],
  "domain": "Enterprise SaaS",
  "responsibilities": ["build product features", "design APIs", "own delivery"],
  "interview_topics": ["API design", "React architecture", "system design"]
}
```

---

### 3. Cluster Profile

Created by grouping similar job profiles.

A cluster is not manually hardcoded. It is dynamically created from patterns found across the user's uploaded job descriptions. Only the initial clusters before a user has uploaded any jobs come from a base model called ESCO for the initial taxonomy.

Example cluster:

```json
{
  "cluster_name": "Senior Full-Stack TypeScript Roles",
  "jobs_count": 18,
  "required_skills": {
    "TypeScript": 16,
    "React": 15,
    "Node.js": 14,
    "PostgreSQL": 10,
    "AWS": 8
  },
  "common_responsibilities": [
    "build full-stack product features",
    "design APIs",
    "collaborate with product and design",
    "own delivery from design to deployment"
  ],
  "common_interview_topics": [
    "React architecture",
    "API design",
    "database schema design",
    "system design",
    "testing strategy"
  ],
  "confidence": "High"
}
```

---

### 4. Prep Plan

Created from the Candidate Profile and one or more Cluster Profiles.

It represents:

- Active weekly tasks
- Skill priorities
- Project tasks
- Practice topics
- Behavioural interview stories
- CV improvement suggestions
- Plan lock status
- Next refresh date

Example:

```json
{
  "plan_name": "Senior Full-Stack TypeScript Prep Plan",
  "duration_weeks": 4,
  "active_week": 1,
  "locked_until": "2026-07-19",
  "top_priorities": [
    "React architecture",
    "API design",
    "cloud deployment",
    "system design communication"
  ],
  "weekly_tasks": [
    "Build a React + TypeScript dashboard",
    "Create REST API endpoints with Node.js",
    "Deploy MVP to a cloud platform",
    "Prepare one ownership story for behavioural interviews"
  ]
}
```

---

## Recommended User Workflow

PrepBuddy should follow a CV-first workflow.

```text
Upload CV
   ↓
Confirm extracted profile
   ↓
Choose target role direction
   ↓
Get initial recommended role clusters
   ↓
Add job descriptions
   ↓
Jobs are converted into structured job profiles
   ↓
Similar jobs are grouped into dynamic prep clusters
   ↓
CV is evaluated against each cluster
   ↓
App creates a stable weekly preparation plan
```

---

## Why CV First?

The CV acts as the candidate's baseline profile.

Without a CV, the app can only say:

> This job requires React, Node.js, AWS, and system design.

With a CV, the app can say:

> You already have backend, database, and enterprise software experience, but you need stronger React, AWS deployment, and AI project proof for this cluster.

The core value is not just job description analysis. The core value is personalized fit analysis.

---

## Dynamic Prep Clustering

### What Is a Dynamic Prep Cluster?

A dynamic prep cluster is a group of similar job descriptions that share repeated preparation requirements.

Example:

```text
50 uploaded jobs
   ↓
18 jobs look like Full-Stack TypeScript roles
10 jobs look like Backend API roles
8 jobs look like AI Product Engineer roles
5 jobs look like Enterprise SaaS roles
```

Instead of creating 50 separate preparation plans, PrepBuddy creates 4–6 focused cluster-level plans.

---

## Where Do Clusters Come From?

Dynamic clusters come from the job descriptions uploaded by the user.

For each job, the app extracts structured signals:

- Skills
- Tools
- Responsibilities
- Seniority
- Domain
- Role family
- Interview topics
- Work style

Then it compares jobs based on similarity.

A possible similarity scoring model:

```text
Skill overlap: 40%
Responsibility overlap: 25%
Tools/platform overlap: 15%
Domain overlap: 10%
Seniority/interview depth: 10%
```

Jobs with high similarity are grouped into the same cluster.

---

## Predetermined Clusters vs Dynamic Clusters

PrepBuddy should not manually predetermine clusters for every possible profession. That would not scale.

Instead, it should use a hybrid approach:

1. Use a standard occupation and skills taxonomy for broad classification.
2. Dynamically generate preparation clusters from the user's actual job descriptions.

Potential taxonomy sources:

- ESCO: useful for Europe/Ireland-focused occupation and skills mapping
- O*NET: useful for detailed occupation, task, skill, and tool profiles
- ESCO/O*NET crosswalk: useful for interoperability between European and US occupation structures

The taxonomy provides a foundation. The user's uploaded jobs create the final prep clusters.

Example:

```text
Standard taxonomy occupation:
Software Developer

Dynamic prep clusters:
- Senior Full-Stack TypeScript Roles
- Backend API + Database Roles
- AI Product / LLM Application Roles
- Enterprise SaaS Workflow Roles
```

---

## CV Strength Evaluation

The CV should be evaluated at three levels.

### Level 1: Target Direction Fit

Before any job descriptions are added, the CV is evaluated against the user's target direction.

Example:

| Target Role | CV Strength |
|---|---:|
| Senior Full-Stack Engineer | 72% |
| Backend Engineer | 78% |
| AI Product Engineer | 48% |
| Platform Engineer | 45% |

This gives an initial recommendation.

---

### Level 2: Individual Job Fit

Each job description gets a lightweight fit score.

Example:

```text
This role is a 74% match.
Strong match: backend APIs, SQL, enterprise software
Weak match: React, AWS, distributed system design
```

This helps with resume tailoring and prioritization, but it should not create a full preparation plan by itself.

---

### Level 3: Cluster-Level Fit

This is the most important evaluation.

The CV is compared against the cluster profile created from many similar JDs.

Example:

| Dynamic Cluster | CV Strength | Main Gaps |
|---|---:|---|
| Backend API + Database Roles | 82% | cloud deployment, distributed systems |
| Senior Full-Stack TypeScript Roles | 68% | React depth, frontend architecture |
| AI Product / LLM Roles | 52% | RAG, evaluations, vector search, AI project proof |

This cluster-level fit drives the preparation plan.

---

## When Should a Preparation Plan Be Created?

The app should not create a full plan after only one job description. It should use staged planning.

```text
0 JDs:
CV-based baseline roadmap

1–4 JDs:
Job-level analysis only + early cluster hints

5–9 JDs:
Draft cluster plan with low/medium confidence

10–15 JDs:
First stable cluster-based preparation plan

15+ JDs:
Weekly refresh only, unless a major shift is detected
```

Recommended threshold for the first stable plan:

```text
10–15 job descriptions
```

This is enough to identify repeated patterns without delaying value too much.

---

## Preventing Constant Plan Changes

Dynamic clusters may update regularly as new jobs are added. However, the active preparation plan should not change every time a new JD is uploaded.

PrepBuddy should separate:

```text
Market Signals
```

from:

```text
Active Prep Plan
```

### Market Signals

These can update continuously.

Examples:

- React appeared in 65% of jobs this week.
- AWS appeared in 42% of jobs.
- LLM/RAG appeared in 18% of jobs.
- Kubernetes appears only in a small number of outlier roles.

### Active Prep Plan

This should remain stable long enough for the user to execute.

Recommended behavior:

- Lock weekly plans for 7 days.
- Refresh plans weekly.
- Do not rewrite active tasks unless a major shift is detected.
- Ask the user before applying major plan changes.

Example alert:

```text
7 of your latest jobs mention AWS deployment. Add AWS deployment to next week's plan?
```

---

## Plan Stability Rules

### Rule 1: Do not change the active weekly plan for minor signals

Example:

```text
One new JD mentions GraphQL.
```

This should not change the plan.

---

### Rule 2: Suggest updates only for major shifts

Example:

```text
12 of the latest 20 jobs mention Python/FastAPI, and the user is now applying heavily to backend Python roles.
```

The app can suggest a roadmap update.

---

### Rule 3: Use confidence levels

Example:

| Cluster | Jobs | Confidence | Plan Status |
|---|---:|---:|---|
| Senior Full-Stack TypeScript | 14 | High | Active plan |
| AI Product / LLM Apps | 5 | Medium | Secondary plan |
| Platform Engineering | 2 | Low | Watch only |

Only high-confidence clusters should drive the main preparation plan.

---

### Rule 4: Let the user control changes

The user should be able to:

- Merge clusters
- Split clusters
- Rename clusters
- Move jobs between clusters
- Mark clusters as low priority
- Accept or reject plan updates
- Lock the plan for a week

---

## Suggested MVP Scope

### MVP Goal

Build a working version that demonstrates the full product logic without trying to support every advanced feature.

### MVP Features

#### 1. CV Upload / Paste

- User uploads or pastes a CV.
- App extracts candidate profile.
- User can confirm or edit extracted details.

#### 2. Target Role Selection

User chooses target directions such as:

- Senior Full-Stack Engineer
- Backend Engineer
- AI Product Engineer
- Platform Engineer
- Data Engineer
- Not sure yet

#### 3. Job Description Input

- User pastes job descriptions.
- Each JD is converted into a structured job profile.

#### 4. Dynamic Clustering

- App groups similar jobs.
- App generates cluster names.
- App shows cluster confidence.

#### 5. Cluster-Level CV Evaluation

- App compares the candidate profile against each cluster.
- App identifies strengths and gaps.

#### 6. Preparation Plan Generation

- App creates a baseline plan after CV input.
- App creates a draft plan after 5+ JDs.
- App creates a stable plan after 10–15 JDs.

#### 7. Plan Locking

- Active plan is locked for 7 days.
- New JDs update market signals but do not automatically rewrite the plan.

#### 8. Dashboard

Dashboard should show:

- Active role clusters
- CV strength per cluster
- Top skill gaps
- Active weekly plan
- Market signal changes
- Recommended project tasks

---

## Possible Tech Stack

### Frontend

```text
React
TypeScript
Tailwind CSS
```

### Backend

```text
Node.js + NestJS
```

or

```text
Python + FastAPI
```

### Database

```text
PostgreSQL
```

Optional:

```text
pgvector
```

for embedding-based similarity search.

### AI Layer

Use an LLM for:

- CV parsing
- JD parsing
- Skill extraction
- Cluster naming
- Gap analysis
- Plan generation

Use embeddings for:

- JD similarity
- Cluster grouping
- Similar job retrieval

### Deployment

Potential options:

```text
Vercel for frontend
Render / Railway / Fly.io for backend
Supabase / Neon for PostgreSQL
```

---

## Suggested Data Model

### Candidate

```text
id
name
current_role
experience_years
target_roles
created_at
updated_at
```

### CandidateSkill

```text
id
candidate_id
skill_name
skill_type
confidence
source
```

### JobDescription

```text
id
candidate_id
company_name
job_title
raw_text
status
created_at
updated_at
```

### JobProfile

```text
id
job_description_id
seniority
role_family
domain
core_skills
secondary_skills
responsibilities
tools
interview_topics
embedding
```

### Cluster

```text
id
candidate_id
name
confidence
status
created_at
updated_at
```

### ClusterJob

```text
id
cluster_id
job_description_id
membership_type
similarity_score
```

### ClusterProfile

```text
id
cluster_id
required_skills_summary
common_responsibilities
common_tools
common_interview_topics
market_signal_summary
```

### FitEvaluation

```text
id
candidate_id
cluster_id
overall_score
skill_score
experience_score
seniority_score
project_proof_score
interview_readiness_score
strengths
gaps
recommendations
```

### PrepPlan

```text
id
candidate_id
cluster_id
name
status
plan_stage
locked_until
created_at
updated_at
```

### PrepTask

```text
id
prep_plan_id
title
description
task_type
priority
status
due_date
```

---

## Plan Stages

```text
BASELINE
EARLY_SIGNAL
DRAFT_CLUSTER_PLAN
STABLE_PLAN
WEEKLY_REFRESH
```

### BASELINE

Created after CV upload and target role selection.

### EARLY_SIGNAL

Created after 1–4 job descriptions.

### DRAFT_CLUSTER_PLAN

Created after 5–9 job descriptions.

### STABLE_PLAN

Created after 10–15 job descriptions.

### WEEKLY_REFRESH

Created after stable planning begins. New JDs update market signals, but the active plan changes only during weekly refresh or after user approval.

---

## Example User Scenario

A user uploads their CV and says they are targeting senior software engineering roles.

The app identifies:

```text
Strengths:
- Backend APIs
- SQL
- Enterprise product experience
- CI/CD exposure

Weak signals:
- React depth
- Cloud deployment
- LLM project proof
- System design communication
```

The user then adds 20 job descriptions.

PrepBuddy creates these clusters:

| Cluster | Jobs | Confidence |
|---|---:|---:|
| Senior Full-Stack TypeScript Roles | 9 | High |
| Backend API + Database Roles | 6 | High |
| AI Product / LLM Roles | 4 | Medium |
| Platform / Cloud Engineering Roles | 1 | Low |

The app evaluates the CV against each cluster:

| Cluster | CV Strength | Main Gap |
|---|---:|---|
| Backend API + Database Roles | 82% | Cloud deployment |
| Senior Full-Stack TypeScript Roles | 68% | React architecture |
| AI Product / LLM Roles | 52% | RAG and AI project proof |

The app creates a 4-week preparation plan focused on:

- React + TypeScript project feature
- API design
- Cloud deployment
- System design practice
- AI feature proof-of-work
- Behavioural stories around ownership and debugging

---

## Future Enhancements

Potential future features:

- Gmail integration for job application tracking
- LinkedIn/job board import
- Calendar-based prep scheduling
- Interview stage tracking
- Resume tailoring per cluster
- Cover letter generation
- Mock interview generation
- Behavioural story builder
- Project recommendation engine
- Progress analytics
- Skill trend dashboard
- Multi-user support for career coaches

---

## Project Differentiation

PrepBuddy is not just a job tracker.

It is not just a resume tailoring tool.

It is not just a generic interview prep app.

Its core differentiator is:

> It identifies preparation patterns across many job descriptions and converts them into a stable execution plan.

---

## MVP Success Criteria

The MVP is successful if it can:

- Parse a CV into a candidate profile
- Parse multiple JDs into structured job profiles
- Group similar jobs into meaningful clusters
- Evaluate CV strength against each cluster
- Identify repeated skill gaps
- Create a weekly preparation plan
- Avoid changing the active plan every time a new JD is added
- Explain its recommendations clearly to the user

---

## Final Summary

PrepBuddy helps candidates move from application chaos to focused preparation.

---

## Database Implementation

The initial PostgreSQL database layer is implemented with SQLAlchemy, Alembic, and pgvector.
See [docs/database.md](docs/database.md) for the schema organization and local setup.
