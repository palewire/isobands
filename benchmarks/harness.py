"""Compare the in-memory from_raster path with GDAL's file-based contour path."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import shutil
import subprocess
import sys
import time
import urllib.request
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import geopandas as gpd
import numpy as np
import xarray as xr
from osgeo import gdal, osr
from shapely.ops import unary_union

from isobands import from_raster

FULL_SOURCE_URL = "https://github.com/pydata/xarray-data/raw/master/air_temperature.nc"
FULL_SOURCE_SHA256 = "c606b89c35970a2983b914b76df4adbb409003ef34aa7cfd7f582e41f307482b"
FULL_TIMESTEP = 0
DEFAULT_LEVELS = (240.0, 250.0, 260.0, 270.0, 280.0, 290.0, 300.0)
_BAND_COVERAGE_RTOL = 1e-4
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SMOKE_FIXTURE = PROJECT_ROOT / "examples/data/air_temperature_time0.npz"


@dataclass(frozen=True)
class BenchmarkInput:
    """Data and provenance prepared before validation and timing."""

    raster: xr.DataArray
    source: str
    source_hash: str
    interpolated: bool


def _cache_dir() -> Path:
    configured = os.environ.get("ISOBANDS_BENCHMARK_CACHE")
    if configured:
        return Path(configured).expanduser()
    if sys.platform == "darwin":
        return Path.home() / "Library/Caches/isobands/benchmarks"
    return (
        Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
        / "isobands/benchmarks"
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _version(distribution: str) -> str | None:
    try:
        return importlib.metadata.version(distribution)
    except importlib.metadata.PackageNotFoundError:
        return None


def _load_npz(path: Path) -> xr.DataArray:
    with np.load(path) as archive:
        value_key = "air" if "air" in archive else "values"
        if value_key not in archive:
            raise ValueError(f"{path} must contain an 'air' or 'values' array.")
        values = archive[value_key]
        if values.ndim == 3:
            values = values[0]
        if values.ndim != 2:
            raise ValueError(
                f"{path} air data must be two-dimensional after timestep selection."
            )
        x = (
            archive["lon"]
            if "lon" in archive
            else np.arange(values.shape[1], dtype=float)
        )
        y = (
            archive["lat"]
            if "lat" in archive
            else np.arange(values.shape[0], dtype=float)
        )
    return xr.DataArray(
        values,
        dims=("lat", "lon"),
        coords={"lon": x, "lat": y},
        name="air",
    )


def _download_full_source(cache: Path) -> Path:
    path = cache / "air_temperature.nc"
    if path.exists() and _sha256(path) == FULL_SOURCE_SHA256:
        return path
    cache.mkdir(parents=True, exist_ok=True)
    partial = cache / "air_temperature.nc.download"
    try:
        urllib.request.urlretrieve(FULL_SOURCE_URL, partial)
        actual = _sha256(partial)
        if actual != FULL_SOURCE_SHA256:
            raise RuntimeError(
                f"Downloaded source checksum mismatch: expected {FULL_SOURCE_SHA256}, got {actual}."
            )
        partial.replace(path)
    finally:
        partial.unlink(missing_ok=True)
    return path


def _parse_grid(value: str) -> tuple[int, int]:
    try:
        rows, columns = (int(part) for part in value.lower().split("x", maxsplit=1))
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "Grid must be ROWSxCOLUMNS, for example 500x1000."
        ) from error
    if rows < 2 or columns < 2:
        raise argparse.ArgumentTypeError("Grid dimensions must each be at least two.")
    return rows, columns


def _interpolate(data: xr.DataArray, shape: tuple[int, int]) -> xr.DataArray:
    """Deterministically resample an upstream 25x53 slice before timed work."""

    y_name, x_name = data.dims
    return data.interp(
        {
            y_name: np.linspace(
                float(data[y_name].min()), float(data[y_name].max()), shape[0]
            ),
            x_name: np.linspace(
                float(data[x_name].min()), float(data[x_name].max()), shape[1]
            ),
        }
    )


def _prepare_input(mode: str, grid: tuple[int, int]) -> BenchmarkInput:
    if mode == "smoke":
        if not SMOKE_FIXTURE.exists():
            raise FileNotFoundError(
                f"Smoke fixture is required at {SMOKE_FIXTURE}. It is not present in this checkout."
            )
        return BenchmarkInput(
            raster=_load_npz(SMOKE_FIXTURE),
            source=str(SMOKE_FIXTURE.relative_to(PROJECT_ROOT)),
            source_hash=_sha256(SMOKE_FIXTURE),
            interpolated=False,
        )

    source = _download_full_source(_cache_dir())
    with xr.open_dataset(source, engine="scipy") as dataset:
        data = dataset["air"].isel(time=FULL_TIMESTEP).load()
    return BenchmarkInput(
        raster=_interpolate(data, grid),
        source=FULL_SOURCE_URL,
        source_hash=_sha256(source),
        interpolated=True,
    )


def _levels(data: xr.DataArray) -> tuple[float, ...]:
    values = np.asarray(data.values)
    minimum, maximum = float(np.nanmin(values)), float(np.nanmax(values))
    levels = tuple(level for level in DEFAULT_LEVELS if minimum < level < maximum)
    if levels:
        return levels
    return (float(np.nanmean(values)),)


def _geotransform(
    data: xr.DataArray,
) -> tuple[float, float, float, float, float, float]:
    y_name, x_name = data.dims
    x, y = np.asarray(data[x_name], dtype=float), np.asarray(data[y_name], dtype=float)
    return (
        float(x[0] - (x[1] - x[0]) / 2),
        float(x[1] - x[0]),
        0.0,
        float(y[0] - (y[1] - y[0]) / 2),
        0.0,
        float(y[1] - y[0]),
    )


def _write_geotiff(data: xr.DataArray, path: Path, crs: str) -> None:
    y_name, x_name = data.dims
    values = np.asarray(data.transpose(y_name, x_name).values, dtype=np.float64)
    driver = gdal.GetDriverByName("GTiff")
    if driver is None:
        raise RuntimeError("GDAL GTiff driver is unavailable.")
    dataset = driver.Create(
        str(path), values.shape[1], values.shape[0], 1, gdal.GDT_Float64
    )
    if dataset is None:
        raise RuntimeError("GDAL could not create benchmark GeoTIFF.")
    try:
        dataset.SetGeoTransform(_geotransform(data))
        spatial_reference = osr.SpatialReference()
        spatial_reference.SetFromUserInput(crs)
        dataset.SetProjection(spatial_reference.ExportToWkt())
        dataset.GetRasterBand(1).WriteArray(values)
        dataset.FlushCache()
    finally:
        dataset = None


def _gdal_contour(tiff: Path, output: Path, levels: Sequence[float]) -> None:
    """Run the installed GDAL command-line contour implementation."""

    executable = shutil.which("gdal_contour")
    if executable is None:
        raise RuntimeError(
            "gdal_contour is required for the file-based baseline but was not found "
            "on PATH. Install conda-forge GDAL 3.12.2 and expose its bin directory."
        )
    output.unlink(missing_ok=True)
    command = [
        executable,
        "-p",
        "-of",
        "GeoJSON",
        "-nln",
        "contours",
        "-amin",
        "min_value",
        "-amax",
        "max_value",
        "--quiet",
    ]
    for level in levels:
        command.extend(("-fl", format(level, ".17g")))
    command.extend((str(tiff), str(output)))
    try:
        subprocess.run(  # noqa: S603 - command is constructed from fixed arguments.
            command, check=True, capture_output=True, text=True
        )
    except subprocess.CalledProcessError as error:
        detail = error.stderr.strip() or error.stdout.strip() or "no diagnostic output"
        raise RuntimeError(f"gdal_contour failed: {detail}") from error
    if not output.is_file():
        raise RuntimeError(
            "gdal_contour exited successfully but did not create output."
        )


def _from_raster_run(
    data: xr.DataArray, levels: Sequence[float], crs: str
) -> tuple[gpd.GeoDataFrame, dict[str, float]]:
    start = time.perf_counter()
    output = from_raster(data, levels=levels, crs=crs)
    return output, {"from_raster": time.perf_counter() - start}


def _gdal_run(
    data: xr.DataArray, levels: Sequence[float], crs: str, workdir: Path
) -> tuple[gpd.GeoDataFrame, dict[str, float]]:
    tiff, contour = workdir / "input.tif", workdir / "contours.geojson"
    tiff.unlink(missing_ok=True)
    Path(f"{tiff}.aux.xml").unlink(missing_ok=True)
    contour.unlink(missing_ok=True)
    started = time.perf_counter()
    _write_geotiff(data, tiff, crs)
    raster_write = time.perf_counter() - started
    started = time.perf_counter()
    _gdal_contour(tiff, contour, levels)
    contour_time = time.perf_counter() - started
    started = time.perf_counter()
    output = gpd.read_file(contour)
    read_time = time.perf_counter() - started
    return output, {
        "xarray_to_geotiff": raster_write,
        "gdal_contour_subprocess": contour_time,
        "geopandas_file_read": read_time,
    }


def _band_geometries(
    output: gpd.GeoDataFrame, minimum: float, maximum: float
) -> dict[tuple[float, float], Any]:
    """Union records by their finite, clipped band labels."""

    grouped: dict[tuple[float, float], list[Any]] = {}
    for lower, upper, geometry in zip(
        output["min_value"],
        output["max_value"],
        output.geometry,
        strict=True,
    ):
        finite_lower = float(lower) if np.isfinite(lower) else minimum
        finite_upper = float(upper) if np.isfinite(upper) else maximum
        label = (max(finite_lower, minimum), min(finite_upper, maximum))
        grouped.setdefault(label, []).append(geometry)
    return {label: unary_union(geometries) for label, geometries in grouped.items()}


def _validate(
    direct: gpd.GeoDataFrame, baseline: gpd.GeoDataFrame, data: xr.DataArray
) -> None:
    if (
        direct.crs is None
        or baseline.crs is None
        or not direct.crs.equals(baseline.crs)
    ):
        raise AssertionError("Contour outputs have different CRS values.")
    if not direct.geometry.is_valid.all() or not baseline.geometry.is_valid.all():
        raise AssertionError("Contour output contains invalid geometries.")
    if not np.allclose(
        direct.total_bounds, baseline.total_bounds, rtol=1e-8, atol=1e-8
    ):
        raise AssertionError("Contour output bounds differ.")
    minimum, maximum = float(np.nanmin(data.values)), float(np.nanmax(data.values))
    direct_bands = _band_geometries(direct, minimum, maximum)
    baseline_bands = _band_geometries(baseline, minimum, maximum)
    if direct_bands.keys() != baseline_bands.keys():
        raise AssertionError(
            "Contour output label keys differ: "
            f"direct={sorted(direct_bands)}, baseline={sorted(baseline_bands)}."
        )
    for label in direct_bands:
        direct_band, baseline_band = direct_bands[label], baseline_bands[label]
        difference = direct_band.symmetric_difference(baseline_band).area
        scale = max(direct_band.area, baseline_band.area, 1.0)
        tolerance = scale * _BAND_COVERAGE_RTOL
        if difference > tolerance:
            raise AssertionError(
                f"Contour coverage differs for label {label}: "
                f"{difference:.6g} exceeds tolerance {tolerance:.6g}."
            )
    difference = (
        unary_union(direct.geometry)
        .symmetric_difference(unary_union(baseline.geometry))
        .area
    )
    scale = max(unary_union(direct.geometry).area, 1.0)
    if difference > scale * 1e-7:
        raise AssertionError(
            f"Contour coverage differs by {difference / scale:.3g} of its area."
        )


def _summary(samples: list[dict[str, float]]) -> dict[str, dict[str, float]]:
    keys = samples[0].keys()
    return {key: _statistics([sample[key] for sample in samples]) for key in keys}


def _statistics(samples: list[float]) -> dict[str, float]:
    values = np.asarray(samples)
    return {
        "mean_seconds": float(np.mean(values)),
        "median_seconds": float(np.median(values)),
        "min_seconds": float(np.min(values)),
        "max_seconds": float(np.max(values)),
    }


@contextmanager
def _workdir(cache: Path) -> Iterator[Path]:
    cache.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="run-", dir=cache) as directory:
        yield Path(directory)


def _metadata(
    data: BenchmarkInput, levels: Sequence[float], repeats: int
) -> dict[str, Any]:
    return {
        "os": platform.platform(),
        "hardware": {
            "machine": platform.machine(),
            "processor": platform.processor() or None,
            "cpu_count": os.cpu_count(),
        },
        "python": sys.version,
        "versions": {
            "gdal": gdal.VersionInfo("RELEASE_NAME"),
            "isobands": _version("isobands"),
            "geopandas": _version("geopandas"),
            "numpy": _version("numpy"),
            "pyproj": _version("pyproj"),
            "scipy": _version("scipy"),
            "shapely": _version("shapely"),
            "xarray": _version("xarray"),
        },
        "source": {"location": data.source, "sha256": data.source_hash},
        "grid_shape": list(data.raster.shape),
        "levels": list(levels),
        "repeats": repeats,
        "interpolated": data.interpolated,
        "peak_memory": {
            "available": False,
            "reason": "Unavailable: this harness has no isolated cross-platform native RSS sampler.",
        },
    }


def _markdown(result: dict[str, Any]) -> str:
    metadata, timings = result["metadata"], result["timings"]
    rows = [
        "# isobands benchmark",
        "",
        f"- Source: `{metadata['source']['location']}` (`{metadata['source']['sha256']}`)",
        f"- Grid: `{metadata['grid_shape']}`; interpolated: `{metadata['interpolated']}`",
        f"- Levels: `{metadata['levels']}`; repeats: `{metadata['repeats']}`",
        f"- GDAL: `{metadata['versions']['gdal']}`; isobands: `{metadata['versions']['isobands']}`",
        "- Peak memory: unavailable (no isolated cross-platform native RSS sampler).",
        "",
        "| Path | Median total seconds | Stages (median; mean/min/max seconds) |",
        "| --- | ---: | --- |",
    ]
    for name, timing in timings.items():
        stages = ", ".join(
            (
                f"{key}={value['median_seconds']:.6f}; "
                f"{value['mean_seconds']:.6f}/{value['min_seconds']:.6f}/{value['max_seconds']:.6f}"
            )
            for key, value in timing["stages"].items()
        )
        rows.append(
            f"| {name} | {timing['total_seconds']['median_seconds']:.6f} | {stages} |"
        )
    return "\n".join(rows) + "\n"


def run(mode: str, repeats: int, warmups: int, grid: tuple[int, int]) -> dict[str, Any]:
    gdal.UseExceptions()
    prepared = _prepare_input(mode, grid)
    crs = "EPSG:4326"
    levels = _levels(prepared.raster)
    values = np.asarray(prepared.raster.values)
    maximum = float(np.nanmax(values))
    contour_upper_bound = (
        maximum + max(abs(float(np.nanmin(values))), abs(maximum), 1.0) * 1e-5
    )
    baseline_levels = (float(np.nanmin(values)), *levels, contour_upper_bound)
    cache = _cache_dir()
    with _workdir(cache) as workdir:
        direct, _ = _from_raster_run(prepared.raster, levels, crs)
        baseline, _ = _gdal_run(prepared.raster, baseline_levels, crs, workdir)
        _validate(direct, baseline, prepared.raster)
        for _ in range(warmups):
            _from_raster_run(prepared.raster, levels, crs)
            _gdal_run(prepared.raster, baseline_levels, crs, workdir)
        direct_runs: list[dict[str, float]] = []
        gdal_runs: list[dict[str, float]] = []
        for _ in range(repeats):
            _, direct_stages = _from_raster_run(prepared.raster, levels, crs)
            _, gdal_stages = _gdal_run(prepared.raster, baseline_levels, crs, workdir)
            direct_runs.append(direct_stages)
            gdal_runs.append(gdal_stages)
    direct_summary, gdal_summary = _summary(direct_runs), _summary(gdal_runs)
    direct_total = _statistics([sum(sample.values()) for sample in direct_runs])
    gdal_total = _statistics([sum(sample.values()) for sample in gdal_runs])
    return {
        "metadata": _metadata(prepared, levels, repeats),
        "validation": {"passed": True},
        "timings": {
            "xarray_to_from_raster_to_geodataframe": {
                "stages": direct_summary,
                "total_seconds": direct_total,
            },
            "xarray_to_geotiff_to_gdal_contour_to_geopandas": {
                "stages": gdal_summary,
                "total_seconds": gdal_total,
            },
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("smoke", "full"), required=True)
    parser.add_argument("--repeats", type=int, default=None)
    parser.add_argument("--warmups", type=int, default=1)
    parser.add_argument("--grid", type=_parse_grid, default=(500, 1000))
    parser.add_argument("--json", type=Path, required=True)
    parser.add_argument("--markdown", type=Path, required=True)
    arguments = parser.parse_args()
    if arguments.repeats is not None and arguments.repeats < 1:
        parser.error("--repeats must be at least one.")
    if arguments.warmups < 0:
        parser.error("--warmups cannot be negative.")
    repeats = arguments.repeats or (2 if arguments.mode == "smoke" else 5)
    result = run(arguments.mode, repeats, arguments.warmups, arguments.grid)
    arguments.json.parent.mkdir(parents=True, exist_ok=True)
    arguments.markdown.parent.mkdir(parents=True, exist_ok=True)
    arguments.json.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    arguments.markdown.write_text(_markdown(result))
    print(_markdown(result), end="")
