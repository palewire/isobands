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
* Integer samples must be between ``-2**53`` and ``2**53`` inclusive. Values
  outside Float64's exact consecutive-integer range are rejected before GDAL
  conversion.
* Missing values must leave at least one finite valid cell. Explicit finite
  ``nodata`` takes precedence over ``_FillValue`` and ``missing_value``.
* GDAL **3.10.2** and **3.12.2** are supported exact runtime baselines. Install
  matching system GDAL development files and select the corresponding
  ``gdal310`` or ``gdal312`` extra; pip alone cannot provide the system library.

The stable convenience promise covers the documented ``isobands()`` API and its
``min_value``, ``max_value``, and ``geometry`` output. The separate
``gdal_fixed_level_polygons()`` API preserves raw fixed-level GDAL feature
labels, order, and geometry without post-processing; it is not an adapter to
the stable convenience schema. Neither API claims support for grids, platforms,
or numeric ranges outside these constraints.
