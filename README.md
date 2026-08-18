# isobands

An easy way to make filled contour maps with Python.

`isobands` converts a regular two-dimensional
[xarray](https://xarray.dev/) raster into filled contour polygons backed by a
[GeoPandas](https://geopandas.org/) `GeoDataFrame`.

## Install

`isobands` needs an installed, matching `osgeo.gdal` Python binding. If your
Conda or system-managed environment already provides one of the
[tested baselines](docs/installation.md), install the package directly:

```sh
pip install isobands
```

For a pip-managed binding, install matching native GDAL 3.13.2 development
files, then use the recommended newest tested and installable extra:

```sh
pip install "isobands[gdal313]"
```

GDAL 3.10.2 and 3.11.5 remain tested advanced compatibility choices through
the `gdal310` and `gdal311` extras. See the [installation
guide](docs/installation.md) for exact versions and platform instructions.
## Quick start

```python
import numpy as np
import xarray as xr

import isobands

data = xr.DataArray(
    np.array([[0.0, 1.0, 2.0], [1.0, 2.0, 3.0], [2.0, 3.0, 4.0]]),
    dims=("y", "x"),
    coords={"x": [0.0, 1.0, 2.0], "y": [2.0, 1.0, 0.0]},
)
bands = isobands.from_raster(data, levels=[1.5, 2.5], crs="EPSG:4326")
print(bands[["min_value", "max_value", "geometry"]])
```

The result always has the stable `min_value`, `max_value`, and `geometry`
columns and a GeoPandas CRS. Exactly one of `levels` or `interval` is required.
Use `levels` for strictly increasing interior thresholds, or `interval` for
integral thresholds. Values equal to a threshold belong to the upper band.

Regular one-dimensional rectilinear coordinates are required, and coordinate
names do not imply a CRS. Pass `crs=` explicitly when metadata is absent or
ambiguous. Explicit finite `nodata` takes precedence over `_FillValue` and
`missing_value`; otherwise nonfinite cells are excluded. Dask-backed arrays
are materialized eagerly for GDAL's in-memory dataset. See the
[guide](docs/index.md) for usage examples and the API reference.

## Real-world example

The runnable [NOAA/NCEP example](examples/air_temperature.py) uses the pinned
fixture in `examples/data/`, calls `from_raster()` with Kelvin levels and
`EPSG:4326`, checks the schema, CRS, and geometry validity, and dissolves
components with GeoPandas:

```sh
python examples/air_temperature.py
```

The [ERA5 MapLibre example](examples/era5_maplibre.py) downloads the global
daily high temperature for August 16, 2020, creates five-degree Celsius
isobands, and writes GeoJSON for the accompanying
[`era5_maplibre.html`](examples/era5_maplibre.html) page. It requires a
Copernicus Climate Data Store API key and the optional `cdsapi`, `h5netcdf`,
and `h5py` packages.

## Documentation

The hosted documentation is intended for
[palewi.re/docs/isobands/](https://palewi.re/docs/isobands/). The source is in
[`docs/`](docs/), with a single-page guide covering installation, quick start,
the API reference, and the MapLibre example. Benchmarks and their
reference data remain in [`benchmarks/`](benchmarks/).
