"""Explicit isoband-level tests."""

from __future__ import annotations

import numpy as np
import pytest
import xarray as xr
from shapely.geometry import Point

from isobands import from_raster


def _raster() -> xr.DataArray:
    return xr.DataArray(
        [[4.0, 15.0], [25.0, 36.0]],
        dims=("y", "x"),
        coords={"x": [0.0, 1.0], "y": [1.0, 0.0]},
    )


def test_explicit_levels_are_clipped_to_data_extrema() -> None:
    """Levels outside the raster range do not create empty outer bands."""

    result = from_raster(
        _raster(),
        levels=[-100.0, 10.0, 20.0, 100.0],
        crs="EPSG:4326",
    )

    assert result[["min_value", "max_value"]].values.tolist() == [
        [4.0, 10.0],
        [10.0, 20.0],
        [20.0, 36.0],
    ]
    assert all(result.min_value < result.max_value)


def test_all_levels_outside_the_range_produce_one_finite_band() -> None:
    """No out-of-range threshold introduces an empty or infinite band."""

    result = from_raster(_raster(), levels=[-100.0, -10.0, 100.0], crs="EPSG:4326")

    assert result[["min_value", "max_value"]].values.tolist() == [[4.0, 36.0]]
    assert result.geometry.iloc[0].is_valid


def test_value_equal_to_threshold_is_assigned_to_the_upper_band() -> None:
    """Threshold labels follow lower-inclusive, upper-exclusive semantics."""

    data = xr.DataArray(
        [[0.0, 1.0], [2.0, 3.0]],
        dims=("y", "x"),
        coords={"x": [0.0, 1.0], "y": [1.0, 0.0]},
    )

    result = from_raster(data, levels=[2.0], crs="EPSG:4326")

    assert result.loc[result.min_value == 2.0].geometry.iloc[0].covers(Point(0.0, 0.0))
    assert (
        not result.loc[result.max_value == 2.0].geometry.iloc[0].covers(Point(0.0, 0.0))
    )


def test_numpy_array_levels_remain_supported() -> None:
    """NumPy arrays retain explicit-level behavior."""

    result = from_raster(_raster(), levels=np.array([10.0, 20.0]), crs="EPSG:4326")

    assert result[["min_value", "max_value"]].values.tolist() == [
        [4.0, 10.0],
        [10.0, 20.0],
        [20.0, 36.0],
    ]


def test_callable_sequence_levels_remain_explicit() -> None:
    """A callable sequence retains explicit-level behavior."""

    class CallableLevels(list[float]):
        def __call__(self, values: np.ndarray) -> np.ndarray:
            raise AssertionError("Explicit levels must not be called")

    result = from_raster(
        _raster(), levels=CallableLevels([10.0, 20.0]), crs="EPSG:4326"
    )

    assert result[["min_value", "max_value"]].values.tolist() == [
        [4.0, 10.0],
        [10.0, 20.0],
        [20.0, 36.0],
    ]


def test_callable_levels_receive_valid_flattened_values() -> None:
    """A level transform receives only finite, non-nodata values."""

    data = xr.DataArray(
        [[1.0, np.nan], [3.0, -999.0]],
        dims=("y", "x"),
        coords={"x": [0.0, 1.0], "y": [1.0, 0.0]},
    )
    received: list[np.ndarray] = []

    def middle(values: np.ndarray) -> np.ndarray:
        received.append(values)
        return np.array([2.0])

    result = from_raster(data, levels=middle, crs="EPSG:4326", nodata=-999.0)

    assert len(received) == 1
    np.testing.assert_array_equal(received[0], np.array([1.0, 3.0]))
    assert result[["min_value", "max_value"]].values.tolist() == [
        [1.0, 2.0],
        [2.0, 3.0],
    ]


def test_lambda_levels_are_supported() -> None:
    """A lambda can calculate interior thresholds from valid values."""

    result = from_raster(
        _raster(),
        levels=lambda values: [float(np.median(values))],
        crs="EPSG:4326",
    )

    assert result[["min_value", "max_value"]].values.tolist() == [
        [4.0, 20.0],
        [20.0, 36.0],
    ]


@pytest.mark.parametrize(
    ("levels", "message"),
    [
        ([], "nonempty"),
        ([1.0, 1.0], "strictly increasing"),
        ([2.0, 1.0], "strictly increasing"),
        ([1.0, np.nan], "finite"),
        ([1.0, np.inf], "finite"),
        ([False, 1.0], "boolean"),
    ],
)
def test_explicit_levels_are_validated(levels, message) -> None:  # type: ignore[no-untyped-def]
    """Explicit thresholds must be finite and strictly increasing."""

    with pytest.raises(ValueError, match=message):
        from_raster(_raster(), levels=levels, crs="EPSG:4326")


@pytest.mark.parametrize(
    ("transform", "message"),
    [
        (lambda values: [], "nonempty"),
        (lambda values: [2.0, 1.0], "strictly increasing"),
        (lambda values: [np.nan], "finite"),
    ],
)
def test_callable_levels_are_validated(transform, message) -> None:  # type: ignore[no-untyped-def]
    """Callable output follows explicit-level validation rules."""

    with pytest.raises(ValueError, match=message):
        from_raster(_raster(), levels=transform, crs="EPSG:4326")


def test_callable_level_exceptions_are_not_hidden() -> None:
    """Errors raised by a level transform reach the caller."""

    def fail(values: np.ndarray) -> np.ndarray:
        raise RuntimeError("classification failed")

    with pytest.raises(RuntimeError, match="classification failed"):
        from_raster(_raster(), levels=fail, crs="EPSG:4326")


def test_exactly_one_band_definition_is_required() -> None:
    """A caller cannot omit or combine level definitions."""

    with pytest.raises(ValueError, match="exactly one"):
        from_raster(_raster(), crs="EPSG:4326")
    with pytest.raises(ValueError, match="exactly one"):
        from_raster(_raster(), levels=[10.0], interval=5.0, crs="EPSG:4326")
    with pytest.raises(ValueError, match="exactly one"):
        from_raster(
            _raster(), levels=lambda values: [10.0], interval=5.0, crs="EPSG:4326"
        )


def test_levels_reject_nonzero_interval_offset() -> None:
    """Offsets only apply to interval-derived thresholds."""

    with pytest.raises(ValueError, match="offset can only be used with interval"):
        from_raster(_raster(), levels=[10.0], offset=2.5, crs="EPSG:4326")
