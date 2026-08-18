Usage and API semantics
=======================

Quickstart
----------

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

The stable output columns are exactly ``min_value``, ``max_value``, and
``geometry``. The result is a GeoPandas ``GeoDataFrame`` with the selected CRS.
The geometry is polygonal and may contain holes or multipart components.

Band definitions
----------------

Exactly one of ``levels`` or ``interval`` is required.

* ``levels`` is a nonempty, strictly increasing, finite sequence of interior
  thresholds. Thresholds outside the finite valid raster range are ignored.
  The first band starts at the valid minimum and the last ends at the valid
  maximum.
* ``interval`` is a positive finite number. Interior thresholds are integral
  multiples of the interval that fall strictly inside the valid range.
  Requests producing more than 100,000 interior thresholds fail before
  allocation.
* A value exactly equal to a threshold belongs to the upper band. This is a
  lower-inclusive, upper-exclusive convention for interior boundaries.
* A constant valid raster produces one full-coverage band with equal
  ``min_value`` and ``max_value`` labels.
* Empty outer bands are not emitted. For example, levels below or above all
  valid values are ignored; if every requested level is outside the range,
  one extrema-to-extrema band remains.

Disconnected and repeated bands
--------------------------------

GDAL can return separate polygons for disconnected valid regions. Rows with the
same ``min_value`` and ``max_value`` are therefore valid and expected; these
are repeated bands, not duplicate errors. Use ordinary GeoPandas operations
when one feature per value interval is useful:

.. code-block:: python

   dissolved = bands.dissolve(by=["min_value", "max_value"], as_index=False)

Nodata-separated components remain separate, and nodata cells are not covered
by any returned polygon. Holes and multipart geometry are retained.

Input grid and eager behavior
-----------------------------

Input must be numeric and have exactly two nonsingleton dimensions. Squeeze
singleton dimensions first. Dask-backed arrays are materialized eagerly while
preparing GDAL's in-memory dataset, so the complete numeric array must fit in
memory.

Each spatial axis must be a regular, one-dimensional rectilinear coordinate.
Axis discovery checks CF ``axis`` and ``standard_name`` metadata before common
``x``/``y``, ``lon``/``lat``, and ``longitude``/``latitude`` names. Ascending and
descending axes are supported. Curvilinear, irregular, ambiguous, missing, or
nonfinite coordinate transforms fail validation.

CRS precedence
--------------

CRS selection has this precedence:

1. the explicit ``crs=`` argument;
2. already-registered rioxarray CRS metadata;
3. recognized CF/grid-mapping metadata, ``spatial_ref``, ``crs_wkt``, or
   ``crs`` metadata.

If no CRS is available, ``isobands`` raises an error explaining how to pass
``crs=``. Coordinate names alone never imply ``EPSG:4326`` or another CRS.

Missing data
------------

An explicit finite ``nodata=`` value overrides metadata ``_FillValue`` and
``missing_value``. Without an explicit value, NaN and other nonfinite floating
cells are nodata. An all-nodata raster fails because no finite extrema or bands
can be created.

Error guidance
--------------

Validation errors are ``ValueError`` instances with the offending requirement
in their message. Check, in order:

1. that the input is numeric and has two nonsingleton dimensions;
2. that both coordinates are one-dimensional, regular, and finite;
3. that exactly one band definition is supplied and levels are strictly
   increasing and finite;
4. that at least one finite cell remains after applying nodata;
5. that a CRS is supplied explicitly or present in recognized metadata.

Numeric range and grid limits
-----------------------------

GDAL receives a finite, conditioned numeric raster. Extremely wide dynamic
ranges can make extrema and thresholds indistinguishable in floating-point
arithmetic; rescale values before calling the function when validation reports
that safe conditioning is impossible. Integer samples must remain within
``-2**53`` through ``2**53`` so GDAL's Float64 raster can represent them
exactly; values outside that range are rejected rather than rounded. Interval
mode has the 100,000-threshold safety limit. Only regular rectilinear
two-dimensional grids are supported; this documentation does not promise
support for curvilinear, irregular, or other grids.

Implementation
--------------

Contour polygons are generated with GDAL ``ContourGenerateEx`` in polygon mode
using GDAL MEM raster and vector datasets. No intermediate disk files are
written by the function.
