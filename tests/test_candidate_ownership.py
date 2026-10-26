"""Ownership constraints; PostgreSQL migration checks opt into an isolated database."""

import os
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.models import Candidate, User


@pytest.fixture
def session():
    engine = create_engine("sqlite://")
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")
            Base.metadata.create_all(connection, tables=[User.__table__, Candidate.__table__])
        with Session(engine) as session:
            yield session
    finally:
        engine.dispose()


def test_users_can_exist_before_onboarding_and_onboard_independently(session):
    users = [User(auth_provider_subject=f"ownership-test-{uuid4()}") for _ in range(2)]
    session.add_all(users)
    session.commit()
    assert session.scalar(select(func.count()).select_from(Candidate)) == 0

    for user in users:
        session.add(Candidate(user_id=user.id))
    session.commit()
    assert set(session.scalars(select(Candidate.user_id))) == {user.id for user in users}


@pytest.mark.parametrize("soft_deleted", [False, True])
def test_user_cannot_own_a_second_candidate_even_after_soft_deletion(session, soft_deleted):
    user = User(auth_provider_subject=f"ownership-test-{uuid4()}")
    session.add(user)
    session.flush()
    candidate = Candidate(user_id=user.id, deleted_at=datetime.now(UTC) if soft_deleted else None)
    session.add(candidate)
    session.commit()
    candidate_id, user_id = candidate.id, user.id

    session.add(Candidate(user_id=user_id))
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()
    assert list(session.scalars(select(Candidate.id))) == [candidate_id]


@pytest.fixture
def migration_connection():
    url = os.environ.get("PREPBUDDY_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set PREPBUDDY_TEST_DATABASE_URL to an isolated PostgreSQL database")
    engine = create_engine(url, hide_parameters=True)
    try:
        with engine.connect() as connection:
            transaction = connection.begin()
            try:
                # Shadow any real candidates table. Only generated test data is touched.
                connection.exec_driver_sql(
                    "CREATE TEMP TABLE candidates ("
                    "id UUID PRIMARY KEY, user_id UUID NOT NULL, deleted_at TIMESTAMPTZ"
                    ") ON COMMIT DROP"
                )
                with Operations.context(MigrationContext.configure(connection)):
                    yield connection
            finally:
                transaction.rollback()
    finally:
        engine.dispose()


@pytest.fixture
def migration():
    scripts = ScriptDirectory(str(Path(__file__).resolve().parents[1] / "alembic"))
    return scripts.get_revision("20261024_0002").module


def insert_candidate(connection, user_id, *, soft_deleted=False):
    candidate_id = uuid4()
    connection.execute(
        text("INSERT INTO candidates (id, user_id, deleted_at) VALUES (:id, :user, :deleted)"),
        {
            "id": candidate_id,
            "user": user_id,
            "deleted": datetime.now(UTC) if soft_deleted else None,
        },
    )
    return candidate_id


@pytest.mark.parametrize("soft_deleted", [False, True])
def test_postgresql_upgrade_preserves_rows_and_rejects_duplicate_owner(
    migration_connection, migration, soft_deleted
):
    connection = migration_connection
    user_id = uuid4()
    candidate_id = insert_candidate(connection, user_id, soft_deleted=soft_deleted)
    migration.upgrade()

    with pytest.raises(IntegrityError) as raised, connection.begin_nested():
        insert_candidate(connection, user_id)
    assert raised.value.orig.sqlstate == "23505"
    assert raised.value.orig.diag.constraint_name == "uq_candidates_user_id"
    assert connection.execute(text("SELECT id FROM candidates")).scalars().all() == [candidate_id]
    insert_candidate(connection, uuid4())


@pytest.mark.parametrize("soft_deleted", [False, True])
def test_postgresql_upgrade_refuses_existing_duplicates_without_changing_data(
    migration_connection, migration, soft_deleted
):
    connection = migration_connection
    user_id = uuid4()
    original_ids = {
        insert_candidate(connection, user_id),
        insert_candidate(connection, user_id, soft_deleted=soft_deleted),
    }
    with pytest.raises(DBAPIError) as raised, connection.begin_nested():
        migration.upgrade()
    message = str(raised.value.orig)
    assert "resolve existing duplicate candidates before retrying" in message
    assert str(user_id) not in message
    assert set(connection.execute(text("SELECT id FROM candidates")).scalars()) == original_ids


def test_postgresql_downgrade_preserves_rows_and_removes_only_the_limit(
    migration_connection, migration
):
    connection = migration_connection
    user_id = uuid4()
    candidate_id = insert_candidate(connection, user_id)
    migration.upgrade()
    migration.downgrade()
    second_id = insert_candidate(connection, user_id)
    assert set(connection.execute(text("SELECT id FROM candidates")).scalars()) == {
        candidate_id,
        second_id,
    }
