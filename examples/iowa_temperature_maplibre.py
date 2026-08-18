"""Create a MapLibre-ready Iowa land-surface-temperature contour map from MODIS.

Run from the repository root with:

    uv run python examples/iowa_temperature_maplibre.py
"""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

import geopandas as gpd
import numpy as np
import xarray as xr
from osgeo import gdal
from shapely import box

from isobands import isobands

DATE = "2020-08-12"
SOURCE_URL = (
    "https://modiseuwest.blob.core.windows.net/modis-061-cogs/"
    "MYD11A1/11/04/2020225/"
    "MYD11A1.A2020225.h11v04.061.2021014002251_LST_Day_1km.tif"
)
SIGNING_URL = "https://planetarycomputer.microsoft.com/api/sas/v1/sign"
EXAMPLES_DIRECTORY = Path(__file__).resolve().parent
OUTPUT_DIRECTORY = EXAMPLES_DIRECTORY / "output"
GEOJSON_PATH = OUTPUT_DIRECTORY / f"iowa-land-surface-temperature-{DATE}.geojson"
NODATA_GEOJSON_PATH = OUTPUT_DIRECTORY / f"iowa-temperature-no-data-{DATE}.geojson"
WEST, SOUTH, EAST, NORTH = -103.0, 39.75, -84.0, 47.0
SOURCE_RESOLUTION = 0.02
AGGREGATION_FACTOR = 4
MINIMUM_VALID_COVERAGE = 0.2
NODATA = -9999.0
TEMPERATURE_LEVELS = [20.0, 25.0, 30.0, 35.0]
KELVIN_SCALE = 0.02


def sign_source_url() -> str:
    """Return a temporary URL for the public MODIS cloud-optimized GeoTIFF."""

    with urlopen(  # noqa: S310
        f"{SIGNING_URL}?{urlencode({'href': SOURCE_URL})}",
    ) as response:
        return str(json.load(response)["href"])


def load_temperature() -> xr.DataArray:
    """Load and aggregate Iowa's valid daytime MODIS temperature pixels."""

    gdal.UseExceptions()
    dataset = gdal.Warp(
        "",
        sign_source_url(),
        format="MEM",
        dstSRS="EPSG:4326",
        outputBounds=(WEST, SOUTH, EAST, NORTH),
        xRes=SOURCE_RESOLUTION,
        yRes=SOURCE_RESOLUTION,
        resampleAlg="near",
    )
    raw_values = dataset.ReadAsArray().astype(float)
    rows = raw_values.shape[0] // AGGREGATION_FACTOR * AGGREGATION_FACTOR
    columns = raw_values.shape[1] // AGGREGATION_FACTOR * AGGREGATION_FACTOR
    raw_values = raw_values[:rows, :columns]
    valid = raw_values != 0
    blocks = raw_values.reshape(
        rows // AGGREGATION_FACTOR,
        AGGREGATION_FACTOR,
        columns // AGGREGATION_FACTOR,
        AGGREGATION_FACTOR,
    )
    valid_blocks = valid.reshape(blocks.shape)
    valid_counts = valid_blocks.sum(axis=(1, 3))
    celsius = blocks * KELVIN_SCALE - 273.15
    averages = np.where(valid_blocks, celsius, 0).sum(axis=(1, 3)) / np.maximum(
        valid_counts,
        1,
    )
    values = np.where(
        valid_counts >= AGGREGATION_FACTOR**2 * MINIMUM_VALID_COVERAGE,
        averages,
        NODATA,
    )
    transform = dataset.GetGeoTransform()
    longitude = (
        transform[0]
        + (
            np.arange(columns // AGGREGATION_FACTOR) * AGGREGATION_FACTOR
            + AGGREGATION_FACTOR / 2
        )
        * transform[1]
    )
    latitude = (
        transform[3]
        + (
            np.arange(rows // AGGREGATION_FACTOR) * AGGREGATION_FACTOR
            + AGGREGATION_FACTOR / 2
        )
        * transform[5]
    )
    return xr.DataArray(
        values,
        dims=("latitude", "longitude"),
        coords={"latitude": latitude, "longitude": longitude},
        name="land_surface_temperature",
        attrs={"units": "degrees_Celsius"},
    )


def color_for(minimum: float) -> str:
    """Return a temperature color for a contour interval."""

    if minimum < TEMPERATURE_LEVELS[0]:
        return "#2c7bb6"
    if minimum < TEMPERATURE_LEVELS[1]:
        return "#abd9e9"
    if minimum < TEMPERATURE_LEVELS[2]:
        return "#fdae61"
    if minimum < TEMPERATURE_LEVELS[3]:
        return "#f46d43"
    return "#d7191c"


def write_geojson(temperature: xr.DataArray) -> gpd.GeoDataFrame:
    """Convert the temperature field into colored contour bands."""

    bands = isobands(
        temperature,
        levels=TEMPERATURE_LEVELS,
        nodata=NODATA,
        crs="EPSG:4326",
    )
    dissolved = bands.dissolve(by=["min_value", "max_value"], as_index=False)
    dissolved["color"] = dissolved["min_value"].map(color_for)
    GEOJSON_PATH.write_text(dissolved.to_json(), encoding="utf-8")
    return dissolved


def write_nodata_geojson(temperature: xr.DataArray) -> None:
    """Export unavailable temperature cells as individual map squares."""

    longitude = temperature.longitude.to_numpy()
    latitude = temperature.latitude.to_numpy()
    longitude_step = float(np.abs(np.diff(longitude)).mean())
    latitude_step = float(np.abs(np.diff(latitude)).mean())
    rows, columns = np.where(temperature.to_numpy() == NODATA)
    geometry = [
        box(
            longitude[column] - longitude_step / 2,
            latitude[row] - latitude_step / 2,
            longitude[column] + longitude_step / 2,
            latitude[row] + latitude_step / 2,
        )
        for row, column in zip(rows, columns, strict=True)
    ]
    cells = gpd.GeoDataFrame(geometry=geometry, crs="EPSG:4326")
    NODATA_GEOJSON_PATH.write_text(cells.dissolve().to_json(), encoding="utf-8")


def main() -> None:
    """Download, contour, and export the Iowa land-surface-temperature map data."""

    OUTPUT_DIRECTORY.mkdir(exist_ok=True)
    temperature = load_temperature()
    bands = write_geojson(temperature)
    write_nodata_geojson(temperature)
    print(f"Wrote {len(bands)} contour bands to {GEOJSON_PATH}")


if __name__ == "__main__":
    main()
