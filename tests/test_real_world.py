"""Real-world and generative validation for the stable isobands API."""

from __future__ import annotations

import json
from itertools import combinations
from pathlib import Path

import numpy as np
import xarray as xr
from hypothesis import example, given, settings
from hypothesis import strategies as st
from numpy.testing import assert_allclose
from osgeo import gdal, ogr
from shapely import from_wkb
from shapely.geometry import Point, Polygon, box
from shapely.ops import unary_union

from isobands import isobands
from isobands._gdal import _normalize_polygon_ring_roles

FIXTURE_PATH = Path(__file__).parents[1] / "examples/data/air_temperature_time0.npz"
RECORD_PATH = (
    Path(__file__).parents[1] / "examples/data/air_temperature_time0.source.json"
)
LEVELS = (240.0, 260.0, 280.0)


def _air_temperature() -> tuple[xr.DataArray, dict[str, object]]:
    """Load the tracked time-zero NMC air-temperature field without network I/O."""

    with np.load(FIXTURE_PATH) as fixture:
        metadata = json.loads(str(fixture["metadata"]))
        data = xr.DataArray(
            fixture["values"],
            dims=("lat", "lon"),
            coords={"lat": fixture["lat"], "lon": fixture["lon"]},
            name="air",
            attrs={
                **metadata["variable_attrs"],
                "source": metadata["dataset_attrs"]["references"],
            },
        )
    return data, metadata


def _direct_gdal_bands(
    values: np.ndarray,
    geotransform: tuple[float, float, float, float, float, float],
    levels: tuple[float, ...],
    *,
    nodata: float | None = None,
) -> dict[tuple[float, float], object]:
    """Return actual-label geometry unions from an independent GDAL invocation."""

    values = np.asarray(values, dtype=np.float64)
    valid = np.isfinite(values) if nodata is None else values != nodata
    minimum = float(np.min(values[valid]))
    maximum = float(np.max(values[valid]))
    outer_upper = maximum + 1e-5
    gdal.UseExceptions()
    raster = gdal.GetDriverByName("MEM").Create(
        "", values.shape[1], values.shape[0], 1, gdal.GDT_Float64
    )
    if raster is None:
        raise RuntimeError("GDAL MEM raster driver is unavailable")
    raster.SetGeoTransform(geotransform)
    band = raster.GetRasterBand(1)
    band.WriteArray(values)
    if nodata is not None:
        band.SetNoDataValue(nodata)
    vector = gdal.GetDriverByName("MEM").Create("", 0, 0, 0, gdal.GDT_Unknown)
    if vector is None:
        raise RuntimeError("GDAL MEM vector driver is unavailable")
    layer = vector.CreateLayer("bands", geom_type=ogr.wkbMultiPolygon)
    if layer is None:
        raise RuntimeError("GDAL could not create baseline contour layer")
    for field_name in ("minimum", "maximum"):
        layer.CreateField(ogr.FieldDefn(field_name, ogr.OFTReal))
    options = [
        "POLYGONIZE=YES",
        "FIXED_LEVELS="
        + ",".join(format(value, ".17g") for value in (minimum, *levels, outer_upper)),
        "ELEV_FIELD_MIN=0",
        "ELEV_FIELD_MAX=1",
    ]
    if nodata is not None:
        options.append(f"NODATA={nodata:.17g}")
    if gdal.ContourGenerateEx(band, layer, options) != gdal.CE_None:
        raise RuntimeError("GDAL could not generate baseline contour polygons")
    geometries: dict[tuple[float, float], list[object]] = {}
    for feature in layer:
        geometry = from_wkb(bytes(feature.GetGeometryRef().ExportToWkb()))
        assert geometry.is_valid
        field_minimum = float(feature.GetFieldAsDouble(0))
        field_maximum = float(feature.GetFieldAsDouble(1))
        if np.isclose(field_maximum, outer_upper, rtol=0.0, atol=1e-9):
            field_maximum = maximum
        geometries.setdefault((field_minimum, field_maximum), []).append(geometry)
    del layer, vector, band, raster
    return {labels: unary_union(parts) for labels, parts in geometries.items()}


def _direct_gdal_band_areas(data: xr.DataArray) -> dict[tuple[float, float], float]:
    """Return actual-label area summaries from a raw GDAL contour invocation."""

    values = np.asarray(data.values, dtype=np.float64)
    lon = np.asarray(data["lon"].values, dtype=np.float64)
    lat = np.asarray(data["lat"].values, dtype=np.float64)
    bands = _direct_gdal_bands(
        values,
        (
            lon[0] - (lon[1] - lon[0]) / 2,
            lon[1] - lon[0],
            0.0,
            lat[0] - (lat[1] - lat[0]) / 2,
            0.0,
            lat[1] - lat[0],
        ),
        LEVELS,
    )
    return {labels: geometry.area for labels, geometry in bands.items()}


def _assert_sample_coverage(
    result: object,
    data: xr.DataArray,
    thresholds: tuple[float, ...],
) -> None:
    """Require each finite sample center to occur in exactly its labeled band."""

    values = np.asarray(data.values)
    x_name = "lon" if "lon" in data.coords else "x"
    y_name = "lat" if "lat" in data.coords else "y"
    lon = np.asarray(data[x_name].values)
    lat = np.asarray(data[y_name].values)
    minimum = float(np.nanmin(values))
    maximum = float(np.nanmax(values))
    boundaries = (
        minimum,
        *(level for level in thresholds if minimum < level < maximum),
        maximum,
    )
    for row, column in np.ndindex(values.shape):
        point = Point(float(lon[column]), float(lat[row]))
        covered = [
            (band.min_value, band.max_value)
            for band in result.itertuples()
            if band.geometry.covers(point)
        ]
        if not np.isfinite(values[row, column]):
            assert not covered
            continue
        expected_index = int(
            np.searchsorted(boundaries[1:-1], values[row, column], side="right")
        )
        assert covered == [boundaries[expected_index : expected_index + 2]]


def _band_unions(result: object) -> dict[tuple[float, float], object]:
    """Combine repeated records with the same labels for geometry comparison."""

    return {
        labels: unary_union(group.geometry)
        for labels, group in result.groupby(["min_value", "max_value"])
    }


def test_noaa_ncep_fixture_is_compact_and_reproducible() -> None:
    """The tracked fixture preserves the pinned upstream identity and metadata."""

    data, metadata = _air_temperature()
    record = json.loads(RECORD_PATH.read_text(encoding="utf-8"))

    assert data.shape == (25, 53)
    assert data.attrs["units"] == "degK"
    assert metadata["dataset_attrs"]["title"] == "4x daily NMC reanalysis (1948)"
    assert metadata["source_dimensions"] == {"time": 2920, "lat": 25, "lon": 53}
    assert metadata["source_sha256"] == (
        "c606b89c35970a2983b914b76df4adbb409003ef34aa7cfd7f582e41f307482b"
    )
    assert data.attrs["source"] == metadata["dataset_attrs"]["references"]
    assert record["fixture"] == FIXTURE_PATH.name
    assert record["source_sha256"] == metadata["source_sha256"]
    assert "weather.gov/disclaimer" in record["redistribution_evidence"]["url"]
    assert "public domain" in record["redistribution_evidence"]["statement"]


def test_real_air_temperature_matches_direct_gdal_summary_and_invariants() -> None:
    """Real NMC air data has stable labels, coverage, topology, and CRS."""

    data, _ = _air_temperature()
    result = isobands(data, levels=LEVELS, crs="EPSG:4326")
    expected_bounds = [[227.0, 240.0], [240.0, 260.0], [260.0, 280.0], [280.0, 302.6]]
    baseline_areas = _direct_gdal_band_areas(data)

    assert result[["min_value", "max_value"]].values.tolist() == expected_bounds
    assert result.crs.to_epsg() == 4326
    assert_allclose(result.total_bounds, [-161.25, 13.75, -28.75, 76.25])
    assert set(result.geometry.geom_type) <= {"Polygon", "MultiPolygon"}
    assert all(geometry.is_valid for geometry in result.geometry)
    assert unary_union(result.geometry).is_valid
    for left, right in combinations(result.itertuples(), 2):
        if left.min_value != right.min_value:
            assert left.geometry.intersection(right.geometry).area == 0.0
    result_areas = {
        labels: geometry.area for labels, geometry in _band_unions(result).items()
    }
    assert set(baseline_areas) == set(map(tuple, expected_bounds))
    assert result_areas.keys() == baseline_areas.keys()
    for labels, baseline_area in baseline_areas.items():
        assert_allclose(result_areas[labels], baseline_area, rtol=3e-6, atol=0.01)
    _assert_sample_coverage(result, data, LEVELS)


def test_real_air_temperature_axis_orientations_are_equivalent() -> None:
    """Reversing regular latitude and longitude axes preserves all bands."""

    data, _ = _air_temperature()
    forward = isobands(data, levels=LEVELS, crs="EPSG:4326")
    reversed_axes = isobands(
        data.isel(lat=slice(None, None, -1), lon=slice(None, None, -1)),
        levels=LEVELS,
        crs="EPSG:4326",
    )

    assert (
        forward[["min_value", "max_value"]].values.tolist()
        == reversed_axes[["min_value", "max_value"]].values.tolist()
    )
    for labels, geometry in _band_unions(forward).items():
        assert (
            geometry.symmetric_difference(_band_unions(reversed_axes)[labels]).area
            < 1e-9
        )


def test_real_air_temperature_derived_nodata_is_excluded() -> None:
    """A derived mask leaves missing real-data centers outside every band."""

    data, _ = _air_temperature()
    masked = data.copy(deep=True)
    masked.values[[4, 12, 18], [8, 26, 42]] = np.nan
    result = isobands(masked, levels=LEVELS, crs="EPSG:4326")

    assert all(geometry.is_valid for geometry in result.geometry)
    _assert_sample_coverage(result, masked, LEVELS)


def test_touching_outside_gdal_ring_is_promoted_without_changing_holes() -> None:
    """The narrow ring-role normalization promotes only a false outside hole."""

    polygon = Polygon(
        [(0, 0), (2, 0), (2, 2), (0, 2), (0, 0)],
        [[(2, 2), (3, 2), (3, 3), (2, 2)]],
    )

    parts = _normalize_polygon_ring_roles(polygon)

    assert len(parts.retained) == len(parts.promoted) == 1
    assert parts.retained[0].is_valid
    assert parts.promoted[0].is_valid
    assert parts.retained[0].area == 4.0
    assert parts.promoted[0].area == 0.5


def test_zero_area_gdal_exterior_is_omitted_without_repairing_topology() -> None:
    """A collinear GDAL artifact has no domain area and produces no replacement."""

    parts = _normalize_polygon_ring_roles(Polygon([(0, 0), (1, 0), (2, 0), (0, 0)]))

    assert parts.retained == ()
    assert parts.promoted == ()


def test_nodata_component_at_threshold_uses_lower_inclusive_labels() -> None:
    """GDAL must not merge an empty lower band into a threshold-starting island."""

    data = xr.DataArray(
        [[-3.0, np.nan, 0.0, 0.0], [0.0, 0.0, np.nan, 3.0]],
        dims=("y", "x"),
        coords={"x": [10.0, 12.0, 14.0, 16.0], "y": [2.0, 0.0]},
    )
    result = isobands(data, levels=[-1.0, 0.0, 1.0], crs="EPSG:4326")

    assert (-1.0, 1.0) not in set(
        map(tuple, result[["min_value", "max_value"]].to_numpy())
    )
    _assert_sample_coverage(result, data, (-1.0, 0.0, 1.0))


def test_thin_nodata_gradient_preserves_gdal_interpolation() -> None:
    """A one-row valid component retains its interpolated threshold, not cell bins."""

    data = xr.DataArray(
        [
            [np.nan, np.nan, np.nan, np.nan],
            [np.nan, 0.0, 10.0, np.nan],
            [np.nan, np.nan, np.nan, np.nan],
        ],
        dims=("y", "x"),
        coords={"x": [0.0, 1.0, 2.0, 3.0], "y": [2.0, 1.0, 0.0]},
    )
    result = isobands(data, levels=[2.0], crs="EPSG:4326")
    padded = np.array(
        [[-999.0, -999.0], [0.0, 10.0], [-999.0, -999.0]],
        dtype=float,
    )
    baseline = _direct_gdal_bands(
        padded,
        (0.5, 1.0, 0.0, 2.5, 0.0, -1.0),
        (2.0,),
        nodata=-999.0,
    )
    package_bands = _band_unions(result)

    assert package_bands.keys() == baseline.keys() == {(0.0, 2.0), (2.0, 10.0)}
    for labels, geometry in baseline.items():
        assert package_bands[labels].symmetric_difference(geometry).area < 1e-9
    assert_allclose(package_bands[(0.0, 2.0)].area, 0.7)
    assert_allclose(package_bands[(0.0, 2.0)].bounds[2], 1.2)


def test_degenerate_gdal_ring_keeps_positive_area_and_valid_domain() -> None:
    """A self-touching GDAL exterior preserves its positive shell and nodata holes."""

    values = np.array(
        [[1.0, 3.0, -1.0, 3.0], [3.0, np.nan, 2.0, np.nan], [3.0, 1.0, np.nan, 0.0]]
    )
    data = xr.DataArray(
        values,
        dims=("y", "x"),
        coords={"x": range(4), "y": [2, 1, 0]},
    )
    result = isobands(data, levels=[-1.0, 0.0, 1.0], crs="EPSG:4326")
    combined = unary_union(result.geometry)
    nodata_domain = unary_union(
        [box(x - 0.5, y - 0.5, x + 0.5, y + 0.5) for x, y in [(1, 1), (3, 1), (2, 0)]]
    )
    valid_domain = box(-0.5, -0.5, 3.5, 2.5).difference(nodata_domain)

    assert all(geometry.is_valid for geometry in result.geometry)
    assert combined.is_valid
    assert combined.symmetric_difference(valid_domain).area < 1e-9
    assert _band_unions(result)[(1.0, 3.0)].area > 7.0
    for left, right in combinations(result.itertuples(), 2):
        if (left.min_value, left.max_value) != (right.min_value, right.max_value):
            assert left.geometry.intersection(right.geometry).area == 0.0
    _assert_sample_coverage(result, data, (-1.0, 0.0, 1.0))


@st.composite
def _regular_masked_fields(draw: st.DrawFn) -> xr.DataArray:
    """Construct small nonconstant regular fields with optional nodata cells."""

    height = draw(st.integers(min_value=2, max_value=4))
    width = draw(st.integers(min_value=2, max_value=4))
    values = np.asarray(
        draw(
            st.lists(
                st.integers(min_value=-3, max_value=3),
                min_size=height * width,
                max_size=height * width,
            )
        ),
        dtype=float,
    ).reshape(height, width)
    values[0, 0] = -3.0
    values[-1, -1] = 3.0
    mask = np.asarray(
        draw(
            st.lists(
                st.booleans(),
                min_size=height * width,
                max_size=height * width,
            )
        )
    ).reshape(height, width)
    mask[0, 0] = mask[-1, -1] = False
    values[mask] = np.nan
    return xr.DataArray(
        values,
        dims=("y", "x"),
        coords={
            "x": np.arange(width, dtype=float) * 2.0 + 10.0,
            "y": np.arange(height - 1, -1, -1, dtype=float) * 2.0,
        },
    )


@settings(max_examples=40, deadline=None)
@example(
    data=xr.DataArray(
        [[1.0, 3.0, -1.0, 3.0], [3.0, np.nan, 2.0, np.nan], [3.0, 1.0, np.nan, 0.0]],
        dims=("y", "x"),
        coords={"x": range(4), "y": [2, 1, 0]},
    )
)
@given(data=_regular_masked_fields())
def test_regular_grids_preserve_labels_masks_and_axis_orientation(
    data: xr.DataArray,
) -> None:
    """Small regular grids retain ordered lower-inclusive bands under reversal."""

    thresholds = (-1.0, 0.0, 1.0)
    result = isobands(data, levels=thresholds, crs="EPSG:4326")
    reversed_axes = isobands(
        data.isel(y=slice(None, None, -1), x=slice(None, None, -1)),
        levels=thresholds,
        crs="EPSG:4326",
    )

    labels = result[["min_value", "max_value"]].values.tolist()
    assert all(lower < upper for lower, upper in labels)
    assert all(geometry.is_valid for geometry in result.geometry)
    for left, right in combinations(result.itertuples(), 2):
        if (left.min_value, left.max_value) != (right.min_value, right.max_value):
            assert left.geometry.intersection(right.geometry).area == 0.0
    _assert_sample_coverage(result, data, thresholds)
    for label, geometry in _band_unions(result).items():
        assert (
            geometry.symmetric_difference(_band_unions(reversed_axes)[label]).area
            < 1e-9
        )
