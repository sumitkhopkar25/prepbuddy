"""FastAPI bearer authentication wiring."""

import re
from typing import Annotated

from fastapi import Depends, HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.identity.service import (
    AuthenticatedPrincipal,
    AuthenticationError,
    InvalidCredentials,
    MissingCredentials,
    TokenValidator,
    UnconfiguredTokenValidator,
)

bearer = HTTPBearer(auto_error=False)


def get_token_validator() -> TokenValidator:
    """Override this dependency with a provider adapter to enable authentication."""
    return UnconfiguredTokenValidator()


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
    except AuthenticationError:
        raise HTTPException(
            status_code=401,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None
