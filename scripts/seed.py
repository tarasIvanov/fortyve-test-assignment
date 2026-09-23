"""Генерація тестових даних: реалістичні поля на території України.

Запуск:
    docker compose exec api python -m scripts.seed --count 50000 --truncate
"""

import argparse
import asyncio
import random
import time

from sqlalchemy import text

from app.db import engine
from app.geometry import build_closed_ring, ring_to_wkt

# Центри областей: поля групуються навколо них, як у реальності, а не рівномірним шумом.
REGIONAL_CENTERS = [
    ("Київщина", 30.52, 50.45),
    ("Львівщина", 24.03, 49.84),
    ("Одещина", 30.73, 46.48),
    ("Харківщина", 36.23, 49.99),
    ("Дніпропетровщина", 35.05, 48.46),
    ("Вінниччина", 28.47, 49.23),
    ("Полтавщина", 34.55, 49.59),
    ("Запоріжжя", 35.14, 47.84),
    ("Херсонщина", 32.62, 46.64),
    ("Черкащина", 32.06, 49.44),
    ("Житомирщина", 28.66, 50.25),
    ("Миколаївщина", 31.99, 46.98),
]

CROPS = ["Пшениця", "Кукурудза", "Соняшник", "Ріпак", "Соя", "Ячмінь", "Цукровий буряк"]

OWNERS = [
    "Іванов І.І.", "Петренко О.М.", "Коваленко С.В.", "Шевченко А.П.",
    "Бондаренко М.І.", 'ТОВ "Агро-Нива"', 'ТОВ "Зерно України"', 'ФГ "Лан"',
    'ПП "Урожай"', 'ТОВ "Степове"',
]

REGION_SPREAD_DEGREES = 1.2
MIN_RADIUS_METERS = 120
MAX_RADIUS_METERS = 1500
MIN_VERTICES = 6
MAX_VERTICES = 12
RADIUS_JITTER = 0.3
OVERLAP_PROBABILITY = 0.12
BATCH_SIZE = 1000

INSERT_SQL = text(
    """
    INSERT INTO fields (name, geom, area_ha, crop, owner)
    VALUES (
        :name,
        ST_GeomFromText(:wkt, 4326),
        ST_Area(ST_GeomFromText(:wkt, 4326)::geography) / 10000,
        :crop,
        :owner
    )
    """
)


def generate_batch(
    rng: random.Random, start_index: int, size: int, previous_center: tuple[float, float] | None
) -> tuple[list[dict], tuple[float, float]]:
    rows: list[dict] = []
    center = previous_center

    for offset in range(size):
        overlaps_previous = center is not None and rng.random() < OVERLAP_PROBABILITY

        if overlaps_previous:
            # Зсув менший за радіус поля гарантує перетин із попереднім.
            center_longitude = center[0] + rng.uniform(-0.004, 0.004)
            center_latitude = center[1] + rng.uniform(-0.004, 0.004)
        else:
            region_name, region_longitude, region_latitude = rng.choice(REGIONAL_CENTERS)
            center_longitude = region_longitude + rng.uniform(-REGION_SPREAD_DEGREES, REGION_SPREAD_DEGREES)
            center_latitude = region_latitude + rng.uniform(-REGION_SPREAD_DEGREES, REGION_SPREAD_DEGREES)

        center = (center_longitude, center_latitude)

        ring = build_closed_ring(
            center_longitude=center_longitude,
            center_latitude=center_latitude,
            radius_meters=rng.uniform(MIN_RADIUS_METERS, MAX_RADIUS_METERS),
            vertex_count=rng.randint(MIN_VERTICES, MAX_VERTICES),
            radius_jitter=RADIUS_JITTER,
            rng=rng,
        )

        crop = rng.choice(CROPS)
        rows.append(
            {
                "name": f"Поле №{start_index + offset + 1} - {crop}",
                "wkt": ring_to_wkt(ring),
                "crop": crop,
                "owner": rng.choice(OWNERS),
            }
        )

    return rows, center


async def seed(count: int, truncate: bool, random_seed: int) -> None:
    rng = random.Random(random_seed)
    started_at = time.perf_counter()

    async with engine.begin() as connection:
        if truncate:
            await connection.execute(text("TRUNCATE TABLE fields"))
            print("Таблиця fields очищена")

        previous_center: tuple[float, float] | None = None
        inserted = 0

        while inserted < count:
            batch_size = min(BATCH_SIZE, count - inserted)
            rows, previous_center = generate_batch(rng, inserted, batch_size, previous_center)
            await connection.execute(INSERT_SQL, rows)
            inserted += batch_size

            if inserted % 10_000 == 0 or inserted == count:
                print(f"Вставлено {inserted}/{count}")

    async with engine.begin() as connection:
        # Без свіжої статистики планувальник може проігнорувати GiST-індекс.
        await connection.execute(text("ANALYZE fields"))

    await engine.dispose()
    print(f"Готово за {time.perf_counter() - started_at:.1f} с")


def main() -> None:
    parser = argparse.ArgumentParser(description="Генерація тестових полів")
    parser.add_argument("--count", type=int, default=50_000, help="Кількість полів")
    parser.add_argument("--truncate", action="store_true", help="Очистити таблицю перед генерацією")
    parser.add_argument("--seed", type=int, default=42, help="Зерно генератора для відтворюваності")
    arguments = parser.parse_args()

    asyncio.run(seed(arguments.count, arguments.truncate, arguments.seed))


if __name__ == "__main__":
    main()
