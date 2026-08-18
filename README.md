# isobands

In seconds, `isobands` turns a two-dimensional
[xarray](https://xarray.dev/) raster into filled contour polygons, using GDAL's
in-memory raster and vector datasets.
It is useful when a few lines of Python should turn gridded values into
analysis-ready [GeoPandas](https://geopandas.org/) geometry—without writing
intermediate files.

> **Alpha:** the public API is small and may change before a stable release.

## Install

`isobands` requires **GDAL 3.12.2**, including the matching system development
headers. PyPI's `GDAL` distribution is source-only: it compiles against the
system library, so `pip` alone cannot install the system GDAL prerequisite.

Install GDAL 3.12.2 with your Unix or macOS package manager (or build that
version), then verify the development installation:

```sh
gdal-config --version  # must print 3.12.2
```

On Windows, [conda-forge](https://conda-forge.org/) is recommended:

```sh
conda install -c conda-forge gdal=3.12.2
```

After the matching GDAL installation is available:

```sh
pip install isobands
```

Contributors can install all locked development and documentation dependencies
with `make install`; this also checks `gdal-config`.

## Quick start

This complete example uses only an in-memory array:

```python
import geopandas as gpd
import numpy as np
import xarray as xr

from isobands import isobands

data = xr.DataArray(
    np.array([[0.0, 1.0, 2.0], [1.0, 2.0, 3.0], [2.0, 3.0, 4.0]]),
    dims=("y", "x"),
    coords={"x": [0.0, 1.0, 2.0], "y": [2.0, 1.0, 0.0]},
)
bands: gpd.GeoDataFrame = isobands(data, levels=[1.5, 2.5], crs="EPSG:4326")
print(bands[["min_value", "max_value", "geometry"]])
```

The result has `min_value`, `max_value`, and `geometry` columns. Use
`levels=[...]` for explicit interior thresholds or `interval=...` for
thresholds at integral multiples of an interval. Exactly one is required;
interval mode is limited to 100,000 interior thresholds.

Disconnected or nodata-separated regions can produce multiple rows with the
same value bounds. Use ordinary GeoPandas operations if a dissolved band is
needed.

## Behavior and limits

- Input is a numeric `xarray.DataArray` with exactly two nonsingleton
  dimensions; singleton dimensions may be squeezed.
- Spatial coordinates must be regular, one-dimensional rectilinear axes.
  CF metadata is preferred when discovering x/y axes. Ascending and descending
  axes work; curvilinear, irregular, ambiguous, and missing axes fail clearly.
- Explicit `crs` wins over registered rioxarray metadata, then recognized
  CF/grid-mapping/spatial-reference metadata. Coordinate names never imply a
  CRS.
- Explicit finite `nodata` wins over `_FillValue`/`missing_value`; otherwise
  nonfinite floating cells are nodata. An all-nodata raster is invalid.
- Explicit levels outside the data range are ignored and outer bands use the
  finite valid extrema. Values equal to a threshold belong to the upper band.
  Constant rasters produce one full-coverage band with equal labels.
- Holes, multipart geometry, CRS, and Dask-backed input (materialized eagerly)
  are preserved.

See the [Sphinx documentation source](docs/index.md) for installation details,
full API semantics, and limitations. Contributor instructions are in
[CONTRIBUTING.md](CONTRIBUTING.md).
