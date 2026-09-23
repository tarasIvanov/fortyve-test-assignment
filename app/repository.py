"""Єдине місце, де живе SQL."""

import json
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import Row, text
from sqlalchemy.ext.asyncio import AsyncSession

# Точка запиту в системі координат WGS84 (SRID 4326).
POINT_SQL = "ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)"

SQUARE_METERS_PER_HECTARE = 10_000

# Головний запит завдання. Винесений у константу, щоб бенчмарк міряв рівно те саме,
# що виконує API, і вони не розійшлися з часом.
FIND_BY_POINT_SQL = text(
    f"""
    SELECT id, name, area_ha, crop, owner,
           ST_Distance(ST_Centroid(geom)::geography, {POINT_SQL}::geography)
               AS distance_to_center_m
    FROM fields
    WHERE ST_Contains(geom, {POINT_SQL})
    ORDER BY distance_to_center_m
    """
)


@dataclass(frozen=True)
class GeometryInspection:
    is_valid: bool
    reason: str
    area_ha: float


class FieldRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def inspect_geometry(self, geojson: str) -> GeometryInspection:
        """Перевіряє геометрію та рахує площу до вставки — одним запитом.

        Площа рахується через каст у geography: у градусах вона фізичного змісту не має,
        а geography дає м² на еліпсоїді WGS84.
        """
        statement = text(
            f"""
            SELECT ST_IsValid(geom)       AS is_valid,
                   ST_IsValidReason(geom) AS reason,
                   ST_Area(geom::geography) / {SQUARE_METERS_PER_HECTARE} AS area_ha
            FROM (SELECT ST_SetSRID(ST_GeomFromGeoJSON(:geojson), 4326) AS geom) AS parsed
            """
        )
        row = (await self._session.execute(statement, {"geojson": geojson})).one()
        return GeometryInspection(is_valid=row.is_valid, reason=row.reason, area_ha=row.area_ha)

    async def create(
        self, *, name: str, geojson: str, area_ha: float, crop: str, owner: str
    ) -> Row[Any]:
        statement = text(
            """
            INSERT INTO fields (name, geom, area_ha, crop, owner)
            VALUES (:name, ST_SetSRID(ST_GeomFromGeoJSON(:geojson), 4326), :area_ha, :crop, :owner)
            RETURNING id, name, ST_AsGeoJSON(geom) AS geometry, area_ha, crop, owner, created_at
            """
        )
        row = (
            await self._session.execute(
                statement,
                {
                    "name": name,
                    "geojson": geojson,
                    "area_ha": area_ha,
                    "crop": crop,
                    "owner": owner,
                },
            )
        ).one()
        await self._session.commit()
        return row

    async def get_by_id(self, field_id: UUID) -> Row[Any] | None:
        statement = text(
            """
            SELECT id, name, ST_AsGeoJSON(geom) AS geometry, area_ha, crop, owner, created_at
            FROM fields
            WHERE id = :field_id
            """
        )
        return (await self._session.execute(statement, {"field_id": field_id})).one_or_none()

    async def list_fields(
        self,
        *,
        crop: str | None,
        owner: str | None,
        min_area: float | None,
        max_area: float | None,
        limit: int,
        offset: int,
    ) -> list[Row[Any]]:
        """Сторінка списку та загальна кількість — одним запитом.

        COUNT(*) OVER () рахує рядки, що пройшли фільтри, ще до LIMIT. Це економить
        другий похід до БД і гарантує, що total узгоджений із поверненою сторінкою.
        """
        conditions: list[str] = []
        parameters: dict[str, Any] = {"limit": limit, "offset": offset}

        if crop is not None:
            conditions.append("crop = :crop")
            parameters["crop"] = crop
        if owner is not None:
            conditions.append("owner = :owner")
            parameters["owner"] = owner
        if min_area is not None:
            conditions.append("area_ha >= :min_area")
            parameters["min_area"] = min_area
        if max_area is not None:
            conditions.append("area_ha <= :max_area")
            parameters["max_area"] = max_area

        # Умови складаються з констант, значення завжди йдуть параметрами.
        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        statement = text(
            f"""
            SELECT id, name, area_ha, crop, owner, COUNT(*) OVER () AS total
            FROM fields
            {where_clause}
            ORDER BY created_at DESC, id
            LIMIT :limit OFFSET :offset
            """
        )
        return list((await self._session.execute(statement, parameters)).all())

    async def find_by_point(self, longitude: float, latitude: float) -> list[Row[Any]]:
        """Головний запит: які поля містять задану точку.

        ST_Contains розкривається планувальником у geom && point AND _ST_Contains(geom, point).
        Перша частина — пошук по GiST-індексу за bounding box (груба фаза), друга —
        точна перевірка належності лише для кількох кандидатів (точна фаза).
        """
        result = await self._session.execute(
            FIND_BY_POINT_SQL, {"lon": longitude, "lat": latitude}
        )
        return list(result.all())


def parse_geometry(raw_geometry: str) -> dict[str, Any]:
    """ST_AsGeoJSON повертає текст — розбираємо його у структуру для відповіді."""
    return json.loads(raw_geometry)
