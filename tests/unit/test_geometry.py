import math
import random

import pytest

from app.geometry import (
    build_closed_ring,
    is_coordinate_within_bounds,
    is_ring_closed,
    meters_to_degrees,
    ring_to_wkt,
)


def test_closed_ring_is_recognised():
    ring = [(30.0, 50.0), (30.1, 50.0), (30.1, 50.1), (30.0, 50.0)]
    assert is_ring_closed(ring)


def test_unclosed_ring_is_rejected():
    ring = [(30.0, 50.0), (30.1, 50.0), (30.1, 50.1)]
    assert not is_ring_closed(ring)


@pytest.mark.parametrize(
    ("longitude", "latitude", "expected"),
    [
        (30.5, 50.4, True),
        (-180.0, -90.0, True),
        (180.1, 50.0, False),
        (30.0, 90.5, False),
    ],
)
def test_coordinate_bounds(longitude, latitude, expected):
    assert is_coordinate_within_bounds(longitude, latitude) is expected


def test_degree_of_longitude_is_shorter_than_degree_of_latitude_in_ukraine():
    """На широті 50° градус довготи коротший за градус широти приблизно в 1.5 раза."""
    degrees_longitude, degrees_latitude = meters_to_degrees(1000, latitude=50.0)

    assert degrees_longitude > degrees_latitude
    assert degrees_longitude / degrees_latitude == pytest.approx(1 / math.cos(math.radians(50)), rel=1e-6)


def test_degrees_match_expected_distance_at_equator():
    degrees_longitude, degrees_latitude = meters_to_degrees(111_320, latitude=0.0)

    assert degrees_latitude == pytest.approx(1.0)
    assert degrees_longitude == pytest.approx(1.0)


def test_generated_ring_is_closed_and_has_expected_vertex_count():
    ring = build_closed_ring(
        center_longitude=30.5,
        center_latitude=50.4,
        radius_meters=500,
        vertex_count=8,
        radius_jitter=0.3,
        rng=random.Random(1),
    )

    assert len(ring) == 9
    assert is_ring_closed(ring)


def test_generated_ring_has_no_duplicate_vertices():
    """Злиплі вершини після округлення зробили б полігон невалідним для PostGIS."""
    for seed in range(200):
        ring = build_closed_ring(
            center_longitude=30.5,
            center_latitude=50.4,
            radius_meters=120,
            vertex_count=12,
            radius_jitter=0.3,
            rng=random.Random(seed),
        )
        vertices = ring[:-1]
        assert len(set(vertices)) == len(vertices)


def test_generated_vertices_go_counterclockwise_without_self_intersection():
    """Кути мають монотонно зростати — саме це гарантує відсутність самоперетинів."""
    center_longitude, center_latitude = 30.5, 50.4
    ring = build_closed_ring(
        center_longitude=center_longitude,
        center_latitude=center_latitude,
        radius_meters=800,
        vertex_count=10,
        radius_jitter=0.3,
        rng=random.Random(5),
    )

    angles = [
        math.atan2(latitude - center_latitude, longitude - center_longitude) % (2 * math.pi)
        for longitude, latitude in ring[:-1]
    ]

    # Кути зростають по колу, тому спадання може статися рівно один раз — там, де послідовність перетинає нуль.
    descents = sum(
        1 for index in range(len(angles)) if angles[index] > angles[(index + 1) % len(angles)]
    )
    assert descents == 1


def test_ring_is_rendered_as_wkt_polygon():
    ring = [(30.0, 50.0), (30.1, 50.0), (30.1, 50.1), (30.0, 50.0)]

    assert ring_to_wkt(ring) == "POLYGON((30.0 50.0, 30.1 50.0, 30.1 50.1, 30.0 50.0))"
