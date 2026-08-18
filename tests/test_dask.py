"""Tests for eager materialization of Dask-backed rasters."""

import numpy as np
import pytest
import xarray as xr

from isobands._validation import prepare_raster


def test_dask_data_is_materialized_eagerly() -> None:
    dask = pytest.importorskip("dask.array")
    data = xr.DataArray(
        dask.from_array(np.arange(6, dtype=float).reshape(2, 3), chunks=(1, 2)),
        dims=("y", "x"),
        coords={"x": [0.0, 1.0, 2.0], "y": [1.0, 0.0]},
    )
    result = prepare_raster(data, crs="EPSG:4326", nodata=None)
    assert isinstance(result.values, np.ndarray)
    assert result.values.shape == (2, 3)
