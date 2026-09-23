"""Вимірювання швидкості пошуку полів за точкою.

Прогонить однакові запити двічі: з доступним GiST-індексом і з примусово вимкненим,
щоб різниця була не заявленою, а виміряною.

Запуск:
    docker compose exec api python -m scripts.benchmark --points 1000
"""

import argparse
import asyncio
import random
import statistics
import time

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings
from app.repository import FIND_BY_POINT_SQL

# Власний engine із вимкненим кешем підготовлених запитів.
# Інакше asyncpg перевикористав би план, побудований ще з увімкненим індексом,
# і другий прогін міряв би не те, що ми думаємо.
engine = create_async_engine(
    settings.database_url,
    poolclass=NullPool,
    connect_args={"statement_cache_size": 0},
)

# Частка точок, узятих із центрів наявних полів: вони гарантовано в щось влучають.
HIT_POINT_RATIO = 0.7

UKRAINE_BOUNDS = {"min_lon": 22.1, "max_lon": 40.2, "min_lat": 44.4, "max_lat": 52.4}

# DISCARD PLANS додатково скидає плани, які PostgreSQL уже закешував для цієї сесії.
DISABLE_INDEX_SQL = [
    "SET enable_indexscan = off",
    "SET enable_bitmapscan = off",
    "DISCARD PLANS",
]
ENABLE_INDEX_SQL = [
    "SET enable_indexscan = on",
    "SET enable_bitmapscan = on",
    "DISCARD PLANS",
]


async def build_sample_points(
    connection: AsyncConnection, count: int, rng: random.Random
) -> list[tuple[float, float]]:
    hit_count = int(count * HIT_POINT_RATIO)

    centroids = (
        await connection.execute(
            text(
                """
                SELECT ST_X(ST_Centroid(geom)) AS lon, ST_Y(ST_Centroid(geom)) AS lat
                FROM fields
                ORDER BY random()
                LIMIT :limit
                """
            ),
            {"limit": hit_count},
        )
    ).all()

    points = [(row.lon, row.lat) for row in centroids]
    points += [
        (
            rng.uniform(UKRAINE_BOUNDS["min_lon"], UKRAINE_BOUNDS["max_lon"]),
            rng.uniform(UKRAINE_BOUNDS["min_lat"], UKRAINE_BOUNDS["max_lat"]),
        )
        for _ in range(count - len(points))
    ]
    rng.shuffle(points)
    return points


async def measure(
    connection: AsyncConnection, points: list[tuple[float, float]]
) -> tuple[list[float], int]:
    durations_ms: list[float] = []
    total_matches = 0

    for longitude, latitude in points:
        started_at = time.perf_counter()
        rows = (
            await connection.execute(FIND_BY_POINT_SQL, {"lon": longitude, "lat": latitude})
        ).all()
        durations_ms.append((time.perf_counter() - started_at) * 1000)
        total_matches += len(rows)

    return durations_ms, total_matches


async def explain(connection: AsyncConnection, point: tuple[float, float]) -> str:
    plan = (
        await connection.execute(
            text(f"EXPLAIN (ANALYZE, BUFFERS) {FIND_BY_POINT_SQL.text}"),
            {"lon": point[0], "lat": point[1]},
        )
    ).all()
    return "\n".join(row[0] for row in plan)


def report(title: str, durations_ms: list[float], total_matches: int, point_count: int) -> None:
    ordered = sorted(durations_ms)
    print(f"\n{title}")
    print(f"  медіана (p50): {statistics.median(ordered):8.2f} мс")
    print(f"  p95:           {ordered[int(len(ordered) * 0.95) - 1]:8.2f} мс")
    print(f"  максимум:      {max(ordered):8.2f} мс")
    print(f"  середнє:       {statistics.mean(ordered):8.2f} мс")
    print(f"  знайдено полів: {total_matches} на {point_count} запитів")


async def run(point_count: int, random_seed: int) -> None:
    rng = random.Random(random_seed)

    async with engine.connect() as connection:
        total_fields = (await connection.execute(text("SELECT count(*) FROM fields"))).scalar_one()
        print(f"Полів у базі: {total_fields}")
        print(f"Точок у прогоні: {point_count}")

        points = await build_sample_points(connection, point_count, rng)

        for statement in ENABLE_INDEX_SQL:
            await connection.execute(text(statement))
        indexed_durations, indexed_matches = await measure(connection, points)
        indexed_plan = await explain(connection, points[0])

        for statement in DISABLE_INDEX_SQL:
            await connection.execute(text(statement))
        sequential_durations, sequential_matches = await measure(connection, points)
        sequential_plan = await explain(connection, points[0])

    await engine.dispose()

    report("З GiST-індексом", indexed_durations, indexed_matches, point_count)
    report("Без індексу (примусовий seq scan)", sequential_durations, sequential_matches, point_count)

    speedup = statistics.median(sequential_durations) / statistics.median(indexed_durations)
    print(f"\nПрискорення за медіаною: ×{speedup:.0f}")

    print("\nПлан з індексом:\n" + indexed_plan)
    print("\nПлан без індексу:\n" + sequential_plan)


def main() -> None:
    parser = argparse.ArgumentParser(description="Бенчмарк пошуку полів за точкою")
    parser.add_argument("--points", type=int, default=1000, help="Кількість тестових точок")
    parser.add_argument("--seed", type=int, default=7, help="Зерно генератора для відтворюваності")
    arguments = parser.parse_args()

    asyncio.run(run(arguments.points, arguments.seed))


if __name__ == "__main__":
    main()
