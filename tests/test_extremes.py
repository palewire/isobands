"""Extrema and topology tests."""

from __future__ import annotations

import numpy as np
import pytest
import xarray as xr
from shapely.geometry import Point, box
from shapely.ops import unary_union

from isobands import isobands


def test_final_band_covers_the_raster_maximum() -> None:
    """The upper outer band includes, rather than excludes, the maximum."""

    data = xr.DataArray(
        [[0.0, 1.0, 2.0], [1.0, 2.0, 3.0], [2.0, 3.0, 4.0]],
        dims=("y", "x"),
        coords={"x": [0.0, 1.0, 2.0], "y": [2.0, 1.0, 0.0]},
    )

    result = isobands(data, levels=[1.5, 3.0], crs="EPSG:4326")

    final_band = result.iloc[-1]
    assert final_band.min_value == 3.0
    assert final_band.max_value == 4.0
    assert final_band.geometry.covers(Point(2.0, 0.0))


def test_constant_raster_produces_one_full_coverage_band() -> None:
    """A constant field remains one valid band with no artificial sliver."""

    data = xr.DataArray(
        [[5.0, 5.0], [5.0, 5.0]],
        dims=("y", "x"),
        coords={"x": [0.0, 1.0], "y": [1.0, 0.0]},
    )

    result = isobands(data, levels=[1.0, 9.0], crs="EPSG:4326")

    assert result[["min_value", "max_value"]].values.tolist() == [[5.0, 5.0]]
    assert result.geometry.iloc[0].is_valid
    assert (
        result.geometry.iloc[0].symmetric_difference(box(-0.5, -0.5, 1.5, 1.5)).area
        < 1e-9
    )


def test_constant_float_extreme_produces_one_full_coverage_band() -> None:
    """A constant value near float64's maximum remains numerically stable."""

    value = 1e308
    data = xr.DataArray(
        [[value, value], [value, value]],
        dims=("y", "x"),
        coords={"x": [0.0, 1.0], "y": [1.0, 0.0]},
    )

    result = isobands(data, levels=[1e307], crs="EPSG:4326")

    assert result[["min_value", "max_value"]].values.tolist() == [[value, value]]
    assert result.geometry.iloc[0].is_valid
    assert (
        result.geometry.iloc[0].symmetric_difference(box(-0.5, -0.5, 1.5, 1.5)).area
        < 1e-9
    )


def test_nonconstant_float_maximum_preserves_exact_labels_and_coverage() -> None:
    """Finite values at float64's maximum contour in a stable scaled range."""

    limit = np.finfo(float).max
    data = xr.DataArray(
        [[limit, limit * 0.5], [limit * 0.25, -limit * 0.5]],
        dims=("y", "x"),
        coords={"x": [0.0, 1.0], "y": [1.0, 0.0]},
    )
    thresholds = [-limit * 0.25, limit * 0.75]

    result = isobands(data, levels=thresholds, crs="EPSG:4326")
    combined = unary_union(result.geometry)

    assert result[["min_value", "max_value"]].values.tolist() == [
        [-limit * 0.5, -limit * 0.25],
        [-limit * 0.25, limit * 0.75],
        [limit * 0.75, limit],
    ]
    assert all(geometry.is_valid for geometry in result.geometry)
    assert combined.is_valid
    assert combined.symmetric_difference(box(-0.5, -0.5, 1.5, 1.5)).area < 1e-9


def test_subnormal_range_produces_valid_full_coverage() -> None:
    """Tiny finite values are scaled without collapsing their thresholds."""

    unit = np.nextafter(0.0, 1.0)
    data = xr.DataArray(
        [[unit, 2 * unit], [3 * unit, 4 * unit]],
        dims=("y", "x"),
        coords={"x": [0.0, 1.0], "y": [1.0, 0.0]},
    )

    result = isobands(data, levels=[2.5 * unit], crs="EPSG:4326")
    combined = unary_union(result.geometry)

    assert result[["min_value", "max_value"]].values.tolist() == [
        [unit, 2.5 * unit],
        [2.5 * unit, 4 * unit],
    ]
    assert all(geometry.is_valid for geometry in result.geometry)
    assert combined.is_valid
    assert combined.symmetric_difference(box(-0.5, -0.5, 1.5, 1.5)).area < 1e-9


@pytest.mark.filterwarnings("error")
def test_collapsed_scaled_thresholds_are_rejected_before_gdal() -> None:
    """Distinct bounds that collapse after scaling cannot silently lose bands."""

    limit = np.finfo(float).max
    data = xr.DataArray(
        [[0.0, 1e-320], [2e-320, limit]],
        dims=("y", "x"),
        coords={"x": [0.0, 1.0], "y": [1.0, 0.0]},
    )

    with pytest.raises(ValueError, match=r"dynamic range too large.*rescale data"):
        isobands(data, levels=[1e-320, 2e-320], crs="EPSG:4326")


def test_representable_large_range_keeps_distinct_scaled_thresholds() -> None:
    """Large finite ranges remain supported when their thresholds survive scaling."""

    limit = np.finfo(float).max
    data = xr.DataArray(
        [[0.0, limit * 0.25], [limit * 0.5, limit]],
        dims=("y", "x"),
        coords={"x": [0.0, 1.0], "y": [1.0, 0.0]},
    )

    result = isobands(
        data,
        levels=[limit * 0.25, limit * 0.5],
        crs="EPSG:4326",
    )

    assert result[["min_value", "max_value"]].values.tolist() == [
        [0.0, limit * 0.25],
        [limit * 0.25, limit * 0.5],
        [limit * 0.5, limit],
    ]
    assert all(geometry.is_valid for geometry in result.geometry)


def test_disconnected_cells_remain_multipart() -> None:
    """Separated high-value regions are retained as separate polygons."""

    values = np.zeros((5, 5))
    values[1, 1] = 10.0
    values[3, 3] = 10.0
    data = xr.DataArray(
        values,
        dims=("y", "x"),
        coords={"x": range(5), "y": range(4, -1, -1)},
    )

    result = isobands(data, levels=[5.0], crs="EPSG:4326")
    high_band = result.loc[result.min_value == 5.0].geometry.iloc[0]

    assert high_band.geom_type == "MultiPolygon"
    assert len(high_band.geoms) == 2
    assert unary_union(result.geometry).covers(Point(1.0, 3.0))
    assert unary_union(result.geometry).covers(Point(3.0, 1.0))
