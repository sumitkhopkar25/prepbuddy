"""ASGI entry point for the PrepBuddy API."""

from typing import Annotated

from fastapi import Depends, FastAPI

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

    return application


app = create_app()
