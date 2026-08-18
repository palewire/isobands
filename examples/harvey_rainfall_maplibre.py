"""Create a MapLibre-ready Hurricane Harvey rainfall contour map from ERA5.

Before running, configure a CDS API key:
https://cds.climate.copernicus.eu/how-to-api

Run from the repository root with:

    uv run --with cdsapi --with h5netcdf --with h5py \
        python examples/harvey_rainfall_maplibre.py
"""

from __future__ import annotations

from pathlib import Path

import cdsapi
import geopandas as gpd
import numpy as np
import xarray as xr

from isobands import isobands

DATE = "2017-08-27"
DATASET = "derived-era5-single-levels-daily-statistics"
GULF_COAST_AREA = [35.0, -103.0, 23.0, -87.0]
EXAMPLES_DIRECTORY = Path(__file__).resolve().parent
OUTPUT_DIRECTORY = EXAMPLES_DIRECTORY / "output"
ERA5_PATH = OUTPUT_DIRECTORY / f"harvey-daily-rainfall-{DATE}.nc"
GEOJSON_PATH = OUTPUT_DIRECTORY / f"harvey-daily-rainfall-{DATE}.geojson"
QUANTILES = [0.2, 0.4, 0.6, 0.8]
COLORS = ["#eff3ff", "#bdd7e7", "#6baed6", "#3182bd", "#08519c"]


def download_era5() -> None:
    """Download ERA5's daily rainfall total for Hurricane Harvey's landfall."""

    OUTPUT_DIRECTORY.mkdir(exist_ok=True)
    cdsapi.Client().retrieve(
        DATASET,
        {
            "product_type": "reanalysis",
            "variable": "total_precipitation",
            "year": "2017",
            "month": "08",
            "day": "27",
            "daily_statistic": "daily_sum",
            "time_zone": "utc+00:00",
            "frequency": "1_hourly",
            "area": GULF_COAST_AREA,
        },
        str(ERA5_PATH),
    )


def load_rainfall() -> xr.DataArray:
    """Load the downloaded precipitation field as millimeters."""

    with xr.open_dataset(ERA5_PATH) as dataset:
        rainfall = (dataset["tp"].squeeze(drop=True) * 1000).load()

    rainfall.attrs["units"] = "millimeters"
    return rainfall


def quintiles(values: np.ndarray) -> np.ndarray:
    """Return the four interior thresholds that split valid values into fifths."""

    return np.quantile(values, QUANTILES)


def color_for(minimum: float, thresholds: np.ndarray) -> str:
    """Return a sequential rainfall color for a contour interval."""

    return COLORS[int(np.searchsorted(thresholds, minimum, side="right"))]


def write_geojson(rainfall: xr.DataArray) -> gpd.GeoDataFrame:
    """Convert rainfall into dissolved, colored quintile bands."""

    thresholds = quintiles(rainfall.to_numpy().ravel())
    bands = isobands(rainfall, levels=quintiles, crs="EPSG:4326")
    dissolved = bands.dissolve(by=["min_value", "max_value"], as_index=False)
    dissolved["color"] = dissolved["min_value"].map(
        lambda minimum: color_for(minimum, thresholds),
    )
    GEOJSON_PATH.write_text(dissolved.to_json(), encoding="utf-8")
    return dissolved


def main() -> None:
    """Download, contour, and export Hurricane Harvey's rainfall field."""

    download_era5()
    bands = write_geojson(load_rainfall())
    print(f"Wrote {len(bands)} contour bands to {GEOJSON_PATH}")


if __name__ == "__main__":
    main()
