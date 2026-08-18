"""Create the compact NOAA/NCEP fixture used by real-world tests.

Run ``UV_NO_ENV_FILE=1 uv run --no-sync python
tests/generate_air_temperature_fixture.py --download`` to retrieve the pinned
source, verify its SHA-256 digest, and rewrite the fixture.  Normal tests use
only the generated ``.npz`` file and never make a network request.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from urllib.request import urlretrieve

import numpy as np
from osgeo import gdal

SOURCE_URL = "https://github.com/pydata/xarray-data/raw/master/air_temperature.nc"
SOURCE_SHA256 = "c606b89c35970a2983b914b76df4adbb409003ef34aa7cfd7f582e41f307482b"
SOURCE_TITLE = "4x daily NMC reanalysis (1948)"
ROOT = Path(__file__).parents[1]
FIXTURE_PATH = ROOT / "examples/data/air_temperature_time0.npz"
RECORD_PATH = ROOT / "examples/data/air_temperature_time0.source.json"
DOWNLOAD_PATH = ROOT / "examples/data/air_temperature.source.nc"


def _sha256(path: Path) -> str:
    """Return the SHA-256 checksum for one local file."""

    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _metadata(dataset: object, air: object) -> dict[str, object]:
    """Return the source metadata required to reproduce this small fixture."""

    dataset_metadata = dataset.GetMetadata()  # type: ignore[union-attr]
    air_metadata = air.GetMetadata()  # type: ignore[union-attr]
    return {
        "dataset_attrs": {
            key.removeprefix("NC_GLOBAL#"): value
            for key, value in dataset_metadata.items()
            if key.startswith("NC_GLOBAL#")
        },
        "variable_attrs": {
            key: value
            for key, value in air_metadata.items()
            if not key.startswith("NETCDF_")
        },
        "source_url": SOURCE_URL,
        "source_sha256": SOURCE_SHA256,
        "source_title": SOURCE_TITLE,
        "variable": "air",
        "source_dimensions": {"time": 2920, "lat": 25, "lon": 53},
    }


def generate(source: Path, output: Path = FIXTURE_PATH) -> None:
    """Verify a source NetCDF file and save ``air.isel(time=0)`` as NPZ."""

    if _sha256(source) != SOURCE_SHA256:
        raise ValueError(f"{source} does not match the pinned NOAA/NCEP SHA-256")
    gdal.UseExceptions()
    dataset = gdal.Open(str(source))
    if dataset is None:
        raise ValueError("GDAL could not open the source NetCDF file")
    if dataset.GetMetadataItem("NC_GLOBAL#title") != SOURCE_TITLE:
        raise ValueError("Source dataset does not have the expected NMC title")
    if (dataset.RasterCount, dataset.RasterYSize, dataset.RasterXSize) != (
        2920,
        25,
        53,
    ):
        raise ValueError("Source air variable does not have the expected dimensions")
    air = dataset.GetRasterBand(1)
    if air is None or air.GetMetadataItem("units") != "degK":
        raise ValueError("Source air variable does not use degK")
    lon_dataset = gdal.Open(f'NETCDF:"{source}":lon')
    lat_dataset = gdal.Open(f'NETCDF:"{source}":lat')
    if lon_dataset is None or lat_dataset is None:
        raise ValueError("GDAL could not read the source longitude or latitude")
    metadata = _metadata(dataset, air)
    scale_factor = float(air.GetMetadataItem("scale_factor") or 1.0)
    time_zero = air.ReadAsArray().astype(np.float64) * scale_factor
    lon = lon_dataset.GetRasterBand(1).ReadAsArray().reshape(-1)
    lat = lat_dataset.GetRasterBand(1).ReadAsArray().reshape(-1)
    del lat_dataset, lon_dataset, dataset

    output.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        output,
        values=np.asarray(time_zero),
        lon=np.asarray(lon),
        lat=np.asarray(lat),
        metadata=json.dumps(metadata, sort_keys=True),
    )
    RECORD_PATH.write_text(
        json.dumps(
            {
                **metadata,
                "fixture": output.name,
                "redistribution_evidence": {
                    "url": "https://www.weather.gov/disclaimer",
                    "statement": (
                        "NOAA/NWS information is in the public domain unless "
                        "specifically noted otherwise and may be used freely."
                    ),
                },
                "generation_command": (
                    "UV_NO_ENV_FILE=1 uv run --no-sync python "
                    "tests/generate_air_temperature_fixture.py --download"
                ),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def main() -> None:
    """Parse CLI options and generate the checked compact fixture."""

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--download",
        action="store_true",
        help="download the pinned source before generating the fixture",
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=DOWNLOAD_PATH,
        help="local NetCDF source path (defaults to examples/data)",
    )
    arguments = parser.parse_args()
    source = arguments.source
    if arguments.download:
        source.parent.mkdir(parents=True, exist_ok=True)
        urlretrieve(SOURCE_URL, source)
    try:
        generate(source)
    finally:
        if arguments.download and source == DOWNLOAD_PATH:
            source.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
