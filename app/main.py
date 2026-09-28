"""ASGI entry point for the PrepBuddy API."""

from typing import Annotated

from fastapi import Depends, FastAPI

from app.identity.dependencies import get_current_principal
from app.identity.service import AuthenticatedPrincipal


def create_app() -> FastAPI:
    application = FastAPI(title="PrepBuddy", version="0.1.0")

    @application.get("/health")
    async def health() -> dict[str, str]:
        """Report process liveness without checking external dependencies."""
        return {"status": "ok"}

    @application.get("/me")
    async def me(
        principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    ) -> dict[str, str]:
        """Return the verified external subject without resolving a database user."""
        return {"subject": principal.subject}

    return application


app = create_app()
