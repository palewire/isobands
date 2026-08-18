Limitations
===========

``isobands`` is an alpha package. Keep these constraints in mind:

* Only numeric ``xarray.DataArray`` inputs with two nonsingleton dimensions are
  supported. Singleton dimensions can be removed with ``squeeze``.
* Coordinates must describe regular, one-dimensional rectilinear axes.
  Curvilinear grids, irregular spacing, ambiguous axis names or metadata, and
  missing coordinates are rejected. Coordinate spacing and derived pixel-corner
  transforms must also remain finite.
* A CRS is not inferred from coordinate names. Supply ``crs=`` or attach
  recognized CRS metadata when the output must be referenced spatially.
* Dask arrays are computed eagerly before GDAL processing; very large arrays
  therefore require enough memory for materialization and GDAL's in-memory
  datasets.
* ``levels`` must be strictly increasing and finite. Thresholds outside the
  valid data range are ignored, so they do not create empty outer bands.
* Interval mode is limited to 100,000 interior thresholds. Use a larger
  interval when the requested value range would exceed that safety limit.
* Data extrema and contour thresholds must remain distinct after safe linear
  conditioning for GDAL. Rescale data whose values span too much of the
  floating-point range to preserve the requested bands.
* Missing values must leave at least one finite valid cell. Explicit finite
  ``nodata`` takes precedence over ``_FillValue`` and ``missing_value``.
* GDAL 3.12.2 is required at runtime. Install matching system GDAL before
  installing the Python package; pip alone cannot provide the system library.

Production Sphinx hosting is intentionally deferred. Until it is configured,
the PyPI Documentation link points to the repository README.
