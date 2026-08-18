# Benchmarks

Run the compact checked-in fixture correctness and timing smoke test:

```sh
make benchmark-smoke
```

Run the full comparison:

```sh
make benchmark
```

The full run downloads `air_temperature.nc` to the platform benchmark cache
(`ISOBANDS_BENCHMARK_CACHE` overrides it), verifies its SHA-256, selects
`air.isel(time=0)`, and **interpolates that native 25x53 slice** to the
configured regular grid before timed work. The default full grid is 500x1000;
it is not a native upstream resolution. Use `BENCHMARK_GRID=250x500`,
`BENCHMARK_REPEATS=10`, or `BENCHMARK_WARMUPS=2` to configure a run.

The harness validates CRS, labels, bounds, valid geometry, and polygon coverage
between `xarray -> from_raster -> GeoDataFrame` and the equivalent file-based
`xarray -> GeoTIFF -> GDAL polygon contour -> GeoJSON -> GeoPandas` path before
warming or timing either implementation. It writes JSON and Markdown reports
under `benchmarks/results/` by default. Reports contain environment, dependency,
source, grid, level, repeat, stage timing, and peak-memory availability data.
There are intentionally no performance pass/fail thresholds.

`scipy` is a benchmark-only dependency because xarray uses it to read the
NetCDF source. The smoke fixture is
`examples/data/air_temperature_time0.npz`. The file-based baseline invokes the
installed `gdal_contour` command, so GDAL's executable directory must be on
`PATH`. Benchmark cache and transient contour files remain outside tracked
source; only `benchmarks/results/reference.{json,md}` is tracked. The reports
show median, mean, minimum, and maximum stage timings, with median totals in
the comparison table.
