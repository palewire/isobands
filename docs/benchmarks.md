Benchmark reference
===================

The checked-in reference result is one informational comparison, not a
guarantee or a CI threshold. It used the pinned NOAA/NCEP source checksum
``c606b89c35970a2983b914b76df4adbb409003ef34aa7cfd7f582e41f307482b``, selected
time zero, interpolated the native 25-by-53 slice to a 500-by-1000 regular
grid **outside the timed work**, and used seven Kelvin levels
``[240, 250, 260, 270, 280, 290, 300]``.

The run used five repeats on macOS arm64 with 10 CPUs, Python 3.13.2, and GDAL
3.12.2. Peak memory was unavailable because the harness has no isolated,
cross-platform native RSS sampler.

.. list-table::
   :header-rows: 1

   * - Workflow
     - Median total
   * - xarray → ``isobands`` → GeoDataFrame
     - 0.032069 s
   * - xarray → GeoTIFF → ``gdal_contour`` subprocess → GeoPandas
     - 0.238969 s

For this run, the file workflow was approximately 7.45x the end-to-end time
of the in-memory workflow. Its median stages were GeoTIFF serialization
0.002728 s, the ``gdal_contour`` subprocess 0.219598 s, and GeoPandas file
read 0.016751 s. The comparison does **not** show that the contour algorithm
itself is faster: saved serialization, subprocess startup, and rereading
overhead drive the difference.

The benchmark harness validates labels, bounds, CRS, geometry validity, and
coverage before timing. The repository's ``benchmarks/README.md`` contains the
commands, configuration, and report details. The 500-by-1000 grid in this
reference is an interpolated benchmark grid, not a claim about native NOAA
resolution.
