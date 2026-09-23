from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.geometry import MIN_RING_POINTS, is_coordinate_within_bounds, is_ring_closed

Position = tuple[float, float]


class PolygonGeometry(BaseModel):
    """GeoJSON-полігон. Координати в порядку [довгота, широта], як у специфікації GeoJSON."""

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
    name: str = Field(min_length=1, max_length=255)
    geometry: PolygonGeometry
    crop: str = Field(min_length=1, max_length=100)
    owner: str = Field(min_length=1, max_length=255)


class FieldSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    area_ha: float
    crop: str
    owner: str


class FieldDetail(FieldSummary):
    geometry: PolygonGeometry
    created_at: datetime


class FieldListResponse(BaseModel):
    total: int
    fields: list[FieldSummary]


class QueryPoint(BaseModel):
    lon: float
    lat: float


class FieldMatch(FieldSummary):
    distance_to_center_m: float


class FindByPointResponse(BaseModel):
    query_point: QueryPoint
    fields: list[FieldMatch]
    query_time_ms: float


class ErrorResponse(BaseModel):
    detail: str
    code: str
