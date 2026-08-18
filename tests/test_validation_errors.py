"""Actionable validation errors for unsupported raster inputs."""

from __future__ import annotations

import numpy as np
import pytest
import xarray as xr
from shapely.geometry import Point

from isobands._coordinates import validate_coordinate
from isobands._gdal import _normalize_gdal_ring_roles
from isobands._validation import prepare_raster


def _data() -> xr.DataArray:
    """Return a minimal regular raster for validation tests."""

    return xr.DataArray(
        [[1.0, 2.0], [3.0, 4.0]],
        dims=("y", "x"),
        coords={"x": [0.0, 1.0], "y": [1.0, 0.0]},
    )


def test_invalid_and_conflicting_crs_metadata_are_actionable() -> None:
    """Invalid CRS hints report their source, while conflicting hints are rejected."""

    invalid = _data()
    invalid.attrs["crs"] = "not-a-crs"
    with pytest.raises(ValueError, match=r"Metadata errors:.*DataArray metadata crs"):
        prepare_raster(invalid, crs=None, nodata=None)

    conflicting = _data()
    conflicting.attrs["crs"] = "EPSG:4326"
    conflicting.encoding["crs"] = "EPSG:3857"
    with pytest.raises(ValueError, match="Ambiguous CRS metadata"):
        prepare_raster(conflicting, crs=None, nodata=None)


@pytest.mark.parametrize(
    ("nodata", "exception"),
    [
        ([1.0, 2.0], ValueError),
        (True, TypeError),
    ],
)
def test_invalid_nodata_values_are_rejected_before_gdal(
    nodata: object,
    exception: type[Exception],
) -> None:
    """A nodata value must be one finite scalar rather than a vector or boolean."""

    with pytest.raises(exception, match="scalar numeric"):
        prepare_raster(_data(), crs="EPSG:4326", nodata=nodata)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("values", "exception", "message"),
    [
        (["west", "east"], TypeError, "numeric"),
        ([0.0, np.nan], ValueError, "nonfinite"),
        ([0.0, 0.0], ValueError, "strictly monotonic"),
    ],
)
def test_coordinate_validation_errors_explain_the_bad_axis(
    values: list[object],
    exception: type[Exception],
    message: str,
) -> None:
    """Unsupported coordinate dtypes, NaNs, and duplicates identify the cause."""

    coordinate = xr.DataArray(values, dims="x", name="x")
    with pytest.raises(exception, match=message):
        validate_coordinate(coordinate, axis="x")


def test_nonpolygon_gdal_output_is_rejected_actionably() -> None:
    """The ring-role normalizer never accepts non-polygon GDAL output."""

    with pytest.raises(RuntimeError, match="non-polygon"):
        _normalize_gdal_ring_roles(Point(0.0, 0.0))
