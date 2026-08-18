# isobands

An easy way to make filled contour maps with Python.

`isobands` converts a regular two-dimensional [xarray](https://xarray.dev/)
`DataArray` into filled contour polygons backed by a
[GeoPandas](https://geopandas.org/) `GeoDataFrame`.

## Installation

`isobands` requires an installed, matching `osgeo.gdal` Python binding. In a
Conda or system-managed environment that already provides a tested binding,
install `isobands` directly:

```console
$ pip install isobands
```

For a pip-managed binding, install matching native GDAL 3.13.2 development
files, then use the recommended newest tested and installable extra:

```console
$ pip install "isobands[gdal313]"
```

The tested exact baselines are GDAL 3.10.2, 3.11.5, 3.12.2, and 3.13.2. GDAL
3.10.2 and 3.11.5 remain advanced compatibility choices through the `gdal310`
and `gdal311` extras. GDAL 3.13.3 is not tested or supported.
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

The `levels` input supplies the interior breakpoints, dividing the data into
bands at 1.5 and 2.5.

For the small grid above, the returned GeoDataFrame begins like this:

| min_value | max_value | geometry |
| ---: | ---: | --- |
| 0.0 | 1.5 | `MULTIPOLYGON (...)` |
| 1.5 | 2.5 | `MULTIPOLYGON (...)` |
| 2.5 | 4.0 | `MULTIPOLYGON (...)` |

## Equal interval breaks

This example uses `interval=5` to create equal-width five-degree temperature
bands and
`crs="EPSG:4326"` to identify the input's longitude-latitude coordinates.

```python
import xarray as xr

from isobands import isobands

temperature = xr.open_dataarray("west-coast-daily-highs.nc")
bands = isobands(temperature, interval=5, crs="EPSG:4326")
```

Set `offset` when equal-width bands need a nonzero alignment. For example,
`interval=5, offset=2.5` creates thresholds at 2.5, 7.5, 12.5, and so on.

For this field, the returned GeoDataFrame begins like this:

| min_value | max_value | geometry |
| ---: | ---: | --- |
| 12.3 | 15.0 | `MULTIPOLYGON (...)` |
| 15.0 | 20.0 | `MULTIPOLYGON (...)` |
| 20.0 | 25.0 | `MULTIPOLYGON (...)` |

The map shows ERA5 daily maximum two-meter temperatures across the U.S. West
Coast on August 16, 2020, when Furnace Creek, California, in Death Valley
recorded 54.4°C, as documented by the
[National Park Service](https://www.nps.gov/deva/learn/news/record-heat-at-death-valley.htm).

```{raw} html
<div style="width: 100%; height: 466px;">
  <iframe
    src="era5_maplibre.html"
    title="ERA5 daily high temperatures on August 16, 2020"
    loading="lazy"
    style="width: 100%; height: 100%; border: 0; display: block;"
  ></iframe>
</div>
```

## Threshold breaks

The `levels` input can also use meaningful external thresholds instead of equal
intervals. This example uses the U.S. EPA's PM2.5 health-category boundaries.

```python
import xarray as xr

from isobands import isobands

pm25 = xr.open_dataarray("nyc-smoke-pm25.nc")
bands = isobands(
    pm25,
    levels=[12.0, 35.4, 55.4, 125.4, 225.4],
    crs="EPSG:4326",
)
```

For this field, the returned GeoDataFrame begins like this:

| min_value | max_value | geometry |
| ---: | ---: | --- |
| 1.4 | 12.0 | `MULTIPOLYGON (...)` |
| 12.0 | 35.4 | `MULTIPOLYGON (...)` |
| 35.4 | 55.4 | `MULTIPOLYGON (...)` |

The map interpolates [EPA AirData](https://www.epa.gov/outdoor-air-quality-data)
daily mean PM2.5 readings across the eastern United States on June 7, 2023,
when Canadian wildfire smoke blanketed the region.

```{raw} html
<div style="width: 100%; height: 466px;">
  <iframe
    src="pm25_maplibre.html"
    title="New York City PM2.5 during Canadian wildfire smoke"
    loading="lazy"
    style="width: 100%; height: 100%; border: 0; display: block;"
  ></iframe>
</div>
```

## Data-derived breaks

Pass a callable to `levels` when the data distribution should determine the
breaks. The callable receives a one-dimensional array of valid values and
returns the interior thresholds.

```python
import numpy as np
import xarray as xr

from isobands import isobands


def quintiles(values):
    return np.quantile(values, [0.2, 0.4, 0.6, 0.8])


rainfall = xr.open_dataarray("harvey-daily-rainfall.nc")
bands = isobands(rainfall, levels=quintiles, crs="EPSG:4326")
```

For this field, the returned GeoDataFrame begins like this:

| min_value | max_value | geometry |
| ---: | ---: | --- |
| 0.0 | 0.1 | `MULTIPOLYGON (...)` |
| 0.1 | 0.9 | `MULTIPOLYGON (...)` |
| 0.9 | 4.3 | `MULTIPOLYGON (...)` |

The map shows ERA5 daily rainfall across Texas and the surrounding Gulf Coast
on August 27, 2017, as Hurricane Harvey stalled over the region. Rainfall
totals are strongly skewed: quintiles make relative variation visible across
the field, but do not represent externally defined severity categories.

```{raw} html
<div style="width: 100%; height: 466px;">
  <iframe
    src="harvey_rainfall_maplibre.html"
    title="Hurricane Harvey rainfall quintiles"
    loading="lazy"
    style="width: 100%; height: 100%; border: 0; display: block;"
  ></iframe>
</div>
```

## No-data cells

Use `nodata` to leave unavailable cells out of the contours instead of treating
them as measured values.

```python
import xarray as xr

from isobands import isobands

temperature = xr.open_dataarray("iowa-land-surface-temperature.nc")
bands = isobands(
    temperature,
    levels=[20, 25, 30, 35],
    nodata=-9999,
    crs="EPSG:4326",
)
```

For this field, the returned GeoDataFrame begins like this:

| min_value | max_value | geometry |
| ---: | ---: | --- |
| 12.1 | 20.0 | `MULTIPOLYGON (...)` |
| 20.0 | 25.0 | `MULTIPOLYGON (...)` |
| 25.0 | 30.0 | `MULTIPOLYGON (...)` |

The map shows NASA MODIS land-surface temperatures across Iowa on August 12,
2020, two days after the derecho. The no-data cells mark pixels without a valid
satellite temperature retrieval, commonly because of clouds or quality flags.

```{raw} html
<div style="width: 100%; height: 466px;">
  <iframe
    src="iowa_temperature_maplibre.html"
    title="Iowa land-surface temperature after the 2020 derecho"
    loading="lazy"
    style="width: 100%; height: 100%; border: 0; display: block;"
  ></iframe>
</div>
```

## API reference

```{eval-rst}
.. autofunction:: isobands.isobands
```

```{eval-rst}
.. autofunction:: isobands.gdal_fixed_level_polygons
```

## Raw GDAL fixed-level compatibility

`gdal_fixed_level_polygons()` is a separate low-level API for workflows that
need native [`gdal_contour -p -fl`](https://gdal.org/programs/gdal_contour.html)
behavior instead of the stable `isobands()` convenience contract:

```python
from isobands import gdal_fixed_level_polygons

native = gdal_fixed_level_polygons(
    data,
    levels=[0.0, 1.0, 2.0, 3.0, 4.0],
    crs="EPSG:4326",
)
print(native[["ID", "floor", "ceil", "geometry"]])
```

Every supplied level, including endpoint and out-of-range levels, is retained
in order. The result uses GDAL's `ID`, `floor`, `ceil`, and `geometry` schema
and feature order. It deliberately does **not** clip labels to data extrema,
create missing outer bands, split or dissolve features, repair topology, or
reorder/canonicalize geometry.

This function uses GDAL's in-process MEM raster driver and virtual `/vsimem`
GeoJSON output driver; it does not invoke `gdal_contour` or create temporary
files. It applies the command's six-decimal fixed-level serialization, and its
fields, order, and WKB match direct command-line output on the supported GDAL
3.10.2, 3.11.5, 3.12.2, and 3.13.2 baselines. The regular-grid validation and
finite nodata conversion still apply before GDAL receives the raster.

## Links

- [Source code](https://github.com/palewire/isobands)
- [Issue tracker](https://github.com/palewire/isobands/issues)
- [Changelog](https://github.com/palewire/isobands/blob/main/CHANGELOG.md)
- [PyPI package](https://pypi.org/project/isobands/)

## About

Ben Welsh first released this module in August 2026 as an spinoff of the
[Reuters Climate Monitor](https://www.reuters.com/graphics/CLIMATE-AUTOMATED/MONITOR/akpeykqqapr/).
GitHub's Copilot, an AI-powered text generator, helped draft this documentation.
Map examples use [MapLibre](https://maplibre.org/),
[OpenFreeMap](https://openfreemap.org/), and
© [OpenStreetMap contributors](https://www.openstreetmap.org/copyright).
