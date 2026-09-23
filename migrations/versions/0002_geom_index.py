"""GiST-індекс по геометрії.

Винесений в окрему міграцію свідомо: у проді такий індекс створюють через
CREATE INDEX CONCURRENTLY, щоб не брати ексклюзивний лок на живій таблиці,
а CONCURRENTLY не виконується всередині транзакції, у яку Alembic загортає
міграцію. Тому крок із побудовою індексу технічно має бути окремим.

Побічний ефект, зручний для демонстрації: індекс можна зняти й повернути
одним `alembic downgrade 0001` / `alembic upgrade head`, не чіпаючи решту схеми.

Revision ID: 0002
Revises: 0001
"""
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # GiST зберігає bounding box кожного полігона в R-дереві: пошук точки
    # спускається лише в ті гілки, чий прямокутник її накриває.
    op.execute("CREATE INDEX fields_geom_gist ON fields USING GIST (geom)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS fields_geom_gist")
