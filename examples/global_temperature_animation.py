"""Create a lightweight, animated global ERA5 temperature contour map.

Before running, configure a CDS API key:
https://cds.climate.copernicus.eu/how-to-api

Run from the repository root with:

    uv run --with cdsapi --with h5netcdf --with h5py \
        python examples/global_temperature_animation.py
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import cdsapi
import numpy as np
import xarray as xr

import isobands

START_DATE = date(2020, 8, 16)
FRAME_COUNT = 7
DATASET = "derived-era5-single-levels-daily-statistics"
GLOBAL_AREA = [90.0, -180.0, -90.0, 180.0]
COARSENING_FACTOR = 4
SIMPLIFICATION_TOLERANCE = 0.15
TEMPERATURE_LEVELS = [-30.0, -20.0, -10.0, 0.0, 10.0, 20.0, 30.0, 40.0]
EXAMPLES_DIRECTORY = Path(__file__).resolve().parent
OUTPUT_DIRECTORY = EXAMPLES_DIRECTORY / "output"
ERA5_PATH = OUTPUT_DIRECTORY / "global-daily-high-2020-08-16-22.nc"
ANIMATION_PATH = OUTPUT_DIRECTORY / "global-temperature-2020-08-16-22.json"


def dates() -> list[date]:
    """Return the consecutive daily frames in the animation."""

    return [START_DATE + timedelta(days=offset) for offset in range(FRAME_COUNT)]


def download_era5() -> None:
    """Download seven global ERA5 daily maximum temperature fields."""

    OUTPUT_DIRECTORY.mkdir(exist_ok=True)
    cdsapi.Client().retrieve(
        DATASET,
        {
            "product_type": "reanalysis",
            "variable": "2m_temperature",
            "year": str(START_DATE.year),
            "month": f"{START_DATE.month:02d}",
            "day": [f"{current.day:02d}" for current in dates()],
            "daily_statistic": "daily_maximum",
            "time_zone": "utc+00:00",
            "frequency": "1_hourly",
            "area": GLOBAL_AREA,
        },
        str(ERA5_PATH),
    )


def load_temperature() -> xr.DataArray:
    """Load daily high temperatures as Celsius on a 1-degree global grid."""

    with xr.open_dataset(ERA5_PATH) as dataset:
        temperature = (dataset["t2m"] - 273.15).load()

    temperature = temperature.assign_coords(
        longitude=((temperature.longitude + 180) % 360) - 180,
    ).sortby("longitude")
    return temperature.coarsen(
        latitude=COARSENING_FACTOR,
        longitude=COARSENING_FACTOR,
        boundary="trim",
    ).mean()


def smooth_temperature(temperature: xr.DataArray) -> xr.DataArray:
    """Apply a small wrapped spatial smoother before contour generation."""

    values = temperature.to_numpy()
    north = np.concatenate((values[..., :1, :], values[..., :-1, :]), axis=-2)
    south = np.concatenate((values[..., 1:, :], values[..., -1:, :]), axis=-2)
    smoothed = (
        4 * values
        + north
        + south
        + np.roll(values, 1, axis=-1)
        + np.roll(values, -1, axis=-1)
    ) / 8
    return temperature.copy(data=smoothed)


def color_for(minimum: float) -> str:
    """Return a Turbo colormap color for a Celsius contour interval."""

    normalized = max(0.0, min((minimum + 60.0) / 120.0, 1.0))
    red = (
        0.13572138
        + 4.61539260 * normalized
        - 42.66032258 * normalized**2
        + 132.13108234 * normalized**3
        - 152.94239396 * normalized**4
        + 59.28637943 * normalized**5
    )
    green = (
        0.09140261
        + 2.19418839 * normalized
        + 4.84296658 * normalized**2
        - 14.18503333 * normalized**3
        + 4.27729857 * normalized**4
        + 2.82956604 * normalized**5
    )
    blue = (
        0.10667330
        + 12.64194608 * normalized
        - 60.58204836 * normalized**2
        + 110.36276771 * normalized**3
        - 89.90310912 * normalized**4
        + 27.34824973 * normalized**5
    )
    return "#" + "".join(
        f"{round(max(0.0, min(channel, 1.0)) * 255):02x}"
        for channel in (red, green, blue)
    )


def round_values(value: Any) -> Any:  # noqa: ANN401
    """Round GeoJSON values to keep the checked-in animation compact."""

    if isinstance(value, float):
        return round(value, 3)
    if isinstance(value, list):
        return [round_values(item) for item in value]
    if isinstance(value, dict):
        return {key: round_values(item) for key, item in value.items()}
    return value


def frame_geojson(temperature: xr.DataArray) -> dict[str, Any]:
    """Contour, simplify, and compact one daily temperature frame."""

    bands = isobands.from_raster(
        smooth_temperature(temperature),
        levels=TEMPERATURE_LEVELS,
        crs="EPSG:4326",
    )
    dissolved = bands.dissolve(by=["min_value", "max_value"], as_index=False)
    dissolved.geometry = dissolved.geometry.simplify(
        SIMPLIFICATION_TOLERANCE,
        preserve_topology=True,
    )
    dissolved["color"] = dissolved["min_value"].map(color_for)
    return round_values(json.loads(dissolved.to_json()))


def write_animation(temperature: xr.DataArray) -> None:
    """Write all daily frames into one MapLibre-ready animation file."""

    frames = []
    for index, current in enumerate(dates()):
        frames.append(
            {
                "date": current.isoformat(),
                "data": frame_geojson(temperature.isel(valid_time=index)),
            }
        )
    ANIMATION_PATH.write_text(json.dumps({"frames": frames}), encoding="utf-8")


def main() -> None:
    """Download, simplify, contour, and export the animated global map."""

    download_era5()
    write_animation(load_temperature())
    print(f"Wrote {FRAME_COUNT} daily frames to {ANIMATION_PATH}")


if __name__ == "__main__":
    main()
