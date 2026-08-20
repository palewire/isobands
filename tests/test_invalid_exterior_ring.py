"""Regression tests for exact self-touching GDAL exterior-ring normalization."""

from __future__ import annotations

import pytest
from shapely.geometry import Point, Polygon
from shapely.validation import explain_validity

from isobands._gdal import _normalize_polygon_ring_roles


def _self_touching_exterior() -> tuple[tuple[float, float], ...]:
    """Return a large shell with a small exact repeated-vertex loop."""
    return (
        (0.0, 0.0),
        (10.0, 0.0),
        (10.0, 10.0),
        (0.0, 10.0),
        (0.0, 0.0),
        (2.0, 2.0),
        (4.0, 2.0),
        (4.0, 4.0),
        (2.0, 4.0),
        (2.0, 2.0),
        (0.0, 0.0),
    )


def test_self_touching_exterior_preserves_valid_contained_interior() -> None:
    """An exact exterior loop and a valid hole remain separate holes."""
    main_shell = (
        (0.0, 0.0),
        (10.0, 0.0),
        (10.0, 10.0),
        (0.0, 10.0),
        (0.0, 0.0),
    )
    repeated_loop = (
        (2.0, 2.0),
        (4.0, 2.0),
        (4.0, 4.0),
        (2.0, 4.0),
        (2.0, 2.0),
    )
    existing_hole = (
        (6.0, 6.0),
        (7.0, 6.0),
        (7.0, 7.0),
        (6.0, 7.0),
        (6.0, 6.0),
    )
    polygon = Polygon(_self_touching_exterior(), [existing_hole])

    assert not polygon.is_valid
    assert explain_validity(Polygon(polygon.exterior.coords)).startswith(
        "Ring Self-intersection"
    )

    parts = _normalize_polygon_ring_roles(polygon)

    assert parts.promoted == ()
    assert len(parts.retained) == 1
    result = parts.retained[0]
    expected = Polygon(main_shell, [repeated_loop, existing_hole])
    assert result.is_valid
    assert result.symmetric_difference(expected).area == 0.0
    assert result.area == pytest.approx(95.0)
    assert tuple(result.exterior.coords) == main_shell
    assert tuple(tuple(ring.coords) for ring in result.interiors) == (
        repeated_loop,
        existing_hole,
    )
    assert result.covers(Point(1.0, 1.0))
    assert not result.covers(Point(3.0, 3.0))
    assert not result.covers(Point(6.5, 6.5))


def test_self_touching_exterior_promotes_valid_outside_interior() -> None:
    """A valid original interior outside the rebuilt shell remains a candidate."""
    outside_ring = (
        (12.0, 0.0),
        (13.0, 0.0),
        (13.0, 1.0),
        (12.0, 1.0),
        (12.0, 0.0),
    )
    parts = _normalize_polygon_ring_roles(
        Polygon(_self_touching_exterior(), [outside_ring])
    )

    assert len(parts.retained) == len(parts.promoted) == 1
    assert parts.retained[0].is_valid
    assert parts.promoted[0].equals_exact(Polygon(outside_ring), tolerance=0.0)


def test_self_touching_exterior_rejects_invalid_original_interior() -> None:
    """An invalid original interior is not repaired while rebuilding the exterior."""
    invalid_ring = (
        (6.0, 6.0),
        (8.0, 8.0),
        (8.0, 6.0),
        (6.0, 8.0),
        (6.0, 6.0),
    )

    with pytest.raises(RuntimeError, match="invalid contour interior ring"):
        _normalize_polygon_ring_roles(
            Polygon(_self_touching_exterior(), [invalid_ring])
        )


def test_ambiguously_nested_self_touching_exterior_raises() -> None:
    """Exact loops nested more than once remain explicitly rejected."""
    nested_exterior = (
        (0.0, 0.0),
        (10.0, 0.0),
        (10.0, 10.0),
        (0.0, 10.0),
        (0.0, 0.0),
        (2.0, 2.0),
        (8.0, 2.0),
        (8.0, 8.0),
        (2.0, 8.0),
        (2.0, 2.0),
        (3.0, 3.0),
        (7.0, 3.0),
        (7.0, 7.0),
        (3.0, 7.0),
        (3.0, 3.0),
        (0.0, 0.0),
    )

    with pytest.raises(RuntimeError, match="ambiguously nested contour exteriors"):
        _normalize_polygon_ring_roles(Polygon(nested_exterior))
