"""Integer precision boundaries before GDAL Float64 conversion."""

from __future__ import annotations

import warnings

import numpy as np
import pytest
import xarray as xr

from isobands import from_raster
from isobands._validation import prepare_raster

EXACT_INTEGER_LIMIT = 2**53


def _data(values: np.ndarray, **kwargs: object) -> xr.DataArray:
    """Return a regular integer raster with optional xarray metadata."""

    return xr.DataArray(
        values,
        dims=("y", "x"),
        coords={"x": [0.0, 1.0], "y": [1.0, 0.0]},
        **kwargs,
    )


@pytest.mark.parametrize(
    "values",
    [
        np.array(
            [[-EXACT_INTEGER_LIMIT, -EXACT_INTEGER_LIMIT + 1]] * 2,
            dtype=np.int64,
        ),
        np.array(
            [[EXACT_INTEGER_LIMIT - 1, EXACT_INTEGER_LIMIT]] * 2,
            dtype=np.int64,
        ),
        np.array(
            [[EXACT_INTEGER_LIMIT - 1, EXACT_INTEGER_LIMIT]] * 2,
            dtype=np.uint64,
        ),
    ],
)
def test_exact_float64_integer_boundaries_are_accepted_without_warnings(
    values: np.ndarray,
) -> None:
    """Signed and unsigned integers through +/- 2**53 remain exact."""

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        raster = prepare_raster(_data(values), crs="EPSG:4326", nodata=None)

    assert raster.min_value == float(np.min(values))
    assert raster.max_value == float(np.max(values))


@pytest.mark.parametrize(
    "values",
    [
        np.array([[EXACT_INTEGER_LIMIT + 1, 0], [1, 2]], dtype=np.int64),
        np.array(
            [[-(EXACT_INTEGER_LIMIT + 1), 0], [1, 2]],
            dtype=np.int64,
        ),
        np.array([[EXACT_INTEGER_LIMIT + 1, 0], [1, 2]], dtype=np.uint64),
    ],
)
def test_adjacent_unrepresentable_integers_are_rejected(values: np.ndarray) -> None:
    """The first nonconsecutive Float64 integer fails before GDAL rounding."""

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        with pytest.raises(ValueError, match="exceed GDAL Float64 exact precision"):
            from_raster(_data(values), interval=1.0, crs="EPSG:4326")


@pytest.mark.parametrize("metadata", [False, True])
def test_out_of_range_integer_nodata_does_not_reject_safe_samples(
    metadata: bool,
) -> None:
    """Only valid integers participate in the Float64 exactness guard."""

    sentinel = EXACT_INTEGER_LIMIT + 1
    values = np.array([[EXACT_INTEGER_LIMIT, sentinel], [0, 1]], dtype=np.int64)
    data = _data(values, attrs={"missing_value": sentinel} if metadata else None)

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        raster = prepare_raster(
            data,
            crs="EPSG:4326",
            nodata=None if metadata else sentinel,
        )

    assert raster.min_value == 0.0
    assert raster.max_value == float(EXACT_INTEGER_LIMIT)
