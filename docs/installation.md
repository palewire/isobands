Installation
============

Exact GDAL prerequisite
-----------------------

The runtime requires **GDAL 3.12.2**, including the matching system
development headers and libraries. The PyPI ``GDAL`` distribution is
source-only: it compiles Python bindings against the system installation, and
``pip`` alone cannot provide that installation. Do not mix headers, libraries,
or Python bindings from another GDAL release.

Linux
~~~~~

Install the exact 3.12.2 runtime and development package from your
distribution's supported repository, or build GDAL 3.12.2 from source. Package
names vary by distribution; the important distinction is the runtime package
and its development package (headers, ``gdal-config``, and linkable libraries).
Then verify the selected development installation:

.. code-block:: console

   $ gdal-config --version
   3.12.2

If multiple GDAL installations exist, put the matching ``gdal-config`` first on
``PATH`` or set ``GDAL_CONFIG`` to its absolute path. ``gdal-config --cflags``
and ``gdal-config --libs`` should refer to the same 3.12.2 prefix.

macOS and Homebrew
~~~~~~~~~~~~~~~~~~

Homebrew users can install GDAL with:

.. code-block:: console

   $ brew install gdal
   $ "$(brew --prefix gdal)/bin/gdal-config" --version
   3.12.2

Keep the Homebrew ``gdal-config``, headers, and libraries together. If a
compiler reports missing ``gdal.h`` or linker symbols, check that
``GDAL_CONFIG`` points to the 3.12.2 executable and that the compiler is using
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
   conda install -c conda-forge gdal=3.12.2
   python -m pip install isobands

Verify the Python environment imports ``osgeo.gdal`` and reports release
``3.12.2`` before running the example or your application. Do not combine a
conda-forge GDAL runtime with unrelated system DLLs.

Install the package
-------------------

After the matching GDAL installation is active:

.. code-block:: console

   $ python -m pip install isobands

Contributor setup
-----------------

Clone the repository and install its locked development, test, benchmark, and
documentation groups:

.. code-block:: console

   $ make install

The ``make`` targets set ``UV_NO_ENV_FILE=1`` and verify ``gdal-config`` before
syncing dependencies. To install only documentation dependencies, use
``make install-docs``.
