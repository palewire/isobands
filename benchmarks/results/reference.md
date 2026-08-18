# isobands benchmark

- Source: `https://github.com/pydata/xarray-data/raw/master/air_temperature.nc` (`c606b89c35970a2983b914b76df4adbb409003ef34aa7cfd7f582e41f307482b`)
- Grid: `[500, 1000]`; interpolated: `True`
- Levels: `[240.0, 250.0, 260.0, 270.0, 280.0, 290.0, 300.0]`; repeats: `5`
- GDAL: `3.12.2`; isobands: `0.1.0a1.post1.dev6+g8fa45c558.d20260818`
- Peak memory: unavailable (no isolated cross-platform native RSS sampler).

| Path | Median total seconds | Stages (median; mean/min/max seconds) |
| --- | ---: | --- |
| xarray_to_from_raster_to_geodataframe | 0.032069 | from_raster=0.032069; 0.032216/0.031960/0.032751 |
| xarray_to_geotiff_to_gdal_contour_to_geopandas | 0.238969 | xarray_to_geotiff=0.002728; 0.002824/0.002507/0.003140, gdal_contour_subprocess=0.219598; 0.221966/0.216482/0.231197, geopandas_file_read=0.016751; 0.016695/0.016475/0.016762 |
