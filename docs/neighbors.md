Neighboring tools
=================

``isobands`` focuses on one conversion: a regular in-memory xarray raster to
filled contour polygons. These neighboring projects solve adjacent problems:

* **GDAL** is the native geospatial engine used by ``isobands``. Its
  ``ContourGenerateEx`` implementation creates the polygons. GDAL 3.10.2 and
  3.12.2 are supported exact runtime baselines.
* **xarray** provides labeled N-dimensional arrays, coordinates, metadata, and
  lazy Dask-backed data. ``isobands`` accepts one two-dimensional
  ``DataArray`` and materializes it before calling GDAL.
* **GeoPandas** stores the returned polygons and CRS, and provides operations
  such as ``dissolve``, spatial joins, and file export.
* **Rasterio** is a useful choice for reading and writing raster files and
  managing affine transforms. Use it when the workflow starts with files;
  ``isobands`` itself uses GDAL's in-memory drivers.
* **xarray-spatial** provides raster analysis and visualization algorithms that
  operate directly on xarray objects. It can be a better fit when contour
  polygons are not the desired output or when a broader raster toolkit is
  needed.
* **Mapshaper** is a command-line tool for simplifying, repairing, and
  transforming vector data. It is complementary after exporting contour
  polygons, rather than a replacement for generating them from a raster.

Choose the tool that matches the representation and operation you need:
``isobands`` is deliberately not a general raster reader, raster analysis
library, or vector post-processing suite.
