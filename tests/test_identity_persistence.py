"""Resolver tests; opt into migrated PostgreSQL with PREPBUDDY_TEST_DATABASE_URL."""

import os
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.db.models import User
from app.identity.service import AuthenticatedPrincipal
from app.identity.user_service import resolve_user


def test_existing_user_does_not_write():
    user = User(id=uuid4(), auth_provider_subject="test-existing")
    session = Mock(spec=Session)
    session.scalar.return_value = user
    assert resolve_user(AuthenticatedPrincipal(user.auth_provider_subject), session) is user
    session.add.assert_not_called()
    session.commit.assert_not_called()


def test_new_user_commits_subject_only():
    session = Mock(spec=Session)
    session.scalar.return_value = None
    user = resolve_user(AuthenticatedPrincipal("test-new"), session)
    assert user.auth_provider_subject == "test-new"
    assert user.email is None
    assert user.display_name is None
    session.add.assert_called_once_with(user)
    session.commit.assert_called_once()


@pytest.mark.parametrize("operation", ["scalar", "commit"])
def test_database_failure_rolls_back(operation):
    session = Mock(spec=Session)
    session.scalar.return_value = None
    error = OperationalError("private SQL", {}, Exception("private connection"))
    getattr(session, operation).side_effect = error
    with pytest.raises(OperationalError):
        resolve_user(AuthenticatedPrincipal("test-failure"), session)
    session.rollback.assert_called_once()


def test_unique_subject_race_returns_winner():
    session = Mock(spec=Session)
    winner = User(id=uuid4(), auth_provider_subject="test-race")
    session.scalar.side_effect = [None, winner]
    cause = Exception()
    cause.sqlstate = "23505"
    cause.diag = SimpleNamespace(constraint_name="uq_users_auth_provider_subject")
    session.commit.side_effect = IntegrityError("insert", {}, cause)
    assert resolve_user(AuthenticatedPrincipal("test-race"), session) is winner
    session.rollback.assert_called_once()


def test_unrelated_integrity_error_is_not_recovered():
    session = Mock(spec=Session)
    session.scalar.return_value = None
    session.commit.side_effect = IntegrityError("insert", {}, Exception())
    with pytest.raises(IntegrityError):
        resolve_user(AuthenticatedPrincipal("test-failure"), session)
    assert session.rollback.called
    session.scalar.assert_called_once()


def test_postgresql_resolution_is_persistent_and_idempotent():
    url = os.environ.get("PREPBUDDY_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set PREPBUDDY_TEST_DATABASE_URL to an isolated migrated PostgreSQL database")
    engine = create_engine(url, hide_parameters=True)
    subject = f"identity-test-{uuid4()}"
    try:
        with engine.connect() as connection:
            transaction = connection.begin()
            try:
                with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
                    first = resolve_user(AuthenticatedPrincipal(subject), session)
                    user_id = first.id
                with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
                    second = resolve_user(AuthenticatedPrincipal(subject), session)
                    assert second.id == user_id
                    assert session.scalar(
                        select(func.count()).select_from(User).where(
                            User.auth_provider_subject == subject
                        )
                    ) == 1
            finally:
                transaction.rollback()
    finally:
        engine.dispose()
