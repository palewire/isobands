# Examples

Run the real-world NOAA/NCEP example from any working directory:

```sh
python /path/to/isobands/examples/air_temperature.py
```

It reads `data/air_temperature_time0.npz`, calls `isobands` with Kelvin
thresholds and explicit `EPSG:4326`, validates the output, and demonstrates a
GeoPandas dissolve. It does not write files by default. The adjacent
`.source.json` records the pinned source checksum and fixture provenance.
