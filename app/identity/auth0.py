"""Auth0 access-token verification for one configured issuer and API audience."""

import re
from functools import lru_cache

import jwt
from fastapi.concurrency import run_in_threadpool
from jwt import PyJWKClient
from jwt.exceptions import PyJWKClientConnectionError, PyJWKClientError
from pydantic import ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.identity.service import (
    AuthenticatedPrincipal,
    AuthenticationUnavailable,
    InvalidCredentials,
)


class Auth0Settings(BaseSettings):
    auth0_domain: str = ""
    auth0_audience: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @field_validator("auth0_domain")
    @classmethod
    def validate_domain(cls, value: str) -> str:
        value = value.strip().lower()
        # Accept tenant/custom DNS names only; keys always come from configured HTTPS.
        label = r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
        if value and (len(value) > 253 or not re.fullmatch(rf"{label}(?:\.{label})+", value)):
            raise ValueError("AUTH0_DOMAIN must be a hostname without scheme or path")
        return value

    @field_validator("auth0_audience")
    @classmethod
    def validate_audience(cls, value: str) -> str:
        return value.strip()

    @property
    def issuer(self) -> str:
        return f"https://{self.auth0_domain}/"


@lru_cache(maxsize=1)
def get_auth0_configuration() -> tuple[Auth0Settings, PyJWKClient | None]:
    """Cache settings and public keys per process; no network call at construction."""
    try:
        settings = Auth0Settings()
    except (ValidationError, OSError):
        raise AuthenticationUnavailable() from None
    if not settings.auth0_domain and not settings.auth0_audience:
        return settings, None
    if not settings.auth0_domain or not settings.auth0_audience:
        raise AuthenticationUnavailable()
    return settings, PyJWKClient(
        settings.issuer + ".well-known/jwks.json",
        cache_jwk_set=True,
        lifespan=300,
        timeout=5,
    )


class Auth0TokenValidator:
    async def validate(self, token: str) -> AuthenticatedPrincipal:
        # Public-key fetches and signature checks must not block the async event loop.
        return await run_in_threadpool(self._validate, token)

    def _validate(self, token: str) -> AuthenticatedPrincipal:
        try:
            # Check header shape before configuration/network access. Never trust token URLs.
            header = jwt.get_unverified_header(token)
            if header.get("alg") != "RS256" or not isinstance(header.get("kid"), str):
                raise InvalidCredentials()
            if not header["kid"]:
                raise InvalidCredentials()
            settings, client = get_auth0_configuration()
            if client is None:
                raise InvalidCredentials()
            key = client.get_signing_key_from_jwt(token)
        except PyJWKClientConnectionError:
            raise AuthenticationUnavailable() from None
        except PyJWKClientError:
            # Includes unknown signing keys after the client's refresh/cooldown policy.
            raise InvalidCredentials() from None
        except jwt.InvalidTokenError:
            raise InvalidCredentials() from None
        except (jwt.PyJWKError, jwt.PyJWKSetError, ValueError, TypeError, OSError):
            raise AuthenticationUnavailable() from None

        try:
            claims = jwt.decode(
                token,
                key.key,
                algorithms=["RS256"],
                issuer=settings.issuer,
                audience=settings.auth0_audience,
                options={"require": ["exp", "iat", "iss", "aud", "sub"]},
            )
        except (jwt.InvalidTokenError, ValueError, TypeError, OverflowError):
            raise InvalidCredentials() from None
        except jwt.InvalidKeyError:
            raise AuthenticationUnavailable() from None

        subject = claims["sub"]
        if not isinstance(subject, str) or not subject.strip() or len(subject) > 255:
            raise InvalidCredentials()
        # /me represents humans, never Auth0 client-credentials service accounts.
        if claims.get("gty") == "client-credentials" or subject.endswith("@clients"):
            raise InvalidCredentials()
        return AuthenticatedPrincipal(subject=subject)
