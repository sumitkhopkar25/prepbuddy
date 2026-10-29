"""ASGI entry point for the PrepBuddy API."""

from typing import Annotated
from uuid import UUID

from fastapi import Depends, FastAPI

from app.candidates.dependencies import create_owned_candidate, get_owned_candidate
from app.candidates.schemas import CandidateCreate, CandidateResponse
from app.identity.dependencies import get_current_user
from app.identity.service import LocalUser


def create_app() -> FastAPI:
    application = FastAPI(title="PrepBuddy", version="0.1.0")

    @application.get("/health")
    async def health() -> dict[str, str]:
        """Report process liveness without checking external dependencies."""
        return {"status": "ok"}

    @application.get("/me")
    async def me(
        user: Annotated[LocalUser, Depends(get_current_user)],
    ) -> dict[str, str]:
        """Return the persistent local identity for the verified external subject."""
        return {"id": user.id, "subject": user.subject}

    @application.post("/candidates", status_code=201, response_model=CandidateResponse)
    def create_candidate(
        data: CandidateCreate,
        user: Annotated[LocalUser, Depends(get_current_user)],
    ) -> CandidateResponse:
        """Create the authenticated user's candidate once."""
        return create_owned_candidate(UUID(user.id), data)

    @application.get("/candidates/me", response_model=CandidateResponse)
    def current_candidate(
        user: Annotated[LocalUser, Depends(get_current_user)],
    ) -> CandidateResponse:
        """Return the authenticated user's candidate baseline."""
        return get_owned_candidate(UUID(user.id))

    return application


app = create_app()
