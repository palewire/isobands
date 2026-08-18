# Changelog

All notable changes to this project are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

### Changed

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
- Publish stable package metadata and retain the Production/Stable classifier
  before the release candidate.
- Add Windows conda-forge smoke validation and document the exact GDAL 3.12.2
  requirement.

### Fixed

- Preserve thin nodata-separated components and their GDAL-interpolated
  threshold geometry.

## [0.1.0a1] - 2026-08-18

### Added

- Alpha `isobands` API for converting regular two-dimensional xarray rasters
  into GDAL-generated filled contour GeoDataFrames, with explicit levels or
  interval thresholds, CRS metadata handling, nodata support, and preserved
  holes and multipart geometry.
- GDAL 3.12.2 prerequisite documentation, strict Sphinx API documentation,
  and Trusted Publishing release plumbing.
