"""Regression tests for GDAL 3.13.2 invalid interior ring normalization.

GDAL 3.13.2 can emit a polygon whose interior ring is a self-touching
figure-8 (``Ring Self-intersection`` in shapely).  The ring has nonzero area
but ``is_valid == False``.  The fix reuses the same repeated-vertex loop
splitting that already normalizes self-touching exterior rings, then
classifies each resulting simple polygon as a retained hole or an outside
promoted candidate.  Ambiguous or malformed invalid interior rings must still
raise explicitly.
"""

from __future__ import annotations

import pytest
from shapely.geometry import Polygon
from shapely.validation import explain_validity

from isobands._gdal import _normalize_polygon_ring_roles

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _diamond(cx: float, cy: float, r: float) -> list[tuple[float, float]]:
    """Return a closed diamond ring centred at (cx, cy) with half-extent r."""
    return [(cx, cy + r), (cx + r, cy), (cx, cy - r), (cx - r, cy), (cx, cy + r)]


# ---------------------------------------------------------------------------
# Pattern classification
# ---------------------------------------------------------------------------


def test_self_touching_interior_ring_is_ring_self_intersection() -> None:
    """The GDAL 3.13.2 interior-ring pattern reports Ring Self-intersection."""

    # Figure-8: upper diamond (5,7) and lower diamond (5,3) sharing vertex (5,5)
    ring_coords = (
        (5.0, 5.0),
        (3.0, 7.0),
        (5.0, 9.0),
        (7.0, 7.0),
        (5.0, 5.0),
        (7.0, 3.0),
        (5.0, 1.0),
        (3.0, 3.0),
        (5.0, 5.0),
    )
    ring = Polygon(ring_coords)
    assert not ring.is_valid
    assert ring.area > 0.0
    assert explain_validity(ring).startswith("Ring Self-intersection")


# ---------------------------------------------------------------------------
# Accepted pattern: both sub-rings inside the shell → two retained holes
# ---------------------------------------------------------------------------


def test_self_touching_interior_ring_both_inside_produces_two_holes() -> None:
    """Both loops of a figure-8 that lies inside the shell become retained holes."""

    # Shell: (0,0)-(10,10); figure-8 fully inside
    shell_coords = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0), (0.0, 0.0)]
    ring_coords = (
        (5.0, 5.0),
        (3.0, 7.0),
        (5.0, 9.0),
        (7.0, 7.0),
        (5.0, 5.0),
        (7.0, 3.0),
        (5.0, 1.0),
        (3.0, 3.0),
        (5.0, 5.0),
    )
    polygon = Polygon(shell_coords, [ring_coords])
    assert not polygon.is_valid

    parts = _normalize_polygon_ring_roles(polygon)

    # One retained polygon (the shell with two holes); no promoted rings
    assert len(parts.retained) == 1
    assert parts.promoted == ()

    result = parts.retained[0]
    assert result.is_valid
    # Shell area minus two diamond holes (each area=8)
    assert abs(result.area - (100.0 - 8.0 - 8.0)) < 1e-9
    assert len(list(result.interiors)) == 2


# ---------------------------------------------------------------------------
# Accepted pattern: one sub-ring outside the shell → one hole + one promoted
# ---------------------------------------------------------------------------


def test_self_touching_interior_ring_one_outside_is_promoted() -> None:
    """A figure-8 whose lower loop is outside the shell is promoted.

    Shared vertex (5, 0) sits on the shell boundary; the lower diamond
    (centred at (5, -2)) lies entirely below y=0 and therefore
    ``shell.touches(lower_loop)`` is True → promoted, not a hole.
    """

    # Shell: standard (0,0)-(10,10) box
    shell_coords = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0), (0.0, 0.0)]
    # Shared vertex at (5, 0) on shell boundary; upper loop inside, lower outside
    ring_coords = (
        (5.0, 0.0),
        (3.0, 2.0),
        (5.0, 4.0),
        (7.0, 2.0),
        (5.0, 0.0),
        (7.0, -2.0),
        (5.0, -4.0),
        (3.0, -2.0),
        (5.0, 0.0),
    )
    polygon = Polygon(shell_coords, [ring_coords])
    assert not polygon.is_valid

    parts = _normalize_polygon_ring_roles(polygon)

    assert len(parts.retained) == 1
    assert len(parts.promoted) == 1

    assert parts.retained[0].is_valid
    assert parts.promoted[0].is_valid
    # Shell area (100) minus the upper-loop hole (area=8)
    assert abs(parts.retained[0].area - (100.0 - 8.0)) < 1e-9
    assert abs(parts.promoted[0].area - 8.0) < 1e-9


# ---------------------------------------------------------------------------
# Rejected: a touching-vertex ring that lands neither inside nor outside
# ---------------------------------------------------------------------------


def test_invalid_interior_ring_overlapping_shell_raises() -> None:
    """An interior ring that partially overlaps the shell boundary still raises."""

    # Shell: (0,0)-(4,4); interior ring overlaps the boundary
    shell_coords = [(0.0, 0.0), (4.0, 0.0), (4.0, 4.0), (0.0, 4.0), (0.0, 0.0)]
    # Two diamonds sharing (3,2): the right loop (centred at (5,2)) is half outside
    ring_coords = (
        (3.0, 2.0),
        (1.0, 4.0),
        (3.0, 6.0),
        (5.0, 4.0),
        (3.0, 2.0),
        (5.0, 0.0),
        (3.0, -2.0),
        (1.0, 0.0),
        (3.0, 2.0),
    )
    polygon = Polygon(shell_coords, [ring_coords])
    assert not polygon.is_valid

    with pytest.raises(RuntimeError, match="invalid contour interior ring"):
        _normalize_polygon_ring_roles(polygon)


# ---------------------------------------------------------------------------
# Rejected: genuinely malformed ring (not a repeated-vertex figure-8)
# ---------------------------------------------------------------------------


def test_self_intersecting_zero_area_interior_ring_is_silently_dropped() -> None:
    """A self-intersecting interior ring whose signed area cancels to zero is dropped.

    The bowtie ring (1,1),(9,9),(9,1),(1,9),(1,1) self-intersects at (5,5)
    but the two triangles wind oppositely so the shoelace area is exactly
    zero.  The code treats it as a zero-area artifact — it is silently
    omitted rather than raising, and the resulting polygon is the intact
    outer shell.
    """
    from shapely import from_wkt

    bowtie_wkt = "POLYGON ((0 0, 10 0, 10 10, 0 10, 0 0), (1 1, 9 9, 9 1, 1 9, 1 1))"
    polygon = from_wkt(bowtie_wkt)
    assert not polygon.is_valid
    # The interior ring's zero area means it cannot carry domain coverage.
    for ring in polygon.interiors:
        assert Polygon(ring.coords).area == 0.0

    parts = _normalize_polygon_ring_roles(polygon)

    # Silently dropped: the result is just the shell with no holes or promoted rings.
    assert len(parts.retained) == 1
    assert parts.promoted == ()
    assert parts.retained[0].is_valid
    assert abs(parts.retained[0].area - 100.0) < 1e-9


# ---------------------------------------------------------------------------
# Regression: existing valid interior rings are still handled correctly
# ---------------------------------------------------------------------------


def test_valid_interior_ring_inside_shell_is_retained_as_hole() -> None:
    """A normal valid hole is unchanged."""

    polygon = Polygon(
        [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0), (0.0, 0.0)],
        [_diamond(5.0, 5.0, 2.0)],
    )
    assert polygon.is_valid

    parts = _normalize_polygon_ring_roles(polygon)

    assert len(parts.retained) == 1
    assert parts.promoted == ()
    assert parts.retained[0].is_valid
    assert abs(parts.retained[0].area - (100.0 - 8.0)) < 1e-9


def test_valid_interior_ring_outside_shell_is_promoted() -> None:
    """A valid ring that lies outside the shell is promoted (existing path)."""

    polygon = Polygon(
        [(0.0, 0.0), (2.0, 0.0), (2.0, 2.0), (0.0, 2.0), (0.0, 0.0)],
        [[(2.0, 2.0), (3.0, 2.0), (3.0, 3.0), (2.0, 2.0)]],
    )
    assert not polygon.is_valid

    parts = _normalize_polygon_ring_roles(polygon)

    assert len(parts.retained) == 1
    assert len(parts.promoted) == 1
    assert parts.retained[0].area == 4.0
    assert abs(parts.promoted[0].area - 0.5) < 1e-9
