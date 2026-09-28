"""Authentication contracts independent of transport, providers, and persistence."""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class AuthenticatedPrincipal:
    """Verified external subject; does not imply a local user record exists."""

    subject: str


class AuthenticationError(Exception):
    """Base class for expected authentication failures."""


class MissingCredentials(AuthenticationError):
    """No credentials were supplied."""


class InvalidCredentials(AuthenticationError):
    """Credentials are malformed or could not be verified."""


class TokenValidator(Protocol):
    async def validate(self, token: str) -> AuthenticatedPrincipal:
        """Verify a token or raise InvalidCredentials; never log raw credentials."""
        ...


class UnconfiguredTokenValidator:
    """Reject all tokens until a real provider adapter is configured."""

    async def validate(self, token: str) -> AuthenticatedPrincipal:
        raise InvalidCredentials()
