"""Explicit isoband-level tests."""

from __future__ import annotations

import numpy as np
import pytest
import xarray as xr
from shapely.geometry import Point

from isobands import isobands


def _raster() -> xr.DataArray:
    return xr.DataArray(
        [[4.0, 15.0], [25.0, 36.0]],
        dims=("y", "x"),
        coords={"x": [0.0, 1.0], "y": [1.0, 0.0]},
    )


def test_explicit_levels_are_clipped_to_data_extrema() -> None:
    """Levels outside the raster range do not create empty outer bands."""

    result = isobands(
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

    result = isobands(_raster(), levels=[-100.0, -10.0, 100.0], crs="EPSG:4326")

    assert result[["min_value", "max_value"]].values.tolist() == [[4.0, 36.0]]
    assert result.geometry.iloc[0].is_valid


def test_value_equal_to_threshold_is_assigned_to_the_upper_band() -> None:
    """Threshold labels follow lower-inclusive, upper-exclusive semantics."""

    data = xr.DataArray(
        [[0.0, 1.0], [2.0, 3.0]],
        dims=("y", "x"),
        coords={"x": [0.0, 1.0], "y": [1.0, 0.0]},
    )

    result = isobands(data, levels=[2.0], crs="EPSG:4326")

    assert result.loc[result.min_value == 2.0].geometry.iloc[0].covers(Point(0.0, 0.0))
    assert (
        not result.loc[result.max_value == 2.0].geometry.iloc[0].covers(Point(0.0, 0.0))
    )


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
        isobands(_raster(), levels=levels, crs="EPSG:4326")


def test_exactly_one_band_definition_is_required() -> None:
    """A caller cannot omit or combine level definitions."""

    with pytest.raises(ValueError, match="exactly one"):
        isobands(_raster(), crs="EPSG:4326")
    with pytest.raises(ValueError, match="exactly one"):
        isobands(_raster(), levels=[10.0], interval=5.0, crs="EPSG:4326")


def test_levels_reject_nonzero_interval_offset() -> None:
    """Offsets only apply to interval-derived thresholds."""

    with pytest.raises(ValueError, match="offset can only be used with interval"):
        isobands(_raster(), levels=[10.0], offset=2.5, crs="EPSG:4326")
