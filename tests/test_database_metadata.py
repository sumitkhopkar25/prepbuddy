from app.db import models  # noqa: F401
from app.db.base import Base

EXPECTED_TABLES = {
    "users",
    "candidates",
    "candidate_target_roles",
    "source_documents",
    "extraction_runs",
    "taxonomy_skills",
    "taxonomy_occupations",
    "taxonomy_occupation_skills",
    "skill_aliases",
    "candidate_profile_versions",
    "candidate_skills",
    "job_descriptions",
    "job_profile_versions",
    "job_profile_skills",
    "job_profile_responsibilities",
    "job_profile_tools",
    "job_profile_interview_topics",
    "clusters",
    "clustering_runs",
    "cluster_versions",
    "cluster_memberships",
    "cluster_skill_summaries",
    "fit_evaluations",
    "market_signal_snapshots",
    "market_signals",
    "prep_plans",
    "prep_plan_versions",
    "prep_tasks",
    "plan_change_proposals",
    "evidence_references",
    "user_corrections",
}


def test_all_expected_tables_are_registered() -> None:
    assert set(Base.metadata.tables) == EXPECTED_TABLES


def test_every_foreign_key_has_an_on_delete_policy() -> None:
    foreign_keys = {
        foreign_key for table in Base.metadata.tables.values() for foreign_key in table.foreign_keys
    }

    assert foreign_keys
    assert all(foreign_key.ondelete for foreign_key in foreign_keys)


def test_versioned_entities_have_unique_version_numbers() -> None:
    expected = {
        "candidate_profile_versions": {"candidate_id", "version"},
        "job_profile_versions": {"job_description_id", "version"},
        "cluster_versions": {"cluster_id", "version"},
        "prep_plan_versions": {"prep_plan_id", "version"},
    }

    for table_name, columns in expected.items():
        table = Base.metadata.tables[table_name]
        unique_column_sets = {
            frozenset(column.name for column in constraint.columns)
            for constraint in table.constraints
            if constraint.__class__.__name__ == "UniqueConstraint"
        }
        assert frozenset(columns) in unique_column_sets
