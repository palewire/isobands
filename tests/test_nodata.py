"""Nodata handling tests."""

from __future__ import annotations

import warnings

import numpy as np
import pytest
import xarray as xr
from shapely.geometry import Point, box
from shapely.ops import unary_union

from isobands import isobands
from isobands._gdal import (
    _condition_contour_input,
    _iter_component_windows,
    _shift_geotransform,
)
from isobands._validation import prepare_raster


def _assert_valid_domain_coverage(result, values: np.ndarray) -> None:  # type: ignore[no-untyped-def]
    """Assert that valid sample centers are covered and NaN centers are not."""

    combined = unary_union(result.geometry)
    height, _ = values.shape
    assert all(geometry.is_valid for geometry in result.geometry)
    assert combined.is_valid
    for row, column in np.ndindex(values.shape):
        point = Point(float(column), float(height - row - 1))
        assert combined.covers(point) is bool(np.isfinite(values[row, column]))


def test_nodata_cell_remains_an_uncovered_hole() -> None:
    """A finite nodata value is excluded from all generated polygons."""

    values = np.array(
        [
            [0.0, 0.0, 0.0, 0.0, 0.0],
            [0.0, 1.0, 1.0, 1.0, 0.0],
            [0.0, 1.0, -999.0, 1.0, 0.0],
            [0.0, 1.0, 1.0, 1.0, 0.0],
            [0.0, 0.0, 0.0, 0.0, 0.0],
        ]
    )
    data = xr.DataArray(
        values,
        dims=("y", "x"),
        coords={"x": range(5), "y": range(4, -1, -1)},
    )

    result = isobands(data, levels=[0.5], crs="EPSG:4326", nodata=-999.0)
    covered = unary_union(result.geometry)

    assert not covered.covers(Point(2.0, 2.0))
    for y_coordinate in range(5):
        for x_coordinate in range(5):
            if (x_coordinate, y_coordinate) != (2, 2):
                assert covered.covers(Point(x_coordinate, y_coordinate))


def test_nan_cells_are_normalized_to_gdal_nodata() -> None:
    """Nonfinite floating cells use the validation layer's finite sentinel."""

    data = xr.DataArray(
        [[0.0, 1.0, 2.0], [1.0, np.nan, 3.0], [2.0, 3.0, 4.0]],
        dims=("y", "x"),
        coords={"x": [0.0, 1.0, 2.0], "y": [2.0, 1.0, 0.0]},
    )

    result = isobands(data, levels=[2.0], crs="EPSG:4326")

    assert not unary_union(result.geometry).covers(Point(1.0, 1.0))


def test_seeded_nan_raster_returns_valid_unionable_geometries() -> None:
    """Conditioning avoids GDAL rings with holes outside their shells."""

    values = np.random.default_rng(85).random((3, 3))
    values[1, 1] = np.nan
    data = xr.DataArray(
        values,
        dims=("y", "x"),
        coords={"x": range(3), "y": range(2, -1, -1)},
    )

    result = isobands(data, levels=[0.25, 0.5, 0.75], crs="EPSG:4326")
    combined = unary_union(result.geometry)

    assert all(geometry.is_valid for geometry in result.geometry)
    assert combined.is_valid
    assert not combined.covers(Point(1.0, 1.0))


def test_zero_nodata_with_float_extremes_stays_finite_and_valid() -> None:
    """A normalized nodata sentinel cannot collide with valid extreme samples."""

    limit = np.finfo(float).max
    data = xr.DataArray(
        [[-limit, -limit, limit], [-limit, 0.0, limit], [limit, limit, limit]],
        dims=("y", "x"),
        coords={"x": range(3), "y": range(2, -1, -1)},
    )
    thresholds = [-limit * 0.5, 0.0, limit * 0.5]

    result = isobands(
        data,
        levels=thresholds,
        crs="EPSG:4326",
        nodata=0.0,
    )
    combined = unary_union(result.geometry)

    assert result[["min_value", "max_value"]].values.tolist() == [
        [-limit, -limit * 0.5],
        [-limit * 0.5, 0.0],
        [0.0, limit * 0.5],
        [limit * 0.5, limit],
    ]
    assert all(geometry.is_valid for geometry in result.geometry)
    assert combined.is_valid
    assert not combined.covers(Point(1.0, 1.0))
    assert combined.covers(Point(0.0, 2.0))
    assert combined.covers(Point(2.0, 0.0))
    assert combined.intersection(box(-0.5, -0.5, 2.5, 2.5)).area > 0.0


def test_large_nodata_with_subnormal_values_is_warning_free() -> None:
    """Nodata is replaced before scaling so it cannot overflow."""

    unit = np.nextafter(0.0, 1.0)
    data = xr.DataArray(
        [[unit, np.nan], [2 * unit, 3 * unit]],
        dims=("y", "x"),
        coords={"x": [0.0, 1.0], "y": [1.0, 0.0]},
    )

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        result = isobands(
            data,
            levels=[2 * unit],
            crs="EPSG:4326",
            nodata=1e308,
        )

    _assert_valid_domain_coverage(result, data.values)


def test_antidiagonal_nodata_components_remain_valid_and_covered() -> None:
    """Disconnected valid components must not be emitted as an invalid hole."""

    values = np.array(
        [
            [-0.4767757315013672, -0.4030177131717534, np.nan],
            [-0.8161681157298062, np.nan, 0.45712105362358924],
            [np.nan, -0.8897067453338636, -0.4500612641879238],
        ]
    )
    data = xr.DataArray(
        values,
        dims=("y", "x"),
        coords={"x": range(3), "y": range(2, -1, -1)},
    )

    result = isobands(data, levels=[-0.5, 0.0, 0.5], crs="EPSG:4326")

    assert set(map(tuple, result[["min_value", "max_value"]].to_numpy())) == {
        (-0.8897067453338636, -0.5),
        (-0.5, 0.0),
        (0.0, 0.45712105362358924),
    }
    _assert_valid_domain_coverage(result, values)


@pytest.mark.parametrize(
    "nodata_indices",
    [
        [(1, 1), (1, 2), (2, 1)],
        [(0, 0), (1, 2), (3, 1)],
    ],
)
def test_adjacent_and_multiple_nodata_masks_preserve_valid_domain(
    nodata_indices,
) -> None:  # type: ignore[no-untyped-def]
    """Nodata clusters and separated nodata cells both retain valid topology."""

    values = np.linspace(-0.9, 0.9, 16).reshape(4, 4)
    for index in nodata_indices:
        values[index] = np.nan
    data = xr.DataArray(
        values,
        dims=("y", "x"),
        coords={"x": range(4), "y": range(3, -1, -1)},
    )

    result = isobands(data, levels=[-0.5, 0.0, 0.5], crs="EPSG:4326")

    _assert_valid_domain_coverage(result, values)


def test_constant_nodata_separated_components_all_receive_global_labels() -> None:
    """Every constant valid island is contoured with its shared exact labels."""

    values = np.array(
        [[5.0, np.nan, 5.0], [np.nan, np.nan, np.nan], [5.0, np.nan, 5.0]]
    )
    data = xr.DataArray(
        values,
        dims=("y", "x"),
        coords={"x": range(3), "y": range(2, -1, -1)},
    )

    result = isobands(data, levels=[1.0, 9.0], crs="EPSG:4326")

    assert result[["min_value", "max_value"]].values.tolist() == [[5.0, 5.0]] * 4
    _assert_valid_domain_coverage(result, values)


def test_isolated_components_are_streamed_as_cropped_windows() -> None:
    """Component discovery retains no full-raster mask for every valid island."""

    values = np.full((11, 11), np.nan)
    values[::2, ::2] = 5.0
    data = xr.DataArray(
        values,
        dims=("y", "x"),
        coords={"x": range(11), "y": range(10, -1, -1)},
    )
    raster = prepare_raster(data, crs="EPSG:4326", nodata=None)
    contour_input = _condition_contour_input(raster, ())
    windows = _iter_component_windows(contour_input, raster.geotransform)

    first_window, _ = next(windows)
    remaining_shapes = [window.values.shape for window, _ in windows]

    assert first_window.values.shape == (1, 1)
    assert all(shape == (1, 1) for shape in remaining_shapes)
    assert len(remaining_shapes) + 1 == 36


def test_crop_geotransform_includes_rotation_and_signed_axes() -> None:
    """Cropping preserves the affine location with any signed or rotated axes."""

    geotransform = (10.0, -2.0, 0.25, -5.0, 0.5, 3.0)

    assert _shift_geotransform(geotransform, row_offset=4, column_offset=7) == (
        -3.0,
        -2.0,
        0.25,
        10.5,
        0.5,
        3.0,
    )


def test_gdal_outside_interior_ring_is_promoted_without_losing_coverage() -> None:
    """A GDAL exterior mislabeled as a hole becomes a separate valid record."""

    values = np.array(
        [
            [1.51582781, 0.62905162, np.nan],
            [-0.56235173, np.nan, 0.59919126],
            [1.72860167, -0.66476523, 1.48848233],
        ]
    )
    data = xr.DataArray(
        values,
        dims=("y", "x"),
        coords={"x": range(3), "y": range(2, -1, -1)},
    )

    result = isobands(data, levels=[-0.5, 0.0, 0.5], crs="EPSG:4326")

    assert set(map(tuple, result[["min_value", "max_value"]].to_numpy())) == {
        (-0.66476523, -0.5),
        (-0.5, 0.0),
        (0.0, 0.5),
        (0.5, 1.72860167),
    }
    assert len(result.loc[result.min_value == 0.5]) == 3
    _assert_valid_domain_coverage(result, values)
    for row, column in np.ndindex(values.shape):
        value = values[row, column]
        if not np.isfinite(value):
            continue
        point = Point(float(column), float(2 - row))
        lower = (
            -0.66476523
            if value < -0.5
            else -0.5
            if value < 0.0
            else 0.0
            if value < 0.5
            else 0.5
        )
        assert any(
            geometry.covers(point)
            for geometry in result.loc[result.min_value == lower].geometry
        )


def test_legitimate_nodata_hole_remains_a_hole() -> None:
    """Ring-role normalization leaves valid GDAL nodata holes unchanged."""

    values = np.array(
        [
            [0.0, 0.0, 0.0, 0.0, 0.0],
            [0.0, 1.0, 1.0, 1.0, 0.0],
            [0.0, 1.0, np.nan, 1.0, 0.0],
            [0.0, 1.0, 1.0, 1.0, 0.0],
            [0.0, 0.0, 0.0, 0.0, 0.0],
        ]
    )
    data = xr.DataArray(
        values,
        dims=("y", "x"),
        coords={"x": range(5), "y": range(4, -1, -1)},
    )

    result = isobands(data, levels=[0.5], crs="EPSG:4326")
    interiors = [
        interior
        for geometry in result.geometry
        for polygon in (
            geometry.geoms if geometry.geom_type == "MultiPolygon" else (geometry,)
        )
        for interior in polygon.interiors
    ]

    assert len(result) == 2
    assert interiors
    assert not unary_union(result.geometry).covers(Point(2.0, 2.0))


def test_deferred_promotions_do_not_duplicate_other_gdal_bands() -> None:
    """Nested outside-ring candidates preserve one non-overlapping band per cell."""

    values = np.array(
        [
            [1.79141971, 0.29433006, 0.86231889, np.nan],
            [1.48729229, -1.25106541, -0.04692269, np.nan],
            [-1.45481232, 1.14688643, np.nan, -0.06892392],
            [-1.70274505, -0.45874325, 0.73768897, -0.70030305],
        ]
    )
    data = xr.DataArray(
        values,
        dims=("y", "x"),
        coords={"x": range(4), "y": range(3, -1, -1)},
    )

    result = isobands(data, levels=[-0.5, 0.0, 0.5], crs="EPSG:4326")

    assert set(map(tuple, result[["min_value", "max_value"]].to_numpy())) == {
        (-1.70274505, -0.5),
        (-0.5, 0.0),
        (0.0, 0.5),
        (0.5, 1.79141971),
    }
    for index, geometry in enumerate(result.geometry):
        for other_index, other_geometry in enumerate(result.geometry.iloc[index + 1 :]):
            if (
                result.min_value.iloc[index]
                != result.min_value.iloc[index + other_index + 1]
            ):
                assert geometry.intersection(other_geometry).area == 0.0

    for row, column in np.ndindex(values.shape):
        value = values[row, column]
        point = Point(float(column), float(3 - row))
        covered = [
            index
            for index, geometry in enumerate(result.geometry)
            if geometry.covers(point)
        ]
        if not np.isfinite(value):
            assert not covered
            continue
        assert len(covered) == 1
        lower = (
            -1.70274505
            if value < -0.5
            else -0.5
            if value < 0.0
            else 0.0
            if value < 0.5
            else 0.5
        )
        assert result.min_value.iloc[covered[0]] == lower


@pytest.mark.parametrize(
    ("index", "value", "expected"),
    [
        (0, -1.0, (-1.0, -0.5)),
        (1, -0.5, (-0.5, 0.0)),
        (2, 0.0, (0.0, 0.5)),
        (3, 0.5, (0.5, 1.0)),
        (4, 1.0, (0.5, 1.0)),
    ],
)
def test_isolated_constant_components_use_lower_inclusive_global_bands(
    index,
    value,
    expected,
) -> None:  # type: ignore[no-untyped-def]
    """Minima, interiors, exact thresholds, and maxima retain ascending labels."""

    values = np.full((5, 5), np.nan)
    values[np.arange(5), np.arange(5)] = [-1.0, -0.5, 0.0, 0.5, 1.0]
    data = xr.DataArray(
        values,
        dims=("y", "x"),
        coords={"x": range(5), "y": range(4, -1, -1)},
    )

    result = isobands(data, levels=[-0.5, 0.0, 0.5], crs="EPSG:4326")
    point = Point(float(index), float(4 - index))
    covered = [
        (row.min_value, row.max_value)
        for _, row in result.iterrows()
        if row.geometry.covers(point)
    ]

    assert covered == [expected]
    for geometry_index, geometry in enumerate(result.geometry):
        for other_geometry in result.geometry.iloc[geometry_index + 1 :]:
            assert geometry.intersection(other_geometry).area == 0.0
