Real-world NOAA/NCEP example
============================

The repository includes a compact, checked-in slice of the NOAA/NCEP
reanalysis air-temperature dataset. The fixture records its source URL,
dimensions, variable metadata, SHA-256 checksum
``c606b89c35970a2983b914b76df4adbb409003ef34aa7cfd7f582e41f307482b`` and
public-domain redistribution evidence in
``examples/data/air_temperature_time0.source.json``. It is the time-zero
``air`` slice from the pinned 25-by-53 source grid, in Kelvin.

Run the executable example from any working directory:

.. code-block:: console

   $ python /path/to/isobands/examples/air_temperature.py

The script resolves the fixture relative to ``__file__`` and does not download
data or write tracked files by default. It:

1. loads values, longitude, latitude, and metadata with NumPy;
2. constructs an xarray ``DataArray`` with the source's ``lat``/``lon`` axes;
3. calls ``isobands(data, levels=[240.0, 260.0, 280.0], crs="EPSG:4326")``;
4. checks the stable output schema, CRS, and Shapely validity; and
5. dissolves repeated components by ``min_value`` and ``max_value`` with
   GeoPandas.

The data has a regular rectilinear grid, so explicit ``EPSG:4326`` is
appropriate for this example. Coordinate names alone are not a CRS inference
rule. To regenerate the fixture after verifying the pinned source, use the
documented command in ``CONTRIBUTING.md``; normal runs of the example use only
the checked-in fixture and make no network request.
