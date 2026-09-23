from uuid import UUID

from app.exceptions import (
    AreaTooSmallError,
    FieldNotFoundError,
    InvalidGeometryError,
    UnsupportedGeometryError,
)
from app.repository import FieldRepository, parse_geometry
from app.schemas import FieldCreate, FieldDetail, FieldMatch, FieldSummary

MIN_AREA_HA = 0.1


class FieldService:
    def __init__(self, repository: FieldRepository) -> None:
        self._repository = repository

    async def create_field(self, payload: FieldCreate) -> FieldDetail:
        if len(payload.geometry.coordinates) != 1:
            raise UnsupportedGeometryError(
                "Підтримуються лише прості полігони з одним кільцем: "
                "дірки (inner rings) наразі не підтримуються"
            )

        geojson = payload.geometry.model_dump_json()
        inspection = await self._repository.inspect_geometry(geojson)

        if not inspection.is_valid:
            raise InvalidGeometryError(f"Полігон невалідний: {inspection.reason}")

        if inspection.area_ha <= MIN_AREA_HA:
            raise AreaTooSmallError(
                f"Площа поля {inspection.area_ha:.4f} га, "
                f"мінімально допустима — {MIN_AREA_HA} га"
            )

        row = await self._repository.create(
            name=payload.name,
            geojson=geojson,
            area_ha=inspection.area_ha,
            crop=payload.crop,
            owner=payload.owner,
        )

        return FieldDetail(
            id=row.id,
            name=row.name,
            geometry=parse_geometry(row.geometry),
            area_ha=row.area_ha,
            crop=row.crop,
            owner=row.owner,
            created_at=row.created_at,
        )

    async def get_field(self, field_id: UUID) -> FieldDetail:
        row = await self._repository.get_by_id(field_id)
        if row is None:
            raise FieldNotFoundError(f"Поле {field_id} не знайдено")

        return FieldDetail(
            id=row.id,
            name=row.name,
            geometry=parse_geometry(row.geometry),
            area_ha=row.area_ha,
            crop=row.crop,
            owner=row.owner,
            created_at=row.created_at,
        )

    async def list_fields(
        self,
        *,
        crop: str | None,
        owner: str | None,
        min_area: float | None,
        max_area: float | None,
        limit: int,
        offset: int,
    ) -> tuple[int, list[FieldSummary]]:
        rows = await self._repository.list_fields(
            crop=crop,
            owner=owner,
            min_area=min_area,
            max_area=max_area,
            limit=limit,
            offset=offset,
        )
        total = rows[0].total if rows else 0
        return total, [FieldSummary.model_validate(row) for row in rows]

    async def find_by_point(self, longitude: float, latitude: float) -> list[FieldMatch]:
        rows = await self._repository.find_by_point(longitude, latitude)
        return [FieldMatch.model_validate(row) for row in rows]
