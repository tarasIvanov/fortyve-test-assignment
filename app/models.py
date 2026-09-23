import uuid
from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import CheckConstraint, DateTime, Float, Index, Text, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Field(Base):
    __tablename__ = "fields"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    # spatial_index=False: GiST-індекс оголошений нижче явно, з тим самим іменем,
    # що й у міграції — інакше alembic autogenerate вирішив би, що індекс зайвий.
    geom: Mapped[str] = mapped_column(
        Geometry(geometry_type="POLYGON", srid=4326, spatial_index=False), nullable=False
    )
    area_ha: Mapped[float] = mapped_column(Float, nullable=False)
    crop: Mapped[str] = mapped_column(Text, nullable=False)
    owner: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint("ST_IsValid(geom)", name="fields_geom_valid"),
        CheckConstraint("area_ha > 0.1", name="fields_area_positive"),
        Index("fields_geom_gist", "geom", postgresql_using="gist"),
        Index("fields_crop_idx", "crop"),
        Index("fields_owner_idx", "owner"),
        Index("fields_area_idx", "area_ha"),
    )
