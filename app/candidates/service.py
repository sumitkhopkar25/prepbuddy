"""Candidate persistence using caller-owned dedicated database sessions."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.candidates import CandidateAlreadyExists, CandidateNotFound
from app.candidates.schemas import CandidateCreate
from app.db.models import Candidate


def get_candidate_for_user(session: Session, user_id: UUID) -> Candidate:
    """Retrieve the owner's stored row, including retained soft-deleted candidates."""
    try:
        candidate = session.scalar(select(Candidate).where(Candidate.user_id == user_id))
    except SQLAlchemyError:
        session.rollback()
        raise
    if candidate is None:
        raise CandidateNotFound()
    return candidate


def create_candidate(session: Session, user_id: UUID, data: CandidateCreate) -> Candidate:
    """Commit one candidate; let the ownership constraint arbitrate concurrent requests."""
    try:
        candidate = Candidate(user_id=user_id, **data.model_dump())
        session.add(candidate)
        session.commit()
        return candidate
    except SQLAlchemyError as error:
        session.rollback()
        if (
            isinstance(error, IntegrityError)
            and getattr(error.orig, "sqlstate", None) == "23505"
            and getattr(getattr(error.orig, "diag", None), "constraint_name", None)
            == "uq_candidates_user_id"
        ):
            raise CandidateAlreadyExists() from None
        raise
