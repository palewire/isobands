"""Interval-derived isoband tests."""

from __future__ import annotations

import math

import numpy as np
import pytest
import xarray as xr

from isobands import isobands
from isobands.core import (
    _MAX_INTERVAL_THRESHOLDS,
    _interval_threshold_count,
    _interval_thresholds,
)


def _raster() -> xr.DataArray:
    return xr.DataArray(
        [[-7.0, -1.0], [3.0, 8.0]],
        dims=("y", "x"),
        coords={"x": [0.0, 1.0], "y": [1.0, 0.0]},
    )


def test_interval_uses_multiples_and_clips_outer_bands() -> None:
    """Interval thresholds are open-interval multiples of the step."""

    result = isobands(_raster(), interval=5.0, crs="EPSG:4326")

    assert result[["min_value", "max_value"]].values.tolist() == [
        [-7.0, -5.0],
        [-5.0, 0.0],
        [0.0, 5.0],
        [5.0, 8.0],
    ]
    assert result.min_value.tolist() == [-7.0, -5.0, 0.0, 5.0]


@pytest.mark.parametrize(
    ("offset", "expected"),
    [
        (2.5, [[-7.0, -2.5], [-2.5, 2.5], [2.5, 7.5], [7.5, 8.0]]),
        (-1.0, [[-7.0, -6.0], [-6.0, -1.0], [-1.0, 4.0], [4.0, 8.0]]),
        (7.5, [[-7.0, -2.5], [-2.5, 2.5], [2.5, 7.5], [7.5, 8.0]]),
    ],
)
def test_interval_offset_aligns_thresholds(
    offset: float, expected: list[list[float]]
) -> None:
    """Offsets align interval thresholds independently of their magnitude."""

    result = isobands(_raster(), interval=5.0, offset=offset, crs="EPSG:4326")

    assert result[["min_value", "max_value"]].values.tolist() == expected


def test_zero_interval_offset_preserves_default_output() -> None:
    """An explicit zero offset retains the legacy interval alignment."""

    default = isobands(_raster(), interval=5.0, crs="EPSG:4326")
    explicit = isobands(_raster(), interval=5.0, offset=0.0, crs="EPSG:4326")

    assert explicit[["min_value", "max_value"]].equals(
        default[["min_value", "max_value"]]
    )


def test_interval_offset_excludes_extrema_on_thresholds() -> None:
    """Extrema matching aligned thresholds remain finite outer-band labels."""

    data = xr.DataArray(
        [[2.5, 5.0], [7.5, 12.5]],
        dims=("y", "x"),
        coords={"x": [0.0, 1.0], "y": [1.0, 0.0]},
    )

    result = isobands(data, interval=5.0, offset=2.5, crs="EPSG:4326")

    assert result[["min_value", "max_value"]].values.tolist() == [
        [2.5, 7.5],
        [7.5, 12.5],
    ]


@pytest.mark.parametrize(
    "interval",
    [0.0, -1.0, math.inf, math.nan, "five", False, np.bool_(True)],
)
def test_interval_must_be_positive_and_finite(interval) -> None:  # type: ignore[no-untyped-def]
    """Invalid interval values receive a focused validation error."""

    with pytest.raises(ValueError, match="positive finite"):
        isobands(_raster(), interval=interval, crs="EPSG:4326")


@pytest.mark.parametrize("offset", [math.inf, math.nan, "zero", False, np.bool_(True)])
def test_interval_offset_must_be_finite_number(offset) -> None:  # type: ignore[no-untyped-def]
    """Invalid offsets receive a focused validation error."""

    with pytest.raises(ValueError, match="offset must be a finite"):
        isobands(_raster(), interval=5.0, offset=offset, crs="EPSG:4326")


def test_interval_rejects_impractical_threshold_count() -> None:
    """A huge interval request fails before allocating its thresholds."""

    with pytest.raises(
        ValueError, match=r"\d+ interior thresholds; choose a larger interval"
    ):
        _interval_thresholds(1e-9, -1.0, 1.0)


def test_interval_rejects_unrepresentably_small_step() -> None:
    """A step too small for the raster range receives an actionable error."""

    with pytest.raises(ValueError, match="too small"):
        _interval_thresholds(1e-320, -1.0, 1.0)


def test_interval_threshold_count_allows_exact_limit_without_allocating() -> None:
    """The configured maximum is accepted by the count guard."""

    assert _interval_threshold_count(0, _MAX_INTERVAL_THRESHOLDS - 1) == (
        _MAX_INTERVAL_THRESHOLDS
    )
    with pytest.raises(ValueError, match=f"maximum {_MAX_INTERVAL_THRESHOLDS}"):
        _interval_threshold_count(0, _MAX_INTERVAL_THRESHOLDS)
