from uuid import uuid4

from httpx import AsyncClient

from tests.integration.factories import field_payload, square_polygon


async def test_field_is_created_with_calculated_area(client: AsyncClient):
    response = await client.post("/api/fields", json=field_payload())

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Тестове поле"
    assert body["geometry"]["type"] == "Polygon"
    # Квадрат 0.02° × 0.02° на широті 50° — приблизно 315 га.
    assert 300 < body["area_ha"] < 330


async def test_self_intersecting_polygon_is_rejected(client: AsyncClient):
    butterfly = {
        "type": "Polygon",
        "coordinates": [
            [[30.52, 50.45], [30.53, 50.46], [30.53, 50.45], [30.52, 50.46], [30.52, 50.45]]
        ],
    }

    response = await client.post("/api/fields", json=field_payload(geometry=butterfly))

    assert response.status_code == 422
    assert response.json()["code"] == "invalid_geometry"


async def test_unclosed_ring_is_rejected(client: AsyncClient):
    unclosed = {
        "type": "Polygon",
        "coordinates": [[[30.52, 50.45], [30.54, 50.45], [30.54, 50.47], [30.52, 50.47]]],
    }

    response = await client.post("/api/fields", json=field_payload(geometry=unclosed))

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


async def test_polygon_with_hole_is_rejected(client: AsyncClient):
    with_hole = square_polygon(30.52, 50.45)
    with_hole["coordinates"].append(square_polygon(30.52, 50.45, half_side_degrees=0.002)["coordinates"][0])

    response = await client.post("/api/fields", json=field_payload(geometry=with_hole))

    assert response.status_code == 422
    assert response.json()["code"] == "unsupported_geometry"


async def test_too_small_field_is_rejected(client: AsyncClient):
    tiny = square_polygon(30.52, 50.45, half_side_degrees=0.00005)

    response = await client.post("/api/fields", json=field_payload(geometry=tiny))

    assert response.status_code == 422
    assert response.json()["code"] == "area_too_small"


async def test_point_inside_two_overlapping_fields_returns_both(client: AsyncClient):
    await client.post("/api/fields", json=field_payload(name="Перше", geometry=square_polygon(30.52, 50.45)))
    await client.post(
        "/api/fields",
        json=field_payload(name="Друге", geometry=square_polygon(30.525, 50.455), owner="Петренко О.М."),
    )

    response = await client.get("/api/fields/find-by-point", params={"lon": 30.523, "lat": 50.453})

    assert response.status_code == 200
    body = response.json()
    assert {field["name"] for field in body["fields"]} == {"Перше", "Друге"}
    assert body["query_point"] == {"lon": 30.523, "lat": 50.453}
    assert body["query_time_ms"] > 0


async def test_point_outside_any_field_returns_empty_list(client: AsyncClient):
    await client.post("/api/fields", json=field_payload())

    response = await client.get("/api/fields/find-by-point", params={"lon": 24.0, "lat": 48.0})

    assert response.status_code == 200
    assert response.json()["fields"] == []


async def test_list_is_filtered_by_crop_and_owner(client: AsyncClient):
    await client.post("/api/fields", json=field_payload(name="Пшеничне", crop="Пшениця"))
    await client.post(
        "/api/fields",
        json=field_payload(name="Соєве", crop="Соя", geometry=square_polygon(31.0, 50.0)),
    )

    response = await client.get("/api/fields", params={"crop": "Соя"})

    body = response.json()
    assert body["total"] == 1
    assert body["fields"][0]["name"] == "Соєве"


async def test_list_is_paginated_and_reports_total(client: AsyncClient):
    for index in range(3):
        await client.post(
            "/api/fields",
            json=field_payload(name=f"Поле {index}", geometry=square_polygon(30.0 + index, 50.0)),
        )

    response = await client.get("/api/fields", params={"limit": 2, "offset": 0})

    body = response.json()
    assert body["total"] == 3
    assert len(body["fields"]) == 2


async def test_field_details_contain_full_geometry(client: AsyncClient):
    created = (await client.post("/api/fields", json=field_payload())).json()

    response = await client.get(f"/api/fields/{created['id']}")

    assert response.status_code == 200
    assert response.json()["geometry"]["coordinates"] == field_payload()["geometry"]["coordinates"]


async def test_unknown_field_returns_not_found(client: AsyncClient):
    response = await client.get(f"/api/fields/{uuid4()}")

    assert response.status_code == 404
    assert response.json()["code"] == "not_found"
