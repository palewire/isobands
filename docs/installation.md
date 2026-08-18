Installation
============

GDAL prerequisite
-----------------

The supported exact baselines are **GDAL 3.10.2**, **3.11.5**, **3.12.2**, and
**3.13.2**. Each requires a matching ``osgeo.gdal`` Python binding. GDAL 3.13.2
is the recommended newest tested and installable baseline for a pip-managed
binding. GDAL 3.13.3 is not tested or supported.

If a Conda or system-managed environment already provides one of these
bindings, install isobands without an extra:

.. code-block:: console

   $ python -m pip install isobands

To install a binding through pip, select an exact extra and install matching
native GDAL development files first. The PyPI ``GDAL`` distribution compiles
against those headers and libraries, so do not mix GDAL releases.

.. list-table:: Pip binding selection
   :header-rows: 1

   * - GDAL version
     - Extra
     - Use
   * - 3.13.2
     - ``gdal313``
     - Recommended tested baseline
   * - 3.12.2
     - ``gdal312``
     - Tested compatibility baseline
   * - 3.11.5
     - ``gdal311``
     - Advanced compatibility baseline
   * - 3.10.2
     - ``gdal310``
     - Advanced compatibility baseline

Linux
~~~~~

Install a selected GDAL runtime and development package from your
distribution's repository or build it from source. Package names vary; you need
the runtime, headers, ``gdal-config``, and linkable libraries. Verify the
selected installation, then install its matching extra:

.. code-block:: console

   $ gdal-config --version
   3.13.2
   $ python -m pip install "isobands[gdal313]"

If multiple GDAL installations exist, put the matching ``gdal-config`` first on
``PATH`` or set ``GDAL_CONFIG`` to its absolute path. ``gdal-config --cflags``
and ``gdal-config --libs`` should refer to the same GDAL prefix.

macOS and Homebrew
~~~~~~~~~~~~~~~~~~

Homebrew users can install GDAL with:

.. code-block:: console

   $ brew install gdal
   $ "$(brew --prefix gdal)/bin/gdal-config" --version

Keep the Homebrew ``gdal-config``, headers, and libraries together. If a
compiler reports missing ``gdal.h`` or linker symbols, check that
``GDAL_CONFIG`` points to the installed GDAL executable and that the compiler is using
the same Homebrew prefix. Remove stale ``GDAL_CONFIG`` settings from another
installation, and make sure the active Python architecture (for example,
arm64) matches the GDAL libraries. Install a pip extra only when the reported
version exactly matches a supported baseline. Reinstalling the Python binding
after correcting the prefix is safer than mixing cached build artifacts.

Windows
~~~~~~~

Use a conda-forge environment so the native GDAL runtime, headers, and
libraries are resolved as one compatible set. This is the same approach used
by the Windows CI smoke job:

.. code-block:: console

   conda create -n isobands python=3.13
   conda activate isobands
   conda install -c conda-forge gdal=3.13.2 geopandas numpy pyproj shapely xarray
   python -m pip install --no-deps isobands

Verify the Python environment imports ``osgeo.gdal`` and reports a supported
release before running the example or your application. Do not combine a
conda-forge GDAL runtime with unrelated system DLLs.

Install the package
-------------------

After the matching GDAL installation is active, install without an extra when
the Python binding already exists:

.. code-block:: console

   $ python -m pip install isobands

When pip must build the binding, use the extra that matches the native GDAL
development installation:

.. code-block:: console

   $ python -m pip install "isobands[gdal313]"

Contributor setup
-----------------

Clone the repository, activate a matching GDAL environment, and install its
development, test, benchmark, and documentation groups:

.. code-block:: console

   $ make install-test GDAL_BASELINE=313 GDAL_PYTHON="$(command -v python)"
   $ make test GDAL_BASELINE=313 GDAL_PYTHON="$(command -v python)"

``GDAL_BASELINE`` is ``310``, ``311``, ``312``, or ``313`` and controls the
exact version check.
``GDAL_PYTHON`` directs test dependencies into an activated conda environment
that already provides matching GDAL bindings. To install only documentation
dependencies, use ``make install-docs``.
