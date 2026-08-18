Limitations
===========

The stable API is intentionally narrow:

* Only numeric ``xarray.DataArray`` inputs with two nonsingleton dimensions are
  supported. Singleton dimensions can be removed with ``squeeze``.
* Coordinates must describe regular, one-dimensional rectilinear axes.
  Curvilinear, irregular spacing, ambiguous axis metadata, missing coordinates,
  and nonfinite transforms are rejected.
* A CRS is not inferred from coordinate names. Supply ``crs=`` or attach
  recognized CRS metadata.
* Dask arrays are computed eagerly before GDAL processing. Large arrays require
  enough memory for materialization and GDAL's in-memory datasets.
* ``levels`` must be strictly increasing and finite. Thresholds outside the
  valid range are ignored, and outer labels use finite valid extrema.
* Interval mode is limited to 100,000 interior thresholds. Use a larger
  interval for a wider value range.
* Data extrema and thresholds must remain distinguishable after safe
  floating-point conditioning. Rescale data whose values span too much of the
  numeric range.
* Missing values must leave at least one finite valid cell. Explicit finite
  ``nodata`` takes precedence over ``_FillValue`` and ``missing_value``.
* GDAL **3.12.2** is required at runtime. Install matching system GDAL
  development files before installing the Python package; pip alone cannot
  provide the system library.

The compatibility promise covers the documented ``isobands()`` API and its
``min_value``, ``max_value``, and ``geometry`` output. It does not claim
support for grids, platforms, or numeric ranges outside these constraints.
