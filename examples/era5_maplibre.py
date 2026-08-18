"""Create a MapLibre-ready contour map from ERA5 daily high temperatures.

Before running, configure a CDS API key:
https://cds.climate.copernicus.eu/how-to-api

Run from the repository root with:

    uv run --with cdsapi --with h5netcdf --with h5py python examples/era5_maplibre.py

Then serve this directory and open ``era5_maplibre.html``:

    python -m http.server --directory examples 8000
"""

from __future__ import annotations

from pathlib import Path

import cdsapi
import geopandas as gpd
import xarray as xr

from isobands import isobands

DATE = "2020-08-16"
DATASET = "derived-era5-single-levels-daily-statistics"
WEST_COAST_AREA = [52.0, -145.0, 22.0, -95.0]
EXAMPLES_DIRECTORY = Path(__file__).resolve().parent
OUTPUT_DIRECTORY = EXAMPLES_DIRECTORY / "output"
ERA5_PATH = OUTPUT_DIRECTORY / f"era5-daily-high-{DATE}.nc"
GEOJSON_PATH = OUTPUT_DIRECTORY / f"era5-daily-high-{DATE}.geojson"
TURBO_MINIMUM = -60.0
TURBO_MAXIMUM = 60.0


def download_era5() -> None:
    """Download ERA5's West Coast daily maximum temperature for the example day."""

    OUTPUT_DIRECTORY.mkdir(exist_ok=True)
    cdsapi.Client().retrieve(
        DATASET,
        {
            "product_type": "reanalysis",
            "variable": "2m_temperature",
            "year": "2020",
            "month": "08",
            "day": "16",
            "daily_statistic": "daily_maximum",
            "time_zone": "utc+00:00",
            "frequency": "1_hourly",
            "area": WEST_COAST_AREA,
        },
        str(ERA5_PATH),
    )


def load_temperature() -> xr.DataArray:
    """Load the downloaded field as Celsius with MapLibre-friendly longitude."""

    with xr.open_dataset(ERA5_PATH) as dataset:
        temperature = (dataset["t2m"].squeeze(drop=True) - 273.15).load()

    temperature = temperature.assign_coords(
        longitude=((temperature.longitude + 180) % 360) - 180,
    ).sortby("longitude")
    temperature.attrs["units"] = "degrees_Celsius"
    return temperature


def color_for(minimum: float) -> str:
    """Return a Turbo colormap color for a Celsius contour interval."""

    span = TURBO_MAXIMUM - TURBO_MINIMUM
    value = max(0.0, min((minimum - TURBO_MINIMUM) / span, 1.0))
    red = (
        0.13572138
        + 4.61539260 * value
        - 42.66032258 * value**2
        + 132.13108234 * value**3
        - 152.94239396 * value**4
        + 59.28637943 * value**5
    )
    green = (
        0.09140261
        + 2.19418839 * value
        + 4.84296658 * value**2
        - 14.18503333 * value**3
        + 4.27729857 * value**4
        + 2.82956604 * value**5
    )
    blue = (
        0.10667330
        + 12.64194608 * value
        - 60.58204836 * value**2
        + 110.36276771 * value**3
        - 89.90310912 * value**4
        + 27.34824973 * value**5
    )
    channels = (red, green, blue)
    return "#" + "".join(
        f"{round(max(0.0, min(channel, 1.0)) * 255):02x}" for channel in channels
    )


def write_geojson(temperature: xr.DataArray) -> gpd.GeoDataFrame:
    """Convert the ERA5 field to dissolved, colored five-degree bands."""

    bands = isobands(temperature, interval=5, crs="EPSG:4326")
    dissolved = bands.dissolve(by=["min_value", "max_value"], as_index=False)
    dissolved["color"] = dissolved["min_value"].map(color_for)
    GEOJSON_PATH.write_text(dissolved.to_json(), encoding="utf-8")
    return dissolved


def main() -> None:
    """Download, contour, and export the map data."""

    download_era5()
    bands = write_geojson(load_temperature())
    print(f"Wrote {len(bands)} contour bands to {GEOJSON_PATH}")


if __name__ == "__main__":
    main()
