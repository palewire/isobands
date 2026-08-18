# isobands

`isobands` converts a regular two-dimensional [xarray](https://xarray.dev/)
`DataArray` into filled contour polygons backed by a
[GeoPandas](https://geopandas.org/) `GeoDataFrame`. It uses GDAL's in-memory
raster and vector drivers, so a normal call does not create intermediate files.

```{contents} Contents
:local:
:depth: 2
```

---

## Installation

GDAL **3.12.2** and its matching development headers are required. The PyPI
`GDAL` distribution is source-only; `pip` cannot install the system library.

**Linux** — install the exact 3.12.2 runtime and development package from your
distribution's repository or build GDAL 3.12.2 from source:

```console
$ gdal-config --version
3.12.2
$ pip install isobands
```

If multiple GDAL installations exist, put the matching `gdal-config` first on
`PATH` or set `GDAL_CONFIG` to its absolute path.

**macOS** — Homebrew users can install GDAL and then the package:

```console
$ brew install gdal
$ "$(brew --prefix gdal)/bin/gdal-config" --version
3.12.2
$ pip install isobands
```

Ensure the active Python architecture (for example, arm64) matches the GDAL
libraries. Reinstalling the Python binding after correcting the prefix is safer
than mixing cached build artifacts.

**Windows** — use a conda-forge environment so the native GDAL runtime,
headers, and libraries are resolved as one compatible set:

```console
conda create -n isobands python=3.13
conda activate isobands
conda install -c conda-forge gdal=3.12.2
pip install isobands
```

**Contributor setup** — clone the repository and install its locked dependency
groups:

```console
$ make install
```

---

## Quick start

Pass an in-memory `xarray.DataArray` and receive a `geopandas.GeoDataFrame`:

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
columns and a GeoPandas CRS.

### Real-world example

The repository includes a runnable NOAA/NCEP air-temperature example using a
pinned fixture in `examples/data/`:

```console
$ python examples/air_temperature.py
```

The script loads a 25×53 Kelvin slice, calls
`isobands(data, levels=[240.0, 260.0, 280.0], crs="EPSG:4326")`, checks the
stable schema, CRS, and Shapely validity, and dissolves repeated components.

---

## API reference

```{eval-rst}
.. autofunction:: isobands.isobands
```

### Dissolving repeated bands

GDAL can return separate polygons for disconnected valid regions. Rows with the
same `min_value` and `max_value` are therefore valid and expected. Use
GeoPandas when one feature per interval is useful:

```python
dissolved = bands.dissolve(by=["min_value", "max_value"], as_index=False)
```

---

## Behavior and limits

### Band definitions

Exactly one of `levels` or `interval` is required.

- `levels` is a nonempty, strictly increasing, finite sequence of interior
  thresholds. Thresholds outside the finite valid raster range are ignored.
  The first band starts at the valid minimum and the last ends at the valid
  maximum.
- `interval` is a positive finite number. Interior thresholds are integral
  multiples of the interval that fall strictly inside the valid range.
  Requests producing more than 100,000 interior thresholds fail before
  allocation.
- A value exactly equal to a threshold belongs to the upper band
  (lower-inclusive, upper-exclusive convention for interior boundaries).
- A constant valid raster produces one full-coverage band with equal
  `min_value` and `max_value` labels.
- Empty outer bands are not emitted.

### Input requirements

- Input must be a numeric `xarray.DataArray` with exactly two nonsingleton
  dimensions. Squeeze singleton dimensions first.
- Each spatial axis must be a regular, one-dimensional rectilinear coordinate.
  Axis discovery checks CF `axis` and `standard_name` metadata before common
  `x`/`y`, `lon`/`lat`, and `longitude`/`latitude` names. Ascending and
  descending axes are supported.
- Curvilinear, irregular, ambiguous, missing, or nonfinite coordinate
  transforms are rejected.
- Dask-backed arrays are materialized eagerly before GDAL processing.

### CRS selection

CRS selection uses this precedence:

1. the explicit `crs=` argument;
2. already-registered rioxarray CRS metadata;
3. recognized CF/grid-mapping metadata, `spatial_ref`, `crs_wkt`, or `crs`.

If no CRS is available, `isobands` raises an error explaining how to pass
`crs=`. Coordinate names alone never imply `EPSG:4326` or another CRS.

### Missing data

An explicit finite `nodata=` value overrides metadata `_FillValue` and
`missing_value`. Without an explicit value, NaN and other nonfinite floating
cells are nodata. An all-nodata raster fails.

### Numeric and grid limits

- Extremely wide dynamic ranges can make extrema and thresholds
  indistinguishable in floating-point arithmetic. Rescale values when
  validation reports that safe conditioning is impossible.
- Integer samples must remain within `-2**53` through `2**53` so GDAL's Float64
  raster can represent them exactly; values outside that range are rejected.
- Interval mode is limited to 100,000 interior thresholds.
- Only regular rectilinear two-dimensional grids are supported.

### Error guidance

Validation errors are `ValueError` instances. Check, in order:

1. the input is numeric and has two nonsingleton dimensions;
2. both coordinates are one-dimensional, regular, and finite;
3. exactly one band definition is supplied and levels are strictly increasing
   and finite;
4. at least one finite cell remains after applying nodata;
5. a CRS is supplied explicitly or present in recognized metadata.

---

## Neighboring tools

`isobands` focuses on one conversion: a regular in-memory xarray raster to
filled contour polygons. These tools solve adjacent problems:

- **GDAL** is the native geospatial engine. Its `ContourGenerateEx`
  implementation creates the polygons; GDAL 3.12.2 is an exact runtime
  prerequisite.
- **xarray** provides labeled N-dimensional arrays, coordinates, metadata, and
  lazy Dask-backed data.
- **GeoPandas** stores the returned polygons and CRS, and provides `dissolve`,
  spatial joins, and file export.
- **Rasterio** is a useful choice for reading and writing raster files and
  managing affine transforms. Use it when the workflow starts with files.
- **xarray-spatial** provides raster analysis algorithms that operate directly
  on xarray objects. It may be a better fit when contour polygons are not the
  desired output.
- **Mapshaper** is a command-line tool for simplifying and transforming vector
  data; it is complementary after exporting contour polygons.

---

## Links

- [Source code](https://github.com/palewire/isobands)
- [Issue tracker](https://github.com/palewire/isobands/issues)
- [Changelog](https://github.com/palewire/isobands/blob/main/CHANGELOG.md)
- [PyPI package](https://pypi.org/project/isobands/)
- [Contributing guide](https://github.com/palewire/isobands/blob/main/CONTRIBUTING.md)
