import os
import subprocess
import sys
from dataclasses import FrozenInstanceError

import pytest
from fastapi.testclient import TestClient

from app.identity import dependencies
from app.identity.dependencies import get_token_validator
from app.identity.service import AuthenticatedPrincipal, InvalidCredentials, LocalUser
from app.main import create_app


class FakeTokenValidator:
    async def validate(self, token: str) -> AuthenticatedPrincipal:
        if token == "test-valid-token":
            return AuthenticatedPrincipal(subject="provider-user-123")
        raise InvalidCredentials(f"Rejected {token}")


@pytest.mark.parametrize("scheme", ["Bearer", "bearer", "BEARER"])
def test_validated_subject(scheme: str, monkeypatch) -> None:
    def resolve(principal):
        assert principal.subject == "provider-user-123"
        return LocalUser("7b9a10ee-f18c-46b2-8bb2-7cd2f25dba00", principal.subject)

    monkeypatch.setattr(dependencies, "resolve_local_user", resolve)
    application = create_app()
    application.dependency_overrides[get_token_validator] = FakeTokenValidator
    with TestClient(application) as client:
        response = client.get("/me", headers={"Authorization": f"{scheme} test-valid-token"})
    assert response.status_code == 200
    assert response.json() == {
        "id": "7b9a10ee-f18c-46b2-8bb2-7cd2f25dba00", "subject": "provider-user-123"
    }


@pytest.mark.parametrize(
    "authorization",
    [None, "Basic test-valid-token", "nonsense", "Bearer", "Bearer ",
     "Bearer   ", "Bearer test-valid-token extra", "Bearer rejected-secret"],
)
def test_authentication_failures(authorization: str | None, caplog, monkeypatch) -> None:
    def unexpected_resolution(principal):
        pytest.fail("Unauthenticated requests must not access persistence")

    monkeypatch.setattr(dependencies, "resolve_local_user", unexpected_resolution)
    application = create_app()
    application.dependency_overrides[get_token_validator] = FakeTokenValidator
    headers = {} if authorization is None else {"Authorization": authorization}
    with TestClient(application) as client:
        response = client.get("/me", headers=headers)
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json() == {"detail": "Authentication required"}
    assert "rejected-secret" not in caplog.text


def test_default_validator_fails_closed() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/me", headers={"Authorization": "Bearer test-valid-token"})
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_principal_is_immutable() -> None:
    principal = AuthenticatedPrincipal(subject="provider-user-123")
    with pytest.raises(FrozenInstanceError):
        principal.subject = "other-user"


def test_public_health_and_import_without_database(tmp_path) -> None:
    environment = os.environ.copy()
    environment.pop("DATABASE_URL", None)
    subprocess.run(
        [sys.executable, "-c", """
import sys
from fastapi.testclient import TestClient
from app.main import app
from app.identity.dependencies import get_token_validator

def unexpected_auth():
    raise AssertionError("Health must not resolve authentication")

app.dependency_overrides[get_token_validator] = unexpected_auth
with TestClient(app) as client:
    response = client.get('/health')
    assert response.status_code == 200
    assert response.json() == {'status': 'ok'}
assert 'app.db.config' not in sys.modules
assert 'app.db.session' not in sys.modules
assert 'sqlalchemy' not in sys.modules
assert 'app.identity.auth0' not in sys.modules
assert 'jwt' not in sys.modules
"""],
        cwd=tmp_path,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )


@pytest.mark.parametrize("error", [RuntimeError("private database URL"), OSError("secret SQL")])
def test_persistence_failure_is_generic(error, monkeypatch, caplog):
    def fail(principal):
        raise error

    monkeypatch.setattr(dependencies, "resolve_local_user", fail)
    application = create_app()
    application.dependency_overrides[get_token_validator] = FakeTokenValidator
    with TestClient(application) as client:
        response = client.get("/me", headers={"Authorization": "Bearer test-valid-token"})
    assert response.status_code == 503
    assert response.json() == {"detail": "Identity service unavailable"}
    assert str(error) not in caplog.text
