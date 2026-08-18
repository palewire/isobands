Usage and API semantics
=======================

Quick start
-----------

The function accepts an in-memory ``xarray.DataArray`` and returns a
``geopandas.GeoDataFrame``:

.. code-block:: python

   import numpy as np
   import xarray as xr

   from isobands import isobands

   data = xr.DataArray(
       np.array([[0.0, 1.0, 2.0], [1.0, 2.0, 3.0], [2.0, 3.0, 4.0]]),
       dims=("y", "x"),
       coords={"x": [0.0, 1.0, 2.0], "y": [2.0, 1.0, 0.0]},
   )
   bands = isobands(data, levels=[1.5, 2.5], crs="EPSG:4326")

The returned columns are ``min_value``, ``max_value``, and ``geometry``.
Geometry and the result CRS are preserved by GeoPandas.
Disconnected or nodata-separated regions can produce multiple rows with the
same bounds; callers can dissolve them with ordinary GeoPandas operations when
one feature per band is required.

Band definitions
----------------

Exactly one of ``levels`` or ``interval`` is required.

* ``levels`` is a strictly increasing, finite sequence of interior thresholds.
  Values outside the finite valid raster range are ignored. The first and last
  bands are clipped to the valid raster minimum and maximum.
* ``interval`` is a positive finite number. Thresholds are integral multiples
  of that interval and are used only when they fall inside the valid range.
  Requests that would create more than 100,000 interior thresholds are rejected
  before allocation.
* A value exactly equal to a threshold belongs to the upper band.
* A constant valid raster returns one full-coverage band whose labels are equal.

Input data and coordinates
--------------------------

Input must be numeric and have exactly two nonsingleton dimensions. Singleton
dimensions may be squeezed first. Dask-backed arrays are materialized eagerly
while preparing the GDAL in-memory dataset.

Each spatial axis must be a regular, one-dimensional rectilinear coordinate.
Axis discovery checks CF ``axis`` and ``standard_name`` metadata before common
``x``/``y``, ``lon``/``lat``, and ``longitude``/``latitude`` names. Both
ascending and descending axes are supported. Curvilinear, irregular,
ambiguous, missing, or numerically nonfinite transforms fail with a clear
validation error.

Coordinate names alone never imply ``EPSG:4326`` or any other CRS.

CRS
---

CRS selection has this precedence:

1. the explicit ``crs=`` argument;
2. already-registered rioxarray CRS metadata;
3. recognized CF/grid-mapping metadata, ``spatial_ref``, ``crs_wkt``, or
   ``crs`` metadata.

If none is available, ``isobands`` raises an error explaining how to pass
``crs=``. It never guesses a CRS from coordinate names.

Missing data
-----------

An explicit finite ``nodata=`` value overrides metadata ``_FillValue`` and
``missing_value``. Without an explicit value, NaN and other nonfinite floating
cells are nodata. An all-nodata raster fails because no finite bands can be
created.

Implementation
--------------

Contour polygons are generated with GDAL ``ContourGenerateEx`` in polygon mode
using GDAL MEM raster and vector datasets. No intermediate disk files are
written. Holes and multipart geometry are retained.
