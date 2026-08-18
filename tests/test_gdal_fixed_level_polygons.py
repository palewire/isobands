"""Raw fixed-level GDAL contour compatibility tests."""

from __future__ import annotations

from pathlib import Path
from shutil import which
from subprocess import run

import geopandas as gpd
import numpy as np
import pytest
import xarray as xr
from geopandas.testing import assert_geodataframe_equal
from shapely import from_wkb
from shapely.geometry import Point
from shapely.ops import unary_union

from isobands import gdal_fixed_level_polygons
from isobands._gdal import _import_gdal
from isobands._validation import RasterSpec, prepare_raster


@pytest.fixture
def fixed_level_raster() -> xr.DataArray:
    """Return a small raster with endpoints and values on fixed levels."""

    return xr.DataArray(
        [[0.0, 1.0, 2.0], [1.0, 2.0, 3.0], [2.0, 3.0, 4.0]],
        dims=("y", "x"),
        coords={"x": [0.0, 1.0, 2.0], "y": [2.0, 1.0, 0.0]},
    )


def _cli_fixed_level_baseline(
    data: xr.DataArray,
    *,
    levels: list[float],
    crs: str,
    nodata: float | None,
    tmp_path: Path,
) -> gpd.GeoDataFrame:
    """Run the native command against the same validated raster input."""

    executable = which("gdal_contour")
    assert executable is not None, (
        "gdal_contour must be available for compatibility tests"
    )
    raster = prepare_raster(data, crs=crs, nodata=nodata)
    input_path = tmp_path / "input.tif"
    output_path = tmp_path / "native.geojson"
    _write_raster(input_path, raster)
    command = [
        executable,
        "-p",
        "-fl",
        *(format(level, ".17g") for level in levels),
        "-amin",
        "floor",
        "-amax",
        "ceil",
        "-f",
        "GeoJSON",
        str(input_path),
        str(output_path),
    ]
    completed = run(command, capture_output=True, text=True, check=False)  # noqa: S603
    assert completed.returncode == 0, completed.stderr
    return _read_cli_output(output_path, raster)


def _read_cli_output(path: Path, raster: RasterSpec) -> gpd.GeoDataFrame:
    """Read CLI GeoJSON with the same GDAL bindings used by the API."""

    gdal, ogr = _import_gdal()
    with (
        gdal.ExceptionMgr(useExceptions=True),
        ogr.ExceptionMgr(useExceptions=True),
    ):
        dataset = gdal.OpenEx(str(path), gdal.OF_VECTOR)
        assert dataset is not None
        layer = dataset.GetLayer()
        assert layer is not None
        records = [
            (
                np.int32(feature.GetFieldAsInteger(0)),
                float(feature.GetFieldAsDouble(1)),
                float(feature.GetFieldAsDouble(2)),
                from_wkb(bytes(feature.GetGeometryRef().ExportToWkb())),
            )
            for feature in layer
        ]
    return gpd.GeoDataFrame(
        records,
        columns=["ID", "floor", "ceil", "geometry"],
        geometry="geometry",
        crs=raster.crs,
    )


def _write_raster(path: Path, raster: RasterSpec) -> None:
    """Write the in-memory API's validated source pixels for the CLI baseline."""

    gdal, _ = _import_gdal()
    height, width = raster.values.shape
    with gdal.ExceptionMgr(useExceptions=True):
        driver = gdal.GetDriverByName("GTiff")
        assert driver is not None
        dataset = driver.Create(str(path), width, height, 1, gdal.GDT_Float64)
        assert dataset is not None
        dataset.SetGeoTransform(raster.geotransform)
        dataset.SetProjection(raster.crs.to_wkt())
        band = dataset.GetRasterBand(1)
        assert band is not None
        values = np.ascontiguousarray(raster.values, dtype=np.float64)
        result = band.WriteRaster(
            0,
            0,
            width,
            height,
            values.tobytes(),
            buf_xsize=width,
            buf_ysize=height,
            buf_type=gdal.GDT_Float64,
        )
        assert result in (None, gdal.CE_None)
        if raster.nodata is not None:
            band.SetNoDataValue(raster.nodata)
        dataset = None


def _assert_exact_native_match(
    actual: gpd.GeoDataFrame,
    expected: gpd.GeoDataFrame,
) -> None:
    """Require matching native schema, properties, order, and encoded geometry."""

    assert list(actual.columns) == ["ID", "floor", "ceil", "geometry"]
    assert list(expected.columns) == list(actual.columns)
    assert actual.crs == expected.crs
    assert_geodataframe_equal(actual, expected, check_like=False)
    assert actual.geometry.to_wkb().tolist() == expected.geometry.to_wkb().tolist()


def test_fixed_level_endpoints_match_native_cli(
    fixed_level_raster: xr.DataArray,
    tmp_path: Path,
) -> None:
    """Endpoint levels remain native boundaries instead of convenience extrema."""

    levels = [0.0, 1.0, 2.0, 3.0, 4.0]
    expected = _cli_fixed_level_baseline(
        fixed_level_raster,
        levels=levels,
        crs="EPSG:4326",
        nodata=None,
        tmp_path=tmp_path,
    )
    actual = gdal_fixed_level_polygons(
        fixed_level_raster,
        levels=levels,
        crs="EPSG:4326",
    )

    native_bounds = expected[["floor", "ceil"]].to_numpy()
    assert expected.ID.tolist() == list(range(len(expected)))
    assert all(np.isclose(native_bounds, level).any() for level in levels)
    _assert_exact_native_match(actual, expected)


def test_fixed_level_exact_threshold_matches_native_cli(
    fixed_level_raster: xr.DataArray,
    tmp_path: Path,
) -> None:
    """A sample equal to a supplied level retains GDAL's upper-band membership."""

    levels = [0.0, 2.0, 4.0]
    expected = _cli_fixed_level_baseline(
        fixed_level_raster,
        levels=levels,
        crs="EPSG:4326",
        nodata=None,
        tmp_path=tmp_path,
    )
    actual = gdal_fixed_level_polygons(
        fixed_level_raster,
        levels=levels,
        crs="EPSG:4326",
    )

    matching_features = expected.loc[expected.geometry.covers(Point(0.0, 0.0))]
    assert len(matching_features) == 1
    assert np.isclose(matching_features.floor.iloc[0], 2.0)
    _assert_exact_native_match(actual, expected)


def test_fixed_level_underflow_and_overflow_match_native_cli(
    fixed_level_raster: xr.DataArray,
    tmp_path: Path,
) -> None:
    """Out-of-range endpoints are preserved as native labels and outer bands."""

    levels = [-10.0, 1.0, 3.0, 10.0]
    expected = _cli_fixed_level_baseline(
        fixed_level_raster,
        levels=levels,
        crs="EPSG:4326",
        nodata=None,
        tmp_path=tmp_path,
    )
    actual = gdal_fixed_level_polygons(
        fixed_level_raster,
        levels=levels,
        crs="EPSG:4326",
    )

    assert expected[["ID", "floor", "ceil"]].values.tolist() == [
        [0.0, -10.0, 1.0],
        [1.0, 1.0, 3.0],
        [2.0, 3.0, 10.0],
    ]
    _assert_exact_native_match(actual, expected)


def test_fixed_level_precision_matches_native_cli(
    fixed_level_raster: xr.DataArray,
    tmp_path: Path,
) -> None:
    """The API uses the CLI's six-decimal fixed-level serialization."""

    levels = [0.123456789, 0.987654321, 3.876543219]
    expected = _cli_fixed_level_baseline(
        fixed_level_raster,
        levels=levels,
        crs="EPSG:4326",
        nodata=None,
        tmp_path=tmp_path,
    )
    actual = gdal_fixed_level_polygons(
        fixed_level_raster,
        levels=levels,
        crs="EPSG:4326",
    )

    native_bounds = expected[["floor", "ceil"]].to_numpy()
    rounded_levels = [float(format(level, "f")) for level in levels]
    assert all(np.isclose(native_bounds, level).any() for level in rounded_levels)
    _assert_exact_native_match(actual, expected)


@pytest.mark.parametrize(
    ("missing_value", "nodata"),
    [(np.nan, None), (-999.0, -999.0)],
)
def test_fixed_level_missing_data_hole_matches_native_cli(
    missing_value: float,
    nodata: float | None,
    tmp_path: Path,
) -> None:
    """NaN and explicit nodata holes retain the native unfilled domain."""

    data = xr.DataArray(
        [
            [0.0, 0.0, 0.0, 0.0, 0.0],
            [0.0, 1.0, 1.0, 1.0, 0.0],
            [0.0, 1.0, missing_value, 1.0, 0.0],
            [0.0, 1.0, 1.0, 1.0, 0.0],
            [0.0, 0.0, 0.0, 0.0, 0.0],
        ],
        dims=("y", "x"),
        coords={"x": range(5), "y": range(4, -1, -1)},
    )
    levels = [0.0, 0.5, 1.0]
    expected = _cli_fixed_level_baseline(
        data,
        levels=levels,
        crs="EPSG:4326",
        nodata=nodata,
        tmp_path=tmp_path,
    )
    actual = gdal_fixed_level_polygons(
        data,
        levels=levels,
        crs="EPSG:4326",
        nodata=nodata,
    )

    assert not unary_union(expected.geometry).covers(Point(2.0, 2.0))
    _assert_exact_native_match(actual, expected)


def test_fixed_level_runs_preserve_native_feature_order_and_wkb(
    fixed_level_raster: xr.DataArray,
    tmp_path: Path,
) -> None:
    """Repeated in-process runs preserve the command's feature and ring order."""

    levels = [0.0, 1.0, 2.0, 3.0, 4.0]
    expected = _cli_fixed_level_baseline(
        fixed_level_raster,
        levels=levels,
        crs="EPSG:4326",
        nodata=None,
        tmp_path=tmp_path,
    )

    for _ in range(3):
        actual = gdal_fixed_level_polygons(
            fixed_level_raster,
            levels=levels,
            crs="EPSG:4326",
        )
        _assert_exact_native_match(actual, expected)
