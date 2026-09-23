"""Чисті геометричні обчислення без участі БД.

Усе, що потребує PostGIS (самоперетини, площа на еліпсоїді, належність точки),
живе в SQL. Тут — лише те, що можна порахувати й перевірити без бази.
"""

import math
import random
from collections.abc import Sequence

Coordinate = tuple[float, float]

METERS_PER_DEGREE_LATITUDE = 111_320.0
MIN_RING_POINTS = 4
COORDINATE_PRECISION = 6

MIN_LONGITUDE, MAX_LONGITUDE = -180.0, 180.0
MIN_LATITUDE, MAX_LATITUDE = -90.0, 90.0


def is_ring_closed(ring: Sequence[Coordinate]) -> bool:
    return len(ring) >= 2 and tuple(ring[0]) == tuple(ring[-1])


def is_coordinate_within_bounds(longitude: float, latitude: float) -> bool:
    return (
        MIN_LONGITUDE <= longitude <= MAX_LONGITUDE
        and MIN_LATITUDE <= latitude <= MAX_LATITUDE
    )


def meters_to_degrees(meters: float, latitude: float) -> tuple[float, float]:
    """Переводить відстань у метрах у зсув за довготою та широтою.

    Градус широти майже сталий (~111 км), а градус довготи звужується до полюсів
    пропорційно косинусу широти: на 50° він приблизно вдвічі коротший за екваторіальний.
    """
    degrees_latitude = meters / METERS_PER_DEGREE_LATITUDE
    degrees_longitude = meters / (METERS_PER_DEGREE_LATITUDE * math.cos(math.radians(latitude)))
    return degrees_longitude, degrees_latitude


def build_closed_ring(
    center_longitude: float,
    center_latitude: float,
    radius_meters: float,
    vertex_count: int,
    radius_jitter: float,
    rng: random.Random,
) -> list[Coordinate]:
    """Будує замкнене кільце навколо центру.

    Вершини розкидані по колу і відсортовані за кутом — саме сортування гарантує,
    що межа не перетне сама себе, тобто полігон вийде валідним.
    """
    angles = sorted(rng.uniform(0.0, 2 * math.pi) for _ in range(vertex_count))

    ring: list[Coordinate] = []
    for angle in angles:
        radius = radius_meters * rng.uniform(1.0 - radius_jitter, 1.0 + radius_jitter)
        degrees_longitude, degrees_latitude = meters_to_degrees(radius, center_latitude)
        ring.append(
            (
                round(center_longitude + degrees_longitude * math.cos(angle), COORDINATE_PRECISION),
                round(center_latitude + degrees_latitude * math.sin(angle), COORDINATE_PRECISION),
            )
        )

    ring.append(ring[0])
    return ring


def ring_to_wkt(ring: Sequence[Coordinate]) -> str:
    points = ", ".join(f"{longitude} {latitude}" for longitude, latitude in ring)
    return f"POLYGON(({points}))"
