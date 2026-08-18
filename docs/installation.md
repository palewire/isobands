Installation
============

System GDAL prerequisite
------------------------

The runtime depends on **GDAL 3.12.2**. The PyPI ``GDAL`` package is
source-only, so it must compile against matching system GDAL headers and
libraries. ``pip`` alone does not install that system prerequisite.

On Unix-like systems, install GDAL 3.12.2 (including its development headers)
with the operating system package manager or build it from source. Before
installing this package, verify the development installation:

.. code-block:: console

   $ gdal-config --version
   3.12.2

The version must be exactly ``3.12.2``. If ``gdal-config`` is not on ``PATH``,
set ``GDAL_CONFIG`` to the matching executable when installing or using the
project.

On Windows, conda-forge is recommended because it supplies the native GDAL
libraries and headers:

.. code-block:: console

   conda install -c conda-forge gdal=3.12.2

Verify that the environment provides GDAL 3.12.2, then install ``isobands``:

.. code-block:: console

   pip install isobands

Contributor setup
-----------------

After installing matching system GDAL, clone the repository and install its
locked development, test, notebook, and documentation groups:

.. code-block:: console

   make install

The ``make`` targets set ``UV_NO_ENV_FILE=1`` and check ``gdal-config`` before
syncing dependencies. To install only documentation dependencies, use
``make install-docs``.
