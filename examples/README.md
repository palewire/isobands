# Examples

Run the real-world NOAA/NCEP example from any working directory:

```sh
python /path/to/isobands/examples/air_temperature.py
```

It reads `data/air_temperature_time0.npz`, calls `isobands` with Kelvin
thresholds and explicit `EPSG:4326`, validates the output, and demonstrates a
GeoPandas dissolve. It does not write files by default. The adjacent
`.source.json` records the pinned source checksum and fixture provenance.

## ERA5 MapLibre contour map

Configure a [Copernicus Climate Data Store API key](https://cds.climate.copernicus.eu/how-to-api),
then download ERA5 daily maximum temperatures and create a MapLibre-ready
GeoJSON file:

```sh
uv run --with cdsapi --with h5netcdf --with h5py python examples/era5_maplibre.py
python -m http.server --directory examples 8000
```

Open <http://localhost:8000/era5_maplibre.html>. The script writes its
downloaded NetCDF file and generated GeoJSON to the ignored `examples/output/`
directory.

## PM2.5 MapLibre contour map

Download EPA monitor data, interpolate daily PM2.5 readings around New York
City, and create a MapLibre-ready GeoJSON file:

```sh
uv run python examples/pm25_maplibre.py
python -m http.server --directory examples 8000
```

Open <http://localhost:8000/pm25_maplibre.html>. The script writes its
downloaded EPA archive and generated GeoJSON to `examples/output/`.

## Iowa land-surface-temperature MapLibre contour map

Download NASA MODIS land-surface temperatures for Iowa after the August 2020
derecho and create a MapLibre-ready GeoJSON file:

```sh
uv run python examples/iowa_temperature_maplibre.py
python -m http.server --directory examples 8000
```

Open <http://localhost:8000/iowa_temperature_maplibre.html>. The script writes
the generated GeoJSON to `examples/output/`.
