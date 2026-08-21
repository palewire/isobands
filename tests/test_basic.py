"""Core public API tests."""

from __future__ import annotations

import inspect
from itertools import combinations

import numpy as np
import xarray as xr
from shapely.geometry import Point, box
from shapely.ops import unary_union

import isobands


def test_public_api_exports_runtime_check_and_from_raster() -> None:
    """The package exports its contour API and runtime diagnostics."""

    assert isobands.__all__ == ["CheckReport", "CheckResult", "check", "from_raster"]
    assert not hasattr(isobands, "isobands")
    assert tuple(inspect.signature(isobands.from_raster).parameters) == (
        "data",
        "levels",
        "interval",
        "offset",
        "crs",
        "nodata",
    )


def test_from_raster_returns_valid_non_overlapping_coverage() -> None:
    """A regular raster produces finite, valid bands covering its domain."""

    data = xr.DataArray(
        [[0.0, 1.0, 2.0], [1.0, 2.0, 3.0], [2.0, 3.0, 4.0]],
        dims=("y", "x"),
        coords={"x": [0.0, 1.0, 2.0], "y": [2.0, 1.0, 0.0]},
    )

    result = isobands.from_raster(data, levels=[1.5, 3.0], crs="EPSG:4326")

    assert list(result.columns) == ["min_value", "max_value", "geometry"]
    assert result.crs.to_epsg() == 4326
    assert result[["min_value", "max_value"]].values.tolist() == [
        [0.0, 1.5],
        [1.5, 3.0],
        [3.0, 4.0],
    ]
    assert all(geometry.is_valid for geometry in result.geometry)
    assert set(result.geometry.geom_type) <= {"Polygon", "MultiPolygon"}
    assert np.allclose(result.total_bounds, [-0.5, -0.5, 2.5, 2.5])
    for left, right in combinations(result.geometry, 2):
        assert left.intersection(right).area == 0.0

    covered = unary_union(result.geometry)
    assert covered.symmetric_difference(box(-0.5, -0.5, 2.5, 2.5)).area < 1e-9
    for x_coordinate in range(3):
        for y_coordinate in range(3):
            assert covered.covers(Point(x_coordinate, y_coordinate))


def test_from_raster_does_not_create_files(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    """The GDAL bridge uses only in-memory datasets."""

    data = xr.DataArray(
        [[0.0, 1.0], [2.0, 3.0]],
        dims=("y", "x"),
        coords={"x": [0.0, 1.0], "y": [1.0, 0.0]},
    )
    monkeypatch.chdir(tmp_path)

    isobands.from_raster(data, levels=[1.0], crs="EPSG:4326")

    assert list(tmp_path.iterdir()) == []
