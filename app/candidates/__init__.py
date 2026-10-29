"""Candidate onboarding and ownership."""


class CandidateAlreadyExists(Exception):
    """The authenticated user already owns a retained candidate."""


class CandidateNotFound(Exception):
    """The authenticated user has no candidate."""
