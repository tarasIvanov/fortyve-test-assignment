from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.geometry import MIN_RING_POINTS, is_coordinate_within_bounds, is_ring_closed

Position = tuple[float, float]


class PolygonGeometry(BaseModel):
    type: Literal["Polygon"]
    coordinates: list[list[Position]]

    @field_validator("coordinates")
    @classmethod
    def validate_rings(cls, rings: list[list[Position]]) -> list[list[Position]]:
        if not rings:
            raise ValueError("Полігон має містити щонайменше одне кільце координат")

        for ring in rings:
            if len(ring) < MIN_RING_POINTS:
                raise ValueError(
                    f"Кільце має містити щонайменше {MIN_RING_POINTS} точки "
                    "(остання дублює першу)"
                )
            if not is_ring_closed(ring):
                raise ValueError("Кільце має бути замкненим: перша точка має збігатися з останньою")
            for longitude, latitude in ring:
                if not is_coordinate_within_bounds(longitude, latitude):
                    raise ValueError(
                        f"Координата [{longitude}, {latitude}] поза допустимим діапазоном "
                        "(довгота -180..180, широта -90..90)"
                    )
        return rings


class FieldCreate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Поле №1 - Пшениця",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [
                            [30.5234, 50.4501],
                            [30.5334, 50.4501],
                        ]
                    ],
                },
                "crop": "Пшениця",
                "owner": "Іванов Т.Ю.",
            }
        }
    )

    name: str = Field(min_length=1, max_length=255)
    geometry: PolygonGeometry
    crop: str = Field(min_length=1, max_length=100)
    owner: str = Field(min_length=1, max_length=255)


class FieldSummary(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "347e88f1-e3fc-4434-bff1-32cb0105b084",
                "name": "Поле №1 - Пшениця",
                "area_ha": 78.99,
                "crop": "Пшениця",
                "owner": "Іванов Т.Ю.",
            }
        },
    )

    id: UUID
    name: str
    area_ha: float
    crop: str
    owner: str


class FieldDetail(FieldSummary):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "347e88f1-e3fc-4434-bff1-32cb0105b084",
                "name": "Поле №1 - Пшениця",
                "area_ha": 78.99,
                "crop": "Пшениця",
                "owner": "Іванов Т.Ю.",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [
                            [30.5234, 50.4501],
                            [30.5334, 50.4501],
                            [30.5334, 50.4601],
                            [30.5234, 50.4601],
                            [30.5234, 50.4501],
                        ]
                    ],
                },
                "created_at": "2026-09-23T18:32:09.686904Z",
            }
        },
    )

    geometry: PolygonGeometry
    created_at: datetime


class FieldListResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "total": 150,
                "fields": [
                    {
                        "id": "347e88f1-e3fc-4434-bff1-32cb0105b084",
                        "name": "Поле №1 - Пшениця",
                        "area_ha": 78.99,
                        "crop": "Пшениця",
                        "owner": "Іванов Т.Ю.",
                    }
                ],
            }
        }
    )

    total: int
    fields: list[FieldSummary]


class QueryPoint(BaseModel):
    lon: float
    lat: float


class FieldMatch(FieldSummary):
    distance_to_center_m: float


class FindByPointResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "query_point": {"lon": 30.525, "lat": 50.455},
                "fields": [
                    {
                        "id": "347e88f1-e3fc-4434-bff1-32cb0105b084",
                        "name": "Поле №1 - Пшениця",
                        "area_ha": 78.99,
                        "crop": "Пшениця",
                        "owner": "Іванов Т.Ю.",
                        "distance_to_center_m": 241.71,
                    }
                ],
                "query_time_ms": 0.34,
            }
        }
    )

    query_point: QueryPoint
    fields: list[FieldMatch]
    query_time_ms: float


class ErrorResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "detail": "Полігон невалідний: Self-intersection[30.525 50.455]",
                "code": "invalid_geometry",
            }
        }
    )

    detail: str
    code: str
