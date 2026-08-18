"""Create a MapLibre-ready PM2.5 contour map from EPA monitor data.

Run from the repository root with:

    uv run python examples/pm25_maplibre.py
"""

from __future__ import annotations

from pathlib import Path
from urllib.request import urlretrieve
from zipfile import ZipFile

import geopandas as gpd
import numpy as np
import pandas as pd
import xarray as xr

import isobands

DATE = "2023-06-07"
EPA_DATA_URL = "https://aqs.epa.gov/aqsweb/airdata/daily_88101_2023.zip"
EXAMPLES_DIRECTORY = Path(__file__).resolve().parent
OUTPUT_DIRECTORY = EXAMPLES_DIRECTORY / "output"
ARCHIVE_PATH = OUTPUT_DIRECTORY / "daily_88101_2023.zip"
GEOJSON_PATH = OUTPUT_DIRECTORY / f"nyc-pm25-{DATE}.geojson"
HEALTH_LEVELS = [12.0, 35.4, 55.4, 125.4, 225.4]
WEST, SOUTH, EAST, NORTH = -89.5, 30.0, -58.0, 50.0


def download_data() -> None:
    """Download EPA's annual PM2.5 monitor archive."""

    OUTPUT_DIRECTORY.mkdir(exist_ok=True)
    urlretrieve(EPA_DATA_URL, ARCHIVE_PATH)


def load_stations() -> gpd.GeoDataFrame:
    """Load daily mean PM2.5 readings from monitors around New York City."""

    matching_rows: list[pd.DataFrame] = []
    with ZipFile(ARCHIVE_PATH) as archive:
        with archive.open(archive.namelist()[0]) as data_file:
            for chunk in pd.read_csv(data_file, chunksize=100_000, low_memory=False):
                matching_rows.append(
                    chunk.loc[
                        (chunk["Date Local"] == DATE)
                        & (chunk["Sample Duration"] == "1 HOUR")
                        & (chunk["Observation Count"] >= 18)
                        & chunk["Longitude"].between(WEST, EAST)
                        & chunk["Latitude"].between(SOUTH, NORTH)
                    ]
                )

    readings = pd.concat(matching_rows, ignore_index=True)
    readings = (
        readings.groupby(["Latitude", "Longitude"], as_index=False)["Arithmetic Mean"]
        .median()
        .rename(columns={"Arithmetic Mean": "pm25"})
    )
    return gpd.GeoDataFrame(
        readings,
        geometry=gpd.points_from_xy(readings["Longitude"], readings["Latitude"]),
        crs="EPSG:4326",
    )


def interpolate(stations: gpd.GeoDataFrame) -> xr.DataArray:
    """Create an inverse-distance-weighted PM2.5 field from monitor readings."""

    longitude = np.linspace(WEST, EAST, 160)
    latitude = np.linspace(SOUTH, NORTH, 120)
    grid_longitude, grid_latitude = np.meshgrid(longitude, latitude)
    distances = np.hypot(
        grid_longitude[..., np.newaxis] - stations["Longitude"].to_numpy(),
        grid_latitude[..., np.newaxis] - stations["Latitude"].to_numpy(),
    )
    weights = 1 / np.maximum(distances, 0.01) ** 2
    values = stations["pm25"].to_numpy()
    field = (weights * values).sum(axis=2) / weights.sum(axis=2)
    return xr.DataArray(
        field,
        dims=("latitude", "longitude"),
        coords={"latitude": latitude, "longitude": longitude},
        name="pm25",
        attrs={"units": "micrograms per cubic meter"},
    )


def color_for(minimum: float) -> str:
    """Return the EPA-style color for a PM2.5 health category."""

    if minimum < HEALTH_LEVELS[0]:
        return "#00e400"
    if minimum < HEALTH_LEVELS[1]:
        return "#ffff00"
    if minimum < HEALTH_LEVELS[2]:
        return "#ff7e00"
    if minimum < HEALTH_LEVELS[3]:
        return "#ff0000"
    if minimum < HEALTH_LEVELS[4]:
        return "#8f3f97"
    return "#7e0023"


def write_geojson(pm25: xr.DataArray) -> gpd.GeoDataFrame:
    """Convert the interpolated field into colored health-category bands."""

    bands = isobands.from_raster(pm25, levels=HEALTH_LEVELS, crs="EPSG:4326")
    dissolved = bands.dissolve(by=["min_value", "max_value"], as_index=False)
    dissolved["color"] = dissolved["min_value"].map(color_for)
    GEOJSON_PATH.write_text(dissolved.to_json(), encoding="utf-8")
    return dissolved


def main() -> None:
    """Download, interpolate, contour, and export the smoke map data."""

    download_data()
    bands = write_geojson(interpolate(load_stations()))
    print(f"Wrote {len(bands)} contour bands to {GEOJSON_PATH}")


if __name__ == "__main__":
    main()
