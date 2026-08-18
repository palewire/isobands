# isobands

An easy wasy to make filled contour maps with Python.

`isobands` converts a regular two-dimensional
[xarray](https://xarray.dev/) raster into filled contour polygons backed by a
[GeoPandas](https://geopandas.org/) `GeoDataFrame`. It uses GDAL's in-memory
raster and vector drivers, so a normal call does not create intermediate files.

## Install

GDAL **3.12.2** and its matching development headers are required. The PyPI
`GDAL` distribution is source-only; `pip` cannot install the system library for
you. On Linux, install the exact GDAL 3.12.2 runtime and development packages
from your distribution or build them from source. On macOS, Homebrew users
should install matching `gdal` headers and libraries. Windows users should use
a conda-forge environment:

```sh
conda install -c conda-forge gdal=3.12.2
```

On Linux and macOS, verify the development installation before installing
`isobands`:

```sh
gdal-config --version  # must print 3.12.2
pip install isobands
```

See the [guide](docs/guide.md) for platform-specific
details and compiler troubleshooting.

## Quick start

```python
import numpy as np
import xarray as xr

from isobands import isobands

data = xr.DataArray(
    np.array([[0.0, 1.0, 2.0], [1.0, 2.0, 3.0], [2.0, 3.0, 4.0]]),
    dims=("y", "x"),
    coords={"x": [0.0, 1.0, 2.0], "y": [2.0, 1.0, 0.0]},
)
bands = isobands(data, levels=[1.5, 2.5], crs="EPSG:4326")
print(bands[["min_value", "max_value", "geometry"]])
```

The result always has the stable `min_value`, `max_value`, and `geometry`
columns and a GeoPandas CRS. Exactly one of `levels` or `interval` is required.
Use `levels` for strictly increasing interior thresholds, or `interval` for
integral thresholds. Values equal to a threshold belong to the upper band.

## Stable compatibility promise

The `0.1.x` API is the single `isobands()` function and its documented
`min_value`/`max_value`/`geometry` output. Compatible `0.1.x` releases keep
those names and meanings. This promise does not expand the documented grid,
numeric, dependency, or platform support.

Regular one-dimensional rectilinear coordinates are required, and coordinate
names do not imply a CRS. Pass `crs=` explicitly when metadata is absent or
ambiguous. Explicit finite `nodata` takes precedence over `_FillValue` and
`missing_value`; otherwise nonfinite cells are excluded. Dask-backed arrays
are materialized eagerly for GDAL's in-memory dataset. See the
[guide](docs/guide.md) for full usage, API reference, behavior, and limits.

## Real-world example

The runnable [NOAA/NCEP example](examples/air_temperature.py) uses the pinned
fixture in `examples/data/`, calls `isobands` with Kelvin levels and
`EPSG:4326`, checks the schema, CRS, and geometry validity, and dissolves
components with GeoPandas:

```sh
python examples/air_temperature.py
```

## Documentation and development

The hosted documentation is intended for
[palewi.re/docs/isobands/](https://palewi.re/docs/isobands/). The source is in
[`docs/`](docs/), with a single-page guide covering installation, quick start,
API reference, behavior, limits, and neighboring tools. Benchmarks and their
reference data remain in [`benchmarks/`](benchmarks/).

Contributors should read [`CONTRIBUTING.md`](CONTRIBUTING.md). Run
`make docs-check` and `make linkcheck` for documentation changes.
