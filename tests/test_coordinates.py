"""Tests for raster coordinate discovery and geotransform construction."""

import warnings

import numpy as np
import pytest
import xarray as xr

from isobands._coordinates import (
    geotransform_from_coordinates,
    identify_spatial_dimensions,
    validate_coordinate,
)
from isobands._validation import prepare_raster


def _raster(
    values: np.ndarray,
    *,
    x: np.ndarray | list[float] = (0, 1, 2),
    y: np.ndarray | list[float] = (2, 1),
    dims: tuple[str, ...] = ("y", "x"),
    coords: dict | None = None,
) -> xr.DataArray:
    if coords is None:
        coords = {"x": list(x), "y": list(y)}
    return xr.DataArray(values, dims=dims, coords=coords)


def test_cf_axis_metadata_precedes_coordinate_names() -> None:
    data = xr.DataArray(
        np.ones((2, 3)),
        dims=("row", "column"),
        coords={
            "column": ("column", [0, 1, 2], {"axis": "X"}),
            "row": ("row", [2, 1], {"standard_name": "latitude"}),
        },
    )
    assert identify_spatial_dimensions(data) == ("column", "row")


def test_descending_axes_and_pixel_center_origin() -> None:
    result = prepare_raster(
        _raster(np.arange(6).reshape(2, 3)), crs="EPSG:3857", nodata=None
    )
    assert result.geotransform == (-0.5, 1.0, 0.0, 2.5, 0.0, -1.0)


def test_dimension_order_is_transposed_to_y_then_x() -> None:
    data = _raster(
        np.array([[1, 2], [3, 4], [5, 6]]),
        x=[10, 20, 30],
        y=[5, 15],
        dims=("x", "y"),
    )
    result = prepare_raster(data, crs="EPSG:3857", nodata=None)
    np.testing.assert_array_equal(result.values, [[1, 3, 5], [2, 4, 6]])
    assert result.geotransform == (5.0, 10.0, 0.0, 0.0, 0.0, 10.0)


def test_geotransform_retains_descending_x_step() -> None:
    assert geotransform_from_coordinates(
        np.array([10.0, 8.0]),
        np.array([20.0, 22.0]),
    ) == (11.0, -2.0, 0.0, 19.0, 0.0, 2.0)


@pytest.mark.parametrize("axis", ["x", "y"])
def test_coordinate_difference_overflow_is_rejected_without_warnings(axis: str) -> None:
    maximum = np.finfo(np.float64).max
    coordinates = {"x": [0.0, 1.0], "y": [0.0, 1.0]}
    coordinates[axis] = [-maximum, maximum]
    data = _raster(np.ones((2, 2)), coords=coordinates)
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        with pytest.raises(ValueError, match=r"differences.*overflow"):
            prepare_raster(data, crs="EPSG:3857", nodata=None)


@pytest.mark.parametrize(
    ("axis", "centers"),
    [
        ("x", [-np.finfo(np.float64).max, -np.finfo(np.float64).max / 2]),
        ("x", [np.finfo(np.float64).max, np.finfo(np.float64).max / 2]),
        ("y", [-np.finfo(np.float64).max, -np.finfo(np.float64).max / 2]),
        ("y", [np.finfo(np.float64).max, np.finfo(np.float64).max / 2]),
    ],
)
def test_pixel_corner_origin_overflow_is_rejected_without_warnings(
    axis: str,
    centers: list[float],
) -> None:
    coordinates = {"x": [0.0, 1.0], "y": [0.0, 1.0]}
    coordinates[axis] = centers
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        with pytest.raises(
            ValueError,
            match=r"geotransform.*finite|origin.*overflow",
        ):
            geotransform_from_coordinates(
                np.asarray(coordinates["x"]),
                np.asarray(coordinates["y"]),
            )


def test_irregular_coordinate_is_rejected() -> None:
    coord = xr.DataArray([0.0, 1.0, 2.1], dims="x", name="x")
    with pytest.raises(ValueError, match="irregularly spaced"):
        validate_coordinate(coord, axis="x")


def test_curvilinear_coordinate_is_rejected() -> None:
    data = xr.DataArray(
        np.ones((2, 2)),
        dims=("y", "x"),
        coords={
            "x": (("y", "x"), [[0.0, 1.0], [0.0, 1.0]]),
            "y": [0.0, 1.0],
        },
    )
    with pytest.raises(ValueError, match="one-dimensional"):
        prepare_raster(data, crs="EPSG:3857", nodata=None)


def test_nonnumeric_and_nonsingleton_three_dimensional_data_are_rejected() -> None:
    nonnumeric = xr.DataArray(
        [["a", "b"], ["c", "d"]],
        dims=("y", "x"),
        coords={"x": [0, 1], "y": [0, 1]},
    )
    with pytest.raises(TypeError, match="numeric"):
        prepare_raster(nonnumeric, crs="EPSG:3857", nodata=None)
    three_dimensional = xr.DataArray(
        np.ones((2, 2, 2)),
        dims=("band", "y", "x"),
        coords={"band": [1, 2], "x": [0, 1], "y": [0, 1]},
    )
    with pytest.raises(ValueError, match="two nonsingleton"):
        prepare_raster(three_dimensional, crs="EPSG:3857", nodata=None)


def test_short_and_misaligned_coordinates_are_rejected() -> None:
    short = xr.DataArray([0.0], dims="x", name="x")
    with pytest.raises(ValueError, match="at least two"):
        validate_coordinate(short, axis="x")
    misaligned = xr.DataArray(
        np.ones((2, 2)),
        dims=("y", "x"),
        coords={
            "x": ("y", [0.0, 1.0]),
            "y": [0.0, 1.0],
        },
    )
    with pytest.raises(ValueError, match="same dimension"):
        prepare_raster(misaligned, crs="EPSG:3857", nodata=None)


def test_ambiguous_and_missing_coordinates_are_rejected() -> None:
    ambiguous = xr.DataArray(
        np.ones((2, 3)),
        dims=("y", "x"),
        coords={"x": [0, 1, 2], "lon": ("x", [0, 1, 2]), "y": [0, 1]},
    )
    with pytest.raises(ValueError, match="Ambiguous"):
        identify_spatial_dimensions(ambiguous)
    missing = xr.DataArray(np.ones((2, 3)), dims=("row", "column"))
    with pytest.raises(ValueError, match="identify"):
        identify_spatial_dimensions(missing)


def test_singleton_dimension_is_squeezed_without_mutating_input() -> None:
    data = xr.DataArray(
        np.arange(6).reshape(1, 2, 3),
        dims=("band", "y", "x"),
        coords={"band": [1], "x": [0, 1, 2], "y": [0, 1]},
    )
    result = prepare_raster(data, crs="EPSG:4326", nodata=None)
    assert result.values.shape == (2, 3)
    assert data.dims == ("band", "y", "x")
