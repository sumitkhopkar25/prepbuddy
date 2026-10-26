"""Lazy candidate persistence and sanitized HTTP errors."""

from uuid import UUID

from fastapi import HTTPException

from app.candidates import CandidateAlreadyExists
from app.candidates.schemas import CandidateCreate, CandidateResponse


def persist_candidate(user_id: UUID, data: CandidateCreate) -> CandidateResponse:
    """Materialize the response before closing the dedicated session."""
    from app.candidates.service import create_candidate
    from app.db.session import SessionLocal

    with SessionLocal() as session:
        candidate = create_candidate(session, user_id, data)
        return CandidateResponse.model_validate(candidate)


def create_owned_candidate(user_id: UUID, data: CandidateCreate) -> CandidateResponse:
    try:
        return persist_candidate(user_id, data)
    except CandidateAlreadyExists:
        raise HTTPException(status_code=409, detail="Candidate already exists") from None
    except Exception:  # noqa: BLE001 - sanitize persistence and configuration failures
        raise HTTPException(status_code=503, detail="Candidate service unavailable") from None
