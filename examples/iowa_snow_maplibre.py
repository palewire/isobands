"""Create a MapLibre-ready Iowa snow-cover contour map from MODIS data.

Run from the repository root with:

    uv run python examples/iowa_snow_maplibre.py
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

DATE = "2011-02-04"
SOURCE_URL = (
    "https://modiseuwest.blob.core.windows.net/modis-061-cogs/"
    "MOD10A1/11/04/2011035/"
    "MOD10A1.A2011035.h11v04.061.2021181172753_NDSI_Snow_Cover.tif"
)
SIGNING_URL = "https://planetarycomputer.microsoft.com/api/sas/v1/sign"
EXAMPLES_DIRECTORY = Path(__file__).resolve().parent
OUTPUT_DIRECTORY = EXAMPLES_DIRECTORY / "output"
GEOJSON_PATH = OUTPUT_DIRECTORY / f"iowa-snow-cover-{DATE}.geojson"
NODATA_GEOJSON_PATH = OUTPUT_DIRECTORY / f"iowa-snow-no-data-{DATE}.geojson"
WEST, SOUTH, EAST, NORTH = -103.0, 39.75, -84.0, 47.0
RESOLUTION = 0.16
NODATA = -9999.0
SNOW_LEVELS = [20.0, 50.0, 80.0]


def sign_source_url() -> str:
    """Return a temporary URL for the public MODIS cloud-optimized GeoTIFF."""

    with urlopen(  # noqa: S310
        f"{SIGNING_URL}?{urlencode({'href': SOURCE_URL})}",
    ) as response:
        return str(json.load(response)["href"])


def load_snow_cover() -> xr.DataArray:
    """Load Iowa's MODIS snow-cover field and preserve unobserved pixels."""

    gdal.UseExceptions()
    dataset = gdal.Warp(
        "",
        sign_source_url(),
        format="MEM",
        dstSRS="EPSG:4326",
        outputBounds=(WEST, SOUTH, EAST, NORTH),
        xRes=RESOLUTION,
        yRes=RESOLUTION,
        resampleAlg="near",
    )
    values = dataset.ReadAsArray().astype(float)
    # MODIS reserves 0-100 for observed snow cover; higher values are status flags.
    values[values > 100] = NODATA
    transform = dataset.GetGeoTransform()
    longitude = transform[0] + (np.arange(dataset.RasterXSize) + 0.5) * transform[1]
    latitude = transform[3] + (np.arange(dataset.RasterYSize) + 0.5) * transform[5]
    return xr.DataArray(
        values,
        dims=("latitude", "longitude"),
        coords={"latitude": latitude, "longitude": longitude},
        name="snow_cover",
        attrs={"units": "percent"},
    )


def color_for(minimum: float) -> str:
    """Return a sequential blue color for a snow-cover interval."""

    if minimum < SNOW_LEVELS[0]:
        return "#deebf7"
    if minimum < SNOW_LEVELS[1]:
        return "#9ecae1"
    if minimum < SNOW_LEVELS[2]:
        return "#3182bd"
    return "#08519c"


def write_geojson(snow_cover: xr.DataArray) -> gpd.GeoDataFrame:
    """Convert the satellite field into colored snow-cover bands."""

    bands = isobands(
        snow_cover,
        levels=SNOW_LEVELS,
        nodata=NODATA,
        crs="EPSG:4326",
    )
    dissolved = bands.dissolve(by=["min_value", "max_value"], as_index=False)
    dissolved["color"] = dissolved["min_value"].map(color_for)
    GEOJSON_PATH.write_text(dissolved.to_json(), encoding="utf-8")
    return dissolved


def write_nodata_geojson(snow_cover: xr.DataArray) -> None:
    """Export unavailable cells as individual map squares."""

    longitude = snow_cover.longitude.to_numpy()
    latitude = snow_cover.latitude.to_numpy()
    longitude_step = float(np.abs(np.diff(longitude)).mean())
    latitude_step = float(np.abs(np.diff(latitude)).mean())
    rows, columns = np.where(snow_cover.to_numpy() == NODATA)
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
    NODATA_GEOJSON_PATH.write_text(cells.to_json(), encoding="utf-8")


def main() -> None:
    """Download, contour, and export the Iowa snow-cover map data."""

    OUTPUT_DIRECTORY.mkdir(exist_ok=True)
    snow_cover = load_snow_cover()
    bands = write_geojson(snow_cover)
    write_nodata_geojson(snow_cover)
    print(f"Wrote {len(bands)} contour bands to {GEOJSON_PATH}")


if __name__ == "__main__":
    main()
