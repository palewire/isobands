"""Tests for CRS and nodata resolution."""

import warnings

import numpy as np
import pytest
import xarray as xr
from numpy.testing import assert_allclose

from isobands._validation import prepare_raster


def _data(**kwargs: object) -> xr.DataArray:
    return xr.DataArray(
        np.array([[1.0, 2.0], [3.0, 4.0]]),
        dims=("y", "x"),
        coords={"x": [0.0, 1.0], "y": [1.0, 0.0]},
        **kwargs,
    )


def test_explicit_crs_wins_over_metadata() -> None:
    data = _data(attrs={"crs": "EPSG:4326"})
    result = prepare_raster(data, crs="EPSG:3857", nodata=None)
    assert result.crs == "EPSG:3857"


def test_crs_metadata_is_used_but_coordinate_names_do_not_infer_wgs84() -> None:
    data = _data(attrs={"crs_wkt": "EPSG:3857"})
    assert prepare_raster(data, crs=None, nodata=None).crs == "EPSG:3857"
    unnamed = xr.DataArray(
        np.ones((2, 2)),
        dims=("latitude", "longitude"),
        coords={"latitude": [1.0, 0.0], "longitude": [0.0, 1.0]},
    )
    with pytest.raises(ValueError, match="Pass crs"):
        prepare_raster(unnamed, crs=None, nodata=None)


def test_cf_grid_mapping_metadata_is_used() -> None:
    grid_mapping = xr.DataArray(
        0,
        name="mapping",
        attrs={
            "grid_mapping_name": "latitude_longitude",
            "earth_radius": 6371000.0,
        },
    )
    data = xr.DataArray(
        np.ones((2, 2)),
        dims=("y", "x"),
        coords={
            "x": [0.0, 1.0],
            "y": [1.0, 0.0],
            "mapping": grid_mapping,
        },
        attrs={"grid_mapping": "mapping"},
    )
    result = prepare_raster(data, crs=None, nodata=None)
    assert result.crs.is_geographic


def test_explicit_and_metadata_nodata_precedence_and_nan_sentinel() -> None:
    data = _data(
        attrs={"missing_value": -999.0},
    )
    data.values[0, 0] = np.nan
    metadata = prepare_raster(data, crs="EPSG:4326", nodata=None)
    assert metadata.nodata == -999.0
    assert np.isfinite(metadata.values).all()
    explicit = prepare_raster(data, crs="EPSG:4326", nodata=-1)
    assert explicit.nodata == -1.0


def test_all_nodata_and_nonfinite_explicit_nodata_are_rejected() -> None:
    data = _data()
    data.values[:] = np.nan
    with pytest.raises(ValueError, match="no valid"):
        prepare_raster(data, crs="EPSG:4326", nodata=None)
    with pytest.raises(ValueError, match="finite"):
        prepare_raster(_data(), crs="EPSG:4326", nodata=np.nan)


def test_integer_values_are_widened_for_unrepresentable_nodata() -> None:
    data = xr.DataArray(
        np.array([[1, 255], [3, 4]], dtype=np.uint8),
        dims=("y", "x"),
        coords={"x": [0.0, 1.0], "y": [1.0, 0.0]},
        attrs={"missing_value": -1},
    )
    result = prepare_raster(data, crs="EPSG:4326", nodata=None)
    assert result.values.dtype.kind == "i"
    assert result.nodata == -1.0
    np.testing.assert_array_equal(result.values, data.values)
    assert result.min_value == 1.0
    assert result.max_value == 255.0
    explicit_data = data.copy(deep=True)
    explicit_data.attrs = {}
    explicit = prepare_raster(explicit_data, crs="EPSG:4326", nodata=-1)
    assert explicit.values.dtype.kind == "i"
    np.testing.assert_array_equal(explicit.values, data.values)
    assert explicit.min_value == 1.0
    assert explicit.max_value == 255.0


@pytest.mark.parametrize("nodata", [1e40, -1e40])
def test_float32_out_of_range_nodata_is_warning_free(nodata: float) -> None:
    data = _data().astype(np.float32)
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        result = prepare_raster(data, crs="EPSG:4326", nodata=nodata)
    assert result.values.dtype == np.float64
    assert result.nodata == nodata
    assert result.min_value == 1.0
    assert result.max_value == 4.0


def test_float32_representable_nodata_retains_dtype() -> None:
    data = _data().astype(np.float32)
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        result = prepare_raster(data, crs="EPSG:4326", nodata=-999.0)
    assert result.values.dtype == np.float32
    assert result.nodata == -999.0
    assert_allclose(result.values, data.values)


def test_float32_rounded_nodata_masks_stored_value() -> None:
    data = _data().astype(np.float32)
    data.values[0, 0] = np.float32(0.1)
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        result = prepare_raster(data, crs="EPSG:4326", nodata=0.1)
    assert result.values.dtype == np.float32
    assert result.nodata == float(np.float32(0.1))
    assert result.min_value == 2.0
    assert result.max_value == 4.0
