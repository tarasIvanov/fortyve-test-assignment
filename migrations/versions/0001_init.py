"""Початкова схема: розширення PostGIS, таблиця fields, індекси.

Revision ID: 0001
Revises:
"""
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    op.execute(
        """
        CREATE TABLE fields (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name        TEXT NOT NULL,
            geom        geometry(Polygon, 4326) NOT NULL,
            area_ha     DOUBLE PRECISION NOT NULL,
            crop        TEXT NOT NULL,
            owner       TEXT NOT NULL,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT fields_geom_valid    CHECK (ST_IsValid(geom)),
            CONSTRAINT fields_area_positive CHECK (area_ha > 0.1)
        )
        """
    )

    # GiST зберігає bounding box кожного полігона в R-дереві: пошук точки
    # спускається лише в ті гілки, чий прямокутник її накриває.
    op.execute("CREATE INDEX fields_geom_gist ON fields USING GIST (geom)")
    op.execute("CREATE INDEX fields_crop_idx  ON fields (crop)")
    op.execute("CREATE INDEX fields_owner_idx ON fields (owner)")
    op.execute("CREATE INDEX fields_area_idx  ON fields (area_ha)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS fields")
