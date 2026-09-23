"""Конструктори тестових даних. Окремо від conftest.py, бо pytest завантажує
conftest власним механізмом — прямий імпорт із нього дав би другий екземпляр модуля."""


def square_polygon(
    center_longitude: float, center_latitude: float, half_side_degrees: float = 0.01
) -> dict:
    left = round(center_longitude - half_side_degrees, 6)
    right = round(center_longitude + half_side_degrees, 6)
    bottom = round(center_latitude - half_side_degrees, 6)
    top = round(center_latitude + half_side_degrees, 6)

    return {
        "type": "Polygon",
        "coordinates": [
            [[left, bottom], [right, bottom], [right, top], [left, top], [left, bottom]]
        ],
    }


def field_payload(
    name: str = "Тестове поле",
    geometry: dict | None = None,
    crop: str = "Пшениця",
    owner: str = "Іванов І.І.",
) -> dict:
    return {
        "name": name,
        "geometry": geometry if geometry is not None else square_polygon(30.52, 50.45),
        "crop": crop,
        "owner": owner,
    }
