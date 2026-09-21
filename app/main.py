"""ASGI entry point for the PrepBuddy API."""

from fastapi import FastAPI


def create_app() -> FastAPI:
    application = FastAPI(title="PrepBuddy", version="0.1.0")

    @application.get("/health")
    async def health() -> dict[str, str]:
        """Report process liveness without checking external dependencies."""
        return {"status": "ok"}

    return application


app = create_app()
