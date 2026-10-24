"""Resolve verified identities using a caller-owned database session."""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.models import User
from app.identity.service import AuthenticatedPrincipal


def resolve_user(principal: AuthenticatedPrincipal, session: Session) -> User:
    """Lookup or create a user; callers should supply a dedicated session."""
    query = select(User).where(User.auth_provider_subject == principal.subject)
    try:
        user = session.scalar(query)
        if user is not None:
            return user
        user = User(auth_provider_subject=principal.subject)
        session.add(user)
        try:
            session.commit()
        except IntegrityError as error:
            session.rollback()
            # Only recover the expected PostgreSQL unique-subject race.
            if (
                getattr(error.orig, "sqlstate", None) != "23505"
                or getattr(getattr(error.orig, "diag", None), "constraint_name", None)
                != "uq_users_auth_provider_subject"
            ):
                raise
            existing = session.scalar(query)
            if existing is None:
                raise
            return existing
        return user
    except SQLAlchemyError:
        session.rollback()
        raise
