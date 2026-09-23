"""GiST-індекс по геометрії.

Revision ID: 0002
Revises: 0001
"""
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE INDEX fields_geom_gist ON fields USING GIST (geom)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS fields_geom_gist")
