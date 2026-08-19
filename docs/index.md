# isobands

An easy way to make filled contour maps with Python.

`isobands` converts a regular two-dimensional [xarray](https://xarray.dev/)
`DataArray` into contoured polygons in a
[GeoPandas](https://geopandas.org/) `GeoDataFrame`.

```{raw} html
<div style="width: 100%; height: 720px;">
  <iframe
    src="global_temperature_animation.html"
    title="Global ERA5 daily high temperatures, August 16 through 22, 2020"
    loading="lazy"
    style="width: 100%; height: 100%; border: 0; display: block;"
  ></iframe>
</div>
```

## Installation

By default, `isobands` requires an installed, matching [`osgeo.gdal`](https://www.osgeo.org/projects/gdal/) Python binding. In a
Conda or system-managed environment that provides such a binding, you can
install `isobands` directly:

```console
pip install isobands
```

Lacking that, you can let pip install GDAL for you by specifying the GDAL version. The latest tested version is GDAL 3.13.2.

```console
pip install "isobands[gdal313]"
```

Installers for `gdal310`, `gdal311` and `gdal312` are also available.

## Quick start

Pass an in-memory `xarray.DataArray` and receive a `geopandas.GeoDataFrame`:

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

The `levels` input supplies the interior breakpoints, dividing the data into
bands at 1.5 and 2.5.

The result always has the stable `min_value`, `max_value`, and `geometry`
columns and a GeoPandas CRS.

The returned GeoDataFrame of the example above would look like so:

| min_value | max_value | geometry |
| ---: | ---: | --- |
| 0.0 | 1.5 | `MULTIPOLYGON (...)` |
| 1.5 | 2.5 | `MULTIPOLYGON (...)` |
| 2.5 | 4.0 | `MULTIPOLYGON (...)` |

## Equal interval breaks

You can use the `intervals` input to specify uniform threshold breaks. This example uses `interval=5` to create five-degree temperature
bands.

```python
import xarray as xr

import isobands

temperature = xr.open_dataarray("west-coast-daily-highs.nc")
bands = isobands.from_raster(temperature, interval=5, crs="EPSG:4326")
```

For this field, the returned GeoDataFrame begins like this:

| min_value | max_value | geometry |
| ---: | ---: | --- |
| 12.3 | 15.0 | `MULTIPOLYGON (...)` |
| 15.0 | 20.0 | `MULTIPOLYGON (...)` |
| 20.0 | 25.0 | `MULTIPOLYGON (...)` |

Set `offset` when equal-width bands need a nonzero starting point. For example,
`interval=5, offset=2.5` creates thresholds at 2.5, 7.5, 12.5, and so on.

The map shows high temperatures on August 16, 2020, when Death Valley
[recorded](https://www.nps.gov/deva/learn/news/record-heat-at-death-valley.htm) a record high of 54.4°C in Furnace Creek.

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

The `levels` input allows you to specify whatever threshold you like. This example uses the EPA's air quality risk categories for particulate matter.

```python
import xarray as xr

import isobands

pm25 = xr.open_dataarray("nyc-smoke-pm25.nc")
bands = isobands.from_raster(
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

The map shows [EPA AirData](https://www.epa.gov/outdoor-air-quality-data)
risk scores on June 7, 2023, when Canadian wildfire smoke blanketed the East Coast.

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

Pass a callable to `levels` to determine breaks based on the data. The function receives a one-dimensional array of valid values and should
return the interior thresholds. This can be useful for quintiles, natural breaks, Jenks breaks and other data-driven strategies.

```python
import numpy as np
import xarray as xr

import isobands


def quintiles(values):
    return np.quantile(values, [0.2, 0.4, 0.6, 0.8])


rainfall = xr.open_dataarray("harvey-daily-rainfall.nc")
bands = isobands.from_raster(rainfall, levels=quintiles, crs="EPSG:4326")
```

For this field, the returned GeoDataFrame begins like this:

| min_value | max_value | geometry |
| ---: | ---: | --- |
| 0.0 | 0.1 | `MULTIPOLYGON (...)` |
| 0.1 | 0.9 | `MULTIPOLYGON (...)` |
| 0.9 | 4.3 | `MULTIPOLYGON (...)` |

The map shows rainfall on August 27, 2017, as Hurricane Harvey stalled over Texas.

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

import isobands

temperature = xr.open_dataarray("iowa-land-surface-temperature.nc")
bands = isobands.from_raster(
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

The map shows land-surface temperatures captured by NASA satellites on August 12,
2020, two days after a historic derecho swept across Iowa. The no-data cells indicate pixels without valid data, typically due to cloud cover obscuring the satellite's sensors.

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
.. autofunction:: isobands.from_raster
```

## Links

- [Source code](https://github.com/palewire/isobands)
- [Issue tracker](https://github.com/palewire/isobands/issues)
- [Changelog](https://github.com/palewire/isobands/blob/main/CHANGELOG.md)
- [PyPI package](https://pypi.org/project/isobands/)

## About

Ben Welsh first released this module in August 2026 as a spinoff of the
[Reuters Climate Monitor](https://www.reuters.com/graphics/CLIMATE-AUTOMATED/MONITOR/akpeykqqapr/).
GitHub's Copilot, an AI-powered text generator, helped draft this documentation.
Map examples use [MapLibre](https://maplibre.org/),
[OpenFreeMap](https://openfreemap.org/), and
© [OpenStreetMap contributors](https://www.openstreetmap.org/copyright).
