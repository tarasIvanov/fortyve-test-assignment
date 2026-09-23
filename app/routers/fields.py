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


@router.post(
    "",
    response_model=FieldDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Створити поле",
    description=(
        "Приймає межі поля як GeoJSON-полігон з одним замкненим кільцем: перша точка "
        "збігається з останньою.\n\n"
        "Площа обчислюється на еліпсоїді WGS84 і має перевищувати 0.1 га. Полігони "
        "з самоперетинами та з дірками відхиляються з кодом 422."
    ),
    response_description="Створене поле з обчисленою площею",
)
async def create_field(
    payload: FieldCreate,
    service: FieldService = Depends(get_field_service),
) -> FieldDetail:
    return await service.create_field(payload)


@router.get(
    "",
    response_model=FieldListResponse,
    summary="Список полів",
    description=(
        "Фільтри комбінуються між собою. `total` — кількість полів, що пройшли фільтри, "
        "незалежно від пагінації.\n\n"
        "Геометрія у списку не повертається: для повного полігона є окремий endpoint."
    ),
    response_description="Сторінка списку та загальна кількість",
)
async def list_fields(
    crop: str | None = Query(default=None, description="Тип культури"),
    owner: str | None = Query(default=None, description="Власник"),
    min_area: float | None = Query(default=None, ge=0, description="Мінімальна площа, га"),
    max_area: float | None = Query(default=None, ge=0, description="Максимальна площа, га"),
    limit: int = Query(
        default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE, description="Розмір сторінки"
    ),
    offset: int = Query(default=0, ge=0, description="Зсув від початку списку"),
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


@router.get(
    "/find-by-point",
    response_model=FindByPointResponse,
    summary="Пошук полів за точкою",
    description=(
        "Повертає всі поля, що містять задану точку, відсортовані за відстанню до центроїда. "
        "Полів може бути кілька, якщо вони перекриваються.\n\n"
        "`query_time_ms` — час виконання SQL-запиту в базі: без конвертації рядків "
        "у моделі та без серіалізації відповіді."
    ),
    response_description="Знайдені поля та час виконання запиту",
)
async def find_fields_by_point(
    lon: float = Query(..., ge=-180, le=180, description="Довгота точки"),
    lat: float = Query(..., ge=-90, le=90, description="Широта точки"),
    service: FieldService = Depends(get_field_service),
) -> FindByPointResponse:
    matches, query_time_ms = await service.find_by_point(lon, lat)

    return FindByPointResponse(
        query_point=QueryPoint(lon=lon, lat=lat),
        fields=matches,
        query_time_ms=query_time_ms,
    )


@router.get(
    "/{field_id}",
    response_model=FieldDetail,
    summary="Деталі поля",
    description="Повертає поле разом із повною геометрією.",
    response_description="Поле з повною геометрією",
)
async def get_field(
    field_id: UUID,
    service: FieldService = Depends(get_field_service),
) -> FieldDetail:
    return await service.get_field(field_id)
