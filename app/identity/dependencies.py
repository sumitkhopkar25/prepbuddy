"""FastAPI bearer authentication wiring."""

import re
from typing import Annotated

from fastapi import Depends, HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.identity.service import (
    AuthenticatedPrincipal,
    AuthenticationError,
    AuthenticationUnavailable,
    InvalidCredentials,
    LocalUser,
    MissingCredentials,
    TokenValidator,
)

bearer = HTTPBearer(auto_error=False)


def get_token_validator() -> TokenValidator:
    """Import the provider lazily to preserve independent application liveness."""
    from app.identity.auth0 import Auth0TokenValidator

    return Auth0TokenValidator()


async def get_current_principal(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Security(bearer)],
    validator: Annotated[TokenValidator, Depends(get_token_validator)],
) -> AuthenticatedPrincipal:
    try:
        if credentials is None:
            raise MissingCredentials()
        # RFC 6750 bearer-token syntax; verification belongs to the adapter.
        if not re.fullmatch(r"[A-Za-z0-9._~+/-]+=*", credentials.credentials):
            raise InvalidCredentials()
        return await validator.validate(credentials.credentials)
    except AuthenticationUnavailable:
        raise HTTPException(status_code=503, detail="Authentication service unavailable") from None
    except AuthenticationError:
        raise HTTPException(
            status_code=401,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None


def resolve_local_user(principal: AuthenticatedPrincipal) -> "LocalUser":
    """Load persistence lazily, only after authentication has succeeded."""
    from app.db.session import SessionLocal
    from app.identity.user_service import resolve_user

    with SessionLocal() as session:
        user = resolve_user(principal, session)
        return LocalUser(id=str(user.id), subject=user.auth_provider_subject)


def get_current_user(
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
) -> "LocalUser":
    # This synchronous dependency runs database work in FastAPI's thread pool.
    try:
        return resolve_local_user(principal)
    except Exception:  # noqa: BLE001 - sanitize all persistence/configuration failures
        # Includes unavailable database configuration and session construction failures.
        raise HTTPException(status_code=503, detail="Identity service unavailable") from None
