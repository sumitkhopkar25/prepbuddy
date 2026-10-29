"""Real HTTP, JWT verification, and committed PostgreSQL; only JWKS transport is replaced."""

import io
import json
import os
import socket
import sys
import time
from threading import Thread
from types import SimpleNamespace
from uuid import UUID, uuid4

import httpx
import jwt
import pytest
import uvicorn
from cryptography.hazmat.primitives.asymmetric import rsa
from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import sessionmaker

from app.db.models import Candidate, User
from app.identity.auth0 import get_auth0_configuration
from app.main import create_app


@pytest.fixture
def api(monkeypatch):
    url = os.environ.get("PREPBUDDY_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set PREPBUDDY_TEST_DATABASE_URL to an isolated migrated PostgreSQL database")
    engine = create_engine(url, hide_parameters=True)
    sessions = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    monkeypatch.setitem(sys.modules, "app.db.session", SimpleNamespace(SessionLocal=sessions))
    domain = "test-tenant.eu.auth0.com"
    audience = "https://api.prepbuddy.test"
    monkeypatch.setenv("AUTH0_DOMAIN", domain)
    monkeypatch.setenv("AUTH0_AUDIENCE", audience)
    get_auth0_configuration.cache_clear()
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key(), as_dict=True)
    jwk.update(kid="api-test-key", use="sig", alg="RS256")

    def fetch(request, **kwargs):
        assert request.full_url == f"https://{domain}/.well-known/jwks.json"
        return io.BytesIO(json.dumps({"keys": [jwk]}).encode())

    monkeypatch.setattr("jwt.jwks_client.urllib.request.build_opener",
                        lambda *args: SimpleNamespace(open=fetch))
    subjects = [f"auth0|api-test-{uuid4()}" for _ in range(2)]

    def headers(index, *, expired=False):
        now = int(time.time())
        encoded = jwt.encode(
            {"sub": subjects[index], "iss": f"https://{domain}/", "aud": audience,
             "iat": now - 60, "exp": now - 1 if expired else now + 300},
            key, algorithm="RS256", headers={"kid": "api-test-key"},
        )
        return {"Authorization": "Bearer " + encoded}

    server = uvicorn.Server(uvicorn.Config(
        create_app(), log_config=None, log_level="critical", access_log=False,
    ))
    thread = None
    listener = socket.socket()
    try:
        listener.bind(("127.0.0.1", 0))
        thread = Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
        thread.start()
        deadline = time.monotonic() + 10
        while not server.started and thread.is_alive() and time.monotonic() < deadline:
            time.sleep(0.01)
        assert server.started, "Test HTTP server failed to start"
        with httpx.Client(
            base_url=f"http://127.0.0.1:{listener.getsockname()[1]}",
            timeout=10, trust_env=False,
        ) as client:
            yield client, headers, sessions
    finally:
        server.should_exit = True
        if thread is not None:
            thread.join(timeout=10)
        listener.close()
        try:
            with engine.begin() as connection:
                # Delete only these generated test users; candidate rows cascade.
                connection.execute(delete(User).where(User.auth_provider_subject.in_(subjects)))
        finally:
            engine.dispose()
            get_auth0_configuration.cache_clear()
        assert thread is None or not thread.is_alive(), "Test HTTP server failed to stop"


def test_candidate_onboarding_over_http_with_postgresql(api):
    client, headers, sessions = api
    assert client.get("/health").json() == {"status": "ok"}
    for path in ("/me", "/candidates/me"):
        response = client.get(path)
        assert response.status_code == 401
        assert response.headers["www-authenticate"] == "Bearer"
    assert client.post("/candidates", json={}).status_code == 401
    assert client.get("/candidates/me", headers=headers(0, expired=True)).status_code == 401

    identities = []
    candidates = []
    for index in range(2):
        auth = headers(index)
        response = client.get("/me", headers=auth)
        assert response.status_code == 200
        identity = response.json()
        identities.append(identity)
        assert client.get("/me", headers=auth).json() == identity
        response = client.get("/candidates/me", headers=auth)
        assert response.status_code == 404
        assert response.json() == {"detail": "Candidate not found"}
        assert client.post("/candidates", headers=auth, json={
            "user_id": str(uuid4()),
        }).status_code == 422
        response = client.post("/candidates", headers=auth, json={
            "name": f"Test Candidate {index}", "experience_years": "6.5",
        })
        assert response.status_code == 201
        candidate = response.json()
        candidates.append(candidate)
        assert candidate["user_id"] == identity["id"]
        assert candidate["experience_years"] == "6.5"
        response = client.get("/candidates/me", headers=auth)
        assert response.status_code == 200
        assert response.json() == candidate
        response = client.post("/candidates", headers=auth, json={})
        assert response.status_code == 409
        assert response.json() == {"detail": "Candidate already exists"}

    assert identities[0]["id"] != identities[1]["id"]
    assert candidates[0]["id"] != candidates[1]["id"]
    response = client.get("/candidates/me", headers=headers(0), params={
        "user_id": identities[1]["id"], "id": candidates[1]["id"],
    })
    assert response.json() == candidates[0]
    # Independent connections see the committed records, beyond the HTTP session lifetimes.
    with sessions() as session:
        for candidate in candidates:
            stored = session.scalar(select(Candidate).where(Candidate.id == UUID(candidate["id"])))
            assert str(stored.user_id) == candidate["user_id"]
            assert stored.name == candidate["name"]
