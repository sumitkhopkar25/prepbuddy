from enum import StrEnum


class DocumentType(StrEnum):
    CV = "CV"
    JOB_DESCRIPTION = "JOB_DESCRIPTION"


class ProcessingStatus(StrEnum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class SkillType(StrEnum):
    CORE = "CORE"
    SECONDARY = "SECONDARY"
    WEAK_SIGNAL = "WEAK_SIGNAL"
    REQUIRED = "REQUIRED"
    NICE_TO_HAVE = "NICE_TO_HAVE"


class ClusterStatus(StrEnum):
    ACTIVE = "ACTIVE"
    LOW_PRIORITY = "LOW_PRIORITY"
    ARCHIVED = "ARCHIVED"


class ConfidenceLevel(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class MembershipType(StrEnum):
    AUTOMATIC = "AUTOMATIC"
    USER_ASSIGNED = "USER_ASSIGNED"
    USER_EXCLUDED = "USER_EXCLUDED"


class PlanStage(StrEnum):
    BASELINE = "BASELINE"
    EARLY_SIGNAL = "EARLY_SIGNAL"
    DRAFT_CLUSTER_PLAN = "DRAFT_CLUSTER_PLAN"
    STABLE_PLAN = "STABLE_PLAN"
    WEEKLY_REFRESH = "WEEKLY_REFRESH"


class PlanStatus(StrEnum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    SUPERSEDED = "SUPERSEDED"
    ARCHIVED = "ARCHIVED"


class TaskStatus(StrEnum):
    TODO = "TODO"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    SKIPPED = "SKIPPED"


class ProposalStatus(StrEnum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class SourceType(StrEnum):
    CV = "CV"
    JOB_DESCRIPTION = "JOB_DESCRIPTION"
    USER = "USER"
    TAXONOMY = "TAXONOMY"
    SYSTEM = "SYSTEM"
