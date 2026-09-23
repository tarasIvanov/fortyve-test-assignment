import time
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.repository import FieldRepository
from app.schemas import (
    ErrorResponse,
    FieldCreate,
    FieldDetail,
    FieldListResponse,
    FindByPointResponse,
    QueryPoint,
)
from app.service import FieldService

router = APIRouter(
    prefix="/api/fields",
    tags=["fields"],
    responses={404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)

MAX_PAGE_SIZE = 100
DEFAULT_PAGE_SIZE = 20


def get_field_service(session: AsyncSession = Depends(get_session)) -> FieldService:
    return FieldService(FieldRepository(session))


@router.post("", response_model=FieldDetail, status_code=status.HTTP_201_CREATED)
async def create_field(
    payload: FieldCreate,
    service: FieldService = Depends(get_field_service),
) -> FieldDetail:
    return await service.create_field(payload)


@router.get("", response_model=FieldListResponse)
async def list_fields(
    crop: str | None = Query(default=None, description="Тип культури"),
    owner: str | None = Query(default=None, description="Власник"),
    min_area: float | None = Query(default=None, ge=0, description="Мінімальна площа, га"),
    max_area: float | None = Query(default=None, ge=0, description="Максимальна площа, га"),
    limit: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    offset: int = Query(default=0, ge=0),
    service: FieldService = Depends(get_field_service),
) -> FieldListResponse:
    total, fields = await service.list_fields(
        crop=crop,
        owner=owner,
        min_area=min_area,
        max_area=max_area,
        limit=limit,
        offset=offset,
    )
    return FieldListResponse(total=total, fields=fields)


# Оголошено до /{field_id}: інакше FastAPI зматчить "find-by-point" як значення field_id.
@router.get("/find-by-point", response_model=FindByPointResponse)
async def find_fields_by_point(
    lon: float = Query(..., ge=-180, le=180, description="Довгота"),
    lat: float = Query(..., ge=-90, le=90, description="Широта"),
    service: FieldService = Depends(get_field_service),
) -> FindByPointResponse:
    started_at = time.perf_counter()
    matches = await service.find_by_point(lon, lat)
    query_time_ms = (time.perf_counter() - started_at) * 1000

    return FindByPointResponse(
        query_point=QueryPoint(lon=lon, lat=lat),
        fields=matches,
        query_time_ms=round(query_time_ms, 2),
    )


@router.get("/{field_id}", response_model=FieldDetail)
async def get_field(
    field_id: UUID,
    service: FieldService = Depends(get_field_service),
) -> FieldDetail:
    return await service.get_field(field_id)
