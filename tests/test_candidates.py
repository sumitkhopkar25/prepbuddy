"""Candidate creation boundaries; PostgreSQL service checks are opt-in."""

import os
import sys
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.candidates import CandidateAlreadyExists
from app.candidates import dependencies as candidate_dependencies
from app.candidates.schemas import CandidateCreate, CandidateResponse
from app.candidates.service import create_candidate
from app.db.models import Candidate, User
from app.identity import dependencies as identity_dependencies
from app.identity.dependencies import get_current_user, get_token_validator
from app.identity.service import LocalUser, UnconfiguredTokenValidator
from app.main import create_app

CANDIDATE_ID = UUID("136a1ea6-3f75-47a5-b43f-fd264a176bcb")


@pytest.fixture
def owner_id():
    return uuid4()


@pytest.fixture
def client(owner_id):
    application = create_app()
    application.dependency_overrides[get_current_user] = lambda: LocalUser(
        id=str(owner_id), subject="test-candidate-owner"
    )
    with TestClient(application) as client:
        yield client


@pytest.fixture
def persistence(monkeypatch):
    def persist(user_id, data):
        return CandidateResponse(id=CANDIDATE_ID, user_id=user_id, **data.model_dump())

    mock = Mock(side_effect=persist)
    monkeypatch.setattr(candidate_dependencies, "persist_candidate", mock)
    return mock


@pytest.mark.parametrize(
    "payload, expected",
    [
        ({}, {"name": None, "current_role": None, "experience_years": None}),
        (
            {
                "name": "  Test Candidate  ",
                "current_role": " Backend Engineer ",
                "experience_years": 6,
            },
            {
                "name": "Test Candidate",
                "current_role": "Backend Engineer",
                "experience_years": "6.0",
            },
        ),
        (
            {"name": None, "current_role": None, "experience_years": "0.5"},
            {"name": None, "current_role": None, "experience_years": "0.5"},
        ),
    ],
)
def test_creation_returns_persisted_data_owned_by_authenticated_user(
    client, persistence, owner_id, payload, expected
):
    response = client.post("/candidates", json=payload)
    assert response.status_code == 201
    assert response.json() == {"id": str(CANDIDATE_ID), "user_id": str(owner_id), **expected}
    persistence.assert_called_once()
    passed_owner, data = persistence.call_args.args
    assert passed_owner == owner_id
    assert isinstance(data, CandidateCreate)
    assert data.name == expected["name"]
    assert data.current_role == expected["current_role"]


@pytest.mark.parametrize(
    "payload",
    [
        {"name": "   "},
        {"current_role": "\t\n"},
        {"name": "x" * 201},
        {"current_role": "x" * 201},
        {"experience_years": -0.1},
        {"experience_years": 1000},
        {"experience_years": "1.23"},
        {"experience_years": "NaN"},
        {"experience_years": "Infinity"},
        {"user_id": str(uuid4())},
        {"id": str(uuid4())},
        {"target_roles": ["Backend Engineer"]},
    ],
)
def test_invalid_or_client_owned_fields_never_reach_candidate_persistence(
    client, persistence, payload
):
    response = client.post("/candidates", json=payload)
    assert response.status_code == 422
    persistence.assert_not_called()


@pytest.mark.parametrize("authorization", [None, "Bearer rejected-private-token"])
def test_unauthenticated_creation_does_not_access_persistence(
    authorization, persistence, monkeypatch, caplog
):
    identity_resolution = Mock(side_effect=AssertionError("Unexpected identity persistence"))
    monkeypatch.setattr(identity_dependencies, "resolve_local_user", identity_resolution)
    application = create_app()
    application.dependency_overrides[get_token_validator] = UnconfiguredTokenValidator
    headers = {} if authorization is None else {"Authorization": authorization}
    with TestClient(application) as client:
        response = client.post("/candidates", json={}, headers=headers)
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json() == {"detail": "Authentication required"}
    identity_resolution.assert_not_called()
    persistence.assert_not_called()
    assert "rejected-private-token" not in caplog.text


@pytest.mark.parametrize(
    "error, status, detail",
    [
        (CandidateAlreadyExists("private duplicate"), 409, "Candidate already exists"),
        (RuntimeError("private database URL"), 503, "Candidate service unavailable"),
        (OSError("private database configuration"), 503, "Candidate service unavailable"),
        (
            OperationalError("private SQL", {}, Exception("private connection")),
            503,
            "Candidate service unavailable",
        ),
    ],
)
def test_candidate_errors_are_sanitized(client, persistence, error, status, detail, caplog):
    persistence.side_effect = error
    response = client.post("/candidates", json={})
    assert response.status_code == status
    assert response.json() == {"detail": detail}
    assert "private" not in response.text
    assert "private" not in caplog.text


def test_service_commits_authenticated_owner_and_validated_baseline_fields(owner_id):
    session = Mock(spec=Session)
    data = CandidateCreate(name=" Test Candidate ", experience_years="6.5")
    candidate = create_candidate(session, owner_id, data)
    assert isinstance(candidate, Candidate)
    assert candidate.user_id == owner_id
    assert candidate.name == "Test Candidate"
    assert candidate.current_role is None
    assert candidate.experience_years == Decimal("6.5")
    session.add.assert_called_once_with(candidate)
    session.commit.assert_called_once_with()
    session.rollback.assert_not_called()
    session.close.assert_not_called()


@pytest.mark.parametrize("operation", ["add", "commit"])
def test_service_rolls_back_and_propagates_database_failures(owner_id, operation):
    session = Mock(spec=Session)
    error = OperationalError("private SQL", {}, Exception("private connection"))
    getattr(session, operation).side_effect = error
    with pytest.raises(OperationalError) as raised:
        create_candidate(session, owner_id, CandidateCreate())
    assert raised.value is error
    session.rollback.assert_called_once_with()
    session.close.assert_not_called()


def integrity_error(sqlstate, constraint):
    cause = Exception("private database details")
    cause.sqlstate = sqlstate
    cause.diag = SimpleNamespace(constraint_name=constraint)
    return IntegrityError("private insert", {}, cause)


def test_service_translates_only_ownership_unique_violation_after_rollback(owner_id):
    session = Mock(spec=Session)
    session.commit.side_effect = integrity_error("23505", "uq_candidates_user_id")
    with pytest.raises(CandidateAlreadyExists):
        create_candidate(session, owner_id, CandidateCreate())
    session.rollback.assert_called_once_with()


@pytest.mark.parametrize(
    "sqlstate, constraint",
    [("23505", "pk_candidates"), ("23503", "uq_candidates_user_id"), (None, None)],
)
def test_service_does_not_relabel_unrelated_integrity_failures(owner_id, sqlstate, constraint):
    session = Mock(spec=Session)
    error = integrity_error(sqlstate, constraint)
    session.commit.side_effect = error
    with pytest.raises(IntegrityError) as raised:
        create_candidate(session, owner_id, CandidateCreate())
    assert raised.value is error
    session.rollback.assert_called_once_with()


@pytest.fixture
def dedicated_session(monkeypatch):
    session = Mock(spec=Session)
    context = MagicMock()
    context.__enter__.return_value = session
    factory = Mock(return_value=context)
    monkeypatch.setitem(sys.modules, "app.db.session", SimpleNamespace(SessionLocal=factory))
    return session, context, factory


def test_endpoint_materializes_response_and_closes_dedicated_session(
    client, owner_id, dedicated_session
):
    session, context, factory = dedicated_session

    def commit():
        session.add.call_args.args[0].id = CANDIDATE_ID

    session.commit.side_effect = commit
    response = client.post("/candidates", json={"experience_years": 0})
    assert response.status_code == 201
    assert response.json() == {
        "id": str(CANDIDATE_ID),
        "user_id": str(owner_id),
        "name": None,
        "current_role": None,
        "experience_years": "0.0",
    }
    factory.assert_called_once_with()
    context.__exit__.assert_called_once_with(None, None, None)
    session.commit.assert_called_once_with()


@pytest.mark.parametrize(
    "sqlstate, constraint, expected_status",
    [
        ("23505", "uq_candidates_user_id", 409),
        ("23505", "pk_candidates", 503),
        ("23503", "fk_candidates_user_id_users", 503),
    ],
)
def test_endpoint_translates_commit_failures_and_closes_session(
    client, dedicated_session, sqlstate, constraint, expected_status, caplog
):
    session, context, _ = dedicated_session
    session.commit.side_effect = integrity_error(sqlstate, constraint)
    response = client.post("/candidates", json={})
    assert response.status_code == expected_status
    assert response.json() == {
        "detail": "Candidate already exists"
        if expected_status == 409
        else "Candidate service unavailable"
    }
    session.rollback.assert_called_once_with()
    context.__exit__.assert_called_once()
    assert "private" not in response.text
    assert "private" not in caplog.text


def test_endpoint_sanitizes_session_construction_failure(client, dedicated_session, caplog):
    _, _, factory = dedicated_session
    factory.side_effect = RuntimeError("private configuration")
    response = client.post("/candidates", json={})
    assert response.status_code == 503
    assert response.json() == {"detail": "Candidate service unavailable"}
    assert "private" not in caplog.text


@pytest.mark.parametrize("soft_deleted", [False, True])
def test_postgresql_service_persists_one_candidate_and_rejects_a_second(soft_deleted):
    url = os.environ.get("PREPBUDDY_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set PREPBUDDY_TEST_DATABASE_URL to an isolated migrated PostgreSQL database")
    engine = create_engine(url, hide_parameters=True)
    try:
        with engine.connect() as connection:
            transaction = connection.begin()
            try:
                with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
                    user = User(auth_provider_subject=f"candidate-test-{uuid4()}")
                    session.add(user)
                    session.commit()
                    owner_id = user.id
                    candidate = create_candidate(
                        session, owner_id, CandidateCreate(experience_years="6.5")
                    )
                    candidate_id = candidate.id
                    if soft_deleted:
                        candidate.deleted_at = datetime.now(UTC)
                        session.commit()
                with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
                    with pytest.raises(CandidateAlreadyExists):
                        create_candidate(session, owner_id, CandidateCreate())
                    assert (
                        session.scalar(
                            select(func.count())
                            .select_from(Candidate)
                            .where(Candidate.user_id == owner_id)
                        )
                        == 1
                    )
                    stored = session.get(Candidate, candidate_id)
                    assert stored.user_id == owner_id
                    assert stored.experience_years == Decimal("6.5")
            finally:
                transaction.rollback()
    finally:
        engine.dispose()
