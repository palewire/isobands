"""Create filled bands from the pinned NOAA/NCEP air-temperature fixture.

Run this file from any working directory with:

    python /path/to/isobands/examples/air_temperature.py

The example reads only the checked-in fixture and does not write files.
"""

from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import xarray as xr

import isobands

FIXTURE = Path(__file__).resolve().parent / "data" / "air_temperature_time0.npz"
LEVELS_KELVIN = (240.0, 260.0, 280.0)


def load_fixture() -> tuple[xr.DataArray, dict[str, object]]:
    """Load the compact, pinned time-zero air-temperature field."""

    with np.load(FIXTURE) as archive:
        metadata = json.loads(str(archive["metadata"]))
        data = xr.DataArray(
            np.asarray(archive["values"], dtype=np.float64),
            dims=("lat", "lon"),
            coords={
                "lat": np.asarray(archive["lat"], dtype=np.float64),
                "lon": np.asarray(archive["lon"], dtype=np.float64),
            },
            name="air",
            attrs={
                **metadata["variable_attrs"],
                "source": metadata["dataset_attrs"]["references"],
            },
        )
    return data, metadata


def main() -> None:
    """Generate, validate, and dissolve the example's filled bands."""

    data, metadata = load_fixture()
    bands = isobands.from_raster(data, levels=LEVELS_KELVIN, crs="EPSG:4326")
    expected_columns = {"min_value", "max_value", "geometry"}
    if set(bands.columns) != expected_columns:
        raise RuntimeError(f"Unexpected output schema: {list(bands.columns)!r}")
    if bands.crs is None or bands.crs.to_epsg() != 4326:
        raise RuntimeError(f"Unexpected CRS: {bands.crs!r}")
    if not bool(bands.geometry.is_valid.all()):
        raise RuntimeError("GDAL returned an invalid contour geometry")

    dissolved: gpd.GeoDataFrame = bands.dissolve(
        by=["min_value", "max_value"],
        as_index=False,
    )
    print(f"Source: {metadata['source_title']} ({metadata['variable']})")
    print(f"Input shape: {data.shape}; units: {data.attrs.get('units')}")
    print(f"Output schema: {list(bands.columns)}; CRS: {bands.crs}")
    print(f"Valid components: {len(bands)}; dissolved bands: {len(dissolved)}")
    print(dissolved[["min_value", "max_value"]].to_string(index=False))


if __name__ == "__main__":
    main()
