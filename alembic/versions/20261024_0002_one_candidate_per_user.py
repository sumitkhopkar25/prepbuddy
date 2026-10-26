"""Enforce one candidate per user without deleting existing records.

Revision ID: 20261024_0002
Revises: 20260830_0001
Create Date: 2026-10-24
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20261024_0002"
down_revision: str | None = "20260830_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Keep the preflight check and constraint creation consistent with concurrent writes.
    op.execute("LOCK TABLE candidates IN ACCESS EXCLUSIVE MODE")
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM candidates GROUP BY user_id HAVING count(*) > 1
            ) THEN
                RAISE EXCEPTION 'Cannot enforce one candidate per user: resolve existing '
                    'duplicate candidates before retrying. No records were changed.';
            END IF;
        END;
        $$
        """
    )
    op.create_unique_constraint(op.f("uq_candidates_user_id"), "candidates", ["user_id"])


def downgrade() -> None:
    op.drop_constraint(op.f("uq_candidates_user_id"), "candidates", type_="unique")
