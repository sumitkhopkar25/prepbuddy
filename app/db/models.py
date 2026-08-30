from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.enums import (
    ClusterStatus,
    ConfidenceLevel,
    DocumentType,
    MembershipType,
    PlanStage,
    PlanStatus,
    ProcessingStatus,
    ProposalStatus,
    SkillType,
    SourceType,
    TaskStatus,
)

EMBEDDING_DIMENSIONS = 1536


def string_enum(enum_type: type, name: str) -> Enum:
    return Enum(
        enum_type,
        name=name,
        native_enum=False,
        create_constraint=True,
        validate_strings=True,
    )


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "users"

    auth_provider_subject: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    email: Mapped[str | None] = mapped_column(String(320))
    display_name: Mapped[str | None] = mapped_column(String(200))
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, server_default="UTC")
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Candidate(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "candidates"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str | None] = mapped_column(String(200))
    current_role: Mapped[str | None] = mapped_column(String(200))
    experience_years: Mapped[Decimal | None] = mapped_column(Numeric(4, 1))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint(
            "experience_years IS NULL OR experience_years >= 0",
            name="experience_years_non_negative",
        ),
        Index("ix_candidates_user_id", "user_id"),
    )


class CandidateTargetRole(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "candidate_target_roles"

    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False
    )
    taxonomy_occupation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("taxonomy_occupations.id", ondelete="SET NULL")
    )
    role_name: Mapped[str] = mapped_column(String(200), nullable=False)
    role_family: Mapped[str | None] = mapped_column(String(120))
    priority: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))

    __table_args__ = (
        UniqueConstraint("candidate_id", "role_name"),
        CheckConstraint("priority > 0", name="priority_positive"),
    )


class SourceDocument(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "source_documents"

    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False
    )
    document_type: Mapped[DocumentType] = mapped_column(
        string_enum(DocumentType, "document_type"), nullable=False
    )
    original_filename: Mapped[str | None] = mapped_column(String(512))
    storage_key: Mapped[str | None] = mapped_column(String(1024))
    mime_type: Mapped[str | None] = mapped_column(String(100))
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    extracted_text: Mapped[str | None] = mapped_column(Text)
    status: Mapped[ProcessingStatus] = mapped_column(
        string_enum(ProcessingStatus, "processing_status"),
        nullable=False,
        server_default=ProcessingStatus.PENDING.value,
    )
    error_message: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        UniqueConstraint("candidate_id", "document_type", "content_hash"),
        Index("ix_source_documents_candidate_status", "candidate_id", "status"),
    )


class ExtractionRun(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "extraction_runs"

    source_document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("source_documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[ProcessingStatus] = mapped_column(
        string_enum(ProcessingStatus, "extraction_status"), nullable=False
    )
    model_provider: Mapped[str | None] = mapped_column(String(100))
    model_name: Mapped[str | None] = mapped_column(String(200))
    prompt_version: Mapped[str] = mapped_column(String(50), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(50), nullable=False)
    raw_output: Mapped[dict | None] = mapped_column(JSONB)
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("ix_extraction_runs_document_started", "source_document_id", "started_at"),
    )


class TaxonomySkill(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "taxonomy_skills"

    taxonomy: Mapped[str] = mapped_column(String(50), nullable=False)
    external_id: Mapped[str | None] = mapped_column(String(255))
    canonical_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    skill_category: Mapped[str | None] = mapped_column(String(100))

    __table_args__ = (
        UniqueConstraint("taxonomy", "external_id", name="uq_taxonomy_skills_taxonomy_external_id"),
        UniqueConstraint(
            "taxonomy", "canonical_name", name="uq_taxonomy_skills_taxonomy_canonical_name"
        ),
    )


class TaxonomyOccupation(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "taxonomy_occupations"

    taxonomy: Mapped[str] = mapped_column(String(50), nullable=False)
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    preferred_label: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    parent_external_id: Mapped[str | None] = mapped_column(String(255))

    __table_args__ = (
        UniqueConstraint(
            "taxonomy", "external_id", name="uq_taxonomy_occupations_taxonomy_external_id"
        ),
    )


class TaxonomyOccupationSkill(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "taxonomy_occupation_skills"

    taxonomy_occupation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("taxonomy_occupations.id", ondelete="CASCADE"),
        nullable=False,
    )
    taxonomy_skill_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("taxonomy_skills.id", ondelete="CASCADE"), nullable=False
    )
    relationship_type: Mapped[str] = mapped_column(String(50), nullable=False)
    importance: Mapped[float | None] = mapped_column(Float)

    __table_args__ = (
        UniqueConstraint("taxonomy_occupation_id", "taxonomy_skill_id", "relationship_type"),
        CheckConstraint(
            "importance IS NULL OR importance BETWEEN 0 AND 1", name="importance_range"
        ),
    )


class SkillAlias(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "skill_aliases"

    taxonomy_skill_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("taxonomy_skills.id", ondelete="CASCADE"), nullable=False
    )
    alias: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_alias: Mapped[str] = mapped_column(String(255), nullable=False)

    __table_args__ = (UniqueConstraint("taxonomy_skill_id", "normalized_alias"),)


class CandidateProfileVersion(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "candidate_profile_versions"

    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False
    )
    source_document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("source_documents.id", ondelete="SET NULL")
    )
    extraction_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("extraction_runs.id", ondelete="SET NULL")
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    current_role: Mapped[str | None] = mapped_column(String(200))
    experience_years: Mapped[Decimal | None] = mapped_column(Numeric(4, 1))
    projects: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    domains: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    achievements: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    seniority_signals: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    confidence: Mapped[float | None] = mapped_column(Float)
    is_user_confirmed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        UniqueConstraint("candidate_id", "version"),
        CheckConstraint("version > 0", name="version_positive"),
        CheckConstraint(
            "confidence IS NULL OR confidence BETWEEN 0 AND 1", name="confidence_range"
        ),
        Index(
            "uq_candidate_profile_versions_one_active",
            "candidate_id",
            unique=True,
            postgresql_where=text("is_active"),
        ),
    )


class CandidateSkill(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "candidate_skills"

    candidate_profile_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("candidate_profile_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    taxonomy_skill_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("taxonomy_skills.id", ondelete="SET NULL")
    )
    skill_name: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(255), nullable=False)
    skill_type: Mapped[SkillType] = mapped_column(
        string_enum(SkillType, "candidate_skill_type"), nullable=False
    )
    proficiency: Mapped[str | None] = mapped_column(String(50))
    confidence: Mapped[float | None] = mapped_column(Float)
    source_type: Mapped[SourceType] = mapped_column(
        string_enum(SourceType, "candidate_skill_source_type"), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("candidate_profile_version_id", "normalized_name", "skill_type"),
        CheckConstraint(
            "confidence IS NULL OR confidence BETWEEN 0 AND 1", name="confidence_range"
        ),
    )


class JobDescription(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "job_descriptions"

    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False
    )
    source_document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("source_documents.id", ondelete="RESTRICT"), nullable=False
    )
    company_name: Mapped[str | None] = mapped_column(String(255))
    job_title: Mapped[str | None] = mapped_column(String(255))
    source_url: Mapped[str | None] = mapped_column(Text)
    application_status: Mapped[str | None] = mapped_column(String(50))
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))

    __table_args__ = (
        UniqueConstraint("source_document_id"),
        Index("ix_job_descriptions_candidate_created", "candidate_id", "created_at"),
    )


class JobProfileVersion(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "job_profile_versions"

    job_description_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("job_descriptions.id", ondelete="CASCADE"), nullable=False
    )
    extraction_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("extraction_runs.id", ondelete="SET NULL")
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    seniority: Mapped[str | None] = mapped_column(String(100))
    role_family: Mapped[str | None] = mapped_column(String(150))
    domain: Mapped[str | None] = mapped_column(String(150))
    work_style: Mapped[str | None] = mapped_column(String(100))
    ai_relevance: Mapped[float | None] = mapped_column(Float)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIMENSIONS))
    embedding_model: Mapped[str | None] = mapped_column(String(200))
    confidence: Mapped[float | None] = mapped_column(Float)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        UniqueConstraint("job_description_id", "version"),
        CheckConstraint("version > 0", name="version_positive"),
        CheckConstraint(
            "ai_relevance IS NULL OR ai_relevance BETWEEN 0 AND 1", name="ai_relevance_range"
        ),
        CheckConstraint(
            "confidence IS NULL OR confidence BETWEEN 0 AND 1", name="confidence_range"
        ),
        Index(
            "uq_job_profile_versions_one_active",
            "job_description_id",
            unique=True,
            postgresql_where=text("is_active"),
        ),
    )


class JobProfileSkill(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "job_profile_skills"

    job_profile_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("job_profile_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    taxonomy_skill_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("taxonomy_skills.id", ondelete="SET NULL")
    )
    skill_name: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(255), nullable=False)
    skill_type: Mapped[SkillType] = mapped_column(
        string_enum(SkillType, "job_skill_type"), nullable=False
    )
    confidence: Mapped[float | None] = mapped_column(Float)
    evidence_text: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        UniqueConstraint("job_profile_version_id", "normalized_name", "skill_type"),
        CheckConstraint(
            "confidence IS NULL OR confidence BETWEEN 0 AND 1", name="confidence_range"
        ),
    )


class JobProfileResponsibility(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "job_profile_responsibilities"

    job_profile_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("job_profile_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_category: Mapped[str | None] = mapped_column(String(200))

    __table_args__ = (UniqueConstraint("job_profile_version_id", "position"),)


class JobProfileTool(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "job_profile_tools"

    job_profile_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("job_profile_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    tool_name: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(255), nullable=False)

    __table_args__ = (UniqueConstraint("job_profile_version_id", "normalized_name"),)


class JobProfileInterviewTopic(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "job_profile_interview_topics"

    job_profile_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("job_profile_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    topic: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_topic: Mapped[str] = mapped_column(String(255), nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float)

    __table_args__ = (UniqueConstraint("job_profile_version_id", "normalized_topic"),)


class Cluster(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "clusters"

    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[ClusterStatus] = mapped_column(
        string_enum(ClusterStatus, "cluster_status"),
        nullable=False,
        server_default=ClusterStatus.ACTIVE.value,
    )
    user_locked: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))

    __table_args__ = (Index("ix_clusters_candidate_status", "candidate_id", "status"),)


class ClusteringRun(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "clustering_runs"

    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[ProcessingStatus] = mapped_column(
        string_enum(ProcessingStatus, "clustering_run_status"), nullable=False
    )
    algorithm_version: Mapped[str] = mapped_column(String(50), nullable=False)
    input_jobs_count: Mapped[int] = mapped_column(Integer, nullable=False)
    parameters: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint("input_jobs_count >= 0", name="input_jobs_count_non_negative"),
        Index("ix_clustering_runs_candidate_started", "candidate_id", "started_at"),
    )


class ClusterVersion(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "cluster_versions"

    cluster_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clusters.id", ondelete="CASCADE"), nullable=False
    )
    clustering_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clustering_runs.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    generated_name: Mapped[str] = mapped_column(String(255), nullable=False)
    confidence: Mapped[ConfidenceLevel] = mapped_column(
        string_enum(ConfidenceLevel, "cluster_confidence"), nullable=False
    )
    confidence_score: Mapped[float | None] = mapped_column(Float)
    common_responsibilities: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    common_tools: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    common_interview_topics: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    market_signal_summary: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    algorithm_version: Mapped[str] = mapped_column(String(50), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        UniqueConstraint("cluster_id", "version"),
        CheckConstraint("version > 0", name="version_positive"),
        CheckConstraint(
            "confidence_score IS NULL OR confidence_score BETWEEN 0 AND 1",
            name="confidence_score_range",
        ),
        Index(
            "uq_cluster_versions_one_active",
            "cluster_id",
            unique=True,
            postgresql_where=text("is_active"),
        ),
    )


class ClusterMembership(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "cluster_memberships"

    cluster_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cluster_versions.id", ondelete="CASCADE"), nullable=False
    )
    job_profile_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("job_profile_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    membership_type: Mapped[MembershipType] = mapped_column(
        string_enum(MembershipType, "membership_type"), nullable=False
    )
    similarity_score: Mapped[float | None] = mapped_column(Float)
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        UniqueConstraint("cluster_version_id", "job_profile_version_id"),
        CheckConstraint(
            "similarity_score IS NULL OR similarity_score BETWEEN 0 AND 1",
            name="similarity_score_range",
        ),
    )


class ClusterSkillSummary(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "cluster_skill_summaries"

    cluster_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cluster_versions.id", ondelete="CASCADE"), nullable=False
    )
    taxonomy_skill_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("taxonomy_skills.id", ondelete="SET NULL")
    )
    skill_name: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(255), nullable=False)
    skill_type: Mapped[SkillType] = mapped_column(
        string_enum(SkillType, "cluster_skill_type"), nullable=False
    )
    job_count: Mapped[int] = mapped_column(Integer, nullable=False)
    frequency: Mapped[float] = mapped_column(Float, nullable=False)

    __table_args__ = (
        UniqueConstraint("cluster_version_id", "normalized_name", "skill_type"),
        CheckConstraint("job_count >= 0", name="job_count_non_negative"),
        CheckConstraint("frequency BETWEEN 0 AND 1", name="frequency_range"),
    )


class FitEvaluation(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "fit_evaluations"

    candidate_profile_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("candidate_profile_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    candidate_target_role_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidate_target_roles.id", ondelete="CASCADE")
    )
    cluster_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cluster_versions.id", ondelete="CASCADE")
    )
    job_profile_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("job_profile_versions.id", ondelete="CASCADE")
    )
    evaluation_version: Mapped[int] = mapped_column(Integer, nullable=False)
    scoring_policy_version: Mapped[str] = mapped_column(String(50), nullable=False)
    overall_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    skill_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    experience_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    seniority_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    project_proof_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    interview_readiness_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    strengths: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    gaps: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    recommendations: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    score_breakdown: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        CheckConstraint(
            "((candidate_target_role_id IS NOT NULL)::integer + "
            "(cluster_version_id IS NOT NULL)::integer + "
            "(job_profile_version_id IS NOT NULL)::integer) = 1",
            name="exactly_one_evaluation_target",
        ),
        CheckConstraint("overall_score BETWEEN 0 AND 100", name="overall_score_range"),
        CheckConstraint("skill_score BETWEEN 0 AND 100", name="skill_score_range"),
        CheckConstraint("experience_score BETWEEN 0 AND 100", name="experience_score_range"),
        CheckConstraint("seniority_score BETWEEN 0 AND 100", name="seniority_score_range"),
        CheckConstraint("project_proof_score BETWEEN 0 AND 100", name="project_proof_score_range"),
        CheckConstraint(
            "interview_readiness_score BETWEEN 0 AND 100", name="interview_readiness_score_range"
        ),
        Index("ix_fit_evaluations_target_role_created", "candidate_target_role_id", "created_at"),
        Index("ix_fit_evaluations_cluster_created", "cluster_version_id", "created_at"),
        Index("ix_fit_evaluations_job_created", "job_profile_version_id", "created_at"),
    )


class MarketSignalSnapshot(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "market_signal_snapshots"

    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False
    )
    cluster_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cluster_versions.id", ondelete="CASCADE")
    )
    window_start: Mapped[date] = mapped_column(Date, nullable=False)
    window_end: Mapped[date] = mapped_column(Date, nullable=False)
    jobs_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        CheckConstraint("window_end >= window_start", name="valid_window"),
        CheckConstraint("jobs_count >= 0", name="jobs_count_non_negative"),
        Index("ix_market_signal_snapshots_candidate_window", "candidate_id", "window_end"),
    )


class MarketSignal(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "market_signals"

    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("market_signal_snapshots.id", ondelete="CASCADE"),
        nullable=False,
    )
    signal_type: Mapped[str] = mapped_column(String(50), nullable=False)
    signal_key: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    occurrence_count: Mapped[int] = mapped_column(Integer, nullable=False)
    frequency: Mapped[float] = mapped_column(Float, nullable=False)
    change_from_previous: Mapped[float | None] = mapped_column(Float)
    is_major_shift: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )

    __table_args__ = (
        UniqueConstraint("snapshot_id", "signal_type", "signal_key"),
        CheckConstraint("occurrence_count >= 0", name="occurrence_count_non_negative"),
        CheckConstraint("frequency BETWEEN 0 AND 1", name="frequency_range"),
    )


class PrepPlan(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "prep_plans"

    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False
    )
    cluster_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clusters.id", ondelete="SET NULL")
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))

    __table_args__ = (Index("ix_prep_plans_candidate_archived", "candidate_id", "is_archived"),)


class PrepPlanVersion(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "prep_plan_versions"

    prep_plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("prep_plans.id", ondelete="CASCADE"), nullable=False
    )
    based_on_cluster_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cluster_versions.id", ondelete="SET NULL")
    )
    based_on_fit_evaluation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("fit_evaluations.id", ondelete="SET NULL")
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[PlanStatus] = mapped_column(
        string_enum(PlanStatus, "plan_status"), nullable=False
    )
    plan_stage: Mapped[PlanStage] = mapped_column(
        string_enum(PlanStage, "plan_stage"), nullable=False
    )
    duration_weeks: Mapped[int] = mapped_column(Integer, nullable=False)
    active_week: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    top_priorities: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    rationale: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        UniqueConstraint("prep_plan_id", "version"),
        CheckConstraint("version > 0", name="version_positive"),
        CheckConstraint("duration_weeks > 0", name="duration_weeks_positive"),
        CheckConstraint("active_week BETWEEN 1 AND duration_weeks", name="active_week_valid"),
        Index(
            "uq_prep_plan_versions_one_active",
            "prep_plan_id",
            unique=True,
            postgresql_where=text("status = 'ACTIVE'"),
        ),
    )


class PrepTask(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "prep_tasks"

    prep_plan_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("prep_plan_versions.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    task_type: Mapped[str] = mapped_column(String(50), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[TaskStatus] = mapped_column(
        string_enum(TaskStatus, "task_status"),
        nullable=False,
        server_default=TaskStatus.TODO.value,
    )
    week_number: Mapped[int] = mapped_column(Integer, nullable=False)
    due_date: Mapped[date | None] = mapped_column(Date)
    source_recommendation: Mapped[dict | None] = mapped_column(JSONB)

    __table_args__ = (
        CheckConstraint("priority > 0", name="priority_positive"),
        CheckConstraint("week_number > 0", name="week_number_positive"),
        Index("ix_prep_tasks_plan_week", "prep_plan_version_id", "week_number"),
    )


class PlanChangeProposal(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "plan_change_proposals"

    prep_plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("prep_plans.id", ondelete="CASCADE"), nullable=False
    )
    source_plan_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("prep_plan_versions.id", ondelete="CASCADE"), nullable=False
    )
    market_signal_snapshot_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("market_signal_snapshots.id", ondelete="SET NULL")
    )
    status: Mapped[ProposalStatus] = mapped_column(
        string_enum(ProposalStatus, "proposal_status"),
        nullable=False,
        server_default=ProposalStatus.PENDING.value,
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    proposed_changes: Mapped[dict] = mapped_column(JSONB, nullable=False)
    major_shift_score: Mapped[float | None] = mapped_column(Float)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint(
            "major_shift_score IS NULL OR major_shift_score BETWEEN 0 AND 1",
            name="major_shift_score_range",
        ),
        Index("ix_plan_change_proposals_plan_status", "prep_plan_id", "status"),
    )


class EvidenceReference(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "evidence_references"

    source_document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("source_documents.id", ondelete="CASCADE"), nullable=False
    )
    entity_type: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    field_name: Mapped[str] = mapped_column(String(100), nullable=False)
    excerpt: Mapped[str] = mapped_column(Text, nullable=False)
    start_offset: Mapped[int | None] = mapped_column(Integer)
    end_offset: Mapped[int | None] = mapped_column(Integer)
    confidence: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        CheckConstraint(
            "start_offset IS NULL OR end_offset IS NULL OR end_offset >= start_offset",
            name="valid_offsets",
        ),
        CheckConstraint(
            "confidence IS NULL OR confidence BETWEEN 0 AND 1", name="confidence_range"
        ),
        Index("ix_evidence_references_entity", "entity_type", "entity_id"),
    )


class UserCorrection(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "user_corrections"

    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False
    )
    entity_type: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    field_name: Mapped[str] = mapped_column(String(100), nullable=False)
    previous_value: Mapped[object | None] = mapped_column(JSONB)
    corrected_value: Mapped[object] = mapped_column(JSONB, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (Index("ix_user_corrections_entity", "entity_type", "entity_id"),)
