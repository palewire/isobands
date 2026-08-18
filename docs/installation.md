Installation
============

GDAL prerequisite
-----------------

The runtime supports the exact **GDAL 3.10.2** and **GDAL 3.12.2** baselines,
including matching system development headers and libraries. The PyPI
``GDAL`` distribution is source-only: it compiles Python bindings against the
system installation. Select the matching ``isobands`` extra; do not mix
headers, libraries, or Python bindings from different GDAL releases.

Linux
~~~~~

Install a supported GDAL runtime and development package from your
distribution's supported repository, or build it from source. Package names
vary by distribution; the important distinction is the runtime package and its
development package (headers, ``gdal-config``, and linkable libraries). Then
verify the selected development installation and install its matching extra:

.. code-block:: console

   $ gdal-config --version
   3.10.2
   $ python -m pip install "isobands[gdal310]"

If multiple GDAL installations exist, put the matching ``gdal-config`` first on
``PATH`` or set ``GDAL_CONFIG`` to its absolute path. ``gdal-config --cflags``
and ``gdal-config --libs`` should refer to the same GDAL prefix.

Use ``isobands[gdal312]`` only with a native GDAL 3.12.2 installation. Plain
``pip install isobands`` does not install GDAL bindings.

macOS and Homebrew
~~~~~~~~~~~~~~~~~~

Homebrew users can install GDAL with:

.. code-block:: console

   $ brew install gdal
   $ "$(brew --prefix gdal)/bin/gdal-config" --version
   3.12.2

Keep the Homebrew ``gdal-config``, headers, and libraries together. If a
compiler reports missing ``gdal.h`` or linker symbols, check that
``GDAL_CONFIG`` points to the installed GDAL executable and that the compiler is using
the same Homebrew prefix. Remove stale ``GDAL_CONFIG`` settings from another
installation, and make sure the active Python architecture (for example,
arm64) matches the GDAL libraries. Reinstalling the Python binding after
correcting the prefix is safer than mixing cached build artifacts.

Windows
~~~~~~~

Use a conda-forge environment so the native GDAL runtime, headers, and
libraries are resolved as one compatible set. This is the same approach used
by the Windows CI smoke job:

.. code-block:: console

   conda create -n isobands python=3.13
   conda activate isobands
   conda install -c conda-forge gdal=3.10.2 geopandas numpy pyproj shapely xarray
   python -m pip install --no-deps isobands

Verify the Python environment imports ``osgeo.gdal`` and reports a supported
release before running the example or your application. Do not combine a
conda-forge GDAL runtime with unrelated system DLLs.

Install the package
-------------------

After the matching GDAL installation is active, choose its exact binding extra:

.. code-block:: console

   $ python -m pip install "isobands[gdal310]"

Contributor setup
-----------------

Clone the repository, activate a matching GDAL environment, and install its
development, test, benchmark, and documentation groups:

.. code-block:: console

   $ make install-test GDAL_BASELINE=310 GDAL_PYTHON="$(command -v python)"
   $ make test GDAL_BASELINE=310 GDAL_PYTHON="$(command -v python)"

``GDAL_BASELINE`` is ``310`` or ``312`` and controls the version check.
``GDAL_PYTHON`` directs test dependencies into an activated conda environment
that already provides matching GDAL bindings. To install only documentation
dependencies, use ``make install-docs``.
