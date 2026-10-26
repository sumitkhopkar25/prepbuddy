"""Create a candidate using a caller-owned dedicated database session."""

from uuid import UUID

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.candidates import CandidateAlreadyExists
from app.candidates.schemas import CandidateCreate
from app.db.models import Candidate


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
