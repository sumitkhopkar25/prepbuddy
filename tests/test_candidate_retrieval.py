"""Current-candidate retrieval, ownership isolation, and persistence boundaries."""

import sys
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.candidates import CandidateNotFound, dependencies
from app.candidates.schemas import CandidateResponse
from app.candidates.service import get_candidate_for_user
from app.db.base import Base
from app.db.models import Candidate, User
from app.identity import dependencies as identity_dependencies
from app.identity.dependencies import get_current_principal, get_current_user, get_token_validator
from app.identity.service import AuthenticatedPrincipal, LocalUser, UnconfiguredTokenValidator
from app.main import create_app


@pytest.fixture
def owner_id():
    return uuid4()


@pytest.fixture
def client(owner_id):
    application = create_app()
    application.dependency_overrides[get_current_user] = lambda: LocalUser(
        id=str(owner_id), subject="retrieval-test-owner"
    )
    with TestClient(application) as client:
        yield client


@pytest.fixture
def dedicated_session(monkeypatch):
    session = Mock(spec=Session)
    context = MagicMock()
    context.__enter__.return_value = session
    factory = Mock(return_value=context)
    monkeypatch.setitem(sys.modules, "app.db.session", SimpleNamespace(SessionLocal=factory))
    return session, context, factory


@pytest.mark.parametrize("experience, serialized", [(None, None), (Decimal(6), "6.0")])
def test_retrieval_uses_authenticated_owner(client, owner_id, monkeypatch, experience, serialized):
    candidate_id = uuid4()
    retrieval = Mock(return_value=CandidateResponse(
        id=candidate_id, user_id=owner_id, name="Test Candidate",
        current_role="Backend Engineer", experience_years=experience,
    ))
    monkeypatch.setattr(dependencies, "retrieve_candidate", retrieval)
    # Client-selected IDs cannot influence ownership, even if supplied in query parameters.
    response = client.get("/candidates/me", params={"user_id": str(uuid4()), "id": str(uuid4())})
    assert response.status_code == 200
    assert response.json() == {
        "id": str(candidate_id), "user_id": str(owner_id), "name": "Test Candidate",
        "current_role": "Backend Engineer", "experience_years": serialized,
    }
    retrieval.assert_called_once_with(owner_id)


def test_missing_candidate_returns_generic_404_and_closes_session(client, dedicated_session):
    session, context, factory = dedicated_session
    session.scalar.return_value = None
    response = client.get("/candidates/me")
    assert response.status_code == 404
    assert response.json() == {"detail": "Candidate not found"}
    factory.assert_called_once_with()
    context.__exit__.assert_called_once()
    assert context.__exit__.call_args.args[0] is CandidateNotFound
    session.commit.assert_not_called()


@pytest.mark.parametrize("authorization", [None, "Bearer rejected-private-token", "Basic invalid"])
def test_authentication_failure_never_reaches_persistence(authorization, monkeypatch, caplog):
    retrieval = Mock(side_effect=AssertionError("Unexpected candidate persistence"))
    identity = Mock(side_effect=AssertionError("Unexpected identity persistence"))
    monkeypatch.setattr(dependencies, "retrieve_candidate", retrieval)
    monkeypatch.setattr(identity_dependencies, "resolve_local_user", identity)
    application = create_app()
    application.dependency_overrides[get_token_validator] = UnconfiguredTokenValidator
    headers = {} if authorization is None else {"Authorization": authorization}
    with TestClient(application) as client:
        response = client.get("/candidates/me", headers=headers)
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json() == {"detail": "Authentication required"}
    retrieval.assert_not_called()
    identity.assert_not_called()
    assert "private" not in response.text + caplog.text


def test_identity_resolution_failure_preserves_503(monkeypatch, caplog):
    application = create_app()
    application.dependency_overrides[get_current_principal] = lambda: AuthenticatedPrincipal(
        subject="retrieval-test-owner"
    )
    monkeypatch.setattr(identity_dependencies, "resolve_local_user", Mock(
        side_effect=RuntimeError("private identity configuration")
    ))
    retrieval = Mock()
    monkeypatch.setattr(dependencies, "retrieve_candidate", retrieval)
    with TestClient(application) as client:
        response = client.get("/candidates/me")
    assert response.status_code == 503
    assert response.json() == {"detail": "Identity service unavailable"}
    retrieval.assert_not_called()
    assert "private" not in response.text + caplog.text


@pytest.mark.parametrize("failure", ["configuration", "construction", "query", "serialization"])
def test_persistence_failures_are_sanitized(
    client, dedicated_session, monkeypatch, caplog, failure
):
    session, context, factory = dedicated_session
    if failure == "configuration":
        class BrokenConfiguration:
            def __getattr__(self, name):
                raise RuntimeError("private database configuration")

        monkeypatch.setitem(sys.modules, "app.db.session", BrokenConfiguration())
    elif failure == "construction":
        factory.side_effect = RuntimeError("private database URL")
    elif failure == "query":
        session.scalar.side_effect = OperationalError("private SQL", {}, Exception("private URL"))
    else:
        session.scalar.return_value = SimpleNamespace(id="private invalid record")
    response = client.get("/candidates/me")
    assert response.status_code == 503
    assert response.json() == {"detail": "Candidate service unavailable"}
    assert "private" not in response.text + caplog.text
    if failure in {"query", "serialization"}:
        context.__exit__.assert_called_once()
    if failure == "query":
        session.rollback.assert_called_once_with()


def test_response_is_materialized_before_session_closes(client, owner_id, dedicated_session):
    session, context, factory = dedicated_session
    candidate_id = uuid4()
    candidate = Candidate(id=candidate_id, user_id=owner_id, experience_years=Decimal(0))
    session.scalar.return_value = candidate

    def close(*args):
        # Make the source unusable when its session closes. The detached response must survive.
        candidate.id = None
        candidate.user_id = None
        candidate.experience_years = None
        return False

    context.__exit__.side_effect = close
    response = client.get("/candidates/me")
    assert response.status_code == 200
    assert response.json() == {
        "id": str(candidate_id), "user_id": str(owner_id), "name": None,
        "current_role": None, "experience_years": "0.0",
    }
    factory.assert_called_once_with()
    context.__exit__.assert_called_once_with(None, None, None)
    session.commit.assert_not_called()
    session.add.assert_not_called()


@pytest.mark.parametrize("soft_deleted", [False, True])
def test_service_queries_only_owned_rows_including_retained_candidates(soft_deleted):
    engine = create_engine("sqlite://")
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")
            Base.metadata.create_all(connection, tables=[User.__table__, Candidate.__table__])
        with Session(engine) as session:
            users = [User(auth_provider_subject=f"retrieval-test-{uuid4()}") for _ in range(3)]
            session.add_all(users)
            session.flush()
            candidates = [Candidate(
                user_id=user.id, deleted_at=datetime.now(UTC) if soft_deleted else None,
            ) for user in users[:2]]
            session.add_all(candidates)
            session.commit()
            for user, candidate in zip(users, candidates):
                assert get_candidate_for_user(session, user.id).id == candidate.id
            with pytest.raises(CandidateNotFound):
                get_candidate_for_user(session, users[2].id)
    finally:
        engine.dispose()


def test_service_rolls_back_query_failure_without_closing_caller_session(owner_id):
    session = Mock(spec=Session)
    error = OperationalError("private SQL", {}, Exception("private URL"))
    session.scalar.side_effect = error
    with pytest.raises(OperationalError) as raised:
        get_candidate_for_user(session, owner_id)
    assert raised.value is error
    session.rollback.assert_called_once_with()
    session.close.assert_not_called()
    session.commit.assert_not_called()
