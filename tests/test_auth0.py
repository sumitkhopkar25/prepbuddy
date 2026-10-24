"""Real JWT signatures with an offline Auth0 public-key endpoint."""

import io
import json
import time
from types import SimpleNamespace
from unittest.mock import Mock
from urllib.error import URLError

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from app.identity import dependencies
from app.identity.auth0 import Auth0Settings, get_auth0_configuration
from app.identity.service import LocalUser
from app.main import create_app

DOMAIN = "test-tenant.eu.auth0.com"
AUDIENCE = "https://api.prepbuddy.local"


@pytest.fixture(scope="module")
def private_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture
def auth0(monkeypatch, tmp_path, private_key):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AUTH0_DOMAIN", DOMAIN)
    monkeypatch.setenv("AUTH0_AUDIENCE", AUDIENCE)
    get_auth0_configuration.cache_clear()
    jwk = jwt.algorithms.RSAAlgorithm.to_jwk(private_key.public_key(), as_dict=True)
    jwk.update(kid="test-key", use="sig", alg="RS256")
    fetch = Mock(side_effect=lambda *args, **kwargs: io.BytesIO(json.dumps({"keys": [jwk]}).encode()))
    monkeypatch.setattr("jwt.jwks_client.urllib.request.build_opener",
                        lambda *args: SimpleNamespace(open=fetch))
    resolve = Mock(side_effect=lambda principal: LocalUser("local-" + principal.subject,
                                                         principal.subject))
    monkeypatch.setattr(dependencies, "resolve_local_user", resolve)
    with TestClient(create_app()) as client:
        yield client, fetch, resolve
    get_auth0_configuration.cache_clear()


def token(private_key, changes=None, remove=None, kid="test-key"):
    now = int(time.time())
    claims = {"sub": "auth0|alice", "iss": f"https://{DOMAIN}/", "aud": AUDIENCE,
              "iat": now, "exp": now + 300}
    claims.update(changes or {})
    if remove:
        del claims[remove]
    return jwt.encode(claims, private_key, algorithm="RS256", headers={"kid": kid})


def request(client, encoded):
    return client.get("/me", headers={"Authorization": "Bearer " + encoded})


def assert_rejected(auth0, encoded, caplog):
    client, _, resolve = auth0
    response = request(client, encoded)
    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication required"}
    assert response.headers["www-authenticate"] == "Bearer"
    resolve.assert_not_called()
    assert encoded not in caplog.text


def test_two_users_and_cached_keys(auth0, private_key):
    client, fetch, resolve = auth0
    alice = request(client, token(private_key)).json()
    assert alice == {"id": "local-auth0|alice", "subject": "auth0|alice"}
    assert request(client, token(private_key)).json() == alice
    bob = request(client, token(private_key, {"sub": "google-oauth2|bob"})).json()
    assert bob["subject"] == "google-oauth2|bob"
    assert bob["id"] != alice["id"]
    assert [call.args[0].subject for call in resolve.call_args_list] == [
        "auth0|alice", "auth0|alice", "google-oauth2|bob"
    ]
    fetch.assert_called_once()
    assert fetch.call_args.args[0].full_url == f"https://{DOMAIN}/.well-known/jwks.json"
    assert fetch.call_args.kwargs["timeout"] == 5


@pytest.mark.parametrize("changes", [
    {"iss": "https://untrusted.example/"}, {"iss": f"https://{DOMAIN}"},
    {"aud": "another-api"}, {"exp": 1}, {"iat": 4102444800}, {"nbf": 4102444800},
    {"sub": ""}, {"sub": " "}, {"sub": 123}, {"sub": "x" * 256},
    {"sub": "service@clients"}, {"gty": "client-credentials"},
    {"aud": "postman-client-id"},
    {"exp": []}, {"iat": "not-a-time"}, {"nbf": {}},
])
def test_reject_invalid_claims(auth0, private_key, changes, caplog):
    assert_rejected(auth0, token(private_key, changes), caplog)


@pytest.mark.parametrize("claim", ["exp", "iat", "iss", "aud", "sub"])
def test_require_claims(auth0, private_key, claim, caplog):
    assert_rejected(auth0, token(private_key, remove=claim), caplog)


def test_wrong_signature(auth0, caplog):
    other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    assert_rejected(auth0, token(other_key), caplog)


def test_reject_unknown_key_without_repeated_fetches(auth0, private_key, caplog):
    assert_rejected(auth0, token(private_key, kid="unknown-key"), caplog)
    assert auth0[1].call_count == 1


def test_key_rotation(auth0, private_key, monkeypatch):
    client, fetch, _ = auth0
    assert request(client, token(private_key)).status_code == 200
    monkeypatch.setattr("jwt.jwks_client.time",
                        SimpleNamespace(monotonic=lambda: time.monotonic() + 31))
    rotated = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = jwt.algorithms.RSAAlgorithm.to_jwk(rotated.public_key(), as_dict=True)
    jwk.update(kid="rotated-key", use="sig", alg="RS256")
    fetch.side_effect = lambda *args, **kwargs: io.BytesIO(json.dumps({"keys": [jwk]}).encode())
    assert request(client, token(rotated, kid="rotated-key")).status_code == 200
    assert fetch.call_count == 2


@pytest.mark.parametrize("encoded", [
    "not-a-jwt", jwt.encode({"sub": "auth0|alice"}, "a" * 32, algorithm="HS256"),
    jwt.encode({"sub": "auth0|alice"}, "", algorithm="none"),
])
def test_bad_tokens_never_fetch_keys(auth0, encoded, caplog):
    assert_rejected(auth0, encoded, caplog)
    auth0[1].assert_not_called()


def test_missing_kid_never_fetches_keys(auth0, private_key, caplog):
    encoded = jwt.encode({"sub": "auth0|alice"}, private_key, algorithm="RS256")
    assert_rejected(auth0, encoded, caplog)
    auth0[1].assert_not_called()


@pytest.mark.parametrize("failure", [URLError("private upstream details"), TimeoutError()])
def test_key_service_failure_is_generic(auth0, private_key, failure, caplog):
    client, fetch, resolve = auth0
    fetch.side_effect = failure
    response = request(client, token(private_key))
    assert response.status_code == 503
    assert response.json() == {"detail": "Authentication service unavailable"}
    resolve.assert_not_called()
    assert "private upstream details" not in caplog.text


def test_malformed_key_response_is_generic(auth0, private_key):
    client, fetch, resolve = auth0
    fetch.side_effect = lambda *args, **kwargs: io.BytesIO(b"not JSON")
    response = request(client, token(private_key))
    assert response.status_code == 503
    resolve.assert_not_called()


@pytest.mark.parametrize("domain,audience,status", [
    ("", "", 401), (DOMAIN, "", 503), ("", AUDIENCE, 503),
    ("https://" + DOMAIN, AUDIENCE, 503), (DOMAIN + "/path", AUDIENCE, 503),
])
def test_unconfigured_or_invalid_configuration(auth0, private_key, monkeypatch,
                                               domain, audience, status):
    client, fetch, resolve = auth0
    monkeypatch.setenv("AUTH0_DOMAIN", domain)
    monkeypatch.setenv("AUTH0_AUDIENCE", audience)
    assert request(client, token(private_key)).status_code == status
    assert client.get("/me").status_code == 401
    assert client.get("/health").status_code == 200
    fetch.assert_not_called()
    resolve.assert_not_called()


def test_settings_read_dotenv_with_environment_precedence(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("AUTH0_DOMAIN", raising=False)
    monkeypatch.setenv("AUTH0_AUDIENCE", AUDIENCE)
    (tmp_path / ".env").write_text(f"AUTH0_DOMAIN={DOMAIN}\nAUTH0_AUDIENCE=overridden\n")
    settings = Auth0Settings()
    assert settings.auth0_domain == DOMAIN
    assert settings.auth0_audience == AUDIENCE
