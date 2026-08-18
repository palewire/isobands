"""Public isoband generation API."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from itertools import pairwise
from math import ceil, floor, isfinite
from typing import Any, TypeGuard

import geopandas as gpd
import numpy as np
import xarray as xr

from isobands._gdal import generate_fixed_level_polygons, generate_polygons
from isobands._validation import prepare_raster

_MAX_INTERVAL_THRESHOLDS = 100_000

LevelValues = Sequence[float] | np.ndarray
LevelTransform = Callable[[np.ndarray], LevelValues]


def isobands(
    data: xr.DataArray,
    *,
    levels: LevelValues | LevelTransform | None = None,
    interval: float | None = None,
    crs: Any | None = None,  # noqa: ANN401
    nodata: float | None = None,
) -> gpd.GeoDataFrame:
    """Create finite, filled contour polygons from a two-dimensional raster.

    Exactly one of ``levels`` or ``interval`` is required. Explicit levels
    are interior thresholds; a callable receives a one-dimensional array of
    valid raster values and returns those thresholds. The returned outer bands
    begin and end at the valid raster extrema. Interval thresholds are integral
    multiples of the supplied interval. A constant raster returns one covering
    band whose ``min_value`` and ``max_value`` are necessarily equal.
    Interval requests are limited to 100,000 interior
    thresholds; use a larger interval for wider value ranges.
    Integer samples must be within Float64's exact consecutive-integer range
    because GDAL contours using Float64 values.
    """

    _validate_band_definition(levels, interval)
    raster = prepare_raster(data, crs=crs, nodata=nodata)
    if _is_explicit_levels(levels):
        thresholds = _explicit_thresholds(levels, raster.min_value, raster.max_value)
    elif _is_level_transform(levels):
        thresholds = _explicit_thresholds(
            levels(raster.valid_values),
            raster.min_value,
            raster.max_value,
        )
    else:
        thresholds = _interval_thresholds(
            interval,
            raster.min_value,
            raster.max_value,
        )
    records = generate_polygons(raster, thresholds=thresholds)
    return gpd.GeoDataFrame(
        records,
        columns=["min_value", "max_value", "geometry"],
        geometry="geometry",
        crs=raster.crs,
    )


def gdal_fixed_level_polygons(
    data: xr.DataArray,
    *,
    levels: Sequence[float],
    crs: Any | None = None,  # noqa: ANN401
    nodata: float | None = None,
) -> gpd.GeoDataFrame:
    """Generate raw GDAL ``gdal_contour -p -fl`` compatible polygons.

    This low-level API applies ``gdal_contour -fl``'s six-decimal fixed-level
    serialization, then returns GDAL's emitted ``ID``, ``floor``, ``ceil``, and
    ``geometry`` fields in feature order. It does not clip endpoint levels to
    raster extrema, add outer bands, dissolve components, repair topology, or
    canonicalize geometry. Use :func:`isobands` for its stable finite-band
    convenience semantics.

    ``levels`` must be a nonempty finite sequence. Their order, including
    repeated levels, is preserved and validated by GDAL's fixed-level contour
    implementation.
    """

    fixed_levels = _fixed_levels(levels)
    raster = prepare_raster(data, crs=crs, nodata=nodata)
    records = generate_fixed_level_polygons(raster, levels=fixed_levels)
    return gpd.GeoDataFrame(
        records,
        columns=["ID", "floor", "ceil", "geometry"],
        geometry="geometry",
        crs=raster.crs,
    )


def _validate_band_definition(
    levels: LevelValues | LevelTransform | None,
    interval: float | None,
) -> None:
    """Validate the mutually exclusive level and interval parameters."""

    if (levels is None) == (interval is None):
        raise ValueError("Specify exactly one of levels or interval.")
    if interval is not None:
        if isinstance(interval, (bool, np.bool_)):
            raise ValueError(
                "interval must be a positive finite number, not a boolean."
            )
        try:
            value = float(interval)
        except (TypeError, ValueError) as error:
            raise ValueError("interval must be a positive finite number.") from error
        if not isfinite(value) or value <= 0:
            raise ValueError("interval must be a positive finite number.")


def _is_level_transform(
    levels: LevelValues | LevelTransform | None,
) -> TypeGuard[LevelTransform]:
    """Return whether levels is a callback rather than explicit thresholds."""

    return callable(levels)


def _is_explicit_levels(
    levels: LevelValues | LevelTransform | None,
) -> TypeGuard[LevelValues]:
    """Return whether levels contains explicit thresholds."""

    return levels is not None and (isinstance(levels, Sequence) or not callable(levels))


def _explicit_thresholds(
    levels: LevelValues,
    minimum: float,
    maximum: float,
) -> tuple[float, ...]:
    """Return finite, strictly increasing thresholds inside raster extrema."""

    try:
        raw_values = np.asarray(levels, dtype=object)
    except (TypeError, ValueError) as error:
        raise ValueError(
            "levels must be a one-dimensional numeric sequence."
        ) from error
    if raw_values.ndim != 1 or raw_values.size == 0:
        raise ValueError("levels must be a nonempty one-dimensional sequence.")
    if any(isinstance(value, (bool, np.bool_)) for value in raw_values):
        raise ValueError("levels must not contain boolean values.")
    try:
        values = raw_values.astype(np.float64)
    except (TypeError, ValueError) as error:
        raise ValueError(
            "levels must be a one-dimensional numeric sequence."
        ) from error
    if not np.all(np.isfinite(values)):
        raise ValueError("levels must contain only finite values.")
    if not np.all(np.diff(values) > 0):
        raise ValueError("levels must be strictly increasing.")
    return tuple(float(value) for value in values if minimum < value < maximum)


def _fixed_levels(levels: Sequence[float]) -> tuple[float, ...]:
    """Validate finite fixed levels without changing their native semantics."""

    try:
        raw_values = np.asarray(levels, dtype=object)
    except (TypeError, ValueError) as error:
        raise ValueError(
            "levels must be a one-dimensional numeric sequence."
        ) from error
    if raw_values.ndim != 1 or raw_values.size == 0:
        raise ValueError("levels must be a nonempty one-dimensional sequence.")
    if any(isinstance(value, (bool, np.bool_)) for value in raw_values):
        raise ValueError("levels must not contain boolean values.")
    try:
        values = raw_values.astype(np.float64)
    except (TypeError, ValueError) as error:
        raise ValueError(
            "levels must be a one-dimensional numeric sequence."
        ) from error
    if not np.all(np.isfinite(values)):
        raise ValueError("levels must contain only finite values.")
    return tuple(float(value) for value in values)


def _interval_thresholds(
    interval: float | None,
    minimum: float,
    maximum: float,
) -> tuple[float, ...]:
    """Return the open-interval integral multiples of an interval."""

    assert interval is not None
    step = float(interval)
    try:
        first_multiple = floor(minimum / step) + 1
        last_multiple = ceil(maximum / step) - 1
    except (OverflowError, ZeroDivisionError) as error:
        raise ValueError("interval is too small for the raster value range.") from error
    if first_multiple > last_multiple:
        return ()
    _interval_threshold_count(first_multiple, last_multiple)
    thresholds = tuple(
        float(multiplier * step)
        for multiplier in range(first_multiple, last_multiple + 1)
        if minimum < multiplier * step < maximum
    )
    if not thresholds:
        return ()
    if not all(left < right for left, right in pairwise(thresholds)):
        raise ValueError("interval cannot produce distinct finite thresholds.")
    return thresholds


def _interval_threshold_count(first_multiple: int, last_multiple: int) -> int:
    """Validate and return the number of interior interval multiples."""

    count = last_multiple - first_multiple + 1
    if count > _MAX_INTERVAL_THRESHOLDS:
        raise ValueError(
            f"interval would produce {count} interior thresholds; "
            f"choose a larger interval (maximum {_MAX_INTERVAL_THRESHOLDS})."
        )
    return count
