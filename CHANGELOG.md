# Changelog

All notable changes to this project are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Fixed

- Normalize GDAL 3.13.2 self-touching interior rings: a ring that revisits an
  exact vertex (``Ring Self-intersection`` in shapely) is now split into its
  simple sub-loops using the existing repeated-vertex splitter, with each
  sub-loop classified as a retained hole or a promoted outside polygon.
  Ambiguous or malformed invalid interior rings continue to raise
  ``RuntimeError``.  Resolves a regression in ERA5 weighted-anomaly contour
  jobs under conda-forge GDAL 3.13.2.

### Changed

- Document that the GDAL extras compile from source and require the matching
  native GDAL library and headers, name the `gdal-config` failure signature
  with macOS and Debian/Ubuntu pointers, and say so in the missing-bindings
  error message.

### Added

- Add a simplified, animated global ERA5 temperature MapLibre example.
- Allow ``levels=`` to accept a callable that derives validated contour
  thresholds from the raster's valid values.
- Add an ``offset`` option for aligning interval-derived contour thresholds to
  a nonzero origin.
- Add a MapLibre example that derives Hurricane Harvey rainfall bands from
  callable quintile levels.
- Add tested exact GDAL 3.11.5 and 3.13.2 binding extras and CI full-suite
  lanes.

### Changed

- Before the first stable release, rename the high-level public function from
  ``isobands()`` to ``from_raster()``. This deliberate breaking change retains
  its two-dimensional xarray input, band-definition validation, finite-band
  behavior, CRS and nodata handling, and
  ``min_value``/``max_value``/``geometry`` GeoDataFrame schema.
- Recommend the tested GDAL 3.13.2 pip extra while documenting installation
  with a pre-existing matching GDAL Python binding.
- Replace the Iowa snow-cover map with a continuous MODIS land-surface-
  temperature contour example that preserves unavailable satellite pixels.
### Fixed

### Removed

- Remove the temporary pre-release native fixed-level compatibility API. The
  package root now exposes only ``from_raster()`` as its runtime public
  function.

### Security

## [0.2.0] - 2026-08-18

### Added

- A MapLibre example that downloads ERA5 daily high temperatures, creates
  filled isobands, and exports colored GeoJSON for a simple interactive map.
- A MapLibre example that turns EPA PM2.5 monitor readings into health-category
  contour bands during New York City's June 2023 wildfire smoke event.
- A MapLibre example that uses missing cells to preserve unavailable areas in
  NASA MODIS snow-cover contour bands across Iowa.

### Changed

- Support exact GDAL 3.10.2 and 3.12.2 baselines with explicit binding
  selection, and cover both baselines in CI.

### Fixed

### Removed

### Security

## [0.1.0] - 2026-08-18

### Added

- Real-world NOAA/NCEP air-temperature fixture and a runnable GeoPandas
  example, with checksum and source metadata.
- Benchmark smoke/full tooling and an informational reference result covering
  the in-memory and file-based workflows.
- Hosted Sphinx documentation and deployment infrastructure, including
  platform installation guidance and neighboring-tool notes.

### Changed

- Freeze the stable single-function API and
  `min_value`/`max_value`/`geometry` output contract.
- Publish stable package metadata and retain the Production/Stable classifier.
- Add Windows conda-forge smoke validation and document the exact GDAL 3.12.2
  requirement.

### Fixed

- Preserve thin nodata-separated components and their GDAL-interpolated
  threshold geometry.
- Preserve positive-area contour loops while omitting GDAL's zero-area ring
  artifacts for valid nodata masks.
- Reject integers outside GDAL Float64's exact consecutive range instead of
  silently collapsing distinct values.

## [0.1.0a1] - 2026-08-18

### Added

- Alpha `isobands` API for converting regular two-dimensional xarray rasters
  into GDAL-generated filled contour GeoDataFrames, with explicit levels or
  interval thresholds, CRS metadata handling, nodata support, and preserved
  holes and multipart geometry.
- GDAL 3.12.2 prerequisite documentation, strict Sphinx API documentation,
  and Trusted Publishing release plumbing.
